from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from showdown_bot.battle.decision import choose_for_request, choose_with_fallback
from showdown_bot.client.connection import ShowdownConnection, authenticate, join_lobby
from showdown_bot.config import Settings
from showdown_bot.engine.belief.hypotheses import SpreadBook, load_spread_book
from showdown_bot.engine.belief.protect_priors import ProtectPriors, load_protect_priors
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.messages import parse_incoming, parse_message
from showdown_bot.team.pack import load_packed_team
from showdown_bot.team.spreads import our_spreads_from_packed

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")
_battle_logs: dict[str, Path] = {}
_last_rqid: dict[str, int] = {}
# Per-room accumulated raw protocol frames, used to rebuild BattleState each turn.
_room_raw: dict[str, list[str]] = {}
_active_format: str | None = None
_our_spreads: dict | None = None  # our own team's real spreads (Stage C)
_book_cache: dict[str, SpreadBook | None] = {}
_priors_cache: dict[str, ProtectPriors | None] = {}


def _get_book(format_id: str | None) -> SpreadBook | None:
    if not format_id:
        return None
    if format_id not in _book_cache:
        try:
            cfg = load_format_config(format_id)
            _book_cache[format_id] = load_spread_book(cfg.meta_path("default_spreads"))
        except Exception as exc:  # noqa: BLE001 - format may be unsupported (e.g. random)
            logger.info("no spread book for %s (%s); heuristic disabled", format_id, exc)
            _book_cache[format_id] = None
    return _book_cache[format_id]


def _get_priors(format_id: str | None) -> ProtectPriors | None:
    if not format_id:
        return None
    if format_id not in _priors_cache:
        try:
            cfg = load_format_config(format_id)
            _priors_cache[format_id] = load_protect_priors(cfg.meta_path("protect_priors"))
        except Exception:  # noqa: BLE001
            _priors_cache[format_id] = None
    return _priors_cache[format_id]


def _log_battle_line(room: str, raw: str) -> None:
    if not room.startswith("battle-"):
        return
    LOG_DIR.mkdir(exist_ok=True)
    if room not in _battle_logs:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _battle_logs[room] = LOG_DIR / f"{room}_{ts}.log"
    _battle_logs[room].open("a", encoding="utf-8").write(raw + "\n")


async def handle_battle_message(conn: ShowdownConnection, room: str, payload: str) -> None:
    req = BattleRequest.model_validate(json.loads(payload))
    if req.wait:
        # Opponent's turn; we've already locked in. Nothing to choose.
        return
    _last_rqid[room] = req.rqid

    book = _get_book(_active_format)
    state: BattleState | None = None
    if book is not None and not req.team_preview:
        try:
            state = BattleState.from_log_text("\n".join(_room_raw.get(room, [])))
            merge_request(req, state)
        except Exception as exc:  # noqa: BLE001 - never block a turn on state build
            logger.warning("state build failed in %s: %s", room, exc)
            state = None

    report: list[str] = []
    if book is not None:
        priors = _get_priors(_active_format)
        choose = choose_with_fallback(
            req, state=state, book=book, our_side=req.side.id, priors=priors, report=report,
            our_spreads=_our_spreads,
        )
    else:
        choose = choose_for_request(req)

    await conn.send(f"{room}|{choose}")
    kind = "team preview" if req.team_preview else "battle"
    logger.info("sent %s (%s)", choose, kind)
    if book is not None and not req.team_preview:
        _emit_turn_trace(room, report)


def _emit_turn_trace(room: str, report: list[str]) -> None:
    """Log a readable per-turn diagnostic (battle events + decision). Opt-out via
    SHOWDOWN_TURN_TRACE=0. Never raises -- diagnostics must not break the loop."""
    if os.environ.get("SHOWDOWN_TURN_TRACE", "1") == "0":
        return
    try:
        from showdown_bot.battle.diagnostics import format_turn_trace

        decision = "\n".join(report) if report else "(no decision report)"
        logger.info("turn trace %s:\n%s", room, format_turn_trace(_room_raw.get(room, []), decision))
    except Exception as exc:  # noqa: BLE001 - diagnostics are best-effort
        logger.debug("turn trace failed in %s: %s", room, exc)


async def _send_default_choose(conn: ShowdownConnection, room: str) -> None:
    rqid = _last_rqid.get(room)
    if rqid is None:
        return
    choose = f"/choose default|{rqid}"
    await conn.send(f"{room}|{choose}")
    logger.info("sent fallback %s", choose)


async def _run_battle_loop(
    conn: ShowdownConnection,
    max_battles: int,
    *,
    cancel_on_done: str | None = "|/cancelsearch",
) -> int:
    battles_finished = 0
    active_battles: set[str] = set()

    async for raw in conn.messages():
        parsed_list = list(parse_incoming(raw))
        for room in {p.room for p in parsed_list if p.room.startswith("battle-")}:
            _room_raw.setdefault(room, []).append(raw)
            _log_battle_line(room, raw)
        for parsed in parsed_list:
            if parsed.prefix == "popup" and parsed.args:
                popup = parsed.args[0]
                logger.warning("popup: %s", popup[:200])
                lower = popup.lower()
                if "not ladderable" in lower:
                    if cancel_on_done:
                        await conn.send(cancel_on_done)
                    await conn.close()
                    raise RuntimeError(popup)
                if "invalid team" in lower or "team was rejected" in lower:
                    if cancel_on_done:
                        await conn.send(cancel_on_done)
                    await conn.close()
                    raise RuntimeError(popup)

            if parsed.prefix == "pm" and parsed.args and "Invalid choice" in parsed.args[-1]:
                for battle_room in list(active_battles):
                    await _send_default_choose(conn, battle_room)
                continue

            if parsed.room.startswith("battle-"):
                if parsed.prefix == "error":
                    await _send_default_choose(conn, parsed.room)
                if parsed.prefix == "request":
                    await handle_battle_message(conn, parsed.room, parsed.payload)
                if parsed.prefix in ("win", "tie"):
                    if parsed.room in active_battles:
                        battles_finished += 1
                        active_battles.discard(parsed.room)
                        _room_raw.pop(parsed.room, None)
                        logger.info(
                            "battle ended in %s (%d/%d)",
                            parsed.room,
                            battles_finished,
                            max_battles,
                        )
                        if battles_finished >= max_battles:
                            if cancel_on_done:
                                await conn.send(cancel_on_done)
                            await conn.close()
                            return battles_finished
                if parsed.prefix == "init" and parsed.args and parsed.args[0] == "battle":
                    active_battles.add(parsed.room)
                    await conn.send(f"|/join {parsed.room}")
                    logger.info("battle started: %s", parsed.room)

        logger.debug("recv %s", raw[:160])

    return battles_finished


async def _connect_and_login(settings: Settings) -> ShowdownConnection:
    conn = ShowdownConnection(settings.server_url)
    await conn.connect()
    await authenticate(conn, settings)
    await join_lobby(conn)
    return conn


async def run_ladder_search(settings: Settings, max_battles: int = 1) -> int:
    global _active_format, _our_spreads
    _active_format = settings.format_id
    conn = await _connect_and_login(settings)
    packed_team = load_packed_team(settings.team_path)
    _our_spreads = our_spreads_from_packed(packed_team)
    await conn.send(f"|/utm {packed_team}")
    await asyncio.sleep(0.3)
    await conn.send(f"|/search {settings.format_id}")
    logger.info("searching ladder format=%s", settings.format_id)
    return await _run_battle_loop(conn, max_battles, cancel_on_done="|/cancelsearch")


async def run_challenge(
    settings: Settings,
    opponent: str,
    max_battles: int = 1,
) -> int:
    """Challenge a player (use when VGC ladder is closed)."""
    global _active_format, _our_spreads
    _active_format = settings.format_id
    conn = await _connect_and_login(settings)
    packed_team = load_packed_team(settings.team_path)
    _our_spreads = our_spreads_from_packed(packed_team)
    await conn.send(f"|/utm {packed_team}")
    await asyncio.sleep(0.3)
    await conn.send(f"|/challenge {opponent}, {settings.format_id}")
    logger.info("challenged %s format=%s", opponent, settings.format_id)
    return await _run_battle_loop(conn, max_battles, cancel_on_done=None)


async def run_smoke_battle(settings: Settings) -> int:
    """End-to-end smoke test using random doubles (no custom team)."""
    conn = await _connect_and_login(settings)
    smoke_settings = Settings(
        username=settings.username,
        password=settings.password,
        server_url=settings.server_url,
        team_path=settings.team_path,
        format_id="gen9randomdoublesbattle",
        auth_login_url=settings.auth_login_url,
        auth_guest_url=settings.auth_guest_url,
    )
    await conn.send("|/utm null")
    await asyncio.sleep(0.2)
    await conn.send(f"|/search {smoke_settings.format_id}")
    logger.info("smoke search format=%s", smoke_settings.format_id)
    return await _run_battle_loop(conn, 1, cancel_on_done="|/cancelsearch")

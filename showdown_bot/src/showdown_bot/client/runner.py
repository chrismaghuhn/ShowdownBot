from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from showdown_bot.battle.decision import choose_for_request
from showdown_bot.client.connection import ShowdownConnection, authenticate, join_lobby
from showdown_bot.config import Settings
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.messages import parse_incoming, parse_message
from showdown_bot.team.pack import load_packed_team

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")
_battle_logs: dict[str, Path] = {}
_last_rqid: dict[str, int] = {}


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
    _last_rqid[room] = req.rqid
    choose = choose_for_request(req)
    await conn.send(f"{room}|{choose}")
    kind = "team preview" if req.team_preview else "battle"
    logger.info("sent %s (%s)", choose, kind)


async def _send_default_choose(conn: ShowdownConnection, room: str) -> None:
    rqid = _last_rqid.get(room)
    if rqid is None:
        return
    choose = f"/choose default #{rqid}"
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
        for parsed in parse_incoming(raw):
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
                _log_battle_line(parsed.room, raw)
                if parsed.prefix == "error":
                    await _send_default_choose(conn, parsed.room)
                if parsed.prefix == "request":
                    await handle_battle_message(conn, parsed.room, parsed.payload)
                if parsed.prefix in ("win", "tie"):
                    if parsed.room in active_battles:
                        battles_finished += 1
                        active_battles.discard(parsed.room)
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
    conn = await _connect_and_login(settings)
    packed_team = load_packed_team(settings.team_path)
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
    conn = await _connect_and_login(settings)
    packed_team = load_packed_team(settings.team_path)
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

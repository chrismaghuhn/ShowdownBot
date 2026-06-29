from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from showdown_bot.battle.decision import choose_for_request, choose_with_fallback
from showdown_bot.client.connection import (
    ShowdownConnection,
    authenticate_local,
)
from showdown_bot.engine.belief.hypotheses import SpreadBook, load_spread_book
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.messages import parse_incoming
from showdown_bot.team.pack import load_packed_team

logger = logging.getLogger(__name__)

LOCAL_SERVER = "ws://localhost:8000/showdown/websocket"


def agent_choose(
    agent: str,
    req: BattleRequest,
    *,
    state: BattleState | None,
    book: SpreadBook | None,
    our_side: str | None,
    priors=None,
) -> str:
    """Pure per-request dispatch shared by both gauntlet clients (unit-testable).

    ``heuristic`` uses the full fallback chain; ``max_damage`` uses the baseline
    via the fallback chain; ``random`` uses the legacy random agent.
    """
    if agent == "random" or state is None or book is None:
        return choose_for_request(req)
    if agent == "max_damage":
        from showdown_bot.battle.baselines import max_damage_choice

        try:
            return max_damage_choice(req, state=state, book=book, our_side=our_side)
        except Exception:  # noqa: BLE001
            return choose_for_request(req)
    return choose_with_fallback(req, state=state, book=book, our_side=our_side, priors=priors)


@dataclass
class GauntletStats:
    games: int = 0
    hero_wins: int = 0
    villain_wins: int = 0
    ties: int = 0
    invalid_choices: int = 0
    crashes: int = 0
    latencies: list[float] = field(default_factory=list)

    @property
    def winrate(self) -> float:
        return self.hero_wins / self.games if self.games else 0.0

    def latency_p95(self) -> float:
        if not self.latencies:
            return 0.0
        ordered = sorted(self.latencies)
        idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
        return ordered[idx]


class _Client:
    """One gauntlet bot: per-room state, agent dispatch, challenge handling."""

    def __init__(self, conn, name, agent, *, book, priors, format_id, packed_team):
        self.conn = conn
        self.name = name
        self.agent = agent
        self.book = book
        self.priors = priors
        self.format_id = format_id
        self.packed_team = packed_team
        self.room_raw: dict[str, list[str]] = {}
        self.latencies: list[float] = []
        self.invalid = 0
        self.crashes = 0

    def _state_for(self, room: str, req: BattleRequest) -> BattleState | None:
        if self.book is None or req.team_preview:
            return None
        try:
            st = BattleState.from_log_text("\n".join(self.room_raw.get(room, [])))
            merge_request(req, st)
            return st
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] state build failed: %s", self.name, exc)
            return None

    async def set_team(self) -> None:
        await self.conn.send(f"|/utm {self.packed_team}" if self.packed_team else "|/utm null")

    async def handle_request(self, room: str, payload: str) -> None:
        req = BattleRequest.model_validate(json.loads(payload))
        state = self._state_for(room, req)
        start = time.perf_counter()
        try:
            choose = agent_choose(
                self.agent, req, state=state, book=self.book,
                our_side=req.side.id, priors=self.priors,
            )
        except Exception as exc:  # noqa: BLE001 - last-ditch, keep the battle alive
            logger.warning("[%s] agent crashed: %s", self.name, exc)
            self.crashes += 1
            choose = f"/choose default #{req.rqid}"
        self.latencies.append(time.perf_counter() - start)
        await self.conn.send(f"{room}|{choose}")


async def _run_client(
    client: _Client,
    *,
    accept_from: str | None,
    on_result,
    stop: asyncio.Event,
) -> None:
    await client.set_team()
    try:
        async for raw in client.conn.messages():
            if stop.is_set():
                break
            parsed_list = list(parse_incoming(raw))
            for room in {p.room for p in parsed_list if p.room.startswith("battle-")}:
                client.room_raw.setdefault(room, []).append(raw)
            for parsed in parsed_list:
                if parsed.prefix == "pm" and parsed.args and accept_from:
                    text = parsed.args[-1]
                    if "/challenge" in text and accept_from.lower() in (parsed.args[0] or "").lower():
                        await client.conn.send(f"|/accept {accept_from}")
                if parsed.prefix == "pm" and parsed.args and "Invalid choice" in parsed.args[-1]:
                    client.invalid += 1
                if parsed.room.startswith("battle-"):
                    if parsed.prefix == "init" and parsed.args and parsed.args[0] == "battle":
                        await client.conn.send(f"|/join {parsed.room}")
                    if parsed.prefix == "error" and "choice" in (parsed.args[0] if parsed.args else "").lower():
                        client.invalid += 1
                    if parsed.prefix == "request":
                        await client.handle_request(parsed.room, parsed.payload)
                    if parsed.prefix in ("win", "tie"):
                        winner = parsed.args[0].strip() if (parsed.prefix == "win" and parsed.args) else None
                        client.room_raw.pop(parsed.room, None)
                        if on_result is not None:
                            await on_result(winner)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] client loop error: %s", client.name, exc)


async def run_local_gauntlet(
    *,
    games: int,
    hero_agent: str = "heuristic",
    villain_agent: str = "max_damage",
    format_id: str,
    team_path: str,
    server_url: str = LOCAL_SERVER,
    hero_name: str = "HeuristicBot",
    villain_name: str = "BaselineBot",
) -> GauntletStats:
    """Play ``games`` battles between two local bots and return aggregate stats.

    Requires a local ``node pokemon-showdown start --no-security`` server.
    """
    book = None
    priors = None
    try:
        cfg = load_format_config(format_id)
        book = load_spread_book(cfg.meta_path("default_spreads"))
        from showdown_bot.engine.belief.protect_priors import load_protect_priors

        priors = load_protect_priors(cfg.meta_path("protect_priors"))
    except Exception:  # noqa: BLE001
        pass
    packed = ""
    try:
        packed = load_packed_team(team_path)
    except Exception:  # noqa: BLE001
        packed = ""

    hero_conn = ShowdownConnection(server_url)
    villain_conn = ShowdownConnection(server_url)
    await hero_conn.connect()
    await villain_conn.connect()
    await authenticate_local(hero_conn, hero_name)
    await authenticate_local(villain_conn, villain_name)

    hero = _Client(hero_conn, hero_name, hero_agent, book=book, priors=priors, format_id=format_id, packed_team=packed)
    villain = _Client(villain_conn, villain_name, villain_agent, book=book, priors=priors, format_id=format_id, packed_team=packed)

    stats = GauntletStats()
    stop = asyncio.Event()
    next_game = asyncio.Event()
    next_game.set()  # allow first challenge

    async def on_hero_result(winner):
        stats.games += 1
        if winner is None:
            stats.ties += 1
        elif winner.lower().startswith(hero_name.lower()[:6]):
            stats.hero_wins += 1
        else:
            stats.villain_wins += 1
        logger.info("game %d/%d done (winner=%s)", stats.games, games, winner)
        if stats.games >= games:
            stop.set()
        else:
            next_game.set()

    hero_task = asyncio.create_task(
        _run_client(hero, accept_from=None, on_result=on_hero_result, stop=stop)
    )
    villain_task = asyncio.create_task(
        _run_client(villain, accept_from=hero_name, on_result=None, stop=stop)
    )

    async def challenger():
        await villain.set_team()
        await asyncio.sleep(0.5)
        while not stop.is_set():
            await next_game.wait()
            next_game.clear()
            if stop.is_set():
                break
            await hero.set_team()
            await asyncio.sleep(0.2)
            await hero_conn.send(f"|/challenge {villain_name}, {format_id}")
            await asyncio.sleep(0.2)

    chal_task = asyncio.create_task(challenger())

    try:
        await asyncio.wait_for(stop.wait(), timeout=max(60.0, games * 30.0))
    except asyncio.TimeoutError:
        logger.warning("gauntlet timed out")
        stop.set()
    finally:
        for t in (chal_task, hero_task, villain_task):
            t.cancel()
        await hero_conn.close()
        await villain_conn.close()

    stats.latencies = hero.latencies
    stats.invalid_choices = hero.invalid + villain.invalid
    stats.crashes = hero.crashes + villain.crashes
    return stats

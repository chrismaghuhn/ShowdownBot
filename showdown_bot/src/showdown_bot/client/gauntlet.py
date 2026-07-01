from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import time
from dataclasses import dataclass, field

from showdown_bot.battle.decision import choose_for_request, choose_with_fallback
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.client.connection import (
    ShowdownConnection,
    authenticate_local,
)
from showdown_bot.engine.belief.hypotheses import SpreadBook, load_opp_sets_for_format, load_spread_book
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.learning.export_runtime import DatasetExportRuntime
from showdown_bot.learning.reranker_shadow import RerankerShadowRuntime
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.messages import parse_incoming
from showdown_bot.team.pack import load_packed_team
from showdown_bot.team.spreads import our_spreads_from_packed

logger = logging.getLogger(__name__)

LOCAL_SERVER = "ws://localhost:8000/showdown/websocket"

# Race conditions, not bad choices: the server rejects a choice we sent for a
# turn that already resolved. These are harmless (the rqid guard protects us) so
# they must not count against the strict invalid-choice criterion.
_BENIGN_CHOICE_ERRORS = ("too late", "nothing to choose")


def _is_real_invalid(text: str | None) -> bool:
    low = (text or "").lower()
    if "invalid choice" not in low and "can't" not in low:
        return False
    return not any(b in low for b in _BENIGN_CHOICE_ERRORS)


def agent_choose(
    agent: str,
    req: BattleRequest,
    *,
    state: BattleState | None,
    book: SpreadBook | None,
    our_side: str | None,
    priors=None,
    report: list[str] | None = None,
    our_spreads: dict | None = None,
    opp_sets: dict | None = None,
    trace=None,
) -> str:
    """Pure per-request dispatch shared by both gauntlet clients (unit-testable).

    ``heuristic`` uses the full fallback chain; ``max_damage`` uses the baseline
    via the fallback chain; ``random`` uses the legacy random agent. ``report``
    (heuristic only) collects a readable decision block for the turn trace.
    """
    # Eval-only opponent policies (T3c): request-only + deterministic, no state/book needed.
    # Local imports keep eval/opponents off the default/import path (live-path guard).
    if agent == "greedy_protect":
        from showdown_bot.eval.opponents.policies import greedy_protect_choice
        return greedy_protect_choice(req)
    if agent == "simple_heuristic":
        from showdown_bot.eval.opponents.policies import simple_heuristic_choice
        return simple_heuristic_choice(req)
    if agent == "scripted_vgc":
        from showdown_bot.eval.opponents.scripted_vgc import scripted_vgc_choice
        return scripted_vgc_choice(req)
    if agent == "random" or state is None or book is None:
        return choose_for_request(req)
    if agent == "max_damage":
        from showdown_bot.battle.baselines import max_damage_choice

        # Eval-deterministic (T3c): paired seed comparison needs a deterministic opponent,
        # so max_damage's rare fallbacks use `/choose default` (not pick_random_pair). The
        # live path (decision.py) calls max_damage_choice with the default fallback -> unchanged.
        try:
            return max_damage_choice(
                req, state=state, book=book, our_side=our_side,
                fallback=lambda r: f"/choose default|{r.rqid}",
            )
        except Exception:  # noqa: BLE001
            return f"/choose default|{req.rqid}"
    return choose_with_fallback(
        req, state=state, book=book, our_side=our_side, priors=priors, report=report,
        our_spreads=our_spreads, opp_sets=opp_sets, trace=trace,
    )


def _latency_p95(latencies) -> float:
    if not latencies:
        return 0.0
    ordered = sorted(latencies)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[idx]


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
        return _latency_p95(self.latencies)


class _Client:
    """One gauntlet bot: per-room state, agent dispatch, challenge handling."""

    def __init__(self, conn, name, agent, *, book, priors, format_id, packed_team, trace=False, opp_sets=None):
        self.conn = conn
        self.name = name
        self.agent = agent
        self.book = book
        self.priors = priors
        self.format_id = format_id
        self.packed_team = packed_team
        # Real own-team spreads (Stage C), default on. SHOWDOWN_REAL_SPREADS=0
        # falls back to the worst-case proxy (OUR_DEF_PRESET) for a clean A/B.
        _real = os.environ.get("SHOWDOWN_REAL_SPREADS", "1") != "0"
        self.our_spreads = our_spreads_from_packed(packed_team) if (packed_team and _real) else None
        self.opp_sets = opp_sets
        self.trace = trace
        self.room_raw: dict[str, list[str]] = {}
        self.last_choose: dict[str, str] = {}
        self.last_request: dict[str, str] = {}
        self.latencies: list[float] = []
        self.invalid = 0
        self.crashes = 0
        # Dataset export seam — None when SHOWDOWN_DATASET_EXPORT is unset (bit-identical path).
        # Thread calc/book/our_spreads/opp_sets/dex/move_meta so rollout mode can reuse
        # the gauntlet's already-built deps (avoids a second CalcClient).
        # In rollout mode from_env builds CalcClient/oracle/speed_oracle from these;
        # in stub mode (default) they are ignored.
        self._export = DatasetExportRuntime.from_env(
            format_id=self.format_id,
            packed_team=self.packed_team,
            mirror_flag=False,
            dex=None,
            move_meta=None,
            book=self.book,
            our_spreads=self.our_spreads,
            opp_sets=self.opp_sets,
            priors=self.priors,
        )
        # Reranker Shadow Mode seam (slice 2b-3a) — None when SHOWDOWN_RERANKER_SHADOW is unset
        # (bit-identical path). Pass the export's provenance so shadow IDs join the export dataset.
        # RerankerShadowRuntime does NOT import lightgbm at module scope; only from_env does, when
        # enabled — so the module-top import above keeps the disabled path lightgbm-free.
        _prov = None
        if self._export is not None:
            _prov = {"git_sha": self._export.git_sha, "dirty_flag": self._export.dirty_flag,
                     "team_hash": self._export.team_hash_, "config_hash": self._export.config_hash_,
                     "run_seed": self._export.run_seed}
        self._shadow = RerankerShadowRuntime.from_env(
            format_id=format_id, packed_team=packed_team, provenance=_prov)

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
        if req.wait:
            # Opponent's turn; we've already locked in. Nothing to choose.
            return
        self.last_request[room] = payload
        state = self._state_for(room, req)
        report: list[str] | None = [] if (self.trace and self.agent == "heuristic") else None
        # Build a DecisionTrace only when export OR shadow is enabled and the heuristic is active.
        # With both seams off (self._export is None and self._shadow is None) -> trace_obj=None
        # (bit-identical path — no trace is constructed, choose is unaffected).
        trace_obj = DecisionTrace() if (
            (self._export is not None or self._shadow is not None)
            and self.agent == "heuristic" and state is not None) else None
        start = time.perf_counter()
        try:
            choose = agent_choose(
                self.agent, req, state=state, book=self.book,
                our_side=req.side.id, priors=self.priors, report=report,
                our_spreads=self.our_spreads, opp_sets=self.opp_sets, trace=trace_obj,
            )
        except Exception as exc:  # noqa: BLE001 - last-ditch, keep the battle alive
            logger.warning("[%s] agent crashed: %s", self.name, exc)
            self.crashes += 1
            choose = f"/choose default|{req.rqid}"
            trace_obj = None  # discard partial trace on crash
        self.latencies.append(time.perf_counter() - start)
        self.last_choose[room] = choose
        await self.conn.send(f"{room}|{choose}")
        # Export observe: only when trace was built (export enabled, heuristic, non-preview).
        if self._export is not None and trace_obj is not None and not req.team_preview:
            try:
                self._export.observe(
                    trace=trace_obj, state=state, request=req,
                    turn_number=getattr(state, "turn", 0),
                    our_side=req.side.id or "p1",
                )
            except Exception as exc:  # noqa: BLE001 - export is best-effort; never stall the battle
                logger.debug("[%s] export observe failed: %s", self.name, exc)
        # Reranker Shadow observe: post-send, bounded, off the event loop (single-worker executor),
        # LOG-ONLY. SAME condition as export so shadow decision indices stay in lockstep with the
        # export dataset. choose is already computed + sent above; this never mutates it.
        if self._shadow is not None and trace_obj is not None and not req.team_preview:   # SAME cond as export
            sh = self._shadow
            decision_index = sh._decision_local_index
            sh.bump_decision_index()                          # advance synchronously, lockstep with export
            if sh.inflight is not None and not sh.inflight.done():
                logger.debug("[%s] shadow busy -> skip (index kept in lockstep)", self.name)
            else:
                fut = asyncio.get_running_loop().run_in_executor(
                    sh.executor, functools.partial(
                        sh.observe_shadow, trace=trace_obj, state=state, request=req, choose=choose,
                        turn_number=getattr(state, "turn", 0), our_side=req.side.id or "p1",
                        decision_index=decision_index))
                sh.inflight = fut
                try:
                    await asyncio.wait_for(asyncio.shield(fut), timeout=sh.timeout_ms / 1000)
                except asyncio.TimeoutError:
                    logger.debug("[%s] shadow scoring exceeded %dms; 1-worker executor caps orphans at 1",
                                 self.name, sh.timeout_ms)
                except Exception as exc:  # noqa: BLE001 - best-effort; never stall the battle
                    logger.debug("[%s] shadow observe failed: %s", self.name, exc)
        if report is not None and not req.team_preview:
            try:
                from showdown_bot.battle.diagnostics import format_turn_trace

                decision = "\n".join(report) if report else "(no decision report)"
                logger.info(
                    "[%s] %s", self.name, format_turn_trace(self.room_raw.get(room, []), decision)
                )
            except Exception as exc:  # noqa: BLE001 - diagnostics are best-effort
                logger.debug("[%s] trace failed: %s", self.name, exc)


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
                # Never let a single bad frame kill the loop and stall the game.
                try:
                    if parsed.prefix == "pm" and parsed.args and accept_from:
                        # Challenge PM: |pm| sender| receiver|/challenge <format>|...
                        # "/challenge" is not in the trailing arg, so scan all args.
                        joined = "|".join(a or "" for a in parsed.args)
                        sender = (parsed.args[0] or "").strip().lower()
                        if "/challenge" in joined and accept_from.lower() in sender:
                            await client.conn.send(f"|/accept {accept_from}")
                    if parsed.prefix == "pm" and parsed.args and _is_real_invalid(parsed.args[-1]):
                        client.invalid += 1
                    if parsed.room.startswith("battle-"):
                        if parsed.prefix == "init" and parsed.args and parsed.args[0] == "battle":
                            await client.conn.send(f"|/join {parsed.room}")
                            if client._export is not None:
                                client._export.start_game()
                            if client._shadow is not None:
                                client._shadow.start_game()
                        if parsed.prefix == "error":
                            err_text = parsed.args[0] if parsed.args else ""
                            if _is_real_invalid(err_text):
                                client.invalid += 1
                                logger.warning(
                                    "[%s] INVALID CHOICE in %s: server=%r | sent=%r | request=%s",
                                    client.name, parsed.room, err_text,
                                    client.last_choose.get(parsed.room),
                                    client.last_request.get(parsed.room, "")[:400],
                                )
                        if parsed.prefix == "request":
                            await client.handle_request(parsed.room, parsed.payload)
                        if parsed.prefix in ("win", "tie"):
                            winner = parsed.args[0].strip() if (parsed.prefix == "win" and parsed.args) else None
                            # Snapshot frames BEFORE pop (T2 result parse + T1a dump both need them).
                            room_frames = list(client.room_raw.get(parsed.room, []))
                            room_raw_path = None
                            # T1a seed-proof: env-gated raw dump. Unset -> no-op (bit-identical path).
                            _dump_dir = os.environ.get("SHOWDOWN_ROOM_RAW_DUMP")
                            if _dump_dir:
                                try:
                                    from showdown_bot.eval.room_dump import dump_room_raw

                                    room_raw_path = dump_room_raw(_dump_dir, client.name, parsed.room, room_frames)
                                except Exception as exc:  # noqa: BLE001 - diagnostic dump is best-effort
                                    logger.debug("[%s] room_raw dump failed: %s", client.name, exc)
                            client.room_raw.pop(parsed.room, None)
                            if client._export is not None:
                                client._export.flush()
                            if on_result is not None:
                                await on_result(winner, room_frames, room_raw_path)
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    logger.warning("[%s] frame error (%s): %s", client.name, parsed.prefix, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] client loop error: %s", client.name, exc)


def _resolve_side_teams(team_path, opp_team_path=None):
    """Return ``(hero_packed, villain_packed)`` for the gauntlet.

    ``opp_team_path=None`` -> **mirror** (villain gets the hero's packed team; the
    original single-team behavior). A distinct ``opp_team_path`` -> non-mirror (T1c).
    Load failures degrade to ``""`` (same tolerance as the original single-team path).
    """
    def _load(path):
        try:
            return load_packed_team(path)
        except Exception:  # noqa: BLE001
            return ""

    hero_packed = _load(team_path)
    villain_packed = _load(opp_team_path) if opp_team_path else hero_packed
    return hero_packed, villain_packed


def _end_hp_diff(parsed, hero_name, villain_name):
    """Hero-side HP sum − villain-side HP sum, via the |player| slot map. None if unreliable."""
    hp = parsed.get("hp_by_slot")
    players = parsed.get("players") or {}
    if not hp:
        return None
    slot_of = {name: slot for slot, name in players.items()}
    hs, vs = slot_of.get(hero_name), slot_of.get(villain_name)
    if hs not in ("p1", "p2") or vs not in ("p1", "p2") or hs == vs:
        return None  # side mapping unreliable -> null, never a blind p1-p2 (T2 Fix 2)
    return round(hp[hs] - hp[vs], 6)


def _battle_result_record(hero_name, villain_name, frames, *, invalid_choices, crashes,
                          decision_latency_p95_ms, room_raw_path):
    """Assemble the battle-derived T2 fields with EXPLICIT hero/villain/tie mapping (Fix 2).

    Unknown winner -> ResultRowError (never guessed). ``end_hp_diff`` is hero-side minus
    villain-side, or None if the |player| slot mapping is unreliable.
    """
    from showdown_bot.eval.battle_parse import parse_battle_result
    from showdown_bot.eval.result_jsonl import ResultRowError

    p = parse_battle_result(frames)
    if p["is_tie"]:
        winner = "tie"
    elif p["winner_name"] == hero_name:
        winner = "hero"
    elif p["winner_name"] == villain_name:
        winner = "villain"
    else:
        raise ResultRowError(
            f"winner {p['winner_name']!r} matches neither hero {hero_name!r} nor villain {villain_name!r}"
        )
    return {
        "winner": winner,
        "turns": p["turns"],
        "end_hp_diff": _end_hp_diff(p, hero_name, villain_name),
        "invalid_choices": invalid_choices,
        "crashes": crashes,
        "decision_latency_p95_ms": decision_latency_p95_ms,
        "room_raw_path": room_raw_path,
    }


async def run_local_gauntlet(
    *,
    games: int,
    hero_agent: str = "heuristic",
    villain_agent: str = "max_damage",
    format_id: str,
    team_path: str,
    opp_team_path: str | None = None,
    server_url: str = LOCAL_SERVER,
    hero_name: str = "HeuristicBot",
    villain_name: str = "BaselineBot",
    on_battle_result=None,
) -> GauntletStats:
    """Play ``games`` battles between two local bots and return aggregate stats.

    ``opp_team_path`` (T1c): when given, the villain fields a **different** packed team
    (non-mirror); default ``None`` keeps the mirror behavior. ``on_battle_result`` (T2):
    when given, a callback is fired once per battle with the assembled battle record
    (default ``None`` -> no behavior change). Requires a local
    ``node pokemon-showdown start --no-security`` server.
    """
    book = None
    priors = None
    opp_sets = {}
    try:
        cfg = load_format_config(format_id)
        book = load_spread_book(cfg.meta_path("default_spreads"))
        from showdown_bot.engine.belief.protect_priors import load_protect_priors

        priors = load_protect_priors(cfg.meta_path("protect_priors"))
    except Exception:  # noqa: BLE001
        pass
    opp_sets = load_opp_sets_for_format(format_id)
    hero_packed, villain_packed = _resolve_side_teams(team_path, opp_team_path)

    # Unique names per run so a killed run's lingering battles aren't rejoined
    # (with --no-security, /trn re-attaches to the same user and its open games).
    import random

    suffix = f"{random.randint(1000, 9999)}"
    hero_name = f"{hero_name}{suffix}"
    villain_name = f"{villain_name}{suffix}"

    hero_conn = ShowdownConnection(server_url)
    villain_conn = ShowdownConnection(server_url)
    await hero_conn.connect()
    await villain_conn.connect()
    await authenticate_local(hero_conn, hero_name)
    await authenticate_local(villain_conn, villain_name)

    trace = os.environ.get("SHOWDOWN_TURN_TRACE", "0") == "1"
    hero = _Client(hero_conn, hero_name, hero_agent, book=book, priors=priors, format_id=format_id, packed_team=hero_packed, trace=trace, opp_sets=opp_sets)
    villain = _Client(villain_conn, villain_name, villain_agent, book=book, priors=priors, format_id=format_id, packed_team=villain_packed, opp_sets=opp_sets)

    stats = GauntletStats()
    stop = asyncio.Event()
    next_game = asyncio.Event()
    next_game.set()  # allow first challenge

    async def on_hero_result(winner, room_frames=None, room_raw_path=None):
        stats.games += 1
        if winner is None:
            stats.ties += 1
        elif winner.lower().startswith(hero_name.lower()[:6]):
            stats.hero_wins += 1
        else:
            stats.villain_wins += 1
        logger.info("game %d/%d done (winner=%s)", stats.games, games, winner)
        # T2 per-battle result: build + emit the record (games=1/row -> run stats == battle stats).
        # Best-effort: a bad record is logged, never stalls progression; a missing row then trips
        # the runner's row-count == len(rows) check (fail-fast at the end).
        if on_battle_result is not None and room_frames is not None:
            try:
                record = _battle_result_record(
                    hero.name, villain.name, room_frames,
                    invalid_choices=hero.invalid + villain.invalid,
                    crashes=hero.crashes + villain.crashes,
                    decision_latency_p95_ms=round(_latency_p95(hero.latencies) * 1000),
                    room_raw_path=room_raw_path,
                )
                on_battle_result(record)
            except Exception as exc:  # noqa: BLE001 - never stall the run; runner row-count catches it
                logger.warning("[battle-result] record/emit failed: %s", exc)
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
        # VGC games run ~15-25 turns and each decision can take a couple seconds
        # (Node calc per turn), so budget generously per game.
        await asyncio.wait_for(stop.wait(), timeout=max(180.0, games * 150.0))
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

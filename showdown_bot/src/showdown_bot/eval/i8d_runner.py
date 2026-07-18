"""I8-D live-latency exposure/cap runner and verdict (design §5, plan §5.1–5.4).

The runner drives the FIXED I8-D schedule battle-by-battle, stops on the exposure floor or a cap
(never mid-battle), and — only once the run has stopped — computes the p95 of active foe-Mega
decisions and renders the three-way verdict. It starts a real server and plays real battles when
invoked; this module only BUILDS that harness. ``measured_ms`` is never an input to the stop rule.
"""
from __future__ import annotations

import json
import os

from showdown_bot.eval.decision_profile import (
    DecisionProfileWriter,
    LiveProfileContext,
    is_active_valid_live_row,
    validate_live_profile_dataset,
)
from showdown_bot.eval.gates import load_latency_budget_ms
from showdown_bot.eval.i8d_schedule import I8D_MAX_BATTLES, I8D_SEED_BASE, build_i8d_schedule

# --- CLOSED numbers -- not chosen here, referenced. D-1 floor (design §5.4), D-2 caps (§4.1). ---
I8D_MIN_ACTIVE_DECISIONS = 60          # ≥ 60 valid active foe-Mega decisions
I8D_MIN_DISTINCT_BATTLES = 20          # from ≥ 20 distinct battle_id
I8D_MAX_SCORED_DECISIONS = 2000        # D-2 decision cap (I8D_MAX_BATTLES=200 lives in i8d_schedule)

INCONCLUSIVE_MESSAGE = "INCONCLUSIVE — exposure floor not met"


class I8DRunError(RuntimeError):
    """The live gate cannot start or continue safely (e.g. a restart would merge a partial run)."""


def exposure_floor_met(active_valid: int, distinct_battles: int) -> bool:
    """D-1, both minima. A precondition evaluated BEFORE any p95 (§5.2); neither may be lowered
    to rescue a run."""
    return active_valid >= I8D_MIN_ACTIVE_DECISIONS and distinct_battles >= I8D_MIN_DISTINCT_BATTLES


def should_stop(*, battles_played: int, scored_decisions: int, active_valid: int,
                distinct_battles: int) -> tuple[bool, str | None]:
    """Plan §5.1's stop rule, in its order: D-1 floor first (the good stop), then the two caps.
    Evaluated by the runner ONLY after a fully-completed, validated battle. There is deliberately
    no latency parameter -- ``measured_ms`` is never a stop input (not a threshold, not a trend,
    not a "looks fine, stop early")."""
    if exposure_floor_met(active_valid, distinct_battles):
        return True, "exposure_floor_met"
    if battles_played >= I8D_MAX_BATTLES:
        return True, "max_battles"
    if scored_decisions >= I8D_MAX_SCORED_DECISIONS:
        return True, "max_scored_decisions"
    return False, None


def i8d_active_p95_ms(measured_values) -> float:
    """The p95 of active-decision ``measured_ms``, as the SAME nearest-rank statistic the
    per-battle gate applies (``gauntlet._latency_p95``) -- reused, not re-derived, so the verdict
    p95 and the gate p95 can never drift (design §5.4). Returns the raw float ms (no rounding):
    the budget comparison is on ``measured_ms`` directly, and rounding would move the > 1000 ms
    boundary."""
    from showdown_bot.client.gauntlet import _latency_p95
    return _latency_p95(list(measured_values))


def i8d_verdict(*, active_valid: int, distinct_battles: int, active_measured_ms,
                budget_ms: int) -> dict:
    """The §5.2 verdict. The floor is a precondition: the p95 is computed and gate-compared ONLY
    when the floor is met. A run that misses the floor is INCONCLUSIVE and reports no gate p95
    (``p95_ms=None``); its exposure p95 may still be surfaced elsewhere, explicitly not a gate
    value."""
    met = exposure_floor_met(active_valid, distinct_battles)
    base = {
        "exposure_floor_met": met,
        "min_active_decisions": I8D_MIN_ACTIVE_DECISIONS,
        "min_distinct_battles": I8D_MIN_DISTINCT_BATTLES,
        "budget_ms": budget_ms,
    }
    if not met:
        return {**base, "verdict": INCONCLUSIVE_MESSAGE, "p95_ms": None, "p95_is_gate_value": False}
    p95 = i8d_active_p95_ms(active_measured_ms)
    return {**base, "verdict": "PASS" if p95 <= budget_ms else "FAIL",
            "p95_ms": p95, "p95_is_gate_value": True}


def _active_measured_ms(profile_out: str) -> list[float]:
    """The ``measured_ms`` of every ACTIVE valid row in the frozen dataset (the verdict
    population). Active rows are ``outcome == "ok"``, so each carries a finite ``measured_ms``."""
    out: list[float] = []
    with open(profile_out, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if is_active_valid_live_row(row):
                out.append(row["measured_ms"])
    return out


def _write_json_atomic(path: str, obj: dict) -> None:
    """Stage the verdict via a temp file + ``os.replace`` so a reader never sees a partial
    verdict. LF-stable (``newline=""`` + explicit ``"\n"``), sorted keys for byte-determinism."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(obj, sort_keys=True, indent=2) + "\n")
    os.replace(tmp, path)


def build_i8d_live_schedule(panel_path: str, *, n_battles: int = I8D_MAX_BATTLES,
                            teams_root: str = "."):
    """Bind the fixed I8-D schedule (all seeds materialised, frozen in ``schedule_hash``) BEFORE
    the first battle. Thin wrapper over ``load_panel`` + ``build_i8d_schedule``; held-out teams
    are excluded and ``seed_index=i`` is bound immutably to row ``i`` by ``build_i8d_schedule``."""
    from showdown_bot.eval.panel import load_panel
    panel = load_panel(panel_path, teams_root=teams_root)
    return build_i8d_schedule(panel, n_battles=n_battles, teams_root=teams_root)


def run_i8d_live_gate(*, schedule, profile_out: str, verdict_out: str, config_hash: str,
                      git_sha: str, calc_backend: str = "oneshot", hero_agent: str = "heuristic",
                      seed_base: str = I8D_SEED_BASE) -> dict:
    """Drive the (already-bound) ``schedule`` with whole-battle stop and render the verdict.

    Restart-from-seed-0-no-merge: refuses a non-empty ``profile_out`` or ``verdict_out``; a run
    restarted for a fault starts fresh from seed 0 and its partial output is discarded, never
    merged.

    Per row, in ``seed_index`` order: build a DISTINCT per-battle ``LiveProfileContext`` (off the
    row's own seed/``battle_id``), play exactly one battle via ``run_local_gauntlet``, then -- only
    after the battle completes -- recount the FROZEN dataset (``validate_live_profile_dataset``,
    which also re-checks integrity) and evaluate the stop rule. A running battle is never aborted,
    so the scored cap is a THRESHOLD the last battle may overshoot by exactly its own rows
    (reported in ``scored_overshoot``, never truncated). The p95 is computed only after the run
    has stopped.
    """
    import asyncio

    from showdown_bot.client.gauntlet import run_local_gauntlet
    from showdown_bot.eval.result_jsonl import make_battle_id
    from showdown_bot.eval.seeding import derive_battle_seed

    for label, p in (("decision profile", profile_out), ("verdict", verdict_out)):
        if os.path.exists(p) and os.path.getsize(p) > 0:
            raise I8DRunError(
                f"{label} output {p} already has content; an I8-D restart runs from seed 0 into "
                f"fresh files and never merges a partial run"
            )

    writer = DecisionProfileWriter(profile_out, manifest=None)
    # Materialise the (empty) dataset up front so the per-battle recount reads a real file even
    # for a battle that scored nothing -- an empty dataset is valid, not a missing-file error.
    open(profile_out, "a", encoding="utf-8", newline="").close()
    budget_ms = load_latency_budget_ms()   # the pinned 1000 ms from gates.yaml, not a local copy

    battles_played = 0
    scored_decisions = active_valid = distinct_battles = 0
    stop_reason: str | None = None
    for row in schedule.rows:   # loader-sorted, contiguous seed_index from 0 (bound up front)
        seed = derive_battle_seed(seed_base, row.seed_index)
        battle_id = make_battle_id(schedule.schedule_hash, row.seed_index, seed)
        context = LiveProfileContext(
            battle_id=battle_id, config_id=hero_agent, config_hash=config_hash,
            schedule_hash=schedule.schedule_hash, format_id=row.format_id,
            git_sha=git_sha, calc_backend=calc_backend)
        asyncio.run(run_local_gauntlet(
            games=1, hero_agent=hero_agent, villain_agent=row.opp_policy,
            format_id=row.format_id, team_path=row.hero_team_path, opp_team_path=row.opp_team_path,
            decision_profile_writer=writer, decision_profile_context=context))
        battles_played += 1
        # §5.4.4: the battle is complete -> adopt it, recount the frozen dataset, THEN stop-check.
        counts = validate_live_profile_dataset(profile_out)
        scored_decisions = counts["rows"]
        active_valid = counts["active_valid_rows"]
        distinct_battles = counts["distinct_active_battle_ids"]
        stop, stop_reason = should_stop(
            battles_played=battles_played, scored_decisions=scored_decisions,
            active_valid=active_valid, distinct_battles=distinct_battles)
        if stop:
            break
    else:
        stop_reason = "schedule_exhausted"

    verdict = i8d_verdict(active_valid=active_valid, distinct_battles=distinct_battles,
                          active_measured_ms=_active_measured_ms(profile_out), budget_ms=budget_ms)
    report = {
        "schedule_hash": schedule.schedule_hash,
        "battles_played": battles_played,
        "scored_decisions": scored_decisions,
        "max_scored_decisions": I8D_MAX_SCORED_DECISIONS,
        "scored_overshoot": max(0, scored_decisions - I8D_MAX_SCORED_DECISIONS),
        "active_valid_decisions": active_valid,
        "distinct_active_battles": distinct_battles,
        "stop_reason": stop_reason,
        **verdict,
    }
    _write_json_atomic(verdict_out, report)
    return report

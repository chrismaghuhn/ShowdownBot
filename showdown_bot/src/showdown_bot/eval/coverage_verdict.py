"""Task 5: the coverage verdict + stop rule (spec §2.3/§2.6, D-2).

The verdict is three-way -- PASS / FAIL / INCONCLUSIVE -- with ABORTED kept OFF the verdict (a
technical abort is voided by the runner and never routed here). It reads dataset-sourced per-cell
counts (Task 3) and the server-authoritative ``safety_violations`` count (from the Task-6 runner
report), never a caller-supplied ``safety_ok``. Safety is checked FIRST (fail-fast), then the
per-cell floors, then the caps -- and the four stop-reasons are one-to-one with the verdict.
"""
from __future__ import annotations

from showdown_bot.eval.coverage_schedule import COVERAGE_CELLS, COVERAGE_MAX_BATTLES

COVERAGE_MAX_SCORED_DECISIONS = 2000

# Per-cell floors (decisions, distinct_battles), spec §2.3 / D-2.
COVERAGE_CELL_FLOORS: dict[str, tuple[int, int]] = {
    "slot0": (30, 10),
    "slot1": (30, 10),
    "both_foe_slots": (15, 6),
    "order_tie": (15, 6),
}


def coverage_floor_met(cell_counts: dict) -> bool:
    """True iff EVERY cell meets both its decision and distinct-battle floor."""
    for cell, (min_decisions, min_battles) in COVERAGE_CELL_FLOORS.items():
        counts = cell_counts.get(cell, {})
        if counts.get("decisions", 0) < min_decisions or counts.get("distinct_battles", 0) < min_battles:
            return False
    return True


def coverage_should_stop(*, battles_played: int, scored_decisions: int, cell_counts: dict,
                         safety_violations: int) -> tuple[bool, str | None]:
    """The stop rule, in its order: a safety violation first (fail-fast), then the coverage floor
    (the good stop), then the two caps. Evaluated by the runner ONLY after a fully-completed,
    validated battle."""
    if safety_violations > 0:
        return True, "safety_violation"
    if coverage_floor_met(cell_counts):
        return True, "coverage_floor_met"
    if battles_played >= COVERAGE_MAX_BATTLES:
        return True, "max_battles"
    if scored_decisions >= COVERAGE_MAX_SCORED_DECISIONS:
        return True, "max_scored_decisions"
    return False, None


def coverage_verdict(*, cell_counts: dict, safety_violations: int, schedule_complete: bool,
                     stop_reason: str) -> dict:
    """Map the run's terminal state to the three-way verdict + its one-to-one stop-reason:

      - ``safety_violations > 0``           -> FAIL,         ``safety_violation``
      - every cell meets its floor          -> PASS,         ``coverage_floor_met``
      - floor unmet but schedule completed  -> FAIL,         ``schedule_exhausted`` (a defect, §2.6(b))
      - floor unmet, a cap truncated it     -> INCONCLUSIVE, the cap's ``stop_reason``
    """
    base = {
        # JSON-native (lists, not tuples) so a written verdict.json round-trips to the returned dict.
        "cell_floors": {cell: list(floor) for cell, floor in COVERAGE_CELL_FLOORS.items()},
        "cell_counts": {cell: cell_counts.get(cell, {}) for cell in COVERAGE_CELLS},
        "safety_violations": safety_violations,
        "schedule_complete": schedule_complete,
    }
    if safety_violations > 0:
        return {**base, "verdict": "FAIL", "stop_reason": "safety_violation"}
    if coverage_floor_met(cell_counts):
        return {**base, "verdict": "PASS", "stop_reason": "coverage_floor_met"}
    if schedule_complete:
        return {**base, "verdict": "FAIL", "stop_reason": "schedule_exhausted"}
    return {**base, "verdict": "INCONCLUSIVE", "stop_reason": stop_reason}

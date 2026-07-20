"""Task 5: the coverage verdict PASS / FAIL / INCONCLUSIVE (ABORTED is kept OFF the verdict, voided
by the runner). Reads dataset-sourced cell counts (Task 3) and the server-authoritative
safety_violations count (Task-6 runner); safety is checked FIRST (fail-fast), then the per-cell
floors, then the caps. Stop-reasons are one-to-one with the verdict.
"""
from __future__ import annotations

from showdown_bot.eval.coverage_verdict import (
    COVERAGE_CELL_FLOORS,
    coverage_floor_met,
    coverage_should_stop,
    coverage_verdict,
)


def _counts(slot0=(30, 10), slot1=(30, 10), both=(15, 6), tie=(15, 6)) -> dict:
    return {
        "slot0": {"decisions": slot0[0], "distinct_battles": slot0[1]},
        "slot1": {"decisions": slot1[0], "distinct_battles": slot1[1]},
        "both_foe_slots": {"decisions": both[0], "distinct_battles": both[1]},
        "order_tie": {"decisions": tie[0], "distinct_battles": tie[1]},
    }


def test_the_floors_are_the_bound_values():
    assert COVERAGE_CELL_FLOORS == {
        "slot0": (30, 10), "slot1": (30, 10), "both_foe_slots": (15, 6), "order_tie": (15, 6),
    }


def test_coverage_floor_met_is_PASS():
    v = coverage_verdict(cell_counts=_counts(), safety_violations=0, schedule_complete=True,
                         stop_reason="coverage_floor_met")
    assert v["verdict"] == "PASS" and v["stop_reason"] == "coverage_floor_met"
    assert coverage_floor_met(_counts()) is True


def test_schedule_exhausted_with_a_cell_below_floor_is_FAIL():
    v = coverage_verdict(cell_counts=_counts(slot0=(29, 10)), safety_violations=0,
                         schedule_complete=True, stop_reason="schedule_exhausted")
    assert v["verdict"] == "FAIL" and v["stop_reason"] == "schedule_exhausted"
    assert coverage_floor_met(_counts(slot0=(29, 10))) is False


def test_a_cap_truncation_before_schedule_end_is_INCONCLUSIVE():
    v = coverage_verdict(cell_counts=_counts(both=(14, 6)), safety_violations=0,
                         schedule_complete=False, stop_reason="max_battles")
    assert v["verdict"] == "INCONCLUSIVE"
    assert v["stop_reason"] in ("max_battles", "max_scored_decisions")


def test_a_safety_violation_is_FAIL_with_its_own_stop_reason():
    # a safety violation FAILs regardless of cell counts (even with every floor met).
    v = coverage_verdict(cell_counts=_counts(), safety_violations=1, schedule_complete=True,
                         stop_reason="safety_violation")
    assert v["verdict"] == "FAIL" and v["stop_reason"] == "safety_violation"


def test_coverage_should_stop_checks_safety_first_then_the_floor_before_the_caps():
    # safety first, even with caps hit and floors met
    assert coverage_should_stop(battles_played=200, scored_decisions=2000, cell_counts=_counts(),
                                safety_violations=1) == (True, "safety_violation")
    # then the floor (the good stop) before the caps
    assert coverage_should_stop(battles_played=200, scored_decisions=2000, cell_counts=_counts(),
                                safety_violations=0) == (True, "coverage_floor_met")
    # a cell short + max_battles reached -> the cap fires (not the floor)
    assert coverage_should_stop(battles_played=200, scored_decisions=0,
                                cell_counts=_counts(slot0=(0, 0)), safety_violations=0) == (True, "max_battles")
    # a cell short + scored-decisions cap reached
    assert coverage_should_stop(battles_played=10, scored_decisions=2000,
                                cell_counts=_counts(slot0=(0, 0)), safety_violations=0) == (True, "max_scored_decisions")
    # nothing yet -> keep going
    assert coverage_should_stop(battles_played=10, scored_decisions=10,
                                cell_counts=_counts(slot0=(0, 0)), safety_violations=0) == (False, None)

"""Tests for eval/teacher_disagreement.py -- classification + bucketing core (2b-3.5 T1,
teacher-disagreement atlas).

Fixtures fabricate decision groups shaped like ``learning.dataset.load_rows`` output (the
``_candidate`` helper is ported from the user's external Decision-Error-Atlas prototype,
``docs/superpowers/plans/2026-07-10-decision-error-atlas.md`` Task 5 Step 1). No dataset file,
no CLI -- fabricated dicts only (Task 2 wires the real loader).
"""
from __future__ import annotations

import math

import pytest

from showdown_bot.eval.teacher_disagreement import (
    TeacherDisagreementError,
    analyze_disagreement,
    group_by_decision,
)


def _candidate(
    decision_id: str,
    candidate_index: int,
    *,
    chosen: bool,
    teacher_best: bool,
    gap: float,
    turn: int = 4,
    mode: str = "NEUTRAL",
    game_id: str = "game-1",
    slot1_action_type: str = "move",
    slot2_action_type: str | None = None,
    slot1_is_protect: bool = False,
    slot2_is_protect: bool = False,
    ko_threatened_count: int = 1,
    speed_control_state: str = "none",
    opponent_response_entropy: float = 1.0,
    score_gap_to_second: float = 0.5,
) -> dict:
    if slot2_action_type is None:
        slot2_action_type = "switch" if candidate_index else "move"
    return {
        "features": {
            "turn_number": turn,
            "game_mode": mode,
            "slot1_action_type": slot1_action_type,
            "slot2_action_type": slot2_action_type,
            "slot1_is_protect": slot1_is_protect,
            "slot2_is_protect": slot2_is_protect,
            "ko_threatened_count": ko_threatened_count,
            "speed_control_state": speed_control_state,
            "opponent_response_entropy": opponent_response_entropy,
            "score_gap_to_second": score_gap_to_second,
        },
        "label": {
            "chosen_by_current_heuristic": chosen,
            "teacher_best": teacher_best,
            "value_gap_to_best": gap,
        },
        "metadata": {
            "candidate_index": candidate_index,
            "decision_id": decision_id,
            "game_id": game_id,
        },
    }


def _flatten(decisions: dict[str, tuple[dict, ...]]) -> list[dict]:
    """Flatten a decision_id -> rows mapping into a flat row list (for group_by_decision)."""
    rows: list[dict] = []
    for group in decisions.values():
        rows.extend(group)
    return rows


# --- group_by_decision -------------------------------------------------------------------------


def test_group_by_decision_keys_on_metadata_decision_id():
    rows = [
        _candidate("b", 0, chosen=True, teacher_best=True, gap=0.0),
        _candidate("a", 0, chosen=True, teacher_best=True, gap=0.0),
        _candidate("a", 1, chosen=False, teacher_best=False, gap=1.0),
    ]

    grouped = group_by_decision(rows)

    assert set(grouped) == {"a", "b"}
    assert len(grouped["a"]) == 2
    assert len(grouped["b"]) == 1


def test_group_by_decision_returns_sorted_keys():
    rows = [
        _candidate("zeta", 0, chosen=True, teacher_best=True, gap=0.0),
        _candidate("alpha", 0, chosen=True, teacher_best=True, gap=0.0),
        _candidate("mid", 0, chosen=True, teacher_best=True, gap=0.0),
    ]

    grouped = group_by_decision(rows)

    assert list(grouped.keys()) == ["alpha", "mid", "zeta"]


def test_group_by_decision_preserves_row_order_within_a_decision():
    rows = [
        _candidate("a", 0, chosen=True, teacher_best=True, gap=0.0),
        _candidate("a", 1, chosen=False, teacher_best=False, gap=1.0),
    ]

    grouped = group_by_decision(rows)

    assert [row["metadata"]["candidate_index"] for row in grouped["a"]] == [0, 1]


# --- classification + corpus counts -------------------------------------------------------------


def test_analyze_disagreement_separates_forced_ties_and_disagreement():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=2.5),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"] == {
        "decisions": 4,
        "forced": 1,
        "teacher_ties": 1,
        "genuine_choices": 2,
        "disagreements": 1,
    }
    assert result["disagreement_rate"] == 0.5
    assert result["high_value_threshold"] == 2.5
    assert result["top_opportunities"][0]["decision_id"] == "disagree"
    assert {row["value"] for row in result["breakdowns"]["response_entropy_bucket"]} == {"medium"}
    assert {row["value"] for row in result["breakdowns"]["heuristic_confidence_bucket"]} == {"medium"}


def test_disagreement_rate_denominator_is_genuine_choices_only():
    # 1 forced + 1 teacher-tie + 3 genuine choices (2 agree, 1 disagree) -> rate is 1/3, not 1/4.
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "agree1": (
            _candidate("agree1", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree1", 1, chosen=False, teacher_best=False, gap=1.0),
        ),
        "agree2": (
            _candidate("agree2", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree2", 1, chosen=False, teacher_best=False, gap=1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=3.0),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["genuine_choices"] == 3
    assert result["corpus"]["disagreements"] == 1
    assert result["disagreement_rate"] == pytest.approx(1 / 3)


def test_disagreement_rate_is_zero_with_no_genuine_choices():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
    }

    result = analyze_disagreement(decisions)

    assert result["disagreement_rate"] == 0.0
    assert result["high_value_threshold"] == 0.0
    assert result["top_opportunities"] == []


# --- high_value_threshold + top_opportunities ----------------------------------------------------


def test_high_value_threshold_is_90th_nearest_rank_of_positive_disagreement_gaps():
    # 10 disagreements with gaps 1..10 -> ceil(0.9*10)-1 = 8 -> sorted[8] == 9.0
    decisions = {
        f"d{i:02d}": (
            _candidate(f"d{i:02d}", 0, chosen=True, teacher_best=False, gap=float(i)),
            _candidate(f"d{i:02d}", 1, chosen=False, teacher_best=True, gap=0.0),
        )
        for i in range(1, 11)
    }

    result = analyze_disagreement(decisions)

    expected = sorted(float(i) for i in range(1, 11))[math.ceil(0.90 * 10) - 1]
    assert expected == 9.0
    assert result["high_value_threshold"] == 9.0


def test_top_opportunities_first_entry_is_the_largest_gap_disagreement():
    decisions = {
        "small": (
            _candidate("small", 0, chosen=True, teacher_best=False, gap=0.5),
            _candidate("small", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "large": (
            _candidate("large", 0, chosen=True, teacher_best=False, gap=7.0),
            _candidate("large", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "medium": (
            _candidate("medium", 0, chosen=True, teacher_best=False, gap=3.0),
            _candidate("medium", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["top_opportunities"][0]["decision_id"] == "large"
    assert result["top_opportunities"][0]["value_gap"] == 7.0
    assert [row["decision_id"] for row in result["top_opportunities"]] == [
        "large",
        "medium",
        "small",
    ]


def test_top_opportunities_ties_break_on_decision_id():
    decisions = {
        decision_id: (
            _candidate(decision_id, 0, chosen=True, teacher_best=False, gap=5.0),
            _candidate(decision_id, 1, chosen=False, teacher_best=True, gap=0.0),
        )
        for decision_id in ("z-last", "a-first")
    }

    result = analyze_disagreement(decisions)

    assert [row["decision_id"] for row in result["top_opportunities"]] == [
        "a-first",
        "z-last",
    ]


def test_top_opportunities_capped_at_20():
    decisions = {
        f"d{i:02d}": (
            _candidate(f"d{i:02d}", 0, chosen=True, teacher_best=False, gap=float(i)),
            _candidate(f"d{i:02d}", 1, chosen=False, teacher_best=True, gap=0.0),
        )
        for i in range(1, 26)
    }

    result = analyze_disagreement(decisions)

    assert len(result["top_opportunities"]) == 20
    assert result["top_opportunities"][0]["decision_id"] == "d25"


# --- bucketing -------------------------------------------------------------------------------


def test_turn_bucket_value_set_reflects_boundaries():
    contexts = (("a", 3), ("b", 4), ("c", 6), ("d", 7))
    decisions = {
        decision_id: (
            _candidate(decision_id, 0, chosen=True, teacher_best=True, gap=0.0, turn=turn),
            _candidate(decision_id, 1, chosen=False, teacher_best=False, gap=1.0, turn=turn),
        )
        for decision_id, turn in contexts
    }

    result = analyze_disagreement(decisions)

    assert {row["value"] for row in result["breakdowns"]["turn_bucket"]} == {
        "turn_1_3",
        "turn_4_6",
        "turn_7_plus",
    }


def test_action_signature_bucket_counts_protects():
    decisions = {
        "both_protect": (
            _candidate(
                "both_protect",
                0,
                chosen=True,
                teacher_best=True,
                gap=0.0,
                slot1_action_type="move",
                slot2_action_type="move",
                slot1_is_protect=True,
                slot2_is_protect=True,
            ),
            _candidate("both_protect", 1, chosen=False, teacher_best=False, gap=1.0),
        ),
    }

    result = analyze_disagreement(decisions)

    signature_row = result["breakdowns"]["action_signature"][0]
    assert signature_row["value"] == "move+move|protects=2"


def test_breakdown_disagreement_rate_and_mean_gap_per_bucket():
    decisions = {
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0, mode="NEUTRAL"),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=1.0, mode="NEUTRAL"),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=4.0, mode="NEUTRAL"),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0, mode="NEUTRAL"),
        ),
    }

    result = analyze_disagreement(decisions)

    mode_rows = {row["value"]: row for row in result["breakdowns"]["game_mode"]}
    assert mode_rows["NEUTRAL"]["decisions"] == 2
    assert mode_rows["NEUTRAL"]["disagreements"] == 1
    assert mode_rows["NEUTRAL"]["disagreement_rate"] == 0.5
    assert mode_rows["NEUTRAL"]["mean_disagreement_gap"] == 4.0


# --- fail-closed invariants --------------------------------------------------------------------


def test_rejects_decision_without_exactly_one_chosen_row_multiple():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("bad", 1, chosen=True, teacher_best=False, gap=1.0),
        )
    }

    with pytest.raises(TeacherDisagreementError, match="exactly one chosen"):
        analyze_disagreement(decisions)


def test_rejects_decision_without_exactly_one_chosen_row_zero():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=False, teacher_best=True, gap=0.0),
            _candidate("bad", 1, chosen=False, teacher_best=False, gap=1.0),
        )
    }

    with pytest.raises(TeacherDisagreementError, match="exactly one chosen"):
        analyze_disagreement(decisions)


def test_rejects_decision_with_no_teacher_best_row():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=True, teacher_best=False, gap=0.0),
            _candidate("bad", 1, chosen=False, teacher_best=False, gap=1.0),
        )
    }

    with pytest.raises(TeacherDisagreementError, match="no teacher-best row"):
        analyze_disagreement(decisions)


@pytest.mark.parametrize("bad_gap", (float("nan"), float("inf"), -float("inf"), -1.0))
def test_rejects_non_finite_or_negative_value_gap_on_chosen_row(bad_gap):
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=True, teacher_best=False, gap=bad_gap),
            _candidate("bad", 1, chosen=False, teacher_best=True, gap=0.0),
        )
    }

    with pytest.raises(TeacherDisagreementError, match="invalid value gap"):
        analyze_disagreement(decisions)


# --- determinism -------------------------------------------------------------------------------


def test_analyze_disagreement_is_deterministic_across_calls():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=2.5),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    first = analyze_disagreement(decisions)
    second = analyze_disagreement(decisions)

    assert first == second


def test_analyze_disagreement_is_input_order_independent():
    decisions = {
        f"d{i:02d}": (
            _candidate(f"d{i:02d}", 0, chosen=True, teacher_best=False, gap=float(i)),
            _candidate(f"d{i:02d}", 1, chosen=False, teacher_best=True, gap=0.0),
        )
        for i in range(1, 6)
    }

    forward = analyze_disagreement(decisions)
    reversed_result = analyze_disagreement(dict(reversed(tuple(decisions.items()))))

    assert forward == reversed_result


def test_group_by_decision_then_analyze_disagreement_round_trip():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=2.0),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }
    rows = _flatten(decisions)

    grouped = group_by_decision(rows)
    result = analyze_disagreement(grouped)

    assert result["corpus"] == {
        "decisions": 3,
        "forced": 1,
        "teacher_ties": 0,
        "genuine_choices": 2,
        "disagreements": 1,
    }

"""Tests for eval/teacher_disagreement.py -- topset-model classification + bucketing core
(2b-3.5 T3, replacing the T1 single-best snapshot that crashed on this codebase's
``value_gap_to_best <= 0`` labels).

Fixtures fabricate decision groups shaped like ``learning.dataset.load_rows`` output (the
``_candidate`` helper is ported, with adaptations for the topset model's stricter typed
validation layer, from the user's external Decision-Error-Atlas prototype). No dataset file,
no CLI -- fabricated dicts only (a later task wires the real loader).
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
    gap: float = 0.0,
    heuristic_rank: int | None = None,
    teacher_rank: int | None = None,
    turn: int = 4,
    mode: str = "NEUTRAL",
    game_id: str = "game-1",
    slot1_action_type: str = "move",
    slot2_action_type: str = "switch",
    slot1_is_protect: bool = False,
    slot2_is_protect: bool = False,
    ko_threatened_count: int = 1,
    speed_control_state: str = "none",
    opponent_response_entropy: float = 1.0,
    score_gap_to_second: float = 0.5,
) -> dict:
    if heuristic_rank is None:
        heuristic_rank = 0 if chosen else 1
    if teacher_rank is None:
        teacher_rank = 0 if teacher_best else 1
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
            "heuristic_rank": heuristic_rank,
            "teacher_rank": teacher_rank,
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
        _candidate("a", 1, chosen=False, teacher_best=False, gap=-1.0),
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
        _candidate("a", 1, chosen=False, teacher_best=False, gap=-1.0),
    ]

    grouped = group_by_decision(rows)

    assert [row["metadata"]["candidate_index"] for row in grouped["a"]] == [0, 1]


# --- topset classification + corpus counts -------------------------------------------------------


def test_forced_decision_is_skipped_from_multi_candidate_and_strict_counts():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"] == {
        "decisions": 1,
        "forced": 1,
        "multi_candidate": 0,
        "heuristic_ties": 0,
        "teacher_ties": 0,
        "strict_unique_choices": 0,
        "topset_agreements": 0,
        "topset_disagreements": 0,
        "strict_agreements": 0,
        "strict_disagreements": 0,
    }
    assert result["topset_disagreement_rate"] == 0.0
    assert result["strict_disagreement_rate"] == 0.0
    assert result["disagreement_rate"] == 0.0
    assert result["top_opportunities"] == []


def test_multi_candidate_with_overlapping_topsets_is_a_strict_agreement():
    decisions = {
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["multi_candidate"] == 1
    assert result["corpus"]["topset_agreements"] == 1
    assert result["corpus"]["topset_disagreements"] == 0
    assert result["corpus"]["strict_agreements"] == 1
    assert result["corpus"]["strict_disagreements"] == 0
    assert result["corpus"]["strict_unique_choices"] == 1
    assert result["disagreement_rate"] == 0.0
    assert result["top_opportunities"] == []


def test_disjoint_topsets_is_a_strict_disagreement():
    decisions = {
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=-2.5),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["topset_agreements"] == 0
    assert result["corpus"]["topset_disagreements"] == 1
    assert result["corpus"]["strict_agreements"] == 0
    assert result["corpus"]["strict_disagreements"] == 1
    assert result["disagreement_rate"] == 1.0
    assert result["topset_disagreement_rate"] == 1.0


def test_heuristic_tie_counted_and_excluded_from_strict():
    # two chosen rows -> heuristic topset {0, 1}; still overlaps the teacher topset {0}, so it's
    # a topset agreement, but it can't be a strict-unique choice (needs exactly one chosen row).
    decisions = {
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=True, teacher_best=False, gap=-1.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["heuristic_ties"] == 1
    assert result["corpus"]["teacher_ties"] == 0
    assert result["corpus"]["strict_unique_choices"] == 0
    assert result["corpus"]["topset_agreements"] == 1
    assert result["corpus"]["strict_agreements"] == 0
    assert result["corpus"]["strict_disagreements"] == 0
    assert result["disagreement_rate"] == 0.0


def test_teacher_tie_counted_and_excluded_from_strict():
    # two teacher_best rows -> teacher topset {0, 1}; overlaps heuristic topset {0}, so it's a
    # topset agreement, but not a strict-unique choice (needs exactly one teacher row).
    decisions = {
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["teacher_ties"] == 1
    assert result["corpus"]["heuristic_ties"] == 0
    assert result["corpus"]["strict_unique_choices"] == 0
    assert result["corpus"]["topset_agreements"] == 1
    assert result["corpus"]["strict_agreements"] == 0
    assert result["corpus"]["strict_disagreements"] == 0


def test_topset_disagreement_rate_uses_multi_candidate_denominator_not_strict():
    # 1 heuristic-tie (topset agreement, not strict) + 1 strict disagreement -> 2 multi_candidate,
    # 1 topset_disagreement (rate 1/2); but only 1 strict_unique_choice, which IS the disagreement
    # (strict rate 1/1). The two rates must differ, proving the denominators are independent.
    decisions = {
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=True, teacher_best=False, gap=-1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=-3.0),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["multi_candidate"] == 2
    assert result["corpus"]["strict_unique_choices"] == 1
    assert result["topset_disagreement_rate"] == pytest.approx(0.5)
    assert result["strict_disagreement_rate"] == 1.0
    assert result["disagreement_rate"] == 1.0


def test_disagreement_rate_is_zero_with_no_strict_unique_choices():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["corpus"]["strict_unique_choices"] == 0
    assert result["strict_disagreement_rate"] == 0.0
    assert result["disagreement_rate"] == 0.0
    assert result["high_value_threshold"] == 0.0
    assert result["top_opportunities"] == []


# --- regret_gap + strict-unique records ----------------------------------------------------------


def test_strict_unique_disagreement_record_has_regret_gap_equal_to_negated_raw_gap():
    decisions = {
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=-3.25),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    record = result["top_opportunities"][0]
    assert record["raw_value_gap"] == -3.25
    assert record["regret_gap"] == 3.25
    assert record["disagreement"] is True


def test_strict_unique_agreement_record_is_excluded_from_top_opportunities():
    decisions = {
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["top_opportunities"] == []


def test_negative_score_gap_on_strict_unique_heuristic_row_raises():
    decisions = {
        "bad": (
            _candidate(
                "bad", 0, chosen=True, teacher_best=False, gap=-1.0, score_gap_to_second=-0.1
            ),
            _candidate("bad", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    with pytest.raises(TeacherDisagreementError, match="score_gap_to_second"):
        analyze_disagreement(decisions)


# --- fail-closed validation layer (_validate_row / _validate_decisions) --------------------------


def test_decisions_must_be_a_dict():
    with pytest.raises(TeacherDisagreementError, match="decisions must be a JSON object"):
        analyze_disagreement([])  # type: ignore[arg-type]


def test_decision_rows_must_be_a_list():
    with pytest.raises(TeacherDisagreementError, match="rows must be a list"):
        analyze_disagreement({"bad": "not-a-list"})  # type: ignore[dict-item]


def test_decision_rows_must_not_be_empty():
    with pytest.raises(TeacherDisagreementError, match="empty candidate group"):
        analyze_disagreement({"bad": ()})


def test_row_missing_top_level_field_raises():
    row = _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0)
    del row["label"]

    with pytest.raises(TeacherDisagreementError, match="missing fields"):
        analyze_disagreement({"bad": (row,)})


def test_row_with_non_boolean_protect_flag_raises():
    row = _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0)
    row["features"]["slot1_is_protect"] = 1  # not a real bool

    with pytest.raises(TeacherDisagreementError, match="must be a boolean"):
        analyze_disagreement({"bad": (row,)})


def test_ko_threatened_count_out_of_vgc_doubles_domain_raises():
    row = _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0, ko_threatened_count=3)

    with pytest.raises(TeacherDisagreementError, match="VGC doubles domain"):
        analyze_disagreement({"bad": (row,)})


def test_rank_zero_flag_mismatch_raises():
    row = _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0, heuristic_rank=1)

    with pytest.raises(TeacherDisagreementError, match="rank-zero status"):
        analyze_disagreement({"bad": (row,)})


def test_teacher_best_row_with_nonzero_gap_raises():
    row = _candidate("bad", 0, chosen=True, teacher_best=True, gap=-0.5)

    with pytest.raises(TeacherDisagreementError, match="exactly zero"):
        analyze_disagreement({"bad": (row,)})


def test_positive_value_gap_raises():
    row = _candidate("bad", 0, chosen=True, teacher_best=False, gap=0.5)

    with pytest.raises(TeacherDisagreementError, match="less than or equal to zero"):
        analyze_disagreement({"bad": (row,)})


def test_noncontiguous_candidate_indices_raises():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("bad", 2, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    with pytest.raises(TeacherDisagreementError, match="contiguous"):
        analyze_disagreement(decisions)


def test_decision_with_multiple_game_ids_raises():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=True, teacher_best=True, gap=0.0, game_id="g1"),
            _candidate("bad", 1, chosen=False, teacher_best=False, gap=-1.0, game_id="g2"),
        ),
    }

    with pytest.raises(TeacherDisagreementError, match="exactly one game_id"):
        analyze_disagreement(decisions)


def test_decision_without_a_heuristic_top_row_raises():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=False, teacher_best=True, gap=0.0),
            _candidate("bad", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    with pytest.raises(TeacherDisagreementError, match="heuristic-top row"):
        analyze_disagreement(decisions)


def test_decision_without_a_teacher_top_row_raises():
    decisions = {
        "bad": (
            _candidate("bad", 0, chosen=True, teacher_best=False, gap=0.0),
            _candidate("bad", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    with pytest.raises(TeacherDisagreementError, match="teacher-top row"):
        analyze_disagreement(decisions)


# --- high_value_threshold + top_opportunities ----------------------------------------------------


def test_high_value_threshold_is_90th_nearest_rank_of_disagreement_regret_gaps():
    # 10 disagreements with raw gaps -1..-10 -> regret_gaps 1..10 -> ceil(0.9*10)-1 = 8 -> sorted[8] == 9.0
    decisions = {
        f"d{i:02d}": (
            _candidate(f"d{i:02d}", 0, chosen=True, teacher_best=False, gap=-float(i)),
            _candidate(f"d{i:02d}", 1, chosen=False, teacher_best=True, gap=0.0),
        )
        for i in range(1, 11)
    }

    result = analyze_disagreement(decisions)

    expected = sorted(float(i) for i in range(1, 11))[math.ceil(0.90 * 10) - 1]
    assert expected == 9.0
    assert result["high_value_threshold"] == 9.0


def test_top_opportunities_first_entry_is_the_largest_regret_disagreement():
    decisions = {
        "small": (
            _candidate("small", 0, chosen=True, teacher_best=False, gap=-0.5),
            _candidate("small", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "large": (
            _candidate("large", 0, chosen=True, teacher_best=False, gap=-7.0),
            _candidate("large", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
        "medium": (
            _candidate("medium", 0, chosen=True, teacher_best=False, gap=-3.0),
            _candidate("medium", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["top_opportunities"][0]["decision_id"] == "large"
    assert result["top_opportunities"][0]["regret_gap"] == 7.0
    assert [row["decision_id"] for row in result["top_opportunities"]] == [
        "large",
        "medium",
        "small",
    ]


def test_top_opportunities_ties_break_on_decision_id():
    decisions = {
        decision_id: (
            _candidate(decision_id, 0, chosen=True, teacher_best=False, gap=-5.0),
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
            _candidate(f"d{i:02d}", 0, chosen=True, teacher_best=False, gap=-float(i)),
            _candidate(f"d{i:02d}", 1, chosen=False, teacher_best=True, gap=0.0),
        )
        for i in range(1, 26)
    }

    result = analyze_disagreement(decisions)

    assert len(result["top_opportunities"]) == 20
    assert result["top_opportunities"][0]["decision_id"] == "d25"


def test_high_value_flag_requires_positive_regret_gap():
    # a disagreement with raw gap == 0.0 has regret_gap == 0.0 -- never high_value, even though
    # the threshold itself is 0.0 in a single-record corpus (>= 0.0 alone would wrongly pass).
    decisions = {
        "zero_regret": (
            _candidate("zero_regret", 0, chosen=True, teacher_best=False, gap=0.0),
            _candidate("zero_regret", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["high_value_threshold"] == 0.0
    assert result["top_opportunities"][0]["regret_gap"] == 0.0
    assert result["top_opportunities"][0]["high_value"] is False


# --- bucketing -------------------------------------------------------------------------------


def test_turn_bucket_value_set_reflects_boundaries():
    contexts = (("a", 3), ("b", 4), ("c", 6), ("d", 7))
    decisions = {
        decision_id: (
            _candidate(decision_id, 0, chosen=True, teacher_best=True, gap=0.0, turn=turn),
            _candidate(decision_id, 1, chosen=False, teacher_best=False, gap=-1.0, turn=turn),
        )
        for decision_id, turn in contexts
    }

    result = analyze_disagreement(decisions)

    assert {row["value"] for row in result["breakdowns"]["turn_bucket"]} == {
        "1-3",
        "4-6",
        "7+",
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
            _candidate("both_protect", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    result = analyze_disagreement(decisions)

    signature_row = result["breakdowns"]["action_signature"][0]
    assert signature_row["value"] == "move+move|protects=2"


def test_heuristic_confidence_bucket_is_tie_or_zero_when_score_gap_is_zero():
    decisions = {
        "flat": (
            _candidate(
                "flat", 0, chosen=True, teacher_best=False, gap=-1.0, score_gap_to_second=0.0
            ),
            _candidate("flat", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    result = analyze_disagreement(decisions)

    record = result["top_opportunities"][0]
    assert record["heuristic_confidence_bucket"] == "tie_or_zero"


def test_breakdown_disagreement_rate_and_mean_regret_per_bucket():
    decisions = {
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0, mode="NEUTRAL"),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=-1.0, mode="NEUTRAL"),
        ),
        "disagree": (
            _candidate(
                "disagree", 0, chosen=True, teacher_best=False, gap=-4.0, mode="NEUTRAL"
            ),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0, mode="NEUTRAL"),
        ),
    }

    result = analyze_disagreement(decisions)

    mode_rows = {row["value"]: row for row in result["breakdowns"]["game_mode"]}
    assert mode_rows["NEUTRAL"]["decisions"] == 2
    assert mode_rows["NEUTRAL"]["agreements"] == 1
    assert mode_rows["NEUTRAL"]["disagreements"] == 1
    assert mode_rows["NEUTRAL"]["disagreement_rate"] == 0.5
    assert mode_rows["NEUTRAL"]["mean_disagreement_regret"] == 4.0


def test_breakdown_scope_and_denominator_report_strict_unique_choices():
    decisions = {
        "forced": (_candidate("forced", 0, chosen=True, teacher_best=True, gap=0.0),),
        "tie": (
            _candidate("tie", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("tie", 1, chosen=True, teacher_best=False, gap=-1.0),
        ),
        "agree": (
            _candidate("agree", 0, chosen=True, teacher_best=True, gap=0.0),
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
    }

    result = analyze_disagreement(decisions)

    assert result["breakdown_scope"] == "strict_unique_choices"
    assert result["breakdown_denominator"] == 1


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
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=-2.5),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }

    first = analyze_disagreement(decisions)
    second = analyze_disagreement(decisions)

    assert first == second


def test_analyze_disagreement_is_input_order_independent():
    decisions = {
        f"d{i:02d}": (
            _candidate(f"d{i:02d}", 0, chosen=True, teacher_best=False, gap=-float(i)),
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
            _candidate("agree", 1, chosen=False, teacher_best=False, gap=-1.0),
        ),
        "disagree": (
            _candidate("disagree", 0, chosen=True, teacher_best=False, gap=-2.0),
            _candidate("disagree", 1, chosen=False, teacher_best=True, gap=0.0),
        ),
    }
    rows = _flatten(decisions)

    grouped = group_by_decision(rows)
    result = analyze_disagreement(grouped)

    assert result["corpus"]["decisions"] == 3
    assert result["corpus"]["forced"] == 1
    assert result["corpus"]["strict_unique_choices"] == 2
    assert result["corpus"]["strict_disagreements"] == 1
    assert result["disagreement_rate"] == 0.5

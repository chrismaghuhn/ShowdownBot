# showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from __future__ import annotations

import pytest

from showdown_bot.eval.accuracy_cap_derisk import (
    DecisionIdComponents,
    DuplicateDecisionIdError,
    assert_decision_ids_unique,
    compute_decision_id,
)


def test_compute_decision_id_is_deterministic():
    c = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    assert compute_decision_id(c) == compute_decision_id(c)


def test_compute_decision_id_changes_with_any_field():
    base = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    variants = [
        DecisionIdComponents(seed_base="other_seed", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=99, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="other_hash", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="other_prefix", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p2", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=99, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=99),
    ]
    base_id = compute_decision_id(base)
    for v in variants:
        assert compute_decision_id(v) != base_id


def test_compute_decision_id_is_a_hex_sha256():
    c = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    did = compute_decision_id(c)
    assert len(did) == 64
    int(did, 16)  # raises if not valid hex


def test_assert_decision_ids_unique_passes_on_unique_ids():
    assert_decision_ids_unique(["a", "b", "c"])  # no raise


def test_assert_decision_ids_unique_raises_on_duplicate():
    with pytest.raises(DuplicateDecisionIdError) as exc_info:
        assert_decision_ids_unique(["a", "b", "a", "c", "b"])
    msg = str(exc_info.value)
    assert "a" in msg and "b" in msg  # both duplicated ids named, not just a count


from showdown_bot.eval.accuracy_cap_derisk import (
    ActionTableRow,
    DecisionIdPairingError,
    compare_action_tables,
)


def _row(decision_id, action_raw, action_canonical=None, *, top_rank_score=1.0,
         chosen_candidate_score=1.0, candidate_resolution_status="exact"):
    return ActionTableRow(
        decision_id=decision_id, chosen_action_raw=action_raw,
        chosen_action_canonical=action_canonical if action_canonical is not None else action_raw,
        candidate_resolution_status=candidate_resolution_status,
        chosen_candidate_rank=0, chosen_rank_mismatch=False,
        top_rank_score=top_rank_score, chosen_candidate_score=chosen_candidate_score,
    )


def test_compare_action_tables_pairs_by_decision_id_not_position():
    ref = [_row("id2", "/choose move 1"), _row("id1", "/choose move 2")]
    cand = [_row("id1", "/choose move 2"), _row("id2", "/choose move 1")]
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert result.direction == "cap4 -> cap6"
    assert len(result.rows) == 2
    assert all(not r.action_changed for r in result.rows)


def test_compare_action_tables_detects_action_change_via_stored_canonical_field():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 2")]
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert result.rows[0].action_changed is True


def test_compare_action_tables_uses_canonical_not_raw_for_action_changed():
    """Two raw strings that differ byte-for-byte but share the same PRE-COMPUTED canonical form
    (simulating what normalize_choose would fold together, e.g. a trailing-space encoding quirk)
    must NOT be reported as an action change -- proving the comparator reads the stored canonical
    field, not the raw one."""
    ref = [_row("id1", "/choose move 1", "canonical:move1")]
    cand = [_row("id1", "/choose move 1 ", "canonical:move1")]  # raw differs, canonical doesn't
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert result.rows[0].action_changed is False


def test_compare_action_tables_does_not_count_pure_score_change_as_action_diff():
    ref = [_row("id1", "/choose move 1", top_rank_score=5.0)]
    cand = [_row("id1", "/choose move 1", top_rank_score=7.0)]  # same action, different score
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    row = result.rows[0]
    assert row.action_changed is False
    assert row.top_rank_score_delta == pytest.approx(2.0)
    assert row.top_rank_score_changed is True  # score change tracked, but NOT an action diff


def test_compare_action_tables_fails_closed_on_missing_id_in_candidate():
    ref = [_row("id1", "/choose move 1"), _row("id2", "/choose move 2")]
    cand = [_row("id1", "/choose move 1")]  # id2 missing
    with pytest.raises(DecisionIdPairingError) as exc_info:
        compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert "id2" in str(exc_info.value)


def test_compare_action_tables_fails_closed_on_extra_id_in_candidate():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 1"), _row("id_extra", "/choose move 2")]
    with pytest.raises(DecisionIdPairingError) as exc_info:
        compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert "id_extra" in str(exc_info.value)


def test_compare_action_tables_fails_closed_on_duplicate_id_within_one_table():
    ref = [_row("id1", "/choose move 1"), _row("id1", "/choose move 2")]
    cand = [_row("id1", "/choose move 1")]
    with pytest.raises(DecisionIdPairingError):
        compare_action_tables(ref, cand, direction="cap4 -> cap6")


def test_compare_action_tables_uses_correctly_named_reference_candidate_fields_not_baseline_replay():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 2")]
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    row = result.rows[0]
    assert row.reference_action_raw == "/choose move 1"
    assert row.candidate_action_raw == "/choose move 2"
    assert not hasattr(row, "baseline_action")
    assert not hasattr(row, "replay_action")


def test_compare_action_tables_direction_is_not_inferred_from_argument_order():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 2")]
    r1 = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    r2 = compare_action_tables(cand, ref, direction="cap6 -> cap4")  # swapped args, swapped label
    assert r1.direction == "cap4 -> cap6"
    assert r2.direction == "cap6 -> cap4"
    # swapping which table is "reference" flips reference/candidate labeling on the SAME
    # underlying decision, proving the function has no baked-in "first arg is always off" bias
    assert r1.rows[0].reference_action_raw == r2.rows[0].candidate_action_raw
    assert r1.rows[0].candidate_action_raw == r2.rows[0].reference_action_raw


def test_compare_action_tables_refuses_incompatible_score_semantics():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 1")]
    result = compare_action_tables(
        ref, cand, direction="off -> cap6", score_comparable=False,
        score_incompatible_reason="legacy_frozen_score not proven equivalent to top_rank_score",
    )
    row = result.rows[0]
    assert row.score_comparable is False
    assert row.top_rank_score_delta is None  # never silently computed
    assert "not proven equivalent" in row.score_incompatible_reason


def test_compare_action_tables_requires_reason_when_score_incompatible():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 1")]
    with pytest.raises(ValueError, match="score_incompatible_reason"):
        compare_action_tables(ref, cand, direction="off -> cap6", score_comparable=False)


from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.eval.accuracy_cap_derisk import build_action_table_row


def _candidate(candidate_id, rank, score):
    return CandidateTrace(
        candidate_id=candidate_id, joint_action=None, rank=rank, aggregate_score=score,
        score_vector=[score], outcome_breakdowns=[], aggregate_breakdown=None,
    )


def test_build_action_table_row_exact_match_rank_zero(scripted_request):
    trace = DecisionTrace(chosen_candidate_id="A", candidates=[
        _candidate("A", 0, 5.0), _candidate("B", 1, 3.0),
    ])
    row = build_action_table_row("d1", "/choose move 1", trace, scripted_request)
    assert row.candidate_resolution_status == "exact"
    assert row.chosen_candidate_rank == 0
    assert row.chosen_rank_mismatch is False
    assert row.top_rank_score == 5.0
    assert row.chosen_candidate_score == 5.0
    assert row.chosen_action_raw == "/choose move 1"
    assert row.chosen_action_canonical  # non-empty; exact shape depends on normalize_choose


def test_build_action_table_row_tera_stripped_and_rank_mismatch_simultaneously(scripted_request):
    """Both facts survive independently -- neither status collapses the other (spec Sec.2.3)."""
    trace = DecisionTrace(chosen_candidate_id="(protect, moonblast->1 tera)", candidates=[
        _candidate("(protect, shadowball->1)", 0, 6.0),
        _candidate("(protect, moonblast->1)", 1, 5.0),  # the real chosen line, at rank 1
    ])
    row = build_action_table_row("d1", "/choose move 1, move 2", trace, scripted_request)
    assert row.candidate_resolution_status == "tera_stripped"
    assert row.chosen_candidate_rank == 1
    assert row.chosen_rank_mismatch is True  # BOTH tera_stripped and rank_mismatch present
    assert row.top_rank_score == 6.0  # rank-0's score, independent of which one is chosen
    assert row.chosen_candidate_score == 5.0


def test_build_action_table_row_ambiguous_label_has_null_chosen_candidate_score(scripted_request):
    trace = DecisionTrace(chosen_candidate_id="(switch, pass)", candidates=[
        _candidate("(switch, pass)", 0, 4.0), _candidate("(switch, pass)", 1, 2.0),
    ])
    row = build_action_table_row("d1", "/choose switch 2, pass", trace, scripted_request)
    assert row.candidate_resolution_status == "ambiguous_label"
    assert row.chosen_candidate_rank is None
    assert row.chosen_rank_mismatch is None
    assert row.chosen_candidate_score is None
    assert row.top_rank_score == 4.0  # top_rank_score still populated -- independent of resolution


def test_build_action_table_row_chosen_missing(scripted_request):
    trace = DecisionTrace(chosen_candidate_id="(nothing matches)", candidates=[
        _candidate("A", 0, 5.0),
    ])
    row = build_action_table_row("d1", "/choose move 3", trace, scripted_request)
    assert row.candidate_resolution_status == "chosen_missing"
    assert row.chosen_candidate_score is None
    assert row.top_rank_score == 5.0


def test_build_action_table_row_empty_trace_keeps_the_action_row(scripted_request):
    """An empty/rank-corrupt trace must not make the whole decision (and its chosen_action_raw)
    disappear -- only the score fields go null, with the status visibly reflecting why."""
    trace = DecisionTrace(chosen_candidate_id=None, candidates=[])
    row = build_action_table_row("d1", "/choose move 1", trace, scripted_request)
    assert row.chosen_action_raw == "/choose move 1"  # action always present
    assert row.top_rank_score is None
    assert row.chosen_candidate_score is None
    assert row.chosen_candidate_rank is None
    assert row.candidate_resolution_status in ("chosen_missing", "other_resolution_error")

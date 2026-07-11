"""Tests for the 2c-slice-0b full-fidelity aggregation-trace sidecar (Task 2).

Offline, research-only: no live-path changes, no RNG, no battles. Mirrors
tests/test_decision_capture.py's Task-3 section for the writer/loader
mechanics, applied to the new agg-trace row schema.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.eval.decision_capture import normalize_choose
from showdown_bot.research.aggregation_trace import (
    AGG_TRACE_SCHEMA_VERSION,
    AggTraceContext,
    AggTraceError,
    AggTraceWriter,
    build_agg_row,
    load_agg_trace,
    validate_agg_row,
)

CHOOSE = "/choose move 1 1, move 2 2|7"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agg_context():
    return AggTraceContext(
        battle_id="battle-a", seed_index=0, our_side="p1", config_id="heuristic",
        config_hash="config-a", schedule_hash="schedule-a",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )


def _resp(target_slot: str) -> list[PlannedAction]:
    """One opponent joint response: slot a attacks ``target_slot``, slot b protects."""
    return [
        PlannedAction("p2", "a", "move", target=("p1", target_slot)),
        PlannedAction("p2", "b", "protect"),
    ]


def _switch_resp() -> list[PlannedAction]:
    return [
        PlannedAction("p2", "a", "switch"),
        PlannedAction("p2", "b", "pass"),
    ]


def _candidate(candidate_id: str, rank: int, aggregate_score: float, score_vector: list[float]) -> CandidateTrace:
    return CandidateTrace(
        candidate_id=candidate_id, joint_action=None, rank=rank,
        aggregate_score=aggregate_score, score_vector=list(score_vector),
        outcome_breakdowns=[OutcomeBreakdown() for _ in score_vector],
        aggregate_breakdown=OutcomeBreakdown(),
    )


def _fake_trace(*, weights: list[float] | None = None) -> DecisionTrace:
    """A DecisionTrace with 2 candidates x 3 opponent responses (fully controlled)."""
    responses = [_resp("a"), _resp("b"), _switch_resp()]
    tr = DecisionTrace(
        game_mode="NEUTRAL",
        aggregation_mode="neutral",
        risk_lambda=0.5,
        must_react_lambda=0.6,
        opponent_responses=responses,
        opponent_response_weights=list(weights) if weights is not None else [],
        candidates=[
            _candidate("cand-A", 0, 3.25, [3.0, 3.5, 3.25]),
            _candidate("cand-B", 1, 1.0, [0.5, 1.0, 1.5]),
        ],
    )
    tr.chosen_candidate_id = "cand-A"
    return tr


def _row_json(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# build_agg_row: schema, parallel lengths, fidelity to the trace
# ---------------------------------------------------------------------------

def test_build_agg_row_parallel_lengths(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert len(row["response_keys"]) == 3
    for cand in row["candidates"]:
        assert len(cand["response_scores"]) == len(row["response_keys"]) == 3
    assert len(row["candidates"]) == 2


def test_build_agg_row_response_keys_are_distinct(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert len(set(row["response_keys"])) == 3


def test_build_agg_row_exported_aggregate_matches_trace(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    by_key = {c["action_key"]: c for c in row["candidates"]}
    for cand_trace in trace.candidates:
        assert by_key[cand_trace.candidate_id]["exported_aggregate_score"] == pytest.approx(
            cand_trace.aggregate_score
        )
        assert by_key[cand_trace.candidate_id]["response_scores"] == pytest.approx(
            cand_trace.score_vector
        )


def test_build_agg_row_uses_candidate_id_as_action_key(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    action_keys = {c["action_key"] for c in row["candidates"]}
    assert action_keys == {"cand-A", "cand-B"}


def test_build_agg_row_carries_aggregation_context(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert row["aggregation_mode"] == "neutral"
    assert row["risk_lambda"] == pytest.approx(0.5)
    assert row["must_react_lambda"] == pytest.approx(0.6)
    assert row["game_mode"] == "NEUTRAL"


def test_build_agg_row_selected_action_key_is_canonical_normalized_choose(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    expected = json.dumps(
        normalize_choose(CHOOSE, req), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert row["selected_action_key"] == expected


def test_build_agg_row_teacher_best_action_keys_empty_in_this_task(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert row["teacher_best_action_keys"] == []


def test_build_agg_row_schema_version(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert row["agg_trace_schema_version"] == AGG_TRACE_SCHEMA_VERSION


def test_build_agg_row_none_choose_gives_none_selected_action_key(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=None, decision_index=0)
    assert row["selected_action_key"] is None


def test_build_agg_row_handles_trace_none(agg_context, decision_fixture):
    req, _kw = decision_fixture
    row = build_agg_row(context=agg_context, trace=None, request=req, choose=CHOOSE, decision_index=0)
    assert row["candidates"] == []
    assert row["response_keys"] == []
    assert row["response_weights"] == []
    assert row["aggregation_mode"] is None
    assert row["risk_lambda"] is None
    assert row["must_react_lambda"] is None
    validate_agg_row(row)  # must still be a valid row


# ---------------------------------------------------------------------------
# response_weights: real-world "unweighted" (empty list) is valid; a present
# but mismatched-length weights list is rejected. Confirmed against the real
# trace population (battle/decision.py: `trace.opponent_response_weights =
# resp_weights or []`) and against battle/policy.py::aggregate_scores's own
# `use_weights = weights is not None and len(weights) == len(scores) and ...`
# -- an empty/mismatched weights list is ALREADY treated as "unweighted" by
# the real aggregation formula, so the row format mirrors that exactly.
# ---------------------------------------------------------------------------

def test_build_agg_row_unweighted_real_decision_is_valid(agg_context, decision_fixture):
    """End-to-end: a real heuristic_choose_for_request call (no priors -> the
    trace's opponent_response_weights is []) must still build+validate a row."""
    from showdown_bot.battle.decision import heuristic_choose_for_request

    req, kw = decision_fixture
    trace = DecisionTrace()
    choose = heuristic_choose_for_request(req, trace=trace, **kw)
    assert trace.opponent_response_weights == []  # confirms the real unweighted case
    assert len(trace.opponent_responses) > 0

    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=choose, decision_index=0)
    assert row["response_weights"] == []
    assert len(row["response_keys"]) == len(trace.opponent_responses)
    for cand in row["candidates"]:
        assert len(cand["response_scores"]) == len(row["response_keys"])
    validate_agg_row(row)


def test_build_agg_row_weighted_responses_round_trip(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace(weights=[0.5, 0.3, 0.2])
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert row["response_weights"] == pytest.approx([0.5, 0.3, 0.2])
    assert len(row["response_weights"]) == len(row["response_keys"])


# ---------------------------------------------------------------------------
# Leakage guard
# ---------------------------------------------------------------------------

def test_build_agg_row_no_outcome_leakage(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    rendered = _row_json(row)
    assert "game_outcome" not in rendered
    assert "winner" not in rendered
    assert "teacher_trace" not in rendered


# ---------------------------------------------------------------------------
# validate_agg_row: fail-closed
# ---------------------------------------------------------------------------

def test_validate_agg_row_rejects_response_scores_length_mismatch(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["candidates"][0]["response_scores"] = row["candidates"][0]["response_scores"][:-1]
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_weights_length_mismatch(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace(weights=[0.5, 0.3, 0.2])
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["response_weights"] = row["response_weights"][:-1]  # length 2, neither 0 nor 3
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_accepts_empty_weights_with_nonempty_responses(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()  # weights default to []
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    assert row["response_weights"] == []
    validate_agg_row(row)  # must not raise


def test_validate_agg_row_rejects_non_finite_score(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["candidates"][0]["response_scores"][0] = float("nan")
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_non_finite_weight(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace(weights=[0.5, 0.3, 0.2])
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["response_weights"][0] = float("inf")
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_non_finite_lambda(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["risk_lambda"] = float("nan")
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_unknown_top_level_field(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["unexpected_field"] = 1
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_missing_required_field(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    del row["response_keys"]
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_unknown_candidate_field(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["candidates"][0]["extra"] = True
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_duplicate_candidate_action_key(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    dup = dict(row["candidates"][0])
    row["candidates"].append(dup)
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


def test_validate_agg_row_rejects_wrong_schema_version(agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    row = build_agg_row(context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0)
    row["agg_trace_schema_version"] = "some-other-version"
    with pytest.raises(AggTraceError):
        validate_agg_row(row)


# ---------------------------------------------------------------------------
# AggTraceWriter / load_agg_trace: mirrors DecisionTraceWriter mechanics
# ---------------------------------------------------------------------------

def test_writer_binds_count_and_sha(tmp_path, agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    path = tmp_path / "agg_trace.jsonl"
    writer = AggTraceWriter(path)
    writer.write(build_agg_row(
        context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0
    ))
    binding = writer.finish_battle(agg_context.battle_id)
    assert binding["agg_trace_count"] == 1
    assert len(binding["agg_trace_sha256"]) == 64
    assert load_agg_trace(path)[0]["battle_id"] == agg_context.battle_id


def test_writer_refuses_duplicate_decision_key(tmp_path, agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    writer = AggTraceWriter(tmp_path / "agg_trace.jsonl.gz")
    row = build_agg_row(
        context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0
    )
    writer.write(row)
    with pytest.raises(AggTraceError, match="duplicate decision key"):
        writer.write(row)


def test_load_agg_trace_gzip_roundtrip(tmp_path, agg_context, decision_fixture):
    req, _kw = decision_fixture
    trace = _fake_trace()
    path = tmp_path / "agg_trace.jsonl.gz"
    writer = AggTraceWriter(path)
    writer.write(build_agg_row(
        context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=0
    ))
    writer.write(build_agg_row(
        context=agg_context, trace=trace, request=req, choose=CHOOSE, decision_index=1
    ))
    rows = load_agg_trace(path)
    assert [r["decision_index"] for r in rows] == [0, 1]


def test_writer_refuses_nonempty_existing_output(tmp_path, agg_context):
    path = tmp_path / "agg_trace.jsonl"
    path.write_text("not empty\n", encoding="utf-8")
    with pytest.raises(AggTraceError, match="missing or empty"):
        AggTraceWriter(path)


def test_finish_battle_raises_when_no_rows(tmp_path, agg_context):
    writer = AggTraceWriter(tmp_path / "agg_trace.jsonl")
    with pytest.raises(AggTraceError):
        writer.finish_battle("no-such-battle")


def test_load_agg_trace_rejects_invalid_row(tmp_path):
    path = tmp_path / "agg_trace.jsonl"
    path.write_text('{"not": "a valid row"}\n', encoding="utf-8")
    with pytest.raises(AggTraceError):
        load_agg_trace(path)

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from showdown_bot.eval.decision_capture import (
    BattleTraceContext,
    DecisionCaptureError,
    DecisionTraceWriter,
    TRACE_SCHEMA_VERSION_V1,
    build_trace_row,
    load_decision_trace,
    normalize_choose,
    observable_state_payload,
    prepare_capture,
    validate_trace_row,
)
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def capture_fixture(decision_fixture):
    req, kw = decision_fixture
    return req, copy.deepcopy(kw["state"])


def test_observable_hash_is_order_independent(capture_fixture):
    request, state = capture_fixture
    left = prepare_capture(state, request)
    state.sides["p1"]["a"].boosts = {"spe": 1, "atk": -1}
    right = prepare_capture(state, request)
    state.sides["p1"]["a"].boosts = {"atk": -1, "spe": 1}
    again = prepare_capture(state, request)
    assert right.observable_state_hash == again.observable_state_hash
    assert left.request_hash == right.request_hash


def test_payload_has_explicit_allowlist(capture_fixture):
    _request, state = capture_fixture
    payload = observable_state_payload(state)
    rendered = json.dumps(payload, sort_keys=True)
    assert "game_outcome" not in rendered
    assert "winner" not in rendered
    assert "teacher" not in rendered


def test_prepare_capture_regular_turn_phase(capture_fixture):
    request, state = capture_fixture
    capture = prepare_capture(state, request)
    assert capture.decision_phase == "regular_turn"


def test_prepare_capture_team_preview_phase():
    data = json.loads((FIXTURES / "request_team_preview.json").read_text())
    request = BattleRequest.model_validate(data)
    capture = prepare_capture(None, request)
    assert capture.decision_phase == "team_preview"
    assert capture.state_summary == {"turn": 0, "field": {}, "sides": {}}


def test_prepare_capture_forced_replacement_phase():
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    request = BattleRequest.model_validate(data)
    capture = prepare_capture(None, request)
    assert capture.decision_phase == "forced_replacement"


@pytest.mark.parametrize(
    ("choose", "kind", "move_id", "target", "tera"),
    [
        ("/choose move 1 1, move 2 2|7", "joint", "fakeout", 1, False),
        ("/choose move 1 1 terastallize, pass|7", "joint", "fakeout", 1, True),
        ("/choose team 1234|7", "team_preview", None, None, False),
        ("/choose default|7", "default", None, None, False),
    ],
)
def test_normalize_choose(choose, kind, move_id, target, tera, capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose(choose, request)
    assert action["kind"] == kind
    if kind == "joint":
        assert action["slots"][0]["move_id"] == move_id
        assert action["slots"][0]["target"] == target
        assert action["slots"][0]["tera"] is tera


def test_normalize_choose_team_preview_order(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose team 1234|7", request)
    assert action["order"] == [1, 2, 3, 4]


def test_normalize_choose_switch(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose switch 3, move 1 1|7", request)
    assert action["kind"] == "joint"
    assert action["slots"][0] == {"kind": "switch", "switch_target": "3"}
    assert action["slots"][1]["kind"] == "move"
    assert action["slots"][1]["move_id"] == "heatwave"


def test_normalize_choose_protect_flags_is_protect(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose move 3 1, move 3 1|7", request)
    assert action["slots"][0]["move_id"] == "protect"
    assert action["slots"][0]["is_protect"] is True
    assert action["slots"][1]["move_id"] == "protect"
    assert action["slots"][1]["is_protect"] is True


def test_normalize_choose_negative_ally_target(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose move 4 -1, pass|7", request)
    assert action["slots"][0]["move_id"] == "knockoff"
    assert action["slots"][0]["target"] == -1
    assert action["slots"][1] == {"kind": "pass"}


def test_normalize_choose_forced_replacement():
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    request = BattleRequest.model_validate(data)
    action = normalize_choose("/choose switch 3, pass|5", request)
    assert action["kind"] == "joint"
    assert action["slots"][0] == {"kind": "switch", "switch_target": "3"}
    assert action["slots"][1] == {"kind": "pass"}


def test_normalize_choose_invalid_move_index_raises(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/choose move 9 1, pass|7", request)


def test_normalize_choose_unsupported_slot_token_raises(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/choose shift, pass|7", request)


def test_normalize_choose_unknown_command_raises(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/forfeit|7", request)


# ---------------------------------------------------------------------------
# Task 3: BattleTraceContext, build_trace_row, DecisionTraceWriter, loader
# ---------------------------------------------------------------------------

@pytest.fixture
def trace_context():
    return BattleTraceContext(
        battle_id="battle-a", seed_index=0, config_id="heuristic",
        config_hash="config-a", schedule_hash="schedule-a",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )


@pytest.fixture
def prepared(capture_fixture):
    request, state = capture_fixture
    return prepare_capture(state, request)


def test_writer_binds_count_and_sha(tmp_path, trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    path = tmp_path / "trace.jsonl"
    writer = DecisionTraceWriter(path)
    writer.write(build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose move 1 1, move 2 2|7", trace=None,
        decision_index=0, decision_latency_ms=12.5,
    ))
    binding = writer.finish_battle(trace_context.battle_id)
    assert binding["decision_trace_count"] == 1
    assert len(binding["decision_trace_sha256"]) == 64
    assert load_decision_trace(path)[0]["battle_id"] == trace_context.battle_id


def test_writer_refuses_duplicate_decision_key(tmp_path, trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    writer = DecisionTraceWriter(tmp_path / "trace.jsonl.gz")
    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose move 1 1, move 2 2|7", trace=None,
        decision_index=0, decision_latency_ms=1.0,
    )
    writer.write(row)
    with pytest.raises(DecisionCaptureError, match="duplicate decision key"):
        writer.write(row)


def test_load_decision_trace_gzip_roundtrip(tmp_path, trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    path = tmp_path / "trace.jsonl.gz"
    writer = DecisionTraceWriter(path)
    writer.write(build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose move 1 1, move 2 2|7", trace=None,
        decision_index=0, decision_latency_ms=1.0,
    ))
    writer.write(build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose move 1 1, move 2 2|7", trace=None,
        decision_index=1, decision_latency_ms=2.0,
    ))
    rows = load_decision_trace(path)
    assert [r["decision_index"] for r in rows] == [0, 1]


def test_writer_refuses_nonempty_existing_output(tmp_path, trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    path = tmp_path / "trace.jsonl"
    path.write_text("not empty\n", encoding="utf-8")
    with pytest.raises(DecisionCaptureError, match="missing or empty"):
        DecisionTraceWriter(path)


def test_build_trace_row_v2_fallback_without_trace(trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose default|7", trace=None, decision_index=0, decision_latency_ms=1.0,
        selection_stage_override="client_exception_default",
        fallback_reason_override="agent_exception",
    )
    assert row["trace_schema_version"] == "decision-trace-v2"
    assert row["candidates"] == []
    assert row["chosen_candidate_key"] is None
    assert row["chosen_candidate_id"] is None
    assert row["chosen_rank"] is None
    assert row["chosen_tera_slot"] is None
    assert row["selection_stage"] == "client_exception_default"
    assert row["fallback_reason"] == "agent_exception"


def test_load_decision_trace_accepts_v1_row():
    row = {
        "trace_schema_version": TRACE_SCHEMA_VERSION_V1,
        "battle_id": "b", "seed_index": 0, "decision_index": 0, "turn_number": 1,
        "our_side": "p1", "config_id": "heuristic", "config_hash": "c" * 64,
        "schedule_hash": "s" * 64, "format_id": "gen9vgc2025regi", "git_sha": "a" * 40,
        "observable_state_hash": "0" * 64, "request_hash": "1" * 64,
        "decision_phase": "regular_turn", "state_summary": {"turn": 1, "field": {}, "sides": {}},
        "actual_choose_string": "/choose move 1 1, pass|1",
        "normalized_action": {"kind": "joint", "slots": [{"kind": "pass"}, {"kind": "pass"}]},
        "chosen_candidate_id": "(Fake Out->1, pass)", "chosen_rank": 0,
        "candidates": [{"candidate_id": "(Fake Out->1, pass)", "rank": 0, "aggregate_score": 1.0}],
        "decision_latency_ms": 1.0,
    }
    validate_trace_row(row)

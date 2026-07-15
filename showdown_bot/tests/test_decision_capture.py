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
    TRACE_SCHEMA_VERSION_V2,
    TRACE_SCHEMA_VERSION_V3,
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


def test_build_trace_row_v3_fallback_without_trace(trace_context, prepared, capture_fixture):
    # All new writes are v3 (Task 1 migration): the three chosen-* keys are
    # always present, even when their value is null (no trace/no candidates).
    request, _state = capture_fixture
    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose default|7", trace=None, decision_index=0, decision_latency_ms=1.0,
        selection_stage_override="client_exception_default",
        fallback_reason_override="agent_exception",
    )
    assert row["trace_schema_version"] == TRACE_SCHEMA_VERSION_V3
    assert row["candidates"] == []
    assert "chosen_candidate_key" in row
    assert "chosen_mega_slot" in row
    assert "chosen_tera_slot" in row
    assert row["chosen_candidate_key"] is None
    assert row["chosen_candidate_id"] is None
    assert row["chosen_rank"] is None
    assert row["chosen_tera_slot"] is None
    assert row["chosen_mega_slot"] is None
    assert row["selection_stage"] == "client_exception_default"
    assert row["fallback_reason"] == "agent_exception"


# T37: legacy v1 trace rows remain loadable, untouched by the v3 migration.
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


@pytest.fixture
def v2_trace_row(trace_context, prepared, capture_fixture, decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace

    request, kw = decision_fixture
    trace = DecisionTrace()
    choose = heuristic_choose_for_request(request, trace=trace, **kw)
    return build_trace_row(
        context=trace_context,
        prepared=prepared,
        request=request,
        choose=choose,
        trace=trace,
        decision_index=0,
        decision_latency_ms=1.0,
    )


@pytest.fixture
def v2_only_trace_row(v2_trace_row):
    """A genuinely v2-schema row.

    ``v2_trace_row`` is built via ``build_trace_row``, which (since Task 1's
    v3 migration) always emits a v3-schema row -- despite the fixture's name.
    This fixture derives a row that actually dispatches to ``_validate_v2_row``
    (not ``_validate_v3_row``): force ``trace_schema_version`` back to v2 and
    drop ``chosen_mega_slot``, which is not a recognized v2 field. The
    candidate_key strings retain their v2-key-format ``mega_evolve`` field,
    but ``_validate_v2_row`` treats candidate_key as an opaque non-empty
    string (schema-shape enforcement is v3-only via
    ``_validate_candidate_key_v2``), so this is still exercising
    ``_validate_v2_row``'s own chosen_rank/chosen_candidate_id/tera_slot-type
    checks, which is what the tests below need.
    """
    row = dict(v2_trace_row)
    row["trace_schema_version"] = TRACE_SCHEMA_VERSION_V2
    del row["chosen_mega_slot"]
    return row


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("chosen_candidate_id", "wrong-id", "chosen_candidate_id must match"),
        ("chosen_rank", 999, "chosen_rank must match"),
        ("chosen_tera_slot", True, "chosen_tera_slot must be null or int"),
    ],
)
def test_validate_v2_row_rejects_inconsistent_chosen_fields(v2_only_trace_row, field, value, match):
    row = dict(v2_only_trace_row)
    row[field] = value
    with pytest.raises(DecisionCaptureError, match=match):
        validate_trace_row(row)


def test_load_decision_trace_rejects_v2_row_with_wrong_chosen_rank(tmp_path, v2_only_trace_row):
    row = dict(v2_only_trace_row)
    row["chosen_rank"] = 999
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(DecisionCaptureError, match="chosen_rank must match"):
        load_decision_trace(path)


def test_load_decision_trace_rejects_v2_row_with_bool_tera_slot(tmp_path, v2_only_trace_row):
    row = dict(v2_only_trace_row)
    row["chosen_tera_slot"] = True
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(DecisionCaptureError, match="chosen_tera_slot must be null or int"):
        load_decision_trace(path)


def _minimal_v2_switch_row(*, switch_target: str = "3"):
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.battle.candidate_identity import joint_action_key
    from showdown_bot.models.actions import SlotAction

    key = joint_action_key(JointAction(
        slot0=SlotAction(kind="switch", target_ident="3"),
        slot1=SlotAction(kind="pass"),
    ))
    return {
        "trace_schema_version": "decision-trace-v2",
        "battle_id": "b",
        "seed_index": 0,
        "decision_index": 0,
        "turn_number": 1,
        "our_side": "p1",
        "config_id": "heuristic",
        "config_hash": "c" * 64,
        "schedule_hash": "s" * 64,
        "format_id": "gen9vgc2025regi",
        "git_sha": "a" * 40,
        "observable_state_hash": "0" * 64,
        "request_hash": "1" * 64,
        "decision_phase": "regular_turn",
        "state_summary": {"turn": 1, "field": {}, "sides": {}},
        "actual_choose_string": f"/choose switch {switch_target}, pass|1",
        "normalized_action": {
            "kind": "joint",
            "slots": [
                {"kind": "switch", "switch_target": switch_target},
                {"kind": "pass"},
            ],
        },
        "chosen_candidate_id": "(switch, pass)",
        "chosen_candidate_key": key,
        "chosen_tera_slot": None,
        "chosen_rank": 0,
        "candidates": [{
            "candidate_id": "(switch, pass)",
            "candidate_key": key,
            "rank": 0,
            "aggregate_score": 1.0,
        }],
        "decision_latency_ms": 1.0,
    }


def test_load_decision_trace_rejects_v2_switch_target_mismatch(tmp_path):
    row = _minimal_v2_switch_row(switch_target="4")
    path = tmp_path / "bad-switch.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(DecisionCaptureError, match="switch target_ident mismatch"):
        load_decision_trace(path)


# T36: legacy v2 trace rows (v1-shaped candidate keys under the v2 schema) remain
# loadable, validated via the unchanged _validate_v2_row code path.
def test_minimal_v2_row_still_loads_unchanged():
    row = _minimal_v2_switch_row()
    validate_trace_row(row)


# ---------------------------------------------------------------------------
# Task 1 (I7a-B): candidate-key v2 and trace-v3.
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_v3_row(v2_trace_row):
    row = copy.deepcopy(v2_trace_row)
    row["trace_schema_version"] = TRACE_SCHEMA_VERSION_V3
    row["chosen_mega_slot"] = None
    for candidate in row["candidates"]:
        payload = json.loads(candidate["candidate_key"])
        payload["version"] = 2
        for slot in payload["slots"]:
            slot["mega_evolve"] = False
        candidate["candidate_key"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    old_chosen = row["chosen_candidate_key"]
    old_to_new = {
        v2["candidate_key"]: v3["candidate_key"]
        for v2, v3 in zip(v2_trace_row["candidates"], row["candidates"], strict=True)
    }
    row["chosen_candidate_key"] = old_to_new[old_chosen]
    return row


def mutate_v3_row(row, mutation):
    row = copy.deepcopy(row)
    payload = json.loads(row["candidates"][0]["candidate_key"])
    if mutation == "v1_key":
        payload["version"] = 1
    elif mutation == "missing_mega_field":
        del payload["slots"][0]["mega_evolve"]
    elif mutation == "unknown_slot_field":
        payload["slots"][0]["extra"] = 1
    elif mutation == "non_bool_tera":
        payload["slots"][0]["terastallize"] = 1
    elif mutation == "dual_overlay":
        payload["slots"][0]["terastallize"] = True
        payload["slots"][0]["mega_evolve"] = True
    elif mutation == "duplicate_key":
        row["candidates"][1]["candidate_key"] = row["candidates"][0]["candidate_key"]
        return row
    elif mutation == "non_canonical_json":
        # Same payload, valid JSON, but not the canonical serialization
        # (extra whitespace after the colon) -- must fail-closed (I7a-B Task 4).
        # Mutate chosen_candidate_key in lockstep (when it originally matched
        # candidates[0]'s key) so this isolates the canonical-format check
        # itself, rather than accidentally tripping the unrelated "chosen_key
        # must reference a traced candidate" check via a now-mismatched
        # literal string.
        original_key = row["candidates"][0]["candidate_key"]
        mutated_key = json.dumps(payload, sort_keys=True, separators=(",", ": "))
        row["candidates"][0]["candidate_key"] = mutated_key
        if row.get("chosen_candidate_key") == original_key:
            row["chosen_candidate_key"] = mutated_key
        return row
    else:
        raise AssertionError(mutation)
    row["candidates"][0]["candidate_key"] = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    )
    return row


def test_valid_v3_row_validates(valid_v3_row):
    validate_trace_row(valid_v3_row)


@pytest.mark.parametrize("mutation", [
    "v1_key", "missing_mega_field", "unknown_slot_field",
    "non_bool_tera", "dual_overlay", "duplicate_key", "non_canonical_json",
])
def test_v3_rejects_invalid_candidate_keys(valid_v3_row, mutation):
    row = mutate_v3_row(valid_v3_row, mutation)
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# ---------------------------------------------------------------------------
# I7a-B merge-blocker follow-up (Task 4): candidate-key-v2 must be canonical,
# not merely well-formed JSON matching the schema.
# ---------------------------------------------------------------------------

_CANONICAL_KEY_PAYLOAD = {
    "version": 2,
    "slots": [
        {
            "kind": "pass", "move_index": None, "target": None,
            "target_ident": None, "terastallize": False, "mega_evolve": False,
        },
        {
            "kind": "pass", "move_index": None, "target": None,
            "target_ident": None, "terastallize": False, "mega_evolve": False,
        },
    ],
}


def test_validate_candidate_key_v2_accepts_canonical_serialization():
    from showdown_bot.eval.decision_capture import _validate_candidate_key_v2

    canonical = json.dumps(
        _CANONICAL_KEY_PAYLOAD, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    _validate_candidate_key_v2(canonical)  # must not raise


def test_validate_candidate_key_v2_rejects_non_canonical_single_key():
    """A single key string that is valid JSON, matches the schema, and
    round-trips to the SAME payload as the canonical serialization, but is
    not byte-for-byte the canonical string itself, must fail-closed."""
    from showdown_bot.eval.decision_capture import _validate_candidate_key_v2

    canonical = json.dumps(
        _CANONICAL_KEY_PAYLOAD, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    non_canonical = canonical.replace(":", ": ")  # extra whitespace after each colon
    assert non_canonical != canonical
    assert json.loads(non_canonical) == json.loads(canonical)
    with pytest.raises(DecisionCaptureError, match="canonical"):
        _validate_candidate_key_v2(non_canonical)


def test_validate_candidate_key_v2_rejects_two_textually_different_semantically_identical_keys():
    """Two key strings that decode to the EXACT same payload (semantically
    identical) but are textually different from each other and from the
    canonical serialization -- both must be individually fail-closed
    rejected, not just one of them."""
    from showdown_bot.eval.decision_capture import _validate_candidate_key_v2

    canonical = json.dumps(
        _CANONICAL_KEY_PAYLOAD, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    key_a = canonical.replace(":", ": ")   # extra space after colons
    key_b = canonical.replace(",", ", ")   # extra space after commas
    assert key_a != key_b
    assert json.loads(key_a) == json.loads(key_b) == json.loads(canonical)

    with pytest.raises(DecisionCaptureError, match="canonical"):
        _validate_candidate_key_v2(key_a)
    with pytest.raises(DecisionCaptureError, match="canonical"):
        _validate_candidate_key_v2(key_b)


@pytest.mark.parametrize("missing_field", [
    "chosen_candidate_key", "chosen_mega_slot", "chosen_tera_slot",
])
def test_v3_rejects_row_missing_chosen_key_field(valid_v3_row, missing_field):
    # v3 requires the three chosen-* keys to be PRESENT (value may be null) --
    # entirely omitting the key (as opposed to setting it to null) must fail.
    row = copy.deepcopy(valid_v3_row)
    del row[missing_field]
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)

"""I7a-B Task 1: candidate-key v2 and decision-trace v3 (identity/schema layer only).

No Mega ranking/scoring logic is exercised here -- the non-Mega decision path is
migrated to key-v2/trace-v3 bookkeeping, and the v3 validators are exercised
directly against literal/constructed rows. See ``docs/superpowers/specs/
2026-07-14-champions-mega-i7-design.md`` Sec.13 for the authoritative schema.
"""
from __future__ import annotations

import copy
import json

import pytest


@pytest.fixture
def capture_fixture(decision_fixture):
    req, kw = decision_fixture
    return req, copy.deepcopy(kw["state"])

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.candidate_identity import (
    ChosenCandidateResolutionError,
    joint_action_key_v2,
    resolve_chosen_candidate,
)
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown
from showdown_bot.eval.decision_capture import (
    DecisionCaptureError,
    SUPPORTED_TRACE_SCHEMA_VERSIONS,
    TRACE_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION_V1,
    TRACE_SCHEMA_VERSION_V2,
    TRACE_SCHEMA_VERSION_V3,
    normalize_choose,
    validate_trace_row,
)
from showdown_bot.models.actions import SlotAction


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_supported_schema_versions_include_v3():
    assert SUPPORTED_TRACE_SCHEMA_VERSIONS == frozenset({
        TRACE_SCHEMA_VERSION_V1, TRACE_SCHEMA_VERSION_V2, TRACE_SCHEMA_VERSION_V3,
    })
    assert TRACE_SCHEMA_VERSION == TRACE_SCHEMA_VERSION_V3


# ---------------------------------------------------------------------------
# /choose normalization: mega overlay token
# ---------------------------------------------------------------------------

def test_normalize_choose_accepts_mega_overlay_token(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose move 1 1 mega, pass|7", request)
    assert action["kind"] == "joint"
    assert action["slots"][0]["mega"] is True
    assert action["slots"][0]["tera"] is False


def test_normalize_choose_rejects_dual_overlay_token(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/choose move 1 1 terastallize mega, pass|7", request)


# ---------------------------------------------------------------------------
# _label_ja: mega suffix (labels are diagnostic only)
# ---------------------------------------------------------------------------

def test_label_ja_adds_mega_suffix(decision_fixture):
    from showdown_bot.battle.decision import _label_ja

    req, _kw = decision_fixture
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1, mega_evolve=True),
        slot1=SlotAction(kind="pass"),
    )
    label = _label_ja(req, ja)
    assert label.startswith("(")
    assert " mega" in label.split(",")[0]


# ---------------------------------------------------------------------------
# decision.py candidate population uses key-v2 (no v1 keys leak into v3 rows)
# ---------------------------------------------------------------------------

def test_heuristic_decision_populates_v2_candidate_keys(decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request

    req, kw = decision_fixture
    trace = DecisionTrace()
    heuristic_choose_for_request(req, trace=trace, **kw)

    assert trace.candidates, "expected at least one traced candidate"
    for cand in trace.candidates:
        payload = json.loads(cand.candidate_key)
        assert payload["version"] == 2
        for slot in payload["slots"]:
            assert "mega_evolve" in slot

    chosen_payload = json.loads(trace.chosen_candidate_key)
    assert chosen_payload["version"] == 2
    assert trace.chosen_mega_slot is None


def test_build_trace_row_from_real_decision_is_v3(trace_context, prepared, capture_fixture, decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.eval.decision_capture import build_trace_row

    request, kw = decision_fixture
    trace = DecisionTrace()
    choose = heuristic_choose_for_request(request, trace=trace, **kw)
    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose=choose, trace=trace, decision_index=0, decision_latency_ms=1.0,
    )
    assert row["trace_schema_version"] == TRACE_SCHEMA_VERSION_V3
    assert row["chosen_mega_slot"] is None
    validate_trace_row(row)


# ---------------------------------------------------------------------------
# Fixtures: trace_context / prepared / capture_fixture are provided by the
# top-level tests/conftest.py.
# ---------------------------------------------------------------------------

@pytest.fixture
def trace_context():
    from showdown_bot.eval.decision_capture import BattleTraceContext

    return BattleTraceContext(
        battle_id="battle-i7a", seed_index=0, config_id="heuristic",
        config_hash="config-a", schedule_hash="schedule-a",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )


@pytest.fixture
def prepared(capture_fixture):
    from showdown_bot.eval.decision_capture import prepare_capture

    request, state = capture_fixture
    return prepare_capture(state, request)


# ---------------------------------------------------------------------------
# T33/T34/T35: mega vs tera chosen-slot semantics
# ---------------------------------------------------------------------------

def _minimal_v3_row(*, key_mega_evolve_slot0: bool, chosen_mega_slot,
                    chosen_tera_slot=None, normalized_mega_slot0: bool):
    """Build a minimal literal v3 row with exactly one candidate (the chosen
    one), so the mega-key-consistency and normalized-action-consistency checks
    can be exercised independently of a real decision/request."""
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1, mega_evolve=key_mega_evolve_slot0),
        slot1=SlotAction(kind="pass"),
    )
    key = joint_action_key_v2(ja)
    return {
        "trace_schema_version": TRACE_SCHEMA_VERSION_V3,
        "battle_id": "b", "seed_index": 0, "decision_index": 0, "turn_number": 1,
        "our_side": "p1", "config_id": "heuristic", "config_hash": "c" * 64,
        "schedule_hash": "s" * 64, "format_id": "gen9vgc2025regi", "git_sha": "a" * 40,
        "observable_state_hash": "0" * 64, "request_hash": "1" * 64,
        "decision_phase": "regular_turn", "state_summary": {"turn": 1, "field": {}, "sides": {}},
        "actual_choose_string": "/choose move 1 1 mega, pass|1",
        "normalized_action": {
            "kind": "joint",
            "slots": [
                {
                    "kind": "move", "move_index": 1, "move_id": "flamethrower", "target": 1,
                    "tera": False, "mega": normalized_mega_slot0, "is_protect": False,
                },
                {"kind": "pass"},
            ],
        },
        "chosen_candidate_id": "(Flamethrower->1 mega, pass)",
        "chosen_candidate_key": key,
        "chosen_tera_slot": chosen_tera_slot,
        "chosen_mega_slot": chosen_mega_slot,
        "chosen_rank": 0,
        "candidates": [{
            "candidate_id": "(Flamethrower->1 mega, pass)",
            "candidate_key": key,
            "rank": 0,
            "aggregate_score": 1.0,
        }],
        "decision_latency_ms": 1.0,
    }


def test_v3_valid_mega_row_validates():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=True, chosen_mega_slot=0,
        chosen_tera_slot=None, normalized_mega_slot0=True,
    )
    validate_trace_row(row)


# T33: both chosen_mega_slot and chosen_tera_slot set -> reject.
def test_v3_rejects_both_mega_and_tera_slot_set():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=True, chosen_mega_slot=0,
        chosen_tera_slot=1, normalized_mega_slot0=True,
    )
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# T34: chosen_mega_slot points at a slot whose candidate_key mega_evolve flag
# doesn't match -> reject.
def test_v3_rejects_chosen_mega_key_mismatch():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=False, chosen_mega_slot=0,
        chosen_tera_slot=None, normalized_mega_slot0=True,
    )
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# T35: normalized_action's mega marker disagrees with chosen_mega_slot -> reject.
def test_v3_rejects_normalized_mega_mismatch():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=True, chosen_mega_slot=0,
        chosen_tera_slot=None, normalized_mega_slot0=False,
    )
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# ---------------------------------------------------------------------------
# resolve_chosen_candidate: v2 keys distinguish mega/non-mega candidates and
# resolve exactly once.
# ---------------------------------------------------------------------------

def _ct(*, candidate_key: str, rank: int) -> CandidateTrace:
    return CandidateTrace(
        candidate_id="x", joint_action=None, rank=rank, aggregate_score=1.0,
        score_vector=[1.0], outcome_breakdowns=[OutcomeBreakdown()],
        aggregate_breakdown=OutcomeBreakdown(), candidate_key=candidate_key,
    )


def test_resolve_chosen_candidate_v2_mega_key_resolves_exactly_once():
    ja_plain = JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass"))
    ja_mega = ja_plain.with_mega(0)
    key_plain, key_mega = joint_action_key_v2(ja_plain), joint_action_key_v2(ja_mega)
    assert key_plain != key_mega

    trace = DecisionTrace(
        chosen_candidate_key=key_mega, chosen_mega_slot=0,
        candidates=[_ct(candidate_key=key_plain, rank=1), _ct(candidate_key=key_mega, rank=0)],
    )
    resolved = resolve_chosen_candidate(trace)
    assert resolved.candidate_key == key_mega
    assert resolved.rank == 0


def test_resolve_chosen_candidate_v2_key_ambiguous_raises():
    dup = joint_action_key_v2(JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass")))
    trace = DecisionTrace(
        chosen_candidate_key=dup,
        candidates=[_ct(candidate_key=dup, rank=0), _ct(candidate_key=dup, rank=1)],
    )
    with pytest.raises(ChosenCandidateResolutionError, match="ambiguous"):
        resolve_chosen_candidate(trace)

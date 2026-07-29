from __future__ import annotations

import re

from showdown_bot.client.live_degradation import (
    ATTRIBUTIONS,
    BATTLE_FIELDS,
    COMPLETION_FIELDS,
    DECISION_FIELDS,
    END_REASONS,
    EVENT_FIELDS,
    EVENT_TYPES,
    OUTCOMES,
    SCHEMA_VERSION,
)


def test_schema_version_literal():
    assert SCHEMA_VERSION == "live-degradation-v1"


def test_decision_fields_are_exactly_the_contract():
    assert DECISION_FIELDS == (
        "schema_version", "run_id", "room_id", "decision_seq", "rqid",
        "book_absent", "team_preview", "state_build_failed",
        "selection_stage", "fallback_reason", "agent_crash_type",
        "derivation_applicable", "is_degraded", "outcome",
    )


def test_battle_fields_are_exactly_the_contract():
    assert BATTLE_FIELDS == (
        "schema_version", "run_id", "room_id", "decisions_total",
        "decisions_not_applicable", "degraded_decisions", "state_build_failures",
        "agent_crashes", "fallback_decisions", "own_invalid_choices",
        "server_errors", "end_reason", "write_errors",
    )


def test_event_fields_are_exactly_the_contract():
    assert EVENT_FIELDS == (
        "schema_version", "run_id", "event_type", "attribution",
        "room_id", "payload", "active_battle_count",
    )


def test_completion_fields_are_exactly_the_contract():
    assert COMPLETION_FIELDS == (
        "schema_version", "run_id", "battles_finished", "unterminated_rooms",
        "write_errors_total", "schema_errors_total", "recorder_errors_total",
        "preflight_ok",
    )


def test_vocabularies_are_closed():
    assert EVENT_TYPES == ("server_error", "invalid_choice_pm")
    assert ATTRIBUTIONS == ("room", "inferred", "unattributed")
    assert END_REASONS == ("win", "tie", "unterminated")
    assert OUTCOMES == ("ok", "crash", "fallback", "degraded_state", "not_applicable")


def test_outcomes_extend_the_existing_vocabulary_by_exactly_one_value():
    """OUTCOMES must be the four existing decision-profile outcomes plus the single
    gate value from 5.1 -- not a second, drifting vocabulary (C6)."""
    from showdown_bot.eval import decision_profile

    assert set(OUTCOMES) - set(decision_profile._OUTCOMES) == {"not_applicable"}
    assert set(decision_profile._OUTCOMES) - set(OUTCOMES) == set()


def test_no_hero_or_villain_field_anywhere():
    """C7: the live runner holds one seat; hero_/villain_ names would be
    structurally always zero and read as 'clean' rather than 'not observable'."""
    every = DECISION_FIELDS + EVENT_FIELDS + BATTLE_FIELDS + COMPLETION_FIELDS
    assert not [f for f in every if f.startswith(("hero_", "villain_"))]


import pytest  # noqa: E402

from showdown_bot.client.live_degradation import (  # noqa: E402
    SchemaError,
    validate_battle_row,
    validate_completion_row,
    validate_decision_row,
    validate_event_row,
)

VALID_DECISION = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "room_id": "battle-gen9vgc2025regg-1", "decision_seq": 0, "rqid": 7,
    "book_absent": False, "team_preview": False, "state_build_failed": False,
    "selection_stage": "heuristic", "fallback_reason": None, "agent_crash_type": None,
    "derivation_applicable": True, "is_degraded": False, "outcome": "ok",
}

VALID_EVENT = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "event_type": "server_error", "attribution": "room",
    "room_id": "battle-gen9vgc2025regg-1",
    "payload": "[Invalid choice] Can't move: Zamazenta needs a target",
    "active_battle_count": 2,
}

VALID_BATTLE = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "room_id": "battle-gen9vgc2025regg-1", "decisions_total": 10,
    "decisions_not_applicable": 1, "degraded_decisions": 2, "state_build_failures": 1,
    "agent_crashes": 0, "fallback_decisions": 1, "own_invalid_choices": 0,
    "server_errors": 1, "end_reason": "win", "write_errors": 0,
}

VALID_COMPLETION = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "battles_finished": 3, "unterminated_rooms": ["battle-gen9vgc2025regg-9"],
    "write_errors_total": 0, "schema_errors_total": 0, "recorder_errors_total": 0,
    "preflight_ok": True,
}


def _mutate(base: dict, **changes) -> dict:
    """Replace values IN PLACE of the original keys, preserving insertion order."""
    out = dict(base)
    out.update(changes)
    return out


def _without(base: dict, key: str) -> dict:
    out = dict(base)
    del out[key]
    return out


def _reordered(row: dict) -> dict:
    """Same keys and values, first two swapped -- a different artifact that still parses."""
    keys = list(row)
    keys[0], keys[1] = keys[1], keys[0]
    return {k: row[k] for k in keys}


def test_the_four_valid_rows_pass():
    """Every mutation below starts from one of these, so if any of them were invalid the
    whole suite would be testing the wrong thing."""
    validate_decision_row(dict(VALID_DECISION))
    validate_event_row(dict(VALID_EVENT))
    validate_battle_row(dict(VALID_BATTLE))
    validate_completion_row(dict(VALID_COMPLETION))


DECISION_MUTATIONS = [
    ("missing_field", _without(VALID_DECISION, "rqid"), "field set/order mismatch"),
    ("extra_field", _mutate(VALID_DECISION, hero_wins=1), "field set/order mismatch"),
    ("wrong_order", _reordered(VALID_DECISION), "field set/order mismatch"),
    ("wrong_schema_version",
     _mutate(VALID_DECISION, schema_version="live-degradation-v2"), "schema_version="),
    ("empty_run_id", _mutate(VALID_DECISION, run_id=""), "run_id must be a non-empty str"),
    ("empty_room_id", _mutate(VALID_DECISION, room_id=""), "room_id must be a non-empty str"),
    ("seq_is_bool",
     _mutate(VALID_DECISION, decision_seq=True), "decision_seq must be a non-negative int"),
    ("seq_negative",
     _mutate(VALID_DECISION, decision_seq=-1), "decision_seq must be a non-negative int"),
    ("rqid_is_str", _mutate(VALID_DECISION, rqid="7"), "rqid must be int or None"),
    ("book_absent_is_int", _mutate(VALID_DECISION, book_absent=1), "book_absent must be bool"),
    ("stage_empty_string",
     _mutate(VALID_DECISION, selection_stage=""), "selection_stage must be a non-empty str"),
    ("unknown_outcome", _mutate(VALID_DECISION, outcome="weird"), "outcome='weird' not in"),
    ("is_degraded_is_str",
     _mutate(VALID_DECISION, is_degraded="yes"), "is_degraded must be bool or None"),
    ("gate_disagrees_with_book_absent",
     _mutate(VALID_DECISION, book_absent=True), "contradicts the section 5.1 rule"),
    ("gate_disagrees_with_team_preview",
     _mutate(VALID_DECISION, team_preview=True), "contradicts the section 5.1 rule"),
    ("not_applicable_outcome_while_gate_true",
     _mutate(VALID_DECISION, outcome="not_applicable"),
     "requires the gate to be false"),
    ("gate_false_but_is_degraded_is_false",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             selection_stage=None, outcome="not_applicable", is_degraded=False),
     "gate false requires is_degraded=None"),
    ("gate_false_but_stage_set",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             outcome="not_applicable", is_degraded=None),
     "gate false requires selection_stage=None"),
    ("gate_false_but_reason_set",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             selection_stage=None, fallback_reason="heuristic_timeout",
             outcome="not_applicable", is_degraded=None),
     "gate false requires fallback_reason=None"),
    ("state_build_failed_while_gate_false",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             state_build_failed=True, selection_stage=None, is_degraded=None,
             outcome="not_applicable"),
     "impossible with the gate false"),
    ("gate_true_but_is_degraded_null",
     _mutate(VALID_DECISION, is_degraded=None), "gate true requires a bool is_degraded"),
    ("crash_type_without_crash_outcome",
     _mutate(VALID_DECISION, agent_crash_type="ValueError"),
     "agent_crash_type set but outcome="),
    ("crash_outcome_without_crash_type",
     _mutate(VALID_DECISION, outcome="crash", is_degraded=True),
     "outcome=crash requires agent_crash_type"),
    ("state_build_failed_not_degraded",
     _mutate(VALID_DECISION, state_build_failed=True),
     "dominate and force is_degraded=True"),
    ("invented_stage",
     _mutate(VALID_DECISION, selection_stage="invented"),
     "selection_stage='invented' not in"),
    ("reason_on_a_completed_heuristic_decision",
     _mutate(VALID_DECISION, fallback_reason="heuristic_timeout"), "is not permitted on"),
    ("unknown_fallback_reason",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="made_up", is_degraded=True, outcome="fallback"),
     "is not permitted on"),
    ("reason_not_allowed_for_its_stage",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="default_pair_error", is_degraded=True, outcome="fallback"),
     "is not permitted on"),
    ("fallback_outcome_on_the_heuristic_stage",
     _mutate(VALID_DECISION, outcome="fallback", is_degraded=True),
     "on a clean decision means"),
    ("ok_outcome_on_a_fallback_stage",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="heuristic_timeout", is_degraded=True, outcome="ok"),
     "is a fallback stage, so outcome must be"),
    ("degraded_state_outcome_without_a_failed_build",
     _mutate(VALID_DECISION, selection_stage="deterministic_default_pair",
             fallback_reason="max_damage_error", is_degraded=True, outcome="degraded_state"),
     "is a fallback stage, so outcome must be"),
    ("stage_absent_without_a_crash",
     _mutate(VALID_DECISION, selection_stage=None, is_degraded=True, outcome="fallback"),
     "no crash"),
    ("reason_missing_on_max_damage_fallback",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback", fallback_reason=None,
             is_degraded=True, outcome="fallback"),
     "unreachable without a fallback_reason"),
    ("reason_missing_on_server_default",
     _mutate(VALID_DECISION, selection_stage="server_default", fallback_reason=None,
             is_degraded=True, outcome="fallback"),
     "unreachable without a fallback_reason"),
    ("reason_less_default_pair_without_a_failed_state_build",
     _mutate(VALID_DECISION, selection_stage="deterministic_default_pair",
             fallback_reason=None, state_build_failed=False, is_degraded=True,
             outcome="fallback"),
     "state-is-None path"),
    ("is_degraded_true_on_a_clean_heuristic_decision",
     _mutate(VALID_DECISION, is_degraded=True), "contradicts is_degraded_decision"),
    ("is_degraded_false_on_a_fallback_stage",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="heuristic_timeout", is_degraded=False, outcome="fallback"),
     "contradicts is_degraded_decision"),
]


@pytest.mark.parametrize("label,row,fragment", DECISION_MUTATIONS,
                         ids=[m[0] for m in DECISION_MUTATIONS])
def test_decision_mutation_is_rejected(label, row, fragment):
    """The fragment check is what stops a mutation passing for the WRONG reason: without it,
    a row mutated to test rule A could be rejected by unrelated rule B and the test would
    still be green while rule A was missing."""
    with pytest.raises(SchemaError, match=re.escape(fragment)):
        validate_decision_row(dict(row))


def test_deterministic_default_pair_may_carry_no_reason_on_the_degraded_state_path():
    """Route 1 of 2: state is None, so the reason is unset. With the gate true that can only
    mean the build was attempted and failed, and state dominance makes the outcome
    degraded_state -- never fallback."""
    validate_decision_row(_mutate(
        VALID_DECISION, selection_stage="deterministic_default_pair", fallback_reason=None,
        state_build_failed=True, is_degraded=True, outcome="degraded_state"))


def test_deterministic_default_pair_with_its_reason_is_a_plain_fallback():
    """Route 2 of 2: the state WAS built, max_damage_choice raised, so the reason is set."""
    validate_decision_row(_mutate(
        VALID_DECISION, selection_stage="deterministic_default_pair",
        fallback_reason="max_damage_error", is_degraded=True, outcome="fallback"))


def test_a_crash_before_the_stage_sink_was_written_is_legitimate():
    """The one case where selection_stage=None survives the gate: the chooser raised before
    _mark_selection ran."""
    validate_decision_row(_mutate(
        VALID_DECISION, selection_stage=None, agent_crash_type="ValueError",
        is_degraded=True, outcome="crash"))

from __future__ import annotations

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

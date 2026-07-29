"""live-degradation-v1: own-seat degradation evidence for the live runner.

Implements docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md.
Deliberately independent of eval/decision_profile's CLOSED schema (section 8, C6): this module
imports that module's two derivation functions and its stage/reason vocabulary, and nothing
else. It never writes a decision-profile row.
"""
from __future__ import annotations

SCHEMA_VERSION = "live-degradation-v1"

DECISION_FIELDS = (
    "schema_version", "run_id", "room_id", "decision_seq", "rqid",
    "book_absent", "team_preview", "state_build_failed",
    "selection_stage", "fallback_reason", "agent_crash_type",
    "derivation_applicable", "is_degraded", "outcome",
)
EVENT_FIELDS = (
    "schema_version", "run_id", "event_type", "attribution",
    "room_id", "payload", "active_battle_count",
)
BATTLE_FIELDS = (
    "schema_version", "run_id", "room_id", "decisions_total",
    "decisions_not_applicable", "degraded_decisions", "state_build_failures",
    "agent_crashes", "fallback_decisions", "own_invalid_choices",
    "server_errors", "end_reason", "write_errors",
)
COMPLETION_FIELDS = (
    "schema_version", "run_id", "battles_finished", "unterminated_rooms",
    "write_errors_total", "schema_errors_total", "recorder_errors_total",
    "preflight_ok",
)

EVENT_TYPES = ("server_error", "invalid_choice_pm")
ATTRIBUTIONS = ("room", "inferred", "unattributed")
END_REASONS = ("win", "tie", "unterminated")

# The four EXISTING classify_live_outcome values plus the single gate value from 5.1.
# Not a second vocabulary -- test_outcomes_extend_the_existing_vocabulary_by_exactly_one_value
# pins it against decision_profile._OUTCOMES so the two can never drift apart.
OUTCOMES = ("ok", "crash", "fallback", "degraded_state", "not_applicable")

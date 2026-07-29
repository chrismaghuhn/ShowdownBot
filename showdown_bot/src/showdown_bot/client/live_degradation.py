"""live-degradation-v1: own-seat degradation evidence for the live runner.

Implements docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md.
Deliberately independent of eval/decision_profile's CLOSED schema (section 8, C6): this module
imports that module's two derivation functions and its stage/reason vocabulary, and nothing
else. It never writes a decision-profile row.
"""
from __future__ import annotations

from showdown_bot.eval.decision_profile import (
    LIVE_FALLBACK_STAGES,
    LIVE_OK_STAGE,
    STAGE_ALLOWED_REASONS,
    is_degraded_decision,
)

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

# The stages the LIVE path can actually produce. Imported, never re-spelled: these are
# decision_profile's frozen I8-D vocabulary, and a second copy here would be free to drift.
# "team_preview" is deliberately absent -- the 5.1 gate excludes it before the derivation runs --
# and so are the BASELINE_* stages, which only the gauntlet's max_damage arm emits.
LIVE_STAGES = frozenset({LIVE_OK_STAGE}) | LIVE_FALLBACK_STAGES

# Fallback stages that CANNOT be reached with fallback_reason=None, read off
# choose_with_fallback's control flow rather than guessed:
#   max_damage_fallback -- only reachable after the heuristic block ran and failed, which is the
#     one place heuristic_timeout/heuristic_error are set. If the heuristic block was skipped
#     (no state, no book) the max_damage branch is skipped by the same condition, so this stage
#     is never marked with the reason still unset.
#   server_default      -- marked literally as
#     _mark_selection(trace, "server_default", "default_pair_error", stage_sink=stage_sink).
# deterministic_default_pair is deliberately NOT here: on the state-is-None path both blocks
# above are skipped and it is marked with the reason still None, which is legitimate.
STAGES_REQUIRING_A_REASON = frozenset({"max_damage_fallback", "server_default"})


class SchemaError(ValueError):
    """A row this module built does not satisfy live-degradation-v1.

    This is a DEFECT signal, not an expected runtime condition: every row is built by this module
    from its own inputs. It is raised by the four validators only, and the recorder always catches
    it -- never the caller, so it can never reach a battle (C11). What "catching" means depends on
    the grain:

      decision / event -> count it, do NOT buffer the row
      battle           -> count it, write the decisions and events but not the battle row
      completion       -> count it, write no completion.json at all

    In every case schema_errors_total is incremented. For the first three grains that count is
    then persisted by the completion write that follows, so the rejection reaches the artifact.
    For the fourth it cannot: the completion write is what the rejection prevented. That one case
    is signalled by logger.error, a non-zero exit and the ABSENCE of completion.json -- a state
    section 8.0 already equates with non-zero counters.
    """


def _require_shape(row: dict, fields: tuple[str, ...], what: str) -> None:
    """Field set AND ORDER. Order matters because the JSONL is read positionally by eye and
    diffed line-by-line; a reordered row is a different artifact even if it parses the same."""
    actual = tuple(row)
    if actual != fields:
        missing = [f for f in fields if f not in row]
        extra = [f for f in actual if f not in fields]
        raise SchemaError(
            f"{what}: field set/order mismatch; missing={missing} extra={extra} "
            f"actual={list(actual)}"
        )
    if row["schema_version"] != SCHEMA_VERSION:
        raise SchemaError(f"{what}: schema_version={row['schema_version']!r}")
    if not isinstance(row["run_id"], str) or not row["run_id"]:
        raise SchemaError(f"{what}: run_id must be a non-empty str, got {row['run_id']!r}")


def _is_int(value: object) -> bool:
    """bool is a subclass of int; True must never pass as a counter or a sequence number."""
    return isinstance(value, int) and not isinstance(value, bool)


def _require_bool(row: dict, key: str, what: str) -> None:
    if not isinstance(row[key], bool):
        raise SchemaError(f"{what}: {key} must be bool, got {row[key]!r}")


def _require_str_or_none(row: dict, key: str, what: str) -> None:
    value = row[key]
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise SchemaError(
            f"{what}: {key} must be a non-empty str or None (no sentinel or empty "
            f"strings, section 8 null rules), got {value!r}"
        )


def _require_count(row: dict, key: str, what: str) -> None:
    if not _is_int(row[key]) or row[key] < 0:
        raise SchemaError(f"{what}: {key} must be a non-negative int, got {row[key]!r}")


def validate_decision_row(row: dict) -> None:
    what = "decision row"
    _require_shape(row, DECISION_FIELDS, what)

    if not isinstance(row["room_id"], str) or not row["room_id"]:
        raise SchemaError(f"{what}: room_id must be a non-empty str, got {row['room_id']!r}")
    _require_count(row, "decision_seq", what)
    if row["rqid"] is not None and not _is_int(row["rqid"]):
        raise SchemaError(f"{what}: rqid must be int or None, got {row['rqid']!r}")
    for key in ("book_absent", "team_preview", "state_build_failed", "derivation_applicable"):
        _require_bool(row, key, what)
    for key in ("selection_stage", "fallback_reason", "agent_crash_type"):
        _require_str_or_none(row, key, what)
    if row["is_degraded"] is not None and not isinstance(row["is_degraded"], bool):
        raise SchemaError(f"{what}: is_degraded must be bool or None, got {row['is_degraded']!r}")
    if row["outcome"] not in OUTCOMES:
        raise SchemaError(f"{what}: outcome={row['outcome']!r} not in {OUTCOMES}")

    applicable = row["derivation_applicable"]
    expected = (not row["book_absent"]) and (not row["team_preview"])
    if applicable != expected:
        raise SchemaError(
            f"{what}: derivation_applicable={applicable} contradicts the section 5.1 rule "
            f"(not book_absent and not team_preview) = {expected}"
        )

    if not applicable:
        if row["is_degraded"] is not None:
            raise SchemaError(
                f"{what}: gate false requires is_degraded=None (not asked is not "
                f"not degraded), got {row['is_degraded']!r}"
            )
        if row["outcome"] != "not_applicable":
            raise SchemaError(f"{what}: gate false requires outcome=not_applicable")
        if row["selection_stage"] is not None:
            raise SchemaError(
                f"{what}: gate false requires selection_stage=None (section 8 null rules)"
            )
        if row["state_build_failed"]:
            raise SchemaError(
                f"{what}: state_build_failed=True is impossible with the gate false -- the "
                f"build is only ATTEMPTED when a book exists and it is not team preview"
            )
    else:
        if not isinstance(row["is_degraded"], bool):
            raise SchemaError(f"{what}: gate true requires a bool is_degraded")
        if row["outcome"] == "not_applicable":
            raise SchemaError(f"{what}: outcome=not_applicable requires the gate to be false")
        crashed = row["agent_crash_type"] is not None
        if crashed and row["outcome"] != "crash":
            raise SchemaError(f"{what}: agent_crash_type set but outcome={row['outcome']!r}")
        if row["outcome"] == "crash" and not crashed:
            raise SchemaError(f"{what}: outcome=crash requires agent_crash_type")
        if (crashed or row["state_build_failed"]) and row["is_degraded"] is not True:
            raise SchemaError(
                f"{what}: crashed/state_build_failed dominate and force is_degraded=True"
            )

    _validate_stage_outcome_reason(row, what)


def _validate_stage_outcome_reason(row: dict, what: str) -> None:
    """The stage vocabulary, and the BIDIRECTIONAL stage/outcome/reason agreement.

    Without this, three contradictory rows validate: an invented stage; a fallback_reason on a
    completed heuristic decision; and outcome="fallback" on selection_stage="heuristic". Each is
    a row this module could only produce by being wrong, and each would read as evidence.

    Dominance is respected, not re-derived: a crash and a failed state build outrank the stage in
    both derivation functions, so the stage/outcome pairing is only asserted when neither applies.
    """
    stage = row["selection_stage"]
    reason = row["fallback_reason"]
    if not row["derivation_applicable"]:
        # The gate-false branch already forced stage to None; a reason cannot survive it either.
        if reason is not None:
            raise SchemaError(f"{what}: gate false requires fallback_reason=None, got {reason!r}")
        return

    crashed = row["agent_crash_type"] is not None
    if stage is None:
        # Legitimate in exactly one case: the chooser raised BEFORE _mark_selection ran, so the
        # sink was never written. Any other absent stage is a row we could not have produced.
        if not crashed:
            raise SchemaError(
                f"{what}: selection_stage=None with the gate true and no crash -- "
                f"choose_with_fallback marks a stage on every return path"
            )
    elif stage not in LIVE_STAGES:
        raise SchemaError(f"{what}: selection_stage={stage!r} not in {sorted(LIVE_STAGES)}")

    if reason is not None:
        if stage is None:
            raise SchemaError(
                f"{what}: fallback_reason without a selection_stage -- _mark_selection always "
                f"writes both together"
            )
        allowed = STAGE_ALLOWED_REASONS.get(stage, frozenset())
        if reason not in allowed:
            raise SchemaError(
                f"{what}: fallback_reason={reason!r} is not permitted on "
                f"selection_stage={stage!r}; allowed: {sorted(allowed) or 'none'}"
            )
    elif stage in STAGES_REQUIRING_A_REASON:
        raise SchemaError(
            f"{what}: selection_stage={stage!r} is unreachable without a fallback_reason -- "
            f"see STAGES_REQUIRING_A_REASON"
        )
    elif stage == "deterministic_default_pair" and not row["state_build_failed"]:
        # This stage has exactly two routes, and the reason distinguishes them:
        #   max_damage_choice raised  -> fallback_reason=max_damage_error, state was built
        #   state is None             -> fallback_reason stays None
        # With the gate true, state is None can ONLY mean the build was attempted and failed
        # (handle_battle_message enters the try solely when a book exists and it is not team
        # preview), so a reason-less row here without state_build_failed describes a path that
        # does not exist.
        raise SchemaError(
            f"{what}: selection_stage=deterministic_default_pair with fallback_reason=None is "
            f"only reachable on the state-is-None path, which with the gate true requires "
            f"state_build_failed=True; the max_damage_error route sets a reason"
        )

    # Outcome agreement, in dominance order -- the same order both derivations use.
    outcome = row["outcome"]
    if crashed:
        # outcome == "crash" is already enforced above, and a crash dominates the stage.
        _require_is_degraded_matches_the_derivation(row, what, crashed=crashed, stage=stage)
        return
    if row["state_build_failed"]:
        if outcome != "degraded_state":
            raise SchemaError(
                f"{what}: state_build_failed=True forces outcome=degraded_state, got "
                f"{outcome!r}"
            )
        _require_is_degraded_matches_the_derivation(row, what, crashed=crashed, stage=stage)
        return
    if stage == LIVE_OK_STAGE:
        if outcome != "ok":
            raise SchemaError(
                f"{what}: selection_stage={LIVE_OK_STAGE!r} on a clean decision means "
                f"outcome=ok, got {outcome!r}"
            )
    elif stage in LIVE_FALLBACK_STAGES:
        if outcome != "fallback":
            raise SchemaError(
                f"{what}: selection_stage={stage!r} is a fallback stage, so outcome must be "
                f"fallback, got {outcome!r}"
            )
    if outcome == "ok" and stage != LIVE_OK_STAGE:
        raise SchemaError(f"{what}: outcome=ok requires selection_stage={LIVE_OK_STAGE!r}")
    if outcome == "fallback" and stage not in LIVE_FALLBACK_STAGES:
        raise SchemaError(
            f"{what}: outcome=fallback requires a fallback stage, got {stage!r}")
    if outcome == "degraded_state":
        raise SchemaError(
            f"{what}: outcome=degraded_state requires state_build_failed=True")

    _require_is_degraded_matches_the_derivation(row, what, crashed=crashed, stage=stage)


def _require_is_degraded_matches_the_derivation(
    row: dict, what: str, *, crashed: bool, stage: str | None,
) -> None:
    """is_degraded must BE the derivation's answer, not merely a plausible boolean.

    Nothing above pins it: with the gate true the field only had to be a bool, so a fallback
    stage could carry is_degraded=False and a clean heuristic decision could carry True -- the
    two rows a reader would most want to trust. Recomputing is exact and cannot drift, because it
    calls the same function record_decision calls rather than restating its rule.

    Honest limit: this cannot catch a bug INSIDE is_degraded_decision. It catches a row whose
    is_degraded disagrees with it, which is what a hand-built, mutated or future-diverged row is.
    """
    expected = is_degraded_decision(
        crashed=crashed, state_degraded=row["state_build_failed"], selection_stage=stage)
    if row["is_degraded"] is not expected:
        raise SchemaError(
            f"{what}: is_degraded={row['is_degraded']!r} contradicts is_degraded_decision("
            f"crashed={crashed}, state_degraded={row['state_build_failed']}, "
            f"selection_stage={stage!r}) = {expected}"
        )


def validate_event_row(row: dict) -> None:
    what = "event row"
    _require_shape(row, EVENT_FIELDS, what)

    if row["event_type"] not in EVENT_TYPES:
        raise SchemaError(f"{what}: event_type={row['event_type']!r} not in {EVENT_TYPES}")
    if row["attribution"] not in ATTRIBUTIONS:
        raise SchemaError(f"{what}: attribution={row['attribution']!r} not in {ATTRIBUTIONS}")
    if not isinstance(row["payload"], str):
        raise SchemaError(f"{what}: payload must be a str, got {row['payload']!r}")
    _require_count(row, "active_battle_count", what)
    _require_str_or_none(row, "room_id", what)

    attribution = row["attribution"]
    if attribution == "unattributed":
        if row["room_id"] is not None:
            raise SchemaError(
                f"{what}: attribution=unattributed requires room_id=None -- charging an "
                f"unattributable event to a room would manufacture degradation (C8)"
            )
    elif row["room_id"] is None:
        raise SchemaError(f"{what}: attribution={attribution!r} requires a room_id")

    if row["event_type"] == "server_error" and attribution != "room":
        raise SchemaError(
            f"{what}: server_error is room-scoped by construction; attribution={attribution!r}"
        )
    if row["event_type"] == "invalid_choice_pm":
        if attribution == "room":
            raise SchemaError(
                f"{what}: the invalid-choice PM carries no room; room attribution is never "
                f"available for it (section 7)"
            )
        if attribution == "inferred" and row["active_battle_count"] != 1:
            raise SchemaError(
                f"{what}: inferred is permitted only when exactly one battle is active, "
                f"got active_battle_count={row['active_battle_count']}"
            )


def validate_battle_row(row: dict) -> None:
    what = "battle row"
    _require_shape(row, BATTLE_FIELDS, what)

    if not isinstance(row["room_id"], str) or not row["room_id"]:
        raise SchemaError(f"{what}: room_id must be a non-empty str, got {row['room_id']!r}")
    for key in (
        "decisions_total", "decisions_not_applicable", "degraded_decisions",
        "state_build_failures", "agent_crashes", "fallback_decisions",
        "own_invalid_choices", "server_errors", "write_errors",
    ):
        _require_count(row, key, what)
    if row["end_reason"] not in END_REASONS:
        raise SchemaError(f"{what}: end_reason={row['end_reason']!r} not in {END_REASONS}")

    total = row["decisions_total"]
    not_applicable = row["decisions_not_applicable"]
    degraded = row["degraded_decisions"]
    if not_applicable > total:
        raise SchemaError(f"{what}: decisions_not_applicable {not_applicable} > total {total}")
    if not_applicable + degraded > total:
        raise SchemaError(
            f"{what}: not_applicable {not_applicable} + degraded {degraded} > total {total} -- "
            f"a not_applicable row has is_degraded=None and is counted by neither the other"
        )
    # state_build_failed and a fallback stage each FORCE is_degraded=True, so both are
    # subsets of degraded_decisions. agent_crashes deliberately is NOT: a crash on the
    # book-absent path (smoke) has the gate false and therefore is_degraded=None.
    if row["state_build_failures"] > degraded:
        raise SchemaError(
            f"{what}: state_build_failures {row['state_build_failures']} > degraded {degraded}"
        )
    if row["fallback_decisions"] > degraded:
        raise SchemaError(
            f"{what}: fallback_decisions {row['fallback_decisions']} > degraded {degraded}"
        )


def validate_completion_row(row: dict, *, expected_run_id: str | None = None) -> None:
    """Validate the single completion object (section 8.0).

    expected_run_id is optional and proves only that the caller and the row agree. It does NOT
    establish the cross-file identity -- a validator handed one object cannot see the other three
    files, and the recorder's own run_id shares a source with this row. That property is the
    ARTIFACT INVARIANT and has its own integration test (Task 12).
    """
    what = "completion row"
    _require_shape(row, COMPLETION_FIELDS, what)

    _require_count(row, "battles_finished", what)
    for key in ("write_errors_total", "schema_errors_total", "recorder_errors_total"):
        _require_count(row, key, what)

    rooms = row["unterminated_rooms"]
    if not isinstance(rooms, list):
        raise SchemaError(f"{what}: unterminated_rooms must be a list, got {rooms!r}")
    for room in rooms:
        if not isinstance(room, str) or not room:
            raise SchemaError(f"{what}: unterminated_rooms holds {room!r}")
    if len(set(rooms)) != len(rooms):
        raise SchemaError(f"{what}: unterminated_rooms has duplicates: {rooms!r}")

    if row["preflight_ok"] is not True:
        raise SchemaError(
            f"{what}: preflight_ok must be True -- this file can only be written after preflight "
            f"succeeded (section 10.1), so {row['preflight_ok']!r} is a defect, not a state"
        )

    if expected_run_id is not None and row["run_id"] != expected_run_id:
        raise SchemaError(
            f"{what}: run_id={row['run_id']!r} does not match expected_run_id="
            f"{expected_run_id!r}"
        )

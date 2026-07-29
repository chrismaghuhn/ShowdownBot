"""live-degradation-v1: own-seat degradation evidence for the live runner.

Implements docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md.
Deliberately independent of eval/decision_profile's CLOSED schema (section 8, C6): this module
imports that module's two derivation functions and its stage/reason vocabulary, and nothing
else. It never writes a decision-profile row.

Every SchemaError message opens with a STABLE RULE IDENTIFIER in brackets, e.g.
``decision row [stage_vocab]: ...``. Tests match on the identifier alone. The prose after it is
free to improve without breaking a single test -- which is the point: a test suite that pins
sentence wording turns every clarification into a contract breach.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from showdown_bot.eval.decision_profile import (
    LIVE_FALLBACK_STAGES,
    LIVE_OK_STAGE,
    STAGE_ALLOWED_REASONS,
    is_degraded_decision,
)

logger = logging.getLogger(__name__)

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


def _fail(what: str, rule: str, detail: str) -> None:
    """Raise with a stable rule identifier in front of free-form prose.

    The identifier is the contract the tests hold us to; the prose is for the human reading the
    log and may be reworded freely. Keeping those two jobs in one string but separately
    addressable is what lets a message improve without breaking a mutation test.
    """
    raise SchemaError(f"{what} [{rule}]: {detail}")


def _require_shape(row: dict, fields: tuple[str, ...], what: str) -> None:
    """Field set AND ORDER. Order matters because the JSONL is read positionally by eye and
    diffed line-by-line; a reordered row is a different artifact even if it parses the same."""
    actual = tuple(row)
    if actual != fields:
        missing = [f for f in fields if f not in row]
        extra = [f for f in actual if f not in fields]
        _fail(what, "shape",
              f"field set/order mismatch; missing={missing} extra={extra} actual={list(actual)}")
    if row["schema_version"] != SCHEMA_VERSION:
        _fail(what, "schema_version",
              f"expected {SCHEMA_VERSION!r}, got {row['schema_version']!r}")
    if not isinstance(row["run_id"], str) or not row["run_id"]:
        _fail(what, "run_id", f"must be a non-empty str, got {row['run_id']!r}")


def _is_int(value: object) -> bool:
    """bool is a subclass of int; True must never pass as a counter or a sequence number."""
    return isinstance(value, int) and not isinstance(value, bool)


def _require_bool(row: dict, key: str, what: str) -> None:
    if not isinstance(row[key], bool):
        _fail(what, "bool", f"{key} must be bool, got {row[key]!r}")


def _require_str_or_none(row: dict, key: str, what: str) -> None:
    value = row[key]
    if value is None:
        return
    if not isinstance(value, str) or not value:
        _fail(what, "str_or_none",
              f"{key} must be a non-empty str or None -- no sentinel values, no empty strings "
              f"(section 8 null rules); got {value!r}")


def _require_count(row: dict, key: str, what: str) -> None:
    if not _is_int(row[key]) or row[key] < 0:
        _fail(what, "count", f"{key} must be a non-negative int, got {row[key]!r}")


def validate_decision_row(row: dict) -> None:
    what = "decision row"
    _require_shape(row, DECISION_FIELDS, what)

    if not isinstance(row["room_id"], str) or not row["room_id"]:
        _fail(what, "room_id", f"must be a non-empty str, got {row['room_id']!r}")
    _require_count(row, "decision_seq", what)
    if row["rqid"] is not None and not _is_int(row["rqid"]):
        _fail(what, "int_or_none", f"rqid must be int or None, got {row['rqid']!r}")
    for key in ("book_absent", "team_preview", "state_build_failed", "derivation_applicable"):
        _require_bool(row, key, what)
    for key in ("selection_stage", "fallback_reason", "agent_crash_type"):
        _require_str_or_none(row, key, what)
    if row["is_degraded"] is not None and not isinstance(row["is_degraded"], bool):
        _fail(what, "is_degraded_type",
              f"is_degraded must be bool or None, got {row['is_degraded']!r}")
    if row["outcome"] not in OUTCOMES:
        _fail(what, "outcome_vocab", f"outcome={row['outcome']!r} not in {OUTCOMES}")

    applicable = row["derivation_applicable"]
    expected = (not row["book_absent"]) and (not row["team_preview"])
    if applicable != expected:
        _fail(what, "gate_rule",
              f"derivation_applicable={applicable} contradicts the section 5.1 rule "
              f"(not book_absent and not team_preview) = {expected}")

    if not applicable:
        if row["is_degraded"] is not None:
            _fail(what, "gate_false_is_degraded",
                  f"the gate is false, so is_degraded must be None -- 'not asked' is not "
                  f"'not degraded'; got {row['is_degraded']!r}")
        if row["outcome"] != "not_applicable":
            _fail(what, "gate_false_outcome",
                  f"the gate is false, so outcome must be 'not_applicable'; "
                  f"got {row['outcome']!r}")
        if row["selection_stage"] is not None:
            _fail(what, "gate_false_stage",
                  f"the gate is false, so selection_stage must be None (section 8 null rules); "
                  f"got {row['selection_stage']!r}")
        if row["state_build_failed"]:
            _fail(what, "gate_false_state_build",
                  "state_build_failed=True is impossible with the gate false -- the build is "
                  "only ATTEMPTED when a book exists and it is not team preview")
    else:
        if not isinstance(row["is_degraded"], bool):
            _fail(what, "gate_true_is_degraded_type",
                  f"the gate is true, so is_degraded must be a bool; got {row['is_degraded']!r}")
        if row["outcome"] == "not_applicable":
            _fail(what, "gate_true_outcome",
                  "outcome='not_applicable' requires the gate to be false")
        crashed = row["agent_crash_type"] is not None
        if crashed and row["outcome"] != "crash":
            _fail(what, "crash_outcome",
                  f"agent_crash_type={row['agent_crash_type']!r} is set, so outcome must be "
                  f"'crash'; got {row['outcome']!r}")
        if row["outcome"] == "crash" and not crashed:
            _fail(what, "crash_requires_type", "outcome='crash' requires an agent_crash_type")
        if (crashed or row["state_build_failed"]) and row["is_degraded"] is not True:
            _fail(what, "dominance_is_degraded",
                  "a crash and a failed state build dominate the stage in both derivations, "
                  "and each forces is_degraded=True")

    _validate_stage_outcome_reason(row, what)


def _validate_stage_outcome_reason(row: dict, what: str) -> None:
    """The stage vocabulary, and the BIDIRECTIONAL stage/outcome/reason agreement.

    Without this, three contradictory rows validate: an invented stage; a fallback_reason on a
    completed heuristic decision; and outcome='fallback' on selection_stage='heuristic'. Each is
    a row this module could only produce by being wrong, and each would read as evidence.

    Dominance is respected, not re-derived: a crash and a failed state build outrank the stage in
    both derivation functions, so the stage/outcome pairing is only asserted when neither applies.
    """
    stage = row["selection_stage"]
    reason = row["fallback_reason"]
    if not row["derivation_applicable"]:
        # The gate-false branch already forced stage to None; a reason cannot survive it either.
        if reason is not None:
            _fail(what, "gate_false_reason",
                  f"the gate is false, so fallback_reason must be None; got {reason!r}")
        return

    crashed = row["agent_crash_type"] is not None
    if stage is None:
        # Legitimate in exactly one case: the chooser raised BEFORE _mark_selection ran, so the
        # sink was never written. Any other absent stage is a row we could not have produced.
        if not crashed:
            _fail(what, "stage_absent",
                  "selection_stage=None with the gate true and no crash -- choose_with_fallback "
                  "marks a stage on every return path, so this row cannot have been produced")
    elif stage not in LIVE_STAGES:
        _fail(what, "stage_vocab",
              f"selection_stage={stage!r} not in {sorted(LIVE_STAGES)}")

    if reason is not None:
        if stage is None:
            _fail(what, "reason_without_stage",
                  f"fallback_reason={reason!r} without a selection_stage -- _mark_selection "
                  f"always writes both together")
        allowed = STAGE_ALLOWED_REASONS.get(stage, frozenset())
        if reason not in allowed:
            _fail(what, "reason_not_allowed",
                  f"fallback_reason={reason!r} is not permitted on selection_stage={stage!r}; "
                  f"allowed: {sorted(allowed) or 'none'}")
    elif stage in STAGES_REQUIRING_A_REASON:
        _fail(what, "reason_required",
              f"selection_stage={stage!r} is unreachable without a fallback_reason -- see "
              f"STAGES_REQUIRING_A_REASON for why the control flow guarantees one")
    elif stage == "deterministic_default_pair" and not row["state_build_failed"]:
        # This stage has exactly two routes, and the reason distinguishes them:
        #   max_damage_choice raised  -> fallback_reason='max_damage_error', state was built
        #   state is None             -> fallback_reason stays None
        # With the gate true, `state is None` can ONLY mean the build was attempted and failed
        # (handle_battle_message enters the try solely when a book exists and it is not team
        # preview), so a reason-less row here without state_build_failed describes a path that
        # does not exist.
        _fail(what, "default_pair_route",
              "selection_stage='deterministic_default_pair' with fallback_reason=None is only "
              "reachable on the state-is-None path, which with the gate true requires "
              "state_build_failed=True; the max_damage_error route sets a reason")

    # Outcome agreement, in dominance order -- the same order both derivations use.
    outcome = row["outcome"]
    if crashed:
        # outcome == 'crash' is already enforced above, and a crash dominates the stage.
        _require_is_degraded_matches_the_derivation(row, what, crashed=crashed, stage=stage)
        return
    if row["state_build_failed"]:
        if outcome != "degraded_state":
            _fail(what, "state_outcome",
                  f"state_build_failed=True forces outcome='degraded_state'; got {outcome!r}")
        _require_is_degraded_matches_the_derivation(row, what, crashed=crashed, stage=stage)
        return
    if stage == LIVE_OK_STAGE:
        if outcome != "ok":
            _fail(what, "ok_outcome",
                  f"selection_stage={LIVE_OK_STAGE!r} on a clean decision means outcome='ok'; "
                  f"got {outcome!r}")
    elif stage in LIVE_FALLBACK_STAGES:
        if outcome != "fallback":
            _fail(what, "fallback_outcome",
                  f"selection_stage={stage!r} is a fallback stage, so outcome must be "
                  f"'fallback'; got {outcome!r}")
    if outcome == "ok" and stage != LIVE_OK_STAGE:
        _fail(what, "outcome_stage_ok",
              f"outcome='ok' requires selection_stage={LIVE_OK_STAGE!r}; got {stage!r}")
    if outcome == "fallback" and stage not in LIVE_FALLBACK_STAGES:
        _fail(what, "outcome_stage_fallback",
              f"outcome='fallback' requires a fallback stage; got {stage!r}")
    if outcome == "degraded_state":
        _fail(what, "outcome_degraded_state",
              "outcome='degraded_state' requires state_build_failed=True")

    _require_is_degraded_matches_the_derivation(row, what, crashed=crashed, stage=stage)


def _require_is_degraded_matches_the_derivation(
    row: dict, what: str, *, crashed: bool, stage: str | None,
) -> None:
    """`is_degraded` must BE the derivation's answer, not merely a plausible boolean.

    Nothing above pins it: with the gate true the field only had to be a bool, so a fallback
    stage could carry is_degraded=False and a clean heuristic decision could carry True -- the
    two rows a reader would most want to trust. Recomputing is exact and cannot drift, because it
    calls the same function `record_decision` calls rather than restating its rule.

    Honest limit: this cannot catch a bug INSIDE is_degraded_decision. It catches a row whose
    is_degraded disagrees with it, which is what a hand-built, mutated or future-diverged row is.
    """
    expected = is_degraded_decision(
        crashed=crashed, state_degraded=row["state_build_failed"], selection_stage=stage)
    if row["is_degraded"] is not expected:
        _fail(what, "is_degraded_derivation",
              f"is_degraded={row['is_degraded']!r} contradicts is_degraded_decision("
              f"crashed={crashed}, state_degraded={row['state_build_failed']}, "
              f"selection_stage={stage!r}) = {expected}")


def validate_event_row(row: dict) -> None:
    what = "event row"
    _require_shape(row, EVENT_FIELDS, what)

    if row["event_type"] not in EVENT_TYPES:
        _fail(what, "event_type_vocab",
              f"event_type={row['event_type']!r} not in {EVENT_TYPES}")
    if row["attribution"] not in ATTRIBUTIONS:
        _fail(what, "attribution_vocab",
              f"attribution={row['attribution']!r} not in {ATTRIBUTIONS}")
    if not isinstance(row["payload"], str):
        _fail(what, "payload_type", f"payload must be a str, got {row['payload']!r}")
    _require_count(row, "active_battle_count", what)
    _require_str_or_none(row, "room_id", what)

    attribution = row["attribution"]
    if attribution == "unattributed":
        if row["room_id"] is not None:
            _fail(what, "unattributed_room",
                  f"attribution='unattributed' requires room_id=None -- charging an "
                  f"unattributable event to a room would manufacture degradation that was never "
                  f"observed on that battle (C8); got {row['room_id']!r}")
    elif row["room_id"] is None:
        _fail(what, "attribution_requires_room",
              f"attribution={attribution!r} requires a room_id")

    if row["event_type"] == "server_error" and attribution != "room":
        _fail(what, "server_error_room_scoped",
              f"|error| arrives inside a battle room and is room-scoped by construction; "
              f"attribution={attribution!r}")
    if row["event_type"] == "invalid_choice_pm":
        if attribution == "room":
            _fail(what, "pm_never_room",
                  "the invalid-choice PM carries no room, so 'room' attribution is never "
                  "available for it (section 7)")
        if attribution == "inferred" and row["active_battle_count"] != 1:
            _fail(what, "pm_inferred_count",
                  f"'inferred' is permitted only when exactly one battle is active; got "
                  f"active_battle_count={row['active_battle_count']}")


def validate_battle_row(row: dict) -> None:
    what = "battle row"
    _require_shape(row, BATTLE_FIELDS, what)

    if not isinstance(row["room_id"], str) or not row["room_id"]:
        _fail(what, "room_id", f"must be a non-empty str, got {row['room_id']!r}")
    for key in (
        "decisions_total", "decisions_not_applicable", "degraded_decisions",
        "state_build_failures", "agent_crashes", "fallback_decisions",
        "own_invalid_choices", "server_errors", "write_errors",
    ):
        _require_count(row, key, what)
    if row["end_reason"] not in END_REASONS:
        _fail(what, "end_reason_vocab",
              f"end_reason={row['end_reason']!r} not in {END_REASONS}")

    total = row["decisions_total"]
    not_applicable = row["decisions_not_applicable"]
    degraded = row["degraded_decisions"]
    if not_applicable > total:
        _fail(what, "not_applicable_gt_total",
              f"decisions_not_applicable {not_applicable} > decisions_total {total}")
    if not_applicable + degraded > total:
        _fail(what, "na_plus_degraded_gt_total",
              f"not_applicable {not_applicable} + degraded {degraded} > total {total} -- a "
              f"not_applicable row has is_degraded=None and is counted by neither the other")
    # state_build_failed and a fallback stage each FORCE is_degraded=True, so both are
    # subsets of degraded_decisions. agent_crashes deliberately is NOT: a crash on the
    # book-absent path (smoke) has the gate false and therefore is_degraded=None.
    if row["state_build_failures"] > degraded:
        _fail(what, "state_build_gt_degraded",
              f"state_build_failures {row['state_build_failures']} > degraded_decisions "
              f"{degraded}, but a failed state build forces is_degraded=True")
    if row["fallback_decisions"] > degraded:
        _fail(what, "fallback_gt_degraded",
              f"fallback_decisions {row['fallback_decisions']} > degraded_decisions {degraded}, "
              f"but a fallback stage forces is_degraded=True")


def validate_completion_row(row: dict, *, expected_run_id: str | None = None) -> None:
    """Validate the single completion object (section 8.0).

    `expected_run_id` is optional and proves only that the caller and the row agree. It does NOT
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
        _fail(what, "unterminated_type",
              f"unterminated_rooms must be a list, got {rooms!r}")
    for room in rooms:
        if not isinstance(room, str) or not room:
            _fail(what, "unterminated_item",
                  f"unterminated_rooms must hold non-empty strings, found {room!r}")
    if len(set(rooms)) != len(rooms):
        _fail(what, "unterminated_duplicates",
              f"unterminated_rooms has duplicates: {rooms!r}")

    if row["preflight_ok"] is not True:
        _fail(what, "preflight_ok",
              f"preflight_ok must be True -- this file can only be written after preflight "
              f"succeeded (section 10.1), so {row['preflight_ok']!r} is a defect, not a state")

    if expected_run_id is not None and row["run_id"] != expected_run_id:
        _fail(what, "expected_run_id",
              f"run_id={row['run_id']!r} does not match expected_run_id={expected_run_id!r}")


DEFAULT_PARENT = Path("logs") / "live-degradation"
DIR_ENV = "SHOWDOWN_LIVE_DEGRADATION_DIR"


class PreflightError(RuntimeError):
    """The sink could not be established. Raised BEFORE connect/search (section 10.1)."""


def _preflight_fail(rule: str, detail: str, cause: BaseException | None = None) -> None:
    """Same identifier-then-prose contract as SchemaError -- tests match the identifier."""
    raise PreflightError(f"preflight [{rule}]: {detail}") from cause


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def resolve_parent(explicit: Path | None = None) -> Path:
    """An explicit parent wins; then the override; then the default.

    An EMPTY override is treated as unset -- an empty string would otherwise resolve to the
    current directory, which is a surprising place to drop evidence.

    This is the module's ONLY environment read, deliberately: a second one could quietly gate
    whether recording happens, and the whole ruling is that nothing may.
    """
    if explicit is not None:
        return Path(explicit)
    override = os.environ.get(DIR_ENV)
    return Path(override) if override else DEFAULT_PARENT


class LiveDegradationRecorder:
    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.write_errors_total = 0
        self.schema_errors_total = 0
        self.recorder_errors_total = 0
        self.battles_finished = 0
        self.unterminated_rooms: list[str] = []
        self._decisions: dict[str, list[dict]] = {}
        self._events: list[dict] = []
        self._room_write_errors: dict[str, int] = {}
        self._seq: dict[str, int] = {}

    @classmethod
    def preflight(cls, *, parent: Path | None = None) -> LiveDegradationRecorder:
        """Create the run directory exclusively and prove the writer works.

        Called BEFORE _connect_and_login and before any /search or challenge (section 10.1).
        This is the ONE place a recording failure may stop the run: nothing has been played, so
        aborting costs nothing, whereas an unwritable sink discovered after 50 ladder games costs
        all 50 games' evidence.

        Exactly two things are binding when the probe fails: the live run does not start, and
        existing evidence is never adopted or overwritten. The second is carried by the exclusive
        create, which refuses a directory that is already there.

        What happens to the directory this preflight just made is NOT part of the contract. This
        implementation leaves it; removing it would be equally allowed, provided the cleanup only
        ever touches the directory this same preflight exclusively created -- deleting anything
        else could destroy a concurrent run's claim. No test may require either behaviour without
        a decision record saying so.
        """
        base = resolve_parent(parent)
        run_id = _new_run_id()
        run_dir = base / run_id
        try:
            os.makedirs(run_dir, exist_ok=False)
        except FileExistsError as exc:
            _preflight_fail("dir_exists", f"run directory already exists: {run_dir}", exc)
        except OSError as exc:
            # Windows and POSIX raise different subclasses when a parent is a file or is
            # unwritable; catching OSError broadly is the portable form.
            _preflight_fail("dir_create", f"cannot create run directory {run_dir}: {exc}", exc)
        probe = run_dir / ".probe"
        try:
            with open(probe, "x", encoding="utf-8") as fh:
                fh.write("probe")
                fh.flush()
                os.fsync(fh.fileno())
            os.remove(probe)
        except OSError as exc:
            _preflight_fail("probe", f"writer probe failed in {run_dir}: {exc}", exc)
        return cls(run_dir, run_id)

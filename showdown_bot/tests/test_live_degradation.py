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
    ("missing_field", _without(VALID_DECISION, "rqid"), "shape"),
    ("extra_field", _mutate(VALID_DECISION, hero_wins=1), "shape"),
    ("wrong_order", _reordered(VALID_DECISION), "shape"),
    ("wrong_schema_version",
     _mutate(VALID_DECISION, schema_version="live-degradation-v2"), "schema_version"),
    ("empty_run_id", _mutate(VALID_DECISION, run_id=""), "run_id"),
    ("empty_room_id", _mutate(VALID_DECISION, room_id=""), "room_id"),
    ("seq_is_bool",
     _mutate(VALID_DECISION, decision_seq=True), "count"),
    ("seq_negative",
     _mutate(VALID_DECISION, decision_seq=-1), "count"),
    ("rqid_is_str", _mutate(VALID_DECISION, rqid="7"), "int_or_none"),
    ("book_absent_is_int", _mutate(VALID_DECISION, book_absent=1), "bool"),
    ("stage_empty_string",
     _mutate(VALID_DECISION, selection_stage=""), "str_or_none"),
    ("unknown_outcome", _mutate(VALID_DECISION, outcome="weird"), "outcome_vocab"),
    ("is_degraded_is_str",
     _mutate(VALID_DECISION, is_degraded="yes"), "is_degraded_type"),
    ("gate_disagrees_with_book_absent",
     _mutate(VALID_DECISION, book_absent=True), "gate_rule"),
    ("gate_disagrees_with_team_preview",
     _mutate(VALID_DECISION, team_preview=True), "gate_rule"),
    ("not_applicable_outcome_while_gate_true",
     _mutate(VALID_DECISION, outcome="not_applicable"),
     "gate_true_outcome"),
    ("gate_false_but_is_degraded_is_false",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             selection_stage=None, outcome="not_applicable", is_degraded=False),
     "gate_false_is_degraded"),
    ("gate_false_but_stage_set",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             outcome="not_applicable", is_degraded=None),
     "gate_false_stage"),
    ("gate_false_but_reason_set",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             selection_stage=None, fallback_reason="heuristic_timeout",
             outcome="not_applicable", is_degraded=None),
     "gate_false_reason"),
    ("state_build_failed_while_gate_false",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             state_build_failed=True, selection_stage=None, is_degraded=None,
             outcome="not_applicable"),
     "gate_false_state_build"),
    ("gate_true_but_is_degraded_null",
     _mutate(VALID_DECISION, is_degraded=None), "gate_true_is_degraded_type"),
    ("crash_type_without_crash_outcome",
     _mutate(VALID_DECISION, agent_crash_type="ValueError"),
     "crash_outcome"),
    ("crash_outcome_without_crash_type",
     _mutate(VALID_DECISION, outcome="crash", is_degraded=True),
     "crash_requires_type"),
    ("state_build_failed_not_degraded",
     _mutate(VALID_DECISION, state_build_failed=True),
     "dominance_is_degraded"),
    ("invented_stage",
     _mutate(VALID_DECISION, selection_stage="invented"),
     "stage_vocab"),
    ("reason_on_a_completed_heuristic_decision",
     _mutate(VALID_DECISION, fallback_reason="heuristic_timeout"), "reason_not_allowed"),
    ("unknown_fallback_reason",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="made_up", is_degraded=True, outcome="fallback"),
     "reason_not_allowed"),
    ("reason_not_allowed_for_its_stage",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="default_pair_error", is_degraded=True, outcome="fallback"),
     "reason_not_allowed"),
    ("fallback_outcome_on_the_heuristic_stage",
     _mutate(VALID_DECISION, outcome="fallback", is_degraded=True),
     "ok_outcome"),
    ("ok_outcome_on_a_fallback_stage",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="heuristic_timeout", is_degraded=True, outcome="ok"),
     "fallback_outcome"),
    ("degraded_state_outcome_without_a_failed_build",
     _mutate(VALID_DECISION, selection_stage="deterministic_default_pair",
             fallback_reason="max_damage_error", is_degraded=True, outcome="degraded_state"),
     "fallback_outcome"),
    ("stage_absent_without_a_crash",
     _mutate(VALID_DECISION, selection_stage=None, is_degraded=True, outcome="fallback"),
     "stage_absent"),
    ("reason_missing_on_max_damage_fallback",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback", fallback_reason=None,
             is_degraded=True, outcome="fallback"),
     "reason_required"),
    ("reason_missing_on_server_default",
     _mutate(VALID_DECISION, selection_stage="server_default", fallback_reason=None,
             is_degraded=True, outcome="fallback"),
     "reason_required"),
    ("reason_less_default_pair_without_a_failed_state_build",
     _mutate(VALID_DECISION, selection_stage="deterministic_default_pair",
             fallback_reason=None, state_build_failed=False, is_degraded=True,
             outcome="fallback"),
     "default_pair_route"),
    ("is_degraded_true_on_a_clean_heuristic_decision",
     _mutate(VALID_DECISION, is_degraded=True), "is_degraded_derivation"),
    ("is_degraded_false_on_a_fallback_stage",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="heuristic_timeout", is_degraded=False, outcome="fallback"),
     "is_degraded_derivation"),
]


@pytest.mark.parametrize("label,row,rule", DECISION_MUTATIONS,
                         ids=[m[0] for m in DECISION_MUTATIONS])
def test_decision_mutation_is_rejected(label, row, rule):
    """Matching the RULE IDENTIFIER, not the sentence, is what stops a mutation passing for the
    wrong reason -- a row mutated to test rule A could be rejected by unrelated rule B and stay
    green while rule A was missing -- without turning every wording improvement into a failure."""
    with pytest.raises(SchemaError, match=re.escape(f"[{rule}]")):
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


EVENT_MUTATIONS = [
    ("missing_field", _without(VALID_EVENT, "payload"), "shape"),
    ("extra_field", _mutate(VALID_EVENT, villain_errors=1), "shape"),
    ("unknown_event_type",
     _mutate(VALID_EVENT, event_type="disconnect"), "event_type_vocab"),
    ("unknown_attribution",
     _mutate(VALID_EVENT, attribution="guess"), "attribution_vocab"),
    ("payload_is_none", _mutate(VALID_EVENT, payload=None), "payload_type"),
    ("count_is_negative", _mutate(VALID_EVENT, active_battle_count=-1), "count"),
    ("count_is_bool", _mutate(VALID_EVENT, active_battle_count=True), "count"),
    ("room_attribution_without_room",
     _mutate(VALID_EVENT, room_id=None), "attribution_requires_room"),
    ("unattributed_with_a_room",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="unattributed"),
     "unattributed_room"),
    ("inferred_without_a_room",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="inferred",
             room_id=None, active_battle_count=1),
     "attribution_requires_room"),
    ("inferred_with_two_active_battles",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="inferred",
             active_battle_count=2),
     "pm_inferred_count"),
    ("server_error_marked_inferred",
     _mutate(VALID_EVENT, attribution="inferred", active_battle_count=1),
     "server_error_room_scoped"),
    ("pm_marked_room",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="room"),
     "pm_never_room"),
]


@pytest.mark.parametrize("label,row,rule", EVENT_MUTATIONS,
                         ids=[m[0] for m in EVENT_MUTATIONS])
def test_event_mutation_is_rejected(label, row, rule):
    with pytest.raises(SchemaError, match=re.escape(f"[{rule}]")):
        validate_event_row(dict(row))


BATTLE_MUTATIONS = [
    ("missing_field", _without(VALID_BATTLE, "write_errors"), "shape"),
    ("extra_field", _mutate(VALID_BATTLE, hero_invalid_total=0), "shape"),
    ("unknown_end_reason", _mutate(VALID_BATTLE, end_reason="aborted"), "end_reason_vocab"),
    ("negative_counter", _mutate(VALID_BATTLE, server_errors=-1), "count"),
    ("counter_is_bool", _mutate(VALID_BATTLE, agent_crashes=True), "count"),
    ("counter_is_float", _mutate(VALID_BATTLE, decisions_total=10.0), "count"),
    ("not_applicable_exceeds_total",
     _mutate(VALID_BATTLE, decisions_not_applicable=11), "not_applicable_gt_total"),
    ("degraded_plus_not_applicable_exceeds_total",
     _mutate(VALID_BATTLE, decisions_not_applicable=9, degraded_decisions=2),
     "na_plus_degraded_gt_total"),
    ("state_build_failures_exceed_degraded",
     _mutate(VALID_BATTLE, state_build_failures=3), "state_build_gt_degraded"),
    ("fallback_exceeds_degraded",
     _mutate(VALID_BATTLE, fallback_decisions=3), "fallback_gt_degraded"),
]


@pytest.mark.parametrize("label,row,rule", BATTLE_MUTATIONS,
                         ids=[m[0] for m in BATTLE_MUTATIONS])
def test_battle_mutation_is_rejected(label, row, rule):
    with pytest.raises(SchemaError, match=re.escape(f"[{rule}]")):
        validate_battle_row(dict(row))


COMPLETION_MUTATIONS = [
    ("missing_field", _without(VALID_COMPLETION, "recorder_errors_total"), "shape"),
    ("extra_field", _mutate(VALID_COMPLETION, recording_ok=True), "shape"),
    ("wrong_schema_version",
     _mutate(VALID_COMPLETION, schema_version="live-degradation-v2"), "schema_version"),
    ("empty_run_id", _mutate(VALID_COMPLETION, run_id=""), "run_id"),
    ("battles_finished_is_bool", _mutate(VALID_COMPLETION, battles_finished=True), "count"),
    ("battles_finished_negative", _mutate(VALID_COMPLETION, battles_finished=-1), "count"),
    ("counter_is_bool", _mutate(VALID_COMPLETION, schema_errors_total=True), "count"),
    ("counter_negative", _mutate(VALID_COMPLETION, recorder_errors_total=-1), "count"),
    ("counter_is_str", _mutate(VALID_COMPLETION, write_errors_total="0"), "count"),
    ("unterminated_is_not_a_list",
     _mutate(VALID_COMPLETION, unterminated_rooms="r"), "unterminated_type"),
    ("unterminated_holds_a_non_string",
     _mutate(VALID_COMPLETION, unterminated_rooms=[1]), "unterminated_item"),
    ("unterminated_holds_an_empty_string",
     _mutate(VALID_COMPLETION, unterminated_rooms=[""]), "unterminated_item"),
    ("unterminated_has_duplicates",
     _mutate(VALID_COMPLETION, unterminated_rooms=["a", "a"]), "unterminated_duplicates"),
    ("preflight_ok_false", _mutate(VALID_COMPLETION, preflight_ok=False), "preflight_ok"),
    ("preflight_ok_is_int", _mutate(VALID_COMPLETION, preflight_ok=1), "preflight_ok"),
]


@pytest.mark.parametrize("label,row,rule", COMPLETION_MUTATIONS,
                         ids=[m[0] for m in COMPLETION_MUTATIONS])
def test_completion_mutation_is_rejected(label, row, rule):
    with pytest.raises(SchemaError, match=re.escape(f"[{rule}]")):
        validate_completion_row(dict(row))


def test_completion_run_id_is_checked_only_when_an_expectation_is_supplied():
    """The validator sees ONE object. It cannot reach the other three files, and passing the
    recorder's own run_id proves only self-consistency -- section 8.0 says so explicitly. The
    cross-file property is the artifact invariant, tested separately in Task 12."""
    validate_completion_row(dict(VALID_COMPLETION))
    validate_completion_row(dict(VALID_COMPLETION),
                            expected_run_id="20260729T101112Z-a1b2c3")
    with pytest.raises(SchemaError, match=re.escape("[expected_run_id]")):
        validate_completion_row(dict(VALID_COMPLETION), expected_run_id="someone-elses-run")


# --- the generic _require_shape rules, on EVERY grain --------------------------
#
# The per-grain lists above test each grain's own semantics. The four rules _require_shape
# enforces -- field set, field ORDER, schema_version, run_id -- belong to every grain equally,
# and testing them on decisions alone would leave three quarters of that claim unproven. This is
# what "closed contract" has to mean: the same rule, checked on every grain it is asserted for.
# The overlap with the per-grain lists is deliberate; duplicated coverage in tests is cheap, and
# removing it would make each list depend on this grid to be honest.

GRAINS = ("decision", "event", "battle", "completion")

GENERIC_RULES = {
    "missing_field": "shape",
    "extra_field": "shape",
    "wrong_order": "shape",
    "wrong_schema_version": "schema_version",
    "empty_run_id": "run_id",
}


def _grain(name: str):
    """(validator, valid_row) for one grain, resolved at call time."""
    return {
        "decision": (validate_decision_row, VALID_DECISION),
        "event": (validate_event_row, VALID_EVENT),
        "battle": (validate_battle_row, VALID_BATTLE),
        "completion": (validate_completion_row, VALID_COMPLETION),
    }[name]


@pytest.mark.parametrize("grain", GRAINS)
@pytest.mark.parametrize("mutation", sorted(GENERIC_RULES))
def test_every_grain_enforces_the_generic_shape_rules(grain, mutation):
    validator, valid = _grain(grain)
    row = dict(valid)
    if mutation == "missing_field":
        row = _without(row, list(row)[-1])
    elif mutation == "extra_field":
        row["hero_smuggled_field"] = 1
    elif mutation == "wrong_order":
        row = _reordered(row)
    elif mutation == "wrong_schema_version":
        row["schema_version"] = "live-degradation-v2"
    elif mutation == "empty_run_id":
        row["run_id"] = ""
    with pytest.raises(SchemaError, match=re.escape(f"[{GENERIC_RULES[mutation]}]")):
        validator(row)


def test_every_grain_accepts_its_own_valid_row_under_the_same_harness():
    """The negative grid above is only meaningful if the harness passes the unmutated row --
    otherwise all twenty cases would 'pass' for the wrong reason."""
    for name in GRAINS:
        validator, valid = _grain(name)
        validator(dict(valid))


def test_live_degradation_dir_is_non_behavioural():
    """It is an IO path with no /choose effect. is_excluded fails closed toward INCLUSION, so
    leaving it unclassified would put the telemetry path into config_hash -- merely choosing
    where to write would change the identity of the run being measured.

    NOTE ON TIMING: this task does not yet READ the variable anywhere in production code, so
    test_every_showdown_env_read_is_classified can only confirm the existing inventory here.
    The full link is proven in Task 4, which introduces the real os.environ read.
    """
    from showdown_bot.eval.config_env import (
        NON_BEHAVIORAL,
        behavior_env,
        is_classified,
        is_excluded,
    )

    name = "SHOWDOWN_LIVE_DEGRADATION_DIR"
    assert name in NON_BEHAVIORAL
    assert is_classified(name)
    assert is_excluded(name)
    assert behavior_env({name: "X:/anywhere"}) == {}


def test_run_directory_is_gitignored():
    """The recorder is ALWAYS ON and writes under the repo root by default. .gitignore covers
    showdown_bot/logs/ only, so without this entry every run would leave untracked evidence in
    git status and break the Task 12 hygiene check."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    target = "logs/live-degradation/20260729T000000Z-abc123/decisions.jsonl"
    proc = subprocess.run(
        ["git", "check-ignore", "--", target],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, (
        f"{target} is not ignored; git check-ignore said rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


from pathlib import Path  # noqa: E402

from showdown_bot.client.live_degradation import (  # noqa: E402
    DEFAULT_PARENT,
    DIR_ENV,
    LiveDegradationRecorder,
    PreflightError,
    resolve_parent,
)


def _refuse_the_probe(monkeypatch):
    """Make only the probe write fail, leaving every other open() alone.

    This patches the MODULE namespace because preflight currently calls the bare builtin open(),
    which Python resolves through module globals first. That is a fact about today's
    implementation, not a requirement on it: if preflight is ever refactored to Path.open(), THIS
    TEST must be adapted -- the patch would otherwise become a silent no-op and prove nothing.
    The test follows the implementation, never the other way round.
    """
    real_open = open

    def _refuse(path, mode="r", *args, **kwargs):
        if str(path).endswith(".probe"):
            raise OSError("read-only filesystem")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("showdown_bot.client.live_degradation.open", _refuse, raising=False)


def test_preflight_creates_an_exclusive_run_dir(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert rec.run_dir.parent == tmp_path
    assert rec.run_dir.is_dir()
    assert rec.run_dir.name == rec.run_id


def test_preflight_refuses_an_existing_run_dir(tmp_path, monkeypatch):
    """C9: a new run must never reuse or overwrite existing evidence."""
    monkeypatch.setattr(
        "showdown_bot.client.live_degradation._new_run_id", lambda: "fixed-run-id")
    LiveDegradationRecorder.preflight(parent=tmp_path)
    with pytest.raises(PreflightError, match=re.escape("[dir_exists]")):
        LiveDegradationRecorder.preflight(parent=tmp_path)


def test_preflight_fails_when_the_parent_is_not_a_directory(tmp_path):
    """Windows and POSIX raise different OSError subclasses here, which is exactly why the
    implementation catches OSError broadly instead of enumerating them."""
    target = tmp_path / "not-a-dir"
    target.write_text("blocking file", encoding="utf-8")
    with pytest.raises(PreflightError, match=re.escape("[dir_create]")):
        LiveDegradationRecorder.preflight(parent=target)


def test_preflight_probe_is_removed_and_the_dir_is_left_empty(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert list(rec.run_dir.iterdir()) == []


def test_preflight_fails_when_the_probe_cannot_be_written(tmp_path, monkeypatch):
    _refuse_the_probe(monkeypatch)
    with pytest.raises(PreflightError, match=re.escape("[probe]")):
        LiveDegradationRecorder.preflight(parent=tmp_path)


def test_default_parent_when_the_override_is_unset(monkeypatch):
    monkeypatch.delenv(DIR_ENV, raising=False)
    assert resolve_parent() == DEFAULT_PARENT
    assert DEFAULT_PARENT == Path("logs") / "live-degradation"


def test_env_override_replaces_the_parent_only(tmp_path, monkeypatch):
    """8.1: the override replaces the PARENT; the <run_id> subdirectory is still created
    beneath it."""
    monkeypatch.setenv(DIR_ENV, str(tmp_path / "custom-sink"))
    rec = LiveDegradationRecorder.preflight()
    assert rec.run_dir.parent == tmp_path / "custom-sink"
    assert rec.run_dir.name == rec.run_id
    assert rec.run_dir.is_dir()


def test_env_override_empty_string_falls_back_to_the_default(monkeypatch):
    """An empty override would otherwise resolve to the current directory."""
    monkeypatch.setenv(DIR_ENV, "")
    assert resolve_parent() == DEFAULT_PARENT


def test_explicit_parent_wins_over_the_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(DIR_ENV, str(tmp_path / "env-sink"))
    rec = LiveDegradationRecorder.preflight(parent=tmp_path / "explicit-sink")
    assert rec.run_dir.parent == tmp_path / "explicit-sink"
    assert not (tmp_path / "env-sink").exists()


def test_the_override_is_the_only_environment_read_in_the_module():
    """The drift test in test_config_env.py scans source for SHOWDOWN_* reads. Keeping this
    module to exactly one environment read keeps that scan unambiguous, and keeps the always-on
    guarantee honest: no second variable can quietly gate whether recording happens."""
    module_path = Path(
        LiveDegradationRecorder.__module__.replace(".", "/") + ".py")
    root = Path(__file__).resolve().parents[1] / "src"
    text = (root / module_path).read_text(encoding="utf-8")
    assert text.count("os.environ") == 1
    assert "os.environ.get(DIR_ENV)" in text
    assert 'DIR_ENV = "SHOWDOWN_LIVE_DEGRADATION_DIR"' in text


def _record_clean(rec, room="battle-x-1", rqid=1):
    return rec.record_decision(
        room_id=room, rqid=rqid, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="heuristic",
        fallback_reason=None, agent_crash_type=None)


def test_gate_false_for_book_absent_records_not_applicable(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=3, book_absent=True, team_preview=False,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None)
    assert row["derivation_applicable"] is False
    assert row["is_degraded"] is None       # NOT False -- "not asked" != "not degraded"
    assert row["outcome"] == "not_applicable"


def test_gate_false_for_team_preview(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=1, book_absent=False, team_preview=True,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None)
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


def test_gate_false_normalises_stage_and_reason_to_none(tmp_path):
    """choose_with_fallback marks 'team_preview' on the preview path, and the caller passes
    whatever the sink holds. The gate-false branch must NULL both fields rather than carry a
    stage the derivation was never asked about (section 8 null rules)."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=1, book_absent=False, team_preview=True,
        state_build_failed=False, selection_stage="team_preview",
        fallback_reason="heuristic_timeout", agent_crash_type=None)
    assert row["selection_stage"] is None
    assert row["fallback_reason"] is None


def test_gate_true_clean_decision(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = _record_clean(rec, rqid=5)
    assert row["derivation_applicable"] is True
    assert row["is_degraded"] is False
    assert row["outcome"] == "ok"


def test_state_build_failure_is_degraded_with_the_stage_it_really_gets(tmp_path):
    """When the state build fails, choose_with_fallback skips both the heuristic and the
    max_damage layer (both require `state is not None`) and lands on
    deterministic_default_pair. state_degraded DOMINATES that stage in both derivations."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=6, book_absent=False, team_preview=False,
        state_build_failed=True, selection_stage="deterministic_default_pair",
        fallback_reason=None, agent_crash_type=None)
    assert row["is_degraded"] is True
    assert row["outcome"] == "degraded_state"


def test_fallback_stage_is_degraded_and_classified_fallback(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=7, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="max_damage_fallback",
        fallback_reason="heuristic_timeout", agent_crash_type=None)
    assert row["is_degraded"] is True and row["outcome"] == "fallback"


def test_crash_dominates_the_stage(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=8, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="heuristic", fallback_reason=None,
        agent_crash_type="ValueError")
    assert row["is_degraded"] is True and row["outcome"] == "crash"


def test_crash_on_the_book_absent_path_stays_not_applicable(tmp_path):
    """A smoke crash has the gate FALSE: neither derivation is called, so is_degraded stays
    null. This is why agent_crashes is not bounded by degraded_decisions."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=9, book_absent=True, team_preview=False,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type="KeyError")
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


def test_decision_seq_is_zero_based_and_separate_per_room(tmp_path):
    """Exactly [0, 1, 0, 2] -- zero-based, and each room counts on its own. 'Monotonic' would
    be a weaker claim that [3, 7, 0, 9] would also satisfy."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    seqs = [
        _record_clean(rec, room=r, rqid=i)["decision_seq"]
        for r, i in (("a", 1), ("a", 2), ("b", 1), ("a", 3))
    ]
    assert seqs == [0, 1, 0, 2]


def test_row_has_exactly_the_declared_fields_in_order(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert tuple(_record_clean(rec)) == DECISION_FIELDS


def test_every_recorded_decision_validates(tmp_path):
    """Not a restatement of the validator: this proves the rows record_decision actually BUILDS
    satisfy it, which is a different claim from the hand-written fixtures in the mutation tests."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rows = [
        _record_clean(rec, rqid=1),
        rec.record_decision(room_id="battle-x-1", rqid=2, book_absent=True,
                            team_preview=False, state_build_failed=False,
                            selection_stage=None, fallback_reason=None,
                            agent_crash_type=None),
        rec.record_decision(room_id="battle-x-1", rqid=3, book_absent=False,
                            team_preview=False, state_build_failed=True,
                            selection_stage="deterministic_default_pair",
                            fallback_reason=None, agent_crash_type=None),
        rec.record_decision(room_id="battle-x-1", rqid=4, book_absent=False,
                            team_preview=False, state_build_failed=False,
                            selection_stage="server_default",
                            fallback_reason="default_pair_error", agent_crash_type=None),
    ]
    for row in rows:
        validate_decision_row(dict(row))
    assert rec.schema_errors_total == 0
    assert len(rec._decisions["battle-x-1"]) == 4


def test_an_invalid_row_is_counted_and_not_buffered(tmp_path, monkeypatch):
    """The validator is a DEFECT signal. If it fires the row is refused rather than written into
    a file consumers are told is schema-valid, the failure is counted, and the recorder status
    goes faulty. It never propagates (C11)."""
    def _reject(row):
        raise SchemaError("forced [test]: injected")

    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(
        "showdown_bot.client.live_degradation.validate_decision_row", _reject)
    _record_clean(rec)
    assert rec.schema_errors_total == 1
    assert rec._decisions.get("battle-x-1", []) == []
    assert rec.exit_status() != 0


def test_a_refused_row_does_not_consume_a_sequence_number(tmp_path, monkeypatch):
    """decision_seq indexes what was BUFFERED. A refused row must not leave a gap, or a reader
    would take the gap for a lost decision."""
    calls = {"n": 0}
    real = None

    def _reject_first(row):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SchemaError("forced [test]: injected")
        return real(row)

    import showdown_bot.client.live_degradation as mod
    real = mod.validate_decision_row
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(mod, "validate_decision_row", _reject_first)
    _record_clean(rec, rqid=1)
    row = _record_clean(rec, rqid=2)
    assert row["decision_seq"] == 0


def test_the_stage_vocabulary_of_choose_with_fallback_is_fully_classifiable():
    """classify_live_outcome RAISES on an unknown stage. That raise is unreachable here only
    because every stage choose_with_fallback can mark is either an intended-completion stage, a
    known fallback stage, or team_preview -- which the 5.1 gate excludes. This turns that
    assumption into a checked invariant: if a future stage is added to battle/decision.py without
    extending the vocabulary, THIS fails rather than a live run."""
    from pathlib import Path

    from showdown_bot.eval.decision_profile import LIVE_FALLBACK_STAGES, LIVE_OK_STAGE

    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "showdown_bot" / "battle" / "decision.py"
    ).read_text(encoding="utf-8")
    marked = set(re.findall(r'_mark_selection\(\s*trace,\s*"([a-z_]+)"', source))
    assert marked, "no _mark_selection call sites found -- the regex needs updating"
    classifiable = {LIVE_OK_STAGE, *LIVE_FALLBACK_STAGES, "team_preview"}
    assert marked <= classifiable, f"unclassifiable stages: {sorted(marked - classifiable)}"


def test_server_error_is_room_attributed(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="server_error",
                          payload="[Invalid choice] Can't move: needs a target",
                          room_id="battle-x-1", active_battle_count=2)
    assert ev["attribution"] == "room" and ev["room_id"] == "battle-x-1"


def test_server_error_payload_is_stored_whole(tmp_path):
    """Section 7 requires the payload; no truncation rule has been approved."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    payload = "x" * 4096
    ev = rec.record_event(event_type="server_error", payload=payload,
                          room_id="battle-x-1", active_battle_count=1)
    assert ev["payload"] == payload


def test_invalid_choice_pm_with_two_active_battles_is_unattributed(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id=None, active_battle_count=2)
    assert ev["attribution"] == "unattributed" and ev["room_id"] is None


def test_invalid_choice_pm_room_hint_is_dropped_when_more_than_one_is_active(tmp_path):
    """Even if a caller passes a room, two active battles make the PM unattributable. Charging
    it anyway would manufacture degradation never observed on that battle (C8)."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id="battle-x-1", active_battle_count=2)
    assert ev["attribution"] == "unattributed" and ev["room_id"] is None


def test_invalid_choice_pm_with_one_active_battle_is_inferred(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id="battle-x-1", active_battle_count=1)
    assert ev["attribution"] == "inferred" and ev["room_id"] == "battle-x-1"


def test_event_row_has_exactly_the_declared_fields_and_validates(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="server_error", payload="p",
                          room_id="battle-x-1", active_battle_count=1)
    assert tuple(ev) == EVENT_FIELDS
    validate_event_row(dict(ev))


def test_an_unknown_event_type_is_counted_and_not_buffered(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.record_event(event_type="disconnect", payload="p",
                     room_id="battle-x-1", active_battle_count=1)
    assert rec.schema_errors_total == 1
    assert rec._events == []
    assert rec.exit_status() != 0


def test_counters_come_from_their_named_sources(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_decision(room_id="R", rqid=2, book_absent=True, team_preview=False,
                        state_build_failed=False, selection_stage=None,
                        fallback_reason=None, agent_crash_type=None)
    rec.record_decision(room_id="R", rqid=3, book_absent=False, team_preview=False,
                        state_build_failed=True,
                        selection_stage="deterministic_default_pair",
                        fallback_reason=None, agent_crash_type=None)
    rec.record_event(event_type="server_error", payload="p",
                     room_id="R", active_battle_count=1)
    rec.record_event(event_type="invalid_choice_pm", payload="p",
                     room_id="R", active_battle_count=1)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["decisions_total"] == 3
    assert row["decisions_not_applicable"] == 1
    assert row["degraded_decisions"] == 1
    assert row["state_build_failures"] == 1
    assert row["agent_crashes"] == 0
    assert row["fallback_decisions"] == 0
    assert row["server_errors"] == 1
    assert row["own_invalid_choices"] == 1     # from the EVENT stream, inferred only
    assert row["write_errors"] == 0
    assert tuple(row) == BATTLE_FIELDS
    validate_battle_row(dict(row))


def test_fallback_decisions_counts_only_gate_true_fallback_outcomes(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.record_decision(room_id="R", rqid=1, book_absent=False, team_preview=False,
                        state_build_failed=False, selection_stage="max_damage_fallback",
                        fallback_reason="heuristic_timeout", agent_crash_type=None)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["fallback_decisions"] == 1 and row["degraded_decisions"] == 1


def test_unattributed_event_increments_no_battle_counter(tmp_path):
    """C8: charging an unattributable event to a room -- or to all -- would manufacture
    degradation never observed on that battle."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_event(event_type="invalid_choice_pm", payload="p",
                     room_id=None, active_battle_count=3)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["own_invalid_choices"] == 0
    assert row["degraded_decisions"] == 0


def test_another_rooms_events_do_not_leak_into_this_battle(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_event(event_type="server_error", payload="p",
                     room_id="OTHER", active_battle_count=2)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["server_errors"] == 0


def test_not_applicable_rows_are_never_counted_as_degraded(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    for i in range(4):
        rec.record_decision(room_id="R", rqid=i, book_absent=True, team_preview=False,
                            state_build_failed=False, selection_stage=None,
                            fallback_reason=None, agent_crash_type=None)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["decisions_not_applicable"] == 4 and row["degraded_decisions"] == 0


def test_a_gate_false_crash_counts_as_a_crash_but_not_as_degraded(tmp_path):
    """agent_crashes is deliberately NOT bounded by degraded_decisions: a crash on the
    book-absent path has the gate false, so is_degraded stays null."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.record_decision(room_id="R", rqid=1, book_absent=True, team_preview=False,
                        state_build_failed=False, selection_stage=None,
                        fallback_reason=None, agent_crash_type="KeyError")
    row = rec.build_battle_row(room_id="R", end_reason="tie")
    assert row["agent_crashes"] == 1
    assert row["degraded_decisions"] == 0
    validate_battle_row(dict(row))

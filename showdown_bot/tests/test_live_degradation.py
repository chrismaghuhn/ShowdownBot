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

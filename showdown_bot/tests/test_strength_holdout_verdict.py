# showdown_bot/tests/test_strength_holdout_verdict.py
"""Task 7: two upstream verdict verifiers -- I8-D and Coverage. Both are exercised against a
STUBBED canonical schedule (the bulk of these tests care about field-level verification logic,
not schedule rebuilding) plus two dedicated, UNSTUBBED tests that call the real offline rebuild
functions against the actual checkout, so this suite proves more than test doubles."""
import json
import math

import pytest

from showdown_bot.eval.coverage_schedule import COVERAGE_EXPECTED_PANEL_HASH, COVERAGE_SEED_BASE
from showdown_bot.eval.coverage_verdict import COVERAGE_CELL_FLOORS, COVERAGE_MAX_SCORED_DECISIONS
from showdown_bot.eval.i8d_runner import (
    I8D_MAX_SCORED_DECISIONS, I8D_MIN_ACTIVE_DECISIONS, I8D_MIN_DISTINCT_BATTLES,
)
from showdown_bot.eval.i8d_schedule import I8D_EXPECTED_PANEL_HASH, I8D_SEED_BASE
from showdown_bot.eval.schedule import Schedule, ScheduleRow
from showdown_bot.eval.strength_holdout_verdict import (
    StrengthHoldoutRunError, verify_coverage_verdict_artifact, verify_i8d_verdict_artifact,
)

_BUDGET_MS = 1000  # config/eval/gates.yaml's decision_latency_p95_budget_ms, at time of writing

_CANDIDATE_IDENTITY = "cand-identity-fixture"
_GIT_SHA = "deadbeefcafef00d"
_CONFIG_HASH = "cfg16testtest01"
_HERO_AGENT = "heuristic"
_CALC_BACKEND = "oneshot"

_IDENTITY_KWARGS = dict(
    candidate_identity=_CANDIDATE_IDENTITY, git_sha=_GIT_SHA, config_hash=_CONFIG_HASH,
    hero_agent=_HERO_AGENT, calc_backend=_CALC_BACKEND,
)


def _write_json(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


# --- I8-D fixtures ---------------------------------------------------------------------------

_I8D_FAKE_SCHEDULE_ROWS = 100  # >= the 90 battles_played the "valid" fixture below claims


def _fake_i8d_schedule(n_rows=_I8D_FAKE_SCHEDULE_ROWS):
    # Task 7 review-fix (P1 #2): must be large enough that a "valid" verdict's battles_played
    # is a geometrically possible subset of the canonical schedule's rows, once
    # verify_i8d_verdict_artifact binds battles_played <= len(canonical.rows).
    opp_choices = (
        ("heuristic", "teams/panel_champions_v0/goodstuff.txt", "fixture-i8d-opp-hash-a"),
        ("max_damage", "teams/panel_champions_v0/tailwind_offense.txt", "fixture-i8d-opp-hash-b"),
    )
    rows = tuple(
        ScheduleRow(
            format_id="gen9championsvgc2026regma", hero_team_path="teams/fixed_champions_v0.txt",
            opp_policy=opp_choices[i % len(opp_choices)][0],
            opp_team_path=opp_choices[i % len(opp_choices)][1], seed_index=i,
            hero_team_hash="fixture-i8d-hero-hash",
            opp_team_hash=opp_choices[i % len(opp_choices)][2], panel_split="dev",
        )
        for i in range(n_rows)
    )
    return Schedule(version="fixture-i8d-v0", rows=rows, schedule_hash="fixture-i8d-schedule-hash",
                     panel_hash=I8D_EXPECTED_PANEL_HASH)


def _valid_i8d_verdict(schedule, **overrides):
    data = {
        "candidate_identity": _CANDIDATE_IDENTITY, "git_sha": _GIT_SHA, "config_hash": _CONFIG_HASH,
        "calc_backend": _CALC_BACKEND, "hero_agent": _HERO_AGENT,
        "verdict": "PASS", "panel_hash": I8D_EXPECTED_PANEL_HASH, "schedule_hash": schedule.schedule_hash,
        "seed_base": I8D_SEED_BASE, "seed_log_verified": True, "p95_is_gate_value": True,
        "hero_team_hash": schedule.rows[0].hero_team_hash,
        "opp_team_hashes": sorted({r.opp_team_hash for r in schedule.rows if r.opp_team_hash is not None}),
        "battles_played": 90, "scored_decisions": 900, "max_scored_decisions": I8D_MAX_SCORED_DECISIONS,
        "scored_overshoot": max(0, 900 - I8D_MAX_SCORED_DECISIONS),
        "active_valid_decisions": 65, "distinct_active_battles": 25,
        "stop_reason": "exposure_floor_met", "exposure_floor_met": True,
        "min_active_decisions": I8D_MIN_ACTIVE_DECISIONS, "min_distinct_battles": I8D_MIN_DISTINCT_BATTLES,
        "budget_ms": _BUDGET_MS, "p95_ms": 250.0,
    }
    data.update(overrides)
    return data


@pytest.fixture
def stub_i8d_schedule(monkeypatch):
    schedule = _fake_i8d_schedule()
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_verdict.build_i8d_canonical_schedule",
        lambda **kwargs: schedule,
    )
    return schedule


def _i8d_call(tmp_path, stub_i8d_schedule, data, name="i8d_verdict.json"):
    path = _write_json(tmp_path, name, data)
    return verify_i8d_verdict_artifact(
        verdict_path=path, teams_root=str(tmp_path), **_IDENTITY_KWARGS,
    )


# --- Coverage fixtures ------------------------------------------------------------------------

_COVERAGE_FAKE_SCHEDULE_ROWS = 130  # >= the 120 battles_played the "valid" fixture below claims


def _fake_coverage_schedule(n_rows=_COVERAGE_FAKE_SCHEDULE_ROWS):
    # Task 7 review-fix (P1 #2): must be large enough that a "valid" verdict's battles_played
    # (and every cell's decisions/distinct_battles) is a geometrically possible subset of the
    # canonical schedule's rows, once verify_coverage_verdict_artifact binds
    # battles_played <= len(canonical.rows).
    opp_choices = (
        ("heuristic", "teams/panel_champions_coverage_v0/cov_foe_slot0.txt", "fixture-cov-opp-hash-a"),
        ("max_damage", "teams/panel_champions_coverage_v0/cov_foe_slot1.txt", "fixture-cov-opp-hash-b"),
    )
    rows = tuple(
        ScheduleRow(
            format_id="gen9championsvgc2026regma", hero_team_path="teams/fixed_champions_v0.txt",
            opp_policy=opp_choices[i % len(opp_choices)][0],
            opp_team_path=opp_choices[i % len(opp_choices)][1], seed_index=i,
            hero_team_hash="fixture-cov-hero-hash",
            opp_team_hash=opp_choices[i % len(opp_choices)][2], panel_split="dev",
        )
        for i in range(n_rows)
    )
    return Schedule(version="fixture-coverage-v0", rows=rows, schedule_hash="fixture-coverage-schedule-hash",
                     panel_hash=COVERAGE_EXPECTED_PANEL_HASH)


def _valid_cell_counts():
    return {
        cell: {"decisions": floor[0] + 5, "distinct_battles": floor[1] + 2}
        for cell, floor in COVERAGE_CELL_FLOORS.items()
    }


def _valid_coverage_verdict(schedule, **overrides):
    data = {
        "schedule_hash": schedule.schedule_hash, "panel_hash": COVERAGE_EXPECTED_PANEL_HASH,
        "candidate_identity": _CANDIDATE_IDENTITY, "git_sha": _GIT_SHA, "config_hash": _CONFIG_HASH,
        "calc_backend": _CALC_BACKEND, "hero_agent": _HERO_AGENT,
        "hero_team_hash": schedule.rows[0].hero_team_hash,
        "opp_team_hashes": sorted({r.opp_team_hash for r in schedule.rows if r.opp_team_hash is not None}),
        "seed_base": COVERAGE_SEED_BASE, "seed_log_verified": True,
        "battles_played": 120, "scored_decisions": 1200, "max_scored_decisions": COVERAGE_MAX_SCORED_DECISIONS,
        "cell_floors": {cell: list(floor) for cell, floor in COVERAGE_CELL_FLOORS.items()},
        "cell_counts": _valid_cell_counts(), "safety_violations": 0, "schedule_complete": False,
        "verdict": "PASS", "stop_reason": "coverage_floor_met",
    }
    data.update(overrides)
    return data


@pytest.fixture
def stub_coverage_schedule(monkeypatch):
    schedule = _fake_coverage_schedule()
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_verdict.build_coverage_live_schedule",
        lambda **kwargs: schedule,
    )
    return schedule


def _cov_call(tmp_path, stub_coverage_schedule, data, name="cov_verdict.json"):
    path = _write_json(tmp_path, name, data)
    return verify_coverage_verdict_artifact(
        verdict_path=path, teams_root=str(tmp_path), **_IDENTITY_KWARGS,
    )


# --- Common artifact boundary (both verifiers) -----------------------------------------------

@pytest.mark.parametrize("verify_fn", [verify_i8d_verdict_artifact, verify_coverage_verdict_artifact])
def test_rejects_a_missing_verdict_path(tmp_path, verify_fn):
    with pytest.raises(StrengthHoldoutRunError):
        verify_fn(verdict_path=str(tmp_path / "does_not_exist.json"), teams_root=str(tmp_path),
                   **_IDENTITY_KWARGS)


@pytest.mark.parametrize("verify_fn", [verify_i8d_verdict_artifact, verify_coverage_verdict_artifact])
def test_rejects_an_empty_verdict_path(tmp_path, verify_fn):
    with pytest.raises(StrengthHoldoutRunError):
        verify_fn(verdict_path="", teams_root=str(tmp_path), **_IDENTITY_KWARGS)


@pytest.mark.parametrize("verify_fn", [verify_i8d_verdict_artifact, verify_coverage_verdict_artifact])
def test_rejects_truncated_json(tmp_path, verify_fn):
    path = tmp_path / "truncated.json"
    path.write_text('{"candidate_identity": "x", "verdict": "PA', encoding="utf-8")
    with pytest.raises(StrengthHoldoutRunError):
        verify_fn(verdict_path=str(path), teams_root=str(tmp_path), **_IDENTITY_KWARGS)


@pytest.mark.parametrize("verify_fn", [verify_i8d_verdict_artifact, verify_coverage_verdict_artifact])
@pytest.mark.parametrize("non_object", ["[]", "null", '"just a string"', "42"])
def test_rejects_non_object_json(tmp_path, verify_fn, non_object):
    path = tmp_path / "non_object.json"
    path.write_text(non_object, encoding="utf-8")
    with pytest.raises(StrengthHoldoutRunError):
        verify_fn(verdict_path=str(path), teams_root=str(tmp_path), **_IDENTITY_KWARGS)


def test_i8d_rejects_a_missing_field(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule)
    del data["scored_overshoot"]
    with pytest.raises(StrengthHoldoutRunError, match="missing"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_an_extra_field(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, unexpected_extra_field="x")
    with pytest.raises(StrengthHoldoutRunError, match="extra"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_coverage_rejects_a_missing_field(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    del data["safety_violations"]
    with pytest.raises(StrengthHoldoutRunError, match="missing"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_an_extra_field(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, unexpected_extra_field="x")
    with pytest.raises(StrengthHoldoutRunError, match="extra"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


# --- I8-D specific ------------------------------------------------------------------------

def test_i8d_valid_matching_verdict_passes(tmp_path, stub_i8d_schedule):
    result = _i8d_call(tmp_path, stub_i8d_schedule, _valid_i8d_verdict(stub_i8d_schedule))
    assert result["verdict"] == "PASS"


@pytest.mark.parametrize("field,wrong_value", [
    ("candidate_identity", "wrong-identity"), ("git_sha", "wrong-sha"),
    ("config_hash", "wrong-cfg"), ("hero_agent", "max_damage"), ("calc_backend", "persistent"),
])
def test_i8d_rejects_each_identity_component_individually(tmp_path, stub_i8d_schedule, field, wrong_value):
    data = _valid_i8d_verdict(stub_i8d_schedule, **{field: wrong_value})
    with pytest.raises(StrengthHoldoutRunError, match=field):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_panel_hash_mismatch(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, panel_hash="wrong-panel-hash")
    with pytest.raises(StrengthHoldoutRunError, match="panel_hash"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_seed_base_mismatch(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, seed_base="wrong-seed-base")
    with pytest.raises(StrengthHoldoutRunError, match="seed_base"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_schedule_hash_mismatch(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, schedule_hash="wrong-schedule-hash")
    with pytest.raises(StrengthHoldoutRunError, match="schedule_hash"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_hero_hash_mismatch(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, hero_team_hash="wrong-hero-hash")
    with pytest.raises(StrengthHoldoutRunError, match="hero_team_hash"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_an_opponent_hashes_mismatch(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, opp_team_hashes=["wrong-opp-hash"])
    with pytest.raises(StrengthHoldoutRunError, match="opp_team_hashes"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


@pytest.mark.parametrize("field", ["min_active_decisions", "min_distinct_battles", "max_scored_decisions", "budget_ms"])
def test_i8d_rejects_wrong_pinned_values(tmp_path, stub_i8d_schedule, field):
    data = _valid_i8d_verdict(stub_i8d_schedule, **{field: 999999})
    with pytest.raises(StrengthHoldoutRunError, match=field):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_an_inconsistent_scored_overshoot(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, scored_overshoot=12345)
    with pytest.raises(StrengthHoldoutRunError, match="scored_overshoot"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


@pytest.mark.parametrize("field", [
    "battles_played", "scored_decisions", "scored_overshoot",
    "active_valid_decisions", "distinct_active_battles",
])
@pytest.mark.parametrize("bad_value", [-1, "5", 1.5, True, None])
def test_i8d_rejects_invalid_counter_types(tmp_path, stub_i8d_schedule, field, bad_value):
    data = _valid_i8d_verdict(stub_i8d_schedule, **{field: bad_value})
    with pytest.raises(StrengthHoldoutRunError):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_active_valid_decisions_exceeding_scored_decisions(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, scored_decisions=10, active_valid_decisions=11,
                               distinct_active_battles=5, min_active_decisions=I8D_MIN_ACTIVE_DECISIONS)
    with pytest.raises(StrengthHoldoutRunError, match="active_valid_decisions"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_distinct_active_battles_exceeding_battles_played(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, battles_played=5, distinct_active_battles=6)
    with pytest.raises(StrengthHoldoutRunError, match="distinct_active_battles"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_claimed_but_unmet_active_decisions_floor(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, active_valid_decisions=I8D_MIN_ACTIVE_DECISIONS - 1)
    with pytest.raises(StrengthHoldoutRunError, match="active_valid_decisions"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_claimed_but_unmet_distinct_battles_floor(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, distinct_active_battles=I8D_MIN_DISTINCT_BATTLES - 1)
    with pytest.raises(StrengthHoldoutRunError, match="distinct_active_battles"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_non_pass_verdict(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, verdict="FAIL")
    with pytest.raises(StrengthHoldoutRunError, match="PASS"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_a_wrong_stop_reason(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, stop_reason="max_battles")
    with pytest.raises(StrengthHoldoutRunError, match="stop_reason"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_p95_is_gate_value_false(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, p95_is_gate_value=False)
    with pytest.raises(StrengthHoldoutRunError, match="p95_is_gate_value"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_exposure_floor_met_false(tmp_path, stub_i8d_schedule):
    data = _valid_i8d_verdict(stub_i8d_schedule, exposure_floor_met=False)
    with pytest.raises(StrengthHoldoutRunError, match="exposure_floor_met"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


@pytest.mark.parametrize("bad_p95", [
    float("nan"), float("inf"), float("-inf"), -1.0, _BUDGET_MS + 1, True,
])
def test_i8d_rejects_invalid_p95_ms(tmp_path, stub_i8d_schedule, bad_p95):
    data = _valid_i8d_verdict(stub_i8d_schedule, p95_ms=bad_p95)
    with pytest.raises(StrengthHoldoutRunError, match="p95_ms"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_rejects_battles_played_exceeding_canonical_schedule_rows(tmp_path, stub_i8d_schedule):
    n_rows = len(stub_i8d_schedule.rows)
    data = _valid_i8d_verdict(stub_i8d_schedule, battles_played=n_rows + 1)
    with pytest.raises(StrengthHoldoutRunError, match="battles_played"):
        _i8d_call(tmp_path, stub_i8d_schedule, data)


def test_i8d_wraps_a_canonical_schedule_rebuild_failure(tmp_path, monkeypatch):
    # Task 7 review-fix (P1 #1): a foreign exception from the real rebuild (e.g. a lower-level
    # Panel/Schedule ValueError) must never escape this module raw -- only StrengthHoldoutRunError.
    def _boom(**kwargs):
        raise ValueError("simulated i8d schedule rebuild failure")

    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_verdict.build_i8d_canonical_schedule", _boom,
    )
    data = _valid_i8d_verdict(_fake_i8d_schedule())
    path = _write_json(tmp_path, "i8d_verdict.json", data)
    with pytest.raises(StrengthHoldoutRunError, match="rebuild"):
        verify_i8d_verdict_artifact(verdict_path=path, teams_root=str(tmp_path), **_IDENTITY_KWARGS)


def test_i8d_rejects_nan_p95_ms_via_json_round_trip(tmp_path, stub_i8d_schedule):
    # json.dumps(float("nan")) writes the bare token NaN, which json.loads parses back to
    # float("nan") (Python's json module allows this non-standard extension by default) -- the
    # same NaN-unsafe-comparison class this whole module must be immune to (mirrors
    # coverage_runner.py's own documented NaN finding for the identical p95_ms check).
    data = _valid_i8d_verdict(stub_i8d_schedule)
    path = tmp_path / "nan_verdict.json"
    text = json.dumps(data).replace(str(data["p95_ms"]), "NaN")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(StrengthHoldoutRunError, match="p95_ms"):
        verify_i8d_verdict_artifact(verdict_path=str(path), teams_root=str(tmp_path), **_IDENTITY_KWARGS)


# --- Coverage specific ---------------------------------------------------------------------

def test_coverage_valid_matching_verdict_passes(tmp_path, stub_coverage_schedule):
    result = _cov_call(tmp_path, stub_coverage_schedule, _valid_coverage_verdict(stub_coverage_schedule))
    assert result["verdict"] == "PASS"


@pytest.mark.parametrize("field,wrong_value", [
    ("candidate_identity", "wrong-identity"), ("git_sha", "wrong-sha"),
    ("config_hash", "wrong-cfg"), ("hero_agent", "max_damage"), ("calc_backend", "persistent"),
])
def test_coverage_rejects_each_identity_component_individually(tmp_path, stub_coverage_schedule, field, wrong_value):
    data = _valid_coverage_verdict(stub_coverage_schedule, **{field: wrong_value})
    with pytest.raises(StrengthHoldoutRunError, match=field):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_panel_hash_mismatch(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, panel_hash="wrong-panel-hash")
    with pytest.raises(StrengthHoldoutRunError, match="panel_hash"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_seed_base_mismatch(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, seed_base="wrong-seed-base")
    with pytest.raises(StrengthHoldoutRunError, match="seed_base"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_schedule_hash_mismatch(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, schedule_hash="wrong-schedule-hash")
    with pytest.raises(StrengthHoldoutRunError, match="schedule_hash"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_hero_hash_mismatch(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, hero_team_hash="wrong-hero-hash")
    with pytest.raises(StrengthHoldoutRunError, match="hero_team_hash"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_an_opponent_hashes_mismatch(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, opp_team_hashes=["wrong-opp-hash"])
    with pytest.raises(StrengthHoldoutRunError, match="opp_team_hashes"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_wrong_max_scored_decisions(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, max_scored_decisions=1)
    with pytest.raises(StrengthHoldoutRunError, match="max_scored_decisions"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_nonzero_safety_violations(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, safety_violations=1)
    with pytest.raises(StrengthHoldoutRunError, match="safety_violations"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


@pytest.mark.parametrize("bad_value", [-1, "0", 1.5, True, None])
def test_coverage_rejects_wrong_safety_violations_type(tmp_path, stub_coverage_schedule, bad_value):
    data = _valid_coverage_verdict(stub_coverage_schedule, safety_violations=bad_value)
    with pytest.raises(StrengthHoldoutRunError):
        _cov_call(tmp_path, stub_coverage_schedule, data)


@pytest.mark.parametrize("bad_value", ["true", 1, 0, None, "False"])
def test_coverage_rejects_wrong_schedule_complete_type(tmp_path, stub_coverage_schedule, bad_value):
    data = _valid_coverage_verdict(stub_coverage_schedule, schedule_complete=bad_value)
    with pytest.raises(StrengthHoldoutRunError, match="schedule_complete"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_accepts_schedule_complete_false_on_an_early_pass(tmp_path, stub_coverage_schedule):
    # A coverage PASS may legitimately happen BEFORE the schedule is exhausted -- schedule_complete
    # must never be required True. Task 7 review-fix (P1 #2): schedule_complete's VALUE is now
    # bound to battles_played == len(canonical.rows), so "early pass" must genuinely under-play
    # the canonical schedule for this to remain a valid False case.
    n_rows = len(stub_coverage_schedule.rows)
    data = _valid_coverage_verdict(stub_coverage_schedule, schedule_complete=False, battles_played=n_rows - 1)
    result = _cov_call(tmp_path, stub_coverage_schedule, data)
    assert result["schedule_complete"] is False


def test_coverage_accepts_schedule_complete_true(tmp_path, stub_coverage_schedule):
    # Task 7 review-fix (P1 #2): schedule_complete=True is only valid when battles_played
    # genuinely equals the canonical schedule's full row count.
    n_rows = len(stub_coverage_schedule.rows)
    data = _valid_coverage_verdict(stub_coverage_schedule, schedule_complete=True, battles_played=n_rows)
    result = _cov_call(tmp_path, stub_coverage_schedule, data)
    assert result["schedule_complete"] is True


def test_coverage_rejects_schedule_complete_true_when_the_schedule_is_not_exhausted(tmp_path, stub_coverage_schedule):
    n_rows = len(stub_coverage_schedule.rows)
    data = _valid_coverage_verdict(stub_coverage_schedule, schedule_complete=True, battles_played=n_rows - 1)
    with pytest.raises(StrengthHoldoutRunError, match="schedule_complete"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_schedule_complete_false_when_the_schedule_is_exhausted(tmp_path, stub_coverage_schedule):
    n_rows = len(stub_coverage_schedule.rows)
    data = _valid_coverage_verdict(stub_coverage_schedule, schedule_complete=False, battles_played=n_rows)
    with pytest.raises(StrengthHoldoutRunError, match="schedule_complete"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_battles_played_exceeding_canonical_schedule_rows(tmp_path, stub_coverage_schedule):
    n_rows = len(stub_coverage_schedule.rows)
    data = _valid_coverage_verdict(stub_coverage_schedule, battles_played=n_rows + 1)
    with pytest.raises(StrengthHoldoutRunError, match="battles_played"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_cell_decisions_exceeding_scored_decisions(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_counts"]["slot0"]["decisions"] = data["scored_decisions"] + 1
    with pytest.raises(StrengthHoldoutRunError, match="decisions"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_cell_distinct_battles_exceeding_battles_played(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_counts"]["slot0"]["distinct_battles"] = data["battles_played"] + 1
    with pytest.raises(StrengthHoldoutRunError, match="distinct_battles"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_wraps_a_canonical_schedule_rebuild_failure(tmp_path, monkeypatch):
    # Task 7 review-fix (P1 #1): a foreign exception from the real rebuild (e.g. a lower-level
    # Panel/Schedule ValueError) must never escape this module raw -- only StrengthHoldoutRunError.
    def _boom(**kwargs):
        raise ValueError("simulated coverage schedule rebuild failure")

    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_verdict.build_coverage_live_schedule", _boom,
    )
    data = _valid_coverage_verdict(_fake_coverage_schedule())
    path = _write_json(tmp_path, "cov_verdict.json", data)
    with pytest.raises(StrengthHoldoutRunError, match="rebuild"):
        verify_coverage_verdict_artifact(verdict_path=path, teams_root=str(tmp_path), **_IDENTITY_KWARGS)


def test_coverage_rejects_wrong_cell_floors_values(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_floors"] = {**data["cell_floors"], "slot0": [1, 1]}
    with pytest.raises(StrengthHoldoutRunError, match="cell_floors"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_wrong_typed_cell_floors(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, cell_floors="not-an-object")
    with pytest.raises(StrengthHoldoutRunError, match="cell_floors"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_missing_cell(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    del data["cell_counts"]["slot0"]
    with pytest.raises(StrengthHoldoutRunError, match="cell_counts"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_an_extra_cell(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_counts"]["not_a_real_cell"] = {"decisions": 5, "distinct_battles": 5}
    with pytest.raises(StrengthHoldoutRunError, match="cell_counts"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_non_object_cell_counts(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, cell_counts=["not", "an", "object"])
    with pytest.raises(StrengthHoldoutRunError, match="cell_counts"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_missing_count_field(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    del data["cell_counts"]["slot0"]["distinct_battles"]
    with pytest.raises(StrengthHoldoutRunError, match="slot0"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_an_extra_count_field(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_counts"]["slot0"]["unexpected"] = 1
    with pytest.raises(StrengthHoldoutRunError, match="slot0"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


@pytest.mark.parametrize("bad_value", [-1, "5", 1.5, True, None])
def test_coverage_rejects_invalid_count_values(tmp_path, stub_coverage_schedule, bad_value):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_counts"]["slot0"]["decisions"] = bad_value
    with pytest.raises(StrengthHoldoutRunError):
        _cov_call(tmp_path, stub_coverage_schedule, data)


@pytest.mark.parametrize("cell", list(COVERAGE_CELL_FLOORS))
def test_coverage_rejects_each_cell_individually_under_its_floor(tmp_path, stub_coverage_schedule, cell):
    data = _valid_coverage_verdict(stub_coverage_schedule)
    data["cell_counts"][cell] = {"decisions": 0, "distinct_battles": 0}
    with pytest.raises(StrengthHoldoutRunError, match=cell):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_non_pass_verdict(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, verdict="FAIL", stop_reason="safety_violation")
    with pytest.raises(StrengthHoldoutRunError, match="PASS"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


def test_coverage_rejects_a_wrong_stop_reason(tmp_path, stub_coverage_schedule):
    data = _valid_coverage_verdict(stub_coverage_schedule, stop_reason="max_battles")
    with pytest.raises(StrengthHoldoutRunError, match="stop_reason"):
        _cov_call(tmp_path, stub_coverage_schedule, data)


# --- Real, unstubbed offline schedule rebuilds (not just test doubles) -----------------------

def test_i8d_canonical_schedule_rebuild_is_real_and_offline():
    from showdown_bot.eval.coverage_runner import build_i8d_canonical_schedule
    schedule = build_i8d_canonical_schedule(teams_root="showdown_bot")
    assert schedule.rows
    assert schedule.schedule_hash
    assert schedule.panel_hash == I8D_EXPECTED_PANEL_HASH


def test_coverage_live_schedule_rebuild_is_real_and_offline():
    from showdown_bot.eval.coverage_runner import build_coverage_live_schedule
    schedule = build_coverage_live_schedule(teams_root="showdown_bot")
    assert schedule.rows
    assert schedule.schedule_hash
    assert schedule.panel_hash == COVERAGE_EXPECTED_PANEL_HASH

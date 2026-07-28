"""decision-profile-v4 schema tests (spec §7)."""
from __future__ import annotations

import pytest  # noqa: F811

from showdown_bot.eval.decision_profile import (  # noqa: F811
    SCHEMA_VERSION_V1,
    SCHEMA_VERSION_V2,
    SCHEMA_VERSION_LIVE,
    validate_profile_row_fields,
    validate_decision_profile_row,
    DecisionProfileError,
)


# ---- §7.1: v4 is a new schema version, not a mutation of v3 ----

def test_v4_schema_version_exists():
    from showdown_bot.eval.decision_profile import SCHEMA_VERSION_V4  # noqa: F811
    assert SCHEMA_VERSION_V4 == "decision-profile-v4"  # noqa: S101
    assert SCHEMA_VERSION_V4 not in {SCHEMA_VERSION_V1, SCHEMA_VERSION_V2, SCHEMA_VERSION_LIVE}  # noqa: S101


# ---- §7.2: v4 field set includes readiness fields ----

def test_v4_field_set_includes_readiness_fields():
    from showdown_bot.eval.decision_profile import _FIELD_SET_V4  # noqa: F811

    readiness_fields = {
        "search_depth", "search_topn_requested", "search_topm_requested",
        "depth2_candidates_selected", "depth2_response_slots_eligible",
        "accuracy_mode", "accuracy_branch_cap",
        "turn1_accuracy_leaf_count", "turn1_accuracy_cap_hits", "turn1_accuracy_cap_fallback",
        "turn2_accuracy_leaf_count", "turn2_accuracy_cap_hits", "turn2_accuracy_cap_fallback",
        "selection_stage", "fallback_reason",
    }
    assert readiness_fields <= _FIELD_SET_V4  # noqa: S101


def test_v4_is_superset_of_v3():
    from showdown_bot.eval.decision_profile import _FIELD_SET_V4, _FIELD_SET_LIVE  # noqa: F811
    assert _FIELD_SET_LIVE < _FIELD_SET_V4  # noqa: S101


# ---- §7.2: exact-closed field validation ----

def _minimal_v4_row():
    """A minimal valid v4 row for field-set testing."""
    from showdown_bot.eval.decision_profile import SCHEMA_VERSION_V4  # noqa: F811
    return {
        "schema_version": SCHEMA_VERSION_V4,
        "source": "live",
        "battle_id": "battle-1",
        "decision_index": 0,
        "arm_id": None,
        "rep": None,
        "config_id": "cfg",
        "format_id": "fmt",
        "git_sha": "abc123",
        "config_hash": "hash",
        "schedule_hash": "sched",
        "profile_manifest_hash": None,
        "calc_backend": "persistent",
        "backend_class": "persistent_warm",
        "cache_class": None,
        "damage_cache_size_at_rep_start": None,
        "speed_cache_size_at_rep_start": None,
        "dex_cache_size_at_rep_start": None,
        "spawn_count_before": 1,
        "transport_retried": False,
        "timer_scope": "agent_choose",
        "measured_ms": 100.0,
        "damage_batch_calls": 5,
        "planned_damage_batches": 3,
        "implicit_damage_batches": 2,
        "stats_batch_calls": 1,
        "types_batch_calls": 0,
        "mixed_batch_calls": 0,
        "transport_calls": 6,
        "transport_attempts": 6,
        "spawn_calls": 0,
        "requests_total": 20,
        "requests_unique": 15,
        "cache_hits": 5,
        "n_candidates": 6,
        "n_responses": 5,
        "n_mega_twins": 0,
        "n_branches": 0,
        "n_worlds": 1,
        "depth2_frontier": 0,
        "foe_mega_active": False,
        "outcome": "ok",
        "foe_mega_slots": [],
        "foe_mega_order_tie": False,
        # v4 readiness fields
        "search_depth": 1,
        "search_topn_requested": 2,
        "search_topm_requested": 2,
        "depth2_candidates_selected": 0,
        "depth2_response_slots_eligible": 0,
        "accuracy_mode": True,
        "accuracy_branch_cap": 6,
        "turn1_accuracy_leaf_count": 10,
        "turn1_accuracy_cap_hits": 0,
        "turn1_accuracy_cap_fallback": False,
        "turn2_accuracy_leaf_count": 0,
        "turn2_accuracy_cap_hits": 0,
        "turn2_accuracy_cap_fallback": False,
        "selection_stage": "heuristic",
        "fallback_reason": None,
    }


def test_v4_exact_field_set_accepts_valid():
    row = _minimal_v4_row()
    validate_profile_row_fields(row)  # should not raise


def test_v4_rejects_missing_field():
    row = _minimal_v4_row()
    del row["search_depth"]
    with pytest.raises(DecisionProfileError, match="missing=.*search_depth"):
        validate_profile_row_fields(row)


def test_v4_rejects_unknown_field():
    row = _minimal_v4_row()
    row["invented_field"] = 42
    with pytest.raises(DecisionProfileError, match="unknown=.*invented_field"):
        validate_profile_row_fields(row)


# ---- §7.3: Cross-field invariants (mutation-style negative tests) ----

def test_depth1_implies_zero_depth2_work():
    """search_depth == 1 -> all depth2 and turn2 counters must be zero."""
    row = _minimal_v4_row()
    row["search_depth"] = 1
    row["depth2_candidates_selected"] = 1  # violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_depth1_implies_zero_turn2():
    row = _minimal_v4_row()
    row["search_depth"] = 1
    row["turn2_accuracy_leaf_count"] = 5  # violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_depth2_frontier_bounded_by_eligible():
    row = _minimal_v4_row()
    row["search_depth"] = 2
    row["depth2_candidates_selected"] = 2
    row["depth2_response_slots_eligible"] = 3
    row["depth2_frontier"] = 4  # > eligible = violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_accuracy_off_implies_zero_leaf_counts():
    row = _minimal_v4_row()
    row["accuracy_mode"] = False
    row["turn1_accuracy_leaf_count"] = 5  # violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_cap_hit_fallback_consistency():
    row = _minimal_v4_row()
    row["turn1_accuracy_cap_hits"] = 2
    row["turn1_accuracy_cap_fallback"] = False  # violation: hits > 0 but fallback False
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_cap_fallback_without_hits():
    row = _minimal_v4_row()
    row["turn1_accuracy_cap_hits"] = 0
    row["turn1_accuracy_cap_fallback"] = True  # violation: no hits but fallback True
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_search_depth_enum():
    """search_depth must be exactly 1 or 2."""
    row = _minimal_v4_row()
    row["search_depth"] = 3
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_accuracy_mode_strict_bool():
    """accuracy_mode must be strict bool, not int."""
    row = _minimal_v4_row()
    row["accuracy_mode"] = 1  # int, not bool
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_counters_reject_bool():
    """Int counters must reject booleans (isinstance(True, int) is True in Python)."""
    row = _minimal_v4_row()
    row["turn1_accuracy_leaf_count"] = True  # bool, not int
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_counters_reject_negative():
    row = _minimal_v4_row()
    row["turn1_accuracy_leaf_count"] = -1
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_depth2_topn_must_be_positive():
    """search_depth==2 requires search_topn_requested >= 1."""
    row = _minimal_v4_row()
    row["search_depth"] = 2
    row["search_topn_requested"] = 0
    row["search_topm_requested"] = 2
    row["depth2_candidates_selected"] = 0
    row["depth2_response_slots_eligible"] = 0
    row["depth2_frontier"] = 0
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_depth2_topm_must_be_positive():
    """search_depth==2 requires search_topm_requested >= 1."""
    row = _minimal_v4_row()
    row["search_depth"] = 2
    row["search_topn_requested"] = 2
    row["search_topm_requested"] = 0
    row["depth2_candidates_selected"] = 0
    row["depth2_response_slots_eligible"] = 0
    row["depth2_frontier"] = 0
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_accuracy_branch_cap_must_be_positive():
    """accuracy_branch_cap must be >= 1 (resolver always returns >= 1)."""
    row = _minimal_v4_row()
    row["accuracy_branch_cap"] = 0
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_fallback_reason_must_be_none_or_str():
    """fallback_reason rejects non-string objects."""
    row = _minimal_v4_row()
    row["fallback_reason"] = {"key": "value"}
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_ok_outcome_rejects_fallback_stage():
    """outcome='ok' with a fallback selection_stage is inconsistent."""
    row = _minimal_v4_row()
    row["outcome"] = "ok"
    row["selection_stage"] = "max_damage_fallback"
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_fallback_outcome_rejects_ok_stage():
    """outcome='fallback' with selection_stage='heuristic' is inconsistent."""
    row = _minimal_v4_row()
    row["outcome"] = "fallback"
    row["measured_ms"] = None
    row["selection_stage"] = "heuristic"
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_v4_foe_mega_slots_validated():
    """v4 rows must also pass the v3 foe_mega_slots validation."""
    row = _minimal_v4_row()
    row["foe_mega_slots"] = ["x"]
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


# ---- backward compatibility: v1/v2/v3 rows still validate ----

def test_v1_row_still_validates():
    """A valid v1 row must not be broken by v4 additions."""
    from showdown_bot.eval.decision_profile import PROFILE_ROW_FIELDS_V1  # noqa: F811
    row = {f: None for f in PROFILE_ROW_FIELDS_V1}
    row["schema_version"] = SCHEMA_VERSION_V1
    validate_profile_row_fields(row)  # should not raise


def test_v3_row_still_validates():
    """A valid v3 row must not be broken by v4 additions."""
    from showdown_bot.eval.decision_profile import PROFILE_ROW_FIELDS_LIVE  # noqa: F811
    row = {f: None for f in PROFILE_ROW_FIELDS_LIVE}
    row["schema_version"] = SCHEMA_VERSION_LIVE
    validate_profile_row_fields(row)  # should not raise


# ---- §7: build_live_profile_row v4 integration ----

def test_build_live_profile_row_v4():
    """build_live_profile_row with readiness produces a valid v4 row."""
    from showdown_bot.eval.decision_profile import build_live_profile_row, SCHEMA_VERSION_V4
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    sink = Depth2ReadinessCounts()
    sink.search_depth = 1
    sink.search_topn_requested = 2
    sink.search_topm_requested = 2
    sink.accuracy_mode = True
    sink.accuracy_branch_cap = 6
    sink.add_turn1_accuracy(leaf_count=10, cap_hits=0)

    counters_before = {
        "damage_batch_calls": 0, "planned_damage_batches": 0, "implicit_damage_batches": 0,
        "stats_batch_calls": 0, "types_batch_calls": 0, "mixed_batch_calls": 0,
        "transport_attempts": 0, "requests_total": 0, "requests_unique": 0,
        "cache_hits": 0, "spawn_count": 0,
    }
    counters_after = {
        "damage_batch_calls": 5, "planned_damage_batches": 3, "implicit_damage_batches": 2,
        "stats_batch_calls": 1, "types_batch_calls": 0, "mixed_batch_calls": 0,
        "transport_attempts": 6, "requests_total": 20, "requests_unique": 15,
        "cache_hits": 5, "spawn_count": 0,
    }
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    shape = MegaShapeCounts(n_candidates=6, n_responses=5)

    row = build_live_profile_row(
        battle_id="b1", decision_index=0, schedule_hash="sh",
        config_id="c", format_id="f", git_sha="g", config_hash="h",
        calc_backend="persistent", outcome="ok", latency_ms=100.0,
        counters_before=counters_before, counters_after=counters_after,
        shape=shape,
        readiness=sink,
        selection_stage="heuristic",
        fallback_reason=None,
    )

    assert row["schema_version"] == SCHEMA_VERSION_V4
    assert row["search_depth"] == 1
    assert row["accuracy_mode"] is True
    assert row["turn1_accuracy_leaf_count"] == 10
    assert row["selection_stage"] == "heuristic"
    assert row["fallback_reason"] is None
    validate_profile_row_fields(row)
    validate_decision_profile_row(row, manifest=None)


def test_build_live_profile_row_no_readiness_stays_v3():
    """Without readiness, build_live_profile_row produces v3 as before."""
    from showdown_bot.eval.decision_profile import build_live_profile_row, SCHEMA_VERSION_LIVE

    counters_before = {
        "damage_batch_calls": 0, "planned_damage_batches": 0, "implicit_damage_batches": 0,
        "stats_batch_calls": 0, "types_batch_calls": 0, "mixed_batch_calls": 0,
        "transport_attempts": 0, "requests_total": 0, "requests_unique": 0,
        "cache_hits": 0, "spawn_count": 0,
    }
    counters_after = dict(counters_before)
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    shape = MegaShapeCounts(n_candidates=2, n_responses=3)

    row = build_live_profile_row(
        battle_id="b1", decision_index=0, schedule_hash="sh",
        config_id="c", format_id="f", git_sha="g", config_hash="h",
        calc_backend="persistent", outcome="ok", latency_ms=50.0,
        counters_before=counters_before, counters_after=counters_after,
        shape=shape,
    )
    assert row["schema_version"] == SCHEMA_VERSION_LIVE

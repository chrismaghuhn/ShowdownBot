"""The central live decision-profile row DTO (I8-D, §2.4/§2.6): built by a NAMED function,
never a 41-field dict inline in gauntlet.py. Counters are per-decision before/after deltas of
the client's cumulative calc counters; live identity is set and microprofile identity is null.
"""
from __future__ import annotations

import pytest

from showdown_bot.battle.mega_scoring import MegaShapeCounts
from showdown_bot.eval.decision_profile import (
    PROFILE_ROW_FIELDS,
    build_live_profile_row,
    snapshot_calc_counters,
    validate_decision_profile_row,
    validate_profile_row_fields,
)


class _FakeBackend:
    def __init__(self, **kw):
        self.stats_batch_calls = kw.get("stats", 0)
        self.types_batch_calls = kw.get("types", 0)
        self.mixed_batch_calls = kw.get("mixed", 0)
        self.transport_attempts = kw.get("attempts", 0)
        self.spawn_count = kw.get("spawn", 0)


class _FakeOracle:
    def __init__(self, backend, **kw):
        self.backend = backend
        self.batch_calls = kw.get("dmg", 0)
        self.planned_damage_batches = kw.get("planned", 0)
        self.implicit_damage_batches = kw.get("implicit", 0)
        self.requests_total = kw.get("reqT", 0)
        self.requests_unique = kw.get("reqU", 0)
        self.cache_hits = kw.get("chits", 0)


def _row(**over):
    kw = dict(
        battle_id="b1", decision_index=3, schedule_hash="sched01", config_id="heuristic",
        format_id="gen9championsvgc2026regma", git_sha="deadbeef", config_hash="cfg01",
        calc_backend="persistent", outcome="ok", latency_ms=12.5,
        counters_before={"damage_batch_calls": 0, "planned_damage_batches": 0,
                         "implicit_damage_batches": 0, "stats_batch_calls": 0,
                         "types_batch_calls": 0, "mixed_batch_calls": 0,
                         "transport_attempts": 0, "spawn_count": 0,
                         "requests_total": 0, "requests_unique": 0, "cache_hits": 0},
        counters_after={"damage_batch_calls": 1, "planned_damage_batches": 1,
                        "implicit_damage_batches": 0, "stats_batch_calls": 16,
                        "types_batch_calls": 2, "mixed_batch_calls": 0,
                        "transport_attempts": 19, "spawn_count": 1,
                        "requests_total": 140, "requests_unique": 9, "cache_hits": 80},
        shape=_shape(twins=24),
    )
    kw.update(over)
    return build_live_profile_row(**kw)


def _shape(**kw):
    s = MegaShapeCounts()
    s.n_candidates = kw.get("cand", 8)
    s.n_responses = kw.get("resp", 48)
    s.n_mega_twins = kw.get("twins", 24)
    s.n_branches = kw.get("br", 3)
    s.n_worlds = kw.get("wld", 1)
    s.depth2_frontier = kw.get("d2f", 0)
    return s


def test_snapshot_reads_the_client_owned_calc_counters():
    b = _FakeBackend(stats=5, types=1, attempts=6, spawn=1)
    o = _FakeOracle(b, dmg=1, planned=1, implicit=0, reqT=72, reqU=3, chits=48)
    snap = snapshot_calc_counters(o, b)
    assert snap == {"damage_batch_calls": 1, "planned_damage_batches": 1,
                    "implicit_damage_batches": 0, "stats_batch_calls": 5, "types_batch_calls": 1,
                    "mixed_batch_calls": 0,
                    "transport_attempts": 6, "spawn_count": 1, "requests_total": 72,
                    "requests_unique": 3, "cache_hits": 48}


def test_a_live_row_has_the_exact_field_set_and_validates():
    row = _row()
    validate_profile_row_fields(row)                    # exact-closed 41 fields
    validate_decision_profile_row(row, manifest=None)   # live rows validate with no manifest
    assert set(row) == set(PROFILE_ROW_FIELDS)


def test_live_identity_is_set_and_microprofile_identity_is_null():
    row = _row()
    assert row["source"] == "live"
    assert row["timer_scope"] == "agent_choose"
    assert (row["battle_id"], row["decision_index"], row["schedule_hash"]) == ("b1", 3, "sched01")
    for f in ("arm_id", "rep", "profile_manifest_hash", "cache_class",
              "damage_cache_size_at_rep_start", "speed_cache_size_at_rep_start",
              "dex_cache_size_at_rep_start"):
        assert row[f] is None, f


def test_ok_has_finite_measured_ms():
    row = _row(outcome="ok", latency_ms=9.75)
    assert row["measured_ms"] == 9.75
    assert row["outcome"] == "ok"


@pytest.mark.parametrize("outcome", ["crash", "fallback", "degraded_state"])
def test_non_ok_has_null_measured_ms_but_keeps_real_counter_deltas(outcome):
    row = _row(outcome=outcome, latency_ms=4000.0)
    assert row["measured_ms"] is None
    # counters are the real deltas regardless of outcome
    assert row["damage_batch_calls"] == 1
    assert row["transport_attempts"] == 19
    assert row["spawn_calls"] == 1


def test_counters_are_after_minus_before_deltas():
    row = _row()
    assert row["damage_batch_calls"] == 1        # 1 - 0
    assert row["stats_batch_calls"] == 16
    assert row["types_batch_calls"] == 2
    assert row["transport_attempts"] == 19
    assert row["transport_calls"] == 1 + 16 + 2  # dmg+stats+types deltas
    assert row["spawn_calls"] == 1               # spawn_count after - before
    assert row["spawn_count_before"] == 0
    assert row["requests_total"] == 140 and row["requests_unique"] == 9 and row["cache_hits"] == 80


def test_shape_comes_from_the_sink_and_drives_foe_mega_active():
    active = _row(shape=_shape(twins=24))
    assert active["n_mega_twins"] == 24 and active["foe_mega_active"] is True
    inactive = _row(shape=_shape(twins=0))
    assert inactive["n_mega_twins"] == 0 and inactive["foe_mega_active"] is False


def test_no_shape_means_zero_workset_and_inactive():
    row = _row(shape=None)
    for f in ("n_candidates", "n_responses", "n_mega_twins", "n_branches", "n_worlds",
              "depth2_frontier"):
        assert row[f] == 0, f
    assert row["foe_mega_active"] is False


def test_backend_class_is_computed_not_supplied():
    import inspect
    assert "backend_class" not in inspect.signature(build_live_profile_row).parameters
    row = _row()
    assert row["backend_class"] in ("clean_cold", "clean_warm", "contaminated", "oneshot")

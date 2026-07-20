"""Task 1: live-only decision-profile **v3** (foe_mega_slots + foe_mega_order_tie).

v3 adds EXACTLY two fields, stamped ONLY by the live builder. The microprofile writer keeps
``decision-profile-v2`` and its exact field set. Value invariants: slots are a sorted-unique int
subset of {0,1}; a recorded slot implies ``n_mega_twins > 0``; ``foe_mega_order_tie`` implies
``n_mega_twins > 0`` AND a recorded slot. v1/v2 back-compat: the frozen live (v2) and microprofile
tiers keep validating byte-for-byte; a mixed v2/v3 file is rejected.

v3 driver tests fail before the migration (the live builder still emits v2 / the two fields are
unknown); the frozen-tier back-compat tests are regression guards that must stay green across it.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from showdown_bot.eval.decision_profile import (
    SCHEMA_VERSION,  # the microprofile / default stamp -- must stay v2
    DecisionProfileError,
    build_live_profile_row,
    validate_decision_profile_dataset,
    validate_decision_profile_row,
    validate_live_profile_dataset,
    validate_profile_row_fields,
)

_V3 = "decision-profile-v3"  # a literal, so this file still COLLECTS before SCHEMA_VERSION_LIVE exists
ROOT = Path(__file__).resolve().parents[2]  # tests/ -> showdown_bot/ -> repo root
_DATA = ROOT / "data" / "eval" / "champions-panel-v0"

_CTR_KEYS = (
    "damage_batch_calls", "planned_damage_batches", "implicit_damage_batches",
    "stats_batch_calls", "types_batch_calls", "mixed_batch_calls",
    "requests_total", "requests_unique", "cache_hits", "transport_attempts", "spawn_count",
)


def _before() -> dict:
    return {k: 0 for k in _CTR_KEYS}


def _after() -> dict:
    # transport_calls = damage+stats+types+mixed = 1+1+1+0 = 3; oneshot: attempts==spawn==calls.
    return {
        "damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
        "stats_batch_calls": 1, "types_batch_calls": 1, "mixed_batch_calls": 0,
        "requests_total": 4, "requests_unique": 4, "cache_hits": 0,
        "transport_attempts": 3, "spawn_count": 3,
    }


def _shape(*, twins=2, slots=(0,), tie=False, cand=12, resp=3, br=2, wld=1, d2f=0):
    # Before GREEN the live builder ignores foe_mega_slots/foe_mega_order_tie (SimpleNamespace lets
    # us attach them regardless); after GREEN it reads them onto the v3 row.
    return SimpleNamespace(
        n_candidates=cand, n_responses=resp, n_mega_twins=twins, n_branches=br,
        n_worlds=wld, depth2_frontier=d2f, foe_mega_slots=slots, foe_mega_order_tie=tie,
    )


def _live(**shape_kw) -> dict:
    return build_live_profile_row(
        battle_id="b0", decision_index=4, schedule_hash="aabbccdd11223344",
        config_id="cfg", format_id="gen9championsvgc2026regma", git_sha="deadbeef",
        config_hash="0" * 16, calc_backend="oneshot", outcome="ok", latency_ms=123.0,
        counters_before=_before(), counters_after=_after(), shape=_shape(**shape_kw),
    )


def _v3_dict(**over) -> dict:
    """A fully-formed v3 row dict: the v2 live base + schema_version v3 + the two new fields.

    Before GREEN this is REJECTED (v3 unknown -> the two fields are 'unknown'); after GREEN it
    validates. Each invariant test asserts the GOOD dict validates FIRST (so it fails RED), then
    that a specific violation raises."""
    d = dict(_live())
    d["schema_version"] = _V3
    d["foe_mega_slots"] = list(over.pop("foe_mega_slots", [0]))
    d["foe_mega_order_tie"] = over.pop("foe_mega_order_tie", False)
    d.update(over)
    return d


def _frozen_row(sub: str) -> dict:
    return json.loads((_DATA / sub / "profile.jsonl").read_text("utf-8").splitlines()[0])


def _micro_manifest() -> dict:
    return json.loads((_DATA / "i8-microprofile" / "profile_manifest.json").read_text("utf-8"))


# ---- v3 driver tests (fail before the migration) -------------------------------------------

def test_a_v3_live_row_has_the_two_new_fields_and_validates():
    row = _live(twins=2, slots=(0,), tie=False)
    assert row["schema_version"] == _V3
    assert row["foe_mega_slots"] == [0]
    assert row["foe_mega_order_tie"] is False
    validate_profile_row_fields(row)               # exact-closed v3 field set
    validate_decision_profile_row(row, manifest=None)


def test_the_microprofile_writer_stays_v2_and_omits_the_v3_fields():
    from showdown_bot.eval import profile_harness
    assert profile_harness.SCHEMA_VERSION == SCHEMA_VERSION == "decision-profile-v2"
    assert SCHEMA_VERSION != _V3
    micro = _frozen_row("i8-microprofile")  # a real microprofile row (v1)
    validate_decision_profile_row(micro, manifest=_micro_manifest())
    assert "foe_mega_slots" not in micro and "foe_mega_order_tie" not in micro


def test_a_v2_row_still_validates_and_rejects_a_v3_field():
    row = _frozen_row("i8d-live-post-lever-b")  # a real v2 live row (42 fields)
    assert row["schema_version"] == "decision-profile-v2"
    validate_decision_profile_row(row, manifest=None)
    bad = dict(row, foe_mega_slots=[0])
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(bad, manifest=None)


def test_a_v1_row_still_validates_unchanged():
    row = _frozen_row("i8d-live")  # a real v1 live row (41 fields)
    assert row["schema_version"] == "decision-profile-v1"
    validate_decision_profile_row(row, manifest=None)


def test_v3_fields_are_absent_not_null_on_pre_v3_rows():
    for sub in ("i8d-live", "i8d-live-post-lever-b"):
        row = _frozen_row(sub)
        assert "foe_mega_slots" not in row and "foe_mega_order_tie" not in row


def test_slots_must_be_a_sorted_unique_int_subset_of_0_1():
    good = _v3_dict(foe_mega_slots=[0, 1], n_mega_twins=2)
    validate_decision_profile_row(good, manifest=None)  # valid -> no raise (FAILS RED)
    for bad_slots in ([2], [1, 0], [0, 0], "x"):
        bad = dict(good, foe_mega_slots=bad_slots)
        with pytest.raises(DecisionProfileError):
            validate_decision_profile_row(bad, manifest=None)


def test_a_recorded_slot_implies_n_mega_twins_positive():
    good = _v3_dict(foe_mega_slots=[0])  # twins=2 from the live base
    validate_decision_profile_row(good, manifest=None)  # valid -> no raise (FAILS RED)
    bad = dict(good, n_mega_twins=0, foe_mega_active=False)  # slot present but no twin
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(bad, manifest=None)


def test_order_tie_true_implies_twins_positive_and_a_recorded_foe_slot():
    good = _v3_dict(foe_mega_slots=[0], foe_mega_order_tie=True)  # tie, twins=2, slot present
    validate_decision_profile_row(good, manifest=None)  # valid -> no raise (FAILS RED)
    bad_no_twins = dict(good, n_mega_twins=0, foe_mega_active=False, foe_mega_slots=[])
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(bad_no_twins, manifest=None)
    bad_no_slot = dict(good, foe_mega_slots=[])  # tie True, twins>0, but no recorded slot
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(bad_no_slot, manifest=None)


# ---- frozen-tier back-compat (regression guards; green from the start, must stay green) ------

def test_the_frozen_v2_live_dataset_still_validates():
    report = validate_live_profile_dataset(
        (_DATA / "i8d-live-post-lever-b" / "profile.jsonl").as_posix()
    )
    assert report["rows"] > 0


def test_the_frozen_microprofile_dataset_still_validates():
    report = validate_decision_profile_dataset(
        (_DATA / "i8-microprofile" / "profile.jsonl").as_posix(),
        manifest=_micro_manifest(),
    )
    assert report["rows"] == 450

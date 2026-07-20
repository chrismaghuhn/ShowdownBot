"""Lever B, T2: decision-profile v1->v2 schema migration (mixed_batch_calls).

The writer now emits ``decision-profile-v2`` with a ``mixed_batch_calls`` counter folded into
``transport_calls``. The validators must accept BOTH the new v2 rows and the frozen v1 evidence
(back-compat), so three frozen datasets (two live, one microprofile) keep validating byte-for-byte.

v2 driver tests fail before the migration (the closed v1 schema rejects the field / the writer
emits v1); the v1 back-compat tests are regression guards that must stay green across it.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    build_live_profile_row,
    validate_decision_profile_dataset,
    validate_decision_profile_row,
    validate_live_profile_dataset,
)

_DATA = Path(__file__).resolve().parents[3] / "data" / "eval" / "champions-panel-v0"

_CTR_KEYS = (
    "damage_batch_calls", "planned_damage_batches", "implicit_damage_batches",
    "stats_batch_calls", "types_batch_calls", "mixed_batch_calls",
    "requests_total", "requests_unique", "cache_hits", "transport_attempts", "spawn_count",
)


def _before() -> dict:
    return {k: 0 for k in _CTR_KEYS}


def _after(mixed: int = 2) -> dict:
    # transport_calls (v2) = damage + stats + types + mixed = 3 + mixed; a oneshot row keeps
    # spawn_count == transport_attempts == transport_calls (no retry).
    n = 3 + mixed
    return {
        "damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
        "stats_batch_calls": 1, "types_batch_calls": 1, "mixed_batch_calls": mixed,
        "requests_total": 4, "requests_unique": 4, "cache_hits": 0,
        "transport_attempts": n, "spawn_count": n,
    }


def _build_live(mixed: int = 2) -> dict:
    shape = SimpleNamespace(
        n_candidates=12, n_responses=3, n_mega_twins=2, n_branches=2, n_worlds=1, depth2_frontier=0,
        foe_mega_slots=(0,), foe_mega_order_tie=False,  # Task 1: stand-in mirrors MegaShapeCounts
    )
    return build_live_profile_row(
        battle_id="b0", decision_index=4, schedule_hash="aabbccdd11223344",
        config_id="cfg", format_id="gen9championsvgc2026regma", git_sha="deadbeef",
        config_hash="0" * 16, calc_backend="oneshot", outcome="ok", latency_ms=123.0,
        counters_before=_before(), counters_after=_after(mixed), shape=shape,
    )


# ---- v2 driver tests (fail before the migration) -------------------------------------------

def test_v2_live_row_validates():
    row = _build_live()
    validate_decision_profile_row(row, manifest=None)
    # Task 1: the live builder now stamps decision-profile-v3; mixed_batch_calls + the transport
    # relation (Lever B, v2) carry into v3 unchanged, which is what this test still guards.
    assert row["schema_version"] == "decision-profile-v3"
    assert row.get("mixed_batch_calls") == 2
    assert row["transport_calls"] == (
        row["damage_batch_calls"] + row["stats_batch_calls"]
        + row["types_batch_calls"] + row["mixed_batch_calls"]
    )


def test_oneshot_spawn_and_transport_relation():
    row = _build_live()
    assert row["calc_backend"] == "oneshot"
    assert row.get("mixed_batch_calls") == 2               # v2 carries the mixed counter
    assert row["spawn_calls"] == row["transport_attempts"]  # oneshot: one spawn per attempt
    assert row["transport_attempts"] >= row["transport_calls"]
    assert row["transport_calls"] == (
        row["damage_batch_calls"] + row["stats_batch_calls"]
        + row["types_batch_calls"] + row["mixed_batch_calls"]
    )


def test_v2_microprofile_row_validates():
    manifest = json.loads((_DATA / "i8-microprofile" / "profile_manifest.json").read_text("utf-8"))
    v1_row = json.loads(
        (_DATA / "i8-microprofile" / "profile.jsonl").read_text("utf-8").splitlines()[0]
    )
    row = dict(v1_row)
    row["schema_version"] = "decision-profile-v2"
    row["mixed_batch_calls"] = 0                            # mixed=0 keeps transport_calls consistent
    validate_decision_profile_row(row, manifest=manifest)
    assert row["schema_version"] == "decision-profile-v2" and "mixed_batch_calls" in row


# ---- v1 back-compat guards (must stay green across the migration) ---------------------------

def test_v1_live_frozen_still_validate():
    for sub in ("i8d-live", "i8d-live-post-lever-a"):
        report = validate_live_profile_dataset(str(_DATA / sub / "profile.jsonl"))
        assert report["rows"] == 679
        assert report["active_valid_rows"] == 60
        assert report["distinct_active_battle_ids"] == 45


def test_v1_microprofile_frozen_still_validates():
    manifest = json.loads((_DATA / "i8-microprofile" / "profile_manifest.json").read_text("utf-8"))
    report = validate_decision_profile_dataset(
        str(_DATA / "i8-microprofile" / "profile.jsonl"), manifest
    )
    assert report["rows"] == 450


# ---- one schema version per dataset (no v1/v2 pooling) --------------------------------------

def _to_v2(row: dict) -> dict:
    r = dict(row)
    r["schema_version"] = "decision-profile-v2"
    r["mixed_batch_calls"] = 0  # keeps transport_calls consistent (adds nothing)
    return r


def _live_v1_rows() -> list[dict]:
    text = (_DATA / "i8d-live-post-lever-a" / "profile.jsonl").read_text("utf-8")
    return [json.loads(line) for line in text.splitlines()[:2]]


def test_live_dataset_v2_only_validates(tmp_path):
    p = tmp_path / "v2.jsonl"
    p.write_text(json.dumps(_to_v2(_live_v1_rows()[0])) + "\n", encoding="utf-8")
    report = validate_live_profile_dataset(str(p))
    assert report["rows"] == 1


def test_live_dataset_mixed_versions_rejected(tmp_path):
    v1, other = _live_v1_rows()
    v2 = _to_v2(other)  # a DIFFERENT frozen row (distinct battle/decision), upgraded to v2
    p = tmp_path / "mixed.jsonl"
    p.write_text(json.dumps(v1) + "\n" + json.dumps(v2) + "\n", encoding="utf-8")
    with pytest.raises(DecisionProfileError, match="schema versions"):
        validate_live_profile_dataset(str(p))


def test_microprofile_dataset_mixed_versions_rejected(tmp_path):
    manifest = json.loads((_DATA / "i8-microprofile" / "profile_manifest.json").read_text("utf-8"))
    lines = (_DATA / "i8-microprofile" / "profile.jsonl").read_text("utf-8").splitlines()
    v1 = json.loads(lines[0])
    v2 = _to_v2(json.loads(lines[1]))  # distinct (arm, rep), upgraded to v2
    p = tmp_path / "mixed_micro.jsonl"
    p.write_text(json.dumps(v1) + "\n" + json.dumps(v2) + "\n", encoding="utf-8")
    with pytest.raises(DecisionProfileError, match="schema versions"):
        validate_decision_profile_dataset(str(p), manifest)


def test_live_dataset_mixed_version_types_rejected(tmp_path):
    """A str and a non-str (int) schema_version in one file must fail as a DecisionProfileError
    (the version-uniqueness rule), never a raw TypeError from sorting mixed JSON types."""
    v1, other = _live_v1_rows()
    bad = dict(other)
    bad["schema_version"] = 1  # a non-str JSON version alongside the string v1
    p = tmp_path / "mixed_types.jsonl"
    p.write_text(json.dumps(v1) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(DecisionProfileError, match="schema versions"):
        validate_live_profile_dataset(str(p))


def test_microprofile_dataset_mixed_version_types_rejected(tmp_path):
    manifest = json.loads((_DATA / "i8-microprofile" / "profile_manifest.json").read_text("utf-8"))
    lines = (_DATA / "i8-microprofile" / "profile.jsonl").read_text("utf-8").splitlines()
    v1 = json.loads(lines[0])
    bad = json.loads(lines[1])
    bad["schema_version"] = 1
    p = tmp_path / "mixed_types_micro.jsonl"
    p.write_text(json.dumps(v1) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(DecisionProfileError, match="schema versions"):
        validate_decision_profile_dataset(str(p), manifest)


# ---- v2 <-> v3 pooling is rejected (Task 1: live-only v3 migration) -------------------------

def _to_v3(row: dict) -> dict:
    r = _to_v2(row)
    r["schema_version"] = "decision-profile-v3"
    r["foe_mega_slots"] = []       # empty slots + no tie -> the v3 invariants are vacuous (always valid)
    r["foe_mega_order_tie"] = False
    return r


def test_a_dataset_mixing_v2_and_v3_is_rejected(tmp_path):
    a, b = _live_v1_rows()
    p = tmp_path / "mixed_v2_v3.jsonl"
    p.write_text(json.dumps(_to_v2(a)) + "\n" + json.dumps(_to_v3(b)) + "\n", encoding="utf-8")
    with pytest.raises(DecisionProfileError, match="schema versions"):
        validate_live_profile_dataset(str(p))

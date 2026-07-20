"""I8-D §3: the LIVE decision-profile DATASET validator.

The mirror of ``validate_decision_profile_dataset`` for a live sidecar (which carries NO
manifest -- a live row has no arm/rep/manifest). On top of the full per-row contract it adds the
two dataset-level invariants a single row cannot express: every row is ``source == "live"`` and
``(battle_id, decision_index)`` is unique. The closed field schema is what keeps any
winner/result/strength/local-path field out -- an unknown key fails the row. Emptiness is a
valid outcome (the exposure floor classifies it INCONCLUSIVE in §4), never corruption.

It also surfaces the ACTIVE verdict population -- ``source==live`` AND
``timer_scope==agent_choose`` AND ``outcome==ok`` AND ``foe_mega_active`` -- so the runner and
any auditor read ONE definition, via the shared ``is_active_valid_live_row`` predicate.

No server/battles: rows are minted via ``build_live_profile_row`` and written with the real
LF-stable ``DecisionProfileWriter``; tamper cases are hand-written to model the untrusted
on-disk file the validator exists to defend against.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.battle.mega_scoring import MegaShapeCounts
from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    DecisionProfileWriter,
    build_live_profile_row,
    is_active_valid_live_row,
    validate_live_profile_dataset,
)

_BEFORE = {"damage_batch_calls": 0, "planned_damage_batches": 0, "implicit_damage_batches": 0,
           "stats_batch_calls": 0, "types_batch_calls": 0, "mixed_batch_calls": 0,
           "transport_attempts": 0,
           "spawn_count": 0, "requests_total": 0, "requests_unique": 0, "cache_hits": 0}
_AFTER = {"damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
          "stats_batch_calls": 16, "types_batch_calls": 2, "mixed_batch_calls": 0,
          "transport_attempts": 19,
          "spawn_count": 1, "requests_total": 140, "requests_unique": 9, "cache_hits": 80}


def _shape(twins):
    s = MegaShapeCounts()
    s.n_candidates = 8
    s.n_responses = 48
    s.n_mega_twins = twins
    s.n_branches = 3
    s.n_worlds = 1
    s.depth2_frontier = 0
    return s


def _row(*, battle_id="b1", decision_index=0, outcome="ok", twins=24, latency_ms=12.5):
    return build_live_profile_row(
        battle_id=battle_id, decision_index=decision_index, schedule_hash="sched01",
        config_id="heuristic", format_id="gen9championsvgc2026regma", git_sha="deadbeef",
        config_hash="cfg01", calc_backend="persistent", outcome=outcome, latency_ms=latency_ms,
        counters_before=dict(_BEFORE), counters_after=dict(_AFTER), shape=_shape(twins))


def _write(tmp_path, rows, name="live.jsonl"):
    w = DecisionProfileWriter(str(tmp_path / name), manifest=None)
    for r in rows:
        w.write(r)
    return w.path


def _write_raw(tmp_path, rows, name="raw.jsonl"):
    """Bypass the writer's per-row validation -- a file on disk is not a trusted writer
    (it may have been hand-edited, truncated or concatenated since it was written)."""
    p = tmp_path / name
    with open(p, "w", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return str(p)


def test_valid_live_dataset_passes_and_reports_active_population(tmp_path):
    path = _write(tmp_path, [
        _row(battle_id="b1", decision_index=0, outcome="ok", twins=24),      # active
        _row(battle_id="b2", decision_index=0, outcome="ok", twins=24),      # active, distinct battle
        _row(battle_id="b2", decision_index=1, outcome="ok", twins=0),       # ok but no foe mega -> not active
        _row(battle_id="b1", decision_index=1, outcome="fallback", twins=24),  # not ok -> not active
    ])
    report = validate_live_profile_dataset(path)
    assert report == {"rows": 4, "active_valid_rows": 2, "distinct_active_battle_ids": 2}


def test_the_live_dataset_validator_accepts_a_v3_dataset(tmp_path):
    # Task 3: build_live_profile_row now stamps decision-profile-v3; a dataset of v3 rows (carrying
    # the two foe-Mega coverage fields) validates and reports its active population.
    s = _shape(24)
    s.foe_mega_slots = (0, 1)
    s.foe_mega_order_tie = True
    row = build_live_profile_row(
        battle_id="bx", decision_index=0, schedule_hash="sched01", config_id="heuristic",
        format_id="gen9championsvgc2026regma", git_sha="deadbeef", config_hash="cfg01",
        calc_backend="persistent", outcome="ok", latency_ms=12.5,
        counters_before=dict(_BEFORE), counters_after=dict(_AFTER), shape=s)
    assert row["schema_version"] == "decision-profile-v3"
    assert row["foe_mega_slots"] == [0, 1] and row["foe_mega_order_tie"] is True
    report = validate_live_profile_dataset(_write(tmp_path, [row]))
    assert report == {"rows": 1, "active_valid_rows": 1, "distinct_active_battle_ids": 1}


def test_distinct_active_battle_ids_dedups_within_a_battle(tmp_path):
    path = _write(tmp_path, [
        _row(battle_id="b1", decision_index=0, outcome="ok", twins=24),
        _row(battle_id="b1", decision_index=1, outcome="ok", twins=24),  # same battle, two active decisions
    ])
    report = validate_live_profile_dataset(path)
    assert report["active_valid_rows"] == 2
    assert report["distinct_active_battle_ids"] == 1


def test_empty_dataset_is_valid_not_corruption(tmp_path):
    # Unlike the microprofile tier, an empty live dataset is a real "0 scored decisions"
    # outcome (INCONCLUSIVE at the exposure floor), not a rejected run.
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    report = validate_live_profile_dataset(str(p))
    assert report == {"rows": 0, "active_valid_rows": 0, "distinct_active_battle_ids": 0}


def test_duplicate_battle_id_decision_index_is_rejected(tmp_path):
    # Per-row validation passes for each (duplicates are fine at the row tier), so both get
    # written; the DATASET tier is the only place this is caught.
    path = _write(tmp_path, [
        _row(battle_id="b1", decision_index=0),
        _row(battle_id="b1", decision_index=0),
    ])
    with pytest.raises(DecisionProfileError, match=r"duplicate \(battle_id, decision_index\)"):
        validate_live_profile_dataset(path)


def test_a_microprofile_row_in_a_live_dataset_is_rejected(tmp_path):
    # All 41 fields still present (only `source` flipped), so the closed-schema check passes
    # and the live-boundary check is what fires -- the mirror of the microprofile tier's own
    # source guard, one boundary in the other direction.
    good = _row(battle_id="b1", decision_index=0)
    bad = dict(good)
    bad["source"] = "microprofile"
    path = _write_raw(tmp_path, [good, bad])
    with pytest.raises(DecisionProfileError, match="may not contain a 'microprofile' row"):
        validate_live_profile_dataset(path)


def test_an_unknown_field_fails_the_closed_schema(tmp_path):
    # A result/strength-shaped field the live schema must never carry.
    bad = dict(_row(battle_id="b1", decision_index=0))
    bad["winner"] = "hero"
    path = _write_raw(tmp_path, [bad])
    with pytest.raises(DecisionProfileError, match=r"unknown=\['winner'\]"):
        validate_live_profile_dataset(path)


def test_a_hand_edited_row_still_fails_per_row_semantics(tmp_path):
    # ok with a null measured_ms violates the §2.6 equivalence: the dataset tier re-runs the
    # FULL per-row contract, so tampering after write is caught.
    bad = dict(_row(battle_id="b1", decision_index=0, outcome="ok", latency_ms=10.0))
    bad["measured_ms"] = None
    path = _write_raw(tmp_path, [bad])
    with pytest.raises(DecisionProfileError, match="outcome == 'ok' must be equivalent"):
        validate_live_profile_dataset(path)


def test_row_index_is_named_in_the_error(tmp_path):
    good = _row(battle_id="b1", decision_index=0)
    bad = dict(_row(battle_id="b2", decision_index=0))
    bad["source"] = "microprofile"
    path = _write_raw(tmp_path, [good, bad])   # the bad row is row 1
    with pytest.raises(DecisionProfileError, match="row 1:"):
        validate_live_profile_dataset(path)


@pytest.mark.parametrize("outcome,twins,expected", [
    ("ok", 24, True),
    ("ok", 0, False),             # ok, but no foe Mega was active on the board
    ("fallback", 24, False),      # a real foe Mega, but the decision was not scored to completion
    ("crash", 24, False),
    ("degraded_state", 24, False),
])
def test_is_active_valid_live_row_predicate(outcome, twins, expected):
    assert is_active_valid_live_row(_row(outcome=outcome, twins=twins)) is expected


def test_dataset_written_for_validation_is_lf_stable(tmp_path):
    path = _write(tmp_path, [_row(battle_id="b1", decision_index=0),
                             _row(battle_id="b1", decision_index=1)])
    raw = open(path, "rb").read()
    assert b"\r" not in raw and raw.endswith(b"\n")
    validate_live_profile_dataset(path)   # and it still validates

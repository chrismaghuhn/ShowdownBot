"""T2 per-battle result JSONL: frozen row schema + validate-on-write + append-only.

Required fields fail fast if missing/None; winner must be a role (hero/villain/tie), not
a suffixed bot name. config_id (bot version) is distinct from format_id; config_hash is
required.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval.result_jsonl import (
    NULLABLE_FIELDS,
    REQUIRED_FIELDS,
    BattleResultWriter,
    ResultRowError,
    make_battle_id,
    validate_battle_row,
)


def _row(**over):
    row = {
        "battle_id": "abc", "run_id": "run16hex", "config_id": "heuristic",
        "format_id": "gen9vgc2025regi", "config_hash": "cfg123", "schedule_hash": "h",
        "seed_index": 0, "opp_policy": "heuristic", "hero_team_path": "teams/fixed_team.txt",
        "opp_team_path": "teams/opp_variant_a.txt", "seed": "sodium,00", "seed_base": "run2026",
        "winner": "hero", "end_reason": "normal",
        "turns": 13, "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 200,
        "git_sha": "deadbeef", "dirty": False, "end_hp_diff": None, "timeouts": None,
        "room_raw_path": None, "panel_hash": None,
    }
    row.update(over)
    return row


def test_valid_row_passes():
    validate_battle_row(_row())  # no raise


@pytest.mark.parametrize("missing", sorted(REQUIRED_FIELDS))
def test_missing_required_field_fails_fast(missing):
    row = _row()
    del row[missing]
    with pytest.raises(ResultRowError):
        validate_battle_row(row)


def test_none_required_field_fails_fast():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(winner=None))


def test_bad_winner_fails_fast():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(winner="HeuristicBot123"))  # must be role hero/villain/tie


def test_unknown_field_fails_fast():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(surprise=1))


def test_config_id_and_format_id_are_both_required():
    assert "config_id" in REQUIRED_FIELDS and "format_id" in REQUIRED_FIELDS
    assert "config_hash" in REQUIRED_FIELDS


def test_dirty_is_required():
    # T3e P4: provenance. `dirty` (git working-tree dirty flag) must be present.
    assert "dirty" in REQUIRED_FIELDS
    row = _row()
    del row["dirty"]
    with pytest.raises(ResultRowError):
        validate_battle_row(row)


def test_seed_base_is_required():
    # T3f Task 2: seed_base lets T5 pair on (schedule_hash, seed_base, seed_index).
    assert "seed_base" in REQUIRED_FIELDS
    validate_battle_row(_row())          # present -> ok
    row = _row()
    del row["seed_base"]
    with pytest.raises(ResultRowError):  # missing -> fail fast
        validate_battle_row(row)


def test_seed_base_is_distinct_from_seed():
    # seed_base is the raw base string; seed is the per-battle derived value — different fields.
    row = _row(seed_base="run2026", seed="sodium,deadbeef")
    validate_battle_row(row)
    assert row["seed_base"] == "run2026" and row["seed"] != row["seed_base"]


def test_run_id_is_required():
    # T3f Task 3: run_id ties every row to the run manifest.
    assert "run_id" in REQUIRED_FIELDS
    validate_battle_row(_row())          # present -> ok
    row = _row()
    del row["run_id"]
    with pytest.raises(ResultRowError):  # missing -> fail fast
        validate_battle_row(row)


def test_team_hashes_are_nullable():
    # T3e P4: hero_team_hash / opp_team_hash are provenance, nullable (legacy schedules omit them).
    assert "hero_team_hash" in NULLABLE_FIELDS and "opp_team_hash" in NULLABLE_FIELDS
    validate_battle_row(_row(hero_team_hash=None, opp_team_hash=None))       # None ok
    validate_battle_row(_row(hero_team_hash="hh16", opp_team_hash="oh16"))   # present ok


def test_panel_split_is_nullable():
    # T3f Task 4: panel_split is "dev"/"heldout" from the schedule row, null for legacy schedules.
    assert "panel_split" in NULLABLE_FIELDS
    validate_battle_row(_row(panel_split=None))       # legacy -> null ok
    validate_battle_row(_row(panel_split="dev"))      # present ok
    validate_battle_row(_row(panel_split="heldout"))


def test_normalized_room_log_sha256_is_nullable():
    # T4c R1: rows WITHOUT the field (legacy, written before it existed) load fine
    # through validate_battle_row -- the gate every row passes in report.RunBundle.load
    # (report.py's per-row loader used by report/eval). No KeyError, no ResultRowError.
    assert "normalized_room_log_sha256" in NULLABLE_FIELDS
    row = _row()
    assert "normalized_room_log_sha256" not in row
    validate_battle_row(row)  # absent (legacy row) -> ok, no KeyError
    validate_battle_row(_row(normalized_room_log_sha256=None))        # None (hash failed) -> ok
    validate_battle_row(_row(normalized_room_log_sha256="a" * 64))    # present -> ok


def test_end_reason_is_required():
    # T3f Task 5: end_reason distinguishes normal vs timeout/forfeit/crash.
    assert "end_reason" in REQUIRED_FIELDS
    validate_battle_row(_row())          # "normal" -> ok
    row = _row()
    del row["end_reason"]
    with pytest.raises(ResultRowError):  # missing -> fail fast
        validate_battle_row(row)


def test_end_reason_accepts_all_and_rejects_invalid():
    for r in ("normal", "timeout", "forfeit", "crash"):
        validate_battle_row(_row(end_reason=r))
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(end_reason="exploded"))   # not an allowed value
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(end_reason=None))         # None fails the required check


def test_make_battle_id_deterministic():
    assert make_battle_id("h", 0, "sodium,00") == make_battle_id("h", 0, "sodium,00")
    assert make_battle_id("h", 0, "sodium,00") != make_battle_id("h", 1, "sodium,00")


def test_decision_trace_binding_fields_are_nullable():
    # Task 3: decision_trace_count / decision_trace_sha256 bind a result row to its
    # sidecar trace file. Absent (capture off / legacy row) -> ok, byte-identical to today.
    assert "decision_trace_count" in NULLABLE_FIELDS
    assert "decision_trace_sha256" in NULLABLE_FIELDS
    row = _row()
    assert "decision_trace_count" not in row and "decision_trace_sha256" not in row
    validate_battle_row(row)  # absent -> ok, no KeyError


def test_decision_trace_binding_fields_present_and_valid():
    validate_battle_row(_row(decision_trace_count=3, decision_trace_sha256="a" * 64))


def test_decision_trace_binding_fields_must_be_present_together():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=3, decision_trace_sha256=None))
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=None, decision_trace_sha256="a" * 64))
    validate_battle_row(_row(decision_trace_count=None, decision_trace_sha256=None))  # both null -> ok


def test_decision_trace_count_must_be_positive_int():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=0, decision_trace_sha256="a" * 64))
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=-1, decision_trace_sha256="a" * 64))
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count="3", decision_trace_sha256="a" * 64))


def test_decision_trace_sha256_must_be_lowercase_hex():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=1, decision_trace_sha256="A" * 64))  # uppercase
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=1, decision_trace_sha256="a" * 63))  # too short
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(decision_trace_count=1, decision_trace_sha256=12345))  # not a string


def test_writer_appends_and_validates(tmp_path):
    p = tmp_path / "results.jsonl"
    w = BattleResultWriter(str(p))
    w.write(_row(seed_index=0))
    w.write(_row(seed_index=1))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["seed_index"] == 0
    with pytest.raises(ResultRowError):
        w.write(_row(winner=None))  # validate-on-write

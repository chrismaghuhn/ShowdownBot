"""T2 per-battle result JSONL: frozen row schema + validate-on-write + append-only.

Required fields fail fast if missing/None; winner must be a role (hero/villain/tie), not
a suffixed bot name. config_id (bot version) is distinct from format_id; config_hash is
required.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval.result_jsonl import (
    REQUIRED_FIELDS,
    BattleResultWriter,
    ResultRowError,
    make_battle_id,
    validate_battle_row,
)


def _row(**over):
    row = {
        "battle_id": "abc", "config_id": "heuristic", "format_id": "gen9vgc2025regi",
        "config_hash": "cfg123", "schedule_hash": "h",
        "seed_index": 0, "opp_policy": "heuristic", "hero_team_path": "teams/fixed_team.txt",
        "opp_team_path": "teams/opp_variant_a.txt", "seed": "sodium,00", "winner": "hero",
        "turns": 13, "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 200,
        "git_sha": "deadbeef", "end_hp_diff": None, "timeouts": None,
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


def test_make_battle_id_deterministic():
    assert make_battle_id("h", 0, "sodium,00") == make_battle_id("h", 0, "sodium,00")
    assert make_battle_id("h", 0, "sodium,00") != make_battle_id("h", 1, "sodium,00")


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

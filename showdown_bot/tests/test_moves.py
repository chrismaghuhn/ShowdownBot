from __future__ import annotations

import pytest

from showdown_bot.engine.moves import blocks_move, get_move_meta, move_priority
from showdown_bot.engine.state import FieldState


def test_known_move_lookup():
    fake = get_move_meta("Fake Out")
    assert fake.priority == 3
    assert fake.category == "physical"
    assert "protect" in fake.flags


def test_unknown_move_default():
    m = get_move_meta("Nonexistent Blast")
    assert m.priority == 0
    assert m.is_damaging
    assert "protect" in m.flags  # conservative: assume blockable


def test_grassy_glide_terrain_priority():
    gg = get_move_meta("Grassy Glide")
    assert move_priority(gg, FieldState()) == 0
    assert move_priority(gg, FieldState(terrain="Grassy Terrain")) == 1


def test_blocks_move_protect_flag():
    assert blocks_move(get_move_meta("Moonblast")) is True
    # Self-targeting status (Tailwind) is not blocked by Protect.
    assert blocks_move(get_move_meta("Tailwind")) is False


def test_spread_and_target_flags():
    eq = get_move_meta("Earthquake")
    assert eq.is_spread
    icy = get_move_meta("Icy Wind")
    assert icy.target == "allAdjacentFoes"
    assert icy.category == "special"


def test_get_move_meta_enriched_from_data():
    m = get_move_meta("Will-O-Wisp")
    assert m.category == "status"
    assert m.status == "brn"
    t = get_move_meta("Tailwind")
    assert t.side_condition == "tailwind"
    sd = get_move_meta("Swords Dance")
    assert sd.boosts == {"atk": 2}
    f = get_move_meta("Fake Out")
    assert "flinch" in f.flags and f.priority == 3
    eq = get_move_meta("Earthquake")
    assert eq.is_spread and eq.target == "allAdjacent"


def test_movedata_has_accuracy_for_every_move():
    import json
    from pathlib import Path
    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "config" / "moves" / "movedata.json")
        .read_text(encoding="utf-8")
    )
    for mid, rec in raw["moves"].items():
        assert "accuracy" in rec, f"{mid} missing accuracy key"


def test_thunder_and_hurricane_base_accuracy_is_70():
    assert get_move_meta("Thunder").accuracy == 70
    assert get_move_meta("Hurricane").accuracy == 70


def test_always_hit_move_accuracy_is_none():
    # Swift/Aura Sphere are @pkmn/dex accuracy===true moves -> normalized to null/None.
    assert get_move_meta("Swift").accuracy is None
    assert get_move_meta("Aura Sphere").accuracy is None


def test_move_table_raises_on_record_missing_accuracy_key(monkeypatch, tmp_path):
    import json
    from showdown_bot.engine import moves as moves_mod

    bad = {
        "source_version": "x", "generation": 9, "format": "f", "data_hash": "h",
        "moves": {"tackle": {"id": "tackle", "name": "Tackle", "category": "Physical",
                              "basePower": 40, "target": "normal"}},  # no "accuracy" key
    }
    bad_path = tmp_path / "movedata.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(moves_mod, "_MOVEDATA", bad_path)
    moves_mod._move_table.cache_clear()
    try:
        with pytest.raises(KeyError):
            moves_mod._move_table()
    finally:
        moves_mod._move_table.cache_clear()

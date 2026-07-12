from __future__ import annotations

import pytest

from showdown_bot.engine.moves import MoveMeta, blocks_move, get_move_meta, hit_probability, move_priority
from showdown_bot.engine.state import FieldState, PokemonState


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


def _mon(**boosts):
    m = PokemonState(species="Test", hp=100, max_hp=100)
    m.boosts.update(boosts)
    return m


def test_hit_probability_always_hit_move_is_none():
    swift = get_move_meta("Swift")
    assert hit_probability(swift, _mon(), _mon(), FieldState()) is None


def test_hit_probability_base_accuracy_no_stages():
    thunder = get_move_meta("Thunder")  # accuracy 70
    p = hit_probability(thunder, _mon(), _mon(), FieldState())
    assert abs(p - 0.70) < 1e-9


def test_hit_probability_positive_accuracy_stage_raises_it():
    thunder = get_move_meta("Thunder")
    p = hit_probability(thunder, _mon(accuracy=1), _mon(), FieldState())
    assert abs(p - 0.93) < 1e-9  # int(70 * 4/3) / 100 = int(93.33)/100 = 0.93


def test_hit_probability_negative_evasion_stage_raises_it():
    # Target evasion DOWN raises the attacker's effective hit chance (stage = acc - evasion,
    # so evasion=-1 contributes the same +1 as attacker accuracy=+1 would).
    thunder = get_move_meta("Thunder")
    p = hit_probability(thunder, _mon(), _mon(evasion=-1), FieldState())
    assert abs(p - 0.93) < 1e-9  # int(70 * 4/3)/100 == same formula as the accuracy=+1 case


def test_hit_probability_stage_clamped_at_plus_six():
    # A low-accuracy synthetic move so the clamp is provably at the BOOST-STAGE level, not
    # just masked by the final [0,1] probability clamp: at stage=6 (3x multiplier) 30 accuracy
    # gives 0.90, well under 1.0 -- an unclamped stage=9 (4x multiplier) would give 1.0, a
    # different value, so this distinguishes "stage clamped to 6" from "stage never clamped".
    low_acc = MoveMeta(id="lowacc", name="LowAcc", accuracy=30, base_power=100,
                        category="physical", target="normal")
    p_six = hit_probability(low_acc, _mon(accuracy=6), _mon(), FieldState())
    p_beyond = hit_probability(low_acc, _mon(accuracy=9), _mon(), FieldState())
    assert abs(p_six - 0.90) < 1e-9
    assert p_six == p_beyond  # clamp(9) == clamp(6)


def test_hit_probability_blizzard_guaranteed_in_snow():
    blizzard = get_move_meta("Blizzard")
    assert hit_probability(blizzard, _mon(), _mon(), FieldState(weather="Snow")) is None


def test_hit_probability_blizzard_not_guaranteed_outside_snow():
    blizzard = get_move_meta("Blizzard")
    p = hit_probability(blizzard, _mon(), _mon(), FieldState(weather="Sandstorm"))
    assert p is not None
    assert abs(p - (blizzard.accuracy / 100.0)) < 1e-9


def test_hit_probability_thunder_guaranteed_in_rain_stage_independent():
    thunder = get_move_meta("Thunder")
    p_no_stage = hit_probability(thunder, _mon(), _mon(), FieldState(weather="RainDance"))
    p_with_stage = hit_probability(thunder, _mon(), _mon(evasion=4), FieldState(weather="RainDance"))
    assert p_no_stage is None and p_with_stage is None  # unconditional, stage never applies


def test_hit_probability_thunder_sun_reduces_to_50_then_applies_stages():
    # Pinned against sim/battle-actions.ts:709-722 at the pinned commit
    # (config/eval/provenance.yaml): sun sets move.accuracy=50, a PLAIN NUMBER that then
    # goes through the SAME stage-multiplier pipeline as any base accuracy — not a flat 0.5.
    thunder = get_move_meta("Thunder")
    p_no_stage = hit_probability(thunder, _mon(), _mon(), FieldState(weather="SunnyDay"))
    assert abs(p_no_stage - 0.50) < 1e-9
    p_with_stage = hit_probability(thunder, _mon(accuracy=2), _mon(), FieldState(weather="SunnyDay"))
    assert abs(p_with_stage - 0.83) < 1e-9  # trunc(50 * 5/3)/100 = trunc(83.33)/100 = 0.83
    assert p_with_stage != 0.50  # the exact bug the earlier design got wrong


def test_hit_probability_clamped_to_one_when_stage_pushes_above_100():
    tackle_like = get_move_meta("Tackle")  # accuracy 100
    p = hit_probability(tackle_like, _mon(accuracy=6), _mon(), FieldState())
    assert p == 1.0

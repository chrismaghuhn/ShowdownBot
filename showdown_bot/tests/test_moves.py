from __future__ import annotations

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

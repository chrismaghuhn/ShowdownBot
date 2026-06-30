import copy

import pytest

from showdown_bot.engine.state import BattleState, PokemonState, FieldState
from showdown_bot.battle.resolve import TurnOutcome
from showdown_bot.learning.simulator import clone_state, apply_outcome_to_state


def _state():
    s = BattleState()
    s.sides["p1"] = {"a": PokemonState(species="Incineroar", hp=200, max_hp=200)}
    s.sides["p2"] = {"a": PokemonState(species="Flutter Mane", hp=100, max_hp=100)}
    return s


def test_clone_is_deep_and_independent():
    s = _state()
    c = clone_state(s)
    c.sides["p1"]["a"].hp = 1
    assert s.sides["p1"]["a"].hp == 200          # original untouched


def test_apply_returns_new_state_and_does_not_mutate_input():
    s = _state()
    before = copy.deepcopy(s)
    out = TurnOutcome()
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt is not s
    # input unchanged (deep compare on the mutated fields)
    assert s.sides["p1"]["a"].hp == before.sides["p1"]["a"].hp
    assert s.sides["p2"]["a"].hp == before.sides["p2"]["a"].hp


# ---------------------------------------------------------------------------
# T2: HP / faint
# ---------------------------------------------------------------------------

def test_hp_delta_fraction_applied_and_clamped():
    s = _state()  # p1a hp 200/200 (1.0), p2a 100/100 (1.0)
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40, ("p1", "a"): -0.25})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert abs(nxt.sides["p2"]["a"].hp_fraction - 0.60) < 1e-9   # 1.0 - 0.40
    assert nxt.sides["p2"]["a"].hp == 60
    assert abs(nxt.sides["p1"]["a"].hp_fraction - 0.75) < 1e-9   # 1.0 - 0.25

def test_hp_unit_075_minus_040():
    s = _state()
    s.sides["p2"]["a"].hp = 75  # 0.75 of 100
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.sides["p2"]["a"].hp == 35                          # 0.75 -> 0.35

def test_hp_clamp_and_faint():
    s = _state()
    out = TurnOutcome(hp_delta={("p2", "a"): -1.5})   # over-kill clamps to 0 + faint
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.sides["p2"]["a"].hp == 0 and nxt.sides["p2"]["a"].fainted is True

def test_hp_synthetic_maxhp_when_unknown():
    s = _state()
    s.sides["p2"]["a"].max_hp = None   # unrevealed -> synthetic 100
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.sides["p2"]["a"].max_hp == 100
    assert abs(nxt.sides["p2"]["a"].hp_fraction - 0.60) < 1e-9


# ---------------------------------------------------------------------------
# T3: field flag application
# ---------------------------------------------------------------------------

def test_field_tailwind_and_trickroom():
    s = _state()
    out = TurnOutcome(flags={"status:tailwind:p1a", "status:trickroom:p2a"})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.field.tailwind["p1"] is True
    assert nxt.field.trick_room is True            # toggled on from default False

def test_unknown_flag_is_ignored():
    s = _state()
    out = TurnOutcome(flags={"status:bogusmove:p1a", "wasted_move", "protect:p1a"})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})   # no crash
    assert nxt.field.tailwind["p1"] is False and nxt.field.trick_room is False

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

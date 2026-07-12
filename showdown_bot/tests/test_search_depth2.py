import copy
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.battle.search import approx_turn2_state


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.field.trick_room = True
    st.turn = 3
    return st


def test_transition_subtracts_damage_marks_faint_advances_turn():
    st = _state()
    # opponent deals 200 to our Incineroar(150) -> faint; we deal 50 to Flutter Mane(131)
    nxt = approx_turn2_state(st, our_side="p1",
        applied_damage={("p1", "a"): 200, ("p2", "a"): 50})
    assert nxt is not st and nxt.side("p1")["a"] is not st.side("p1")["a"]  # deep copy
    assert nxt.side("p1")["a"].hp == 0 and nxt.side("p1")["a"].fainted is True
    assert nxt.side("p2")["a"].hp == 81 and nxt.side("p2")["a"].fainted is False
    assert nxt.turn == 4                      # turn advanced
    assert nxt.field.trick_room is True       # field persists (no counters in FieldState)
    assert st.side("p1")["a"].hp == 150        # original untouched


def test_transition_clamps_hp_nonnegative():
    st = _state()
    nxt = approx_turn2_state(st, our_side="p1", applied_damage={("p2", "a"): 9999})
    assert nxt.side("p2")["a"].hp == 0 and nxt.side("p2")["a"].fainted is True

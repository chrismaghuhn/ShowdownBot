from showdown_bot.battle.rollout_adapter import conditions_from_battle
from showdown_bot.engine.state import BattleState, PokemonState

A = ("p1", "a")
B = ("p2", "a")


def _state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", status="brn", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    return st


def test_conditions_from_battle_seeds_status_tailwind_weather():
    st = _state()
    st.field.tailwind["p1"] = True
    st.field.weather = "Sandstorm"
    cs = conditions_from_battle(st)
    assert cs.mons[A].status == "brn"
    assert cs.mons[B].status is None
    assert "tailwind" in cs.sides["p1"]
    assert "sandstorm" in cs.field


def test_conditions_from_battle_seeds_grassy_terrain():
    st = _state()
    st.field.terrain = "Grassy Terrain"
    cs = conditions_from_battle(st)
    assert "grassyterrain" in cs.field


def test_conditions_from_battle_empty_field():
    cs = conditions_from_battle(_state())
    assert cs.field == {}
    assert cs.sides.get("p1", {}) == {}

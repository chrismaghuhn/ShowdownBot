from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.battle.rollout_adapter import apply_line_effects, conditions_from_battle
from showdown_bot.engine.moves import get_move_meta
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


def test_apply_line_effects_inflicts_primary_status():
    st = _state()  # p2a has no status
    cs = conditions_from_battle(st)
    wow = get_move_meta("Will-O-Wisp")  # status == "brn"
    action = PlannedAction("p1", "a", "move", move=wow, target=B, is_ours=True)
    apply_line_effects(cs, [action])
    assert cs.mons[B].status == "brn"


def test_apply_line_effects_does_not_overwrite_existing_status():
    st = _state()
    st.sides["p2"]["a"].status = "par"
    cs = conditions_from_battle(st)
    wow = get_move_meta("Will-O-Wisp")
    apply_line_effects(cs, [PlannedAction("p1", "a", "move", move=wow, target=B, is_ours=True)])
    assert cs.mons[B].status == "par"  # already statused -> unchanged

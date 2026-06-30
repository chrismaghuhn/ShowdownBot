from __future__ import annotations

from showdown_bot.engine.belief.game_mode import GameMode, classify_game_mode
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState


class LowDamageCalc:
    """Never produces a guaranteed KO -> base mode is always NEUTRAL."""

    def damage_batch(self, requests):
        return [DamageResult(min_damage=10, max_damage=20, max_hp=100) for _ in requests]


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _base_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    st.sides["p1"]["a"].move_names = {"Knock Off"}
    st.sides["p2"]["a"].move_names = {"Moonblast"}
    return st


def test_neutral_baseline():
    st = _base_state()
    mode = classify_game_mode(st, our_side="p1", calc=LowDamageCalc(), book=_book())
    assert mode == GameMode.NEUTRAL


def test_behind_in_mons_is_must_react():
    st = _base_state()
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", fainted=True, hp=0, max_hp=155)
    mode = classify_game_mode(st, our_side="p1", calc=LowDamageCalc(), book=_book())
    assert mode == GameMode.MUST_REACT


def test_ahead_in_mons_is_ahead():
    st = _base_state()
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", fainted=True, hp=0, max_hp=100)
    mode = classify_game_mode(st, our_side="p1", calc=LowDamageCalc(), book=_book())
    assert mode == GameMode.AHEAD


def test_opp_low_hp_is_ahead():
    st = _base_state()
    st.sides["p2"]["a"].hp = 30  # 30% -> low-HP target
    mode = classify_game_mode(st, our_side="p1", calc=LowDamageCalc(), book=_book())
    assert mode == GameMode.AHEAD


def test_opp_tailwind_even_is_must_react():
    st = _base_state()
    st.field.tailwind["p2"] = True
    mode = classify_game_mode(st, our_side="p1", calc=LowDamageCalc(), book=_book())
    assert mode == GameMode.MUST_REACT

from __future__ import annotations

from showdown_bot.engine.belief.game_mode import GameMode, compute_game_mode
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState


class ScriptBackend:
    """Scripted backend keyed on (move, defender_species) -> (min_dmg, max_hp)."""

    def __init__(self, script: dict[tuple[str, str], tuple[int, int]]):
        self.script = script

    def calc_batch(self, requests):
        out = []
        for req in requests:
            key = (req.move, req.defender.species)
            min_dmg, max_hp = self.script.get(key, (0, 999))
            out.append(
                DamageResult(
                    rolls=[min_dmg, min_dmg],
                    min_damage=min_dmg,
                    max_damage=min_dmg,
                    max_hp=max_hp,
                    id=req.id,
                )
            )
        return out


def _book():
    cfg = load_format_config("gen9vgc2026regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _state() -> BattleState:
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(
        species="Incineroar", hp=200, max_hp=200, move_names={"Flare Blitz"}
    )
    state.sides["p2"]["a"] = PokemonState(
        species="Flutter Mane", hp=130, max_hp=130, move_names={"Moonblast"}
    )
    return state


def test_must_react_when_our_mon_is_ohkod():
    book = _book()
    backend = ScriptBackend(
        {
            ("Moonblast", "Incineroar"): (260, 202),  # opp OHKOs us
            ("Flare Blitz", "Flutter Mane"): (300, 131),
        }
    )
    mode = compute_game_mode(
        _state(), our_side="p1", calc=CalcClient(backend=backend), book=book
    )
    assert mode is GameMode.MUST_REACT


def test_ahead_when_safe_and_we_ko():
    book = _book()
    backend = ScriptBackend(
        {
            ("Moonblast", "Incineroar"): (60, 202),  # we survive
            ("Flare Blitz", "Flutter Mane"): (300, 131),  # we OHKO max-bulk opp
        }
    )
    mode = compute_game_mode(
        _state(), our_side="p1", calc=CalcClient(backend=backend), book=book
    )
    assert mode is GameMode.AHEAD


def test_neutral_when_safe_but_no_ko():
    book = _book()
    backend = ScriptBackend(
        {
            ("Moonblast", "Incineroar"): (60, 202),  # we survive
            ("Flare Blitz", "Flutter Mane"): (50, 200),  # we cannot KO max bulk
        }
    )
    mode = compute_game_mode(
        _state(), our_side="p1", calc=CalcClient(backend=backend), book=book
    )
    assert mode is GameMode.NEUTRAL

from __future__ import annotations

import pytest

from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SetHypothesis,
    build_hypotheses,
    load_spread_book,
)
from showdown_bot.engine.calc.client import CalcClient, SubprocessCalcBackend
from showdown_bot.engine.calc.models import DamageRequest
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState


def _book():
    cfg = load_format_config("gen9vgc2026regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def test_unknown_item_yields_multiple_candidates():
    book = _book()
    h = SetHypothesis(species="Incineroar", spreads=book.get("Incineroar"))
    assert len(h.item_candidates(OFFENSE)) >= 2


def test_known_item_collapses_candidates():
    book = _book()
    h = SetHypothesis(
        species="Incineroar",
        item="Sitrus Berry",
        item_known=True,
        spreads=book.get("Incineroar"),
    )
    assert h.item_candidates(OFFENSE) == ["Sitrus Berry"]
    assert h.as_defender(DEFENSE).item == "Sitrus Berry"


def test_offense_and_defense_presets_differ():
    book = _book()
    spreads = book.get("Flutter Mane")
    assert spreads.offense.evs != spreads.defense.evs


def test_build_hypotheses_for_opponent_side():
    cfg = load_format_config("gen9vgc2026regi")
    state = BattleState()
    state.sides["p2"]["a"] = PokemonState(species="Flutter Mane", ability="Protosynthesis")
    hyps = build_hypotheses(state, cfg, "p2")
    assert "a" in hyps
    assert hyps["a"].ability == "Protosynthesis"


@pytest.mark.integration
def test_offense_preset_hits_harder_than_defense_preset():
    book = _book()
    flutter = SetHypothesis(species="Flutter Mane", spreads=book.get("Flutter Mane"))
    incin = SetHypothesis(species="Incineroar", spreads=book.get("Incineroar"))
    client = CalcClient(backend=SubprocessCalcBackend())

    # Flutter Mane attacking in offense vs defense spread, same defender.
    off = client.damage(
        DamageRequest(
            attacker=flutter.as_attacker(OFFENSE, move="Moonblast"),
            defender=incin.as_defender(DEFENSE),
            move="Moonblast",
        )
    )
    deff = client.damage(
        DamageRequest(
            attacker=flutter.as_attacker(DEFENSE, move="Moonblast"),
            defender=incin.as_defender(DEFENSE),
            move="Moonblast",
        )
    )
    assert off.max_damage > deff.max_damage

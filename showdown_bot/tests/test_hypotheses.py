from __future__ import annotations

import pytest

from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SetHypothesis,
    SpreadBook,
    SpreadPreset,
    SpeciesSpreads,
    build_hypotheses,
    hypothesis_from_state,
    load_spread_book,
)
from showdown_bot.engine.calc.client import CalcClient, SubprocessCalcBackend
from showdown_bot.engine.calc.models import DamageRequest
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState


def _book():
    cfg = load_format_config("gen9vgc2025regi")
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
    cfg = load_format_config("gen9vgc2025regi")
    state = BattleState()
    state.sides["p2"]["a"] = PokemonState(species="Flutter Mane", ability="Protosynthesis")
    hyps = build_hypotheses(state, cfg, "p2")
    assert "a" in hyps
    assert hyps["a"].ability == "Protosynthesis"


def _distinctive_spreads() -> SpeciesSpreads:
    """A committed spread that is deliberately NOT the book default, so a test
    asserting we got THIS spread (not the default fallback) is meaningful."""
    offense = SpreadPreset(nature="Naive", evs={"atk": 4, "spa": 252, "spe": 252}, items=["Life Orb"])
    defense = SpreadPreset(nature="Impish", evs={"hp": 252, "def": 252, "spe": 4}, items=["Leftovers"])
    return SpeciesSpreads(offense=offense, defense=defense)


def _default_spreads() -> SpeciesSpreads:
    offense = SpreadPreset(nature="Hardy", evs={}, items=[])
    defense = SpreadPreset(nature="Hardy", evs={}, items=[])
    return SpeciesSpreads(offense=offense, defense=defense)


def test_hypothesis_from_state_resolves_post_mega_species_to_base_species_spread():
    """P1.2: after Mega evolution mon.species is the post-Mega display name
    ("Aerodactyl-Mega") while base_species_id correctly stays the pre-Mega base
    id ("aerodactyl"). hypothesis_from_state must resolve the committed spread
    via the base species id, not the raw post-Mega species string, else it
    silently falls back to the book default (worst-case) instead of the
    actually-committed spread."""
    committed = _distinctive_spreads()
    book = SpreadBook(default=_default_spreads(), species={"aerodactyl": committed})
    mon = PokemonState(species="Aerodactyl-Mega", base_species_id="aerodactyl")

    hyp = hypothesis_from_state(mon, book)

    assert hyp.spreads is committed
    assert hyp.spreads.offense.nature == "Naive"
    assert hyp.spreads.offense.evs == {"atk": 4, "spa": 252, "spe": 252}
    assert hyp.spreads.defense.nature == "Impish"
    assert hyp.spreads.defense.evs == {"hp": 252, "def": 252, "spe": 4}
    # not the book default (that would mean the lookup missed and fell back).
    assert hyp.spreads is not book.default


def test_hypothesis_from_state_non_mega_lookup_unchanged():
    """Regression: for a never-Mega'd mon, base_species_id already equals
    to_id(species) via PokemonState.__post_init__, so the spread_lookup_key
    based resolution must produce the exact same result as a raw species-id
    lookup did before this fix."""
    committed = _distinctive_spreads()
    book = SpreadBook(default=_default_spreads(), species={"incineroar": committed})
    mon = PokemonState(species="Incineroar")

    assert mon.base_species_id == "incineroar"
    hyp = hypothesis_from_state(mon, book)

    assert hyp.spreads is committed
    assert hyp.spreads is book.species["incineroar"]


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

"""Lever A, commit 3: fold the game-mode incoming into the shared scoring flush.

RED->GREEN proofs for the production fold. T1 proves the eager classify at
decision.py:397 is gone (replaced by enqueue-into-shared-oracle + resolve after the
flush). T8 proves the mega resolver fires exactly once across worlds. T9 proves the
injected calc is never dropped.
"""
from __future__ import annotations

import showdown_bot.battle.decision as decision
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import (
    SpeciesSpreads, SpreadBook, SpreadPreset)
from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.calc_profile import calc_profile_from_config
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest


def _gating_req():
    def ms(names):
        return [{"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal", "disabled": False}
                for n in names]
    return BattleRequest.model_validate({
        "active": [{"moves": ms(["Rock Slide"]), "canMegaEvo": True},
                   {"moves": ms(["Moonblast"]), "canMegaEvo": False}],
        "side": {"name": "Player1", "id": "p1", "pokemon": [
            {"ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100", "active": True,
             "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": [to_id("Rock Slide")], "baseTypes": ["Rock", "Flying"], "item": "Aerodactylite"},
            {"ident": "p1: Whimsicott", "details": "Whimsicott, L50", "condition": "100/100", "active": True,
             "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": [to_id("Moonblast")], "baseTypes": ["Grass", "Fairy"]}]}, "rqid": 1})


def _gating_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item="Aerodactylite", types=["Rock", "Flying"], hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Whimsicott", base_species_id="whimsicott",
                                       types=["Grass", "Fairy"], hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl",
                                       item="Aerodactylite", item_known=True,
                                       types=["Rock", "Flying"], hp=100, max_hp=100)
    return st


def _run_mega(**overrides):
    champions = load_format_config("gen9championsvgc2026regma")
    cp = calc_profile_from_config(champions)
    spreads = SpeciesSpreads(offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
                             defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}))
    oracle = overrides.get("oracle") or DamageOracle()
    kw = dict(
        state=_gating_state(), book=SpreadBook(default=spreads), our_side="p1",
        calc=oracle.client, oracle=oracle,
        speed_oracle=SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=cp),
        dex=None, our_spreads={"aerodactyl": spreads, "whimsicott": spreads},
        format_config=champions, risk_lambda=0.0,
    )
    kw.update({k: v for k, v in overrides.items() if k != "oracle"})
    return _choose_best(_gating_req(), **kw)


def test_fold_decision_enqueues_classification_into_shared_oracle(monkeypatch):
    """After the fold, _choose_best resolves GameMode via the two-phase
    enqueue_classification (into the shared oracle) + resolve after the flush, NOT the
    eager classify_game_mode at decision.py:397. RED before the fold: enqueue_classification
    is never invoked by the decision (it still calls classify_game_mode)."""
    called = {"enqueue": 0}
    real = getattr(decision, "enqueue_classification", None)

    def _spy(*a, **k):
        called["enqueue"] += 1
        return real(*a, **k)

    monkeypatch.setattr(decision, "enqueue_classification", _spy, raising=False)
    ja, score = _run_mega()
    assert ja.slot0.kind == "move"  # a real decision was produced
    assert called["enqueue"] == 1  # via the two-phase enqueue, exactly once


def test_mega_resolver_runs_exactly_once_across_worlds(monkeypatch):
    """The resolver that computes GameMode (with its conditional second flush) must fire
    exactly once per decision even when multiple worlds are sampled."""
    import showdown_bot.engine.belief.game_mode as gm
    calls = {"n": 0}
    real = gm.resolve_classification

    def _counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)
    monkeypatch.setattr(gm, "resolve_classification", _counting)
    # also patch the name imported into decision, if it imports it directly
    if hasattr(decision, "resolve_classification"):
        monkeypatch.setattr(decision, "resolve_classification", _counting)
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    _run_mega()
    assert calls["n"] == 1, f"resolver fired {calls['n']} times (expected exactly 1)"


def test_injected_calc_is_never_dropped():
    """The shared oracle's client is the injected calc; a decision must route through it
    and never construct a default CalcClient for classification."""
    champions = load_format_config("gen9championsvgc2026regma")
    cp = calc_profile_from_config(champions)
    spreads = SpeciesSpreads(offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
                             defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}))
    oracle = DamageOracle()
    seen = {"n": 0}
    real_db = oracle.client.damage_batch

    def _wrapped(reqs):
        seen["n"] += 1
        return real_db(reqs)
    oracle.client.damage_batch = _wrapped
    _run_mega(oracle=oracle,
              speed_oracle=SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=cp))
    assert seen["n"] > 0  # the injected calc client actually received the classification/scoring calc

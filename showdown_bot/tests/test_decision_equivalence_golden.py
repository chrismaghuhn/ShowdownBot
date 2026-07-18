"""Lever A, commit 2 (hardened): decision-equivalence GOLDEN (T2/T5).

Pins the FULL ranked candidate list (before the trace's top-K truncation) EXACTLY against a
committed golden file -- game_mode, and every candidate's id (tie-break order), aggregate score,
and full score vector -- for a non-mega (Reg-I) and a foe-Mega (Champions) board, both with
opponent moves so classification issues real incoming requests that the fold folds. Exact
serialized comparison (no approx): the fold is behavior-neutral, so every value is bit-identical.
"""
from __future__ import annotations

import json
from pathlib import Path

import showdown_bot.battle.decision as decision
from showdown_bot.battle.decision import _choose_best, heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import (
    SpeciesSpreads, SpreadBook, SpreadPreset, load_spread_book)
from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.calc_profile import calc_profile_from_config
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle, SpeedRange
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

FIX = Path(__file__).parent / "fixtures"


def _serialize(trace):
    return {"game_mode": trace.game_mode,
            "candidates": [[c.candidate_id, c.aggregate_score, list(c.score_vector)]
                           for c in trace.candidates]}


# ---------- non-mega (Reg-I): deterministic FakeCalc, production-faithful oracle ----------
class _FakeCalc:
    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(species, ["Normal"])


def _regi_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


def test_regi_non_mega_decision_golden(monkeypatch):
    monkeypatch.setattr(decision, "TOP_K_TRACE_CANDIDATES", 100000)  # full ranked list, no truncation
    fake = _FakeCalc()
    trace = DecisionTrace()
    out = heuristic_choose_for_request(
        _regi_req(), state=_regi_state(),
        book=load_spread_book(load_format_config("gen9vgc2025regi").meta_path("default_spreads")),
        our_side="p1", calc=fake, oracle=DamageOracle(client=fake),
        speed_oracle=_FakeSpeed(), dex=_FakeDex(), trace=trace,
    )
    assert out == "/choose move 3, move 3|2"
    golden = json.loads((FIX / "lever_a_golden_regi.json").read_text())
    assert _serialize(trace) == golden


def _regi_req():
    return BattleRequest.model_validate(json.loads((FIX / "request_doubles_moves.json").read_text()))


# ---------- foe-Mega (Champions): real calc, opponent WITH moves, production-faithful ----------
def _gating_req():
    def ms(names):
        return [{"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal", "disabled": False}
                for n in names]
    return BattleRequest.model_validate({
        "active": [{"moves": ms(["Rock Slide"]), "canMegaEvo": True},
                   {"moves": ms(["Moonblast"]), "canMegaEvo": False}],
        "side": {"name": "P1", "id": "p1", "pokemon": [
            {"ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100", "active": True,
             "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": [to_id("Rock Slide")], "baseTypes": ["Rock", "Flying"], "item": "Aerodactylite"},
            {"ident": "p1: Whimsicott", "details": "Whimsicott, L50", "condition": "100/100", "active": True,
             "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": [to_id("Moonblast")], "baseTypes": ["Grass", "Fairy"]}]}, "rqid": 1})


def _gating_state():
    st = BattleState()
    a = PokemonState(species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
                     types=["Rock", "Flying"], hp=100, max_hp=100)
    a.move_names = {"Rock Slide"}
    b = PokemonState(species="Whimsicott", base_species_id="whimsicott", types=["Grass", "Fairy"],
                     hp=100, max_hp=100)
    b.move_names = {"Moonblast"}
    opp = PokemonState(species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
                       item_known=True, types=["Rock", "Flying"], hp=100, max_hp=100)
    opp.move_names = {"Rock Slide", "Earthquake"}
    st.sides["p1"]["a"], st.sides["p1"]["b"], st.sides["p2"]["a"] = a, b, opp
    return st


def test_foe_mega_decision_golden(monkeypatch):
    monkeypatch.setattr(decision, "TOP_K_TRACE_CANDIDATES", 100000)
    champions = load_format_config("gen9championsvgc2026regma")
    cp = calc_profile_from_config(champions)
    spreads = SpeciesSpreads(offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
                             defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}))
    oracle = DamageOracle()
    trace = DecisionTrace()
    ja, score = _choose_best(
        _gating_req(), state=_gating_state(), book=SpreadBook(default=spreads), our_side="p1",
        calc=oracle.client, oracle=oracle,
        speed_oracle=SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=cp),
        dex=None, our_spreads={"aerodactyl": spreads, "whimsicott": spreads},
        format_config=champions, risk_lambda=0.0, trace=trace,
    )
    assert ja.slot0.mega_evolve is True and ja.slot0.move_index == 1
    golden = json.loads((FIX / "lever_a_golden_champions.json").read_text())
    assert _serialize(trace) == golden

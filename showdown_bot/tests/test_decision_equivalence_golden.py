"""Lever A, commit 2 (hardened): decision-equivalence GOLDEN (T2/T5).

A production-faithful characterization pin of the CURRENT decision output for a non-mega (Reg-I)
and a foe-Mega (Champions) board, BOTH with opponent moves so classification issues real incoming
requests that the fold must fold. It pins the full contract the reviewer requires: the chosen
action, the GameMode, the tie-break ORDER of the traced candidates, and each candidate's full
aggregate score and score vector. Green now; its job is to STAY green through the fold.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _assert_candidates(trace, expected):
    """Bind GameMode, tie-break order (candidate ids), aggregate scores and full score vectors."""
    got = [(c.candidate_id, c.rank) for c in trace.candidates]
    assert got == [(cid, i) for i, (cid, _agg, _sv) in enumerate(expected)], got
    for c, (cid, agg, sv) in zip(trace.candidates, expected):
        assert c.aggregate_score == pytest.approx(agg, rel=1e-6, abs=1e-9), (cid, c.aggregate_score)
        assert c.score_vector == pytest.approx(sv, rel=1e-6, abs=1e-9), (cid, c.score_vector)


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


def _regi_book():
    return load_spread_book(load_format_config("gen9vgc2025regi").meta_path("default_spreads"))


def _regi_req():
    return BattleRequest.model_validate(json.loads((FIX / "request_doubles_moves.json").read_text()))


def _regi_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}          # opponent HAS moves -> real incoming fold
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


def test_regi_non_mega_decision_golden():
    fake = _FakeCalc()
    trace = DecisionTrace()
    out = heuristic_choose_for_request(
        _regi_req(), state=_regi_state(), book=_regi_book(), our_side="p1",
        calc=fake, oracle=DamageOracle(client=fake), speed_oracle=_FakeSpeed(), dex=_FakeDex(),
        trace=trace,
    )
    assert out == "/choose move 3, move 3|2"
    assert trace.game_mode == "NEUTRAL"
    _assert_candidates(trace, [
        ("(Protect, Protect)", 3.0528, [5.4, 5.4, 3.6, 1.8, 3.6]),
        ("(Fake Out->2, Earth Power->2)", 2.7225919999999997, [2.62, 2.62, 2.9, 2.62, 2.9]),
        ("(Fake Out->2, Solar Beam->2)", 2.7225919999999997, [2.62, 2.62, 2.9, 2.62, 2.9]),
        ("(Fake Out->2, Heat Wave)", 2.4278699999999995, [2.69, 2.69, 1.635, 2.69, 2.97]),
        ("(Fake Out->2, Earth Power->1)", 2.3328320000000002, [2.62, 2.62, 1.5, 2.62, 2.9]),
        ("(Fake Out->2, Solar Beam->1)", 2.3328320000000002, [2.62, 2.62, 1.5, 2.62, 2.9]),
    ])


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
    opp.move_names = {"Rock Slide", "Earthquake"}        # opponent HAS moves -> real incoming fold
    st.sides["p1"]["a"], st.sides["p1"]["b"], st.sides["p2"]["a"] = a, b, opp
    return st


def test_foe_mega_decision_golden():
    champions = load_format_config("gen9championsvgc2026regma")
    cp = calc_profile_from_config(champions)
    spreads = SpeciesSpreads(offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
                             defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}))
    oracle = DamageOracle()  # oracle.client is the real calc used everywhere on this path
    trace = DecisionTrace()
    ja, score = _choose_best(
        _gating_req(), state=_gating_state(), book=SpreadBook(default=spreads), our_side="p1",
        calc=oracle.client, oracle=oracle,
        speed_oracle=SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=cp),
        dex=None, our_spreads={"aerodactyl": spreads, "whimsicott": spreads},
        format_config=champions, risk_lambda=0.0, trace=trace,
    )
    assert ja.slot0.kind == "move" and ja.slot0.move_index == 1 and ja.slot0.target == 1
    assert ja.slot0.mega_evolve is True and ja.slot0.terastallize is False
    assert ja.slot1.kind == "move" and ja.slot1.move_index == 1 and ja.slot1.mega_evolve is False
    assert score == pytest.approx(-4.657968164560821, rel=1e-9)
    assert trace.game_mode == "NEUTRAL"
    _mega = [-5.3305077591, -5.3305077591, -2.4, -5.5056507847, -5.5056507847, -5.5056507847, -5.5056507847]
    _base = [-5.462751875, -5.462751875, -2.4, -5.6688503146, -5.6688503146]
    _assert_candidates(trace, [
        ("(Rock Slide->1 mega, Moonblast->1)", -4.657968164560821, _mega),
        ("(Rock Slide->1 mega, Moonblast->2)", -4.657968164560821, _mega),
        ("(Rock Slide->2 mega, Moonblast->1)", -4.657968164560821, _mega),
        ("(Rock Slide->2 mega, Moonblast->2)", -4.657968164560821, _mega),
        ("(Rock Slide->1, Moonblast->1)", -4.765951946333246, _base),
        ("(Rock Slide->1, Moonblast->2)", -4.765951946333246, _base),
        ("(Rock Slide->2, Moonblast->1)", -4.765951946333246, _base),
        ("(Rock Slide->2, Moonblast->2)", -4.765951946333246, _base),
    ])

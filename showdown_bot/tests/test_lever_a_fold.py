"""Lever A, commit 3: fold the game-mode incoming into the shared scoring flush.

Binding counterproofs for the production fold:
  T1  -- the game-mode INCOMING no longer pays its own Node spawn: on a board where the
         opponent HAS moves (so classification issues real incoming ko-threat requests), the
         damage backend's spawn count equals the SHARED oracle's flush count -- i.e. all damage,
         classification included, went through the one shared oracle. Pre-fold the private classify
         oracle made spawn_count > oracle.batch_calls.
  T4  -- CalcError in the shared first flush AND in the conditional outgoing (second) flush both
         propagate fail-closed.
  T8  -- with two genuinely-sampled worlds the mode resolver fires EXACTLY once (after world 0).
  T9  -- the injected calc client is never dropped: a default CalcClient/backend construction hard
         fails, and the injected client receives the concrete classification (opp-attacks-us) requests.
"""
from __future__ import annotations

import pytest

import showdown_bot.battle.decision as decision
import showdown_bot.battle.mega_scoring as mega_scoring
import showdown_bot.engine.belief.game_mode as gm
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import (
    SpeciesSpreads, SpreadBook, SpreadPreset)
from showdown_bot.engine.calc.client import CalcError, SubprocessCalcBackend
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.calc_profile import calc_profile_from_config
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

CHAMPIONS = load_format_config("gen9championsvgc2026regma")
CP = calc_profile_from_config(CHAMPIONS)
SPREADS = SpeciesSpreads(offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
                         defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}))


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
    """Foe-Mega board where the OPPONENT HAS MOVES -> classification issues real incoming
    ko-threat requests (without them the fold would be a no-op and prove nothing)."""
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


def _run_mega(*, oracle=None, speed_oracle=None, trace=None):
    oracle = oracle or DamageOracle()
    speed_oracle = speed_oracle or SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=CP)
    return _choose_best(
        _gating_req(), state=_gating_state(), book=SpreadBook(default=SPREADS), our_side="p1",
        calc=oracle.client, oracle=oracle, speed_oracle=speed_oracle, dex=None,
        our_spreads={"aerodactyl": SPREADS, "whimsicott": SPREADS},
        format_config=CHAMPIONS, risk_lambda=0.0, trace=trace,
    )


# --------------------------------------------------------------------------- T1
def test_fold_game_mode_incoming_costs_no_separate_spawn():
    """The opponent has moves, so classification issues real incoming requests. After the fold
    ALL damage (classification incoming/outgoing + scoring) resolves through the SHARED oracle, so
    the damage backend's spawn count equals the shared oracle's flush count and there is no gap /
    transport-retry. Pre-fold the private classify oracle made spawn_count > oracle.batch_calls."""
    assert _gating_state().sides["p2"]["a"].move_names  # the fold has something to fold
    oracle = DamageOracle()  # real SubprocessCalcBackend; oracle.client.backend is the damage backend
    _run_mega(oracle=oracle, trace=None)  # trace=None so the out-of-scope trace game-mode calls don't run
    backend = oracle.client.backend
    assert oracle.batch_calls >= 1  # real damage work happened
    # the binding claim: no damage spawn happened OUTSIDE the shared oracle (no separate game-mode flush)
    assert backend.spawn_count == oracle.batch_calls
    # equivalently, no un-oracled attempt -> transport_retried would be False
    assert backend.transport_attempts == backend.damage_batch_calls


# --------------------------------------------------------------------------- T4
class _RaiseOnNth:
    """Damage backend that returns valid results for the first ``ok`` calc_batch calls, then raises
    CalcError -- to hit either the shared first flush (ok=0) or the conditional outgoing flush."""
    def __init__(self, ok):
        self.ok = ok
        self.calls = 0

    def calc_batch(self, requests):
        self.calls += 1
        if self.calls > self.ok:
            raise CalcError("injected calc failure")
        return [DamageResult(min_damage=1, max_damage=2, max_hp=200, id=r.id) for r in requests]


def test_calcerror_in_shared_first_flush_propagates_fail_closed():
    from showdown_bot.engine.calc.client import CalcClient
    oracle = DamageOracle(client=CalcClient(backend=_RaiseOnNth(ok=0)))
    with pytest.raises(CalcError):
        _run_mega(oracle=oracle, trace=None)


def test_calcerror_in_conditional_outgoing_flush_propagates_fail_closed():
    """The game-mode base path: incoming flush succeeds, threatened == 0, then the OUTGOING
    (second) flush raises -- the CalcError must propagate."""
    from showdown_bot.engine.calc.client import CalcClient
    st = _gating_state()
    backend = _RaiseOnNth(ok=1)  # incoming flush ok, outgoing flush raises
    oracle = DamageOracle(client=CalcClient(backend=backend))
    handle = gm.enqueue_base_game_mode(st, our_side="p1", oracle=oracle, book=SpreadBook(default=SPREADS))
    oracle.flush()  # incoming resolves (min_damage=1 -> not a guaranteed OHKO -> threatened == 0)
    with pytest.raises(CalcError):
        gm.resolve_base_game_mode(handle, oracle=oracle)  # enqueues outgoing + flushes -> raises
    assert backend.calls >= 2  # the second (outgoing) flush was the one that raised


# --------------------------------------------------------------------------- T8
def test_mode_resolver_fires_exactly_once_across_two_sampled_worlds(monkeypatch):
    """With two genuinely-sampled worlds the memoized resolver runs once (after world 0) and is
    reused for world 1 -- not once per world."""
    world1 = SpeciesSpreads(offense=SpreadPreset(nature="Hardy", evs={}),
                            defense=SpreadPreset(nature="Hardy", evs={}))
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    monkeypatch.setattr(mega_scoring, "build_world_dist", lambda *a, **k: {"aerodactyl": [(world1, 1.0)]})
    monkeypatch.setattr(mega_scoring, "sample_worlds",
                        lambda *a, **k: [({}, 0.7), ({"aerodactyl": world1}, 0.3)])
    resolve_calls = {"n": 0}
    real_resolve = gm.resolve_classification

    def _spy(*a, **k):
        resolve_calls["n"] += 1
        return real_resolve(*a, **k)
    monkeypatch.setattr(decision, "resolve_classification", _spy)

    trace = DecisionTrace()
    _run_mega(trace=trace)
    assert resolve_calls["n"] == 1, f"resolver fired {resolve_calls['n']} times (expected 1)"
    # two worlds were actually evaluated: the pooled per-candidate score_vector spans both worlds,
    # so it is longer than the single-world vector (7 responses -> > 7 pooled).
    assert trace.candidates
    assert len(trace.candidates[0].score_vector) > 7


# --------------------------------------------------------------------------- T9
def test_injected_calc_is_never_dropped_for_a_default(monkeypatch):
    """Any construction of a DEFAULT calc backend hard-fails, so the decision must use ONLY the
    injected client -- and that client must receive the concrete classification (opp-attacks-us)
    requests."""
    monkeypatch.setattr(
        "showdown_bot.engine.calc.client.make_calc_backend",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("a default calc backend must not be built")),
    )
    seen_attackers: list[str] = []
    oracle = DamageOracle(client=_make_recording_client(seen_attackers))
    _run_mega(oracle=oracle, trace=None)
    # the injected client received the game-mode INCOMING (opponent attacking us): attacker == opp
    assert "Aerodactyl" in seen_attackers  # the opponent (Aerodactyl) as attacker == a ko-threat calc


def _make_recording_client(sink: list):
    from showdown_bot.engine.calc.client import CalcClient

    class _Rec:
        def calc_batch(self, requests):
            for r in requests:
                sink.append(r.attacker.species)
            return [DamageResult(min_damage=1, max_damage=2, max_hp=200, id=r.id) for r in requests]

    return CalcClient(backend=_Rec())

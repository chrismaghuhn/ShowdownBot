"""Lever A, commit 3: fold the game-mode incoming into the shared scoring flush.

Binding counterproofs for the production fold (see the §3.4 Erratum in the design):
  T1  -- all classification damage routes through the SHARED oracle (spawn_count == oracle.batch_calls),
         so no damage spawn happens outside it. The net saving is >= 1 spawn; on the reference board
         BOTH incoming and outgoing fold (outgoing is cache-served) -> -2 and damage_batch_calls stays 1.
  T4  -- CalcError fail-closed: the shared first flush error propagates through _choose_best; the
         conditional OUTGOING is always cache-served AT THE DECISION LEVEL (no second backend call), so
         its error surface exists only at the game_mode unit level, where it also propagates.
  T8  -- with two genuinely-sampled worlds the mode resolver fires EXACTLY once and returns the SAME
         GameMode the pre-fold eager classifier would (same mode consumed across both worlds).
  T9  -- the injected calc client is never dropped: default backend construction hard-fails, and the
         EXACT classification incoming request keys are received by the injected client.
"""
from __future__ import annotations

import pytest

import showdown_bot.battle.decision as decision
import showdown_bot.battle.mega_scoring as mega_scoring
import showdown_bot.engine.belief.game_mode as gm
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
from showdown_bot.engine.calc.client import CalcClient, CalcError, SubprocessCalcBackend
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
BOOK = SpreadBook(default=SPREADS)


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
    """Foe-Mega board where the OPPONENT HAS MOVES -> classification issues real incoming requests."""
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
        _gating_req(), state=_gating_state(), book=BOOK, our_side="p1",
        calc=oracle.client, oracle=oracle, speed_oracle=speed_oracle, dex=None,
        our_spreads={"aerodactyl": SPREADS, "whimsicott": SPREADS},
        format_config=CHAMPIONS, risk_lambda=0.0, trace=trace,
    )


# --------------------------------------------------------------------------- T1
def test_fold_routes_all_classification_damage_through_the_shared_oracle():
    """The opponent has moves, so classification issues real incoming requests. After the fold ALL
    damage (classification incoming/outgoing + scoring) resolves through the SHARED oracle, so the
    damage backend's spawn count equals the shared oracle's flush count and no un-oracled attempt
    happens. Per the erratum the outgoing is cache-served here, so damage_batch_calls stays 1 and the
    net saving is -2 vs the pre-fold spawn_count of 3."""
    assert _gating_state().sides["p2"]["a"].move_names  # the fold has real incoming to fold
    oracle = DamageOracle()
    _run_mega(oracle=oracle, trace=None)  # trace=None: the out-of-scope trace game-mode calls don't run
    b = oracle.client.backend
    assert oracle.batch_calls >= 1
    assert b.spawn_count == oracle.batch_calls          # no damage spawn OUTSIDE the shared oracle
    assert b.transport_attempts == b.damage_batch_calls  # -> transport_retried would be False
    # actual contract on this board (erratum): incoming + outgoing both fold; outgoing cache-served
    assert oracle.batch_calls == 1
    assert b.damage_batch_calls == 1                     # NOT 2 -- outgoing was cache-served
    assert oracle.cache_hits > 0                          # the outgoing requests hit the scoring cache


# --------------------------------------------------------------------------- T4
class _RaiseAfter:
    def __init__(self, ok):
        self.ok = ok
        self.calls = 0

    def calc_batch(self, requests):
        self.calls += 1
        if self.calls > self.ok:
            raise CalcError("injected calc failure")
        return [DamageResult(min_damage=1, max_damage=2, max_hp=200, id=r.id) for r in requests]


def test_calcerror_in_shared_first_flush_propagates_through_choose_best():
    oracle = DamageOracle(client=CalcClient(backend=_RaiseAfter(ok=0)))
    with pytest.raises(CalcError):
        _run_mega(oracle=oracle, trace=None)


def test_outgoing_flush_is_cache_served_at_the_decision_level():
    """Through _choose_best the conditional outgoing makes NO second backend call (its requests are
    served from the scoring cache), so a calc that raises AFTER the first flush never fires -- the
    outgoing has no decision-level error surface, which is exactly why the outgoing fail-closed case
    is a game_mode-unit test (below)."""
    backend = _RaiseAfter(ok=1)  # would raise on any 2nd backend call
    oracle = DamageOracle(client=CalcClient(backend=backend))
    _run_mega(oracle=oracle, trace=None)  # must NOT raise
    assert backend.calls == 1  # exactly one backend flush; the outgoing was cache-served


def test_calcerror_in_conditional_outgoing_flush_propagates_fail_closed():
    """game_mode unit: the outgoing flush is the ONLY place the outgoing calc is issued when its
    requests are uncached. Incoming flush succeeds, threatened == 0, then the outgoing flush raises."""
    backend = _RaiseAfter(ok=1)
    oracle = DamageOracle(client=CalcClient(backend=backend))
    handle = gm.enqueue_base_game_mode(_gating_state(), our_side="p1", oracle=oracle, book=BOOK)
    oracle.flush()  # incoming resolves (min_damage=1 -> not a guaranteed OHKO -> threatened == 0)
    with pytest.raises(CalcError):
        gm.resolve_base_game_mode(handle, oracle=oracle)
    assert backend.calls >= 2  # the second (outgoing) flush was the one that raised


# --------------------------------------------------------------------------- T8
def test_mode_resolver_fires_once_and_returns_the_pre_fold_mode_across_two_worlds(monkeypatch):
    """Two genuinely-sampled worlds: the memoized resolver runs EXACTLY once and returns the same
    GameMode the eager pre-fold classifier would -- so both worlds are scored with the unchanged mode."""
    world1 = SpeciesSpreads(offense=SpreadPreset(nature="Hardy", evs={}),
                            defense=SpreadPreset(nature="Hardy", evs={}))
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    monkeypatch.setattr(mega_scoring, "build_world_dist", lambda *a, **k: {"aerodactyl": [(world1, 1.0)]})
    monkeypatch.setattr(mega_scoring, "sample_worlds",
                        lambda *a, **k: [({}, 0.7), ({"aerodactyl": world1}, 0.3)])
    calls = {"n": 0, "modes": []}
    real = gm.resolve_classification

    def _spy(*a, **k):
        m = real(*a, **k)
        calls["n"] += 1
        calls["modes"].append(m)
        return m
    monkeypatch.setattr(decision, "resolve_classification", _spy)

    # what the pre-fold eager classifier produces on this board (the mode that must be consumed)
    pre_fold_mode = gm.classify_game_mode(
        _gating_state(), our_side="p1", calc=DamageOracle().client, book=BOOK)

    trace = DecisionTrace()
    _run_mega(trace=trace)
    assert calls["n"] == 1, f"resolver fired {calls['n']} times (expected 1)"
    assert calls["modes"][0] == pre_fold_mode          # same mode consumed as pre-fold
    assert len(trace.candidates[0].score_vector) > 7   # both worlds were evaluated (pooled vector)


# --------------------------------------------------------------------------- T9
def test_injected_calc_receives_the_exact_classification_requests(monkeypatch):
    """A default calc backend must NEVER be constructed, and the injected client must receive the
    EXACT classification incoming request keys (own and opponent are both Aerodactyl, so a species
    check is insufficient -- we match full DamageOracle keys)."""
    monkeypatch.setattr(
        "showdown_bot.engine.calc.client.make_calc_backend",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("a default calc backend must not be built")),
    )
    # capture the EXACT classification incoming keys the DECISION enqueues (same profile/state)
    captured_keys: set = set()
    real_enq = gm.enqueue_classification

    def _spy_enq(*a, **k):
        h = real_enq(*a, **k)
        captured_keys.update(h.keys)
        return h
    monkeypatch.setattr(decision, "enqueue_classification", _spy_enq)

    received: list = []

    class _Rec:
        def calc_batch(self, requests):
            received.extend(requests)
            return [DamageResult(min_damage=1, max_damage=2, max_hp=200, id=r.id) for r in requests]

    _run_mega(oracle=DamageOracle(client=CalcClient(backend=_Rec())), trace=None)
    assert captured_keys  # the board really does issue classification incoming requests
    received_keys = {DamageOracle._key(r) for r in received}
    # every classification incoming request was resolved by the injected client (via the shared flush)
    assert captured_keys <= received_keys

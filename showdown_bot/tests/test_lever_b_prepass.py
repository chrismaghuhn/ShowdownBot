"""Lever B, T5: reordered, gated, best-effort decision-start pre-pass.

The pre-pass coalesces the early, world-invariant board stats+types into ONE shared mixed
transport and seeds the speed + dex caches, so the lazy path (type-enrichment, opponent modeling,
_opponent_speed) becomes a pure cache hit. It is gated on a shared backend/generation, disables
its speed half in K-world, and on ANY mixed transport failure injects nothing and falls back to
the unchanged lazy path. Late Mega-form speeds (speed_for_species) stay lazy by design.

The transport-COUNT counterproofs use a deterministic fake backend that mimics the calc counter
surface exactly (call counting must not depend on Node flakiness); behaviour-neutrality of the
VALUES is proven separately by the golden decision-equivalence suite (T6). One real-Node end-to-end
proves the pre-pass fires inside the reordered decision.
"""
from __future__ import annotations

import pytest

from showdown_bot.battle.decision import _choose_best, _decision_start_prepass
from showdown_bot.battle.opponent import SpeciesDex, _opponent_speed
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
from showdown_bot.engine.calc.client import CalcClient, CalcError, SubprocessCalcBackend
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
_BOARD_SPECIES = ("Aerodactyl", "Whimsicott", "Landorus-Therian")


class _FakeBackend:
    """Deterministic calc backend mimicking the real counter surface, so pre-pass transport COUNTS
    and cache seeding are provable without Node flakiness."""

    def __init__(self):
        self.stats_batch_calls = 0
        self.types_batch_calls = 0
        self.mixed_batch_calls = 0
        self.transport_attempts = 0
        self.spawn_count = 0

    def stats_batch(self, specs, *, gen=9):
        if not specs:
            return []
        self.stats_batch_calls += 1
        self.spawn_count += 1
        self.transport_attempts += 1
        return [{"spe": 100} for _ in specs]

    def types_batch(self, species):
        if not species:
            return []
        self.types_batch_calls += 1
        self.spawn_count += 1
        self.transport_attempts += 1
        return [["Normal"] for _ in species]

    def mixed_batch(self, specs, species, *, gen=9):
        if not specs and not species:
            return [], []
        self.mixed_batch_calls += 1
        self.spawn_count += 1
        self.transport_attempts += 1
        return [{"spe": 100} for _ in specs], [["Normal"] for _ in species]


class _MixedRaises(_FakeBackend):
    """Real per-kind transports, but mixed_batch fails at the transport level (timeout/process).
    The failed attempt is still counted, exactly like the real mixed_batch."""

    def mixed_batch(self, specs, species, *, gen=9):
        if not specs and not species:
            return [], []
        self.mixed_batch_calls += 1
        self.spawn_count += 1
        self.transport_attempts += 1
        raise CalcError("injected mixed transport failure")


class _MixedAttrError(_FakeBackend):
    """mixed_batch raises a PROGRAMMING error (not a transport error), which must NOT be masked."""

    def mixed_batch(self, specs, species, *, gen=9):
        raise AttributeError("a bug in mixed_batch must not be swallowed as a cache miss")


def _shared(backend=None):
    b = backend or _FakeBackend()
    return CalcClient(backend=b), SpeedOracle(stats_backend=b, profile=CP), SpeciesDex(b)


def _board():
    """Foe-Mega board whose mons carry NO cached typing, so the lazy path really would call
    dex.types() and _opponent_speed() -- the pre-pass must warm both."""
    st = BattleState()
    a = PokemonState(species="Aerodactyl", base_species_id="aerodactyl", hp=100, max_hp=100)
    a.move_names = {"Rock Slide"}
    b = PokemonState(species="Whimsicott", base_species_id="whimsicott", hp=100, max_hp=100)
    b.move_names = {"Moonblast"}
    opp = PokemonState(species="Landorus-Therian", base_species_id="landorustherian",
                       hp=100, max_hp=100)
    opp.move_names = {"Earthquake"}
    st.sides["p1"]["a"], st.sides["p1"]["b"], st.sides["p2"]["a"] = a, b, opp
    return st


def _prepass(calc, speed_oracle, dex, st, *, opp_sets=None):
    _decision_start_prepass(
        st, our_side="p1", opp_side="p2", calc=calc, speed_oracle=speed_oracle, dex=dex,
        book=BOOK, opp_sets=opp_sets, calc_profile=CP,
    )


def _drive_early_consumers(speed_oracle, dex, st):
    for sp in _BOARD_SPECIES:
        dex.types(sp)
    _opponent_speed(st.sides["p2"]["a"], st.field, "p2",
                    speed_oracle=speed_oracle, book=BOOK, opp_sets=None)


# ---- the hard-pinned RED baseline (unwarmed) -----------------------------------------------

def test_unwarmed_baseline_is_nonzero():
    """Pins the RED baseline: WITHOUT the pre-pass the early consumers spawn exactly
    3 types_batch (one per board species) + 1 stats_batch (opponent_range's three specs in one
    batch). The phase-snapshot below proves the pre-pass collapses these to 0."""
    calc, speed_oracle, dex = _shared()
    _drive_early_consumers(speed_oracle, dex, _board())
    b = calc.backend
    assert b.types_batch_calls == 3
    assert b.stats_batch_calls == 1
    assert b.mixed_batch_calls == 0


# ---- P1.2: phase-snapshot counterproof -----------------------------------------------------

def test_prepass_phase_snapshot_early_consumers_zero():
    calc, speed_oracle, dex = _shared()
    st = _board()
    _prepass(calc, speed_oracle, dex, st)
    b = calc.backend
    # exactly ONE shared mixed transport; the pre-pass issues no separate stats/types spawn
    assert b.mixed_batch_calls == 1
    assert (b.stats_batch_calls, b.types_batch_calls) == (0, 0)
    # the EARLY consumers now hit the warm caches -> zero additional spawns (vs the 3 + 1 baseline)
    _drive_early_consumers(speed_oracle, dex, st)
    assert (b.stats_batch_calls, b.types_batch_calls) == (0, 0)
    assert b.mixed_batch_calls == 1


# ---- P1.1: best-effort fallback on a mixed transport failure -------------------------------

def test_prepass_mixed_error_falls_back_to_lazy():
    calc, speed_oracle, dex = _shared(_MixedRaises())
    st = _board()
    _prepass(calc, speed_oracle, dex, st)
    b = calc.backend
    # the failed mixed attempt is counted; NOTHING was injected (no partial cache)
    assert b.mixed_batch_calls == 1
    assert b.stats_batch_calls == 0 and b.types_batch_calls == 0
    assert dex._cache == {} and speed_oracle._spe_cache == {}
    # the unchanged lazy path still runs: types via types_batch, speed via stats_batch
    _drive_early_consumers(speed_oracle, dex, st)
    assert b.types_batch_calls == 3 and b.stats_batch_calls == 1


# ---- backend-topology guard ----------------------------------------------------------------

def test_prepass_disabled_on_mismatched_backend():
    calc = CalcClient(backend=_FakeBackend())
    other = _FakeBackend()                           # a DIFFERENT backend for speed/dex
    speed_oracle = SpeedOracle(stats_backend=other, profile=CP)
    dex = SpeciesDex(other)
    _prepass(calc, speed_oracle, dex, _board())
    # guard tripped: no mixed transport on either backend, no cross-injection
    assert calc.backend.mixed_batch_calls == 0 and other.mixed_batch_calls == 0
    assert dex._cache == {} and speed_oracle._spe_cache == {}


def test_prepass_disabled_on_generation_mismatch():
    import dataclasses

    calc, _, dex = _shared()
    # same backend as calc/dex, but a profile whose generation differs from calc_profile's
    speed_oracle = SpeedOracle(
        stats_backend=calc.backend, profile=dataclasses.replace(CP, generation=CP.generation + 1)
    )
    _prepass(calc, speed_oracle, dex, _board())      # _prepass passes calc_profile=CP
    assert calc.backend.mixed_batch_calls == 0       # guard tripped on the generation mismatch
    assert dex._cache == {} and speed_oracle._spe_cache == {}


def test_prepass_passes_the_profile_generation_to_mixed_batch():
    """P1: the pre-pass must compute stats at the profile's generation, not the gen-9 default --
    else a stat computed as gen 9 would be cached (via _spec_key) under a gen-N key, a wrong hit.
    Types stay gen 9 internally, matching types_batch."""
    import dataclasses

    class _GenRec(_FakeBackend):
        def __init__(self):
            super().__init__()
            self.mixed_gen = None

        def mixed_batch(self, specs, species, *, gen=9):
            self.mixed_gen = gen
            return super().mixed_batch(specs, species, gen=gen)

    backend = _GenRec()
    gen8 = dataclasses.replace(CP, generation=8)       # matches the calc_profile passed below
    calc = CalcClient(backend=backend)
    speed_oracle = SpeedOracle(stats_backend=backend, profile=gen8)
    dex = SpeciesDex(backend)
    _decision_start_prepass(
        _board(), our_side="p1", opp_side="p2", calc=calc, speed_oracle=speed_oracle,
        dex=dex, book=BOOK, opp_sets=None, calc_profile=gen8,
    )
    assert backend.mixed_batch_calls == 1
    assert backend.mixed_gen == 8                       # stats computed at the profile's generation


# ---- K-world: types warmed, speed left lazy ------------------------------------------------

def test_prepass_speed_disabled_in_k_world(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    calc, speed_oracle, dex = _shared()
    _prepass(calc, speed_oracle, dex, _board())
    b = calc.backend
    assert b.mixed_batch_calls == 1                  # types still warmed (one mixed, types-only)
    for sp in _BOARD_SPECIES:
        dex.types(sp)
    assert b.types_batch_calls == 0                  # types were warmed
    assert speed_oracle._spe_cache == {}             # speed was NOT seeded in K-world


# ---- likely-speed mon: single spec, no range prefetch --------------------------------------

def test_prepass_no_range_prefetch_for_likely_speed_mon():
    from showdown_bot.battle.opponent import opp_speed_branch

    _, speed_oracle, _ = _shared()
    opp = _board().sides["p2"]["a"]
    branch = opp_speed_branch(opp, {"landorustherian": SPREADS})
    assert branch.use_likely is True
    specs = speed_oracle.specs_for_branch(opp, BOOK, branch)
    assert len(specs) == 1                           # likely_speed path: one spec, no range prefetch


# ---- P1.1: a warm dex/speed cache (reused across the battle) adds no transport --------------

def test_prepass_skips_transport_when_caches_are_warm():
    calc, speed_oracle, dex = _shared()
    _prepass(calc, speed_oracle, dex, _board())
    assert calc.backend.mixed_batch_calls == 1       # first decision warms the board
    _prepass(calc, speed_oracle, dex, _board())      # second decision, SAME oracles/caches
    assert calc.backend.mixed_batch_calls == 1       # +0: everything was already warm, no re-send


# ---- P1.3: only CalcError is best-effort; a programming error must surface ------------------

def test_prepass_does_not_swallow_programming_errors():
    calc, speed_oracle, dex = _shared(_MixedAttrError())
    with pytest.raises(AttributeError):
        _prepass(calc, speed_oracle, dex, _board())


# ---- end-to-end: the reordered real-Node decision issues exactly one mixed_batch ------------

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
    """The proven Lever A foe-Mega board (opponent Aerodactyl, typings already set)."""
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


def test_prepass_runs_once_in_the_real_decision():
    backend = SubprocessCalcBackend()
    calc = CalcClient(backend=backend)
    oracle = DamageOracle(client=calc)
    speed_oracle = SpeedOracle(stats_backend=backend, profile=CP)
    dex = SpeciesDex(backend)
    _choose_best(
        _gating_req(), state=_gating_state(), book=BOOK, our_side="p1",
        calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
        our_spreads={"aerodactyl": SPREADS, "whimsicott": SPREADS},
        format_config=CHAMPIONS, risk_lambda=0.0,
    )
    # exactly one shared board pre-warm; late Mega speed_for_species stats are counted separately
    assert backend.mixed_batch_calls == 1

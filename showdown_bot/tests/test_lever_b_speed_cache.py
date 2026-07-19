"""Lever B, T3: SpeedOracle exact cache-first opponent_range + seed_results + specs_for_branch.

opponent_range must check the exact (gen + full CalcMon payload) cache first and batch only the
cold misses into ONE stats_batch (never one-per-spec, never split), stay byte-identical in its
SpeedRange, and be seedable with zero transport via seed_results. specs_for_branch returns exactly
the specs the lazy path would build for a given opponent-speed branch (here the three range specs
when no curated set applies); the branch itself is decided once in battle.opponent.opp_speed_branch.
"""
from __future__ import annotations

from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.speed import SpeedOracle, effective_speed
from showdown_bot.engine.state import FieldState, PokemonState


class _RecBackend:
    """Records each stats_batch's specs and returns a deterministic spe per spec, keyed by
    nature so min/likely/max stay distinguishable and a wrong cache hit surfaces as a wrong
    value. types_batch present for parity with the real backend surface."""

    def __init__(self):
        self.batches: list[list] = []

    @staticmethod
    def _spe(s):
        return {"Brave": 80, "Jolly": 150}.get(s.nature, 110)

    def stats_batch(self, specs, *, gen=9):
        self.batches.append(list(specs))
        return [{"spe": self._spe(s)} for s in specs]

    def types_batch(self, species):
        return [["Normal"] for _ in species]

    @property
    def n_batches(self) -> int:
        return len(self.batches)

    @property
    def total_specs(self) -> int:
        return sum(len(b) for b in self.batches)


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _oracle():
    return SpeedOracle(stats_backend=_RecBackend())


_MON = PokemonState(species="Flutter Mane")


def test_opponent_range_cold_miss_one_batch():
    o = _oracle()
    o.opponent_range(_MON, FieldState(), "p2", book=_book())
    assert o.backend.n_batches == 1            # ONE batch, not one per spec
    assert o.backend.total_specs == 3          # all three cold specs in it


def test_opponent_range_byte_identical():
    o = _oracle()
    rng1 = o.opponent_range(_MON, FieldState(), "p2", book=_book())
    rng2 = o.opponent_range(_MON, FieldState(), "p2", book=_book())
    assert (rng1.min, rng1.likely, rng1.max) == (80, 110, effective_speed(150, scarf=True))
    assert rng1 == rng2                        # cache-first does not perturb the result


def test_opponent_range_warm_zero_transport():
    o = _oracle()
    o.opponent_range(_MON, FieldState(), "p2", book=_book())
    o.opponent_range(_MON, FieldState(), "p2", book=_book())
    assert o.backend.n_batches == 1            # the warm second call issues no new transport


def test_opponent_range_partial_hit_one_batch():
    o = _oracle()
    specs = o._range_specs(_MON, _book())      # the exact three specs opponent_range uses
    o.seed_results([(specs[1], {"spe": 110})])  # pre-seed only the likely one
    assert o.backend.n_batches == 0            # seeding is transport-free
    rng = o.opponent_range(_MON, FieldState(), "p2", book=_book())
    assert o.backend.n_batches == 1            # the two remaining misses go in ONE batch
    assert o.backend.total_specs == 2
    assert rng.likely == effective_speed(110)  # the seeded value was used


def test_seed_results_no_io():
    o = _oracle()
    specs = o._range_specs(_MON, _book())
    o.seed_results([(s, {"spe": 111}) for s in specs])
    assert o.backend.n_batches == 0            # pure cache injection, no spawn
    o.opponent_range(_MON, FieldState(), "p2", book=_book())
    assert o.backend.n_batches == 0            # every spec was a hit


def test_specs_for_branch_range_matches_range_specs():
    from showdown_bot.battle.opponent import opp_speed_branch

    o = _oracle()
    # No curated set -> the shared branch is the opponent_range path, so specs_for_branch returns
    # exactly the three range specs (the likely-set branch is proven in test_lever_b_prepass).
    branch = opp_speed_branch(_MON, None)
    assert branch.use_likely is False
    specs = o.specs_for_branch(_MON, _book(), branch)
    expected = o._range_specs(_MON, _book())
    assert [s.to_payload() for s in specs] == [s.to_payload() for s in expected]

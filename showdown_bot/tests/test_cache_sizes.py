"""I8-A Task A3 — semantic cache sizes, readable at rep start.

Design `docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md` (Rev. 11) §2.8:
`cache_class` is derived from the arm's declared lifecycle and then FALSIFIED by three
observed cache sizes sampled at rep start. Only one direction is sound and it rests
entirely on the fact pinned here:

    cache_class == "cold"  =>  all three sizes are 0

A freshly constructed cache is *provably* empty, because each __init__ sets it to {}
(oracle.py:24, speed.py:103, opponent.py:45). So a non-empty cache at rep start disproves
a declared per_rep lifecycle -- catching a harness that reuses an object it said was fresh,
which plain manifest-equality cannot.

The CONVERSE is deliberately not tested and not asserted anywhere: "warm => sizes > 0" is
unsound (a reused SpeciesDex on a board whose species were never looked up is legitimately
empty). Design §9 entries 23/51 record two revisions that shipped exactly that kind of
over-strict rule and would have rejected real, successful rows.

These are reads of attributes that already exist. A3 adds no interface.
"""

from __future__ import annotations

import pytest

from showdown_bot.battle.opponent import SpeciesDex
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.speed import SpeedOracle


class _FakeStatsBackend:
    """Answers stats/types without Node."""

    def stats_batch(self, specs, *, gen: int = 9):
        return [{"spe": 100} for _ in specs]

    def types_batch(self, species):
        return [["Fire"] for _ in species]

    def close(self) -> None:
        pass


def _cache_probes():
    return [
        ("damage", DamageOracle(), lambda o: len(o._cache)),
        ("speed", SpeedOracle(stats_backend=_FakeStatsBackend()), lambda o: len(o._spe_cache)),
        ("dex", SpeciesDex(_FakeStatsBackend()), lambda o: len(o._cache)),
    ]


@pytest.mark.parametrize("name, obj, probe", _cache_probes(), ids=lambda v: getattr(v, "__name__", str(v))[:12])
def test_a_freshly_constructed_cache_is_empty(name, obj, probe):
    # The empirical basis for the design's ONLY sound cache direction.
    # Pinned by test, never by inspection.
    assert probe(obj) == 0


def test_the_three_caches_are_reachable_by_the_names_the_design_cites():
    # The design's validator cites these three attributes by name (oracle.py:24,
    # speed.py:103, opponent.py:45). If any is renamed, the profile silently loses
    # its falsifier -- so the names are part of the contract.
    assert isinstance(DamageOracle()._cache, dict)
    assert isinstance(SpeedOracle(stats_backend=_FakeStatsBackend())._spe_cache, dict)
    assert isinstance(SpeciesDex(_FakeStatsBackend())._cache, dict)


def test_speed_cache_grows_on_a_resolved_lookup_and_is_reused():
    oracle = SpeedOracle(stats_backend=_FakeStatsBackend())
    assert len(oracle._spe_cache) == 0

    oracle._base_speed("Incineroar", "Careful", {"hp": 252})
    assert len(oracle._spe_cache) == 1

    oracle._base_speed("Incineroar", "Careful", {"hp": 252})   # same key -> cache hit
    assert len(oracle._spe_cache) == 1


def test_dex_cache_grows_on_a_resolved_lookup_and_is_reused():
    dex = SpeciesDex(_FakeStatsBackend())
    assert len(dex._cache) == 0

    dex.types("Incineroar")
    assert len(dex._cache) == 1

    dex.types("Incineroar")
    assert len(dex._cache) == 1


def test_a_reused_cache_carries_entries_across_reps_which_is_what_cold_must_disprove():
    # The scenario the falsifier exists for: an arm declares per_rep, but the harness
    # hands the SAME oracle to rep 1. Its cache is non-empty at rep start, which
    # disproves the declared lifecycle. Without this observation, the row could claim
    # cold, match the manifest, and silently measure a warm cache.
    reused = SpeedOracle(stats_backend=_FakeStatsBackend())
    reused._base_speed("Incineroar", "Careful", {"hp": 252})   # "rep 0"

    size_at_rep_1_start = len(reused._spe_cache)               # sampled at rep start

    assert size_at_rep_1_start > 0        # a genuinely cold rep could never report this
    assert len(SpeedOracle(stats_backend=_FakeStatsBackend())._spe_cache) == 0

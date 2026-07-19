"""Lever B, T4: SpeciesDex.seed_results — transport-free cache seeding.

The decision-start pre-pass computes board-species typings once (in the shared mixed_batch) and
injects them here; a subsequent dex.types() for a seeded species must be a pure cache hit with no
types_batch spawn. seed_results itself never touches the backend.
"""
from __future__ import annotations

from showdown_bot.battle.opponent import SpeciesDex


class _RecDex:
    """Counts types_batch calls; a seeded read must not reach it."""

    def __init__(self):
        self.calls = 0

    def types_batch(self, species):
        self.calls += 1
        return [["Fire"] for _ in species]


def test_seeded_dex_zero_spawn():
    b = _RecDex()
    dex = SpeciesDex(b)
    dex.seed_results([("Charizard", ["Fire", "Flying"])])
    assert b.calls == 0                              # seeding is transport-free
    assert dex.types("Charizard") == ["Fire", "Flying"]
    assert b.calls == 0                              # the read hit the seeded cache, no spawn


def test_dex_seed_results_no_io():
    b = _RecDex()
    dex = SpeciesDex(b)
    dex.seed_results([("Venusaur", ["Grass", "Poison"]), ("Blastoise", ["Water"])])
    assert b.calls == 0
    assert dex.types("Venusaur") == ["Grass", "Poison"]
    assert dex.types("Blastoise") == ["Water"]
    assert b.calls == 0

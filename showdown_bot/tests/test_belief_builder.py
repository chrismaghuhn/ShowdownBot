"""Tests for learning/belief_builder.py — Task D2a: BeliefSide + _quality + build_known_side.

PokemonSlot fields (confirmed from models/request.py + fixture request_doubles_moves.json):
  ident      : str  e.g. "p1: Incineroar"
  details    : str  e.g. "Incineroar, L50, F"
  condition  : str  e.g. "150/150"
  active     : bool
  stats      : dict[str, int]  e.g. {"atk":100,"def":100,"spa":100,"spd":100,"spe":100}
  moves      : list[str]  — move ids  e.g. ["fakeout","flareblitz","protect","knockoff"]

Species parse: parse_details(slot.details).species  (engine/state.py)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.learning.belief_builder import BeliefSide, _quality, build_known_side
from showdown_bot.models.request import BattleRequest, PokemonSlot

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture: real team_slots from request_doubles_moves.json
# ---------------------------------------------------------------------------

@pytest.fixture
def known_team_slots() -> list[PokemonSlot]:
    """Return req.side.pokemon (4 PokemonSlots: 2 active, 2 bench) from the
    canonical doubles fixture. This is the exact input shape build_known_side expects."""
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    return req.side.pokemon


# ---------------------------------------------------------------------------
# Task D2a tests
# ---------------------------------------------------------------------------

def test_quality_ok_when_no_flags():
    assert _quality() == ("ok",)


def test_quality_sorted_deduped_flags():
    result = _quality("weak_speed_fallback", "no_move_prior", "no_move_prior")
    assert result == ("no_move_prior", "weak_speed_fallback")


def test_build_known_side_includes_full_team(known_team_slots):
    """build_known_side must include ALL team mons in movesets/stats/quality,
    and bench mons (active=False) must appear in roster."""
    bs = build_known_side(known_team_slots)

    assert isinstance(bs, BeliefSide)

    # All four slots must have movesets, stats, quality entries
    assert set(bs.movesets.keys()) == {slot.ident for slot in known_team_slots}
    assert set(bs.stats.keys()) == {slot.ident for slot in known_team_slots}
    assert set(bs.quality.keys()) == {slot.ident for slot in known_team_slots}

    # Bench mons (active=False) must appear in roster
    bench_idents = {slot.ident for slot in known_team_slots if not slot.active}
    assert bench_idents, "fixture must have at least one bench mon"
    assert set(bs.roster.keys()) == bench_idents

    # Active mons must NOT appear in roster (roster = bench only)
    active_idents = {slot.ident for slot in known_team_slots if slot.active}
    for ident in active_idents:
        assert ident not in bs.roster

    # All quality values must be ("ok",) — our team is fully known
    assert all(q == ("ok",) for q in bs.quality.values()), (
        f"Expected all quality ('ok',), got: {bs.quality}"
    )


def test_build_known_side_movesets_match_slot(known_team_slots):
    """Each slot's movesets[ident] must equal list(slot.moves)."""
    bs = build_known_side(known_team_slots)
    for slot in known_team_slots:
        assert bs.movesets[slot.ident] == list(slot.moves), (
            f"moveset mismatch for {slot.ident}"
        )


def test_build_known_side_spe_stat(known_team_slots):
    """stats[ident]['spe'] must equal slot.stats['spe'] for every slot."""
    bs = build_known_side(known_team_slots)
    for slot in known_team_slots:
        assert bs.stats[slot.ident] == {"spe": slot.stats["spe"]}, (
            f"spe mismatch for {slot.ident}"
        )


def test_build_known_side_returns_fresh_containers(known_team_slots):
    """Two calls must return independent containers (no shared mutation risk)."""
    bs1 = build_known_side(known_team_slots)
    bs2 = build_known_side(known_team_slots)
    assert bs1 is not bs2
    assert bs1.movesets is not bs2.movesets
    assert bs1.roster is not bs2.roster


def test_belief_side_is_frozen(known_team_slots):
    """BeliefSide must be a frozen dataclass (attribute reassignment raises)."""
    bs = build_known_side(known_team_slots)
    with pytest.raises((AttributeError, TypeError)):
        bs.roster = {}  # type: ignore[misc]

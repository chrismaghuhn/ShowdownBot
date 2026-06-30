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


# ---------------------------------------------------------------------------
# Task D2b fixtures
# ---------------------------------------------------------------------------

from showdown_bot.engine.state import BattleState, PokemonState  # noqa: E402


@pytest.fixture
def opp_state() -> BattleState:
    """Minimal BattleState with p2 having two active mons (Incineroar + Flutter Mane)."""
    s = BattleState()
    s.sides["p1"]["a"] = PokemonState(species="Rillaboom", hp=200, max_hp=200)
    s.sides["p1"]["b"] = PokemonState(species="Urshifu", hp=180, max_hp=180)
    s.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150, moves=set())
    s.sides["p2"]["b"] = PokemonState(species="Flutter Mane", hp=120, max_hp=120, moves=set())
    return s


@pytest.fixture
def opp_state_with_revealed() -> BattleState:
    """p2 has Incineroar in slot 'a' with fakeout already revealed."""
    s = BattleState()
    s.sides["p1"]["a"] = PokemonState(species="Rillaboom", hp=200, max_hp=200)
    s.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150, moves={"fakeout"})
    return s


@pytest.fixture
def opp_state_no_moves() -> BattleState:
    """p2 has Incineroar with no revealed moves and no priors will be supplied."""
    s = BattleState()
    s.sides["p1"]["a"] = PokemonState(species="Rillaboom", hp=200, max_hp=200)
    s.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150, moves=set())
    return s


# ---------------------------------------------------------------------------
# Task D2b tests
# ---------------------------------------------------------------------------

from showdown_bot.learning.belief_builder import (  # noqa: E402
    FALLBACK_BELIEF_MOVE,
    build_opponent_belief,
)


def test_opp_roster_is_empty_and_keys_are_active_only(opp_state):
    """Opponent belief must have empty roster and only active species as keys."""
    bs = build_opponent_belief(opp_state, "p2", likely_sets={}, move_priors={})
    assert bs.roster == {}
    # Only the two active p2 mons should be keyed (by species)
    assert set(bs.movesets) == {"Incineroar", "Flutter Mane"}


def test_revealed_moves_first_then_prior_fill_dedupe_cap4(opp_state_with_revealed):
    """Revealed moves come first; prior fills; deduplication; cap at 4."""
    # Incineroar revealed {"fakeout"}; prior has fakeout + 4 more (5 total)
    mp = {"incineroar": ["fakeout", "knockoff", "flareblitz", "partingshot", "uturn"]}
    bs = build_opponent_belief(
        opp_state_with_revealed, "p2", likely_sets={}, move_priors=mp
    )
    # revealed "fakeout" first, then knockoff/flareblitz/partingshot from prior (uturn cut by cap)
    assert bs.movesets["Incineroar"] == ["fakeout", "knockoff", "flareblitz", "partingshot"]


def test_no_prior_no_revealed_uses_fallback_and_flags(opp_state_no_moves):
    """When no moves and no priors, moveset is [FALLBACK_BELIEF_MOVE] + 'no_move_prior' flag."""
    bs = build_opponent_belief(opp_state_no_moves, "p2", likely_sets={}, move_priors={})
    assert bs.movesets["Incineroar"] == [FALLBACK_BELIEF_MOVE]
    assert "no_move_prior" in bs.quality["Incineroar"]


def test_hidden_bench_like_entry_is_ignored(opp_state):
    """Injecting a non-active key into state.sides['p2'] must NOT appear in belief."""
    # This is the limited-view safety gate
    opp_state.sides["p2"]["c"] = PokemonState(
        species="Calyrex-Shadow", hp=180, max_hp=180, moves=set()
    )
    bs = build_opponent_belief(opp_state, "p2", likely_sets={}, move_priors={})
    assert "Calyrex-Shadow" not in bs.movesets
    assert "Calyrex-Shadow" not in bs.stats
    assert "Calyrex-Shadow" not in bs.quality


def test_build_opponent_belief_has_no_known_team_param():
    """API guard: signature must not expose known_team, team, or full_roster."""
    import inspect
    params = inspect.signature(build_opponent_belief).parameters
    assert "known_team" not in params
    assert "team" not in params
    assert "full_roster" not in params


def test_opp_belief_keys_are_consistent(opp_state):
    """movesets, stats, quality must all share the same key set."""
    bs = build_opponent_belief(opp_state, "p2", likely_sets={}, move_priors={})
    assert set(bs.movesets) == set(bs.stats) == set(bs.quality)


# ---------------------------------------------------------------------------
# Task D3: build_belief_for_side dispatcher + integration
# ---------------------------------------------------------------------------

from showdown_bot.learning.belief_builder import build_belief_for_side  # noqa: E402


@pytest.fixture
def state_for_belief(known_team_slots) -> "BattleState":
    """BattleState whose p1 active mons match the known_team_slots fixture.

    request_doubles_moves.json has p1 active: Incineroar + Rillaboom.
    p2 active: Incineroar (as a placeholder to exercise the opp builder).
    """
    s = BattleState()
    s.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    s.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    s.sides["p2"]["a"] = PokemonState(
        species="Flutter Mane", hp=120, max_hp=120, moves=set()
    )
    s.sides["p2"]["b"] = PokemonState(
        species="Tornadus", hp=140, max_hp=140, moves=set()
    )
    return s


def test_dispatcher_routes_to_known_for_our_side(state_for_belief, known_team_slots):
    """side == our_side → build_known_side path; produces a non-empty belief."""
    bs = build_belief_for_side(
        state_for_belief, "p1",
        our_side="p1", known_team=known_team_slots,
        likely_sets={}, move_priors={},
    )
    # known builder path: full team's movesets or roster must be non-empty
    assert bs.roster or bs.movesets, "known builder must produce non-empty belief"


def test_dispatcher_routes_to_opponent_for_opp_side(state_for_belief, known_team_slots):
    """side != our_side → opponent builder path; roster must be empty (hidden bench)."""
    bs = build_belief_for_side(
        state_for_belief, "p2",
        our_side="p1", known_team=known_team_slots,
        likely_sets={}, move_priors={},
    )
    assert bs.roster == {}, "opponent builder path must have empty bench (limited-view)"


def test_determinism(state_for_belief, known_team_slots):
    """Two identical build_belief_for_side calls must produce equal BeliefSide objects."""
    a = build_belief_for_side(
        state_for_belief, "p2",
        our_side="p1", known_team=known_team_slots,
        likely_sets={}, move_priors={},
    )
    b = build_belief_for_side(
        state_for_belief, "p2",
        our_side="p1", known_team=known_team_slots,
        likely_sets={}, move_priors={},
    )
    assert a == b, "build_belief_for_side must be deterministic"


def test_belief_feeds_rollout_labels(state_for_belief, known_team_slots):
    """Integration: BeliefSide → per-side dicts → decide() returns a non-None JointAction.

    This is the 'deterministic belief source for rollout_labels' deliverable.
    No export-swap, no training: just prove the triple is consumable by decide().

    state_for_belief: p1 active = Incineroar + Rillaboom (matching known_team_slots).
    known_team_slots: req.side.pokemon from request_doubles_moves.json (4 slots, keyed
                      by ident e.g. 'p1: Incineroar').
    deps: stripped decision_fixture kw (book/calc/oracle/speed_oracle/dex).
    """
    import json
    from showdown_bot.learning.decide_adapter import decide
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.engine.moves import _move_table
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.calc.models import DamageResult
    from showdown_bot.engine.speed import SpeedRange

    class _FakeCalc:
        backend = None
        def damage_batch(self, requests):
            return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]

    class _FakeOracle:
        def request(self, req):
            return (req.attacker.species, req.move, req.defender.species)
        def get(self, key):
            return DamageResult(min_damage=45, max_damage=70, max_hp=150)
        def damage(self, req):
            return DamageResult(min_damage=45, max_damage=70, max_hp=150)
        def flush(self):
            pass

    class _FakeSpeed:
        def our_speed(self, base, mon, field, side):
            return base or 100
        def opponent_range(self, mon, field, side, *, book):
            return SpeedRange(min=80, likely=110, max=150)

    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    deps = dict(
        book=book,
        calc=_FakeCalc(),
        oracle=_FakeOracle(),
        speed_oracle=_FakeSpeed(),
    )

    meta = _move_table()

    # Build p1 (our side) belief from known team
    us = build_belief_for_side(
        state_for_belief, "p1",
        our_side="p1", known_team=known_team_slots,
        likely_sets={}, move_priors={},
    )
    # Build p2 (opponent) belief — prior-based, limited-view.
    # No speed_oracle here: _belief_speed falls through to (0, "weak_speed_fallback"),
    # which is fine — we only need the belief triple to be consumable by decide().
    opp = build_opponent_belief(
        state_for_belief, "p2",
        likely_sets={}, move_priors={},
        speed_oracle=None,
    )

    roster = {"p1": us.roster, "p2": opp.roster}
    movesets = {"p1": us.movesets, "p2": opp.movesets}
    stats = {"p1": us.stats, "p2": opp.stats}

    ja = decide(
        state_for_belief, "p1",
        roster=roster, movesets=movesets, stats=stats,
        move_meta=meta, deps=deps,
    )
    assert ja is not None, "decide() must return a JointAction (synthesized request was enumerable)"
    assert isinstance(ja, JointAction)

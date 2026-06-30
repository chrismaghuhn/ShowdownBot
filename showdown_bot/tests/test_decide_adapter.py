"""Tests for learning/decide_adapter.py — Task 2: synthesize_request.

Field names confirmed from models/request.py:
  BattleRequest: active, side, rqid, force_switch (alias forceSwitch), team_preview, wait
  SideInfo: name, id, pokemon
  PokemonSlot: ident, details, condition, active, stats, moves, base_types, item
  ActiveSlot: moves, can_terastallize (alias canTerastallize), trapped
  MoveSlot: move, id, pp, maxpp, target, disabled

Fainted active slot: active[i] = None  AND  force_switch[i] = True.
move_meta source: engine/moves.py  _move_table() / get_move_meta(mid).target
"""
from __future__ import annotations

import pytest

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.engine.moves import _move_table
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.learning.decide_adapter import synthesize_request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _move_meta():
    """Return the real move-meta map from engine/moves.py."""
    return _move_table()


def _state():
    """Minimal two-slot p1 side with one active mon, no bench."""
    s = BattleState()
    s.sides["p1"]["a"] = PokemonState(
        species="Incineroar", hp=200, max_hp=200,
    )
    # p2 active only — needed so state is valid but we never read their bench
    s.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    return s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_synthesized_request_is_enumerable():
    """A minimal 1-active-mon request must yield >= 1 legal joint action."""
    s = _state()
    roster = {"p1": {}}          # no bench
    stats = {"p1": {"Incineroar": {"spe": 90}}}
    movesets = {"p1": {"Incineroar": ["fakeout", "knockoff", "flareblitz", "partingshot"]}}
    req = synthesize_request(
        s, "p1",
        roster=roster, movesets=movesets, stats=stats,
        move_meta=_move_meta(),
    )
    assert req.side.id == "p1"
    assert req.active, "active list must not be empty"
    assert req.active[0] is not None, "living active slot must not be None"
    assert len(req.active[0].moves) >= 1
    acts = enumerate_my_actions(req, moved_since_switch=[False, False])
    assert acts, "enumerate_my_actions must return >= 1 legal action"


def test_force_switch_for_fainted_active():
    """The REAL gate: a fainted active slot produces switch-only actions from enumerate_my_actions.

    force_switch[0] must be True AND enumeration must yield NO move-kind action for slot0.
    """
    s = _state()
    # Faint the active mon
    s.sides["p1"]["a"].fainted = True
    s.sides["p1"]["a"].hp = 0

    # Provide a bench replacement
    bench = PokemonState(species="Rillaboom", hp=200, max_hp=200)
    roster = {"p1": {"p1: Rillaboom": bench}}
    movesets = {"p1": {"p1: Rillaboom": ["fakeout"]}}
    stats = {"p1": {"p1: Rillaboom": {"spe": 85}}}

    req = synthesize_request(
        s, "p1",
        roster=roster, movesets=movesets, stats=stats,
        move_meta=_move_meta(),
    )

    assert req.force_switch is not None
    assert req.force_switch[0] is True, "fainted active slot must set force_switch[0]=True"

    acts = enumerate_my_actions(req, moved_since_switch=[False, False])
    slot0_kinds = {ja.slot0.kind for ja in acts}
    assert "move" not in slot0_kinds, (
        f"fainted slot 0 must produce switch-only actions, got: {slot0_kinds}"
    )


def test_rqid_is_deterministic_synthetic():
    """synthesize_request must produce the same rqid on identical calls."""
    s = _state()
    base_kwargs = dict(
        roster={"p1": {}},
        movesets={"p1": {"Incineroar": ["fakeout", "knockoff"]}},
        stats={"p1": {"Incineroar": {"spe": 90}}},
        move_meta=_move_meta(),
    )
    r1 = synthesize_request(s, "p1", **base_kwargs)
    r2 = synthesize_request(s, "p1", **base_kwargs)
    assert r1.rqid == r2.rqid, "rqid must be deterministic for the same state+side"


def test_no_hidden_roster_read():
    """Requesting p2 with no caller-supplied roster/movesets/stats must raise, not read hidden state."""
    s = _state()
    with pytest.raises((ValueError, KeyError)):
        synthesize_request(
            s, "p2",
            roster={},          # p2 has NO entry
            movesets={},
            stats={},
            move_meta=_move_meta(),
        )

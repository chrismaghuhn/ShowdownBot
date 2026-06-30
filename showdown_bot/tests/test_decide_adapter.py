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


# ---------------------------------------------------------------------------
# Task 3: decide() + both-sides resolve_turn smoke
# ---------------------------------------------------------------------------

# Fakes from conftest (replicated here so tests are self-contained)
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


def _p1_beliefs(fixture_req):
    """Build p1 roster/movesets/stats matching the decision_fixture state.

    decision_fixture state has p1 active: Incineroar (slot a) + Rillaboom (slot b).
    Bench from the fixture request: Flutter Mane + Landorus (not in state — skip for
    synthesize_request which reads state for active slots only).
    """
    roster = {"p1": {}}  # no bench in the conftest _state()
    movesets = {
        "p1": {
            "Incineroar": ["fakeout", "flareblitz", "protect", "knockoff"],
            "Rillaboom": ["heatwave", "earthpower", "protect", "solarbeam"],
        }
    }
    stats = {
        "p1": {
            "Incineroar": {"spe": 100},
            "Rillaboom": {"spe": 100},
        }
    }
    return roster, movesets, stats


def _p2_fake_beliefs():
    """Build fake p2 belief for the decision_fixture opp side.

    decision_fixture state has p2 active: Flutter Mane (slot a) + Tornadus (slot b).
    We supply fake movesets/stats for both (belief-agnostic: caller supplies them).
    """
    roster = {"p2": {}}  # no bench — only two active mons in fixture state
    movesets = {
        "p2": {
            "Flutter Mane": ["moonblast", "shadowball", "protect", "dazzlinggleam"],
            "Tornadus": ["tailwind", "bleakwindstorm", "protect", "u-turn"],
        }
    }
    stats = {
        "p2": {
            "Flutter Mane": {"spe": 151},
            "Tornadus": {"spe": 120},
        }
    }
    return roster, movesets, stats


def test_decide_returns_jointaction(decision_fixture):
    """decide() must return a JointAction for the our-side p1."""
    from showdown_bot.learning.decide_adapter import decide
    from showdown_bot.battle.actions import JointAction

    req, kw = decision_fixture
    state = kw["state"]
    roster, movesets, stats = _p1_beliefs(req)

    # deps = kw minus state and our_side (decide passes those explicitly)
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    result = decide(
        state, "p1",
        roster=roster, movesets=movesets, stats=stats,
        move_meta=_move_meta(),
        deps=deps,
    )
    assert isinstance(result, JointAction), f"Expected JointAction, got {type(result)}"


def test_decide_both_sides_feed_resolve_turn(decision_fixture):
    """BOTH sides decide from the state; their JointActions plan + resolve_turn (the 1c goal).

    Grounded signatures:
      _plan_my_actions(req, ja, *, state, our_side, opp_side, speed_oracle) -> list[PlannedAction]
      resolve_turn(state, actions, damage_fn, *, our_side, field, tie_break) -> TurnOutcome
    """
    from showdown_bot.learning.decide_adapter import decide, synthesize_request
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.battle.decision import _plan_my_actions
    from showdown_bot.battle.resolve import resolve_turn, TurnOutcome

    req, kw = decision_fixture
    state = kw["state"]

    # Build per-side beliefs
    p1_roster, p1_movesets, p1_stats = _p1_beliefs(req)
    p2_roster, p2_movesets, p2_stats = _p2_fake_beliefs()

    # deps: sanitized to _CORE_DEP_KEYS — pass book/calc/oracle/speed_oracle/dex from fixture
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    meta = _move_meta()

    # Decide for both sides
    ja_p1 = decide(state, "p1", roster=p1_roster, movesets=p1_movesets, stats=p1_stats,
                   move_meta=meta, deps=deps)
    ja_p2 = decide(state, "p2", roster=p2_roster, movesets=p2_movesets, stats=p2_stats,
                   move_meta=meta, deps=deps)

    assert isinstance(ja_p1, JointAction)
    assert isinstance(ja_p2, JointAction)

    # Synthesize requests so _plan_my_actions can decode move indices
    req_p1 = synthesize_request(state, "p1", roster=p1_roster, movesets=p1_movesets,
                                stats=p1_stats, move_meta=meta)
    req_p2 = synthesize_request(state, "p2", roster=p2_roster, movesets=p2_movesets,
                                stats=p2_stats, move_meta=meta)

    speed_oracle = kw.get("speed_oracle")

    # Plan both sides' actions
    plan_p1 = _plan_my_actions(
        req_p1, ja_p1,
        state=state, our_side="p1", opp_side="p2",
        speed_oracle=speed_oracle,
    )
    plan_p2 = _plan_my_actions(
        req_p2, ja_p2,
        state=state, our_side="p2", opp_side="p1",
        speed_oracle=speed_oracle,
    )

    # Trivial damage_fn: 0.15 (non-KO chip; avoids needing a full DamageModel)
    def _fake_damage_fn(action, target_mon):
        return 0.15

    # Resolve the turn — must not raise; must return a TurnOutcome
    outcome = resolve_turn(
        state,
        plan_p1 + plan_p2,
        _fake_damage_fn,
        our_side="p1",
        field=state.field,
    )
    assert isinstance(outcome, TurnOutcome), f"Expected TurnOutcome, got {type(outcome)}"


def test_decide_is_deterministic(decision_fixture):
    """Identical inputs must produce identical JointAction.as_pair()."""
    from showdown_bot.learning.decide_adapter import decide

    req, kw = decision_fixture
    state = kw["state"]
    roster, movesets, stats = _p1_beliefs(req)
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}
    meta = _move_meta()

    a = decide(state, "p1", roster=roster, movesets=movesets, stats=stats,
               move_meta=meta, deps=deps)
    b = decide(state, "p1", roster=roster, movesets=movesets, stats=stats,
               move_meta=meta, deps=deps)

    assert a.as_pair() == b.as_pair(), (
        f"decide() is not deterministic: {a.as_pair()} != {b.as_pair()}"
    )

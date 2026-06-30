"""C1: make_resolve teacher adapter tests.

Ground truth for beliefs / fixture patterns from test_decide_adapter.py's
both-sides smoke test (_p1_beliefs / _p2_fake_beliefs helpers, exact param
names, how deps is assembled).
"""
from __future__ import annotations

import copy

from showdown_bot.engine.moves import _move_table


# ---------------------------------------------------------------------------
# Helpers — mirror test_decide_adapter.py belief builders exactly
# ---------------------------------------------------------------------------

def _p1_beliefs():
    """p1 roster/movesets/stats matching the conftest decision_fixture state.

    State has p1 active: Incineroar (slot a) + Rillaboom (slot b).  No bench.
    """
    roster = {"p1": {}}
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
    """p2 beliefs: Flutter Mane (slot a) + Tornadus (slot b).  No bench."""
    roster = {"p2": {}}
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


def _combined_beliefs():
    """Merge p1 + p2 beliefs into the combined dicts make_resolve expects."""
    p1_roster, p1_movesets, p1_stats = _p1_beliefs()
    p2_roster, p2_movesets, p2_stats = _p2_fake_beliefs()
    roster = {**p1_roster, **p2_roster}
    movesets = {**p1_movesets, **p2_movesets}
    stats = {**p1_stats, **p2_stats}
    return roster, movesets, stats


# ---------------------------------------------------------------------------
# C1 test: make_resolve returns (next_state, reward) without mutating input
# ---------------------------------------------------------------------------

def test_resolve_returns_next_state_and_reward(decision_fixture):
    """make_resolve(root_our_side="p1", ...) must:
    - return (nxt, reward) where nxt is a new BattleState and reward is a float
    - NOT mutate the input state (clone semantics)
    """
    from showdown_bot.learning.rollout import make_resolve
    from showdown_bot.learning.decide_adapter import decide

    req, kw = decision_fixture
    state = kw["state"]

    roster, movesets, stats = _combined_beliefs()
    meta = _move_table()

    # deps: everything except state and our_side (same pattern as test_decide_adapter)
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    resolve = make_resolve(
        root_our_side="p1",
        roster_by_side=roster,
        movesets_by_side=movesets,
        stats_by_side=stats,
        move_meta=meta,
        deps=deps,
        weights=None,
    )

    # Decide for both sides (JointAction is the cleanest first test)
    p1_r, p1_m, p1_s = _p1_beliefs()
    p2_r, p2_m, p2_s = _p2_fake_beliefs()

    our_ja = decide(state, "p1", roster=p1_r, movesets=p1_m, stats=p1_s,
                    move_meta=meta, deps=deps)
    opp_ja = decide(state, "p2", roster=p2_r, movesets=p2_m, stats=p2_s,
                    move_meta=meta, deps=deps)

    # Snapshot before resolve
    before = copy.deepcopy(state)

    nxt, reward = resolve(state, our_ja, opp_ja)

    assert nxt is not state, "resolve must return a NEW state object, not the input"
    assert isinstance(reward, float), f"reward must be float, got {type(reward)}"

    # Input state must be byte-identical after resolve
    assert state.sides == before.sides, "resolve must NOT mutate input state.sides"
    assert state.field == before.field, "resolve must NOT mutate input state.field"

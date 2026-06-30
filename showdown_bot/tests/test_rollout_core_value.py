"""C0 prerequisite tests: _choose_best returns (best_ja, best_val); decide clones state."""
from __future__ import annotations

import copy

import pytest

from showdown_bot.battle.decision import _choose_best, _choose_best_ja, heuristic_choose_for_request
from showdown_bot.protocol.encoder import encode_choose
from showdown_bot.engine.moves import _move_table


# ---------------------------------------------------------------------------
# Helpers — p1 roster/movesets/stats matching the conftest decision_fixture
# ---------------------------------------------------------------------------

def _p1_beliefs():
    """Build p1 roster/movesets/stats matching the decision_fixture state.

    decision_fixture state has p1 active: Incineroar (slot a) + Rillaboom (slot b).
    No bench in the conftest _state().
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


# ---------------------------------------------------------------------------
# Test 1: _choose_best returns (JointAction, float) — [0] matches old core
# ---------------------------------------------------------------------------

def test_choose_best_returns_action_and_value(decision_fixture):
    req, kw = decision_fixture
    ja, val = _choose_best(req, **kw)
    # [0] must be the same action the old core returns
    assert ja.as_pair() == _choose_best_ja(req, **kw).as_pair()
    # [1] must be a float (the pick_best aggregate scalar)
    assert isinstance(val, float)
    # public choice unchanged — best_val is just exposed, never changes the action
    assert encode_choose(ja.as_pair(), rqid=req.rqid) == heuristic_choose_for_request(req, **kw)


# ---------------------------------------------------------------------------
# Test 2: decide() must not mutate the caller's state
# ---------------------------------------------------------------------------

def test_decide_does_not_mutate_state(decision_fixture):
    """C0 prerequisite: decide() must leave the input state byte-identical."""
    from showdown_bot.learning.decide_adapter import decide

    req, kw = decision_fixture
    state = kw["state"]
    side = kw.get("our_side", "p1")

    before = copy.deepcopy(state)

    roster, movesets, stats = _p1_beliefs()
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    decide(
        state, side,
        roster=roster,
        movesets=movesets,
        stats=stats,
        move_meta=_move_table(),
        deps=deps,
    )

    # apply_own_team_knowledge + dex enrichment must hit a CLONE, not this state
    assert state.sides == before.sides and state.field == before.field


# ---------------------------------------------------------------------------
# Test 3: _choose_best refactor must NOT break trace/report passthrough
# ---------------------------------------------------------------------------

def test_choose_best_preserves_trace_and_report(decision_fixture):
    """The _choose_best refactor must NOT break 1b capture."""
    from showdown_bot.battle.decision_trace import DecisionTrace

    req, kw = decision_fixture
    # Strip any trace/report keys that may be present (shouldn't be, but be safe)
    kw2 = {k: v for k, v in kw.items() if k not in ("trace", "report")}

    tr = DecisionTrace()
    rep: list[str] = []
    _choose_best(req, trace=tr, report=rep, **kw2)

    # _choose_best must populate the trace
    assert tr.chosen_candidate_id is not None
    assert len(tr.candidates) >= 1

    # Public wrapper path must produce the same chosen_candidate_id
    tr2 = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr2, **kw2)
    assert tr2.chosen_candidate_id == tr.chosen_candidate_id

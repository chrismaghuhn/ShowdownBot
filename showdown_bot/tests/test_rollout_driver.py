"""C3: rollout_labels driver tests.

Ground truth confirmed against source:
  DecisionTrace.candidates          -- list[CandidateTrace]
  CandidateTrace.candidate_id       -- str
  CandidateTrace.joint_action       -- JointAction
  CandidateTrace.aggregate_score    -- float  (real name, plan's guess was correct)
  DecisionTrace.opponent_responses  -- list[list[PlannedAction]]  (from decision.py line 414)
  DecisionTrace.opponent_response_weights -- list[float]  (real name, plan's guess was correct)
  DecisionTrace.chosen_candidate_id -- str | None

  counterfactual_value(start_state, candidate, responses, *, decide, resolve, leaf, cfg)
    responses = list[(opp_action, weight)]   <-- (opp, w) tuples

  label_decision per-candidate keys (teacher.py lines 83-92):
    counterfactual_value_raw
    counterfactual_value_normalized_within_decision
    value_gap_to_best
    counterfactual_rank
    teacher_rank
    heuristic_rank
    teacher_best
    chosen_by_current_heuristic
"""
from __future__ import annotations

import copy

from showdown_bot.engine.moves import _move_table


# ---------------------------------------------------------------------------
# Fixture wiring helpers — identical to test_rollout_adapters.py
# ---------------------------------------------------------------------------

def _p1_beliefs():
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
    p1_r, p1_m, p1_s = _p1_beliefs()
    p2_r, p2_m, p2_s = _p2_fake_beliefs()
    return {**p1_r, **p2_r}, {**p1_m, **p2_m}, {**p1_s, **p2_s}


def _make_all(decision_fixture):
    """Return (state, deps, roster, movesets, stats, meta, resolve, decide_fn, leaf_fn)."""
    from showdown_bot.learning.rollout import make_resolve, make_decide, make_leaf

    req, kw = decision_fixture
    state = kw["state"]
    roster, movesets, stats = _combined_beliefs()
    meta = _move_table()
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    common = dict(
        root_our_side="p1",
        roster_by_side=roster,
        movesets_by_side=movesets,
        stats_by_side=stats,
        move_meta=meta,
        deps=deps,
    )
    resolve = make_resolve(weights=None, **common)
    decide_fn = make_decide(**common)
    leaf_fn = make_leaf(**common)
    return state, deps, roster, movesets, stats, meta, resolve, decide_fn, leaf_fn


# ---------------------------------------------------------------------------
# Helper: capture a real populated DecisionTrace
# ---------------------------------------------------------------------------

def _capture_trace(decision_fixture):
    """Run heuristic_choose_for_request with a DecisionTrace and return (trace, state)."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace

    req, kw = decision_fixture
    state = kw["state"]
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    return tr, state


# ---------------------------------------------------------------------------
# Test (a): H=0 end-to-end math — THE primary gate
# ---------------------------------------------------------------------------

def test_h0_equals_weighted_mean_of_resolve_rewards(decision_fixture):
    """With H=0 and use_leaf=False, counterfactual_value must equal the
    weighted mean of resolve rewards exactly (spec Q7d, tolerance 1e-9).

    Uses two DIFFERENT opponent JointActions so the per-response rewards differ
    and the weighted mean is non-trivial.  Weights are non-uniform (0.7 / 0.3).
    """
    from showdown_bot.learning.teacher import counterfactual_value, RolloutConfig, US, THEM
    from showdown_bot.learning.decide_adapter import decide as raw_decide

    state, deps, roster, movesets, stats, meta, resolve, decide_fn, leaf_fn = _make_all(
        decision_fixture
    )

    # Candidate: p1's heuristic best JointAction
    p1_r, p1_m, p1_s = _p1_beliefs()
    candidate = raw_decide(
        state, "p1",
        roster=p1_r, movesets=p1_m, stats=p1_s,
        move_meta=meta, deps=deps,
    )

    # Two distinct opponent responses: use US and THEM decide calls so the actions
    # (and therefore the resolve rewards) differ.
    opp_resp1 = decide_fn(state, THEM)   # heuristic best for p2
    # For the second response we get a p1-side decide output and use it as a
    # "different" opp action — it's a different JointAction so the reward differs.
    opp_resp2 = decide_fn(state, US)     # p1 JA used as the second opp response variant

    # Non-uniform weights summing to 1
    w1, w2 = 0.7, 0.3
    R = [(opp_resp1, w1), (opp_resp2, w2)]

    cfg = RolloutConfig(H=0, use_leaf=False)
    cfv = counterfactual_value(
        state, candidate, R,
        decide=decide_fn, resolve=resolve, leaf=leaf_fn, cfg=cfg,
    )

    expected = sum(w * resolve(state, candidate, opp)[1] for opp, w in R)
    assert abs(cfv - expected) < 1e-9, (
        f"H=0 math failed: cfv={cfv!r}, expected={expected!r}, diff={abs(cfv - expected)!r}"
    )


# ---------------------------------------------------------------------------
# Test (b): start state unchanged after a full rollout (H=4)
# ---------------------------------------------------------------------------

def test_start_state_unchanged_after_full_rollout(decision_fixture):
    """A deep H=4 rollout must not mutate the input start_state."""
    from showdown_bot.learning.teacher import counterfactual_value, RolloutConfig, THEM

    state, deps, roster, movesets, stats, meta, resolve, decide_fn, leaf_fn = _make_all(
        decision_fixture
    )
    from showdown_bot.learning.decide_adapter import decide as raw_decide

    p1_r, p1_m, p1_s = _p1_beliefs()
    candidate = raw_decide(
        state, "p1",
        roster=p1_r, movesets=p1_m, stats=p1_s,
        move_meta=meta, deps=deps,
    )
    opp_resp = decide_fn(state, THEM)
    R = [(opp_resp, 1.0)]

    before = copy.deepcopy(state)

    cfg = RolloutConfig(H=4, use_leaf=True)
    counterfactual_value(
        state, candidate, R,
        decide=decide_fn, resolve=resolve, leaf=leaf_fn, cfg=cfg,
    )

    assert state.sides == before.sides, "rollout must NOT mutate state.sides"
    assert state.field == before.field, "rollout must NOT mutate state.field"


# ---------------------------------------------------------------------------
# Test (c): determinism — same inputs → identical cfv
# ---------------------------------------------------------------------------

def test_rollout_is_deterministic(decision_fixture):
    """Same state + candidate + R → identical counterfactual_value on both calls."""
    from showdown_bot.learning.teacher import counterfactual_value, RolloutConfig, THEM

    state, deps, roster, movesets, stats, meta, resolve, decide_fn, leaf_fn = _make_all(
        decision_fixture
    )
    from showdown_bot.learning.decide_adapter import decide as raw_decide

    p1_r, p1_m, p1_s = _p1_beliefs()
    candidate = raw_decide(
        state, "p1",
        roster=p1_r, movesets=p1_m, stats=p1_s,
        move_meta=meta, deps=deps,
    )
    opp_resp = decide_fn(state, THEM)
    R = [(opp_resp, 1.0)]

    cfg = RolloutConfig(H=2, use_leaf=True)
    cfv1 = counterfactual_value(
        state, candidate, R,
        decide=decide_fn, resolve=resolve, leaf=leaf_fn, cfg=cfg,
    )
    cfv2 = counterfactual_value(
        state, candidate, R,
        decide=decide_fn, resolve=resolve, leaf=leaf_fn, cfg=cfg,
    )
    assert cfv1 == cfv2, f"rollout must be deterministic; got {cfv1!r} then {cfv2!r}"


# ---------------------------------------------------------------------------
# Test (d): rollout_labels replaces stub — real label_decision keys returned
# ---------------------------------------------------------------------------

def test_rollout_labels_replaces_stub(decision_fixture):
    """rollout_labels(trace, state, ...) must:
    - return one entry per top-K candidate
    - each value-dict has ALL real label_decision keys (from teacher.py)
    - chosen_candidate_id appears in the returned dict
    """
    from showdown_bot.learning.rollout import rollout_labels
    from showdown_bot.learning.teacher import RolloutConfig

    req, kw = decision_fixture
    tr, state = _capture_trace(decision_fixture)

    # Sanity: trace must have been populated
    assert tr.chosen_candidate_id is not None, "trace must be populated by heuristic_choose_for_request"
    assert len(tr.candidates) >= 1, "trace must have at least one candidate"

    roster, movesets, stats = _combined_beliefs()
    meta = _move_table()
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    cfg = RolloutConfig(H=2, top_k=6, use_leaf=True)

    labels = rollout_labels(
        tr, state,
        root_our_side="p1",
        roster_by_side=roster,
        movesets_by_side=movesets,
        stats_by_side=stats,
        move_meta=meta,
        deps=deps,
        cfg=cfg,
    )

    # At least one entry returned
    assert labels, "rollout_labels must return a non-empty dict"

    # Number of entries = min(top_k, len(candidates))
    expected_count = min(cfg.top_k, len(tr.candidates))
    assert len(labels) == expected_count, (
        f"expected {expected_count} labels, got {len(labels)}"
    )

    # Every per-candidate value-dict must have the REAL label_decision keys
    required_keys = {
        "counterfactual_value_raw",
        "counterfactual_value_normalized_within_decision",
        "value_gap_to_best",
        "counterfactual_rank",
        "teacher_rank",
        "heuristic_rank",
        "teacher_best",
        "chosen_by_current_heuristic",
    }
    for cid, vdict in labels.items():
        assert required_keys <= set(vdict), (
            f"candidate {cid!r} missing keys: {required_keys - set(vdict)}"
        )

    from showdown_bot.battle.candidate_identity import candidate_identity, resolve_chosen_candidate

    chosen = resolve_chosen_candidate(tr)
    assert candidate_identity(chosen) in labels, (
        f"chosen candidate identity {candidate_identity(chosen)!r} not in labels keys: {set(labels)}"
    )

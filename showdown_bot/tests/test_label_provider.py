# tests/test_label_provider.py
"""TDD tests for learning/label_provider.py (Phase 3 slice 1d-1)."""
from __future__ import annotations

import pytest

from showdown_bot.battle.candidate_identity import candidate_identity
from showdown_bot.learning.schema import LABEL_KEYS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def trace_fixture(decision_fixture):
    """A populated DecisionTrace with at least one candidate."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    return tr


@pytest.fixture
def stub_ctx_and_inputs(decision_fixture):
    """A (trace, state, request, FeatureContext) tuple whose teacher_config == StubLabelProvider().teacher_config()."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.learning.features import FeatureContext
    from showdown_bot.learning.label_provider import StubLabelProvider
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    state = kw["state"]
    our_side = kw.get("our_side", "p1")
    ctx = FeatureContext(
        run_id="r",
        game_id="g",
        decision_id="d",
        decision_local_index=0,
        turn_number=getattr(state, "turn", 0),
        our_side=our_side,
        format_id="fmt",
        team_hash="t",
        config_hash="c",
        git_sha="s",
        dirty_flag=False,
        teacher_config=StubLabelProvider().teacher_config(),
        sampling_policy="all",
        mirror_flag=True,
    )
    return tr, state, req, ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_stub_provider_teacher_config():
    from showdown_bot.learning.label_provider import StubLabelProvider
    p = StubLabelProvider()
    assert p.teacher_config() == {"teacher_version": "stub-h0", "trainable_label": False}


def test_stub_provider_labels_all_candidates(trace_fixture):
    from showdown_bot.learning.label_provider import StubLabelProvider
    p = StubLabelProvider()
    labels = p.labels_for_decision(trace_fixture, None, None, context=None)
    assert set(labels) == {candidate_identity(c) for c in trace_fixture.candidates}
    for lab in labels.values():
        assert set(lab) == set(LABEL_KEYS)         # exact key set
        assert all(v == 0 for v in lab.values())   # zeroed (byte-identical to today)


def test_validate_label_prefix_rejects_holey_set(trace_fixture):
    from showdown_bot.learning.label_provider import _validate_label_prefix
    # labels for candidate 0 and 2 but not 1 -> a holey ranking -> reject
    ids = [candidate_identity(c) for c in trace_fixture.candidates]
    holey = {ids[0]: {}, ids[2]: {}} if len(ids) >= 3 else {}
    if not holey:
        pytest.skip("Need at least 3 candidates to build a holey set")
    with pytest.raises(ValueError):
        _validate_label_prefix(trace_fixture, holey)


def test_validate_label_prefix_rejects_empty_for_nonempty_trace(trace_fixture):
    from showdown_bot.learning.label_provider import _validate_label_prefix
    with pytest.raises(ValueError):
        _validate_label_prefix(trace_fixture, {})   # empty labels for a non-empty trace -> reject


def test_validate_label_prefix_rejects_identity_collision_outside_labeled_prefix():
    """Legacy v1 collision in unlabeled tail must fail before prefix check accepts."""
    from showdown_bot.battle.candidate_identity import ChosenCandidateResolutionError
    from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
    from showdown_bot.battle.evaluate import OutcomeBreakdown
    from showdown_bot.learning.label_provider import _validate_label_prefix

    shared = "(Knock Off->1, switch)"
    empty_breakdown = OutcomeBreakdown()
    trace = DecisionTrace(candidates=[
        CandidateTrace(
            candidate_id=shared, rank=0, aggregate_score=1.0, score_vector=[1.0],
            joint_action=None, outcome_breakdowns=[empty_breakdown], aggregate_breakdown=empty_breakdown,
        ),
        CandidateTrace(
            candidate_id=shared, rank=1, aggregate_score=0.5, score_vector=[0.5],
            joint_action=None, outcome_breakdowns=[empty_breakdown], aggregate_breakdown=empty_breakdown,
        ),
        CandidateTrace(
            candidate_id="(pass, pass)", rank=2, aggregate_score=0.0, score_vector=[0.0],
            joint_action=None, outcome_breakdowns=[empty_breakdown], aggregate_breakdown=empty_breakdown,
        ),
    ])
    labels = {shared: {k: 0 for k in LABEL_KEYS}}
    with pytest.raises(ChosenCandidateResolutionError, match="ambiguous candidate identity"):
        _validate_label_prefix(trace, labels)


def test_stub_row_metadata_teacher_version(stub_ctx_and_inputs):
    """PIN: row metadata teacher_version comes from ctx.teacher_config (NOT hardcoded).
    ctx.teacher_config == StubLabelProvider().teacher_config() -> "stub-h0", trainable_label False.
    """
    from showdown_bot.learning.features import extract_features
    from showdown_bot.learning.label_provider import StubLabelProvider
    trace, state, req, ctx = stub_ctx_and_inputs
    p = StubLabelProvider()
    labels = p.labels_for_decision(trace, state, req, context=ctx)
    rows = extract_features(trace, state, req, ctx, labels=labels)
    assert len(rows) > 0
    assert all(r.metadata["teacher_version"] == "stub-h0" for r in rows)
    assert all(r.metadata["teacher_config"]["trainable_label"] is False for r in rows)


# ---------------------------------------------------------------------------
# 1d-2 tests: RolloutLabelProvider + RolloutLabelError
# ---------------------------------------------------------------------------

def _make_rollout_deps(kw):
    """Build a deps dict from decision_fixture kwargs (mirrors test_rollout_driver.py).

    Also injects move_meta from _move_table() — the runtime includes this in deps
    so RolloutLabelProvider can pass it through to rollout_labels.
    """
    from showdown_bot.engine.moves import _move_table
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}
    deps["move_meta"] = _move_table()
    return deps


def _make_rollout_ctx(state, our_side="p1", cfg=None):
    """Build a minimal FeatureContext for rollout tests."""
    from showdown_bot.learning.features import FeatureContext
    from showdown_bot.learning.teacher import RolloutConfig
    if cfg is None:
        cfg = RolloutConfig(H=1, top_k=2)
    teacher_config = {
        "teacher_version": f"rollout-h{cfg.H}-v1",
        "trainable_label": True,
        "rollout_config": {"H": cfg.H, "gamma": cfg.gamma, "top_k": cfg.top_k, "use_leaf": cfg.use_leaf},
    }
    return FeatureContext(
        run_id="r",
        game_id="g",
        decision_id="d",
        decision_local_index=0,
        turn_number=getattr(state, "turn", 0),
        our_side=our_side,
        format_id="fmt",
        team_hash="t",
        config_hash="c",
        git_sha="s",
        dirty_flag=False,
        teacher_config=teacher_config,
        sampling_policy="all",
        mirror_flag=True,
    )


def test_rollout_provider_teacher_config():
    """teacher_config returns rollout-h{H}-v1, trainable_label True, rollout_config present."""
    from showdown_bot.learning.label_provider import RolloutLabelProvider
    from showdown_bot.learning.teacher import RolloutConfig
    cfg = RolloutConfig(H=4)
    p = RolloutLabelProvider(deps={}, likely_sets={}, move_priors={}, cfg=cfg)
    tc = p.teacher_config()
    assert tc["teacher_version"] == "rollout-h4-v1"
    assert tc["trainable_label"] is True
    assert "rollout_config" in tc
    rc = tc["rollout_config"]
    assert rc["H"] == 4
    assert rc["gamma"] == cfg.gamma
    assert rc["top_k"] == cfg.top_k
    assert rc["use_leaf"] == cfg.use_leaf


def test_rollout_provider_labels_topk(decision_fixture):
    """labels_for_decision returns top-K entries, each with exact LABEL_KEYS."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.learning.label_provider import RolloutLabelProvider
    from showdown_bot.learning.teacher import RolloutConfig

    req, kw = decision_fixture
    state = kw["state"]
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)

    deps = _make_rollout_deps(kw)
    cfg = RolloutConfig(H=1, top_k=3)
    p = RolloutLabelProvider(deps=deps, likely_sets={}, move_priors={}, cfg=cfg)
    ctx = _make_rollout_ctx(state, our_side="p1", cfg=cfg)

    labels = p.labels_for_decision(tr, state, req, context=ctx)

    assert labels, "must return at least one label"
    for lab in labels.values():
        assert set(lab) == set(LABEL_KEYS), f"LABEL_KEYS mismatch: {set(lab) ^ set(LABEL_KEYS)}"


def test_no_opponent_responses_raises_rollout_label_error(decision_fixture):
    """A trace with no opponent_responses raises RolloutLabelError (recoverable)."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.learning.label_provider import RolloutLabelProvider
    from showdown_bot.learning.rollout import RolloutLabelError
    from showdown_bot.learning.teacher import RolloutConfig

    req, kw = decision_fixture
    state = kw["state"]
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)

    # Strip opponent responses so rollout_labels hits the "at least one" raise
    tr.opponent_responses = []
    tr.opponent_response_weights = []

    deps = _make_rollout_deps(kw)
    cfg = RolloutConfig(H=1, top_k=3)
    p = RolloutLabelProvider(deps=deps, likely_sets={}, move_priors={}, cfg=cfg)
    ctx = _make_rollout_ctx(state, our_side="p1", cfg=cfg)

    with pytest.raises(RolloutLabelError):
        p.labels_for_decision(tr, state, req, context=ctx)


def test_weights_integrity_stays_hard_fail(decision_fixture):
    """Malformed weights (length mismatch) raise plain ValueError, NOT RolloutLabelError.

    This tests that the integrity-bug raises at lines 254/260 are NOT reclassified.
    """
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.learning.label_provider import RolloutLabelProvider
    from showdown_bot.learning.rollout import RolloutLabelError
    from showdown_bot.learning.teacher import RolloutConfig

    req, kw = decision_fixture
    state = kw["state"]
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)

    # Must have at least one response (otherwise RolloutLabelError fires first)
    if not tr.opponent_responses:
        pytest.skip("trace has no opponent_responses")

    # Set all weights to 0 to trigger the "sum <= 0" integrity error (line 260 in rollout.py).
    # This path is reachable via rollout_labels -> _drop_switch_responses -> _normalize_responses
    # and is an integrity bug that MUST stay as plain ValueError (not RolloutLabelError).
    n = len(tr.opponent_responses)
    tr.opponent_response_weights = [0.0] * n

    deps = _make_rollout_deps(kw)
    cfg = RolloutConfig(H=1, top_k=3)
    p = RolloutLabelProvider(deps=deps, likely_sets={}, move_priors={}, cfg=cfg)
    ctx = _make_rollout_ctx(state, our_side="p1", cfg=cfg)

    # Must be plain ValueError, NOT a subclass of RolloutLabelError
    with pytest.raises(ValueError):
        p.labels_for_decision(tr, state, req, context=ctx)

    # Ensure it is NOT caught as a RolloutLabelError
    try:
        p.labels_for_decision(tr, state, req, context=ctx)
    except RolloutLabelError:
        pytest.fail("integrity ValueError was incorrectly reclassified as RolloutLabelError")
    except ValueError:
        pass  # correct — integrity bug stays hard-fail

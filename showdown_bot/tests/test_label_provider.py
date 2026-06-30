# tests/test_label_provider.py
"""TDD tests for learning/label_provider.py (Phase 3 slice 1d-1)."""
from __future__ import annotations

import pytest

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
    assert set(labels) == {c.candidate_id for c in trace_fixture.candidates}
    for lab in labels.values():
        assert set(lab) == set(LABEL_KEYS)         # exact key set
        assert all(v == 0 for v in lab.values())   # zeroed (byte-identical to today)


def test_validate_label_prefix_rejects_holey_set(trace_fixture):
    from showdown_bot.learning.label_provider import _validate_label_prefix
    # labels for candidate 0 and 2 but not 1 -> a holey ranking -> reject
    ids = [c.candidate_id for c in trace_fixture.candidates]
    holey = {ids[0]: {}, ids[2]: {}} if len(ids) >= 3 else {}
    if not holey:
        pytest.skip("Need at least 3 candidates to build a holey set")
    with pytest.raises(ValueError):
        _validate_label_prefix(trace_fixture, holey)


def test_validate_label_prefix_rejects_empty_for_nonempty_trace(trace_fixture):
    from showdown_bot.learning.label_provider import _validate_label_prefix
    with pytest.raises(ValueError):
        _validate_label_prefix(trace_fixture, {})   # empty labels for a non-empty trace -> reject


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

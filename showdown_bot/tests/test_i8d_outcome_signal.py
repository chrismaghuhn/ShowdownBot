"""I8-D authoritative live-outcome signal (option b): a small, optional stage_sink written
where choose_with_fallback already sets selection_stage/fallback_reason, plus the pure
classifier that maps the EXISTING fallback contract to a decision-profile outcome.

Binding: fallback is derived only from the existing selection_stage vocabulary; crash and
degraded_state are classified separately and never approximated through the stage sink; the
sink is None by default through the whole chain, adds no objects/trace/candidate-matrix when
absent, and is set with small scalar assignments inside the existing agent_choose window.
"""
from __future__ import annotations

import pytest

from showdown_bot.battle.decision import (
    SelectionStageSink,
    _mark_selection,
    choose_with_fallback,
)
from showdown_bot.eval.decision_profile import (
    LIVE_FALLBACK_STAGES,
    LIVE_OK_STAGE,
    classify_live_outcome,
)


# --------------------------------------------------------------------------
# the pure classifier — the existing vocabulary, no invented semantics
# --------------------------------------------------------------------------

def test_the_fallback_stages_are_exactly_the_existing_non_heuristic_selection_stages():
    # These are the stages choose_with_fallback actually marks below its heuristic branch.
    assert LIVE_OK_STAGE == "heuristic"
    assert LIVE_FALLBACK_STAGES == frozenset(
        {"max_damage_fallback", "deterministic_default_pair", "server_default"}
    )


def test_a_completed_heuristic_is_ok():
    assert classify_live_outcome(
        crashed=False, state_degraded=False, selection_stage="heuristic") == "ok"


@pytest.mark.parametrize("stage", sorted(LIVE_FALLBACK_STAGES))
def test_a_real_fallback_stage_is_fallback(stage):
    assert classify_live_outcome(
        crashed=False, state_degraded=False, selection_stage=stage) == "fallback"


def test_crash_is_never_fallback_even_with_a_fallback_stage():
    # A crash is classified independently and must dominate any stage the sink happens to carry.
    assert classify_live_outcome(
        crashed=True, state_degraded=False, selection_stage="max_damage_fallback") == "crash"
    assert classify_live_outcome(
        crashed=True, state_degraded=False, selection_stage="heuristic") == "crash"


def test_degraded_state_is_never_fallback():
    # State-build failure is classified independently and is not approximated via the sink.
    assert classify_live_outcome(
        crashed=False, state_degraded=True, selection_stage=None) == "degraded_state"
    assert classify_live_outcome(
        crashed=False, state_degraded=True, selection_stage="max_damage_fallback") == "degraded_state"


def test_classifier_never_consumes_fallback_reason():
    """A set fallback_reason without the matching fallback STAGE must not be accepted as
    fallback. Structurally: the classifier's only stage input is selection_stage, so a
    heuristic stage is ok regardless of any reason the sink also carries."""
    import inspect

    params = set(inspect.signature(classify_live_outcome).parameters)
    assert "fallback_reason" not in params, "classification must not depend on fallback_reason"
    # heuristic stage stays ok; there is no way for a reason to flip it.
    assert classify_live_outcome(
        crashed=False, state_degraded=False, selection_stage="heuristic") == "ok"


def test_an_unknown_stage_on_a_completed_decision_fails_closed():
    from showdown_bot.eval.decision_profile import DecisionProfileError

    with pytest.raises(DecisionProfileError):
        classify_live_outcome(crashed=False, state_degraded=False, selection_stage="something_new")
    with pytest.raises(DecisionProfileError):
        classify_live_outcome(crashed=False, state_degraded=False, selection_stage=None)


# --------------------------------------------------------------------------
# the stage_sink is written where _mark_selection already runs (no reconstruction)
# --------------------------------------------------------------------------

def test_mark_selection_populates_the_sink_with_the_existing_values():
    sink = SelectionStageSink()
    _mark_selection(None, "max_damage_fallback", "heuristic_timeout", stage_sink=sink)
    assert sink.selection_stage == "max_damage_fallback"
    assert sink.fallback_reason == "heuristic_timeout"
    # heuristic success: reason stays None (the existing contract), and the sink reflects it.
    sink2 = SelectionStageSink()
    _mark_selection(None, "heuristic", stage_sink=sink2)
    assert (sink2.selection_stage, sink2.fallback_reason) == ("heuristic", None)


def test_choose_with_fallback_marks_the_sink_before_returning_on_a_real_fallback(monkeypatch):
    """Force the heuristic layer to fail so choose_with_fallback takes a genuine fallback path.
    The sink must carry a real fallback stage the INSTANT choose_with_fallback returns — i.e. it
    was set inside _mark_selection during the call, NOT reconstructed by the caller afterward.
    No DecisionTrace is involved."""
    import showdown_bot.battle.baselines as baselines
    import showdown_bot.battle.decision as dmod

    def _boom(*a, **k):
        raise RuntimeError("heuristic exploded")

    monkeypatch.setattr(dmod, "heuristic_choose_for_request", _boom)
    # max_damage_choice is imported INSIDE choose_with_fallback from baselines — patch it there.
    monkeypatch.setattr(baselines, "max_damage_choice", lambda *a, **k: "/choose move 1|7")

    req = _fake_req()
    sink = SelectionStageSink()
    choice = choose_with_fallback(
        req, state=object(), book=object(), our_side="p1", trace=None, stage_sink=sink)
    assert choice == "/choose move 1|7"
    assert sink.selection_stage == "max_damage_fallback"      # a real fallback stage
    assert sink.fallback_reason == "heuristic_error"
    assert classify_live_outcome(
        crashed=False, state_degraded=False, selection_stage=sink.selection_stage) == "fallback"


def test_stage_sink_does_not_change_the_chosen_action(monkeypatch):
    """Byte-/value-identical chosen action with and without the sink."""
    import showdown_bot.battle.decision as dmod
    monkeypatch.setattr(dmod, "heuristic_choose_for_request", lambda *a, **k: "/choose move 2|9")
    req = _fake_req()
    without = choose_with_fallback(req, state=object(), book=object(), our_side="p1", trace=None)
    with_sink = choose_with_fallback(
        req, state=object(), book=object(), our_side="p1", trace=None, stage_sink=SelectionStageSink())
    assert without == with_sink == "/choose move 2|9"


def test_no_sink_means_no_extra_object_written():
    """Without a sink, _mark_selection touches nothing new (the trace-None, sink-None path is a
    no-op beyond the existing trace write)."""
    # Purely that the default path accepts no sink and raises nothing.
    _mark_selection(None, "heuristic")            # no trace, no sink -> no-op, no error
    _mark_selection(None, "server_default", "default_pair_error")


class _FakeReq:
    rqid = 7
    team_preview = False
    wait = False

    class side:
        id = "p1"


def _fake_req():
    return _FakeReq()

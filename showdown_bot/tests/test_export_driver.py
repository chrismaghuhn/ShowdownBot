"""Tests for export_driver.maybe_observe_decision (post 1d-3: no internal sampling gate).

The sampling gate moved to DatasetExportRuntime.observe; the driver is now a
pure extract+add function.  These tests call it with already-computed labels.
"""
import pytest
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision
from showdown_bot.learning.label_provider import StubLabelProvider


def _ctx_and_trace(decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.learning.provenance import build_feature_context
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    ctx = build_feature_context(
        git_sha="s", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=0,
        game_index=0, decision_local_index=0, turn_number=1, our_side=kw.get("our_side", "p1"),
        format_id="fmt", mirror_flag=False, teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
    )
    return tr, kw["state"], req, ctx


def test_adds_rows_with_stub_labels(decision_fixture):
    """Driver with pre-computed stub labels produces one row per candidate."""
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    labels = StubLabelProvider().labels_for_decision(tr, state, req, context=ctx)
    n = maybe_observe_decision(exp, ctx=ctx, trace=tr, state=state, request=req, labels=labels)
    assert n == len(tr.candidates) and len(exp.rows_for_test()) == n


def test_added_rows_are_validated(decision_fixture):
    """Every row added by the driver must pass validate_row (schema contract)."""
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    from showdown_bot.learning.schema import validate_row
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    labels = StubLabelProvider().labels_for_decision(tr, state, req, context=ctx)
    maybe_observe_decision(exp, ctx=ctx, trace=tr, state=state, request=req, labels=labels)
    for row in exp.rows_for_test():
        validate_row(row)   # add() already validated; re-assert


def test_extract_features_called_with_provided_labels(decision_fixture, monkeypatch):
    """The driver passes the caller-supplied labels to extract_features (not its own)."""
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    import showdown_bot.learning.export_driver as drv
    captured = {}
    real = drv.extract_features
    def _spy(*a, **k):
        captured["labels"] = k.get("labels")
        return real(*a, **k)
    monkeypatch.setattr(drv, "extract_features", _spy)
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    labels = StubLabelProvider().labels_for_decision(tr, state, req, context=ctx)
    maybe_observe_decision(exp, ctx=ctx, trace=tr, state=state, request=req, labels=labels)
    assert captured.get("labels") is labels

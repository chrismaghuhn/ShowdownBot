import pytest
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision


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


def test_sampled_decision_adds_rows(decision_fixture):
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    n = maybe_observe_decision(exp, 0, ctx=ctx, trace=tr, state=state, request=req)
    assert n == len(tr.candidates) and len(exp.rows_for_test()) == n


def test_unsampled_decision_adds_nothing_and_skips_extract(decision_fixture, monkeypatch):
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    import showdown_bot.learning.export_driver as drv
    called = {"n": 0}
    real = drv.extract_features
    monkeypatch.setattr(drv, "extract_features", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or real(*a, **k))
    exp = DatasetExporter(SamplingPolicy(policy="every_nth", rate=2))
    assert maybe_observe_decision(exp, 1, ctx=ctx, trace=tr, state=state, request=req) == 0  # odd -> not sampled
    assert exp.rows_for_test() == [] and called["n"] == 0                                     # extract NOT called
    assert maybe_observe_decision(exp, 0, ctx=ctx, trace=tr, state=state, request=req) > 0     # even -> sampled
    assert called["n"] == 1


def test_added_rows_are_validated(decision_fixture):
    tr, state, req, ctx = _ctx_and_trace(decision_fixture)
    from showdown_bot.learning.schema import validate_row
    exp = DatasetExporter(SamplingPolicy(policy="all"))
    maybe_observe_decision(exp, 0, ctx=ctx, trace=tr, state=state, request=req)
    for row in exp.rows_for_test():
        validate_row(row)   # B2 add() already validated; re-assert

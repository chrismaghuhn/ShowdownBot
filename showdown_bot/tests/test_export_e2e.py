# tests/test_export_e2e.py
import io
from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision
from showdown_bot.learning.label_provider import StubLabelProvider
from showdown_bot.learning.provenance import build_feature_context


def _ctx(our_side):
    return build_feature_context(
        git_sha="s", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=0,
        game_index=0, decision_local_index=0, turn_number=1, our_side=our_side,
        format_id="fmt", mirror_flag=False, teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all")


def test_e2e_choice_identical_and_jsonl_byte_identical(decision_fixture):
    req, kw = decision_fixture
    our_side = kw.get("our_side", "p1")
    # gate 1: trace=None choice
    base = heuristic_choose_for_request(req, trace=None, **kw)

    def _run():
        tr = DecisionTrace()
        choice = heuristic_choose_for_request(req, trace=tr, **kw)
        exp = DatasetExporter(SamplingPolicy(policy="all"))
        ctx = _ctx(our_side)
        labels = StubLabelProvider().labels_for_decision(tr, kw["state"], req, context=ctx)
        maybe_observe_decision(exp, ctx=ctx, trace=tr, state=kw["state"], request=req, labels=labels)
        buf = io.StringIO(); exp.flush_sorted(buf)
        return choice, buf.getvalue()

    c1, j1 = _run()
    c2, j2 = _run()
    assert c1 == base          # gate 2: enabled choice == trace=None choice
    assert j1 != ""            # rows were produced
    assert j1 == j2            # gate 7: byte-identical across runs (same inputs)

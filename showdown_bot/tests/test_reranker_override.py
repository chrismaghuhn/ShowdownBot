# tests/test_reranker_override.py
"""Slice 2b-4 Task 1: reranker-override choice core. Stub-booster only -- no
lightgbm, no real model load, no battles."""
from __future__ import annotations

import inspect

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.learning import reranker_override as reranker_override_module
from showdown_bot.learning.features import extract_features
from showdown_bot.learning.provenance import build_feature_context
from showdown_bot.learning.reranker_override import RerankerOverride
from showdown_bot.learning.reranker_shadow import score_candidates
from showdown_bot.learning.reranker_features import feature_schema_hash
from showdown_bot.learning.schema import FEATURE_COLUMNS
from showdown_bot.protocol.encoder import encode_choose

FORMAT_ID = "gen9vgc2025regi"


def _run_decision(decision_fixture):
    req, kw = decision_fixture
    tr = DecisionTrace()
    choose = heuristic_choose_for_request(req, trace=tr, **kw)
    return tr, kw["state"], req, choose, kw.get("our_side", "p1")


def _manifest_for(trace, state, request, our_side, *, dex=None, move_meta=None):
    """Build a self-consistent manifest from the SAME context-build recipe
    ``score_candidates`` uses internally, so the categorical encodings cover
    every string-valued column this trace/state/request actually produces."""
    ctx = build_feature_context(
        git_sha="n/a", dirty_flag=False, team_hash_="n/a", config_hash_="n/a", run_seed=0,
        game_index=-1, decision_local_index=0, turn_number=getattr(state, "turn", 0),
        our_side=our_side, format_id=FORMAT_ID, mirror_flag=False,
        teacher_config={"teacher_version": "test"}, sampling_policy="all",
        dex=dex, move_meta=move_meta,
    )
    rows = extract_features(trace, state, request, ctx)
    feature_names = list(FEATURE_COLUMNS)
    cat_names = [c for c in feature_names if any(isinstance(r.features.get(c), str) for r in rows)]
    encodings: dict = {}
    for c in cat_names:
        vals = sorted({str(r.features.get(c)) for r in rows})
        m = {"__unk__": 0}
        for v in vals:
            m.setdefault(v, len(m))
        encodings[c] = m
    manifest = {
        "feature_names": feature_names,
        "categorical_feature_names": cat_names,
        "categorical_encodings": encodings,
        "feature_schema_hash": feature_schema_hash(feature_names, cat_names),
    }
    return manifest, rows


class _StubBooster:
    """Fixed per-candidate scores, in candidate order (trace order)."""

    def __init__(self, scores, feature_names):
        self._scores = list(scores)
        self._feature_names = list(feature_names)

    def feature_name(self):
        return list(self._feature_names)

    def predict(self, X):
        n = len(X)
        assert n == len(self._scores), "test stub sized wrong -- fix the test"
        return list(self._scores)


class _RaisingBooster:
    """feature_name() matches the manifest (schema check passes); predict() raises."""

    def __init__(self, feature_names):
        self._feature_names = list(feature_names)

    def feature_name(self):
        return list(self._feature_names)

    def predict(self, X):
        raise RuntimeError("boom: predict failed")


# ---------------------------------------------------------------------------
# Score-forced argmax
# ---------------------------------------------------------------------------

def test_override_returns_argmax_candidate_choose(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    assert len(tr.candidates) >= 2, "fixture must yield >=2 candidates for a meaningful override test"
    manifest, _rows = _manifest_for(tr, state, req, side)

    n = len(tr.candidates)
    forced_index = n - 1
    # Sanity: the forced candidate must NOT be the heuristic's own pick, so the
    # override's choose is expected to genuinely differ from heuristic_choose.
    assert tr.candidates[forced_index].candidate_id != tr.chosen_candidate_id

    scores = [0.0] * n
    scores[forced_index] = 100.0
    booster = _StubBooster(scores, manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    result = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )

    expected = encode_choose(tr.candidates[forced_index].joint_action.as_pair(), rqid=req.rqid)
    assert result == expected
    assert result != heuristic_choose


# ---------------------------------------------------------------------------
# Stable tie-break: equal scores -> lowest candidate_index, deterministic
# ---------------------------------------------------------------------------

def test_tie_break_is_lowest_index_and_deterministic(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    n = len(tr.candidates)

    scores = [7.0] * n  # every candidate ties
    booster = _StubBooster(scores, manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    expected = encode_choose(tr.candidates[0].joint_action.as_pair(), rqid=req.rqid)

    r1 = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    r2 = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    assert r1 == expected
    assert r1 == r2  # deterministic across repeated calls with identical inputs


# ---------------------------------------------------------------------------
# Fail-safe modes: NEVER raise, always return heuristic_choose unchanged
# ---------------------------------------------------------------------------

def test_failsafe_predict_raises_returns_heuristic_choose(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    booster = _RaisingBooster(manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    result = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    assert result == heuristic_choose


def test_failsafe_schema_hash_mismatch_returns_heuristic_choose(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    bad_manifest = dict(manifest)
    bad_manifest["feature_schema_hash"] = "deadbeefdeadbeef"  # self-inconsistent
    booster = _StubBooster([1.0] * len(tr.candidates), manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=bad_manifest, format_id=FORMAT_ID)

    assert override._schema_ok is False
    result = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    assert result == heuristic_choose


# ---------------------------------------------------------------------------
# candidate-vs-baseline-diff Task 1: selection-stage / fallback-reason
# telemetry -- pure side effect on the passed trace, choice strings unchanged
# (see the assertions above, which still pin the same returned choose values).
# ---------------------------------------------------------------------------

def test_override_marks_selection_stage(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    scores = [0.0] * len(tr.candidates)
    scores[-1] = 100.0
    override = RerankerOverride(
        booster=_StubBooster(scores, manifest["feature_names"]),
        manifest=manifest, format_id=FORMAT_ID,
    )
    out = override.override_choice(
        trace=tr, state=state, request=req,
        heuristic_choose=heuristic_choose, our_side=side,
    )
    assert out != heuristic_choose
    assert tr.selection_stage == "reranker_override"
    assert tr.fallback_reason is None


def test_schema_failure_marks_heuristic_failsafe(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    bad_manifest = dict(manifest)
    bad_manifest["feature_schema_hash"] = "deadbeef"
    override = RerankerOverride(
        booster=_StubBooster([1.0] * len(tr.candidates), manifest["feature_names"]),
        manifest=bad_manifest, format_id=FORMAT_ID,
    )
    out = override.override_choice(
        trace=tr, state=state, request=req,
        heuristic_choose=heuristic_choose, our_side=side,
    )
    assert out == heuristic_choose
    assert tr.selection_stage == "heuristic"
    assert tr.fallback_reason == "reranker_schema_mismatch"


def test_failsafe_booster_feature_order_mismatch_returns_heuristic_choose(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    # Booster reports a DIFFERENT feature order than the manifest -> model<->manifest guard trips.
    shuffled = list(reversed(manifest["feature_names"]))
    booster = _StubBooster([1.0] * len(tr.candidates), shuffled)
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    assert override._schema_ok is False
    result = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    assert result == heuristic_choose


def test_failsafe_empty_candidates_returns_heuristic_choose(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    booster = _StubBooster([], manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    empty_trace = DecisionTrace()  # candidates == []
    result = override.override_choice(
        trace=empty_trace, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    assert result == heuristic_choose


def test_failsafe_argmax_not_a_joint_action_returns_heuristic_choose(decision_fixture):
    """Belt-and-suspenders: an argmax candidate whose joint_action isn't
    resolvable (not a JointAction) fails safe rather than raising."""
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    n = len(tr.candidates)
    tr.candidates[0].joint_action = "not-a-joint-action"  # corrupt just this one field
    scores = [0.0] * n
    scores[0] = 100.0  # force the corrupted candidate to win
    booster = _StubBooster(scores, manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    result = override.override_choice(
        trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
    )
    assert result == heuristic_choose


# ---------------------------------------------------------------------------
# Determinism: no RNG, no clock on the hot scoring path
# ---------------------------------------------------------------------------

def test_determinism_two_calls_identical_inputs_identical_output(decision_fixture):
    tr, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(tr, state, req, side)
    n = len(tr.candidates)
    scores = [float(i) for i in range(n)]  # distinct scores -> a real (non-tie) argmax
    booster = _StubBooster(scores, manifest["feature_names"])
    override = RerankerOverride(booster=booster, manifest=manifest, format_id=FORMAT_ID)

    results = {
        override.override_choice(
            trace=tr, state=state, request=req, heuristic_choose=heuristic_choose, our_side=side,
        )
        for _ in range(5)
    }
    assert len(results) == 1


def test_no_time_or_random_import_on_the_hot_path():
    """Structural guard: unlike the shadow's 50ms-timeout affordance, the
    override scores INLINE with no wall-clock/RNG branch anywhere on its hot
    path (module source, the override_choice method, and the shared
    score_candidates pipeline it calls)."""
    module_src = inspect.getsource(reranker_override_module)
    for banned in ("import time", "import random", "time.sleep", "asyncio.wait_for"):
        assert banned not in module_src, f"{banned!r} found in reranker_override.py"

    method_src = inspect.getsource(RerankerOverride.override_choice)
    for banned in ("time.", "random.", "datetime"):
        assert banned not in method_src, f"{banned!r} found in override_choice"

    score_src = inspect.getsource(score_candidates)
    for banned in ("time.", "random.", "datetime"):
        assert banned not in score_src, f"{banned!r} found in score_candidates"

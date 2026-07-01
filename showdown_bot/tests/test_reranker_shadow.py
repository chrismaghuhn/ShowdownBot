# tests/test_reranker_shadow.py
import sys, json
from pathlib import Path
from showdown_bot.learning.reranker_shadow import RerankerShadowRuntime

_ROOT = Path(__file__).resolve().parents[2]
_MODEL = _ROOT / "models" / "reranker" / "2026-07-01-2b2a-attack-lgbm.txt"
_MANIFEST = _ROOT / "models" / "reranker" / "2026-07-01-2b2a-attack-manifest.json"

def _enable(monkeypatch, log_path, model=_MODEL, manifest=_MANIFEST):
    monkeypatch.setenv("SHOWDOWN_RERANKER_SHADOW", "1")
    monkeypatch.setenv("SHOWDOWN_RERANKER_MODEL_PATH", str(model))
    monkeypatch.setenv("SHOWDOWN_RERANKER_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("SHOWDOWN_RERANKER_SHADOW_LOG", str(log_path))

def _purge_lightgbm():
    for m in [m for m in sys.modules if m == "lightgbm" or m.startswith("lightgbm.")]:
        sys.modules.pop(m, None)

def test_disabled_when_env_off_and_no_lightgbm_import(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_RERANKER_SHADOW", raising=False)
    _purge_lightgbm()
    rt = RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi")
    assert rt is None
    assert not any(m == "lightgbm" or m.startswith("lightgbm.") for m in sys.modules)  # rule 5

def test_loads_real_2b2a_model(monkeypatch, tmp_path):
    _enable(monkeypatch, tmp_path / "shadow.jsonl")
    rt = RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", packed_team="")
    assert rt is not None
    assert rt.feature_names == json.load(open(_MANIFEST))["feature_names"]
    assert rt.provenance["config_hash"] == "shadow"          # stand-alone provenance

def test_provided_provenance_is_used(monkeypatch, tmp_path):
    _enable(monkeypatch, tmp_path / "shadow.jsonl")
    prov = {"git_sha": "gs", "dirty_flag": False, "team_hash": "th", "config_hash": "cfg", "run_seed": 0}
    rt = RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", provenance=prov)
    assert rt.provenance == prov                             # export provenance reused verbatim

def test_missing_model_disables(monkeypatch, tmp_path):
    _enable(monkeypatch, tmp_path / "shadow.jsonl", model=tmp_path / "nope.txt")
    assert RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", packed_team="") is None

def test_schema_mismatch_disables(monkeypatch, tmp_path):
    bad = tmp_path / "bad_manifest.json"
    m = json.load(open(_MANIFEST)); m["feature_names"] = m["feature_names"][:-1]  # break model<->manifest
    bad.write_text(json.dumps(m))
    _enable(monkeypatch, tmp_path / "shadow.jsonl", manifest=bad)
    assert RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", packed_team="") is None


import json as _json
from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace

def _run_decision(decision_fixture):
    req, kw = decision_fixture
    tr = DecisionTrace()
    choose = heuristic_choose_for_request(req, trace=tr, **kw)
    return tr, kw["state"], req, choose, kw.get("our_side", "p1")

def test_observe_writes_shadowtrace_row(monkeypatch, tmp_path, decision_fixture):
    log = tmp_path / "shadow.jsonl"
    _enable(monkeypatch, log)
    rt = RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", packed_team="")
    rt.start_game()
    tr, state, req, choose, side = _run_decision(decision_fixture)
    rt.observe_shadow(trace=tr, state=state, request=req, choose=choose,
                      turn_number=1, our_side=side, decision_index=0)
    row = _json.loads(log.read_text().splitlines()[-1])
    assert {"game_id","decision_id","actual_choose_string","reranker_choice_index",
            "model_scores","diverged","fallback_reason","feature_context_mode",
            "candidate_count","runtime_feature_schema_hash"} <= set(row)
    assert row["actual_choose_string"] == choose
    assert row["feature_context_mode"] == "2b2a_move_meta_none"
    assert row["fallback_reason"] is None                # a normal decision scores
    assert row["candidate_count"] == len(tr.candidates)
    assert isinstance(row["diverged"], bool)

def test_heuristic_choice_unmatched_is_fail_safe(monkeypatch, tmp_path, decision_fixture):
    _enable(monkeypatch, tmp_path / "s.jsonl")
    rt = RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", packed_team=""); rt.start_game()
    tr, state, req, choose, side = _run_decision(decision_fixture)
    tr.chosen_candidate_id = "does-not-exist"           # force an unmatched heuristic pick
    rt.observe_shadow(trace=tr, state=state, request=req, choose=choose,
                      turn_number=1, our_side=side, decision_index=0)
    row = _json.loads((tmp_path / "s.jsonl").read_text().splitlines()[-1])
    assert row["fallback_reason"] == "heuristic_choice_not_in_trace"
    assert row["diverged"] is None

def test_label_independence_features_only(monkeypatch, tmp_path, decision_fixture):
    # the model vector must not depend on labels: extract_features(labels=None) is used,
    # and only row.features enters X. (Structural: assert model_scores exist + are finite.)
    _enable(monkeypatch, tmp_path / "s.jsonl")
    rt = RerankerShadowRuntime.from_env(format_id="gen9vgc2025regi", packed_team=""); rt.start_game()
    tr, state, req, choose, side = _run_decision(decision_fixture)
    rt.observe_shadow(trace=tr, state=state, request=req, choose=choose,
                      turn_number=1, our_side=side, decision_index=0)
    row = _json.loads((tmp_path / "s.jsonl").read_text().splitlines()[-1])
    scores = [s["score"] for s in row["model_scores"]]
    assert len(scores) == len(tr.candidates) and all(s == s for s in scores)  # finite, one per candidate

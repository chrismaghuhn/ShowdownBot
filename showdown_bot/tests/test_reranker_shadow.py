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

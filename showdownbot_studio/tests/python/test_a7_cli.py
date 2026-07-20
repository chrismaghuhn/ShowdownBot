from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.cli import main
from showdownbot_studio_exporter.validate_bundle import BundleValidationError, validate_bundle_dir

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"
FIX06 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-06" / "bundle"


def _export_args(out: Path) -> list[str]:
    return [
        "--out", str(out),
        "--battle-log", str(FIX01 / "battle.log"),
        "--decision-trace", str(FIX01 / "decision_trace.jsonl"),
        "--results", str(FIX01 / "results.jsonl"),
        "--run-manifest", str(FIX01 / "results.manifest.json"),
        "--config-manifest", str(FIX01 / "results.config-manifest.json"),
    ]


def test_cli_replay_trace_success(tmp_path):
    out = tmp_path / "bundle"
    assert main(_export_args(out)) == 0
    validate_bundle_dir(out)


def test_cli_replay_only_success(tmp_path):
    out = tmp_path / "bundle"
    assert main(["--out", str(out), "--battle-log", str(FIX01 / "battle.log"), "--results", str(FIX01 / "results.jsonl")]) == 0


def test_cli_trace_only_success(tmp_path):
    out = tmp_path / "bundle"
    assert main(["--out", str(out), "--decision-trace", str(FIX01 / "decision_trace.jsonl"), "--results", str(FIX01 / "results.jsonl")]) == 0


def test_cli_refuse_neither_input(tmp_path):
    out = tmp_path / "bundle"
    assert main(["--out", str(out)]) == 2
    assert not out.exists()


def test_cli_refuse_output_exists(tmp_path):
    out = tmp_path / "bundle"
    out.mkdir()
    assert main(_export_args(out)) == 2


def test_cli_refuse_output_inside_sources(tmp_path):
    out = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "evil-out"
    try:
        code = main(["--out", str(out), "--battle-log", str(FIX01 / "battle.log")])
        assert code == 2
    finally:
        if out.exists():
            import shutil
            shutil.rmtree(out, ignore_errors=True)


def test_cli_refuse_provenance_disagreement(tmp_path):
    out = tmp_path / "bundle"
    result_path = tmp_path / "results.jsonl"
    row = json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    row["config_hash"] = "deadbeefdeadbeef"
    result_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    code = main([
        "--out", str(out),
        "--battle-log", str(FIX01 / "battle.log"),
        "--decision-trace", str(FIX01 / "decision_trace.jsonl"),
        "--results", str(result_path),
    ])
    assert code == 2
    assert not out.exists()


def test_cli_require_battle_id_when_ambiguous(tmp_path, monkeypatch):
    out = tmp_path / "bundle"
    smoke = STUDIO_ROOT.parent / "data" / "eval" / "champions-panel-v0" / "smoke-i7a-mega"
    code = main([
        "--out", str(out),
        "--decision-trace", str(smoke / "decision_trace.jsonl"),
        "--results", str(smoke / "results.jsonl"),
    ])
    assert code == 2
    assert not out.exists()


def test_validate_fixture06_refuses():
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(FIX06)
    assert exc.value.reason == "hash_mismatch"

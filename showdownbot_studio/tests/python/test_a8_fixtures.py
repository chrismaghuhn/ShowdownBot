from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

import pytest

from conftest import REPO_ROOT, STUDIO_ROOT

from showdownbot_studio_exporter.cli import main
from showdownbot_studio_exporter.export_bundle import export_bundle
from showdownbot_studio_exporter.validate_bundle import validate_bundle_dir

FIX01_SRC = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"
FIX03_SRC = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-03"
BUNDLES = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture01_bundle_exists_and_validates():
    validate_bundle_dir(BUNDLES / "fixture-01")


def test_two_exports_fixture01_identical(tmp_path):
    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    kw = dict(
        battle_log=FIX01_SRC / "battle.log",
        decision_trace=FIX01_SRC / "decision_trace.jsonl",
        results=FIX01_SRC / "results.jsonl",
        run_manifest=FIX01_SRC / "results.manifest.json",
        config_manifest=FIX01_SRC / "results.config-manifest.json",
    )
    export_bundle(out=out1, **kw)
    export_bundle(out=out2, **kw)
    files1 = {p.name: _sha(p) for p in sorted(out1.iterdir())}
    files2 = {p.name: _sha(p) for p in sorted(out2.iterdir())}
    assert files1 == files2


def test_synthetic_fixture_reports_git_and_dirty_unknown():
    for fix in ("fixture-01", "fixture-03"):
        manifest = validate_bundle_dir(BUNDLES / fix)
        assert manifest["git_sha"] == "unknown"
        assert manifest["source_provenance"]["dirty"] is None


def test_synthetic_sentinels_match_no_committed_eval_identity():
    sentinels = {
        "synthetic00000001",
        "synthetic00000003",
        "syntheticrun00001",
        "bbbbbbbbbbbbbbbb",
        "cccccccccccccccc",
        "dddddddddddddddd",
        "eeeeeeeeeeeeeeee",
    }
    eval_root = REPO_ROOT / "data" / "eval"
    if not eval_root.is_dir():
        return
    for path in eval_root.rglob("*"):
        if path.suffix not in {".json", ".jsonl"} and not path.name.endswith(".manifest.json"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for s in sentinels:
            assert s not in text, f"{s} found in {path}"


def test_fixture10_bundle_has_no_leaks():
    bundle = BUNDLES / "fixture-10"
    for f in bundle.iterdir():
        data = f.read_bytes()
        for needle in (b"LeakPlayerOne", b"NickLeak", b"http://"):
            assert needle not in data


def test_fixture03_has_fallback():
    decisions = (BUNDLES / "fixture-03" / "decisions.jsonl").read_text(encoding="utf-8")
    assert "heuristic_timeout" in decisions


def test_sources_md_lists_synthetic_kind():
    text = (STUDIO_ROOT / "fixtures" / "viewer-v0" / "SOURCES.md").read_text(encoding="utf-8")
    assert "synthetic-coherent-v1" in text
    assert "synthetic00000001" in text

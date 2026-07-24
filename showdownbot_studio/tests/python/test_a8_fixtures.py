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


def test_one_byte_source_mutation_changes_bundle_digest(tmp_path):
    """Bundle contract §15 gate 3: "A one-byte source mutation changes the bundle digest."
    Negation of gate 1 above (same source -> identical digest): a different source must
    produce a different digest. The audit found this genuinely MISSING -- no test mutated a
    source byte and confirmed the re-export changed. Flips one HP digit on fixture-01's
    |switch| line ("35/35" -> "36/35"), a byte that lands inside the parsed battle.jsonl
    (hp.current), not on a filtered/irrelevant protocol line.
    """
    original_log = FIX01_SRC / "battle.log"
    original_bytes = original_log.read_bytes()
    needle = b"Pikachu, L50|35/35"
    assert original_bytes.count(needle) == 1  # precondition: exactly one byte-site to flip
    mutated_bytes = original_bytes.replace(needle, b"Pikachu, L50|36/35", 1)
    assert mutated_bytes != original_bytes

    mutated_src_dir = tmp_path / "src"
    mutated_src_dir.mkdir()
    mutated_log = mutated_src_dir / "battle-mutated.log"
    mutated_log.write_bytes(mutated_bytes)

    kw = dict(
        decision_trace=FIX01_SRC / "decision_trace.jsonl",
        results=FIX01_SRC / "results.jsonl",
        run_manifest=FIX01_SRC / "results.manifest.json",
        config_manifest=FIX01_SRC / "results.config-manifest.json",
    )
    out1 = tmp_path / "unmutated"
    export_bundle(out=out1, battle_log=original_log, **kw)
    out2 = tmp_path / "mutated"
    export_bundle(out=out2, battle_log=mutated_log, **kw)

    assert _sha(out1 / "battle.jsonl") != _sha(out2 / "battle.jsonl")
    m1 = validate_bundle_dir(out1)
    m2 = validate_bundle_dir(out2)
    assert m1["files"]["battle_log"]["sha256"] != m2["files"]["battle_log"]["sha256"]


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

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT, SMOKE

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_bundle import export_bundle
from showdownbot_studio_exporter.provenance import ProvenanceSources, resolve_provenance
from showdownbot_studio_exporter.validate_bundle import validate_bundle_dir

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"
FIX04_BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-04"
FIX05_BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-05"


def test_unknown_git_sha_dirty_null():
    rows = json.loads((FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    prov = resolve_provenance(ProvenanceSources(trace_rows=[json.loads((FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])], result_row=json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])))
    assert prov.git_sha == "unknown"
    assert prov.dirty is None


def test_provenance_disagreement_refuses(tmp_path):
    row = json.loads((FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    result = json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    result["config_hash"] = "deadbeefdeadbeef"
    with pytest.raises(ExportRefuse) as exc:
        resolve_provenance(ProvenanceSources(trace_rows=[row], result_row=result))
    assert exc.value.reason == "provenance_disagreement"


def test_trace_rows_disagreeing_config_hash_refuses():
    lines = (FIX01 / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assert len(rows) >= 2
    rows[1] = dict(rows[1])
    rows[1]["config_hash"] = "aaaaaaaaaaaaaaaa"
    result = json.loads((FIX01 / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    with pytest.raises(ExportRefuse) as exc:
        resolve_provenance(ProvenanceSources(trace_rows=rows, result_row=result))
    assert exc.value.reason == "provenance_disagreement"
    assert "config_hash" in exc.value.message


def test_export_modes_replay_trace_replay_only_trace_only(tmp_path):
    out1 = tmp_path / "rt"
    export_bundle(out=out1, battle_log=FIX01 / "battle.log", decision_trace=FIX01 / "decision_trace.jsonl", results=FIX01 / "results.jsonl")
    m1 = validate_bundle_dir(out1)
    assert m1["files"]["battle_log"]["present"] and m1["files"]["decision_trace"]["present"]

    out2 = tmp_path / "ro"
    export_bundle(out=out2, battle_log=FIX01 / "battle.log", results=FIX01 / "results.jsonl")
    m2 = validate_bundle_dir(out2)
    assert m2["files"]["battle_log"]["present"] and not m2["files"]["decision_trace"]["present"]
    assert m2["trace_schema_version"] is None

    out3 = tmp_path / "to"
    export_bundle(out=out3, decision_trace=SMOKE / "decision_trace.jsonl", results=SMOKE / "results.jsonl", battle_id="3e6a178b0900195e")
    m3 = validate_bundle_dir(out3)
    assert not m3["files"]["battle_log"]["present"] and m3["files"]["decision_trace"]["present"]


def test_frozen_fixture04_replay_only_nullability():
    m = validate_bundle_dir(FIX04_BUNDLE)
    assert m["trace_schema_version"] is None
    assert m["source_hashes"]["decision_trace"] is None
    assert m["source_provenance"]["our_side"] is None


def test_frozen_fixture05_trace_only():
    m = validate_bundle_dir(FIX05_BUNDLE)
    assert not m["files"]["battle_log"]["present"]
    assert m["files"]["decision_trace"]["present"]

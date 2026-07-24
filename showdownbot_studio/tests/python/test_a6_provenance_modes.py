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
FIX04_SRC = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-04"
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


def test_frozen_fixture04_replay_only_resolves_shared_fields_from_result_row():
    """Bundle contract §14 fixture 20 / §11.1.3: with no trace row available, config_hash,
    git_sha, config_id, schedule_hash, and seed_index must resolve from the result row (the
    2nd-priority source once the trace row -- the 1st -- is absent in replay-only mode).

    test_frozen_fixture04_replay_only_nullability (above) proves the §11.1.2 nullability half
    of fixture 20's own §14 text; it does not prove this half -- that the non-null shared
    fields actually come from the result row, not merely that they are present. Extends the
    existing fixture-04 precedent per §1's own fixture-20 recipe ("a pytest extension over the
    existing fixture-04 export rather than a new bundle") instead of authoring a new fixture
    directory -- a fresh fixture-20 bundle in this same replay-only mode would be
    content-identical in shape to the already-committed bundles/fixture-04.
    """
    m = validate_bundle_dir(FIX04_BUNDLE)
    result_row = json.loads((FIX04_SRC / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert m["config_hash"] == result_row["config_hash"]
    assert m["git_sha"] == result_row["git_sha"]
    assert m["source_provenance"]["config_id"] == result_row["config_id"]
    assert m["source_provenance"]["schedule_hash"] == result_row["schedule_hash"]
    assert m["source_provenance"]["seed_index"] == result_row["seed_index"]


def test_frozen_fixture05_trace_only():
    m = validate_bundle_dir(FIX05_BUNDLE)
    assert not m["files"]["battle_log"]["present"]
    assert m["files"]["decision_trace"]["present"]

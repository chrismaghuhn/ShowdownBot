from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_bundle import export_bundle
from showdownbot_studio_exporter.export_decisions import load_trace_rows

FIX01_TRACE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "decision_trace.jsonl"
FIX01_LOG = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "battle.log"


def test_refuse_v1_trace_export():
    rows = load_trace_rows(FIX01_TRACE)
    row = copy.deepcopy(rows[0])
    row["trace_schema_version"] = "decision-trace-v1"
    row.pop("chosen_candidate_key", None)
    path = Path(tempfile.mkdtemp()) / "v1.jsonl"
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ExportRefuse) as exc:
        load_trace_rows(path)
    assert exc.value.reason == "unsupported_trace_v1"


def test_v1_with_log_replay_only(tmp_path):
    rows = load_trace_rows(FIX01_TRACE)
    row = copy.deepcopy(rows[0])
    row["trace_schema_version"] = "decision-trace-v1"
    trace = tmp_path / "v1.jsonl"
    trace.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    out = tmp_path / "bundle"
    # trace export refused when passed as decision-trace
    with pytest.raises(ExportRefuse):
        export_bundle(out=out, battle_log=FIX01_LOG, decision_trace=trace)
    out2 = tmp_path / "bundle2"
    export_bundle(out=out2, battle_log=FIX01_LOG, results=STUDIO_ROOT / "fixtures/viewer-v0/sources/fixture-01/results.jsonl")

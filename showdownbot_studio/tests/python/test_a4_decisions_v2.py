from __future__ import annotations

import copy
import json

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "decision_trace.jsonl"


def test_v2_row_exports():
    rows = load_trace_rows(FIX01)
    row = copy.deepcopy(rows[2])
    row["trace_schema_version"] = "decision-trace-v2"
    blob, _, version = export_decisions_jsonl([row])
    assert version == "decision-trace-v2"
    out = json.loads(blob.decode("utf-8").splitlines()[0])
    assert out["decision_index"] == row["decision_index"]

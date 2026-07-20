from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows


FIX01_TRACE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "decision_trace.jsonl"


def test_v3_export_produces_three_phases():
    rows = load_trace_rows(FIX01_TRACE)
    blob, warnings, version = export_decisions_jsonl(rows)
    assert version == "decision-trace-v3"
    phases = set()
    has_chosen = False
    for line in blob.decode("utf-8").splitlines():
        row = json.loads(line)
        phases.add(row["decision_phase"])
        if row.get("chosen_candidate_key"):
            has_chosen = True
    assert phases == {"team_preview", "forced_replacement", "regular_turn"}
    assert has_chosen


def test_v3_aggregation_null_with_warning():
    rows = load_trace_rows(FIX01_TRACE)
    blob, warnings, _ = export_decisions_jsonl(rows)
    row = json.loads(blob.decode("utf-8").splitlines()[0])
    assert row["aggregation"]["mode"] is None
    assert row["warning_count"] >= 1


def test_v3_empty_candidates_team_preview_ok():
    rows = load_trace_rows(FIX01_TRACE)
    blob, _, _ = export_decisions_jsonl(rows)
    row0 = json.loads(blob.decode("utf-8").splitlines()[0])
    assert row0["candidates"] == []
    assert row0["chosen_candidate_key"] is None

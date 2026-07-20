from __future__ import annotations

import hashlib
import json

import pytest

from conftest import SMOKE

from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows

SMOKE_TRACE = SMOKE / "decision_trace.jsonl"
PINNED = "7070338b77425621b6c3720e1f5cea651dff832dc6a0a8884de047c6647ff197"


def test_smoke_trace_hash_pinned():
    got = hashlib.sha256(SMOKE_TRACE.read_bytes()).hexdigest()
    assert got == PINNED


def test_smoke_nonempty_chosen_rows_export():
    rows = load_trace_rows(SMOKE_TRACE)
    blob, _, _ = export_decisions_jsonl(rows)
    lines = blob.decode("utf-8").splitlines()
    assert len(lines) == len(rows)
    nonempty = 0
    for line in lines:
        row = json.loads(line)
        if row.get("candidates"):
            if row.get("chosen_candidate_key") is not None:
                nonempty += 1
    assert nonempty > 0


def test_smoke_empty_candidate_rows_export_clean():
    rows = load_trace_rows(SMOKE_TRACE)
    blob, _, _ = export_decisions_jsonl(rows)
    by_index = {r["decision_index"]: r for r in rows}
    for out_line in blob.decode("utf-8").splitlines():
        out = json.loads(out_line)
        src = by_index[out["decision_index"]]
        if not src.get("candidates"):
            assert out["chosen_candidate_key"] is None

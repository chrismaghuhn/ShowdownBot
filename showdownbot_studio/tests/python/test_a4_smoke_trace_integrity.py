from __future__ import annotations

import hashlib
import json

from conftest import SMOKE, read_normalized_bytes

from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows

SMOKE_TRACE = SMOKE / "decision_trace.jsonl"
# Checkout-independent: sha256 of the file's bytes with CRLF normalized to LF (matches
# the git blob, which is LF). Hashing raw read_bytes() here is checkout-dependent --
# core.autocrlf can check this same blob out as CRLF depending on the local machine and
# .gitattributes coverage at checkout time. See SOURCES.md's "104-candidate
# bounded-render" entry for the measured CRLF/LF split this constant used to encode.
PINNED = "546693fc6e5d3efeeb69f673c4aa270524c0ef639f0fbff861b8b23d5a1a146f"


def test_smoke_trace_hash_pinned():
    got = hashlib.sha256(read_normalized_bytes(SMOKE_TRACE)).hexdigest()
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

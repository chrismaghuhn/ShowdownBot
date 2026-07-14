from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.eval.accuracy_baseline import BaselineRow, canonical_float, freeze_baseline


def test_canonical_float_representation_is_stable():
    assert canonical_float(1.0) == canonical_float(1.00000000)
    assert canonical_float(0.1 + 0.2) == canonical_float(0.3)  # rounds away fp noise
    assert isinstance(canonical_float(1.5), str)
    assert canonical_float(-0.0) == canonical_float(0.0)  # -0.0 == 0.0; must not look like a diff


def test_freeze_baseline_produces_one_row_per_decision(tmp_path, monkeypatch):
    # A minimal fake corpus of 2 ExtractedDecision-shaped inputs, using a stub chooser so this
    # test doesn't require the real calc backend -- freeze_baseline's job is the FILE FORMAT and
    # provenance capture, not re-testing heuristic_choose_for_request itself.
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    calls = []

    def fake_choose(decision, *, accuracy_mode):
        calls.append((decision, accuracy_mode))
        return f"move 1", 0.42

    decisions = [
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=1,
            request_hash="reqhash0", log_prefix_hash="prefixhash0", _debug_prefix_line_count=1,
        ),
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=2,
            request_hash="reqhash1", log_prefix_hash="prefixhash1", _debug_prefix_line_count=1,
        ),
    ]

    out_path = tmp_path / "baseline.jsonl"
    rows = freeze_baseline(
        decisions, out_path=out_path, chooser=fake_choose,
        source_commit="deadbeef", config_hash="cafef00d",
        python_version="3.11.0", dependency_lock_hash="lockhash123",
    )
    assert len(rows) == 2
    assert [c[1] for c in calls] == [False, False]  # accuracy_mode explicitly off, every call

    with open(out_path, "r", encoding="utf-8") as fh:
        written = [json.loads(line) for line in fh]
    assert len(written) == 2
    for row in written:
        assert row["source_commit"] == "deadbeef"
        assert row["config_hash"] == "cafef00d"
        assert row["python_version"] == "3.11.0"
        assert row["dependency_lock_hash"] == "lockhash123"
        assert row["accuracy_mode"] is False
        assert isinstance(row["score"], str)  # canonical float, not a raw Python float
        assert "request_hash" in row and "log_prefix_hash" in row

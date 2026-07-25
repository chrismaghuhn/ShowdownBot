"""Protocol contract fixture guard (spec section 8.1, studio-protocol-contract lane). Confirms
the JSONL transcript and golden-event fixtures exist with real content -- the gdUnit-side test
that actually replays the transcript and compares it against the golden file lives at
godot/tests/protocol/test_protocol_decoder_local_transcript.gd.
"""
from __future__ import annotations

import json

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_FIXTURE_DIR = STUDIO_ROOT / "fixtures" / "live-protocol-v0" / "local-spectate-01"


def test_transcript_jsonl_exists_and_has_valid_frame_objects():
    path = _FIXTURE_DIR / "transcript.jsonl"
    assert path.is_file(), f"missing frozen protocol transcript fixture: {path}"
    raw_lines = [raw for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]
    assert raw_lines, f"transcript fixture is empty: {path}"
    for raw_line in raw_lines:
        obj = json.loads(raw_line)
        assert "sequence" in obj and "raw_frame" in obj


def test_golden_events_jsonl_exists_and_has_valid_event_objects():
    path = _FIXTURE_DIR / "golden_events.jsonl"
    assert path.is_file(), f"missing golden-event fixture: {path}"
    raw_lines = [raw for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]
    assert raw_lines, f"golden-event fixture is empty: {path}"
    for raw_line in raw_lines:
        obj = json.loads(raw_line)
        assert "event_type" in obj


def test_sources_md_documents_both_fixtures():
    path = _FIXTURE_DIR.parent / "SOURCES.md"
    text = path.read_text(encoding="utf-8")
    assert "transcript.jsonl" in text and "golden_events.jsonl" in text

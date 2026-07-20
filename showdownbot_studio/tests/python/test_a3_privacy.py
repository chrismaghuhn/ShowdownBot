from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT, SYNTHETIC

from showdownbot_studio_exporter.export_battle import export_battle_jsonl, read_battle_log
from showdownbot_studio_exporter.privacy import PRIVACY_PROFILE, pseudonymize_request_payload


PRIVACY_LOG = SYNTHETIC / "privacy_leak.log"
FIXTURE10_LOG = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-10" / "battle.log"


def test_privacy_profile_constant():
    assert PRIVACY_PROFILE["profile"] == "portable-pseudonymous-v1"


def test_fixture10_request_payload_is_json_parsed():
    from showdownbot_studio_exporter.privacy import parse_request_line

    lines = read_battle_log(FIXTURE10_LOG)
    req_lines = [ln for ln in lines if ln.startswith("|request|")]
    assert req_lines
    payload = parse_request_line(req_lines[0])
    assert isinstance(payload, dict)
    assert payload["side"]["name"] == "LeakPlayerOne"


def test_fixture10_request_side_name_pseudonymized():
    from showdownbot_studio_exporter.privacy import parse_request_line

    lines = read_battle_log(FIXTURE10_LOG)
    payload = parse_request_line(next(ln for ln in lines if ln.startswith("|request|")))
    cleaned = pseudonymize_request_payload(payload)
    assert cleaned["side"]["name"] == "p1"
    battle_bytes = export_battle_jsonl(lines)
    assert b"LeakPlayerOne" not in battle_bytes


def test_fixture10_request_nickname_stripped_or_pseudonymized():
    lines = read_battle_log(FIXTURE10_LOG)
    battle_bytes = export_battle_jsonl(lines)
    assert b"NickLeak" not in battle_bytes


def test_fixture10_other_literals_absent():
    lines = read_battle_log(FIXTURE10_LOG)
    battle_bytes = export_battle_jsonl(lines)
    for needle in (b"http://", b"LeakPlayerTwo", b"999", b"C:\\Users\\fixture\\leak.log"):
        assert needle not in battle_bytes


def test_fixture10_source_unchanged():
    before = hashlib.sha256(FIXTURE10_LOG.read_bytes()).hexdigest()
    export_battle_jsonl(read_battle_log(FIXTURE10_LOG))
    after = hashlib.sha256(FIXTURE10_LOG.read_bytes()).hexdigest()
    assert before == after


def test_privacy_leak_matches_fixture10_source():
    assert PRIVACY_LOG.read_bytes() == FIXTURE10_LOG.read_bytes()

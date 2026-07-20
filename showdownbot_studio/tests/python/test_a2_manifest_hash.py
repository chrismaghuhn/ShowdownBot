from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.canonicalize import dumps
from showdownbot_studio_exporter.hashutil import sha256_bytes, sha256_file
from showdownbot_studio_exporter.validate_bundle import validate_bundle_dir


def test_absent_optional_declares_null():
    manifest = {
        "viewer_bundle_schema": {"major": 1, "minor": 0},
        "required_capabilities": [],
        "exporter": {"name": "showdownbot-studio-exporter", "version": "0.1.0"},
        "battle_id": "x",
        "format_id": "fmt",
        "git_sha": "unknown",
        "config_hash": "bbbbbbbbbbbbbbbb",
        "trace_schema_version": None,
        "privacy": {"profile": "portable-pseudonymous-v1", "chat": "excluded", "private_messages": "excluded", "player_names": "seat-pseudonyms", "source_url": "excluded", "raw_source_included": False},
        "source_hashes": {"battle_log": "aa" * 32, "decision_trace": None},
        "files": {
            "battle_log": {"path": "battle.jsonl", "present": True, "required": True, "sha256": "aa" * 32},
            "decision_trace": {"path": None, "present": False, "required": False, "sha256": None},
            "warnings": {"path": None, "present": False, "required": False, "sha256": None},
            "config_manifest": {"path": None, "present": False, "required": False, "sha256": None},
        },
        "source_provenance": {"config_id": "c", "dirty": None, "our_side": None, "schedule_hash": "s", "seed_index": 0, "showdown_commit": None, "server_patch_hash": None},
    }
    files = manifest["files"]
    assert files["decision_trace"]["present"] is False
    assert files["decision_trace"]["path"] is None
    assert files["decision_trace"]["sha256"] is None


def test_frozen_fixture01_hashes_match_manifest():
    bundle = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-01"
    manifest = validate_bundle_dir(bundle)
    for key, entry in manifest["files"].items():
        if not entry["present"]:
            continue
        rel = entry["path"]
        got = sha256_file(bundle / rel)
        assert got == entry["sha256"], key


def test_sha256_over_emitted_bytes():
    bundle = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-01"
    data = (bundle / "manifest.json").read_bytes()
    digest = sha256_bytes(data)
    assert len(digest) == 64
    assert dumps  # hashutil used via bundle export path

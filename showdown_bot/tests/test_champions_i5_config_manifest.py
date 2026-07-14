"""Regression: frozen I5 config-manifest sidecar matches result-row config_hash."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.eval.result_jsonl import make_config_hash

_REPO_ROOT = Path(__file__).resolve().parents[2]
_I5_DIR = _REPO_ROOT / "data" / "eval" / "champions-panel-v0" / "smoke-i5"
_CONFIG_MANIFEST = _I5_DIR / "results.jsonl.config-manifest.json"
_RESULTS = _I5_DIR / "results.jsonl"
_EXPECTED_CONFIG_HASH = "b8a0aa12b9f6c4de"


@pytest.fixture
def i5_config_manifest() -> dict:
    if not _CONFIG_MANIFEST.is_file():
        pytest.skip(f"missing frozen artifact: {_CONFIG_MANIFEST}")
    return json.loads(_CONFIG_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture
def i5_result_rows() -> list[dict]:
    if not _RESULTS.is_file():
        pytest.skip(f"missing frozen artifact: {_RESULTS}")
    return [json.loads(line) for line in _RESULTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_i5_frozen_config_manifest_rehashes_to_config_hash(i5_config_manifest):
    manifest = i5_config_manifest["manifest"]
    stored = i5_config_manifest["config_hash"]
    assert stored == _EXPECTED_CONFIG_HASH
    assert make_config_hash(manifest) == stored


def test_i5_result_rows_share_frozen_config_hash(i5_config_manifest, i5_result_rows):
    stored = i5_config_manifest["config_hash"]
    assert len(i5_result_rows) == 10
    assert {row["config_hash"] for row in i5_result_rows} == {stored}

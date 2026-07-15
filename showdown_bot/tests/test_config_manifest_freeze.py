"""I7a-C P1.4: reproducible config-manifest freeze sidecar.

``write_config_manifest_sidecar`` is the ONE dedicated, fail-closed writer for
``<results>.config-manifest.json`` -- it must call ``effective_config_manifest`` (the
same function the CLI's live config_hash computation uses), verify the computed hash
matches every row's ``config_hash`` in the target results file, and refuse to silently
overwrite an existing sidecar or freeze against a results file with missing/inconsistent
``config_hash`` values.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval.config_manifest_freeze import (
    ConfigManifestFreezeError,
    write_config_manifest_sidecar,
)
from showdown_bot.eval.config_env import effective_config_manifest
from showdown_bot.eval.result_jsonl import make_config_hash

FORMAT_ID = "gen9championsvgc2026regma"


def _write_results(tmp_path, config_hash: str, n: int = 2):
    path = tmp_path / "results.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"battle_id": f"b{i}", "config_hash": config_hash}) + "\n")
    return path


def test_write_config_manifest_sidecar_matches_effective_manifest_hash(tmp_path):
    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)

    out_path = write_config_manifest_sidecar(
        results_path, agent="heuristic", format_id=FORMAT_ID, env={},
    )

    assert out_path == results_path.with_name(results_path.name + ".config-manifest.json")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["config_hash"] == config_hash
    assert payload["manifest"] == manifest
    assert make_config_hash(payload["manifest"]) == payload["config_hash"]


def test_write_config_manifest_sidecar_fails_closed_on_hash_mismatch(tmp_path):
    results_path = _write_results(tmp_path, "deadbeefdeadbeef")

    with pytest.raises(ConfigManifestFreezeError, match="mismatch"):
        write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

    assert not results_path.with_name(results_path.name + ".config-manifest.json").exists()


def test_write_config_manifest_sidecar_fails_closed_on_missing_results(tmp_path):
    missing = tmp_path / "nope.jsonl"
    with pytest.raises(ConfigManifestFreezeError, match="does not exist|missing|empty"):
        write_config_manifest_sidecar(missing, agent="heuristic", format_id=FORMAT_ID, env={})


def test_write_config_manifest_sidecar_fails_closed_on_inconsistent_row_hashes(tmp_path):
    path = tmp_path / "results.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"battle_id": "b0", "config_hash": "aaaaaaaaaaaaaaaa"}) + "\n")
        fh.write(json.dumps({"battle_id": "b1", "config_hash": "bbbbbbbbbbbbbbbb"}) + "\n")

    with pytest.raises(ConfigManifestFreezeError, match="inconsistent|multiple"):
        write_config_manifest_sidecar(path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_write_config_manifest_sidecar_fails_closed_on_missing_row_config_hash(tmp_path):
    path = tmp_path / "results.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"battle_id": "b0"}) + "\n")

    with pytest.raises(ConfigManifestFreezeError, match="config_hash"):
        write_config_manifest_sidecar(path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_write_config_manifest_sidecar_refuses_to_overwrite_existing_sidecar(tmp_path):
    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)

    write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

    with pytest.raises(ConfigManifestFreezeError, match="already exists"):
        write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

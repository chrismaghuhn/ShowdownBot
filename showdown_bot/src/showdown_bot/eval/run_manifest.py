"""Run-level provenance: run_id + a self-describing manifest sidecar (T3f Task 3).

A single ``--result-out`` run gets one ``run_id`` (constant across every row) and one
``<result-out>.manifest.json`` sidecar, so T5 can consume a run without re-deriving anything.
``run_id`` = ``sha1(canonical([seed_base, schedule_hash, config_hash, start_ts]))[:16]``,
where ``start_ts`` is captured once per run — so repeating a run yields a new ``run_id``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

# Repo root (contains config/ and tools/): this file is at
# <repo>/showdown_bot/src/showdown_bot/eval/run_manifest.py -> parents[4] == <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROVENANCE = _REPO_ROOT / "config" / "eval" / "provenance.yaml"
_SERVER_PATCH = _REPO_ROOT / "tools" / "eval" / "patches" / "pokemon-showdown-seeded-battle.patch"


class ProvenanceError(ValueError):
    """``provenance.yaml`` is missing or malformed."""


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha16(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()[:16]


def load_showdown_commit(path=None) -> str:
    """Read ``showdown_commit`` from ``config/eval/provenance.yaml`` (never a code constant)."""
    p = Path(path) if path is not None else _PROVENANCE
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ProvenanceError(f"provenance config not found: {p}") from exc
    commit = (data or {}).get("showdown_commit")
    if not commit:
        raise ProvenanceError(f"provenance config missing 'showdown_commit': {p}")
    return str(commit)


def server_patch_hash(patch_path=None) -> str | None:
    """Content hash of the versioned seeded-battle server patch, or None if unreadable."""
    p = Path(patch_path) if patch_path is not None else _SERVER_PATCH
    try:
        return _sha16(p.read_bytes())
    except OSError:
        return None


def make_run_id(seed_base, schedule_hash, config_hash, start_ts) -> str:
    """Stable per-run id. Constant across a run's rows (all four inputs fixed for the run),
    but changes when the run is repeated because ``start_ts`` is captured once per run."""
    return _sha16(_canonical([seed_base, schedule_hash, config_hash, start_ts]).encode("utf-8"))


def manifest_path_for(result_out: str) -> str:
    """Deterministic sidecar path: ``<result_out>.manifest.json``."""
    return f"{result_out}.manifest.json"


def build_run_manifest(*, run_id, seed_base, schedule_hash, panel_hash, config_hash,
                       start_ts, pythonhashseed, cli_invocation, git_sha, dirty,
                       showdown_commit=None, patch_hash=None,
                       provenance_path=None, patch_path=None) -> dict:
    """Assemble the run manifest. ``showdown_commit``/``patch_hash`` default to the config
    value + the patch-file content hash respectively (injectable for tests)."""
    return {
        "run_id": run_id,
        "seed_base": seed_base,
        "schedule_hash": schedule_hash,
        "panel_hash": panel_hash,
        "config_hash": config_hash,
        "start_ts": start_ts,
        "pythonhashseed": pythonhashseed,
        "cli_invocation": cli_invocation,
        "showdown_commit": (
            showdown_commit if showdown_commit is not None
            else load_showdown_commit(provenance_path)
        ),
        "server_patch_hash": patch_hash if patch_hash is not None else server_patch_hash(patch_path),
        "git_sha": git_sha,
        "dirty": dirty,
    }


def write_run_manifest(result_out: str, manifest: dict) -> str:
    """Write the manifest once to ``manifest_path_for(result_out)``; return that path."""
    path = manifest_path_for(result_out)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return path

"""Atomic bundle export orchestration."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from .canonicalize import dumps
from .errors import ExportRefuse
from .export_battle import export_battle_jsonl, read_battle_log
from .export_decisions import export_decisions_jsonl, load_trace_rows
from .hashutil import sha256_bytes, sha256_file
from .join import join_request_protocol_indices, load_log_lines
from .pathsafety import check_output_path
from .privacy import PRIVACY_PROFILE
from .provenance import ProvenanceSources, load_json, load_result_row, resolve_provenance
from .validate_bundle import validate_bundle_dir
from .warnings_emit import build_warnings

EXPORTER_NAME = "showdownbot-studio-exporter"
EXPORTER_VERSION = "0.1.0"


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _build_files_manifest(
    *,
    has_battle: bool,
    has_decisions: bool,
    has_warnings: bool,
    has_config: bool,
    digests: dict[str, str | None],
) -> dict[str, Any]:
    def entry(present: bool, required: bool, rel: str | None, digest: str | None) -> dict[str, Any]:
        if present:
            return {"path": rel, "present": True, "required": required, "sha256": digest}
        return {"path": None, "present": False, "required": required, "sha256": None}

    return {
        "battle_log": entry(has_battle, has_battle, "battle.jsonl" if has_battle else None, digests.get("battle")),
        "decision_trace": entry(
            has_decisions, has_decisions, "decisions.jsonl" if has_decisions else None, digests.get("decisions")
        ),
        "warnings": entry(has_warnings, False, "warnings.json" if has_warnings else None, digests.get("warnings")),
        "config_manifest": entry(
            has_config, False, "config-manifest.json" if has_config else None, digests.get("config")
        ),
    }


def export_bundle(
    *,
    out: Path,
    battle_log: Path | None = None,
    decision_trace: Path | None = None,
    results: Path | None = None,
    run_manifest: Path | None = None,
    config_manifest: Path | None = None,
    battle_id: str | None = None,
    repo_root: Path | None = None,
    replace_fn=os.replace,
) -> None:
    """Write a complete bundle to ``out`` via sibling staging + atomic replace."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[4]

    has_battle = battle_log is not None
    has_trace = decision_trace is not None
    if not has_battle and not has_trace:
        raise ExportRefuse("missing_mode_inputs", "need --battle-log and/or --decision-trace")

    input_paths = [p for p in (battle_log, decision_trace, results, run_manifest, config_manifest) if p]
    check_output_path(out, input_paths=input_paths, repo_root=repo_root)

    staging = out.parent / f".{out.name}.staging-{uuid4()}"
    try:
        staging.mkdir(parents=True, exist_ok=False)
        _export_to_staging(
            staging,
            battle_log=battle_log,
            decision_trace=decision_trace,
            results=results,
            run_manifest=run_manifest,
            config_manifest=config_manifest,
            battle_id=battle_id,
        )
        validate_bundle_dir(staging)
        try:
            replace_fn(staging, out)
        except OSError as exc:
            raise ExportRefuse("atomic_publish_unsupported", str(exc)) from exc
    except Exception:
        # Own only staging. Never delete --out: a raced/foreign tree must survive.
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _export_to_staging(
    staging: Path,
    *,
    battle_log: Path | None,
    decision_trace: Path | None,
    results: Path | None,
    run_manifest: Path | None,
    config_manifest: Path | None,
    battle_id: str | None,
) -> None:
    trace_rows = load_trace_rows(decision_trace) if decision_trace else None
    if trace_rows and not battle_id:
        battle_ids = {r["battle_id"] for r in trace_rows}
        if len(battle_ids) == 1:
            battle_id = next(iter(battle_ids))
        elif len(battle_ids) > 1:
            raise ExportRefuse("ambiguous_battle_id", "multiple battle_id values; pass --battle-id")
    if trace_rows and battle_id:
        trace_rows = [r for r in trace_rows if r.get("battle_id") == battle_id]
        if not trace_rows:
            raise ExportRefuse("battle_id_mismatch", f"no trace rows for battle_id {battle_id!r}")
    result_row = load_result_row(results, battle_id) if results else None
    manifest_obj = load_json(run_manifest) if run_manifest else None
    config_obj = load_json(config_manifest) if config_manifest else None

    prov = resolve_provenance(
        ProvenanceSources(trace_rows=trace_rows, result_row=result_row, run_manifest=manifest_obj, config_manifest=config_obj),
        battle_id_override=battle_id or (result_row.get("battle_id") if result_row else None),
    )

    if config_obj and config_obj.get("config_hash") != prov.config_hash:
        raise ExportRefuse("config_hash_mismatch", "config manifest disagrees with provenance config_hash")

    has_battle = battle_log is not None
    has_trace = trace_rows is not None

    log_lines: list[str] = []
    battle_bytes: bytes | None = None
    battle_source_hash: str | None = None
    if has_battle:
        log_lines = read_battle_log(battle_log)
        battle_bytes = export_battle_jsonl(log_lines)
        battle_source_hash = sha256_file(battle_log)

    join_map: dict[int, int | None] = {}
    if has_battle and has_trace:
        join_map = join_request_protocol_indices(trace_rows, log_lines)

    decisions_bytes: bytes | None = None
    decision_warnings: dict[int, list[str]] = {}
    trace_version: str | None = None
    trace_source_hash: str | None = None
    if has_trace:
        decisions_bytes, decision_warnings, trace_version = export_decisions_jsonl(
            trace_rows,
            request_protocol_index_by_decision=join_map if has_battle else None,
            manifest_battle_id=prov.battle_id,
            manifest_our_side=prov.our_side,
        )
        trace_source_hash = sha256_file(decision_trace)

    warnings_obj = build_warnings(decision_warnings) if decision_warnings else {"warnings": []}
    warnings_bytes = dumps(warnings_obj)
    has_warnings = bool(warnings_obj.get("warnings"))

    config_bytes: bytes | None = None
    has_config = config_obj is not None
    if has_config:
        config_bytes = dumps(config_obj)

    digests: dict[str, str | None] = {}
    if battle_bytes is not None:
        _write_bytes(staging / "battle.jsonl", battle_bytes)
        digests["battle"] = sha256_bytes(battle_bytes)
    if decisions_bytes is not None:
        _write_bytes(staging / "decisions.jsonl", decisions_bytes)
        digests["decisions"] = sha256_bytes(decisions_bytes)
    if has_warnings:
        _write_bytes(staging / "warnings.json", warnings_bytes)
        digests["warnings"] = sha256_bytes(warnings_bytes)
    if config_bytes is not None:
        _write_bytes(staging / "config-manifest.json", config_bytes)
        digests["config"] = sha256_bytes(config_bytes)

    mode_trace_version = trace_version if has_trace else None
    manifest = {
        "viewer_bundle_schema": {"major": 1, "minor": 0},
        "required_capabilities": [],
        "exporter": {"name": EXPORTER_NAME, "version": EXPORTER_VERSION},
        "battle_id": prov.battle_id,
        "format_id": prov.format_id,
        "git_sha": prov.git_sha,
        "config_hash": prov.config_hash,
        "trace_schema_version": mode_trace_version,
        "privacy": PRIVACY_PROFILE,
        "source_hashes": {
            "battle_log": battle_source_hash if has_battle else None,
            "decision_trace": trace_source_hash if has_trace else None,
        },
        "files": _build_files_manifest(
            has_battle=has_battle,
            has_decisions=has_trace,
            has_warnings=has_warnings,
            has_config=has_config,
            digests=digests,
        ),
        "source_provenance": {
            "config_id": prov.config_id,
            "dirty": prov.dirty,
            "our_side": prov.our_side if has_trace else None,
            "schedule_hash": prov.schedule_hash,
            "seed_index": prov.seed_index,
            "showdown_commit": prov.showdown_commit,
            "server_patch_hash": prov.server_patch_hash,
        },
    }
    _write_bytes(staging / "manifest.json", dumps(manifest))

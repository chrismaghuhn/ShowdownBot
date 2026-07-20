"""Bundle directory validation (reader stage §8.6)."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ExportRefuse
from .hashutil import sha256_file

SUPPORTED_MAJORS = frozenset({1})
LOGICAL_FILE_KEYS = ("battle_log", "decision_trace", "warnings", "config_manifest")
LOGICAL_FILE_KEY_SET = frozenset(LOGICAL_FILE_KEYS)
CANONICAL_PATHS = {
    "battle_log": "battle.jsonl",
    "decision_trace": "decisions.jsonl",
    "warnings": "warnings.json",
    "config_manifest": "config-manifest.json",
}
SUPPORTED_TRACE_SCHEMA_VERSIONS = frozenset({"decision-trace-v2", "decision-trace-v3"})


class BundleValidationError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(f"{reason}: {message}")


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BundleValidationError("malformed_type", f"{label} must be an object")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise BundleValidationError("malformed_type", f"{label} must be a boolean")
    return value


def _derive_mode(files: dict[str, Any]) -> str:
    bl = _require_object(files.get("battle_log"), "files.battle_log")
    dt = _require_object(files.get("decision_trace"), "files.decision_trace")
    bl_req = _require_bool(bl.get("required"), "files.battle_log.required")
    bl_pres = _require_bool(bl.get("present"), "files.battle_log.present")
    dt_req = _require_bool(dt.get("required"), "files.decision_trace.required")
    dt_pres = _require_bool(dt.get("present"), "files.decision_trace.present")
    if bl_req != bl_pres or dt_req != dt_pres:
        raise BundleValidationError("malformed_manifest", "required != present on mode keys")
    if bl_pres and dt_pres:
        return "replay_trace"
    if bl_pres:
        return "replay_only"
    if dt_pres:
        return "trace_only"
    raise BundleValidationError("missing_mode", "bundle has neither battle_log nor decision_trace")


def _resolve_declared_path(bundle_root: Path, rel_path: str) -> Path:
    if not isinstance(rel_path, str) or not rel_path:
        raise BundleValidationError("malformed_path", "empty path")
    if rel_path.startswith(("/", "\\")) or "\\" in rel_path:
        raise BundleValidationError("malformed_path", f"non-portable path {rel_path!r}")
    pure = PurePosixPath(rel_path)
    if pure.is_absolute() or pure.anchor:
        raise BundleValidationError("malformed_path", f"absolute path {rel_path!r}")
    if ".." in pure.parts or any(part == "" for part in pure.parts):
        raise BundleValidationError("malformed_path", f"path escapes or is empty: {rel_path!r}")
    if len(pure.parts) != 1:
        raise BundleValidationError("malformed_path", f"subdirectory path not allowed: {rel_path!r}")

    candidate = (bundle_root / pure.as_posix()).resolve()
    root = bundle_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BundleValidationError("path_escape", f"path escapes bundle: {rel_path!r}") from exc
    if candidate.parent != root:
        raise BundleValidationError("path_escape", f"path not a direct child: {rel_path!r}")
    return candidate


def validate_bundle_dir(path: Path) -> dict[str, Any]:
    path = path.resolve()
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise BundleValidationError("missing_manifest", "manifest.json not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise BundleValidationError("malformed_type", "manifest must be an object")

    major = manifest.get("viewer_bundle_schema", {}).get("major")
    if major not in SUPPORTED_MAJORS:
        raise BundleValidationError("unsupported_major", f"unsupported major {major!r}")

    for cap in manifest.get("required_capabilities") or []:
        raise BundleValidationError("unsupported_capability", f"unsupported capability {cap!r}")

    files = _require_object(manifest.get("files"), "files")
    unknown = set(files) - LOGICAL_FILE_KEY_SET
    if unknown:
        raise BundleValidationError("unknown_logical_key", f"unknown files keys: {sorted(unknown)}")
    missing_keys = LOGICAL_FILE_KEY_SET - set(files)
    if missing_keys:
        raise BundleValidationError("malformed_manifest", f"missing files keys: {sorted(missing_keys)}")

    mode = _derive_mode(files)

    for key in ("warnings", "config_manifest"):
        entry = _require_object(files.get(key), f"files.{key}")
        required = _require_bool(entry.get("required"), f"files.{key}.required")
        if required is True:
            raise BundleValidationError("malformed_manifest", f"{key} must not be required")

    declared_names: set[str] = set()
    seen_paths: set[str] = set()
    for logical in LOGICAL_FILE_KEYS:
        entry = _require_object(files.get(logical), f"files.{logical}")
        present = _require_bool(entry.get("present"), f"files.{logical}.present")
        _require_bool(entry.get("required"), f"files.{logical}.required")
        rel_path = entry.get("path")
        declared_sha = entry.get("sha256")
        if present:
            if rel_path is None:
                raise BundleValidationError("malformed_manifest", f"{logical}: present without path")
            if not isinstance(rel_path, str):
                raise BundleValidationError("malformed_type", f"files.{logical}.path must be a string")
            canonical = CANONICAL_PATHS[logical]
            if rel_path != canonical:
                raise BundleValidationError(
                    "noncanonical_path",
                    f"{logical} must map to {canonical!r}, got {rel_path!r}",
                )
            if rel_path in seen_paths:
                raise BundleValidationError("duplicate_path", f"path reused: {rel_path!r}")
            seen_paths.add(rel_path)
            file_path = _resolve_declared_path(path, rel_path)
            if not file_path.is_file():
                raise BundleValidationError("missing_file", f"missing {rel_path}")
            got = sha256_file(file_path)
            if got != declared_sha:
                raise BundleValidationError("hash_mismatch", f"{rel_path} hash mismatch")
            declared_names.add(file_path.name)
        else:
            if rel_path is not None or declared_sha is not None:
                raise BundleValidationError("malformed_manifest", f"{logical}: absent must have null path/sha256")

    for child in path.iterdir():
        if child.is_dir():
            raise BundleValidationError("undeclared_subdirectory", f"subdirectory not allowed: {child.name}")
        if child.name == "manifest.json":
            continue
        if child.is_file() and child.name not in declared_names:
            raise BundleValidationError("undeclared_file", f"undeclared file {child.name}")

    _check_nullability(manifest, mode)

    if mode in ("replay_trace", "trace_only"):
        version = manifest.get("trace_schema_version")
        if version not in SUPPORTED_TRACE_SCHEMA_VERSIONS:
            raise BundleValidationError(
                "unsupported_trace_schema_version",
                f"unsupported trace_schema_version {version!r}",
            )
        decisions_rel = files["decision_trace"]["path"]
        _validate_decision_identities(_resolve_declared_path(path, decisions_rel))

    return manifest


def _check_nullability(manifest: dict[str, Any], mode: str) -> None:
    if mode == "replay_only":
        if manifest.get("trace_schema_version") is not None:
            raise BundleValidationError("nullability", "trace_schema_version must be null in replay-only")
        if manifest.get("source_hashes", {}).get("decision_trace") is not None:
            raise BundleValidationError("nullability", "source_hashes.decision_trace must be null")
        sp = manifest.get("source_provenance") or {}
        if sp.get("our_side") is not None:
            raise BundleValidationError("nullability", "our_side must be null in replay-only")
    if mode == "trace_only":
        if manifest.get("source_hashes", {}).get("battle_log") is not None:
            raise BundleValidationError("nullability", "source_hashes.battle_log must be null in trace-only")


def _validate_decision_identities(decisions_path: Path) -> None:
    seen: set[int] = set()
    with decisions_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            idx = row["decision_index"]
            if idx in seen:
                raise BundleValidationError("duplicate_decision_index", f"duplicate decision_index {idx}")
            seen.add(idx)


def validate_bundle_dir_or_refuse(path: Path) -> None:
    try:
        validate_bundle_dir(path)
    except BundleValidationError as exc:
        raise ExportRefuse(exc.reason, exc.message) from exc

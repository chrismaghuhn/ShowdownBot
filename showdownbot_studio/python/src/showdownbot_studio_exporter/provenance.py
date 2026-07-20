"""Provenance resolution per contract §11.1.3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ExportRefuse


@dataclass
class ProvenanceSources:
    trace_rows: list[dict[str, Any]] | None = None
    result_row: dict[str, Any] | None = None
    run_manifest: dict[str, Any] | None = None
    config_manifest: dict[str, Any] | None = None


@dataclass
class ResolvedProvenance:
    battle_id: str
    format_id: str
    git_sha: str
    config_hash: str
    config_id: str
    schedule_hash: str
    seed_index: int
    our_side: str | None
    dirty: bool | None
    showdown_commit: str | None
    server_patch_hash: str | None
    trace_schema_version: str | None


_TRACE_IDENTITY_FIELDS = (
    "battle_id",
    "git_sha",
    "config_hash",
    "config_id",
    "schedule_hash",
    "seed_index",
    "format_id",
    "our_side",
    "trace_schema_version",
)


def _first_trace(sources: ProvenanceSources) -> dict[str, Any] | None:
    if sources.trace_rows:
        return sources.trace_rows[0]
    return None


def _agree_selected_trace_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) <= 1:
        return
    first = rows[0]
    for idx, row in enumerate(rows[1:], start=1):
        for field in _TRACE_IDENTITY_FIELDS:
            left = first.get(field)
            right = row.get(field)
            if str(left) != str(right):
                raise ExportRefuse(
                    "provenance_disagreement",
                    f"field {field!r} disagrees across trace rows[0] vs [{idx}]: {left!r} != {right!r}",
                )


def _pick(field: str, sources: ProvenanceSources, order: list[str]) -> Any:
    values: dict[str, Any] = {}
    trace = _first_trace(sources)
    if trace and field in trace:
        values["trace"] = trace[field]
    if sources.result_row and field in sources.result_row:
        values["result"] = sources.result_row[field]
    manifest_field_map = {
        "git_sha": "git_sha",
        "config_hash": "config_hash",
        "schedule_hash": "schedule_hash",
        "dirty": "dirty",
        "showdown_commit": "showdown_commit",
        "server_patch_hash": "server_patch_hash",
    }
    if sources.run_manifest and field in manifest_field_map:
        mf = manifest_field_map[field]
        if mf in sources.run_manifest:
            values["manifest"] = sources.run_manifest[mf]
    if not values:
        return None
    ordered = [values[src] for src in order if src in values]
    if not ordered:
        return None
    first = ordered[0]
    for val in ordered[1:]:
        if str(val) != str(first):
            raise ExportRefuse(
                "provenance_disagreement",
                f"field {field!r} disagrees across sources: {values}",
            )
    return first


def resolve_provenance(
    sources: ProvenanceSources,
    *,
    battle_id_override: str | None = None,
) -> ResolvedProvenance:
    if sources.trace_rows:
        _agree_selected_trace_rows(sources.trace_rows)

    trace = _first_trace(sources)
    battle_id = battle_id_override or _pick("battle_id", sources, ["trace", "result"])
    if battle_id is None:
        raise ExportRefuse("missing_provenance", "battle_id unavailable")

    if sources.trace_rows:
        for row in sources.trace_rows:
            if row.get("battle_id") != battle_id:
                raise ExportRefuse("battle_id_mismatch", "trace rows disagree on battle_id")

    git_sha = _pick("git_sha", sources, ["trace", "result", "manifest"])
    if git_sha is None:
        raise ExportRefuse("missing_provenance", "git_sha unavailable")

    dirty_raw = _pick("dirty", sources, ["result", "manifest"])
    if git_sha == "unknown":
        dirty: bool | None = None
    elif dirty_raw is None:
        dirty = None
    else:
        dirty = bool(dirty_raw)

    our_side = trace.get("our_side") if trace else None

    format_id = _pick("format_id", sources, ["trace", "result"])
    if format_id is None:
        raise ExportRefuse("missing_provenance", "format_id unavailable")
    config_id = _pick("config_id", sources, ["trace", "result"])
    if config_id is None:
        raise ExportRefuse("missing_provenance", "config_id unavailable")
    config_hash = _pick("config_hash", sources, ["trace", "result", "manifest"])
    if config_hash is None:
        raise ExportRefuse("missing_provenance", "config_hash unavailable")
    schedule_hash = _pick("schedule_hash", sources, ["trace", "result", "manifest"])
    if schedule_hash is None:
        raise ExportRefuse("missing_provenance", "schedule_hash unavailable")
    seed_index = _pick("seed_index", sources, ["trace", "result"])
    if seed_index is None:
        raise ExportRefuse("missing_provenance", "seed_index unavailable")

    return ResolvedProvenance(
        battle_id=str(battle_id),
        format_id=str(format_id),
        git_sha=str(git_sha),
        config_hash=str(config_hash),
        config_id=str(config_id),
        schedule_hash=str(schedule_hash),
        seed_index=int(seed_index),
        our_side=our_side,
        dirty=dirty,
        showdown_commit=_pick("showdown_commit", sources, ["manifest"]),
        server_patch_hash=_pick("server_patch_hash", sources, ["manifest"]),
        trace_schema_version=trace.get("trace_schema_version") if trace else None,
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_result_row(path: Path, battle_id: str | None) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if battle_id is not None:
        matched = [r for r in rows if r.get("battle_id") == battle_id]
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            raise ExportRefuse("ambiguous_battle_id", f"multiple result rows for {battle_id!r}")
        return None
    if len(rows) == 1:
        return rows[0]
    return None

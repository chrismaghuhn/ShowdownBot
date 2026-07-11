"""Bind decision-trace sidecar rows to result rows and fail closed on any
mismatch between the two.

This is an offline module: it does not touch the live battle path. It exists
so downstream candidate-vs-baseline diff tooling can trust that a sidecar
trace file actually corresponds to the result rows it claims to bind to
(same battle, same decision count, same content) before drawing any
conclusions from it.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from showdown_bot.eval.decision_capture import TRACE_SCHEMA_VERSION


class DecisionDiffError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTraceRun:
    config_hash: str
    schedule_hash: str
    rows_by_battle: dict[str, tuple[dict, ...]]


def _trace_line(row: dict) -> bytes:
    return (json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def validate_trace_run(result_rows: list[dict], trace_rows: list[dict]) -> ValidatedTraceRun:
    by_result = {row["battle_id"]: row for row in result_rows}
    if len(by_result) != len(result_rows):
        raise DecisionDiffError("duplicate result battle_id")
    grouped = {}
    for row in trace_rows:
        if row["trace_schema_version"] != TRACE_SCHEMA_VERSION:
            raise DecisionDiffError("unknown trace schema version")
        battle_id = row["battle_id"]
        if battle_id not in by_result:
            raise DecisionDiffError(f"trace battle absent from results: {battle_id}")
        result = by_result[battle_id]
        for field in ("seed_index", "config_hash", "schedule_hash", "format_id", "git_sha"):
            if row[field] != result[field]:
                raise DecisionDiffError(f"{battle_id}: {field} mismatch")
        grouped.setdefault(battle_id, []).append(row)
    for battle_id, result in by_result.items():
        expected_count = result.get("decision_trace_count")
        expected_sha = result.get("decision_trace_sha256")
        if expected_count is None or expected_sha is None:
            raise DecisionDiffError(f"{battle_id}: missing decision trace binding")
        rows = sorted(grouped.get(battle_id, []), key=lambda row: row["decision_index"])
        indices = [row["decision_index"] for row in rows]
        if indices != list(range(len(rows))):
            raise DecisionDiffError(f"{battle_id}: non-contiguous or duplicate decision key")
        if len(rows) != expected_count:
            raise DecisionDiffError(f"{battle_id}: count mismatch")
        actual_sha = hashlib.sha256(b"".join(_trace_line(row) for row in rows)).hexdigest()
        if actual_sha != expected_sha:
            raise DecisionDiffError(f"{battle_id}: sha mismatch")
        grouped[battle_id] = tuple(rows)
    config_hashes = {row["config_hash"] for row in result_rows}
    schedule_hashes = {row["schedule_hash"] for row in result_rows}
    if len(config_hashes) != 1 or len(schedule_hashes) != 1:
        raise DecisionDiffError("run provenance is not constant")
    return ValidatedTraceRun(
        config_hash=next(iter(config_hashes)), schedule_hash=next(iter(schedule_hashes)),
        rows_by_battle={key: grouped[key] for key in sorted(grouped)},
    )

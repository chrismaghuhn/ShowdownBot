"""Decision trace normalization to presentation rows."""

from __future__ import annotations

import json
import math
from typing import Any

from .errors import ExportRefuse
from .privacy import strip_state_summary_nicknames
from .warnings_emit import AGGREGATION_MODE_NOT_RECORDED

TRACE_V1 = "decision-trace-v1"
TRACE_V2 = "decision-trace-v2"
TRACE_V3 = "decision-trace-v3"
SUPPORTED = frozenset({TRACE_V2, TRACE_V3})


def _is_canonical_candidate_key(key: str) -> bool:
    try:
        parsed = json.loads(key)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return canonical == key


def _resolve_chosen(row: dict[str, Any]) -> dict[str, Any] | None:
    candidates = row.get("candidates") or []
    chosen_key = row.get("chosen_candidate_key")
    if not candidates:
        if any(row.get(f) is not None for f in ("chosen_candidate_key", "chosen_candidate_id", "chosen_rank")):
            raise ExportRefuse(
                "chosen_integrity",
                f"decision {row['decision_index']}: chosen fields set with empty candidates",
            )
        return None
    if chosen_key is None:
        raise ExportRefuse(
            "chosen_integrity",
            f"decision {row['decision_index']}: chosen_candidate_key null with non-empty candidates",
        )
    matches = [c for c in candidates if c.get("candidate_key") == chosen_key]
    if len(matches) == 0:
        raise ExportRefuse(
            "chosen_integrity",
            f"decision {row['decision_index']}: chosen_candidate_key unresolvable",
        )
    if len(matches) > 1:
        raise ExportRefuse(
            "ambiguous_chosen_candidate",
            f"decision {row['decision_index']}: ambiguous chosen_candidate_key",
        )
    matched = matches[0]
    if row.get("chosen_rank") != matched.get("rank"):
        raise ExportRefuse(
            "chosen_rank_mismatch",
            f"decision {row['decision_index']}: chosen_rank mismatch",
        )
    return matched


def _top1_top2_margin(candidates: list[dict[str, Any]]) -> float | None:
    if len(candidates) < 2:
        return None
    ranked = sorted(candidates, key=lambda c: c["rank"])
    return ranked[0]["aggregate_score"] - ranked[1]["aggregate_score"]


def load_trace_rows(path) -> list[dict[str, Any]]:
    import sys
    from pathlib import Path

    repo_src = Path(__file__).resolve().parents[4] / "showdown_bot" / "src"
    if repo_src.is_dir() and str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    from showdown_bot.eval.decision_capture import DecisionCaptureError, validate_trace_row

    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            version = row.get("trace_schema_version")
            if version == TRACE_V1:
                raise ExportRefuse("unsupported_trace_v1", "decision-trace-v1 is not supported for trace export")
            try:
                validate_trace_row(row)
            except DecisionCaptureError as exc:
                msg = str(exc)
                if "chosen" in msg or "normalized_action" in msg or "candidate" in msg:
                    raise ExportRefuse("chosen_integrity", msg) from exc
                raise ExportRefuse("trace_validation", msg) from exc
            rows.append(row)
    return rows


def export_decisions_jsonl(
    trace_rows: list[dict[str, Any]],
    *,
    request_protocol_index_by_decision: dict[int, int | None] | None = None,
    manifest_battle_id: str | None = None,
    manifest_our_side: str | None = None,
) -> tuple[bytes, dict[int, list[str]], str]:
    """Return (jsonl bytes, per-decision warnings, trace_schema_version)."""
    if not trace_rows:
        raise ExportRefuse("empty_trace", "decision trace has no rows")

    version = trace_rows[0].get("trace_schema_version")
    if version not in SUPPORTED:
        raise ExportRefuse("unsupported_trace_version", f"unknown trace schema: {version!r}")

    # Duplicate request_hash across rows -> refuse
    hash_counts: dict[str, int] = {}
    for row in trace_rows:
        hash_counts[row["request_hash"]] = hash_counts.get(row["request_hash"], 0) + 1
    for req_hash, count in hash_counts.items():
        if count > 1:
            raise ExportRefuse(
                "ambiguous_request_hash_join",
                f"request_hash {req_hash} appears in {count} trace rows",
            )

    identity_keys: set[tuple[Any, ...]] = set()
    out_rows: list[dict[str, Any]] = []
    decision_warnings: dict[int, list[str]] = {}
    join_map = request_protocol_index_by_decision or {}

    for row in sorted(trace_rows, key=lambda r: r["decision_index"]):
        if not math.isfinite(row.get("decision_latency_ms", 0)):
            raise ExportRefuse("non_finite_value", f"decision {row['decision_index']}: non-finite latency")

        if manifest_battle_id and row.get("battle_id") != manifest_battle_id:
            raise ExportRefuse("battle_id_mismatch", f"decision {row['decision_index']}: battle_id mismatch")
        if manifest_our_side and row.get("our_side") != manifest_our_side:
            raise ExportRefuse("our_side_mismatch", f"decision {row['decision_index']}: our_side mismatch")

        key = (row["battle_id"], row["decision_index"], row["our_side"])
        if key in identity_keys:
            raise ExportRefuse("duplicate_decision_identity", f"duplicate decision key {key!r}")
        identity_keys.add(key)

        candidates = row.get("candidates") or []
        seen_keys: set[str] = set()
        for cand in candidates:
            ck = cand.get("candidate_key")
            if ck is not None:
                if not _is_canonical_candidate_key(ck):
                    raise ExportRefuse(
                        "non_canonical_candidate_key",
                        f"decision {row['decision_index']}: non-canonical candidate_key",
                    )
                if ck in seen_keys:
                    raise ExportRefuse(
                        "duplicate_candidate_key",
                        f"decision {row['decision_index']}: duplicate candidate_key",
                    )
                seen_keys.add(ck)
            score = cand.get("aggregate_score")
            if not isinstance(score, (int, float)) or not math.isfinite(score):
                raise ExportRefuse("non_finite_value", f"decision {row['decision_index']}: non-finite score")

        _resolve_chosen(row)

        warnings = [AGGREGATION_MODE_NOT_RECORDED]
        decision_warnings[row["decision_index"]] = warnings

        presentation_candidates = []
        for cand in candidates:
            presentation_candidates.append(
                {
                    "candidate_id": cand["candidate_id"],
                    "candidate_key": cand.get("candidate_key"),
                    "rank": cand["rank"],
                    "aggregate_score": cand["aggregate_score"],
                }
            )

        out_rows.append(
            {
                "decision_index": row["decision_index"],
                "turn_number": row["turn_number"],
                "request_protocol_index": join_map.get(row["decision_index"]),
                "decision_phase": row["decision_phase"],
                "decision_latency_ms": row["decision_latency_ms"],
                "observable_state_hash": row["observable_state_hash"],
                "request_hash": row["request_hash"],
                "state_summary": strip_state_summary_nicknames(row["state_summary"]),
                "normalized_action": row["normalized_action"],
                "actual_choose_string": row["actual_choose_string"],
                "candidates": presentation_candidates,
                "chosen_candidate_key": row.get("chosen_candidate_key"),
                "chosen_candidate_id": row.get("chosen_candidate_id"),
                "chosen_rank": row.get("chosen_rank"),
                "chosen_tera_slot": row.get("chosen_tera_slot"),
                "chosen_mega_slot": row.get("chosen_mega_slot"),
                "selection_stage": row.get("selection_stage"),
                "fallback_reason": row.get("fallback_reason"),
                "aggregation": {
                    "mode": None,
                    "risk_lambda": None,
                    "must_react_lambda": None,
                },
                "top1_top2_margin": _top1_top2_margin(candidates),
                "fallback_used": row.get("fallback_reason") is not None,
                "warning_count": len(warnings),
            }
        )

    from .canonicalize import dumps

    lines = [dumps(row) + b"\n" for row in out_rows]
    return b"".join(lines), decision_warnings, version

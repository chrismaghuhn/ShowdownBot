"""Request-hash join between raw log and trace rows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .errors import ExportRefuse
from .hashutil import request_hash_from_payload
from .privacy import parse_request_line


@dataclass(frozen=True)
class RequestIndexEntry:
    protocol_index: int
    request_hash: str
    rqid: int | None


def index_requests_from_log(lines: list[str]) -> list[RequestIndexEntry]:
    """Mirror room_raw_replay skip rules: skip rqid resends and req.wait."""
    seen_rqids: set[int] = set()
    entries: list[RequestIndexEntry] = []
    for i, line in enumerate(lines):
        if not line.startswith("|request|"):
            continue
        payload = parse_request_line(line)
        if payload is None:
            continue
        rqid = payload.get("rqid")
        if isinstance(rqid, int):
            if rqid in seen_rqids:
                continue
            seen_rqids.add(rqid)
        if payload.get("wait"):
            continue
        req_hash = request_hash_from_payload(payload)
        entries.append(RequestIndexEntry(i, req_hash, rqid if isinstance(rqid, int) else None))
    return entries


def join_request_protocol_indices(
    trace_rows: list[dict[str, Any]],
    lines: list[str],
) -> dict[int, int | None]:
    """Map decision_index -> request_protocol_index."""
    hash_counts = Counter(row["request_hash"] for row in trace_rows)
    for req_hash, count in hash_counts.items():
        if count > 1:
            raise ExportRefuse(
                "ambiguous_request_hash_join",
                f"request_hash {req_hash} appears in {count} trace rows",
            )

    hash_to_index: dict[str, int] = {}
    for entry in index_requests_from_log(lines):
        if entry.request_hash in hash_to_index:
            raise ExportRefuse(
                "ambiguous_request_hash_join",
                f"request_hash {entry.request_hash} appears in multiple raw requests",
            )
        hash_to_index[entry.request_hash] = entry.protocol_index

    return {row["decision_index"]: hash_to_index.get(row["request_hash"]) for row in trace_rows}


def load_log_lines(path) -> list[str]:
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []

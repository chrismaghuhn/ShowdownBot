"""Bundle-level and per-decision warning emission."""

from __future__ import annotations

from typing import Any

AGGREGATION_MODE_NOT_RECORDED = "aggregation_mode_not_recorded"


def build_warnings(
    decision_warnings: dict[int, list[str]],
) -> dict[str, Any]:
    """Build warnings.json content from per-decision warning codes."""
    entries: list[dict[str, Any]] = []
    for decision_index in sorted(decision_warnings):
        for code in decision_warnings[decision_index]:
            entries.append({"decision_index": decision_index, "code": code})
    return {"warnings": entries}


def aggregation_warning_for_row() -> str:
    return AGGREGATION_MODE_NOT_RECORDED

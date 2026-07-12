from __future__ import annotations

import json

from showdown_bot.learning.outcome_join.contracts import (
    REPORT_SCHEMA_VERSION, canonical_json, content_sha256,
)


def build_report(*, dataset_sha: str, groups: list[dict]) -> dict:
    groups = sorted(groups, key=lambda g: g["team_hash"])
    complete = all(g["skipped_reason"] is None for g in groups)
    total_labelled = sum(g["labelled"] for g in groups)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "dataset_sha256": dataset_sha,
        "total_labelled": total_labelled,
        "groups": groups,
    }
    report["report_sha256"] = content_sha256(report)
    return report


def format_json(report: dict) -> str:
    return canonical_json({k: v for k, v in report.items() if k != "report_sha256"})


def format_md(report: dict) -> str:
    lines = [f"# Outcome-Join Report — {report['status']}",
             f"- dataset_sha256: `{report['dataset_sha256']}`",
             f"- total_labelled: {report['total_labelled']}", "", "## Groups"]
    for g in report["groups"]:
        tag = "labelled" if g["skipped_reason"] is None else f"SKIPPED ({g['skipped_reason']})"
        lines.append(f"- `{g['team_hash']}`: {g['labelled']} — {tag} — "
                     f"constants={g['constants']} dist={g['distribution']} "
                     f"turn_violations={g['turn_violations']}")
    return "\n".join(lines) + "\n"

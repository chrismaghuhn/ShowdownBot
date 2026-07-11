"""Deterministic JSON/Markdown audit reports (Phase 3, dataset-reranker-audit
slice, Task 8). Pure rendering: takes an AuditResult and returns/writes
byte-identical output for identical inputs (sorted keys/lists, no wall-clock
inside the identity content). Offline/pure: no network, no live battle imports.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from showdown_bot.learning.audit.contracts import (
    AuditError, AuditResult, Finding, REPORT_SCHEMA_VERSION,
)


def finding_dict(finding: Finding) -> dict:
    return {
        "code": finding.code, "severity": finding.severity.value, "scope": finding.scope,
        "message": finding.message, "count": finding.count,
        "denominator": finding.denominator, "rate": finding.rate,
        "split": finding.split, "feature": finding.feature,
        "examples": list(finding.examples), "evidence": finding.evidence,
        "remediation": finding.remediation,
    }


def build_report_object(result: AuditResult) -> dict:
    limitations = sorted(
        f"{name} unavailable" for name, available in result.capability.items() if not available)
    obj = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "status": result.status,
        "provenance": result.provenance,
        "capability": result.capability,
        "limitations": limitations,
        "findings": [finding_dict(f) for f in result.sorted_findings()],
        "metrics": result.metrics,
    }
    validate_finite(obj)
    return obj


def validate_finite(value, path="$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise AuditError(f"non-finite report value at {path}")
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            validate_finite(value[key], f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_finite(item, f"{path}[{index}]")


def render_markdown(obj: dict) -> str:
    findings = obj["findings"]
    lines = [f"# {obj['status']}", "",
             f"- FAIL: {sum(f['severity'] == 'FAIL' for f in findings)}",
             f"- WARN: {sum(f['severity'] == 'WARN' for f in findings)}",
             f"- INFO: {sum(f['severity'] == 'INFO' for f in findings)}", "",
             "## Findings", "",
             "| severity | code | scope | count | rate | message |",
             "| --- | --- | --- | ---: | ---: | --- |"]
    for finding in findings:
        rate = "n/a" if finding["rate"] is None else f"{finding['rate']:.6f}"
        lines.append(f"| {finding['severity']} | {finding['code']} | {finding['scope']} | "
                     f"{finding['count']} | {rate} | {finding['message']} |")
    lines += ["", "## Provenance", "", "```json",
              json.dumps(obj["provenance"], sort_keys=True, indent=2), "```", "",
              "## Limitations", "",
              *(obj["limitations"] or ["none"]), "",
              "## Metrics", "", "```json",
              json.dumps(obj["metrics"], sort_keys=True, indent=2), "```", ""]
    return "\n".join(lines)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def write_reports(out_dir: Path, result: AuditResult) -> None:
    obj = build_report_object(result)
    write_json(out_dir / "audit.json", obj)
    (out_dir / "audit.md").write_text(render_markdown(obj), encoding="utf-8")

from __future__ import annotations

import csv
import json
from pathlib import Path

from showdown_bot.analysis.generalisation.contracts import GeneralisationError


class OutputError(GeneralisationError):
    pass


def derive_findings(report):
    findings = list(report.get("findings", []))
    for row in report.get("coverage", []):
        if not row.get("complete", True):
            findings.append({"code": "REQUIRED_CELL_MISSING", "severity": "WARN",
                             "scope": row["cell_id"], "message": "required cell is incomplete",
                             "count": row.get("n", 0), "denominator": row.get("required_unique_seeds")})
        if row.get("underpowered"):
            findings.append({"code": "CELL_UNDERPOWERED", "severity": "WARN",
                             "scope": row["cell_id"], "message": "cell is underpowered"})
    if report.get("side_capability") == "NOT_EVALUABLE":
        findings.append({"code": "SIDE_GENERALISATION_NOT_EVALUABLE", "severity": "WARN",
                         "scope": "hero_side", "message": "only one controlled side is unavailable"})
    if report.get("unplanned_count", 0):
        findings.append({"code": "UNPLANNED_EXPLORATORY_CELL", "severity": "WARN",
                         "scope": "matrix", "message": "observations exist outside the matrix",
                         "count": report["unplanned_count"]})
    for row in report.get("paired", []):
        if row.get("regression"):
            findings.append({"code": "PROTECTED_CELL_REGRESSION", "severity": "WARN",
                             "scope": row["cell_id"],
                             "message": "candidate regresses in a protected cell",
                             "evidence": {"delta": row["delta"],
                                          "p_adjusted": row["p_adjusted"]}})
    worst = report.get("worst_cell")
    if worst is not None:
        findings.append({"code": "WORST_CELL", "severity": "INFO",
                         "scope": worst["cell_id"], "message": "lowest eligible cell win rate",
                         "evidence": {"win_rate": worst["win_rate"], "n": worst["n"]}})
    if report.get("status") == "IMPROVEMENT":
        findings.append({"code": "CANDIDATE_IMPROVEMENT", "severity": "INFO",
                         "scope": "macro", "message": "candidate meets improvement gate"})
    return sorted(findings, key=lambda item: (item["severity"], item["code"], item["scope"]))


def _render_markdown(report):
    lines = ["# Team- und Matchup-Generalisation", "", f"Status: `{report['status']}`", "",
             f"Analysis-ID: `{report['analysis_id']}`", "", "## Coverage", "",
             "| cell_id | n | complete |", "|---|---:|---|"]
    for row in sorted(report.get("coverage", []), key=lambda item: item["cell_id"]):
        lines.append(f"| {row['cell_id']} | {row.get('n', 0)} | {row.get('complete', False)} |")
    lines.extend(["", "## Diagnostic slices", "",
                  "| dimension | value | n | win_rate | underpowered |",
                  "|---|---|---:|---:|---|"])
    for row in sorted(report.get("diagnostic_slices", []),
                      key=lambda item: (item["dimension"], item["value"])):
        lines.append(f"| {row['dimension']} | {row['value']} | {row['n']} | "
                     f"{row['win_rate']:.6f} | {row['underpowered']} |")
    lines.extend(["", "## Findings", ""])
    findings = report.get("findings", [])
    lines.extend(f"- `{item['severity']}` `{item['code']}`: {item['message']}" for item in findings)
    if not findings:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _write_csv(path, rows):
    rows = list(rows)
    fields = sorted({key for row in rows for key in row}) or ["cell_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def write_analysis_outputs(out_dir, report, observations, *, overwrite=False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = ("generalisation-manifest.json", "matchup-observations.jsonl",
             "coverage-matrix.csv", "cell-metrics.csv", "paired-deltas.csv", "findings.json",
             "report.json", "report.md")
    targets = [out / name for name in names]
    if not overwrite and any(path.exists() for path in targets):
        raise OutputError("analysis output exists; pass overwrite to replace known outputs")
    enriched = dict(report)
    enriched["findings"] = derive_findings(enriched)
    temporary = out / ".generalisation-output-tmp"
    temporary.mkdir(exist_ok=False)
    ordered = sorted(observations, key=lambda row: (row["config_hash"], row["seed_index"], row["battle_id"]))
    (temporary / names[0]).write_text(
        json.dumps(enriched["generalisation_manifest"], sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (temporary / names[1]).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in ordered),
                                     encoding="utf-8", newline="\n")
    _write_csv(temporary / names[2], sorted(enriched.get("coverage", []), key=lambda row: row["cell_id"]))
    _write_csv(temporary / names[3], sorted(enriched.get("cells", []), key=lambda row: row["cell_id"]))
    _write_csv(temporary / names[4], sorted(enriched.get("paired", []), key=lambda row: row["cell_id"]))
    (temporary / names[5]).write_text(json.dumps(enriched["findings"], sort_keys=True, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    (temporary / names[6]).write_text(json.dumps(enriched, sort_keys=True, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    (temporary / names[7]).write_text(_render_markdown(enriched), encoding="utf-8", newline="\n")
    for name in names:
        source, target = temporary / name, out / name
        if target.exists():
            target.unlink()
        source.replace(target)
    temporary.rmdir()
    return tuple(out / name for name in names)


def write_fatal_report(out_dir, error, *, overwrite=False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out / "report.json", out / "report.md"
    if not overwrite and (json_path.exists() or md_path.exists()):
        raise OutputError("fatal report output exists")
    report = {"schema_version": "generalisation-report-v1", "status": "INVALID",
              "analysis_id": None, "findings": [{"code": "FATAL_INPUT", "severity": "FAIL",
                  "scope": "input", "message": str(error)}]}
    json_tmp, md_tmp = out / ".report.json.tmp", out / ".report.md.tmp"
    json_tmp.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(f"# Team- und Matchup-Generalisation\n\nStatus: `INVALID`\n\n- `{type(error).__name__}`: {error}\n",
                      encoding="utf-8")
    json_tmp.replace(json_path)
    md_tmp.replace(md_path)
    return report

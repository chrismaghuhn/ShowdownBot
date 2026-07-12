from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from showdown_bot.learning.outcome_join.contracts import (
    AuditConfig, OutcomeJoinError, canonical_json, content_sha256, read_jsonl,
)
from showdown_bot.learning.outcome_join.bridge import group_dataset_rows, reconstruct_mapping
from showdown_bot.learning.outcome_join.integrity import check_group
from showdown_bot.learning.outcome_join.join import build_labels, apply_labels
from showdown_bot.learning.outcome_join.report import build_report, format_json, format_md


def _results_index(results_paths):
    """team_hash -> {seed_index: result_row}. Falls hero_team_hash fehlt, wird die
    Datei unter dem Sentinel-Key None geführt und später per Gate zugeordnet."""
    by_team = {}
    for path in results_paths:
        rows = read_jsonl(path)
        team = None
        for r in rows:
            team = r.get("hero_team_hash") or team
        by_team.setdefault(team, {}).update({int(r["seed_index"]): r for r in rows})
    return by_team


def run_outcome_join(*, dataset_path, results_paths, out_dir, mode="label",
                     config: AuditConfig | None = None) -> int:
    config = config or AuditConfig()
    config.validate()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        rows = read_jsonl(dataset_path)
        groups = group_dataset_rows(rows)
    except (OutcomeJoinError, KeyError) as exc:
        (out_dir / "outcome-join-report.json").write_text(
            canonical_json({"status": "FATAL_INPUT", "error": str(exc)}), encoding="utf-8")
        return 1

    results_by_team = _results_index(results_paths)
    all_labels, group_reports = [], []
    for group in groups:
        results = results_by_team.get(group.team_hash) or results_by_team.get(None) or {}
        results_list = [results[s] for s in sorted(results)]
        mapping = reconstruct_mapping(
            group, results_list, dirty_candidates=config.dirty_candidates,
            run_seed_candidates=config.run_seed_candidates) if results_list else None
        gate = check_group(group, mapping, results) if mapping else None
        if mapping is None or not gate.passed:
            reason = ("no_results" if not results_list else
                      "no_unique_constants" if mapping is None else
                      "coverage" if not gate.coverage_ok else "turn_violation")
            group_reports.append({"team_hash": group.team_hash, "labelled": 0,
                "skipped_reason": reason, "constants": [], "distribution": {},
                "turn_violations": 0 if gate is None else gate.turn_violations})
            continue
        labels = build_labels(group, mapping, results)
        all_labels.extend(labels)
        dist = Counter(lab.winner for lab in labels)
        group_reports.append({"team_hash": group.team_hash, "labelled": len(labels),
            "skipped_reason": None, "constants": list(mapping.constants),
            "distribution": dict(dist), "turn_violations": 0})

    all_labels.sort(key=lambda lab: (lab.team_hash, lab.seed_index))
    (out_dir / "outcome-labels.jsonl").write_text(
        "".join(canonical_json(lab.to_row()) + "\n" for lab in all_labels), encoding="utf-8")
    report = build_report(dataset_sha=content_sha256(rows), groups=group_reports)
    (out_dir / "outcome-join-report.json").write_text(format_json(report) + "\n", encoding="utf-8")
    (out_dir / "outcome-join-report.md").write_text(format_md(report), encoding="utf-8")
    if mode == "apply":
        apply_labels(rows, all_labels, out_dir / "dataset_with_outcomes.jsonl.gz")
    return 0 if report["status"] == "COMPLETE" else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser("outcome-join")
    p.add_argument("--dataset", required=True)
    p.add_argument("--results", nargs="+", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--mode", choices=("label", "apply"), default="label")
    a = p.parse_args(argv)
    return run_outcome_join(dataset_path=a.dataset, results_paths=a.results,
                            out_dir=a.out_dir, mode=a.mode)

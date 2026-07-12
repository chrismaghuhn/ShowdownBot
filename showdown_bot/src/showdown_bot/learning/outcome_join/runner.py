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


def _load_results_sources(results_paths):
    """[(path_str, {seed_index: result_row}), ...] -- one entry per results
    file, kept SEPARATE (never merged by hero_team_hash).

    `hero_team_hash` (schedule/eval-side provenance, `eval.result_jsonl`) and
    the dataset's own `team_hash` (export-side provenance,
    `learning.provenance.team_hash` over the packed team string) are different
    hashes over different inputs -- confirmed against the real
    phase3-slice2b25a reference data: zero overlap across all (group, results
    file) pairs, even for the matching hero. Equality-matching them is
    unreliable, so every group tries every source file and keeps whichever
    one(s) pass the FULL integrity gate (bijective-over-group bridge + 0
    turn-violations) -- this is exactly the plan's own documented
    "hero_team_hash absent -> the gate alone decides" fallback, applied
    universally since the equality path structurally never matches on real
    data. The turn-check uses real per-battle data (`turns` per seed_index) so
    it uniquely disambiguates in practice: each of the 4 reference groups
    passes against exactly one results file, with 9-63 turn-violations against
    every other file.
    """
    return [(str(path), {int(r["seed_index"]): r for r in read_jsonl(path)})
            for path in results_paths]


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

    results_sources = _load_results_sources(results_paths)
    all_labels, group_reports = [], []
    for group in groups:
        passing = []
        best_turn_violations = None
        for _path, results in results_sources:
            results_list = [results[s] for s in sorted(results)]
            if not results_list:
                continue
            try:
                mapping = reconstruct_mapping(
                    group, results_list, dirty_candidates=config.dirty_candidates,
                    run_seed_candidates=config.run_seed_candidates)
            except OutcomeJoinError:
                mapping = None
            if mapping is None:
                continue
            gate = check_group(group, mapping, results)
            if best_turn_violations is None or gate.turn_violations < best_turn_violations:
                best_turn_violations = gate.turn_violations
            if gate.passed:
                passing.append((mapping, results))
        if len(passing) != 1:
            reason = ("no_results" if not results_sources else
                      "ambiguous_results_file" if len(passing) > 1 else
                      "no_matching_results_file")
            group_reports.append({"team_hash": group.team_hash, "labelled": 0,
                "skipped_reason": reason, "constants": [], "distribution": {},
                "turn_violations": 0 if best_turn_violations is None else best_turn_violations})
            continue
        mapping, results = passing[0]
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

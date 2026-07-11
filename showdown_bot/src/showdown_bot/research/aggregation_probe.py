"""Offline 2c aggregation probe (C-path / research; NO live-path changes, NO RNG, NO battles).

Question: would re-aggregating a decision's candidates under a different opponent-response RISK
function change the chosen action and/or its agreement with the rollout teacher — measured ONLY on
already-persisted 2b-2.5a features?

REDUCED FIDELITY (important, stated in the report): the raw per-opponent-response score vectors and
response weights are NOT persisted in the dataset (features.py consumes them into summary stats and
discards them). So the risk "variants" here are proxies built from the persisted per-candidate
summaries — `heuristic_aggregate_score` (already the risk_lambda-weighted baseline), `score_mean_vs_opp`,
`score_worst_response`, `score_var_vs_opp`. They capture the mean/worst/mean-variance axes, NOT an
arbitrary risk_lambda sweep or true CVaR over the full response vector. A null result here rules the
response-risk direction out cheaply; a positive result justifies a full-fidelity re-run that exports
the raw vectors.

Baseline action = argmax(`heuristic_aggregate_score`) (apples-to-apples with the argmax variants; the
live tera/tie-break logic is deliberately not modelled). Teacher = the `teacher_best` candidate set.
Everything is deterministic (candidate-index tie-break, sorted output, no RNG).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from showdown_bot.learning.dataset import group_decisions, load_rows

PROBE_SCHEMA_VERSION = "2c-aggregation-probe-v1"

# Per-candidate summary features this probe requires (finite) to use a decision.
REQUIRED_FEATURES = (
    "heuristic_aggregate_score",
    "score_mean_vs_opp",
    "score_worst_response",
    "score_var_vs_opp",
)

NEAR_TIE_EPS = 1e-6


def _mean_minus_lambda_std(lam: float):
    def scorer(f: dict) -> float:
        return f["score_mean_vs_opp"] - lam * math.sqrt(max(0.0, float(f["score_var_vs_opp"])))
    return scorer


# name -> scorer(features)->float (higher = better). "baseline_aggregate" is the reference.
VARIANTS: dict = {
    "baseline_aggregate": lambda f: float(f["heuristic_aggregate_score"]),
    "mean": lambda f: float(f["score_mean_vs_opp"]),
    "worst_case": lambda f: float(f["score_worst_response"]),
    "mean_minus_0.5std": _mean_minus_lambda_std(0.5),
    "mean_minus_1.0std": _mean_minus_lambda_std(1.0),
    "mean_minus_2.0std": _mean_minus_lambda_std(2.0),
}
BASELINE = "baseline_aggregate"


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _usable(decision) -> bool:
    if len(decision.rows) < 2:
        return False  # single-candidate / forced: nothing can change
    for row in decision.rows:
        f = row["features"]
        if any((k not in f) or not _finite(f[k]) for k in REQUIRED_FEATURES):
            return False
    return True


def _ranked(decision, scorer) -> list[int]:
    """candidate_index order, best first; deterministic tie-break by candidate_index asc."""
    scored = [
        (row["metadata"]["candidate_index"], float(scorer(row["features"])))
        for row in decision.rows
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return [ci for ci, _s in scored]


def _score_of(decision, scorer, candidate_index: int) -> float:
    for row in decision.rows:
        if row["metadata"]["candidate_index"] == candidate_index:
            return float(scorer(row["features"]))
    raise KeyError(candidate_index)


def _teacher_best_set(decision) -> set[int]:
    return {
        row["metadata"]["candidate_index"]
        for row in decision.rows
        if bool(row["label"].get("teacher_best"))
    }


@dataclass
class _VariantAcc:
    changed: int = 0
    agree: int = 0
    fixed_teacher_miss: int = 0
    broke_teacher_hit: int = 0
    top2_flip: int = 0
    margin_delta_sum: float = 0.0
    changed_in_near_tie: int = 0


def run_probe(dataset_path: str, *, variants: dict | None = None) -> dict:
    variants = variants or VARIANTS
    if BASELINE not in variants:
        raise ValueError(f"variants must include the reference {BASELINE!r}")
    rows = load_rows(str(dataset_path), validate=True)
    decisions = group_decisions(rows)

    usable = 0
    skipped_single = 0
    skipped_missing = 0
    near_tie = 0
    baseline_agree = 0
    acc = {name: _VariantAcc() for name in variants if name != BASELINE}

    for d in decisions:
        if len(d.rows) < 2:
            skipped_single += 1
            continue
        if not _usable(d):
            skipped_missing += 1
            continue
        usable += 1
        tb = _teacher_best_set(d)
        base_rank = _ranked(d, variants[BASELINE])
        base_top = base_rank[0]
        base_top1_score = _score_of(d, variants[BASELINE], base_rank[0])
        base_top2_score = _score_of(d, variants[BASELINE], base_rank[1])
        base_margin = base_top1_score - base_top2_score
        is_near_tie = base_margin < NEAR_TIE_EPS
        if is_near_tie:
            near_tie += 1
        base_hits = base_top in tb
        if base_hits:
            baseline_agree += 1

        for name, scorer in variants.items():
            if name == BASELINE:
                continue
            a = acc[name]
            rank = _ranked(d, scorer)
            top = rank[0]
            var_hits = top in tb
            if var_hits:
                a.agree += 1
            if top != base_top:
                a.changed += 1
                if is_near_tie:
                    a.changed_in_near_tie += 1
            if not base_hits and var_hits:
                a.fixed_teacher_miss += 1
            if base_hits and not var_hits:
                a.broke_teacher_hit += 1
            if rank[:2] != base_rank[:2]:
                a.top2_flip += 1
            var_margin = _score_of(d, scorer, rank[0]) - _score_of(d, scorer, rank[1])
            a.margin_delta_sum += (var_margin - base_margin)

    def _rate(n: int) -> float | None:
        return (n / usable) if usable else None

    variant_report = {}
    for name in sorted(acc):
        a = acc[name]
        variant_report[name] = {
            "changed_action_rate": _rate(a.changed),
            "teacher_agreement_delta": (
                (a.agree - baseline_agree) / usable if usable else None
            ),
            "variant_teacher_agreement": _rate(a.agree),
            "variant_fixed_teacher_miss": a.fixed_teacher_miss,
            "variant_fixed_teacher_miss_rate": _rate(a.fixed_teacher_miss),
            "variant_broke_teacher_hit": a.broke_teacher_hit,
            "variant_broke_teacher_hit_rate": _rate(a.broke_teacher_hit),
            "top2_flip_rate": _rate(a.top2_flip),
            "mean_margin_delta": (a.margin_delta_sum / usable) if usable else None,
            "changed_in_near_tie": a.changed_in_near_tie,
        }

    return {
        "probe_schema_version": PROBE_SCHEMA_VERSION,
        "fidelity": "reduced-summary-proxy (raw per-response vectors not persisted)",
        "dataset_decisions_total": len(decisions),
        "usable_decisions": usable,
        "skipped_single_candidate": skipped_single,
        "skipped_missing_data": skipped_missing,
        "near_tie_decisions": near_tie,
        "near_tie_rate": _rate(near_tie),
        "baseline_teacher_agreement": _rate(baseline_agree),
        "variants": variant_report,
    }


def format_md(report: dict) -> str:
    lines = [
        "# 2c Aggregation Probe — reduced-fidelity, offline on 2b-2.5a",
        "",
        f"**Fidelity:** {report['fidelity']}. Baseline = argmax(heuristic_aggregate_score); "
        "teacher = teacher_best set. No live-path changes, no RNG, no battles.",
        "",
        f"- decisions total: {report['dataset_decisions_total']}",
        f"- **usable (multi-candidate, features finite): {report['usable_decisions']}**",
        f"- skipped single-candidate: {report['skipped_single_candidate']}",
        f"- skipped missing-data: {report['skipped_missing_data']}",
        f"- near-tie decisions: {report['near_tie_decisions']} "
        f"(rate {report['near_tie_rate']})",
        f"- baseline teacher-agreement: {report['baseline_teacher_agreement']}",
        "",
        "| variant | changed_action | teacher_agree_Δ | fixed_miss | broke_hit | top2_flip | mean_margin_Δ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in sorted(report["variants"]):
        v = report["variants"][name]
        def fmt(x):
            return f"{x:.4f}" if isinstance(x, float) else str(x)
        lines.append(
            f"| {name} | {fmt(v['changed_action_rate'])} | {fmt(v['teacher_agreement_delta'])} "
            f"| {v['variant_fixed_teacher_miss']} | {v['variant_broke_teacher_hit']} "
            f"| {fmt(v['top2_flip_rate'])} | {fmt(v['mean_margin_delta'])} |"
        )
    return "\n".join(lines) + "\n"


def format_json(report: dict) -> str:
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Offline 2c aggregation probe (reduced fidelity).")
    p.add_argument("dataset", help="path to a 2b-2.5a-style dataset .jsonl(.gz)")
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    args = p.parse_args(argv)
    report = run_probe(args.dataset)
    from pathlib import Path

    Path(args.out_json).write_text(format_json(report), encoding="utf-8")
    Path(args.out_md).write_text(format_md(report), encoding="utf-8")
    v = report["variants"]
    best_delta = max((vv["teacher_agreement_delta"] or 0.0) for vv in v.values()) if v else 0.0
    max_changed = max((vv["changed_action_rate"] or 0.0) for vv in v.values()) if v else 0.0
    print(f"PROBE: usable={report['usable_decisions']} max_changed_action={max_changed:.4f} "
          f"best_teacher_agree_delta={best_delta:+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

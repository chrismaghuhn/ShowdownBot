"""Render a deterministic candidate-vs-baseline differential report.

This module turns the dict returned by
`showdown_bot.eval.decision_diff.analyze_decision_diff` into a fixed-shape
report object (stable key order via sorting, no non-finite numbers) and a
verdict-first Markdown rendering of that object.

It is offline and pure: no battle execution, no CLI, no file I/O. The
strength verdict itself remains the existing paired-statistics gate; this
report only presents that evidence alongside first-divergence associations
and matchup/regression context -- it does not introduce a new gate.
"""
from __future__ import annotations

import json
import math

from showdown_bot.eval.decision_diff import DecisionDiffError

REPORT_SCHEMA_VERSION = "decision-diff-report-v1"


def _bucket_sort_key(bucket: dict) -> tuple:
    return (
        bucket["hero_archetype"], bucket["opponent_archetype"],
        bucket["opponent_policy"], bucket["lead"],
    )


def validate_finite_numbers(value, path: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise DecisionDiffError(f"non-finite report number at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            validate_finite_numbers(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_finite_numbers(child, f"{path}[{index}]")


def build_report_object(analysis: dict) -> dict:
    obj = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "capability_mode": analysis["capability_mode"],
        "provenance": analysis["provenance"],
        "integrity": analysis["integrity"],
        "strength": {"source": "existing paired statistics", **analysis["strength"]},
        "outcomes": analysis["outcomes"],
        "decision_differences": analysis.get("decision_differences"),
        "matchup_buckets": sorted(analysis.get("matchup_buckets", []), key=_bucket_sort_key),
        "stability": analysis.get("stability", {"status": "not_provided"}),
        "regressions": analysis.get("regressions", {}),
        "top_positive_associations": analysis.get("top_positive_associations", []),
        "top_negative_associations": analysis.get("top_negative_associations", []),
        "limitations": [
            "first divergence is an association, not causal proof",
            "strength acceptance remains in the existing paired gate",
            "counterfactual regret is outside this report",
        ],
    }
    validate_finite_numbers(obj)
    return obj


def render_markdown(obj: dict) -> str:
    lines = [
        "# Candidate-vs-Baseline Differential Report", "",
        f"- capability mode: `{obj['capability_mode']}`",
        f"- paired battles: {obj['integrity']['paired_battles']}",
        "- interpretation: diagnostic evidence; strength gate unchanged", "",
        "## Inputs and provenance", "",
        "```json", json.dumps(obj["provenance"], sort_keys=True, indent=2), "```", "",
        "## Integrity and coverage", "",
    ]
    for key, value in sorted(obj["integrity"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## Existing paired strength evidence", ""]
    for key, value in sorted(obj["strength"].items()):
        lines.append(f"- {key}: {_fmt(value)}")
    lines += ["", "## Outcome flips", ""]
    for key, value in sorted(obj["outcomes"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## First direct divergences", ""]
    differences = obj.get("decision_differences")
    if differences is None:
        lines.append("Unavailable in outcome-only mode.")
    else:
        for key, value in sorted(differences.items()):
            lines.append(f"- {key}: {_fmt(value)}")
    lines += ["", "## Matchup buckets", "",
              "| hero archetype | opponent archetype | policy | lead | n | candidate win rate | underpowered |",
              "| --- | --- | --- | --- | ---: | ---: | --- |"]
    for bucket in obj["matchup_buckets"]:
        lines.append(
            f"| {bucket['hero_archetype']} | {bucket['opponent_archetype']} | "
            f"{bucket['opponent_policy']} | {bucket['lead']} | {bucket['n']} | "
            f"{_fmt(bucket['candidate_win_rate'])} | {bucket['underpowered']} |"
        )
    lines += ["", "## Stability", "", "```json",
              json.dumps(obj["stability"], sort_keys=True, indent=2), "```", "",
              "## Regressions", ""]
    for key, value in sorted(obj["regressions"].items()):
        lines.append(f"- {key}: {_fmt(value)}")
    for title, key in (
        ("Positive flip associations", "top_positive_associations"),
        ("Negative flip associations", "top_negative_associations"),
    ):
        lines += ["", f"## {title}", ""]
        for item in obj[key]:
            lines.append(f"- {item['primary']}: {item['associated_battles']}")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in obj["limitations"])
    return "\n".join(lines) + "\n"


def _fmt(value) -> str:
    return f"{value:.6f}" if isinstance(value, float) else str(value)

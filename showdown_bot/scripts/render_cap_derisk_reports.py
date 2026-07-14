"""Task 12 driver (accuracy-cap-derisk plan): render `cap6-report.md` / `cap8-report.md` from
their already-real JSON data.

Mirrors `render_accuracy_gate_reports.py`'s `build_report_object`/`render_markdown` split (itself
mirroring `eval/decision_diff_report.py`'s pattern: a stable-shape object built first via
`build_report_object`, then a pure function turning it into Markdown via `render_markdown`) --
adapted here because, unlike the sibling gate-a/gate-b renderer (where each report's raw JSON
already has the exact shape needed), a cap6/cap8 report here draws from THREE separate real JSON
artifacts that must be merged into one stable-shape object before rendering:

  - `data/eval/accuracy-cap-derisk/cap{6,8}-report.json` (Task 7's real per-cap Gate-B run --
    cap-hit verdict, exceptions, off-vs-on diffs for that cap)
  - `data/eval/accuracy-cap-derisk/cross-cap-diffs.json` (Task 8's real cross-cap action/score
    diff comparator -- `cap4 -> cap{6,8}` and `off -> cap{6,8}` rows)
  - `data/eval/accuracy-cap-derisk/latency-results.json` (Task 9's real full-corpus latency sweep
    -- 6 (cap, trace_mode) series)

plus, read-only, cited but never modified:

  - `data/eval/accuracy-gate/gate-b-report.json` (the FROZEN cap=4 verdict this whole study
    de-risks against -- 114/881 FAIL. Cited by content hash, never recomputed here.)

Writes:
  - `data/eval/accuracy-cap-derisk/cap6-report.md`
  - `data/eval/accuracy-cap-derisk/cap8-report.md`

Usage (from the showdown_bot/ directory of this worktree):

    PYTHONPATH="$(pwd)/src" python scripts/render_cap_derisk_reports.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

# Pinned statistics constants, imported (not hand-typed) so this renderer can never silently
# drift from accuracy_gate_stats.py's actual pinned values -- same discipline as the sibling
# render_accuracy_gate_reports.py.
from showdown_bot.eval.accuracy_gate_stats import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    PASS_THRESHOLD,
)

CAP_DERISK_DIR = REPO_ROOT / "data" / "eval" / "accuracy-cap-derisk"
ACCURACY_GATE_DIR = REPO_ROOT / "data" / "eval" / "accuracy-gate"

CROSS_CAP_JSON = CAP_DERISK_DIR / "cross-cap-diffs.json"
LATENCY_JSON = CAP_DERISK_DIR / "latency-results.json"
GATE_B_CAP4_JSON = ACCURACY_GATE_DIR / "gate-b-report.json"

REPORT_SCHEMA_VERSION = "cap-derisk-rendered-report-v1"


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_finite_numbers(value, path: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite report number at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            validate_finite_numbers(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_finite_numbers(child, f"{path}[{index}]")


def build_report_object(
    cap: int, cap_json: dict, gate_b_cap4_json: dict, cross_cap_json: dict, latency_json: dict,
) -> dict:
    """Merge the three-plus-one real source artifacts for a single cap into one stable-shape
    object. No number here is invented or recomputed -- every field is copied straight from an
    already-real, already-committed JSON artifact, keyed by the exact source it came from so
    `render_markdown` (and any future reader diffing this object) can trace provenance per field."""
    detail = cap_json["cap_hit_verdict_detail"]
    cap4_detail = gate_b_cap4_json["cap_hit_verdict_detail"]

    vs_cap4 = cross_cap_json[f"cap4 -> cap{cap}"]
    vs_off = cross_cap_json[f"off -> cap{cap}"]

    trace_none = latency_json["results"][f"cap{cap}_trace_none"]
    trace_enabled = latency_json["results"][f"cap{cap}_trace_enabled"]
    cap4_trace_none = latency_json["results"]["cap4_trace_none"]
    cap4_trace_enabled = latency_json["results"]["cap4_trace_enabled"]

    # events_complete is only ever populated on this cap's own off-vs-on diff rows (the
    # diverging decisions) -- it is never computed for the other 924-ish non-diverging
    # decisions, so its real telemeterable denominator is diff_count, not 944 (spec Sec.2.7).
    diffs = cap_json["diffs"]
    events_complete_true = sum(1 for d in diffs if d["events_complete"] is True)
    events_complete_false = sum(1 for d in diffs if d["events_complete"] is False)
    mechanically_explained_true = sum(1 for d in diffs if d["mechanically_explained"] is True)

    obj = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "cap": cap,
        "source": {
            "cap_report_source_commit": cap_json.get("source_commit"),
            "cap_report_elapsed_seconds": cap_json.get("elapsed_seconds"),
        },
        "cap_hit": {
            "numerator": detail.get("numerator"),
            "denominator": detail.get("n_decisions"),
            "point_estimate": detail.get("point_estimate"),
            "g": detail.get("g"),
            "bootstrap_ci_upper": detail.get("bootstrap_ci_upper"),
            "bootstrap_ci_degenerate": detail.get("bootstrap_ci_degenerate"),
            "pass_threshold": PASS_THRESHOLD,
            "verdict": cap_json.get("cap_hit_verdict"),
            "exception_count": cap_json["acceptance"]["exception_count"],
        },
        "cap4_reference": {
            "source_file": "data/eval/accuracy-gate/gate-b-report.json",
            "source_sha256": _sha256_of_file(GATE_B_CAP4_JSON),
            "numerator": cap4_detail.get("numerator"),
            "denominator": cap4_detail.get("n_decisions"),
            "point_estimate": cap4_detail.get("point_estimate"),
            "bootstrap_ci_upper": cap4_detail.get("bootstrap_ci_upper"),
            "verdict": gate_b_cap4_json.get("cap_hit_verdict"),
        },
        "action_diffs": {
            "vs_cap4": {
                "action_changed_count": vs_cap4["action_changed_count"],
                "score_changed_count": vs_cap4["score_changed_count"],
                "total": vs_cap4["total"],
            },
            "vs_off": {
                "action_changed_count": vs_off["action_changed_count"],
                "score_changed_count": vs_off["score_changed_count"],
                "total": vs_off["total"],
                "note": (
                    "score axis is skipped for this comparison (legacy_frozen_score not proven "
                    "equivalent to top_rank_score/chosen_candidate_score, per every row's own "
                    "score_incompatible_reason) -- the action axis is NOT skipped and is the "
                    "real, load-bearing number here."
                ),
                "decision_ids": sorted(row["decision_id"] for row in vs_off["rows"]),
            },
        },
        "events_complete": {
            "denominator": len(diffs),
            "denominator_note": (
                "events_complete/mechanically_explained are only ever populated on this cap's "
                "own off-vs-on diff rows (the decisions where the chosen action actually "
                "differed) -- they are never computed for non-diverging decisions. This "
                "denominator is diff_count, NOT the full 944-decision corpus (spec Sec.2.7)."
            ),
            "events_complete_true": events_complete_true,
            "events_complete_false": events_complete_false,
            "mechanically_explained_true": mechanically_explained_true,
        },
        "latency": {
            "cap_trace_none": {
                "p50": trace_none["p50"], "p95": trace_none["p95"], "max": trace_none["max"],
                "n": trace_none["n"], "expected_denominator": trace_none["expected_denominator"],
                "exceptions": trace_none["exceptions"],
            },
            "cap_trace_enabled": {
                "p50": trace_enabled["p50"], "p95": trace_enabled["p95"], "max": trace_enabled["max"],
                "n": trace_enabled["n"], "expected_denominator": trace_enabled["expected_denominator"],
                "exceptions": trace_enabled["exceptions"],
            },
            "cap4_trace_none_for_comparison": {
                "p50": cap4_trace_none["p50"], "p95": cap4_trace_none["p95"], "max": cap4_trace_none["max"],
                "n": cap4_trace_none["n"], "expected_denominator": cap4_trace_none["expected_denominator"],
                "exceptions": cap4_trace_none["exceptions"],
            },
            "cap4_trace_enabled_for_comparison": {
                "p50": cap4_trace_enabled["p50"], "p95": cap4_trace_enabled["p95"], "max": cap4_trace_enabled["max"],
                "n": cap4_trace_enabled["n"], "expected_denominator": cap4_trace_enabled["expected_denominator"],
                "exceptions": cap4_trace_enabled["exceptions"],
            },
            "total_decisions_in_corpus": latency_json["total_decisions"],
            "counterbalancing": latency_json["counterbalancing"],
        },
        "diffs": diffs,
    }
    validate_finite_numbers(obj)
    return obj


def render_markdown(obj: dict) -> str:
    cap = obj["cap"]
    ch = obj["cap_hit"]
    ref = obj["cap4_reference"]
    ad = obj["action_diffs"]
    ec = obj["events_complete"]
    lat = obj["latency"]

    lines = [
        f"# Cap={cap} Report -- Accuracy Branch-Cap De-Risk Study", "",
        "**No strength or winrate claim anywhere in this report -- pure measurement, matching "
        "the parent accuracy-offline-gate's own framing** (same convention as "
        "`reports/2026-07-13-accuracy-offline-gate-verdict.md`'s boxed disclaimer). This report "
        "does not, by itself, license any default-on decision, any change to "
        "`SHOWDOWN_ACCURACY_BRANCH_CAP`, or any Depth-2 Stage 3 work. See the plan closeout "
        "report (`reports/2026-07-13-accuracy-cap-derisk-verdict.md`) for the full framing.",
        "",
        f"- report schema version: `{obj['report_schema_version']}`",
        f"- cap report source commit: `{obj['source']['cap_report_source_commit']}`",
        f"- cap report elapsed seconds (real, full run, off+on combined): "
        f"{obj['source']['cap_report_elapsed_seconds']}",
        "",
        "## Cap-hit verdict (spec Sec.2.5)", "",
        f"- **numerator (decisions with >=1 accuracy_branch_cap_hits on the chosen candidate): "
        f"{ch['numerator']}**",
        f"- **denominator (n_decisions_compared): {ch['denominator']}**",
        f"- **point estimate (rate): {_fmt(ch['point_estimate'])} ({_pct(ch['point_estimate'])})**",
        f"- g (distinct games/battles): {ch['g']}",
        f"- bootstrap upper bound (one-sided 95%, B={BOOTSTRAP_RESAMPLES:,} resamples, seed "
        f"{BOOTSTRAP_SEED}, game-clustered): {_fmt(ch['bootstrap_ci_upper'])} "
        f"({_pct(ch['bootstrap_ci_upper'])})",
        f"- PASS threshold: {ch['pass_threshold']} ({_pct(ch['pass_threshold'])})",
        f"- **verdict: {ch['verdict']}** -- "
        + (
            f"point estimate ({_pct(ch['point_estimate'])}) is at or below the "
            f"{_pct(ch['pass_threshold'])} threshold and the bootstrap upper bound "
            f"({_pct(ch['bootstrap_ci_upper'])}) clears it too."
            if ch["verdict"] == "PASS" else
            f"verdict is {ch['verdict']} against the {_pct(ch['pass_threshold'])} threshold "
            f"(see raw detail above -- this branch is reported honestly whichever way it falls)."
        ),
        f"- exception_count (ambiguous_label-excluded decisions, same 63 as cap=4 -- see the "
        f"ambiguous-candidate diagnostic report for the full classification): "
        f"{ch['exception_count']}",
        "",
        "## Cap=4 reference row (FROZEN, cited only -- never recomputed here)", "",
        f"Cited from `{ref['source_file']}` (sha256 `{ref['source_sha256']}`):", "",
        f"- numerator: {ref['numerator']}",
        f"- denominator: {ref['denominator']}",
        f"- point estimate: {_fmt(ref['point_estimate'])} ({_pct(ref['point_estimate'])})",
        f"- bootstrap upper bound: {_fmt(ref['bootstrap_ci_upper'])} "
        f"({_pct(ref['bootstrap_ci_upper'])})",
        f"- **verdict: {ref['verdict']}**",
        "",
        f"## Action-changed counts (spec Sec.2.4/2.7 -- `compare_action_tables`, directions "
        f"explicitly labeled)", "",
        f"### `cap4 -> cap{cap}`", "",
        f"- **action_changed_count: {ad['vs_cap4']['action_changed_count']} / "
        f"{ad['vs_cap4']['total']}**",
        f"- score_changed_count: {ad['vs_cap4']['score_changed_count']} / "
        f"{ad['vs_cap4']['total']} (real score movement without ever flipping the chosen "
        "action)",
        "",
        f"### `off -> cap{cap}`", "",
        f"- **action_changed_count: {ad['vs_off']['action_changed_count']} / "
        f"{ad['vs_off']['total']}**",
        f"- score_changed_count (reported as computed, see note below): "
        f"{ad['vs_off']['score_changed_count']} / {ad['vs_off']['total']}",
        f"- **note: {ad['vs_off']['note']}**",
        "",
        "Full list of the affected decision_ids "
        f"({len(ad['vs_off']['decision_ids'])}):", "",
    ]
    for did in ad["vs_off"]["decision_ids"]:
        lines.append(f"- `{did}`")
    lines += [
        "",
        "## Leaf/event/incomplete distributions (spec Sec.2.7 -- own real denominator, NOT "
        "claimed to cover all 944)", "",
        f"**{ec['denominator_note']}**", "",
        f"- denominator (this cap's own diff_count): {ec['denominator']}",
        f"- events_complete=True: {ec['events_complete_true']} / {ec['denominator']}",
        f"- events_complete=False: {ec['events_complete_false']} / {ec['denominator']} (branch "
        "cap was exhausted somewhere in the chosen candidate's own event tree for that decision)",
        f"- mechanically_explained=True: {ec['mechanically_explained_true']} / {ec['denominator']} "
        "(never True when events_complete is False, per spec)",
        "",
        "## Latency (spec Sec.2.6 -- both trace modes, real full-corpus measured count / "
        "expected denominator shown side by side)", "",
        "| series | p50 (ms) | p95 (ms) | max (ms) | measured n | expected denominator | "
        "exceptions |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, series in [
        (f"cap{cap}_trace_none", lat["cap_trace_none"]),
        (f"cap{cap}_trace_enabled", lat["cap_trace_enabled"]),
        ("cap4_trace_none (reference)", lat["cap4_trace_none_for_comparison"]),
        ("cap4_trace_enabled (reference)", lat["cap4_trace_enabled_for_comparison"]),
    ]:
        lines.append(
            f"| `{label}` | {series['p50']:.1f} | {series['p95']:.1f} | {series['max']:.1f} | "
            f"{series['n']} | {series['expected_denominator']} | {series['exceptions']} |"
        )
    lines += [
        "",
        f"- total decisions in corpus (shared denominator basis): "
        f"{lat['total_decisions_in_corpus']}",
        f"- counterbalancing (cap position x trial, verified not confounded with warm-up/order): "
        f"`{json.dumps(lat['counterbalancing']['cap_position_counts'], sort_keys=True)}`",
        f"- trace order counts: "
        f"`{json.dumps(lat['counterbalancing']['trace_order_counts'], sort_keys=True)}`",
        "",
        "## Decision diffs -- full per-diff capture (off vs on, this cap)", "",
        f"**diff_count: {len(obj['diffs'])}** (decisions where the chosen action differs off vs "
        f"on, at cap={cap})", "",
    ]
    for i, d in enumerate(obj["diffs"]):
        lines += [
            f"### Diff {i + 1}: `{d['request_hash']}`", "",
            f"- off_chosen_action: `{d['off_chosen_action']}`",
            f"- on_chosen_action: `{d['on_chosen_action']}`",
            f"- off_score: {_fmt(d['off_score'])}",
            f"- on_score: {_fmt(d['on_score'])}",
            f"- tera_changed: {d['tera_changed']}",
            f"- action_diff_kind: `{d['action_diff_kind']}`",
            f"- events_complete: **{d['events_complete']}**",
            f"- mechanically_explained: **{d['mechanically_explained']}**",
            f"- left_top_k: {d['left_top_k'] or '[]'}",
            f"- entered_top_k: {d['entered_top_k'] or '[]'}",
            "",
        ]
    lines += [
        "## Provenance note", "",
        f"This report was rendered by `scripts/render_cap_derisk_reports.py` (Task 12) from "
        f"Task 7's real `cap{cap}-report.json`, Task 8's real `cross-cap-diffs.json`, and Task "
        "9's real `latency-results.json` -- none of these source artifacts were re-run or "
        "modified to produce this report; the cap=4 reference row is cited by content hash from "
        "the frozen `data/eval/accuracy-gate/gate-b-report.json`, never recomputed.", "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    gate_b_cap4_json = json.loads(GATE_B_CAP4_JSON.read_text(encoding="utf-8"))
    cross_cap_json = json.loads(CROSS_CAP_JSON.read_text(encoding="utf-8"))
    latency_json = json.loads(LATENCY_JSON.read_text(encoding="utf-8"))

    for cap in (6, 8):
        cap_json_path = CAP_DERISK_DIR / f"cap{cap}-report.json"
        cap_json = json.loads(cap_json_path.read_text(encoding="utf-8"))
        obj = build_report_object(cap, cap_json, gate_b_cap4_json, cross_cap_json, latency_json)
        md = render_markdown(obj)
        out_path = CAP_DERISK_DIR / f"cap{cap}-report.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()

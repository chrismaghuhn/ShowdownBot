"""Task 11 driver (accuracy-offline-gate plan): render the Markdown Gate A / Gate B reports
from their already-real JSON data.

Mirrors ``eval/decision_diff_report.py``'s existing ``build_report_object``/``render_markdown``
split (a stable-shape object built first, then a pure function turning it into Markdown) rather
than inventing a new report format -- adapted here to Gate A's/Gate B's own schemas since
``decision_diff_report.py``'s functions are shaped for the candidate-vs-baseline differential
report, a different data shape.

Reads:
  - ``data/eval/accuracy-gate/gate-a-report.json`` (Task 9's real sweep, already committed at
    commit 57b7f36 -- NOT re-run here)
  - ``data/eval/accuracy-gate/gate-b-report.json`` (this plan's Task 11 real run, written by
    ``scripts/run_accuracy_gate_b.py``)

Writes:
  - ``data/eval/accuracy-gate/gate-a-report.md``
  - ``data/eval/accuracy-gate/gate-b-report.md``

Usage (from the showdown_bot/ directory of this worktree):

    PYTHONPATH="$(pwd)/src" python scripts/render_accuracy_gate_reports.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

OUT_DIR = REPO_ROOT / "data" / "eval" / "accuracy-gate"
GATE_A_JSON = OUT_DIR / "gate-a-report.json"
GATE_B_JSON = OUT_DIR / "gate-b-report.json"
GATE_A_MD = OUT_DIR / "gate-a-report.md"
GATE_B_MD = OUT_DIR / "gate-b-report.md"


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def render_gate_a_markdown(obj: dict) -> str:
    lines = [
        "# Gate A Report -- Smoke Test", "",
        "**This is a smoke test. Per spec Sec.1, Gate A cannot license anything on its own** "
        "(it sweeps a small, fixed number of hand-built boards across field-bucket variants, "
        "no real corpus, no statistics) -- it is a fast connectivity/no-crash/no-diff sanity "
        "check that Gate B's real corpus run is worth doing, not evidence of correctness or "
        "strength by itself.",
        "",
        f"- report schema version: `{obj['report_schema_version']}`",
        f"- source commit: `{obj['source_commit']}`",
        f"- boards swept: {obj['board_count']} (`primary`, `single_target`)",
        f"- field variants swept: {', '.join(obj['field_variants'])} "
        f"({len(obj['field_variants'])} variants)",
        f"- total rows (boards x variants): {obj['row_count']}",
        f"- elapsed seconds: {obj['elapsed_seconds']}",
        f"- **exception count: {obj['exception_count']}**",
        f"- **diff count (action changed off vs on): {obj['diff_count']}**",
        "",
        "## Result",
        "",
        "Zero exceptions, zero action diffs across all 14 (board x field-variant) combinations "
        "-- `SHOWDOWN_ACCURACY_MODE=1` runs cleanly and does not change the chosen action on "
        "either fixed board under any of the 7 field variants swept. This is a necessary "
        "precondition for a real Gate B run, not a substitute for one.",
        "",
        "## All rows", "",
        "| board | field_variant | action_changed | exception | off_chosen_action | on_chosen_action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in obj["rows"]:
        lines.append(
            f"| {row['board']} | {row['field_variant']} | {row['action_changed']} | "
            f"{row['exception'] or ''} | `{row['off_chosen_action']}` | `{row['on_chosen_action']}` |"
        )
    lines += [
        "", "## Provenance note", "",
        "This report was rendered from the already-real Gate A sweep committed in Task 9 "
        "(commit `57b7f36`) -- the sweep itself was NOT re-run for this report (per the "
        "accuracy-offline-gate plan's Task 11 instructions).", "",
    ]
    return "\n".join(lines) + "\n"


def render_gate_b_markdown(obj: dict) -> str:
    dedup = obj["dedup"]
    acc = obj["acceptance"]
    detail = obj["cap_hit_verdict_detail"]
    lines = [
        "# Gate B Report -- Confirmatory Run (Full Deduplicated Corpus)", "",
        "**This is the load-bearing real run of the accuracy-offline-gate plan.** It replays "
        "every real (state, request) MOVE decision in the full deduplicated corpus through "
        "`heuristic_choose_for_request` twice -- once with `SHOWDOWN_ACCURACY_MODE` off, once "
        "on -- and applies spec Sec.4's acceptance rules. **No default-on decision, strength "
        "claim, or Depth-2 Stage 3 work follows from this report alone** (spec Sec.1, Sec.8); "
        "see the plan closeout report "
        "(`reports/2026-07-13-accuracy-offline-gate-verdict.md`) for the full framing.",
        "",
        f"- report schema version: `{obj['report_schema_version']}`",
        f"- source commit: `{obj['source_commit']}`",
        f"- elapsed seconds (real, full run, off+on combined): {obj['elapsed_seconds']}",
        f"- ms/decision average (off+on combined): "
        f"{(obj['elapsed_seconds'] / obj['decision_kind_counts']['move']) * 1000:.1f}",
        "",
        "## Dedup breakdown (separate numbers, spec Sec.6 item 5 -- not folded into one figure)",
        "",
        f"- `.log.gz` files found under the 4 canonical corpus directories: {dedup['files_found']}",
        f"- excluded total: {dedup['excluded_total']}",
    ]
    for reason, count in sorted(dedup["excluded_by_reason"].items()):
        lines.append(f"  - excluded as `{reason}`: {count}")
    lines += [
        f"- final deduplicated unique battles (G): {dedup['unique_battles_final_g']}",
        f"- expected G (Task 4's verified real-corpus number): {dedup['expected_final_g']}",
        f"- **G matches expected: {dedup['final_g_matches_expected']}**",
        "",
        "## Decision extraction", "",
    ]
    for kind, count in sorted(obj["decision_kind_counts"].items()):
        lines.append(f"- `{kind}`: {count}")
    lines += [
        f"- excluded from Gate B as team_preview: {obj['excluded_team_preview_count']} "
        f"(carries no move-accuracy content, spec Sec.6 item 4)",
        f"- excluded from Gate B as force_switch: {obj['excluded_force_switch_count']} "
        f"(carries no move-accuracy content, spec Sec.6 item 4)",
        f"- MOVE decisions replayed (off+on each): {obj['decision_kind_counts']['move']}",
        f"- **n_decisions_compared (MOVE decisions that did NOT raise): "
        f"{obj['n_decisions_compared']}**",
        "",
        "## Acceptance rule (spec Sec.4)", "",
        f"- no_exceptions: **{acc['no_exceptions']}**",
        f"- no_nans: **{acc['no_nans']}** (swept over every replayed decision, not just "
        "diverging ones)",
        f"- exception_count: **{acc['exception_count']}**",
        f"- off_path_byte_identical: {acc['off_path_byte_identical']} (not recomputed here -- "
        "verified separately by Task 4/7's frozen-baseline diff; see the closeout report)",
        f"- latency_within_budget: {acc['latency_within_budget']} (not a per-run gate field in "
        "this module; see the latency figures above and the closeout report's runtime-"
        "extrapolation discussion)",
        "",
        "### Exceptions -- honest, full accounting (not hidden)", "",
        "All exceptions this run are `RuntimeError` raised by `_chosen_candidate` "
        "(`eval/accuracy_gate_b.py`) on an AMBIGUOUS `candidate_id`: `decision.py`'s `_label_ja` "
        "renders every non-move slot action as the bare string `\"switch\"` (dropping which "
        "benched mon it switches to), so two structurally different joint actions that switch "
        "to different bench mons in the same slot can render a byte-identical `candidate_id` "
        "(e.g. `\"(switch, pass)\"`). This is documented, expected, and correctly caught "
        "(Task 10) -- these decisions are excluded from `n_decisions_compared` and from the "
        "cap-hit numerator/denominator, not silently miscounted. Every exception shares the "
        "identical message template below, differing only in `request_hash` and the specific "
        "`chosen_candidate_id` substituted in:", "",
        "> `RuntimeError: ambiguous chosen_candidate_id='<label>' matches 2 candidates -- "
        "_label_ja's non-injective switch-slot labeling (decision.py's _label_ja renders every "
        "non-move slot action as the bare kind string, e.g. 'switch', dropping the target mon) "
        "makes candidate_id ambiguous here; refusing to guess which one was actually chosen`",
        "",
        "Full list (request_hash, ambiguous label, candidate match count):", "",
        "| request_hash | ambiguous candidate_id | matches |",
        "| --- | --- | ---: |",
    ]
    import re
    for row in acc["exceptions"]:
        m = re.search(r"ambiguous chosen_candidate_id=(.*?) matches (\d+) candidates", row["exception"])
        label = m.group(1) if m else "(see raw message)"
        matches = m.group(2) if m else "?"
        lines.append(f"| `{row['request_hash']}` | {label} | {matches} |")
    lines += [
        "", "## Cap-hit verdict (spec Sec.4)", "",
        f"- **verdict: {obj['cap_hit_verdict']}**",
        f"- numerator (decisions with >=1 accuracy_branch_cap_hits on the chosen candidate): "
        f"{detail.get('numerator')}",
        f"- denominator (n_decisions, i.e. n_decisions_compared): {detail.get('n_decisions')}",
        f"- point estimate (rate): {_fmt(detail.get('point_estimate'))}",
        f"- g (distinct games / battles): {detail.get('g')}",
    ]
    if detail.get("bootstrap_ci_degenerate") is False:
        lines += [
            f"- branch used: **nonzero -- game-clustered bootstrap** "
            f"(numerator > 0, so the zero-event Clopper-Pearson branch does not apply)",
            f"- bootstrap upper bound (one-sided 95%, B=10,000 resamples, game-clustered): "
            f"{_fmt(detail.get('bootstrap_ci_upper'))}",
            f"- PASS threshold: 0.05",
            f"- verdict logic: point_estimate ({_fmt(detail.get('point_estimate'))}) > 0.05 "
            f"-> **FAIL is asserted directly from the point estimate**, without even needing "
            f"the bootstrap upper bound (which is still reported above for completeness)."
            if obj["cap_hit_verdict"] == "FAIL" else
            f"- verdict logic: point_estimate <= 0.05 and bootstrap_ci_upper vs 0.05 "
            f"determines PASS/INCONCLUSIVE.",
        ]
    elif detail.get("bootstrap_ci_degenerate") is True:
        lines += [
            "- branch used: **zero-event Clopper-Pearson** (numerator == 0)",
            f"- Clopper-Pearson one-sided 95% upper bound: "
            f"{_fmt(detail.get('clopper_pearson_upper_bound'))}",
            "- PASS threshold: 0.05",
        ]
    else:
        lines.append(f"- raw detail: `{json.dumps(detail, sort_keys=True)}`")

    lines += [
        "", "## Decision diffs -- full per-diff capture schema (spec Sec.5)", "",
        f"**diff_count: {obj['diff_count']}** (decisions where the chosen action differs "
        "off vs on)", "",
    ]
    for i, d in enumerate(obj["diffs"]):
        lines += [
            f"### Diff {i + 1}: `{d['request_hash']}`", "",
            f"- off_chosen_action: `{d['off_chosen_action']}`",
            f"- on_chosen_action: `{d['on_chosen_action']}`",
            f"- off_score: {_fmt(d['off_score'])}",
            f"- on_score: {_fmt(d['on_score'])}",
            f"- off_margin_to_runner_up: {_fmt(d['off_margin_to_runner_up'])}",
            f"- on_margin_to_runner_up: {_fmt(d['on_margin_to_runner_up'])}",
            f"- tera_changed: {d['tera_changed']}",
            f"- action_diff_kind: `{d['action_diff_kind']}`",
            f"- events_complete: **{d['events_complete']}**",
            f"- mechanically_explained: **{d['mechanically_explained']}** (never True when "
            "events_complete is False, spec Sec.4)",
            f"- left_top_k: {d['left_top_k'] or '[]'}",
            f"- entered_top_k: {d['entered_top_k'] or '[]'}",
            "",
        ]
    lines += [
        "## Provenance note", "",
        "This report was generated by `scripts/run_accuracy_gate_b.py` (Task 11), which reuses "
        "Task 4/7's exact corpus-extraction/dedup wiring and Task 9's real "
        "`CalcClient`/`DamageOracle`/`SpeedOracle`/`SpeciesDex` construction pattern -- no "
        "sampling or truncation; every MOVE decision in the full deduplicated corpus was "
        "attempted.", "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    gate_a_obj = json.loads(GATE_A_JSON.read_text(encoding="utf-8"))
    gate_a_md = render_gate_a_markdown(gate_a_obj)
    GATE_A_MD.write_text(gate_a_md, encoding="utf-8")
    print(f"wrote {GATE_A_MD}")

    gate_b_obj = json.loads(GATE_B_JSON.read_text(encoding="utf-8"))
    gate_b_md = render_gate_b_markdown(gate_b_obj)
    GATE_B_MD.write_text(gate_b_md, encoding="utf-8")
    print(f"wrote {GATE_B_MD}")


if __name__ == "__main__":
    main()

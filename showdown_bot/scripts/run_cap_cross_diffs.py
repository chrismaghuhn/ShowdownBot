# showdown_bot/scripts/run_cap_cross_diffs.py
"""Real run: cap6-vs-cap4, cap6-vs-off, cap8-vs-cap4, cap8-vs-off action diffs, via
compare_action_tables (Task 2), reading the action-capture tables from Task 5 and the
decision-id-manifest from Task 4. Every row already carries a pre-computed chosen_action_canonical
-- this script performs no live normalize_choose calls. off-vs-cap score comparisons are
explicitly SKIPPED (spec Sec.2.3 -- legacy_frozen_score's construction is verified non-equivalent
to chosen_candidate_score, see this plan's "Real API facts" section).

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/run_cap_cross_diffs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"


def _load_rows(path: Path):
    from showdown_bot.eval.accuracy_cap_derisk import ActionTableRow
    return [ActionTableRow(**json.loads(l)) for l in path.read_text(encoding="utf-8").splitlines() if l]


def main() -> None:
    out_path = OUT_DIR / "cross-cap-diffs.json"
    if out_path.exists():
        raise SystemExit(f"BLOCKED: {out_path} already exists -- delete it explicitly first if a genuine re-run is intended.")

    from dataclasses import asdict

    from showdown_bot.eval.accuracy_cap_derisk import ActionTableRow, compare_action_tables

    manifest_rows = [
        json.loads(l) for l in (OUT_DIR / "decision-id-manifest.jsonl").read_text(encoding="utf-8").splitlines() if l
    ]
    off_rows = [
        ActionTableRow(
            decision_id=r["decision_id"],
            chosen_action_raw=r["legacy_frozen_chosen_action"],
            chosen_action_canonical=r["legacy_frozen_action_canonical"],
            candidate_resolution_status="exact", chosen_candidate_rank=0, chosen_rank_mismatch=False,
            top_rank_score=None, chosen_candidate_score=None,
        )
        for r in manifest_rows
    ]
    cap4_rows = _load_rows(OUT_DIR / "cap4_auxiliary-action-capture.jsonl")
    cap6_rows = _load_rows(OUT_DIR / "cap6-action-capture.jsonl")
    cap8_rows = _load_rows(OUT_DIR / "cap8-action-capture.jsonl")

    pairs = [
        ("cap4 -> cap6", cap4_rows, cap6_rows, True, None),
        ("cap4 -> cap8", cap4_rows, cap8_rows, True, None),
        ("off -> cap6", off_rows, cap6_rows, False, "legacy_frozen_score not proven equivalent to top_rank_score/chosen_candidate_score"),
        ("off -> cap8", off_rows, cap8_rows, False, "legacy_frozen_score not proven equivalent to top_rank_score/chosen_candidate_score"),
    ]

    results = {}
    for direction, ref, cand, score_comparable, reason in pairs:
        diff = compare_action_tables(
            ref, cand, direction=direction, score_comparable=score_comparable,
            score_incompatible_reason=reason,
        )
        score_changed_count = sum(
            1 for r in diff.rows if r.top_rank_score_changed or r.chosen_candidate_score_changed
        )
        print(f"{direction}: {diff.action_changed_count}/{len(diff.rows)} action changes "
              f"(score_comparable={score_comparable}, score_changed_count={score_changed_count})")
        results[direction] = {
            "action_changed_count": diff.action_changed_count,
            "score_changed_count": score_changed_count,
            "total": len(diff.rows),
            "rows": [asdict(r) for r in diff.rows if r.action_changed],  # only the changed rows, full table is large
        }

    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()

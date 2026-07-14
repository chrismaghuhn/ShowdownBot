"""Real run: validates the cap=4 auxiliary action-capture table (Task 5) against the frozen
gate-b-report.json's historical 20 diffs, two-stage (spec Sec.2.3). HARD CHECKPOINT -- if this
fails, STOP, do not run Task 7/8's cap6/cap8 comparisons against this table.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/validate_cap4_auxiliary.py
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
GATE_B_REPORT = DATA_EVAL / "accuracy-gate" / "gate-b-report.json"
MANIFEST_PATH = DATA_EVAL / "accuracy-cap-derisk" / "decision-id-manifest.jsonl"
AUX_PATH = DATA_EVAL / "accuracy-cap-derisk" / "cap4_auxiliary-action-capture.jsonl"
OUT_PATH = DATA_EVAL / "accuracy-cap-derisk" / "cap4-auxiliary-validation-report.json"


def main() -> None:
    if OUT_PATH.exists():
        raise SystemExit(f"BLOCKED: {OUT_PATH} already exists -- delete it explicitly first if a genuine re-validation is intended.")

    from showdown_bot.eval.accuracy_cap_derisk import (
        ActionTableRow, build_request_hash_index, run_stage1_raw_reproduction, run_stage2_semantic_diff,
    )

    gate_b = json.loads(GATE_B_REPORT.read_text(encoding="utf-8"))
    manifest_rows = [json.loads(l) for l in MANIFEST_PATH.read_text(encoding="utf-8").splitlines() if l]
    aux_rows_raw = [json.loads(l) for l in AUX_PATH.read_text(encoding="utf-8").splitlines() if l]
    aux_rows = [ActionTableRow(**r) for r in aux_rows_raw]

    # fail-closed request_hash -> manifest-row index (Task 6 correction): a bare dict
    # comprehension here would silently collapse a duplicated request_hash to one row, breaking
    # this script's decision_id-based joining claim without any visible error.
    manifest_by_request_hash = build_request_hash_index(manifest_rows)
    excluded_request_hashes = {e["request_hash"] for e in gate_b["acceptance"]["exceptions"]}
    if len(excluded_request_hashes) != 63:
        raise SystemExit(f"BLOCKED: expected 63 historical exceptions, found {len(excluded_request_hashes)}")

    eligible_881_decision_ids = {
        manifest_by_request_hash[rh]["decision_id"]
        for rh in manifest_by_request_hash if rh not in excluded_request_hashes
    }
    if len(eligible_881_decision_ids) != 881:
        raise SystemExit(f"BLOCKED: expected 881 eligible decision_ids, got {len(eligible_881_decision_ids)}")

    # historical on_chosen_action for exactly the frozen 20, keyed by decision_id
    frozen_20_on_actions = {
        manifest_by_request_hash[d["request_hash"]]["decision_id"]: d["on_chosen_action"]
        for d in gate_b["diffs"]
    }

    frozen_off_actions_881 = {
        manifest_by_request_hash[rh]["decision_id"]: manifest_by_request_hash[rh]["legacy_frozen_chosen_action"]
        for rh in manifest_by_request_hash if rh not in excluded_request_hashes
    }
    aux_881 = [r for r in aux_rows if r.decision_id in eligible_881_decision_ids]

    print(f"Stage 1: raw reproduction check on {len(aux_881)} eligible decisions "
          f"(expecting exactly {len(frozen_20_on_actions)} raw diffs, exact on-action values)...")
    stage1 = run_stage1_raw_reproduction(aux_881, frozen_off_actions_881, frozen_20_on_actions)
    print(f"Stage 1 PASSED: raw diff set AND exact on-action values reproduce the frozen 20.")

    frozen_canonical_881 = {
        manifest_by_request_hash[rh]["decision_id"]: manifest_by_request_hash[rh]["legacy_frozen_action_canonical"]
        for rh in manifest_by_request_hash if rh not in excluded_request_hashes
    }
    print("Stage 2: normalized semantic diff on the same 881...")
    stage2 = run_stage2_semantic_diff(aux_881, frozen_canonical_881)
    print(f"Stage 2: {stage2.action_changed_count} semantically distinct action changes "
          f"(raw Stage-1 diff count was {len(stage1.raw_diff_decision_ids)} -- if smaller, "
          f"the difference is pre-existing representational diffs, not a failure).")

    # --- the 63 historical exclusions, evaluated separately, never folded into Stage 1/2 above ---
    excluded_decision_ids = {manifest_by_request_hash[rh]["decision_id"] for rh in excluded_request_hashes}
    aux_63 = [r for r in aux_rows if r.decision_id in excluded_decision_ids]
    frozen_actions_63 = {
        manifest_by_request_hash[rh]["decision_id"]: manifest_by_request_hash[rh]["legacy_frozen_chosen_action"]
        for rh in excluded_request_hashes
    }
    diffs_among_63 = sum(
        1 for r in aux_63 if r.chosen_action_raw != frozen_actions_63.get(r.decision_id)
    )
    print(f"Among the 63 historical exclusions: {diffs_among_63} raw action diffs found "
          f"(diagnostic bonus info for Task 10/11 -- NOT part of Stage 1/2, frozen gate unchanged).")

    OUT_PATH.write_text(json.dumps({
        "stage1_passed": stage1.passed,
        "stage1_raw_diff_count": len(stage1.raw_diff_decision_ids),
        "stage2_semantic_diff_count": stage2.action_changed_count,
        "diffs_among_historical_63": diffs_among_63,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print("\nVALIDATION GATE PASSED. Cap=6/8 may now be compared against the cap4_auxiliary table.")


if __name__ == "__main__":
    main()

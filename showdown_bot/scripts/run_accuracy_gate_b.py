"""Task 11 driver (accuracy-offline-gate plan): Gate B confirmatory run, for real, over the
FULL deduplicated corpus.

This is the load-bearing real run of the whole 11-task plan. It reuses Task 4/Task 7's exact
corpus-extraction/dedup wiring verbatim (same 4 glob dirs, same 6 manifest files, same
``keep_priority``, the same ``deduplicate_battle_logs``/``extract_decisions_from_log`` calls
from ``room_raw_replay.py``) and Task 9's real ``CalcClient``/``DamageOracle``/``SpeedOracle``/
``SpeciesDex`` construction pattern, then calls ``eval.accuracy_gate_b.run_gate_b`` (Task 10)
over every extracted MOVE decision (accuracy off AND on, per decision -- two full
``heuristic_choose_for_request`` calls per replayed decision).

Writes ``data/eval/accuracy-gate/gate-b-report.json`` (the full, real result payload) --
``data/eval/accuracy-gate/gate-b-report.md`` is rendered from that JSON by a separate,
lighter step (kept separate so the JSON can be regenerated/reviewed without re-running the
real, multi-minute replay).

Usage (from the showdown_bot/ directory of this worktree):

    PYTHONPATH="$(pwd)/src" python scripts/run_accuracy_gate_b.py

(PYTHONPATH must point at THIS worktree's src/ -- the machine has an editable pip install of
showdown-bot pointing at the main repo checkout, not this worktree; without the override,
imports silently resolve to the wrong package.)
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

# Real calc backend, persistent Node process -- matches Task 4/7's drivers (avoids a fresh spawn
# per decision across the ~944 real MOVE decisions x2 this script replays). SHOWDOWN_CALC_BACKEND
# is NON_BEHAVIORAL (eval/config_env.py) -- transport only, never affects which move is chosen.
os.environ.setdefault("SHOWDOWN_CALC_BACKEND", "persistent")

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))  # shadow the editable install (main-repo gotcha)

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-gate"
REPORT_JSON_OUT = OUT_DIR / "gate-b-report.json"

FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85  # plan's directly-verified real-corpus number; Task 4/7 both checked this


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> None:
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_gate_b import run_gate_b
    from showdown_bot.eval.room_raw_replay import (
        RequestKind,
        deduplicate_battle_logs,
        extract_decisions_from_log,
    )

    print(f"showdown_bot resolved from: {SHOWDOWN_BOT_ROOT}")

    # --- Step 1: glob every .log.gz under the 4 canonical corpus directories -- IDENTICAL to
    # run_accuracy_baseline_freeze.py / run_accuracy_baseline_diff.py ---
    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw",
        DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw",
        DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)
    print(f"found {len(log_files)} .log.gz files under the 4 canonical corpus directories")

    # --- Step 2: global battle-level dedup -- IDENTICAL to run_accuracy_baseline_freeze.py ---
    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl",
        DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl",
        DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    exclusion_reasons = dict(Counter(e.reason for e in dedup_report.excluded))
    print(f"dedup: files_found={dedup_report.files_found} kept={len(dedup_report.kept)} "
          f"excluded={len(dedup_report.excluded)} final_g={dedup_report.final_g} "
          f"excluded_by_reason={exclusion_reasons}")

    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(
            f"BLOCKED: expected final_g == {EXPECTED_FINAL_G} (Task 4's verified real-corpus "
            f"number), got {dedup_report.final_g}. Refusing to run Gate B over an unverified "
            f"corpus (spec Sec.6 item 6 / Sec.7). Every downstream number would need "
            f"re-deriving before proceeding -- STOP, do not silently continue."
        )

    # --- Step 3: extract decisions from every kept file; build a battle_id_for(d) closure keyed
    # off which kept file d came from (object-identity keyed -- robust regardless of whether
    # request_hash is battle-scoped-unique, which it is not guaranteed to be in general even
    # though it happens to hold for this corpus per Task 7's diff). ---
    all_decisions = []
    decision_to_battle_id: dict[int, str] = {}
    kind_counts = {RequestKind.MOVE: 0, RequestKind.TEAM_PREVIEW: 0, RequestKind.FORCE_SWITCH: 0}
    kept_sorted = sorted(dedup_report.kept, key=str)
    for p in kept_sorted:
        battle_id = _rel(p)
        decisions = extract_decisions_from_log(p)
        for d in decisions:
            kind_counts[d.kind] = kind_counts.get(d.kind, 0) + 1
            decision_to_battle_id[id(d)] = battle_id
        all_decisions.extend(decisions)
    print(f"decision kinds across {len(kept_sorted)} kept files: "
          f"{ {k.value: v for k, v in kind_counts.items()} }")
    move_decision_count = kind_counts[RequestKind.MOVE]
    print(f"{move_decision_count} MOVE decisions will be replayed x2 (off+on) by Gate B")

    def battle_id_for(d):
        return decision_to_battle_id[id(d)]

    # --- Step 4: real calc/oracle chain -- IDENTICAL construction pattern to Task 4/7/9's
    # drivers (real objects, real replayed battle states, not fakes). oracle_factory (not a
    # single shared instance) matches run_gate_b's signature -- it builds a fresh DamageOracle
    # per _decide_with_trace call, mirroring how decision.py's own real callers use it. ---
    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    print(f"\nrunning Gate B (Task 10's run_gate_b) over the FULL deduplicated corpus: "
          f"{move_decision_count} MOVE decisions x 2 (off+on) -- this is the load-bearing real "
          f"run, no sampling/truncation.")
    t0 = time.perf_counter()
    result = run_gate_b(
        decisions=all_decisions, battle_id_for=battle_id_for,
        book=book, calc=calc, oracle_factory=lambda: DamageOracle(calc),
        speed_oracle=speed_oracle, dex=dex,
    )
    elapsed = time.perf_counter() - t0
    print(f"Gate B run complete in {elapsed:.1f}s "
          f"({(elapsed / move_decision_count) * 1000:.1f} ms/decision average, off+on combined)")

    try:
        calc.close()
    except Exception:  # noqa: BLE001 - best-effort cleanup, never fail the run over it
        pass

    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception as exc:  # noqa: BLE001 - provenance is best-effort for the report
        source_commit = None
        print(f"WARNING: could not determine source_commit via git rev-parse HEAD: {exc}")

    # --- Step 5: build the report payload (spec Sec.5/Sec.6 item 5's separate-numbers
    # requirement -- dedup breakdown reported as distinct fields, not folded into one number) ---
    payload = {
        "report_schema_version": "gate-b-report-v1",
        "source_commit": source_commit,
        "elapsed_seconds": round(elapsed, 1),
        "dedup": {
            "files_found": dedup_report.files_found,
            "excluded_total": len(dedup_report.excluded),
            "excluded_by_reason": exclusion_reasons,
            "unique_battles_final_g": dedup_report.final_g,
            "expected_final_g": EXPECTED_FINAL_G,
            "final_g_matches_expected": dedup_report.final_g == EXPECTED_FINAL_G,
        },
        "decision_kind_counts": {k.value: v for k, v in kind_counts.items()},
        "n_decisions_compared": result.n_decisions_compared,
        "excluded_team_preview_count": result.excluded_team_preview_count,
        "excluded_force_switch_count": result.excluded_force_switch_count,
        "cap_hit_verdict": result.cap_hit_verdict.value if result.cap_hit_verdict else None,
        "cap_hit_verdict_detail": result.cap_hit_verdict_detail,
        "acceptance": {
            "no_exceptions": result.acceptance.no_exceptions,
            "no_nans": result.acceptance.no_nans,
            "exception_count": len(result.acceptance.exceptions),
            "exceptions": [
                {"request_hash": rh, "exception": msg}
                for rh, msg in result.acceptance.exceptions
            ],
            "off_path_byte_identical": result.acceptance.off_path_byte_identical,
            "latency_within_budget": result.acceptance.latency_within_budget,
        },
        "diff_count": len(result.diffs),
        "diffs": [
            {
                "request_hash": d.request_hash,
                "off_chosen_action": d.off_chosen_action,
                "on_chosen_action": d.on_chosen_action,
                "off_score": d.off_score,
                "on_score": d.on_score,
                "off_margin_to_runner_up": d.off_margin_to_runner_up,
                "on_margin_to_runner_up": d.on_margin_to_runner_up,
                "tera_changed": d.tera_changed,
                "action_diff_kind": d.action_diff_kind,
                "events_complete": d.events_complete,
                "mechanically_explained": d.mechanically_explained,
                "left_top_k": d.left_top_k,
                "entered_top_k": d.entered_top_k,
            }
            for d in result.diffs
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    print(f"\nwrote {REPORT_JSON_OUT}")

    print(f"\nn_decisions_compared={result.n_decisions_compared} "
          f"exceptions={len(result.acceptance.exceptions)} "
          f"no_nans={result.acceptance.no_nans} "
          f"diff_count={len(result.diffs)} "
          f"cap_hit_verdict={result.cap_hit_verdict}")
    print("\nDONE.")


if __name__ == "__main__":
    main()

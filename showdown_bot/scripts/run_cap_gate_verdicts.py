"""Real run: SHOWDOWN_ACCURACY_BRANCH_CAP in {6, 8}, full G=85 corpus, via the UNCHANGED
accuracy_gate_b.run_gate_b / accuracy_gate_stats.verdict_for_cap_hit_rate (spec Sec.2.5). Mirrors
run_accuracy_gate_b.py exactly except for the branch-cap env var and output path. cap=4 is never
run here -- data/eval/accuracy-gate/gate-b-report.json stays the sole authoritative cap=4 result.

Usage (from showdown_bot/):
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_gate_verdicts.py --cap 6
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_gate_verdicts.py --cap 8
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

os.environ["SHOWDOWN_CALC_BACKEND"] = "persistent"  # forced, not setdefault

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, required=True, choices=[6, 8])
    args = parser.parse_args()

    out_path = OUT_DIR / f"cap{args.cap}-report.json"
    if out_path.exists():
        raise SystemExit(f"BLOCKED: {out_path} already exists -- delete it explicitly first if a genuine re-run is intended.")

    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_gate_b import run_gate_b
    from showdown_bot.eval.room_raw_replay import (
        RequestKind, deduplicate_battle_logs, extract_decisions_from_log,
    )

    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw", DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw", DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)

    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl", DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl", DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl", DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(f"BLOCKED: expected final_g == {EXPECTED_FINAL_G}, got {dedup_report.final_g}")

    all_decisions = []
    decision_to_battle_id: dict[int, str] = {}
    kind_counts: Counter = Counter()
    for p in sorted(dedup_report.kept, key=str):
        battle_id = _rel(p)
        for d in extract_decisions_from_log(p):
            kind_counts[d.kind] += 1
            decision_to_battle_id[id(d)] = battle_id
            all_decisions.append(d)

    def battle_id_for(d):
        return decision_to_battle_id[id(d)]

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(args.cap)
    print(f"running Gate B (unchanged run_gate_b) at cap={args.cap}, full corpus...")
    t0 = time.perf_counter()
    result = run_gate_b(
        decisions=all_decisions, battle_id_for=battle_id_for,
        book=book, calc=calc, oracle_factory=lambda: DamageOracle(calc),
        speed_oracle=speed_oracle, dex=dex,
    )
    elapsed = time.perf_counter() - t0
    os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
    print(f"cap={args.cap} Gate B complete in {elapsed:.1f}s")

    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception:
        source_commit = None

    move_decision_count = kind_counts[RequestKind.MOVE]
    payload = {
        "report_schema_version": "cap-derisk-gate-report-v1",
        "branch_cap": args.cap,
        "source_commit": source_commit,
        "elapsed_seconds": round(elapsed, 1),
        "dedup": {
            "files_found": dedup_report.files_found, "unique_battles_final_g": dedup_report.final_g,
        },
        "decision_kind_counts": {k.value: v for k, v in kind_counts.items()},
        "n_decisions_compared": result.n_decisions_compared,
        "cap_hit_verdict": result.cap_hit_verdict.value if result.cap_hit_verdict else None,
        "cap_hit_verdict_detail": result.cap_hit_verdict_detail,
        "acceptance": {
            "no_exceptions": result.acceptance.no_exceptions,
            "no_nans": result.acceptance.no_nans,
            "exception_count": len(result.acceptance.exceptions),
            "exceptions": [{"request_hash": rh, "exception": msg} for rh, msg in result.acceptance.exceptions],
        },
        "diff_count": len(result.diffs),
        "diffs": [
            {
                "request_hash": d.request_hash, "off_chosen_action": d.off_chosen_action,
                "on_chosen_action": d.on_chosen_action, "off_score": d.off_score, "on_score": d.on_score,
                "tera_changed": d.tera_changed, "action_diff_kind": d.action_diff_kind,
                "events_complete": d.events_complete, "mechanically_explained": d.mechanically_explained,
                "left_top_k": d.left_top_k, "entered_top_k": d.entered_top_k,
            }
            for d in result.diffs
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"n_decisions_compared={result.n_decisions_compared} exceptions={len(result.acceptance.exceptions)} "
          f"diff_count={len(result.diffs)} cap_hit_verdict={result.cap_hit_verdict}")


if __name__ == "__main__":
    main()

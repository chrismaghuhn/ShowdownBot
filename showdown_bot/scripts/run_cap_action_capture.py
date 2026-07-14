"""Real run: for a given SHOWDOWN_ACCURACY_BRANCH_CAP value, replay all 944 MOVE decisions through
heuristic_choose_for_request(trace=...) with SHOWDOWN_ACCURACY_MODE=1, and build a full action
table (spec Sec.2.3) via build_action_table_row -- each row's chosen_action_canonical computed
against that decision's own real request.

cap=4's run is an AUXILIARY action-capture -- explicitly labeled as such, never a new gate verdict
(data/eval/accuracy-gate/gate-b-report.json stays the sole authoritative cap=4 result). cap=6/cap=8
are this study's own primary action-capture runs.

Usage (from showdown_bot/):
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 4 --label cap4_auxiliary
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 6 --label cap6
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 8 --label cap8
"""

from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ["SHOWDOWN_CALC_BACKEND"] = "persistent"  # forced, not setdefault -- see Task 9's note
# on why silently inheriting a caller's different backend value would badly skew results.

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
MANIFEST_PATH = OUT_DIR / "decision-id-manifest.jsonl"
FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85
LABEL_TO_CAP = {"cap4_auxiliary": 4, "cap6": 6, "cap8": 8}


def _file_content_hash(path) -> str | None:
    """sha1[:16] of a file's bytes (mirrors run_accuracy_baseline_freeze.py's own local copy of
    cli.py's private config-hash provenance helper)."""
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:  # noqa: BLE001 - provenance is best-effort; missing file -> None
        return None


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, required=True, choices=[4, 6, 8])
    parser.add_argument("--label", type=str, required=True, choices=sorted(LABEL_TO_CAP))
    args = parser.parse_args()

    expected_cap = LABEL_TO_CAP[args.label]
    if expected_cap != args.cap:
        raise SystemExit(
            f"BLOCKED: --label {args.label!r} implies cap={expected_cap}, but --cap {args.cap} "
            f"was passed -- refusing to write a mismatched artifact."
        )

    out_path = OUT_DIR / f"{args.label}-action-capture.jsonl"
    meta_path = OUT_DIR / f"{args.label}-action-capture-meta.json"
    existing = [p for p in (out_path, meta_path) if p.exists()]
    if existing:
        raise SystemExit(
            f"BLOCKED: {[str(p) for p in existing]} already exist (checked independently, "
            f"either one present blocks the run). Refusing to silently overwrite -- delete both "
            f"explicitly first if a genuine re-run is intended."
        )

    if not MANIFEST_PATH.exists():
        raise SystemExit(f"BLOCKED: {MANIFEST_PATH} not found -- run Task 4 first.")
    expected_decision_ids = {
        json.loads(l)["decision_id"] for l in MANIFEST_PATH.read_text(encoding="utf-8").splitlines() if l
    }

    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.moves import movedata_path
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_cap_derisk import (
        DecisionIdComponents, build_action_table_row, compute_decision_id,
    )
    from showdown_bot.eval.config_env import behavior_env, build_config_manifest, config_provenance_for_format
    from showdown_bot.eval.result_jsonl import make_config_hash
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

    missing_identity = [p for p in dedup_report.kept if p not in dedup_report.kept_identities]
    if missing_identity:
        raise SystemExit(
            f"BLOCKED: {len(missing_identity)} kept file(s) have no SeedIdentity in "
            f"kept_identities (content-hash-fallback-kept) -- this plan's decision_id scheme "
            f"assumes every kept file has one, verified true for this corpus as of writing; "
            f"re-verify before proceeding. Files: {missing_identity}"
        )

    all_decisions = []
    for p in sorted(dedup_report.kept, key=str):
        identity = dedup_report.kept_identities[p]
        for d in extract_decisions_from_log(p):
            if d.kind != RequestKind.MOVE:
                continue
            did = compute_decision_id(DecisionIdComponents(
                seed_base=identity.seed_base, seed_index=identity.seed_index,
                request_hash=d.request_hash, log_prefix_hash=d.log_prefix_hash,
                side=d.side, rqid=d.request.rqid, turn=d.turn,
            ))
            all_decisions.append((did, d))
    print(f"{len(all_decisions)} MOVE decisions to replay at cap={args.cap}")

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
    os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(args.cap)

    rows = []
    t0 = time.perf_counter()
    for decision_id, d in all_decisions:
        trace = DecisionTrace()
        chosen = heuristic_choose_for_request(
            d.request, state=copy.deepcopy(d.state), book=book, our_side=d.side,
            calc=calc, oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=dex, trace=trace,
        )
        rows.append(build_action_table_row(decision_id, chosen, trace, d.request))
    elapsed = time.perf_counter() - t0
    print(f"cap={args.cap} action-capture complete in {elapsed:.1f}s "
          f"({(elapsed / len(all_decisions)) * 1000:.1f} ms/decision)")

    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass

    actual_decision_ids = {r.decision_id for r in rows}
    if actual_decision_ids != expected_decision_ids:
        raise SystemExit(
            f"BLOCKED: this run's decision_id set does not exactly match the manifest -- "
            f"missing={sorted(expected_decision_ids - actual_decision_ids)[:5]}... "
            f"extra={sorted(actual_decision_ids - expected_decision_ids)[:5]}... "
            f"(counts: manifest={len(expected_decision_ids)} this_run={len(actual_decision_ids)})"
        )

    status_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r.candidate_resolution_status] = status_counts.get(r.candidate_resolution_status, 0) + 1
    print(f"candidate_resolution_status breakdown: {status_counts}")

    # --- provenance: cap, label, source_commit, real config_hash, dependency provenance,
    # matching this project's established convention (scripts/run_accuracy_baseline_freeze.py).
    # config_hash is computed from an EXPLICITLY built env dict (SHOWDOWN_ACCURACY_MODE=1,
    # SHOWDOWN_ACCURACY_BRANCH_CAP=<cap> forced onto a snapshot of the current process env) --
    # NOT from behavior_env()'s no-arg default (which reads live os.environ at call time). This
    # makes config_hash correct regardless of whether the two accuracy env vars are still set on
    # the process at this point in the script; an earlier draft of this script computed
    # provenance strictly AFTER popping them, which would have silently hashed the OFF-mode
    # environment instead of the mode this run actually used. ---
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"could not determine source_commit via git rev-parse HEAD: {exc}")

    explicit_env = dict(os.environ)
    explicit_env["SHOWDOWN_ACCURACY_MODE"] = "1"
    explicit_env["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(args.cap)
    priors_hash = _file_content_hash(load_format_config(FORMAT_ID).meta_path("protect_priors"))
    spreads_hash = _file_content_hash(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    movedata_hash = _file_content_hash(movedata_path())
    provenance = config_provenance_for_format(FORMAT_ID)
    manifest = build_config_manifest(
        agent="heuristic", format_id=FORMAT_ID, priors_hash=priors_hash, spreads_hash=spreads_hash,
        env=behavior_env(environ=explicit_env), movedata_hash=movedata_hash,
        format_config_hash=provenance["format_config_hash"],
        calc_pin_hash=provenance["calc_pin_hash"],
    )
    config_hash = make_config_hash(manifest)
    lock_file = SHOWDOWN_BOT_ROOT / "pyproject.toml"
    dependency_lock_hash = hashlib.sha256(lock_file.read_bytes()).hexdigest()

    os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)

    # --- all computation done; write BOTH files atomically now, last, so a failure anywhere
    # above (including the provenance block) can never leave the main table present without its
    # meta sidecar, or vice versa. ---
    capture_content = "".join(
        json.dumps(asdict(r), sort_keys=True) + "\n" for r in sorted(rows, key=lambda x: x.decision_id)
    )
    meta_content = json.dumps({
        "cap": args.cap, "label": args.label, "source_commit": source_commit,
        "config_hash": config_hash, "python_version": sys.version,
        "dependency_lock_hash": dependency_lock_hash,
        "row_count": len(rows), "elapsed_seconds": round(elapsed, 1),
        "candidate_resolution_status_counts": status_counts,
    }, indent=2, sort_keys=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(out_path, capture_content)
    print(f"wrote {out_path} ({len(rows)} rows)")
    _atomic_write_text(meta_path, meta_content)
    print(f"wrote {meta_path} (config_hash={config_hash})")


if __name__ == "__main__":
    main()

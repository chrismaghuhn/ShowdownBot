"""Real run: full-corpus latency, both trace modes (none / DecisionTrace()), for
SHOWDOWN_ACCURACY_BRANCH_CAP in {4 (cap4_auxiliary), 6, 8}, spec Sec.2.6. Cap order uses a cyclic
Latin square over the sorted game index (guarantees each cap lands in each cap-order position an
equal +/-1 number of times) -- the pure `cap_order_for_game`/`CAPS` logic lives in
showdown_bot.eval.accuracy_cap_derisk (unit-tested there, imported here) rather than as a private
helper in this driver script, per this plan's Architecture convention that pure logic belongs in
accuracy_cap_derisk.py. Trace-mode order alternates off a single monotonic (game, cap)-slot
counter (guarantees exact +/-1 balance between trace_enabled-first and trace_none-first). Both are
DETERMINISTIC combinatorial designs, not randomized -- see this task's "Corrections applied here"
note for why a random.shuffle-based design was replaced. Realized position-frequency counts are
recorded and fail-closed asserted to differ by at most 1 before any latency number is reported.
The persistent calc backend is enforced fail-closed and warmed once, up front, before any timed
measurement.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/run_cap_latency_sweep.py
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys
import time
from pathlib import Path

_existing_backend = os.environ.get("SHOWDOWN_CALC_BACKEND")
if _existing_backend is not None and _existing_backend != "persistent":
    raise SystemExit(
        f"BLOCKED: SHOWDOWN_CALC_BACKEND is already set to {_existing_backend!r} in this "
        f"environment -- this latency sweep requires the persistent backend specifically "
        f"(a different backend has a completely different latency profile and would silently "
        f"invalidate every measurement below). Unset it or explicitly set it to 'persistent' "
        f"before running."
    )
os.environ["SHOWDOWN_CALC_BACKEND"] = "persistent"

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85
TRACE_MODES = [False, True]  # False=trace_none, True=trace_enabled


def _percentile(sorted_ms: list[float], q: float) -> float:
    idx = min(len(sorted_ms) - 1, max(0, int(round(q * (len(sorted_ms) - 1)))))
    return sorted_ms[idx]


def main() -> None:
    out_path = OUT_DIR / "latency-results.json"
    if out_path.exists():
        raise SystemExit(f"BLOCKED: {out_path} already exists -- delete it explicitly first if a genuine re-run is intended.")

    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_cap_derisk import CAPS, cap_order_for_game
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

    # group decisions by game (source file) for per-game cap/trace-mode-order counterbalancing
    by_game: dict[str, list] = {}
    for p in sorted(dedup_report.kept, key=str):
        decisions = [d for d in extract_decisions_from_log(p) if d.kind == RequestKind.MOVE]
        by_game[str(p)] = decisions
    total_decisions = sum(len(v) for v in by_game.values())
    print(f"{total_decisions} MOVE decisions across {len(by_game)} games")
    expected_per_series = total_decisions  # each of the 6 (cap, trace_mode) series should measure
    # every decision exactly once absent an exception

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    def decide(d, cap, with_trace):
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
        os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(cap)
        trace = DecisionTrace() if with_trace else None
        t0 = time.perf_counter()
        heuristic_choose_for_request(
            d.request, state=copy.deepcopy(d.state), book=book, our_side=d.side,
            calc=calc, oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=dex, trace=trace,
        )
        return (time.perf_counter() - t0) * 1000.0

    # --- warm the backend once, controlled, before ANY timed measurement ---
    print("warming persistent calc backend...")
    first_game_decisions = next(iter(by_game.values()))
    for d in first_game_decisions[:3]:
        decide(d, cap=4, with_trace=False)
    print("warm-up complete")

    # --- deterministic cap-order Latin square + monotonic trace-mode alternation ---
    game_ids = sorted(by_game)
    series_keys = [f"cap{c}_{'trace_enabled' if t else 'trace_none'}" for c in CAPS for t in TRACE_MODES]
    results: dict[str, list[float]] = {k: [] for k in series_keys}
    exception_counts: dict[str, int] = {k: 0 for k in series_keys}
    measured_counts: dict[str, int] = {k: 0 for k in series_keys}
    cap_position_counts: dict[int, list[int]] = {c: [0] * len(CAPS) for c in CAPS}
    trace_order_counts = {"trace_enabled_first": 0, "trace_none_first": 0}

    combined_index = 0  # increments once per (game, cap) slot across the WHOLE sweep -- this is
    # what makes the trace-mode alternation exact regardless of len(game_ids) or len(CAPS) parity.
    for game_index, game_id in enumerate(game_ids):
        cap_order = cap_order_for_game(game_index)
        for cap_position, cap in enumerate(cap_order):
            cap_position_counts[cap][cap_position] += 1
            trace_order = TRACE_MODES if combined_index % 2 == 0 else list(reversed(TRACE_MODES))
            trace_order_counts["trace_enabled_first" if trace_order[0] else "trace_none_first"] += 1
            combined_index += 1
            for with_trace in trace_order:
                series_key = f"cap{cap}_{'trace_enabled' if with_trace else 'trace_none'}"
                for d in by_game[game_id]:
                    try:
                        ms = decide(d, cap, with_trace)
                        results[series_key].append(ms)
                        measured_counts[series_key] += 1
                    except Exception as exc:  # noqa: BLE001
                        exception_counts[series_key] += 1
                        print(f"EXCEPTION cap={cap} trace_enabled={with_trace}: {exc}")

    os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass

    # --- counterbalancing is a CHECKED property of this actual run, not just the intended
    # design: fail-closed before reporting any latency number if either invariant is violated. ---
    for cap, positions in cap_position_counts.items():
        spread = max(positions) - min(positions)
        if spread > 1:
            raise SystemExit(
                f"BLOCKED: cap={cap} cap-order position counts {positions} (index = cap-order "
                f"position 0/1/2) span {spread} across {len(game_ids)} games -- the Latin-square "
                f"counterbalancing invariant (max-min <= 1) was violated, investigate "
                f"cap_order_for_game (showdown_bot/eval/accuracy_cap_derisk.py) before trusting "
                f"any latency number below."
            )
    te_first = trace_order_counts["trace_enabled_first"]
    tn_first = trace_order_counts["trace_none_first"]
    if abs(te_first - tn_first) > 1:
        raise SystemExit(
            f"BLOCKED: trace-mode order counts (enabled_first={te_first}, none_first={tn_first}) "
            f"differ by {abs(te_first - tn_first)} across {combined_index} (game, cap) slots -- "
            f"the trace-mode alternation invariant (differ by <= 1) was violated."
        )
    print(f"counterbalancing verified: cap_position_counts={cap_position_counts} "
          f"trace_order_counts={trace_order_counts}")

    for series_key in series_keys:
        actual = measured_counts[series_key] + exception_counts[series_key]
        if actual != expected_per_series:
            raise SystemExit(
                f"BLOCKED: series {series_key!r} measured+excepted {actual} decisions, expected "
                f"exactly {expected_per_series} -- some decisions were silently skipped, "
                f"investigate before trusting this series' p50/p95/max."
            )

    summary = {}
    for series_key, values in results.items():
        values_sorted = sorted(values)
        summary[series_key] = {
            "n": len(values_sorted),
            "p50": _percentile(values_sorted, 0.50) if values_sorted else None,
            "p95": _percentile(values_sorted, 0.95) if values_sorted else None,
            "max": values_sorted[-1] if values_sorted else None,
            "exceptions": exception_counts[series_key],
            "expected_denominator": expected_per_series,
        }

    out_path.write_text(json.dumps({
        "total_decisions": total_decisions, "sampled": False,
        "counterbalancing": {
            "cap_position_counts": cap_position_counts, "trace_order_counts": trace_order_counts,
        },
        "results": summary,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    for series_key, s in summary.items():
        print(f"{series_key}: n={s['n']}/{s['expected_denominator']} p50={s['p50']:.1f}ms "
              f"p95={s['p95']:.1f}ms max={s['max']:.1f}ms exceptions={s['exceptions']}")


if __name__ == "__main__":
    main()

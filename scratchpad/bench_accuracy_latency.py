"""Accuracy-branching slice -- Task 8 local latency micro-bench.

Mirrors the 2c depth-2 Stage-1 gate method (reports/2026-07-12-2c-depth2-derisk-verdict.md,
harness copied from scratchpad/bench_depth2_latency.py of that slice): persistent real
CalcClient Node backend, fresh per-decision DamageOracle, one realistic doubles board that
carries a spread move with accuracy<100 on EACH side (p1 Rillaboom: Heat Wave 90%; p2
Tornadus: Bleakwind Storm 80%) so accuracy branching actually forks, timed across
SHOWDOWN_ACCURACY_MODE off (baseline) vs on x SHOWDOWN_ACCURACY_BRANCH_CAP in {2,4,6,8}.
n=25/config after 5 warmups. Gate: p95<1000ms (mirrors the depth-2 gate).

In addition to latency, this script tracks how often resolve_turn_branches actually hits
its branch_cap (i.e. falls back to legacy implicit-hit resolution for the remaining pending
accuracy events instead of fully expanding the tree) -- both at the call level (every
resolve_turn_branches invocation across a decision's full candidate x response sweep) and at
the decision level (did ANY call within a decision hit the cap). This is done via a thin
monkeypatch of evaluate.resolve_turn_branches that delegates to the real function and just
increments counters -- it adds no extra resolve_turn calls beyond what production already
performs, so it does not distort the timing.
"""
from __future__ import annotations

import copy
import json
import math
import os
import time
from pathlib import Path

os.environ["SHOWDOWN_CALC_BACKEND"] = "persistent"   # production/Kaggle mode; oneshot spawns Node per flush

ROOT = Path(r"C:\Users\chris\Documents\SHowdown BOt\.claude\worktrees\accuracy-hit-probability\showdown_bot")
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT / "src"))   # the editable install resolves to the MAIN repo checkout,
                                          # not this worktree -- must shadow it explicitly (same
                                          # gotcha the depth-2 bench hit).

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.opponent import SpeciesDex
from showdown_bot.battle.oracle import DamageOracle
import showdown_bot.battle.evaluate as evaluate_mod
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIX = ROOT / "tests" / "fixtures" / "request_doubles_moves.json"


def make_state() -> BattleState:
    st = BattleState()
    # p1 actives per the request fixture: Incineroar (Fake Out/Flare Blitz/Protect/Knock Off,
    # all 100% acc) + Rillaboom (Heat Wave 90% SPREAD/Earth Power/Protect/Solar Beam) --
    # Heat Wave supplies the p1-side accuracy<100 spread move.
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    # Bleakwind Storm (80% acc, allAdjacentFoes) supplies the p2-side accuracy<100 spread move.
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


REQ = BattleRequest.model_validate(json.loads(FIX.read_text()))
BASE_STATE = make_state()
BOOK = load_spread_book(load_format_config("gen9vgc2025regi").meta_path("default_spreads"))
CALC = CalcClient()                                   # persistent (measure decision, not spawn)
SPEED = SpeedOracle(stats_backend=CALC.backend)
DEX = SpeciesDex(CALC.backend)

# --- branch-cap-hit instrumentation: wrap resolve_turn_branches, don't reimplement it ---
_orig_resolve_turn_branches = evaluate_mod.resolve_turn_branches
_stats = {"calls": 0, "calls_hit_cap": 0, "decision_hit": False}


def _tracking_resolve_turn_branches(*args, **kwargs):
    leaves, fallback_leaves, fork_records = _orig_resolve_turn_branches(*args, **kwargs)
    _stats["calls"] += 1
    if fallback_leaves > 0:
        _stats["calls_hit_cap"] += 1
        _stats["decision_hit"] = True
    return leaves, fallback_leaves, fork_records


evaluate_mod.resolve_turn_branches = _tracking_resolve_turn_branches


def decide():
    st = copy.deepcopy(BASE_STATE)                    # fresh, off the clock
    oracle = DamageOracle(CALC)                        # fresh per decision (production)
    return heuristic_choose_for_request(
        REQ, state=st, book=BOOK, our_side="p1",
        calc=CALC, oracle=oracle, speed_oracle=SPEED, dex=DEX,
    )


def pct(sorted_ms: list[float], q: float) -> float:
    idx = min(len(sorted_ms) - 1, int(math.ceil(q * len(sorted_ms))) - 1)
    return sorted_ms[idx]


def bench(label: str, env: dict[str, object], n: int = 25, warmup: int = 5):
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = str(v)
    for _ in range(warmup):
        decide()
    ts, choice = [], None
    total_calls = 0
    total_calls_hit = 0
    decisions_with_hit = 0
    for _ in range(n):
        st = copy.deepcopy(BASE_STATE)
        oracle = DamageOracle(CALC)
        _stats["calls"] = 0
        _stats["calls_hit_cap"] = 0
        _stats["decision_hit"] = False
        t0 = time.perf_counter()
        choice = heuristic_choose_for_request(
            REQ, state=st, book=BOOK, our_side="p1",
            calc=CALC, oracle=oracle, speed_oracle=SPEED, dex=DEX,
        )
        ts.append((time.perf_counter() - t0) * 1000.0)
        total_calls += _stats["calls"]
        total_calls_hit += _stats["calls_hit_cap"]
        if _stats["decision_hit"]:
            decisions_with_hit += 1
    ts.sort()
    call_hit_rate = (total_calls_hit / total_calls) if total_calls else 0.0
    decision_hit_rate = decisions_with_hit / n
    return {
        "label": label, "p50": pct(ts, 0.50), "p95": pct(ts, 0.95), "max": ts[-1],
        "choice": choice, "total_calls": total_calls, "call_hit_rate": call_hit_rate,
        "decision_hit_rate": decision_hit_rate,
    }


OFF = {"SHOWDOWN_ACCURACY_MODE": None, "SHOWDOWN_ACCURACY_BRANCH_CAP": None}


def on(cap):
    return {"SHOWDOWN_ACCURACY_MODE": "1", "SHOWDOWN_ACCURACY_BRANCH_CAP": cap}


CONFIGS = [
    ("accuracy=off (baseline)", OFF),
    ("accuracy=on  cap=2", on(2)),
    ("accuracy=on  cap=4", on(4)),
    ("accuracy=on  cap=6", on(6)),
    ("accuracy=on  cap=8", on(8)),
]

print("board: p1 Incineroar+Rillaboom(HeatWave90%) vs p2 FlutterMane+Tornadus(BleakwindStorm80%)")
print("n=25/config, warmup=5 | pin p95<1000ms\n")
print(f"{'config':<26} {'p50':>7} {'p95':>7} {'max':>7}  {'gate':>6}  {'call-hit%':>9}  {'dec-hit%':>8}  {'calls/dec':>9}  choice")
rows = []
for label, env in CONFIGS:
    r = bench(label, env)
    rows.append(r)
    gate = "PASS" if r["p95"] < 1000 else "FAIL"
    calls_per_dec = r["total_calls"] / 25.0
    print(f"{r['label']:<26} {r['p50']:>7.1f} {r['p95']:>7.1f} {r['max']:>7.1f}  {gate:>6}  "
          f"{r['call_hit_rate']*100:>8.1f}%  {r['decision_hit_rate']*100:>7.1f}%  {calls_per_dec:>9.1f}  {r['choice']}")

# --- determinism: accuracy=on cap=4 twice -> identical choice ---
c1 = bench("det-1", on(4), n=3, warmup=1)["choice"]
c2 = bench("det-2", on(4), n=3, warmup=1)["choice"]
print(f"\ndeterminism accuracy=on(cap=4) twice: {'IDENTICAL' if c1 == c2 else 'DIFFER'}  ({c1!r} vs {c2!r})")

# --- off-parity: unset vs explicit SHOWDOWN_ACCURACY_MODE=0 -> identical choice ---
u = bench("unset", OFF, n=3, warmup=1)["choice"]
zero = bench("mode=0", {**OFF, "SHOWDOWN_ACCURACY_MODE": "0"}, n=3, warmup=1)["choice"]
print(f"off-parity unset == mode=0: {'IDENTICAL' if u == zero else 'DIFFER'}  ({u!r} vs {zero!r})")

# --- did accuracy mode change the choice vs baseline on THIS board? ---
base_choice = rows[0]["choice"]
print("\naccuracy=on vs accuracy=off choice on this board:")
for r in rows[1:]:
    print(f"  {r['label']:<20} {'CHANGED' if r['choice'] != base_choice else 'same'}  ({r['choice']})")

try:
    CALC.close()
except Exception:
    pass

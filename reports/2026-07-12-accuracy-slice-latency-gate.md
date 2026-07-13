# Accuracy-branching slice — Task 8 latency micro-bench verdict (local)

**Date:** 2026-07-12 · **Branch:** `feat/slice-accuracy-hit-probability` · **HEAD:** `2ed181a` · **Gate:** Stage-1-equivalent local latency de-risk, mirroring `2026-07-12-2c-depth2-derisk-verdict.md`'s Stage 1 method.

## TL;DR

- **PASS, kept the existing default.** With the production `persistent` calc backend, `SHOWDOWN_ACCURACY_BRANCH_CAP=4` (today's default) measures p95 ≈ 174–181 ms locally across two runs. Scaled ×5 for a heavier Kaggle-weight board (the depth-2 precedent's own scaling rule), that's ≈ 871–905 ms — under the 1000 ms pin, but with a **materially thinner margin (~10–13%) than the depth-2 precedent enjoyed (~27%) at its chosen point.**
- **cap=6 and cap=8 both FAIL the scaled gate** (p95×5 ≈ 1015–1075 ms, over 1000 ms) and buy almost nothing extra: the branch-cap-hit rate is *identical* between cap=6 and cap=8 (6.9% both runs), so cap=8 is strictly worse than cap=6 for this board (same fidelity, more latency). Neither is viable at the 5× multiplier.
- **cap=4 is the largest cap that clears the scaled gate**, matching the plan's instruction to pick the largest value that stays comfortably under 1000 ms. **Default unchanged: `SHOWDOWN_ACCURACY_BRANCH_CAP` stays `4`.** `decision.py` was NOT modified.
- **Non-obvious finding, reported honestly rather than smoothed over:** `branch_cap` is a **global call budget shared across the entire recursive tree**, not a per-path depth limit. On a line with 2 simultaneous accuracy<100 events (this board's actual worst case — Heat Wave 90% vs Bleakwind Storm 80% both firing in the same candidate/response pairing), a *fully* fallback-free resolution needs up to `2^(k+1)-1 = 7` total `resolve_turn` calls, not `2^k = 4`. That's why cap=2 and cap=4 tied at an *identical* 44.0% call-hit-rate in both runs — cap=4 exhausts its whole budget resolving one half of the tree and still falls back on the other half. cap=4 does resolve strictly *more* of the tree per line than cap=2 (confirmed by manual trace of the recursion, not by the coarse hit-rate stat, which can't see partial-tree quality), so it isn't a wasted step, but the raw "hit rate" metric alone understates that.
- Determinism and off-parity both hold (accuracy=on(4) run twice → identical; unset == explicit `SHOWDOWN_ACCURACY_MODE=0` → identical). On this one board, the chosen decision is unchanged by accuracy mode at any tested cap — consistent with the earlier tasks' finding that this machinery is a fidelity/EV-precision improvement, not something expected to flip decisions on every board.

## Method

Mirrors the depth-2 Stage-1 gate (`reports/2026-07-12-2c-depth2-derisk-verdict.md`): persistent real `CalcClient` Node backend (`SHOWDOWN_CALC_BACKEND=persistent`), fresh per-decision `DamageOracle`, one realistic doubles board, timed `heuristic_choose_for_request` across configs, n=25/config after 5 warmups, p50/p95/max in ms, gate p95<1000ms.

**Board** (`scratchpad/bench_accuracy_latency.py`, `make_state()` + the existing `tests/fixtures/request_doubles_moves.json`): p1 Incineroar (Fake Out/Flare Blitz/Protect/Knock Off, all 100% acc) + Rillaboom (Heat Wave **90%**, `allAdjacentFoes` spread /Earth Power/Protect/Solar Beam) vs p2 Flutter Mane (Moonblast/Shadow Ball, both 100%) + Tornadus (Tailwind/Bleakwind Storm **80%**, `allAdjacentFoes` spread). This is the *same* board the depth-2 bench used (`bench_depth2_latency.py`, recovered from this session's own scratchpad temp dir — see Deviations below) — it already happens to carry an accuracy<100 spread move on each side (Heat Wave for p1, Bleakwind Storm for p2), satisfying the plan's board requirement without needing a new fixture.

**Configs:** `SHOWDOWN_ACCURACY_MODE` off (baseline, today's exact always-hit path) vs on × `SHOWDOWN_ACCURACY_BRANCH_CAP` ∈ {2,4,6,8}.

**Branch-cap-hit instrumentation:** a thin monkeypatch of `showdown_bot.battle.evaluate.resolve_turn_branches` that delegates to the real function and increments counters on the returned `fallback_leaves` — no extra `resolve_turn` calls beyond what production already performs, so it doesn't distort timing. Two rates are reported: **call-hit%** (fraction of the ~350 `resolve_turn_branches` invocations per decision — one per candidate×response `evaluate_line` call — where *at least one* leaf in that call's tree hit the cap) and **dec-hit%** (fraction of the 25 sampled top-level decisions with *at least one* such call). dec-hit% saturates at 100% for every `on` config because across ~350 evaluated lines per decision, at least one always has a simultaneous 2-event tree — that's an artifact of sample size per decision, not informative; **call-hit% is the meaningful number.**

## Results

Two independent runs (identical script, ~1 min apart, low system jitter — reported for reproducibility, not because either is more "correct"):

**Run 1:**

| config | p50 (ms) | p95 (ms) | max (ms) | call-hit% | dec-hit% | calls/decision | gate p95<1000 | p95×5 (Kaggle est.) |
|---|---|---|---|---|---|---|---|---|
| accuracy=off (baseline) | 56.7 | 59.2 | 59.2 | 0.0% | 0.0% | 0 | PASS | 296 ms |
| accuracy=on cap=2 | 118.4 | 139.3 | 141.3 | 44.0% | 100.0% | 350 | PASS | 696.5 ms |
| accuracy=on cap=4 | 161.0 | 181.1 | 188.9 | 44.0% | 100.0% | 350 | PASS | 905.5 ms |
| accuracy=on cap=6 | 188.1 | 203.4 | 204.1 | 6.9% | 100.0% | 350 | PASS (local) | **1017 ms — over** |
| accuracy=on cap=8 | 192.9 | 214.4 | 231.9 | 6.9% | 100.0% | 350 | PASS (local) | **1072 ms — over** |

**Run 2** (with `calls/decision` diagnostic added):

| config | p50 (ms) | p95 (ms) | max (ms) | call-hit% | dec-hit% | calls/decision | gate p95<1000 | p95×5 (Kaggle est.) |
|---|---|---|---|---|---|---|---|---|
| accuracy=off (baseline) | 58.5 | 60.6 | 61.1 | 0.0% | 0.0% | 0 | PASS | 303 ms |
| accuracy=on cap=2 | 119.8 | 142.8 | 151.5 | 44.0% | 100.0% | 350 | PASS | 714 ms |
| accuracy=on cap=4 | 160.3 | 174.3 | 179.2 | 44.0% | 100.0% | 350 | PASS | 871.5 ms |
| accuracy=on cap=6 | 187.9 | 211.5 | 212.0 | 6.9% | 100.0% | 350 | PASS (local) | **1057.5 ms — over** |
| accuracy=on cap=8 | 193.5 | 214.9 | 216.8 | 6.9% | 100.0% | 350 | PASS (local) | **1074.5 ms — over** |

- **Determinism:** accuracy=on(cap=4) twice → identical choice ✅
- **Off-parity:** `SHOWDOWN_ACCURACY_MODE` unset == explicit `"0"` → identical choice ✅
- **Decision invariance on this board:** all four caps produce the same choice as accuracy=off. One board, not conclusive evidence the machinery never changes a decision (Task 7's tests already cover cases where it does affect scoring) — just that this particular Protect/Fake-Out-heavy candidate set doesn't flip here.
- **Overhead shape:** accuracy mode's cost over baseline is dominated by the ~350 extra `resolve_turn_branches` calls it does per decision (vs 0 for the off path, which just does one plain `resolve_turn` per line) — the marginal per-cap-step cost (cap=2→4→6→8) shrinks as cap grows (≈+42ms, +30ms, +11ms in run 2), consistent with the call-hit-rate plateauing (44%→44%→6.9%→6.9%) — most of the *additional* forced-hit-cap tree exploration is already captured by cap≈4–6, and pushing the budget further mostly pays for lines that would need `2^4-1=15` calls (a 3rd simultaneous event via KO/redirection cascades) to fully resolve — out of reach of cap=8 too.

## Verdict

- Applying the depth-2 precedent's rule verbatim — "pick the largest value whose p95, scaled ×5 for Kaggle-board weight, stays under the 1000ms pin" — **cap=4 is that value** in both runs (871.5–905.5 ms, i.e. 9.5–12.9% margin). cap=6 and cap=8 both exceed 1000ms at the ×5 estimate in both runs (1015–1075 ms) and are rejected on latency alone, independent of their (mediocre) fidelity payoff.
- The margin at cap=4 (~10–13%) is real but noticeably thinner than the depth-2 precedent's own chosen point (`(N,M)=(4,4)` at 143.0ms local → 715ms scaled, ~28.5% margin). This is worth flagging for whoever eventually runs a Stage-3-equivalent (actual Kaggle) check on this slice: if the true Kaggle multiplier turns out higher than 5× (the depth-2 report itself only estimated 5× from one board's ADR-0004 comparison, it's not a measured constant), cap=4's margin could get tight. Not a blocker today — just a thinner cushion than the pattern this method usually produces.
- **`SHOWDOWN_ACCURACY_BRANCH_CAP`'s default of `4` is confirmed correct by the data and left unchanged.** `showdown_bot/src/showdown_bot/battle/decision.py`'s `_accuracy_branch_cap()` was not modified.

## Deviations from the plan text

1. **Script location for the depth-2 precedent.** The plan said to check `scratchpad/bench_depth2_latency.py` in both this worktree and the main repo checkout — neither had it (scratch files aren't committed; `scratchpad/` isn't a tracked directory in this repo, confirmed via `git log --all` on that path returning nothing). It *was* found, however, in this session's own Claude Code scratchpad temp directory (`...\Temp\claude\...\scratchpad\bench_depth2_latency.py`), apparently left over from the session that produced the depth-2 report. Read in full and reused as the harness template per the plan's own fallback instruction ("if you cannot find the original script anywhere, reconstruct... from the report's own description") — except it *was* found, just not in either of the two locations the plan named, so no reconstruction-from-description was actually needed.
2. **Board reuse instead of new construction.** The plan allowed reusing the depth-2 board-construction helper "if one already exists and is importable." It isn't a standalone importable helper (it's a private `make_state()` inline in the bench script), so it was copied inline rather than imported — same effect. This board already satisfied the "accuracy<100 spread move on each side" requirement (Heat Wave 90% / Bleakwind Storm 80%), so no new fixture was built.
3. **`sys.path` shadowing gotcha (same class of issue as the depth-2 report's Node-spawn gotcha, documented so it doesn't recur):** this worktree's `showdown_bot` package is *not* what `pip`'s editable install resolves to — `pip show showdown-bot` points at the main repo checkout (`C:\Users\chris\Documents\SHowdown BOt\showdown_bot`), so a bare `import showdown_bot` from inside this worktree silently picks up the **other worktree's/main repo's code**, not this branch's `resolve_turn_branches`/`AccuracyDiagnostics` additions. The original depth-2 script already worked around this (`sys.path.insert(0, str(ROOT / "src"))` before import) — carried forward here unchanged, pointed at this worktree's `src/`. Verified explicitly before trusting any measurement (`evaluate_mod.__file__` resolved to the worktree path, and `hasattr(evaluate_mod, "resolve_turn_branches")` was `True` only after the path insert).
4. **`accuracy_branch_cap_hits` isn't surfaced by `heuristic_choose_for_request`.** The plan asked for the observed hit rate "at each cap value," but that field only lives on the per-line `TurnOutcome` returned by `evaluate_line`/`resolve_turn_branches` — `decision.py` doesn't aggregate or expose it up through the public decision entry point. Rather than reimplement `resolve_turn_branches` or reach into private internals more invasively, the bench monkeypatches the function at the module level it's imported into (`evaluate.resolve_turn_branches`) to tap the value it already computes, with negligible (dict-increment) overhead in the timed path.

## Status

Local latency micro-bench complete, both runs agree on the verdict. `SHOWDOWN_ACCURACY_BRANCH_CAP` default (`4`) confirmed by measurement and left unchanged; no `decision.py` diff to commit. A Stage-3-equivalent (real Kaggle-hardware) check of this slice's actual latency multiplier is not part of this task and is not blocking — flagged above as a follow-up worth doing before this margin is trusted at full production load.

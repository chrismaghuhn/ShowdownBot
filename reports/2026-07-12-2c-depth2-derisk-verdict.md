# 2c depth-2 de-risk — Stage 1 + 2 verdict (local ladder)

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-depth2` · **Gate:** de-risk ladder stages 1 (latency) + 2 (offline decision-diff kill-switch). Stage 3 (Kaggle winrate) is deferred to the autonomous-implementer's compute.

## TL;DR

- **Stage 1 (latency): PASS, wide margin.** With the production `persistent` calc backend, depth-2 adds only ~30–90 ms and **+1 Node round-trip** over depth-1. Every tested frontier (N,M) up to (6,5)=258 ms clears the 1000 ms pin. Latency is **not** the constraint. Determinism + off-parity confirmed.
- **Stage 2 (kill-switch): does NOT fire → proceed.** depth-2 **changes the decision in 7/7 field-buckets**, and in the direction the atlas weakness predicts: it **reduces Protect-spam** (`(Protect, Protect)` → aggression). The "depth is moot" hypothesis is refuted.
- **Recommendation:** proceed to **Stage 3** (small Kaggle winrate probe, depth-1 vs depth-2, on 05's archetype-covering panel). Recommended default frontier **(N,M) = (3,3)** (≤(4,4) for Kaggle-CPU margin). Merge the off-by-default machinery to local main now.

## Stage 1 — local latency micro-bench

**Method.** Mirrors the +Sampling gate (`2026-07-12-2c-sampling-latency-gate.md`): persistent real `CalcClient` Node backend (`SHOWDOWN_CALC_BACKEND=persistent`, `spawn_count=1`), fresh per-decision `DamageOracle`, one realistic doubles board (the depth-2 test board: 68 candidates × 5 opponent responses), timed `heuristic_choose_for_request` across `SHOWDOWN_SEARCH_DEPTH∈{1,2}` × frontier `(TOPN, TOPM)`, n=25/config after 5 warmups. Script: `scratchpad/bench_depth2_latency.py`.

| config | p50 (ms) | p95 (ms) | max (ms) | round-trips | gate p95<1000 |
|---|---|---|---|---|---|
| depth=1 (unset baseline) | 59.2 | 60.7 | 61.0 | 2 | PASS |
| depth=2  N=2 M=2 | 86.2 | 105.3 | 107.2 | 3 | PASS |
| depth=2  N=3 M=2 | 101.6 | 111.2 | 113.5 | — | PASS |
| depth=2  N=2 M=3 | 97.4 | 103.7 | 108.5 | — | PASS |
| depth=2  N=3 M=3 | 110.0 | 115.7 | 116.2 | 3 | PASS |
| depth=2  N=4 M=4 | 143.0 | 145.8 | 148.7 | — | PASS |
| depth=2  N=6 M=5 | 236.8 | 257.9 | 259.0 | — | PASS |

- **Determinism:** depth=2 (2,2) twice → identical choice ✅
- **Off-parity:** `SHOWDOWN_SEARCH_DEPTH` unset == depth=1 → identical choice ✅
- **Max affordable (N,M):** not reached — even (6,5) at p95 258 ms leaves ~740 ms headroom. depth-2's cost is **+1 Node round-trip** for the whole turn-2 frontier (the shared-oracle auto-flush batches it), so it scales with Python per-line work, not calc round-trips (unlike +Sampling, which was linear in K).
- **Kaggle margin note:** this board's depth-1 (60 ms) sits *below* the ADR-0004 ~300–470 ms band (a light board / few distinct calcs), so absolute numbers under-represent a heavy board. The transferable finding is the **~1.5–2.5× depth-2 multiplier**. On a 5× heavier Kaggle decision, (4,4)≈730 ms (safe), (6,5)≈1290 ms (over) → recommend **(N,M) ≤ (4,4)**.

### Gotcha (cost me a 35-min hang, documented so it doesn't recur)

`make_calc_backend()` defaults to `SHOWDOWN_CALC_BACKEND="oneshot"`, which spawns a fresh `node calc.mjs` **per flush** (~0.5 s). A latency bench MUST set `persistent` (production/Kaggle mode) or every calc pays a Node startup. The first bench run used the default and spent 35 min blocked on Node spawns before it was killed — a bench artifact, not a depth-2 property.

## Stage 2 — offline decision-diff kill-switch

**Why not the literal Spec-01 diff / the atlas.** There is **no free offline corpus of replayable boards**: the 2b-2.5a dataset and the teacher-disagreement atlas are `{features, label, metadata}` (encoded vectors, not `BattleState`s), and the Spec-01 `decision-diff` compares captured sidecars from *game runs* (needs games). The atlas buckets, however, are **field-defined** (`tailwind_both`, `trick_room`, weather), so we probe them directly: vary `FieldState` on the fixed realistic board and compare depth-1 vs depth-2 (3,3) `chosen_candidate_id`. Script: `scratchpad/stage2_decision_diff.py`.

| bucket | depth-1 | depth-2 (3,3) | diff | protect count |
|---|---|---|---|---|
| neutral | (Protect, Protect) | (Fake Out→1, Solar Beam→2) | CHANGED | 2→0 |
| tailwind_both | (Protect, Protect) | (Fake Out→1, Solar Beam→2) | CHANGED | 2→0 |
| tailwind_p2 (us) | (Protect, Protect) | (Fake Out→1, Solar Beam→2) | CHANGED | 2→0 |
| tailwind_p1 (opp) | (Protect, Protect) | (Flare Blitz→1, Protect) | CHANGED | 2→1 |
| trick_room | (Protect, Protect) | (Flare Blitz→1, Protect) | CHANGED | 2→1 |
| sun | (Protect, Protect) | (Fake Out→1, Solar Beam→2) | CHANGED | 2→0 |
| rain | (Protect, Protect) | (Fake Out→1, Solar Beam→2) | CHANGED | 2→0 |

**Result: 7/7 changed; every change reduces Protect-spam** (2→0 or 2→1), and depth-2 is **field-sensitive** (a different aggressive line under trick_room / opp-tailwind proves the field propagates into the search). The kill-switch (which fires only if depth changes ~nothing) does **not** fire.

**Caveats (do not over-read):**
1. This is **one board's Protect-default, robust across field settings — not 7 independent boards.** The buckets are real (depth-2 responds to the field), but the underlying team is one. A diverse team panel is Stage 3's job (05's archetype-covering wall), not synthesizable here (no free board corpus; only one realistic move-decision fixture exists).
2. **Decision-change ≠ improvement.** Stage 2 is only the necessary condition. Whether de-Protecting actually *wins* is exactly what Stage 3 measures. The atlas says the Protect-spam is a *weakness*, so the direction is encouraging — but that is a hypothesis Stage 3 tests, not a result.

## Verdict & next step

- Stages 1 + 2 are **GO**: depth-2 is affordable and it changes decisions in the hypothesized (de-Protect) direction. Neither cheap local gate kills it.
- **Stage 3 (Kaggle, autonomous-implementer / user compute):** paired winrate probe, baseline depth-1 vs candidate depth-2 at **(N,M)=(3,3)**, analyzed on 05's archetype-covering measurement wall (finally gate-able without the archetype-overfit that voided the last two held-out gates). Held-out is **not** spent by this local ladder.
- The machinery is **off-by-default and byte-identical when off** (full suite 1590 pass; exact-value off-parity), so it is safe to merge to local main ahead of the Stage-3 verdict — same pattern as the +Sampling machinery slice.

## Status

Machinery slice, off-by-default. Local ladder stages 1 + 2 **PASS/GO**. Stage 3 is the only remaining gate and needs games → deferred to the autonomous-implementer (owns the origin push). Not pushed from here.

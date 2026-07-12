# 2c +Sampling machinery — local latency gate

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-sampling` · **Gate:** infrastructure (latency + determinism + off-parity), NOT winrate (per spec)

## Method

Local per-decision micro-benchmark (no battle server; CPU freed after the TCG
training was killed). Real `CalcClient` Node backend (persistent), fresh
per-decision `DamageOracle`. Board: sun_dev-faithful, both active opp mons
**curated-varying** (Flutter Mane + Incineroar) → build_world_dist yields a
2-mon × 2-point dist → **up to 4 distinct worlds**. Timed
`heuristic_choose_for_request` across `SHOWDOWN_WORLD_SAMPLES` K∈{1,2,4,8,16},
n=25/K, after warmup. Script: `scratchpad/bench_kworld_latency.py`.

## Prerequisite (verified separately)

`opp_sets` is keyed by `to_id` (matches the live `opp_sets.get(to_id(species))`
lookup); all 6 curated species have `curated != book_worst_case`; the K-world
branch fires on the dev panel. sun_dev = 4 varying mons, trickroom/rain = 1
(Incineroar). So the gate measures real work.

## Results

| K | p50 | p95 | max | p95 < 1000 ms |
|---|-----|-----|-----|---------------|
| 1 | 324 | 337 | 337 | PASS (baseline; matches ADR-0004 ~300–470 ms) |
| 2 | 377 | 391 | 400 | PASS |
| 4 | 463 | 473 | 484 | PASS |
| 8 | 667 | **716** | 771 | PASS |
| 16 | 1161 | **1341** | 1410 | **FAIL** |

- **Determinism:** K=8 run twice → identical choice ✅
- **Off-parity:** unset == K=1 (byte-identical at /choose) ✅

## Verdict

- **Max affordable K = 8** (p95 716 ms, ~284 ms headroom to the 1000 ms pin).
- **Safe/comfortable K = 4** (p95 473 ms, ~2× headroom) — recommended when
  running on Kaggle's shared CPU, where the margin at K=8 could tighten (local
  K=1 = 337 ms sits in the ADR-0004 ~300–470 ms band, so local ≈ Kaggle; K=8
  local 716 ms → likely <1000 ms on Kaggle but with less margin).

## Key finding (a prior hypothesis was falsified)

**Predicted:** latency plateaus at the number of *distinct* worlds (≤4 here),
because the shared-oracle single-flush dedups identical calcs → K=8/16 ≈ K=4.

**Observed:** latency rises **~linearly in K** (≈ 300 + 65·K ms), NOT plateauing.

**Why:** the shared oracle dedups the **Node calc round-trip** (identical
merged_sets → identical cache keys), but the **per-world Python work is not
deduped** — `predict_responses(opp_sets=merged_sets)` + `DamageModel(...)` +
`evaluate_line(...)`×responses (with `rollout_horizon=2` multi-turn rollout) run
once **per sampled world**, even when many sampled worlds are byte-identical
(K=16 on a 2-varying board evaluates 16 worlds though only 4 are distinct).

**The lever to exceed K=8 (follow-up, NOT this slice):** dedup identical sampled
worlds *before* the eval loop — collapse `sample_worlds` output to distinct
`merged_sets`, summing their weights. For a flat aggregator this is
mathematically identical (byte-identical decision), just faster: latency would
then scale with **distinct** worlds (≤ 2^{#varying active mons}), restoring the
plateau. With that, K=16 on this board would cost ≈ K=4. This belongs in the
+Sampling real-prior slice (or a perf slice), where the chosen K and prior
resolution justify it. Documented here; deliberately out of this machinery
slice's scope.

## Scope / status

Machinery slice, off-by-default, byte-identical when unset (config_hash +
Guard A decision-parity + this off-parity check). Local gate **PASS** at K≤8.
The optional winrate no-regression (dev-strength A/B) is explicitly *not* a GO
criterion for this slice and needs games → deferred to the autonomous-implementer
(owns the origin push). Held-out is **not** spent here.

# 2c Search-Spine — +Sampling machinery (K-world opponent-set sampling) — Design

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-sampling` (off local `main 8cadb3e`) · **Status:** design, user-approved ("passt so")

## Goal

Wrap the existing 1-ply per-candidate evaluation in a loop over **K sampled opponent-set "worlds"**, aggregating each candidate's score across worlds × responses with the existing aggregator — behind an off-by-default env toggle, byte-identical when unset. This is the **machinery** half of the +Sampling axis (`TestBOtpläne/02-decision-engine §3` + `ADR-0004`). It is an **infrastructure slice**, gated on **latency + no-regression + reproducibility**, not winrate. Its core deliverable is the **maximum K that fits the latency budget** (the R2 de-risking). The winrate payoff is deferred to a follow-up slice that authors a real weighted set prior.

## Motivation & honest scope bound

Today `opp_sets` is a **single point estimate** per opponent mon (curated set where available, else a worst-case preset) — `DamageModel(opp_sets=...)` and `predict_responses(opp_sets=...)` both freeze that one assignment. +Sampling replaces the point estimate with **K sampled worlds** and aggregates across them, so the bot hedges its set-uncertainty instead of committing to one guess.

The consumption seam already fits: `DamageModel`/`predict_responses` accept `opp_sets`; `DamageOracle` set-keys its cache (K worlds are automatically correct and can share one calc flush); `aggregate_scores`/`pick_best` already collapse a weighted score vector. **What must be built: the world-sampler + seeded RNG + a set *distribution* to sample from.** This slice uses a **crude distribution assembled from existing data** (curated set + worst-case presets) — deliberately not a real belief. So this slice **proves the machinery and measures latency**; it is not expected to move winrate (a crude distribution is not a good belief). That is by design: latency is the gating unknown and is independent of prior quality.

## Scope

**In:** a `world_sampler` module; the K-world loop wrapping `score_plan` in `_choose_best`; a per-decision seeded RNG (reusing the `seeding.py` sha256 convention); the crude distribution builder over existing data; one env knob; latency measurement at K∈{2,4,8}; tests.
**Out (non-goals):** a real weighted multi-set meta-prior (follow-up data slice); nested CVaR-over-worlds (a semantic refinement — this slice uses the existing flat aggregator); any Bayes/posterior update over sets; adaptive-K (fixed K per run this slice); the winrate gate (deferred to the prior slice); any change to `evaluate_line`, the oracle, or the aggregator.

## Design

### 1. Crude set distribution (`engine/belief/world_sampler.py`, from existing data — no new authoring)

For each revealed opponent mon, build a small weighted list of candidate `SpeciesSpreads`:
- If a curated set exists (`opp_sets[species]` from `likely_sets.yaml`): `[(curated, 0.6), (worst_case_offense, 0.2), (worst_case_defense, 0.2)]`.
- Else (worst-case book only): `[(worst_case_offense, 0.5), (worst_case_defense, 0.5)]`.

`worst_case_offense`/`worst_case_defense` come from the existing `SpreadBook` (`hypotheses.py`, the offense/defense presets). This is a **placeholder distribution** — the follow-up slice replaces it with a real weighted prior; the sampler interface stays the same.

### 2. World sampler (seeded, stratified, deterministic)

```
sample_worlds(per_mon_dist, k, rng) -> list[(world, weight)]
```
- A `world` = a dict `{species_id -> chosen SpeciesSpreads}` (one set per opponent mon).
- **Stratified:** the single most-likely world (every mon's highest-weight set) is **always index 0** (weight = product of per-mon top weights, renormalized). The remaining K−1 worlds are drawn i.i.d. from the per-mon distributions using `rng`.
- `world weight` = product of its per-mon set weights, then all K weights renormalized to sum 1.
- `k == 1` (or toggle off) → return only the most-likely world → **byte-identical to today** (single curated/worst-case set).
- `rng` = `random.Random(seed)` where `seed` is derived **deterministically from the decision state** + `seed_base` via the `eval/seeding.py` sha256 convention — e.g. `sha256(f"{seed_base}:{turn}:{board_key}")`, `board_key` a stable hash of the request/field so the **same decision always samples the same worlds** (`seed_base` from `SHOWDOWN_BATTLE_SEED_BASE`, else a fixed constant). Pure, no global RNG. The exact key is an implementation detail; the invariant is *same decision → same worlds* (not a run-varying stream — `battle_index` is not reliably available inside `_choose_best`).

### 3. K-world loop wrapping `score_plan` (`battle/decision.py`)

Today (decision.py ~294-315): one `DamageModel` + `predict_responses` over the single `opp_sets`, `score_plan` returns a per-response score vector, `pick_best` collapses it. New (only when `SHOWDOWN_WORLD_SAMPLES > 1`):

- Build the K worlds via the sampler.
- For each world `w_k`: build its `predict_responses(opp_sets=w_k)` + `DamageModel(opp_sets=w_k, oracle=shared_oracle)`. **Share ONE `DamageOracle` across all K models**, and call `prefetch` for **all K models before the first `get()`** → a single batched Node round trip for the whole cross-product (the oracle already set-keys, so correctness is automatic and same-set overlap dedupes).
- For each candidate: concatenate its per-world response-score vectors into one length-`Σ_k N_k` vector, with `weights[k,j] = world_weight_k × response_weight_{k,j}`.
- `pick_best(items, mode, weights=flat_weights)` — **unchanged**. The mode is classified once from state (not per world). If the CVaR slice is also present, `SHOWDOWN_NEUTRAL_CVAR=1` makes the aggregator take the CVaR tail across the whole world×response vector (compose-later; not required here).

### 4. Env knob (`eval/config_env.py`, BEHAVIOR_AFFECTING)

| env var | default | effect |
|---|---|---|
| `SHOWDOWN_WORLD_SAMPLES` | `0`/unset → treated as 1 | number of sampled worlds K; ≤1 → single most-likely world (byte-identical); ≥2 → K-world sampling |

Reader mirrors `_must_react_lambda` (private `_world_samples()` clamped to `[1, 32]`). When ≤1, the sampler/loop are not entered → config_hash + `/choose` byte-identical to `main`.

## Invariants

- **INV-off-byte-identical:** `SHOWDOWN_WORLD_SAMPLES` unset/≤1 → byte-identical to `main` (config_hash, `/choose`, results). Proven by a config_hash test + a decision-parity fixture.
- **INV-anytime (INV-3):** the 4 s worker-thread fallback (`choose_with_fallback`) is unchanged; a K-world decision that overruns still falls back to the heuristic/max_damage. No new failure mode.
- **INV-determinism:** the same decision (same `seed_base` + decision state + K) → identical sampled worlds → identical `/choose`. Seeded, no global RNG.
- **INV-ablation (INV-4):** one toggle, default-off; ships (as enabling infra) only after the latency + no-regression gate.

## Gate (infrastructure, not winrate)

Kaggle dev-strength run (`2b4_devstrength_v001`) at K∈{1,2,4,8} via the env-A/B kernel (baseline `{}` vs candidate `{SHOWDOWN_WORLD_SAMPLES:"K"}`):
- **Latency:** p95 **< 1000 ms** (ADR-0004 pin; current ~300-470 ms) — find the **max K** that holds; 4 s wall is the hard fallback, never the target.
- **No-regression:** winrate at the chosen K is not significantly *worse* than baseline (crude distribution → expect ~neutral; a big regression means a bug).
- **Determinism:** byte-reproducible; safety gates clean.
- **NOT a winrate GO** — this slice enables the axis and pins the affordable K; the winrate test comes with the real prior slice. Held-out is **not** spent here.

## Files

- Create `showdown_bot/src/showdown_bot/engine/belief/world_sampler.py` — distribution builder + `sample_worlds`.
- Modify `showdown_bot/src/showdown_bot/battle/decision.py` — the K-world loop around `score_plan` (guarded by `_world_samples() > 1`), shared-oracle prefetch, flat weight assembly.
- Modify `showdown_bot/src/showdown_bot/eval/config_env.py` — classify `SHOWDOWN_WORLD_SAMPLES` BEHAVIOR_AFFECTING.
- Tests: `showdown_bot/tests/test_world_sampler.py` (sampler determinism/stratification/weights), extend `test_config_env.py`, a decision-parity test (K=1 == main), and a K≥2 smoke (correct vector length + weights, no crash) with a fake oracle.

## Testing

- **Sampler:** k=1 → most-likely world only; stratified world always index 0; weights renormalize to 1; same seed → same worlds; different seed → different draws; per-mon dist with/without curated set.
- **Loop (fake DamageModel/oracle, no battles):** K worlds → score vector of length Σ N_k with weights = world×response; K=1 path identical to the single-world path; shared oracle prefetched once.
- **Off-parity:** `SHOWDOWN_WORLD_SAMPLES` unset → decision trace identical to `main` on a fixed fixture.
- **config_env:** classified BEHAVIOR_AFFECTING; config_hash changes when set ≥2, unchanged when unset.

## Risks / notes

- **Latency is the point.** K worlds ≈ K× distinct calcs minus same-set overlap; the shared-oracle single-flush is the mitigation. If K=2 already breaks 1000 ms, that is the finding (→ the prior slice must be coarse / adaptive-K needed) — better to learn it now than after authoring a prior.
- **Crude distribution → no winrate win expected.** The slice's value is latency + machinery + reproducibility. Do not over-read a neutral winrate as failure.
- **Compose-later with CVaR:** flat aggregation over the world×response vector reuses `aggregate_scores` as-is; the CVaR-over-worlds semantics arrive for free once both slices are present (`SHOWDOWN_NEUTRAL_CVAR=1`). Nested CVaR-over-worlds (per-world value then risk over worlds) is a deliberate non-goal here.

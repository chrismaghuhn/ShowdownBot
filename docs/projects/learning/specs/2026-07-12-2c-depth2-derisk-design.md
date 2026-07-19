# 2c Search-Spine — Depth-2 de-risk (cheap approximate 2-ply) — Design

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-depth2` (off local `main f6715c8`) · **Status:** design, awaiting user review

## Goal

Add an **off-by-default, cheap, approximate depth-2 adversarial search** to the 1-ply decision core, to **test whether search depth breaks the 1-ply ceiling** in the depth-bound weakness buckets (the atlas's `tailwind_both` 92%, high-response-entropy — depth-bound + diffuse). This is a **de-risk experiment**, not a production search engine: its deliverable is a **verdict** (does depth help, cheaply measured) before any big forward-sim investment.

## Motivation & honest scope bound

The atlas ([[next-slice-1ply-ceiling]]) concluded the remaining gap is **DEPTH-bound**, not 1-ply-heuristic-fixable. Every external reference (foul-play/poke-engine, PokéChamp, TFM) confirms search+calc is the path — but every off-the-shelf fast forward-sim is **Singles-only**, so a proper Doubles depth-2 would need a fast Doubles forward-sim (a large build). **We deliberately avoid that here.** Instead we build the cheapest thing that is still a *real 2-ply decision* (the turn-2 choice depends on the turn-1 outcome), on the current infra, and use it to *cheaply learn whether depth is even the lever* — before committing to a forward-sim.

The current eval is **1-ply**: `enumerate_my_actions` → `predict_responses` (≤K weighted opponent responses) → `evaluate_line` per (my, opp) line, whose horizon value is a **heuristic fixed-policy `ConditionEngine` rollout** (`rollout.py`: no opponent tree, no state transition, pure ratio arithmetic — invariants I-2/I-6). It is **not** adversarial search and **not** a forward-sim.

## Scope

**In:** an off-by-default `SHOWDOWN_SEARCH_DEPTH` toggle; a **coarse turn-2 state approximation** (apply calc damage + `ConditionEngine` step + faints); a **recursive 1-ply evaluation** at the approximated turn-2 state for the **top-N** turn-1 lines × **top-M** opponent responses; **hard pruning**; **batched calc** via the existing `DamageModel.enqueue`/`oracle.flush()` single-flush; **response-weighted expectimax** backup reusing `aggregate_scores`; latency measurement; tests; the offline decision-diff de-risk harness wiring.

**Out (non-goals):** a real forward-sim (build/extend a fast Doubles sim); full move-effect simulation at turn-2 (only damage + conditions + faints); matrix-maximin search structure (deferred — keep the current aggregation to isolate the depth variable); depth > 2; composition with +Sampling K-world sampling (depth-2 runs on the single most-likely world; `SHOWDOWN_WORLD_SAMPLES` stays 1); any change to the winrate policy default; the winrate gate itself (deferred to stage 3 of the de-risk ladder).

## Design

### 1. Toggle (`eval/config_env.py`, BEHAVIOR_AFFECTING)

| env var | default | effect |
|---|---|---|
| `SHOWDOWN_SEARCH_DEPTH` | `1` | `1` → verbatim 1-ply (byte-identical); `2` → approximate depth-2 for the top-N lines |

Reader mirrors `_world_samples()` (private `_search_depth()` clamped to `{1, 2}`). When `1`, the depth-2 branch is not entered → config_hash + `/choose` byte-identical to `main`.

### 2. The recursive seam (`battle/decision.py::_choose_best`, and `battle/search.py` new)

Today `_choose_best` builds a `score_plan(my_plan) -> list[float]` over the K opponent responses and `pick_best` aggregates. Depth-2 wraps the **leaf value**:

- Compute the 1-ply value for every candidate as now (cheap; already batched).
- Select the **top-N** candidate `my_plan`s by their 1-ply aggregate (N small, e.g. 2–3).
- For each selected `my_plan` and its **top-M** opponent responses (M small, e.g. 2; by response weight): produce an **approximate turn-2 state** (§3), then run a **1-ply decision** on it via the *existing* machinery (`predict_responses` + `DamageModel` + `evaluate_line` + `aggregate_scores`) → the turn-2 aggregate is that leaf's depth-2 value.
- Back the depth-2 leaf values up as the candidate's new score vector; `pick_best(items, mode, weights=resp_weights)` — **unchanged aggregator**, same mode/weights as 1-ply (response-weighted expectimax). Non-selected candidates keep their 1-ply value (they were already worse; depth-2 only *refines the ranking near the top*).
- **All turn-2 calc requests across the selected lines are enqueued into one shared `DamageOracle` and flushed once** (reuse the +Sampling `DamageModel.enqueue` single-flush) → one batched Node round trip for the whole depth-2 frontier.

Put the recursion in a new `battle/search.py` (`depth2_value(...)`) that `_choose_best` calls; keep `_choose_best` readable.

### 3. Coarse turn-2 state approximation (`battle/search.py`) — the load-bearing, honest-limited part

Given the turn-1 `(my_plan, opp_actions)` and the calc damage already computed for that line, produce an approximate next `BattleState`:
- **HP:** subtract the line's calc damage (expected roll) from each hit mon; clamp ≥ 0.
- **Faints:** mark mons at 0 HP fainted; a fainted mon takes no turn-2 action.
- **Conditions/field:** advance via the existing `ConditionEngine.step` (the same engine `rollout.py` uses) — Tailwind/Trick-Room/screen/weather counters decrement, boosts persist, etc.
- **Turn:** `turn += 1`; reset per-turn flags (`moved_since_switch`, protect, Fake-Out eligibility) consistently with how the live loop resets them.

**Honest limitation (a-priori):** this models exactly what calc + `ConditionEngine` model (damage, faints, conditions/modifiers) — **NOT** arbitrary move secondary effects (status, hazards, switches beyond the chosen action, item/ability triggers) at turn-2. This is the "coarse" in coarse-depth-2, and the reason this is a **de-risk**, not production. A false-negative risk (the coarse turn-2 undersells depth) is accepted and called out in stage 2 of the ladder.

### 4. Search structure — response-weighted expectimax at both plies (NOT maximin)

Reuse `aggregate_scores`/`pick_best` recursively (the current NEUTRAL/must_react/AHEAD mode). Rationale: the de-risk isolates **one** variable — depth. Switching to foul-play-style matrix-maximin simultaneously would confound "did depth help?" with "did maximin help?"; and the maximin-vs-mean axis is already explored ([[2c-aggregation-investigation]], a dead end for global scalar tuning). Matrix-maximin-at-depth is a **separate** follow-up if depth-2 shows promise.

## Invariants

- **INV-off-byte-identical:** `SHOWDOWN_SEARCH_DEPTH` unset/1 → byte-identical to `main` (config_hash, `/choose`). config_hash test + a decision-parity fixture.
- **INV-anytime (INV-3):** the 4 s worker-thread fallback (`choose_with_fallback`) is unchanged; a depth-2 decision that overruns still falls back to the 1-ply/heuristic path. No new failure mode.
- **INV-determinism:** same state + `SHOWDOWN_SEARCH_DEPTH=2` → identical `/choose` (deterministic pruning + seeded/no-RNG transition + shared-oracle set-keyed cache).
- **INV-orthogonal:** depth-2 does not touch the +Sampling K-world path; with `SHOWDOWN_WORLD_SAMPLES=1` (default) depth-2 runs on the single most-likely world.

## De-risk ladder (the whole point — cheap verdict before compute)

1. **Build** depth-2 off-by-default + a **latency gate** (Kaggle env-A/B `SHOWDOWN_SEARCH_DEPTH∈{1,2}` on `2b4_devstrength`, or a local micro-bench like the +Sampling gate): p95 < 1000 ms; find the max affordable (N, M) pruning; prove byte-identical-off.
2. **Offline decision-diff** (reuse Spec-01 `decision-diff` + the disagreement atlas): does depth-2 **change decisions** in the depth-bound buckets (`tailwind_both` etc.) vs 1-ply? **If it changes ~nothing there → depth is moot here → STOP, ~0 Kaggle cost.** (This is the cheap kill-switch.)
3. **Only if it changes decisions:** a small **Kaggle winrate probe** (baseline depth-1 vs candidate depth-2) on **05's archetype-covering measurement wall** — now finally gate-able without the archetype-overfit that voided the last 2 held-out gates.

## Files

- Create `showdown_bot/src/showdown_bot/battle/search.py` — `depth2_value(...)` + the turn-2 state approximation.
- Modify `showdown_bot/src/showdown_bot/battle/decision.py` — the top-N/top-M depth-2 wrap in `_choose_best` (guarded by `_search_depth() > 1`), shared-oracle single-flush.
- Modify `showdown_bot/src/showdown_bot/eval/config_env.py` — classify `SHOWDOWN_SEARCH_DEPTH` BEHAVIOR_AFFECTING.
- Tests: `test_search_depth2.py` (transition approximation correctness; top-N/top-M frontier + single-flush with a fake oracle; recursion backup = expectimax; a depth-1==unset parity fixture), extend `test_config_env.py`.

## Testing

- **Transition:** damage subtracted + faints marked + `ConditionEngine.step` applied + turn advanced; produces a valid `BattleState` a 1-ply decision accepts.
- **Frontier/pruning:** only top-N candidates × top-M responses expanded; all turn-2 calc enqueued once, flushed once (fake oracle asserts a single flush).
- **Backup:** depth-2 leaf values aggregate via the same `aggregate_scores` as 1-ply; ranking near the top can change, non-selected candidates unchanged.
- **Off-parity:** `SHOWDOWN_SEARCH_DEPTH` unset → decision trace identical to `main` on a fixed fixture; config_hash unchanged when unset, changes when 2.
- **Anytime:** a depth-2 overrun still falls back (INV-3 unchanged).

## Risks / notes

- **Coarse-transition false-negative:** the turn-2 approximation (damage+conditions only) may undersell depth → a neutral stage-2/stage-3 result could be the *approximation's* fault, not depth's. Mitigation: stage 2 measures *decision change* (a necessary condition) cheaply; if depth-2 changes decisions but doesn't win (stage 3), that's a fair signal the coarse depth-2 isn't enough → then (and only then) the fast-forward-sim investment is justified. Either way we learn something real, cheaply.
- **Latency:** depth-2 ≈ N×M extra 1-ply evaluations; the single-flush batches the calc, but the Python per-line work (`predict_responses`/`evaluate_line`) is the cost (per the +Sampling linear-in-K finding). Hard pruning (small N, M) + measuring the max affordable frontier is the mitigation; if even (2,2) breaks 1000 ms, that is the finding.
- **Compose-later:** depth-2 × +Sampling (search over K sampled worlds) is a deliberate non-goal here; both are off-by-default and orthogonal, so they compose later without rework.

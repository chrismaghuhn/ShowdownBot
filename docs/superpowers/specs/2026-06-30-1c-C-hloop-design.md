# Phase 3 Slice 1c-C: H-loop teacher wiring — Design

**Goal:** Bind the 1a teacher's injectable `decide`/`resolve`/`leaf` to the real
simulator (1c-A `apply_outcome_to_state` + 1c-B `decide`) and drive
`counterfactual_value` + `label_decision` over a captured decision — producing the REAL
silver labels that replace `stub-h0`.

**Status:** brainstorming, 2026-06-30, branch `phase3-1c-simulator-teacher`. Baseline: 1c-A
(`apply_outcome_to_state`) + 1c-B (`decide`, `synthesize_request`, `_choose_best_ja`) done,
353 green. Defer the opponent belief source + limited-view to 1c-D.

## Binding (Q1) — three adapters fed to `counterfactual_value`
The teacher (1a) is `counterfactual_value(start_state, candidate, responses, *, decide,
resolve, leaf, cfg)`, with `decide(state, "us"|"them")`, `resolve(state, our_action,
opp_action) -> (next_state, reward)`, `leaf(state) -> float`. 1c-C provides:

| adapter | wiring |
|---|---|
| `resolve(state, our_ja, opp_ja)` | plan both sides → `DamageModel(state)` → `resolve_turn` → `outcome` → `next = apply_outcome_to_state(state, outcome, {us:our_ja, them:opp_ja}, roster_by_side)` (1c-A) → `reward = score_outcome(outcome, our_side)` (incremental). Returns `(next, reward)`. |
| `decide(state, "us"/"them")` | maps the token → concrete side → 1c-B `decide(state, side, roster=…, movesets=…, stats=…, move_meta=…, deps=…)`. **Clones the state internally** (see Determinism). |
| `leaf(state)` | the one-ply aggregate from our perspective: `synthesize_request(state, our_side, …)` → the decision core → `best_val` (the pick_best aggregate score). |

### Perspective + side mapping (pinned)
- **All rewards and leaf values are from the ORIGINAL labeled decision side's
  perspective** (`root_our_side`), NOT from the side currently deciding. In follow-up
  turns `"them"` also decides, but `score_outcome`/`leaf` are always evaluated from
  `root_our_side` — otherwise the sign flips with the active side.
- **Static token map** (fixed for the whole rollout, never derived from `state`):
  `side_for = {"us": root_our_side, "them": opponent_of(root_our_side)}`. `"us"` is
  always the side of the original decision.

## Candidate injection (Q3) + follow-ups (Q4) — consume the 1b `DecisionTrace`
The 1b `DecisionTrace` already captures exactly what the teacher needs: `candidates[].
joint_action` = the top-K **fixed turn-0 actions**; `opponent_responses` + `weights` = the
candidate-independent response set `R`. 1c-C consumes a captured `(trace, state)`:
- candidates = `trace.candidates[].joint_action` (top-K).
- `R` = `[(r.actions, r.weight) for r in trace.opponent_responses/weights]`. **Pinned:**
  if `trace.opponent_response_weights` is empty, use **uniform** weights; weights are
  **normalized once** (sum to 1) before `counterfactual_value`; the order of `R` is stable
  and matches `candidate.score_vector`'s response order from 1b.
- For each candidate: `cfv = counterfactual_value(state, candidate, R, decide, resolve, leaf,
  cfg)`. Turns 1..H use `decide` for BOTH sides.
- `label_decision({cand_id: cfv}, heuristic_values, chosen)` → the real label, replacing
  `stub-h0` (`teacher_version` becomes the real H-loop teacher; `trainable_label: true`).

## Leaf core extension (no duplication)
1c-B's `_choose_best_ja(req,...) -> JointAction` is extended to `_choose_best(req,...) ->
(JointAction, float)` returning `(best_ja, best_val)` (the existing `pick_best` already
yields both). `decide`/the public wrapper take `[0]`; `leaf` takes `[1]`. Behavior-
preserving (the equivalence test still gates it). NO second evaluation path — the teacher
bootstraps with the **same** value the bot scores with.

**Pinned:** `best_val` is the **exact scalar `pick_best` used to choose `best_ja`** — not
recomputed, not from the trace, not rebuilt from `score_vector`. Tests: `_choose_best(req)[0]
== _choose_best_ja(req)` (or the wrapper still encodes the same choice); `heuristic_choose_for_request`
output unchanged; `leaf_value(state, side, …) == _choose_best(req)[1]`.

## Budget (Q2)
`RolloutConfig(H=4, gamma=0.75, top_k=6, use_leaf=True)` (from 1a). `|R|` comes from the
trace (small). Decision-level sampling reuses 1b's `SamplingPolicy`. **Strictly offline** —
a fresh `DamageModel` per `resolve`/`decide`/`leaf` is correct and acceptable (no live
latency; only offline compute, bounded by sampling + H/top_k). Optimization (model caching
per rollout state) is deferred, not required for v1.

## roster/movesets/stats (Q5) + deferred (Q6)
`resolve`/`decide`/`leaf` are parameterized by `roster_by_side`/`movesets_by_side`/
`stats_by_side` (the 1c-B/1c-A inputs). **Our** side = known (the real request/team). **The
opponent's** roster/movesets/stats = belief — **deferred to 1c-D** (likely_sets/curated).
For 1c-C, the caller/tests pass them in (a fake opp belief for tests). 1c-C never reads a
hidden opponent bench/set from the state (inherited from 1c-B's no-hidden-read guard).

## Determinism + no mutation (Q7) — the central safety property
- **`apply_outcome_to_state` is immutable** (1c-A clones, returns a new state). Every
  candidate×response branch starts from the SAME `start_state` and clones forward → no
  cross-branch contamination.
- **Finding (must fix): `decide` currently mutates.** `_choose_best_ja` calls
  `apply_own_team_knowledge(state, …)` + dex type-enrichment, both of which **mutate** the
  passed state. In the rollout `decide(state,"us")` then `decide(state,"them")` would corrupt
  the shared state → non-determinism. **Fix:** the `decide` adapter **clones the state
  internally** before the core, so the rollout state is never mutated by a decision.
- **Deterministic calc:** `damage_fn` uses a fixed roll (min/max, not random); the heuristic
  is deterministic; no RNG in the rollout. ⇒ identical `(trace, state, rosters, cfg)` ⇒
  identical labels.
- **Tests:** (a) same inputs → same `counterfactual_value`/labels (determinism); (b) the
  `start_state` is byte-unchanged after a full rollout (no mutation); (c) two candidates'
  rollouts don't affect each other; (d) **H=0 end-to-end math:**
  `counterfactual_value(start, candidate, R, cfg=RolloutConfig(H=0, use_leaf=False))
  == weighted mean over R of resolve(start, candidate, response).reward` — the primary
  whole-pipeline sanity test; (e) the `decide`-clone guard (from 1c-C0): a full rollout
  leaves the input state's items/types unmutated.

## Decomposition (the plan will cut it)
- **1c-C0 (two prerequisite patches, both gated):** (a) extend the core to `_choose_best`
  returning `(best_ja, best_val)` (behavior-preserving; equivalence gate) + `leaf_value(state,
  side, …)`; (b) **patch `decide_adapter.decide` to `clone_state(state)` before the decision
  core** (technically a 1c-B fix, but a hard prerequisite — without it the H-loop is not
  trustworthy). Test: `decide(state, side, …)` leaves `state` byte-identical (items/types
  unmutated).
- **1c-C1:** the `resolve` adapter (plan + DamageModel + resolve_turn + apply + score_outcome).
- **1c-C2:** the `decide` adapter (token→side, **internal clone**) + the `make_*` wiring.
- **1c-C3:** the driver — consume `(trace, state)` → `counterfactual_value` per candidate →
  `label_decision`; determinism + no-mutation + H=0 sanity tests.

## Non-goals (hard)
No opponent belief source / limited-view (1c-D), no model, no training, no reranker, no
export wiring (a later slice swaps the stub teacher in the 1b export for the real one).

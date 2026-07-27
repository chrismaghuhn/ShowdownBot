# Stage-3 Readiness: Accuracy-Configuration Consistency Across Coarse Depth-2 Evaluation

**Date:** 2026-07-27

**Status:** DRAFT — design approved in conversation; written specification awaiting owner review

**Project:** Learning / search

**Scope:** compatibility, observability, and cost evidence only

## 1. Decision

Make the existing off-by-default coarse Depth-2 path use the same resolved accuracy
configuration at both plies, in both the non-Mega and Mega scoring paths, without changing the
search algorithm, frontier policy, state transition, defaults, or fallback chain.

The slice also makes the executed method observable in a new exact-closed live decision-profile
schema. The resulting artifact must distinguish Turn-1 from Turn-2 accuracy work, requested from
executed search frontier, accuracy cap fallback from decision fallback, and clean completion from
timeout or degradation.

This slice does **not** claim that Depth-2 is stronger. It establishes a necessary and measurable
precondition for a later diverse-development-panel comparison.

## 2. Verified current state

The following facts were re-checked against `main` at `cc38908` before this specification was
written:

1. `battle/decision.py::_choose_best` resolves `_accuracy_mode()` and
   `_accuracy_branch_cap()` exactly once per scored decision and stores the results in local
   immutable Python scalars.
2. Those resolved values already reach the normal 1-ply, Tera, own-Mega, and foe-Mega scoring
   paths.
3. The two Depth-2 adapters deliberately omit them:
   - `battle/decision.py` builds `d2_eval_kwargs` without `accuracy_mode` or
     `accuracy_branch_cap`;
   - `battle/mega_scoring.py` does the same for the Mega grid.
4. Consequently, with the production defaults (`accuracy_mode=True`, cap `6`) and
   `SHOWDOWN_SEARCH_DEPTH=2`, unrefined slots use probability-weighted accuracy scoring while
   refined slots are replaced by Turn-2 values produced with `evaluate_line`'s legacy
   `accuracy_mode=False` default.
5. The omission is an explicitly recorded sequencing gap, not an unexplained regression:
   accuracy integration excluded Depth-2, and accuracy was made default-on later.
6. The existing coarse successor is deliberately limited to a deep copy, HP subtraction,
   faint marking, and `turn += 1`. Field booleans persist. It does not run a full simulator.
7. When accuracy is enabled, `evaluate_line` returns a probability-weighted score but exposes one
   deterministic `representative_outcome`; the current Depth-2 bridge builds its successor from
   that one outcome.
8. The current backup replaces selected response-vector slots with a Turn-2 aggregate. It is not
   a cumulative two-turn return.
9. The focused current tests are green (`tests/test_search_depth2.py` and
   `tests/test_accuracy_mode_wiring.py`: 12 passed), but their documented scope excludes the
   Accuracy × Depth-2 composition.
10. `decision-trace-v3` and `decision-profile-v3` are exact-closed schemas. Adding unknown
    telemetry fields without a versioned contract would correctly fail validation.

When older prose conflicts with these facts, the production path, corrected implementation plan,
Git history, and current tests govern this slice. In particular, the original Depth-2 design's
stronger description of condition advancement is not silently reinstated here.

## 3. Goal and success condition

For one scored decision call, every 1-ply and Turn-2 evaluation must receive the exact same
resolved accuracy mode and branch cap. This includes base actions, Tera overlays, own-Mega
contexts, foe-Mega contexts, and role-reversed Turn-2 candidate evaluation.

The slice succeeds only if:

- the inconsistency is mechanically reproduced before the change;
- both Depth-2 call paths forward the same resolved values after the change;
- Depth-1 and explicit accuracy-off control paths retain their deterministic decision projection;
- the representative Turn-1 leaf and coarse successor semantics do not change;
- no extra Turn-1 accuracy leaf is expanded into Turn 2;
- persisted telemetry proves which method ran and whether either ply hit the accuracy branch cap;
- focused and full verification pass;
- a reproducible cost preflight reports Accuracy-off/on and cold/warm strata without inventing a
  new latency threshold.

## 4. Scope

### 4.1 In scope

- Pin the existing once-per-decision accuracy resolution as an enforced invariant.
- Forward `accuracy_mode` and `accuracy_branch_cap` through:
  - the non-Mega `decision.py -> search.py` Depth-2 path;
  - the Mega `mega_scoring.py -> search.py` Depth-2 path.
- Add optional in-memory, at-origin work counters for the actual scoring calls.
- Persist the counters and effective configuration in `decision-profile-v4`.
- Preserve read support and exact validation for frozen decision-profile v1-v3 rows.
- Add focused equality, forwarding, non-expansion, schema, and semantic-validator tests.
- Run a fixed-host, persistent-backend cost preflight at `(N, M) = (3, 3)`, split by
  Accuracy-off/on and cold/warm cache class.
- Write a closeout report containing results and explicit non-claims.

### 4.2 Out of scope

- Enabling Depth-2 by default.
- Changing `SHOWDOWN_SEARCH_TOPN`, `SHOWDOWN_SEARCH_TOPM`, or their defaults.
- Changing the accuracy branch cap, its deterministic cap fallback, or the pinned cap `6`.
- Expanding every Turn-1 hit/miss leaf into Turn 2.
- Computing a cumulative Turn-1 + Turn-2 value.
- Replacing the coarse successor with a full Doubles simulator.
- Changing field persistence, switch modeling, secondaries, items, abilities, or per-turn flags.
- Combining Depth-2 with K-world sampling.
- Changing `aggregate_scores`, risk lambdas, response weights, tie breaking, or candidate order.
- Changing timeout behavior, fallback selection, degradation classification, or chooser behavior.
- Wiring the standalone `AccuracyDiagnostics` derived metrics into live decision making.
- Building or running the diverse development panel.
- Any held-out run, ledger entry, Strength claim, or production-default decision.
- The separate live-runner degradation-recording slice in `client/runner.py`.

## 5. Terminology and non-claim

The method after this slice is:

> **Accuracy-aware coarse Depth-2 evaluation; not a two-turn expectiminimax or full
> probabilistic rollout.**

Specifically:

- Turn 1 is probability-weighted for candidate scoring.
- A refined Turn-2 evaluation starts from the same single deterministic representative Turn-1
  outcome used today.
- Turn 2 becomes probability-weighted under the same accuracy configuration as Turn 1.
- The search does not integrate the Turn-2 value across every Turn-1 hit/miss successor.
- The existing selected-slot replacement backup remains unchanged and is not re-described as a
  conventional cumulative search return.

Any report or roadmap update from this slice must use this limited description.

## 6. Architecture

### 6.1 One resolved accuracy configuration per decision

`_choose_best` remains the sole resolution point:

```text
_accuracy_mode()       -> accuracy_mode
_accuracy_branch_cap() -> accuracy_branch_cap
```

No downstream normal, Tera, Mega, or Turn-2 function may:

- re-read either environment variable;
- recompute a default;
- normalize the values again; or
- substitute its function default for an omitted argument.

The current pair of local bool/int values is sufficient. A new configuration object is not
introduced merely for ceremony. Tests will prove that each resolver is called once and that all
downstream spies receive equal values by identity/value as applicable.

### 6.2 Non-Mega data flow

```text
_choose_best
  resolve accuracy once
  evaluate all 1-ply candidate/response lines with that configuration
  rank by existing 1-ply aggregate
  select existing top-N candidates and top-M response slots
  for each selected slot:
    keep the existing representative Turn-1 outcome
    derive the existing coarse successor inputs
    call depth2_value with d2_eval_kwargs containing the same accuracy values
  replace the same selected score-vector slots
  call the unchanged pick_best
```

`search.py::_score_turn2_plans` already passes `eval_kwargs` to `evaluate_line`. The compatibility
change must use this seam; it must not add a second environment reader or a parallel evaluator.

### 6.3 Mega data flow

`mega_scoring.py::score_evaluated_variants` follows the same rule. Its existing
`accuracy_mode`/`accuracy_branch_cap` parameters are the authoritative values received from
`_choose_best`. The function adds those exact values to its `d2_eval_kwargs` before calling
`depth2_value_for_mega_context`.

Every existing context-binding invariant stays load-bearing:

- each refined response index uses its own bound Mega evaluation context;
- no response is rebound to another own-Mega or foe-Mega context;
- no zero-weight response is reintroduced;
- the global top-N and per-record top-M selection stay unchanged.

### 6.4 Representative-leaf pin

The slice does not alter how `LineEvaluation.representative_outcome` is chosen. A focused
counterproof must construct multiple Turn-1 accuracy leaves and demonstrate:

- the same deterministic representative outcome is used before and after the compatibility
  change;
- exactly one successor per selected `(candidate, response slot)` reaches `depth2_value`;
- Depth-2 call count remains bounded by the existing frontier, never multiplied by the number of
  Turn-1 accuracy leaves.

### 6.5 Optional at-origin telemetry

Add a dedicated optional in-memory `Depth2ReadinessCounts`-style sink rather than overloading
`DecisionTrace` or inferring work after the fact. The exact name may change in the implementation
plan, but its ownership and semantics are fixed here.

It is allocated only when the existing decision-profile writer is enabled. With no sink:

- no telemetry object is allocated;
- no counter is incremented;
- no serialization occurs;
- the returned action and deterministic decision projection remain unchanged.

The sink records work where it actually happens:

| Quantity | Source of truth |
|---|---|
| effective search depth | once-resolved decision setting |
| requested top-N/top-M | once-resolved frontier settings |
| selected candidate count | actual frontier selection |
| eligible response-slot count | actual response arrays after weighting/filtering |
| evaluated Depth-2 slots | immediately before each real Depth-2 refinement |
| effective accuracy mode/cap | the once-resolved decision values |
| Turn-1 evaluated accuracy leaves | sum of `TieOrderEvaluation.accuracy_leaf_count` returned by actual 1-ply scoring calls |
| Turn-2 evaluated accuracy leaves | the same sum returned by actual `_score_turn2_plans` scoring calls |
| Turn-1 / Turn-2 cap hits | `LineEvaluation.fallback_leaves` from the corresponding actual scoring calls |
| deterministic cap fallback used | derived and validated as `cap_hits > 0` per ply |

The optional evaluation sink must be passed only to real scoring calls. Trace-only diagnostic
recomputation must not increment it, or the exported counts would describe observation overhead
rather than the method that selected the action.

Timeout, decision fallback, and degradation reason remain authoritative in the existing
`SelectionStageSink` and outcome classifier. The profile builder joins those signals with the
readiness counts; it does not invent a second fallback vocabulary.

## 7. Persisted telemetry contract

### 7.1 Why a new schema version is required

`decision-profile-v3` is exact-closed and backs frozen evidence. It must not be mutated or
reinterpreted. New writes made by the updated writer use `decision-profile-v4`; validators retain
version-specific support for v1-v3 byte contracts.

No frozen artifact is rewritten.

### 7.2 New v4 fields

In addition to the existing live profile fields, v4 contains exact-validated fields equivalent to:

| Field | Type | Rule |
|---|---|---|
| `search_depth` | int | exactly `1` or `2` |
| `search_topn_requested` | int | positive resolved parser output, even when Depth-2 is not executed |
| `search_topm_requested` | int | positive resolved parser output, even when Depth-2 is not executed |
| `depth2_candidates_selected` | int | non-negative |
| `depth2_response_slots_eligible` | int | non-negative |
| `accuracy_mode` | bool | strict bool, never int |
| `accuracy_branch_cap` | int | positive |
| `turn1_accuracy_leaf_count` | int | non-negative; zero when Accuracy mode is off |
| `turn1_accuracy_cap_hits` | int | non-negative |
| `turn1_accuracy_cap_fallback` | bool | equals `turn1_accuracy_cap_hits > 0` |
| `turn2_accuracy_leaf_count` | int | non-negative; zero when Accuracy mode is off |
| `turn2_accuracy_cap_hits` | int | non-negative |
| `turn2_accuracy_cap_fallback` | bool | equals `turn2_accuracy_cap_hits > 0` |
| `selection_stage` | string or null | existing stage vocabulary only |
| `fallback_reason` | string or null | existing reason vocabulary only |

The existing `depth2_frontier` field remains the actual number of evaluated Depth-2 response
slots and must equal the at-origin readiness count.

### 7.3 Cross-field invariants

The v4 semantic validator fails closed unless:

- `search_depth == 1` implies:
  - `depth2_candidates_selected == 0`;
  - `depth2_frontier == 0`;
  - both Turn-2 accuracy counts are zero and `turn2_accuracy_cap_fallback` is false;
- `search_depth == 2` with active K-world sampling (`n_worlds > 1`) still implies zero
  Depth-2 work;
- `depth2_frontier <= depth2_response_slots_eligible`;
- `depth2_candidates_selected <= search_topn_requested`;
- `depth2_frontier <= depth2_candidates_selected * search_topm_requested`;
- `accuracy_mode is False` implies all accuracy leaf and cap-hit counters are zero;
- a positive cap-hit count implies the corresponding cap-fallback boolean is true and vice versa;
- Turn-2 accuracy counts are zero and `turn2_accuracy_cap_fallback` is false when no Depth-2
  slot was evaluated;
- `outcome`, `selection_stage`, and `fallback_reason` remain mutually consistent under the
  existing fallback/degradation classifier;
- all counters use strict integer checks that reject booleans, negatives, NaN-like foreign
  values, and unknown fields.

The validator may add tighter mechanically derivable bounds during implementation-plan review,
but it may not weaken these rules.

### 7.4 Why DecisionTrace is not expanded here

The review requested DecisionTrace **or** export visibility. DecisionProfile is the selected
export because it already carries per-decision identity, latency, calc work, frontier shape, and
outcome. Duplicating the same run telemetry into `decision-trace-v3` would require a second schema
migration and create two sources of truth.

Candidate-level accuracy research details remain in DecisionTrace. Method-execution and cost
telemetry live in DecisionProfile v4.

## 8. Equality contracts

“Byte-identical” in this slice means equality of the deterministic decision projection, not
equality of wall-clock or newly versioned telemetry bytes.

### 8.1 Depth-1 control

With `SHOWDOWN_SEARCH_DEPTH` unset or `1`, before-versus-after comparison must preserve:

- enumerated legal joint actions;
- candidate order and stable keys;
- opponent-response order and weights;
- per-response candidate score vectors;
- aggregate scores;
- selected candidate and encoded `/choose`;
- tie-breaking result;
- deterministic DecisionTrace decision fields;
- selection stage, fallback reason, and degradation classification.

Timing and DecisionProfile schema bytes are excluded: v4 intentionally adds telemetry and
wall-clock values are not deterministic.

### 8.2 Accuracy-off Depth-2 control

With `SHOWDOWN_SEARCH_DEPTH=2` and explicit `SHOWDOWN_ACCURACY_MODE=0`, the same projection must
match the pre-slice Depth-2 behavior:

- identical frontier selection;
- identical coarse successor inputs;
- identical refined score-vector slots;
- identical final candidate order, aggregate scores, and choice;
- identical fallback/degradation classification.

Passing explicit `False`/cap values through `eval_kwargs` must not change
`evaluate_line`'s legacy accuracy-off behavior.

## 9. Error and fallback behavior

- No new exception handler is added to scoring.
- No exception is swallowed to make a profile appear clean.
- The existing four-second heuristic timeout and fallback chain are unchanged.
- Accuracy branch-cap fallback remains deterministic and separate from chooser fallback.
- In-memory telemetry updates perform no file I/O and no environment reads.
- Profile serialization remains after the measured decision and successful send, following the
  current client discipline.
- With profiling disabled, the compatibility code performs only the two additional keyword
  forwards required for Turn-2 scoring.
- With profiling enabled, malformed or inconsistent telemetry fails the measurement run closed;
  it must not silently drop a field or coerce a type.
- Any timeout, client exception, non-heuristic selection stage, degraded state, or cap fallback is
  reported in its own field. A cap fallback must never be presented as a fully enumerated
  accuracy result; the later panel gate must pre-register how it is classified.

## 10. Test design

Tests are written red before implementation.

### 10.1 Configuration and forwarding

1. Patch both accuracy resolvers with call-count spies; one scored decision calls each exactly
   once.
2. Non-Mega Depth-2: a `depth2_value` spy receives the exact resolved mode/cap in
   `eval_kwargs` for every refined slot.
3. Mega Depth-2: `depth2_value_for_mega_context` receives the same values for base, own-Mega, and
   foe-Mega-bound refined slots.
4. Downstream functions contain no new accuracy environment reads.

### 10.2 Behavioral counterproofs

1. A controlled low-accuracy Turn-2 move produces a different refined value between
   Accuracy-off and Accuracy-on, proving the parameter is consumed rather than merely forwarded.
2. Depth-1 deterministic projection matches the pre-slice golden.
3. Accuracy-off Depth-2 deterministic projection matches the pre-slice golden, including
   frontier, score vectors, aggregates, and chosen action.
4. Multiple Turn-1 leaves still produce one Depth-2 successor per selected response slot.
5. K-world active suppresses Depth-2 exactly as before.
6. Zero-weight Mega responses remain excluded.
7. Candidate/context binding and first-wins tie behavior remain unchanged.

### 10.3 Telemetry and schema

1. Turn-1 and Turn-2 leaf/cap counts increment only at their real scoring call sites.
2. Trace recomputation does not alter counts.
3. Requested and actual frontier counters match both non-Mega and Mega execution.
4. Profiling off allocates no readiness sink and changes no deterministic decision field.
5. Profile v4 exact-field validation rejects missing and unknown fields.
6. Every cross-field invariant in §7.3 receives a mutation-style negative test.
7. Existing v1-v3 frozen fixtures remain readable under their original field sets.
8. Selection stage, timeout/fallback reason, and degradation outcome join correctly.

### 10.4 Verification commands

The implementation plan must name the exact focused test files. Final verification includes:

- all new focused tests;
- existing Search, Accuracy, Mega, decision-profile, gauntlet-dispatch, and degradation tests;
- the full `showdown_bot` test suite;
- generator/freshness checks for any changed generated contract;
- `git diff --check`.

No success claim may quote only the focused suite.

## 11. Cost preflight

### 11.1 Matrix

Use the fixed Windows measurement host and persistent calc backend. Run the same positions and
seeds across:

| Search | Accuracy | Frontier |
|---|---|---|
| Depth 1 | off | not applicable |
| Depth 1 | on, cap 6 | not applicable |
| Depth 2 | off | `(3, 3)` |
| Depth 2 | on, cap 6 | `(3, 3)` |

Each arm reports cold and warm cache strata separately. Reuse the existing reproducible profile
harness/manifest conventions; do not rely on a scratch-only one-off script for the final evidence.

### 11.2 Required outputs

For every arm and cache stratum report:

- repetitions and valid-row count;
- p50, p95, and maximum measured latency;
- timeout count;
- chooser-fallback and degradation count;
- Turn-1 and Turn-2 accuracy leaf counts;
- Turn-1 and Turn-2 cap-hit counts;
- deterministic cap-fallback count;
- requested and actual Depth-2 frontier;
- calc transport calls, attempts, spawns, total/unique requests, and cache hits per decision;
- environment/provenance identity already required by the profile harness.

### 11.3 Interpretation

- Cold and warm rows are never pooled.
- Accuracy-off/on comparisons are descriptive cost evidence only.
- The existing 1000-ms **live** budget is unchanged, but it is not reinterpreted as a per-arm
  microprofile threshold.
- No new latency threshold is invented in this slice.
- Any timeout, degradation, malformed row, missing telemetry, or profile-schema violation makes
  the preflight invalid rather than a pass.
- A later behavior-changing candidate still requires the applicable live latency gate before any
  Strength run.

## 12. Delivery sequence

1. Add failing Accuracy × Depth-2 forwarding and consumption tests.
2. Pin once-per-decision resolution with call-count tests.
3. Forward the resolved values through the non-Mega Depth-2 seam.
4. Forward them through the Mega Depth-2 seam.
5. Add failing at-origin telemetry tests.
6. Add the optional in-memory readiness sink without persistence.
7. Add decision-profile-v4 fields, versioned validators, and backward-compatibility tests.
8. Join existing stage/fallback/outcome signals into v4.
9. Run focused verification.
10. Run the full suite and `git diff --check`.
11. Run and freeze the cost preflight.
12. Write the closeout report and reconcile Roadmap/Project Index without making a Strength claim.
13. Only afterward design the separate diverse development panel and Depth-1-vs-Depth-2
    experiment.

## 13. Expected production files

The implementation plan is expected to touch only the minimum subset of:

- `showdown_bot/src/showdown_bot/battle/decision.py`
- `showdown_bot/src/showdown_bot/battle/search.py`
- `showdown_bot/src/showdown_bot/battle/mega_scoring.py`
- `showdown_bot/src/showdown_bot/battle/evaluate.py`
- `showdown_bot/src/showdown_bot/client/gauntlet.py`
- `showdown_bot/src/showdown_bot/eval/decision_profile.py`
- corresponding focused tests
- one project report and the canonical status documents after verification

If implementation requires a second persisted sidecar, a DecisionTrace schema change, chooser
change, frontier change, or state-transition change, stop and return to design review.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Parameter forwarded but ignored | Low-accuracy Turn-2 consumption counterproof |
| Different paths resolve different settings | Single resolution point plus call-count and spy tests |
| Apparent “full probabilistic search” claim | Pinned terminology and representative-leaf non-expansion test |
| Hidden Turn-2 branch-cap fallback | At-origin per-ply cap telemetry in exact-closed profile v4 |
| Telemetry counts trace recomputation | Sink only on real scoring call sites |
| Schema drift corrupts frozen evidence | New v4 field set; v1-v3 preserved unchanged |
| Profiling changes decisions | Off-by-default sink plus deterministic projection equality tests |
| Mega context rebound during refactor | Existing per-index context tests plus new forwarding spies |
| Search tree grows accidentally | Frontier and one-successor-per-selected-slot counterproofs |
| Preflight overclaims live latency | Cold/warm separation and explicit microprofile non-claim |
| Scope expands into search redesign | Stop condition in §13 |

## 15. Acceptance and non-claims

The slice may be marked complete only when:

- every success condition in §3 is evidenced;
- the full suite passes with no new unexplained skip/xfail;
- profile v4 validates exact fields and semantic relations;
- prior profile schemas remain readable;
- cost preflight artifacts are reproducible and complete;
- the closeout report states what was verified locally and what remains unrun.

The completion statement must say:

> When the existing coarse Depth-2 path is used, its Turn-1 and Turn-2 evaluations now use one
> resolved accuracy configuration, and the executed work is observable.

It must **not** say:

- Depth-2 is stronger;
- Depth-2 is production-ready or default-on;
- the method computes a full two-turn expected value;
- the 1000-ms live gate passed;
- the diverse panel passed;
- Champions Strength changed from NO-GO;
- a new holdout is authorized.

# 2c-Slice-0b — Mode-Aware Full-Fidelity Aggregation Export + Probe

**Status:** design for review · **Path:** B/C (offline research) — the live decision path is unchanged.

## 1. Why

Probe 0a (`research/aggregation_probe.py`, reduced fidelity) showed the response aggregation is **not
a dead lever**: a plain mean beats the current risk-weighted aggregate by ~+4pp teacher-agreement,
and more risk-averse variants are worse. But 0a cannot act, because (a) it used summary-stat proxies,
not the real per-response vectors, and (b) reading `battle/policy.py::aggregate_scores` revealed the
aggregation is **mode-dependent with three independent knobs**:

```
AHEAD       -> (weighted) mean                         # risk_lambda irrelevant
NEUTRAL     -> wmean - risk_lambda * wvar              # risk_lambda=0 == weighted mean
MUST_REACT  -> avg - must_react_lambda * (avg - worst) # SEPARATE knob (SHOWDOWN_MUST_REACT_LAMBDA,
                                                        # default 0.6; docstring: historically "too passive")
```

So the +4pp mixes **risk_lambda** (neutral), **must_react_lambda** (must_react), and
**weighted-vs-unweighted** response weighting. This slice separates them on real data before any live
scalar change.

## 2. Goal / Non-Goals

**Goal:** export the true per-candidate × per-opponent-response scores + response weights + the exact
mode and both lambdas for a **bounded** run, then re-run the probe mode-split at full fidelity, so the
three effects are cleanly separated and a pre-registered decision rule picks the actual first 2c lever.

**Non-goals:** no live-policy change; no world/set sampling; no search depth; no change to *what the
bot chooses*. The only decision-path touch is additive, off-by-default telemetry (record the lambdas
+ mode already used at aggregation time).

## 3. Component A — full-fidelity aggregation export (off-by-default)

A research-only JSONL sidecar, disabled by default, written from the already-built `DecisionTrace`
(which already carries `candidates[].score_vector` = per-response scores, `opponent_response_weights`,
`game_mode`). The decision path additionally records — as pure side-effect telemetry, like Spec 01's
`selection_stage` — the exact `risk_lambda`, `must_react_lambda`, and the aggregation `mode` that
`aggregate_scores` received. Enabled only via an env gate (e.g. `SHOWDOWN_AGG_TRACE_OUT`); when unset,
no trace object work beyond today, no file, byte-identical dispatch.

Per decision the sidecar row contains:
- `battle_id`, `turn_number`, `our_side`, `decision_id`, provenance (git_sha, config_hash, format_id)
- `game_mode` **and** the exact `aggregation_mode` + `risk_lambda` + `must_react_lambda` used
- `selected_action_key` (normalized via the Spec-01 `normalize_choose`)
- `teacher_best_action_keys` (list; may be empty pre-label or a tie set), joined from the datagen teacher
- `response_keys` (normalized opponent responses) + `response_weights` (parallel)
- `candidates`: for each — `action_key`, `exported_aggregate_score`, `response_scores` (parallel to
  `response_keys`)

Fail-closed row validation + a stable canonical serialization (reuse the Spec-01/audit patterns).

## 4. Component B — mode-aware full-fidelity probe

Reads the sidecar; for each decision, deterministically re-ranks candidates under variants, **replaying
the exact mode-specific formula from `policy.py`** so a sweep is only applied where it is meaningful:
- **AHEAD:** weighted mean vs unweighted mean only (risk knobs do nothing here — flag if any variant
  claims to change an AHEAD decision via a risk knob → bug).
- **NEUTRAL:** `risk_lambda` sweep `{0.0, 0.1, 0.25, 0.5, 0.75, 1.0}` (0.0 == weighted mean),
  plus weighted vs unweighted, plus weight-flatten / weight-sharpen.
- **MUST_REACT:** `must_react_lambda` sweep `{0.0, 0.3, 0.6, 1.0}` (0.0 == mean, 1.0 == pure worst),
  plus weighted vs unweighted.

**Self-consistency pin (hard):** replaying the current mode formula with the exported
`risk_lambda`/`must_react_lambda`/weights must reproduce **every** candidate's
`exported_aggregate_score` within a stated float tolerance (not just the top action), and reconstruct
the exported `selected_action_key`. A mismatch is a fatal probe error (the export is incomplete or the
replay is wrong) — never silently proceed.

## 5. Report (deterministic JSON + Markdown)

Separates and reports, **globally and per mode**, with `mode_sample_count` and
`mode_changed_action_rate` prominent (so a small-mode-large-effect result is not hidden by a global
average):
- **risk effect** (NEUTRAL risk_lambda sweep)
- **must-react-risk effect** (MUST_REACT must_react_lambda sweep) — reported as its own story
- **response-weight effect** (weight flatten/sharpen)
- **weighted-vs-unweighted effect**

Each with: usable/skipped counts, `changed_action_rate`, `teacher_agreement_delta`,
`variant_fixed_teacher_miss`, `variant_broke_teacher_hit`, top2-flip, margin deltas, near-tie rate.
No non-finite numbers; sorted keys/lists; byte-identical for identical input.

## 6. Data source — bounded Kaggle run

The raw traces exist only during battles and were not persisted for 2b-2.5a, so a **small** datagen
run (Kaggle; e.g. the rain panel or smaller) with the export ON produces the sidecar + teacher labels.
No local battles. Reuses the existing datagen kernel + sharding.

## 7. Pre-registered decision rules (gate the actual first 2c lever)

```
NEUTRAL signal at risk_lambda↓ (teacher_agreement_delta >= +2pp, fixed_miss >> broke_hit,
        changed_action_rate >= 5%)            -> 2c-Slice-1 = live-gated risk_lambda A/B
MUST_REACT signal at must_react_lambda↓        -> 2c-Slice-1 = live-gated must_react_lambda A/B
                                                  (story: "must_react policy too passive", not "risk too high")
signal only in unweighted mean                 -> resp_weights audit / calibration probe, no lambda change
AHEAD signal                                   -> weighting / response-model check (risk does nothing there)
worst / CVaR worse                             -> park the CVaR/risk-aversion direction explicitly
no full-fidelity signal                        -> drop the aggregation lever, proceed to bounded depth-1
```

## 8. Invariants / testing

- INV-1 (export is telemetry, allowed in the live path), INV-4 (off-by-default + ablation), no RNG,
  byte-identical when the env gate is unset (golden test).
- Unit tests: export writer off = byte-identical / no file, on = correct fields + validation;
  probe mode-split correctness, the self-consistency pin (all candidates), determinism (shuffled input
  → identical report), non-finite rejection.
- Closeout: the bounded run + the full-fidelity probe report + the decision-rule verdict.

## 9. Relation to prior work

Reuses Spec-01 `decision_capture.normalize_choose` (action keys) + the sidecar/validation patterns and
the audit's deterministic-report discipline. Supersedes probe 0a's reduced-fidelity risk variants with
the real mode-split ones; 0a stays as the finding's provenance.

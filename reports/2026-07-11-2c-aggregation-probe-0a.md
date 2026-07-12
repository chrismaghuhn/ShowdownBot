# 2c aggregation probe 0a — reduced-fidelity, offline on 2b-2.5a

**Date:** 2026-07-11 · **research/C-path, offline only** — no live-path change, no RNG, no battles.

## Purpose

Cheaply test (before building anything live) whether re-aggregating a decision's candidates under a
different opponent-response **risk** function changes the chosen action and its agreement with the
rollout teacher — using ONLY already-persisted 2b-2.5a features.

## Fidelity (important)

The raw per-opponent-response score vectors and response weights are **not persisted** in the
dataset (`features.py` consumes them into summary stats and discards them). So the risk "variants"
here are **proxies** from the persisted per-candidate summaries (`heuristic_aggregate_score` = the
current risk-weighted baseline, `score_mean_vs_opp`, `score_worst_response`, `score_var_vs_opp`).
They capture the mean/worst/mean-variance axes — NOT an arbitrary risk_lambda sweep or true CVaR over
the full response vector.

## Result (3133 usable multi-candidate decisions)

| variant | changed_action | teacher_agree_Δ | fixed_miss | broke_hit |
|---|---:|---:|---:|---:|
| mean | 0.170 | **+0.040** | 242 | 116 |
| mean−0.5·std | 0.186 | +0.020 | 211 | 149 |
| mean−1.0·std | 0.180 | −0.005 | 149 | 166 |
| mean−2.0·std | 0.255 | −0.064 | 138 | 338 |
| worst_case | 0.167 | −0.015 | 109 | 155 |

baseline teacher-agreement 0.502 · near-tie rate 0.297 · single-candidate skipped 169.

## Reading — NOT a null result

- **"Aggregation is dead" is no longer tenable.** A plain **mean** aggregation agrees with the
  teacher **+4pp** more than the current risk-weighted aggregate (fixes 242 teacher-misses, breaks
  116). More risk-averse variants (mean−λ·std, worst_case) get progressively **worse** → the plan's
  2c-"CVaR" direction is **contra-indicated** by this probe.
- The direction that helps is toward **less** risk-aversion / plainer aggregation, not more.

## Caveats → why 0a is not actionable live

1. **Reduced fidelity** (summary proxies, not the full per-response re-aggregation).
2. **Three effects are conflated.** During review, reading `battle/policy.py::aggregate_scores`
   revealed the aggregation is **mode-dependent with three knobs**, not one:
   - `AHEAD` → (weighted) mean (risk_lambda irrelevant)
   - `NEUTRAL` → `wmean − risk_lambda·wvar`  (risk_lambda=0 == weighted mean)
   - `MUST_REACT` → `avg − must_react_lambda·(avg − worst)`  (a **separate** knob,
     `SHOWDOWN_MUST_REACT_LAMBDA`, default 0.6 — the docstring flags it historically "too passive")
   So the +4pp mixes risk_lambda (neutral), must_react_lambda (must_react), and weighted-vs-unweighted.
3. **Teacher-agreement ≠ winrate.**

## Next: 2c-Slice-0b (spec'd separately)

A **mode-aware full-fidelity** trace export (raw per-response scores + weights + game_mode + both
lambdas, off-by-default, bounded run) + a mode-split re-run of this probe, with a self-consistency
pin, to separate risk_lambda / must_react_lambda / weighting before any live scalar change.
Pre-registered decision rules gate whether a live-gated λ (or mr_lambda) A/B, a resp_weights audit,
or bounded depth-1 is the actual first 2c lever.

# 2c-Slice-0b — Mode-Aware Full-Fidelity Aggregation Probe — Verdict

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-aggregation-probe` · **Status:** T5 verdict reached; T6 closeout.

## TL;DR

The bot's response-aggregation is **too worst-case-conservative in both risk modes.** On a full-fidelity,
self-consistency-pinned probe over a 75-battle **rain** datagen panel (real Kaggle run):

- **Primary lever — `must_react_lambda↓` (MUST_REACT mode):** from the `0.6` default toward `0.0`,
  teacher-agreement rises **+13.7pp** (33 decisions fixed / 2 broken, 16:1), n=232 MUST_REACT decisions.
  Cleanest, most one-directional signal. `must_react_lambda↑` (toward pure worst-case) hurts.
- **Secondary — `risk_lambda↓` (NEUTRAL mode):** +6.0pp at `0.1` (24 fixed / 6 broke, 4:1), n=332.
  Real but with more collateral breakage. `risk_lambda↑` hurts hard (−12pp).
- **Dead directions:** the CVaR / worst-case direction (must_react↑, risk↑) clearly HURTS (−12pp) — as
  probe 0a already suggested. The response-weighting is **not** a lever (unweighted = wash −1.3pp,
  flatten = −9.1pp) → the protect-prior weights do useful work; **keep them**.

**Pre-registered decision rule (spec §7): `2c-Slice-1 = a live-gated `must_react_lambda` A/B`** (story:
"must_react is too passive", not "risk too high"). This offline signal **greenlights a live winrate test;
it is NOT itself a strength proof** — see Caveats.

## What this slice built

A **mode-aware, full-fidelity** offline probe to separate the three aggregation knobs that probe 0a had
conflated (`+4pp mean`), before any live scalar change:

1. **Off-by-default full-fidelity export** (`research/aggregation_trace.py`, wired via
   `--agg-trace-out` / `SHOWDOWN_AGG_TRACE_OUT`): the exact per-candidate × per-opponent-response score
   matrix, response weights, exact `aggregation_mode` + both lambdas, per decision. Byte-identical when
   off (golden-tested).
2. **Mode-aware probe** (`research/aggregation_probe.py::run_full_fidelity_probe`): `replay_aggregate` is
   a **bit-exact mirror** of `battle/policy.py::aggregate_scores` (unweighted paths use
   `statistics.mean`/`pvariance` exactly). A **hard self-consistency pin** replays every candidate and
   must reproduce its exported score; mode-split sweeps of `risk_lambda` (NEUTRAL),
   `must_react_lambda` (MUST_REACT), and weighted-vs-unweighted / flatten / sharpen.
3. **Offline teacher-label join** (`research/agg_teacher_join.py`): the full-fidelity scores live in the
   agg-trace, the teacher labels in the ML dataset — two independent writers, no shared key. The join
   reconstructs `game_id → seed_index` self-consistently (replayed `make_run_id`/`make_game_id`,
   bijective + turn-count cross-check), then **intersection-joins on `(seed_index, turn_number)`** with
   positional candidate alignment, fail-closed on ambiguity.

## Fidelity (the core validation)

**Self-consistency pin: `max_abs_error = 0.0` over 6201 candidates** (2968 AHEAD-invariance checks) on the
full panel — and identically `0.0` on the 10-battle shard (720 candidates). The bit-exact
`replay_aggregate` reproduces **every** live `aggregate_scores` output. The full-fidelity export + replay
is validated on real Kaggle data, not just fixtures. (The `statistics.mean`/`pvariance` fix vs the plan's
naive `sum/len` paraphrase is what makes this exact rather than ~1e-9-fragile.)

## Numbers (full rain panel, 75 battles; n=NEUTRAL 332 / AHEAD 498 / MUST_REACT 232; 991 teacher-labeled)

| Variant | Δ teacher-agree | fixed / broke | changed |
|---|---:|---:|---:|
| **must_react_lambda 0.0** | **+13.7pp** | **33 / 2** | 19% |
| must_react_lambda 0.3 | +9.7pp | 24 / 2 | 13% |
| must_react_lambda 0.6 *(baseline)* | 0 | — | — |
| must_react_lambda 1.0 | −1.3pp | 1 / 4 | 5% |
| **risk_lambda 0.1** | **+6.0pp** | **24 / 6** | 33% |
| risk_lambda 0.0 | +5.0pp | 26 / 11 | 36% |
| risk_lambda 0.25 | +4.4pp | 18 / 5 | 28% |
| risk_lambda 0.5 *(baseline)* | 0 | — | — |
| risk_lambda 0.75 | −10.7pp | 1 / 33 | 16% |
| risk_lambda 1.0 | −12.1pp | 1 / 37 | 18% |
| unweighted | −1.3pp | 34 / 47 | 12% |
| flatten (weights → uniform) | −9.1pp | 4 / 31 | 15% |
| sharpen | +1.7pp | 16 / 11 | 13% |

## Caveats (read before acting)

1. **Teacher-agreement ≠ winrate.** All deltas are measured against the stored **rollout teacher**, which
   this slice separately confirmed is **belief-dependent / circular** (its opponent model is the same
   single-point prior the live bot uses). "More teacher-agreement" ⇒ "moves toward the teacher's pick",
   **not** proven "wins more".
2. **The teacher is structurally a mean-evaluator.** `counterfactual_value` is a weighted **mean** over
   opponent responses, so agreeing with it is inherently **biased toward the mean-aggregation levers**
   (`must_react_lambda↓`, `risk_lambda↓`) being tested here — partly tautological. The **+13.7pp likely
   overstates** the real effect. However, the **direction is robust independent of that bias**: the fact
   that `must_react_lambda↑` and `risk_lambda↑` clearly HURT (−12pp) shows over-conservatism is real, not
   a mean-bias artifact.
3. **Rain panel only.** Rain is tailwind-heavy — exactly where MUST_REACT / worst-case conservatism
   bites. The signal may be partly rain-specific; the live A/B (or additional panels) generalizes it.

Net: **direction solid (bot is over-conservative), magnitude optimistic → the live winrate A/B is the
real test, not a formality.**

## Bugs found + fixed during the run (staged shard caught them before the full run)

- **Agg-trace write was not fail-safe** (`client/gauntlet.py`): a lossy `_label_ja` switch-collision made
  `validate_agg_row` raise in the (unwrapped) agg-trace write, which propagated and **skipped the dataset
  export below** (independence violation) + a loud `DATAGEN: FAIL`. Fixed (`415be3b`): best-effort
  try/except, no propagate, index only on success. OFF path byte-identical.
- **No decision join key:** added a nullable `turn_number` to the agg-trace row (`415be3b`) so the offline
  join has a reliable `(seed_index, turn_number)` key (the naive `decision_index` re-index breaks once
  agg-trace and dataset drop different decisions — team-preview vs duplicate-switch).
- **Pre-existing (not fixed here, flagged):** duplicate-`_label_ja`-switch decisions are silently dropped
  from datasets too (the export's own label-prefix guard). Broad data-quality gap; worth a future ticket.

## Tooling delivered (all off-by-default, byte-identical when unused)

`917847a` 0a probe+report → `2360777` spec → `42bdf2d` plan → `d26ebed` T1 (decision-trace telemetry) →
`83f3f0d` T2 (agg-trace writer) → `fc82f4b` T3 (gauntlet/cli wiring) → `84e6c0a` T3-fix
(`SHOWDOWN_AGG_TRACE_OUT` env alias + `NON_BEHAVIORAL` classification) → `0f5fdb6` T4 (mode-aware probe +
self-consistency pin) → `415be3b` fix (fail-safe write + turn_number) → `c8bf00b` T5 (teacher-join).

## Provenance (Kaggle)

- Repro-validation gate `sb-repro-validation` on `0f5fdb6`: **PASS** (10/10 winner+seed+byte-repro).
- Shard `sb-datagen-rain-aggtrace` (rain, SHARD 0/8, ~10 battles) on `415be3b`: DATAGEN DONE.
- Full panel `sb-datagen-rain-full-aggtrace` (rain, unsharded, 75 battles) on `415be3b`: DATAGEN DONE,
  7581 dataset rows / 1184 agg rows / 75 results. Runtime ~1 kernel (unsharded fit comfortably; no
  multi-kernel sharding needed for 75 battles).
- Artifacts under `.claude/worktrees/2c-aggregation-probe/kaggle_out/` (git-ignored).

## Next

- **2c-Slice-1 (the verdict's slice):** a **live-gated `must_react_lambda` A/B** (e.g. `0.0`/`0.3` vs the
  `0.6` default), a paired Kaggle strength run + McNemar (like 2b-4), held-out discipline. `risk_lambda↓`
  is a strong secondary candidate. This is where the offline greenlight becomes a real strength claim.
- Optionally verify the over-conservatism signal on other panels (sun/trickroom/fixed) to check
  rain-specificity before or alongside the live A/B.

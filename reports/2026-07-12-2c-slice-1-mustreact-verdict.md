# 2c-Slice-1 — `must_react_lambda` live dev-strength A/B — Verdict

**Date:** 2026-07-12 (autonomous overnight) · **Branch:** `feat/slice-2c-1-mustreact` · **Status:** dev-strength verdict; held-out NOT spent (user-gated).

## TL;DR

The 2c-0b offline probe said the bot is over-conservative and greenlit **lowering** `must_react_lambda`
(0.6 → 0.3). The live dev-strength McNemar (150 games vs `max_damage`) says the offline metric was
**inverted**:

- `must_react_lambda=0.3` (less conservative): **REGRESSION** — winrate 6.7% vs 18.0% baseline, **−11.3pp,
  p=0.0005**.
- `must_react_lambda=0.8` (more conservative): **GO** — winrate 29.3% vs 18.0% baseline, **+11.3pp,
  p=0.0002**.

Perfectly symmetric → **monotonic: higher `must_react_lambda` → higher winrate vs `max_damage`. The
offline probe pointed the wrong way.** The live gate turned a misleading offline signal into a **real
candidate improvement: `must_react_lambda 0.6 → 0.8`** — a pure heuristic scalar (`SHOWDOWN_MUST_REACT_LAMBDA=0.8`,
no ML). **Caveat: vs `max_damage` only** (see below) → it is a **dev-GO candidate, not a ship**; the
**held-out gate (varied opponents, user-gated) is the real test and was NOT spent.**

## The A/Bs (dev-strength, `2b4_devstrength_v001`, 150 games, fixed hero vs max_damage on rain/sun/trickroom)

| candidate vs baseline 0.6 | winrate (cand / base) | Δ | McNemar (A-won-B-lost / B-won-A-lost, n_disc) | p | verdict |
|---|---|---:|---|---:|---|
| `must_react_lambda=0.3` | 6.7% / 18.0% | −11.3pp | 3 / 20, n=23 | 0.0005 | **REGRESSION** |
| `must_react_lambda=0.8` | 29.3% / 18.0% | +11.3pp | 19 / 2, n=21 | 0.0002 | **GO** |

Both safety-gate-clean, byte-reproducible, latency p95 ≤ 467ms. The 0.8 gain is driven by the sun cell
(18% → 66%); rain and trickroom cells stay low (12% / 10%).

## Why the offline metric inverted (mechanistic, not noise)

The 2c-0b probe scored variants by agreement with the **rollout teacher**, whose `counterfactual_value` is
a weighted **mean over opponent responses** — so it favors mean-aggregation (low `must_react_lambda`). But
the eval opponent is `max_damage`, which plays the **worst-case damage move**. So worst-case-conservative
aggregation (high `must_react_lambda`) correctly models the opponent and wins, while the mean-teacher rated
it worst. **The teacher is blind to the opponent's actual policy, so its preferred direction was exactly
backwards vs winrate.** (See memory `teacher-agreement-winrate-inversion`.)

The offline signal was also **rain-specific**: re-running the full-fidelity probe on a trickroom datagen
panel, `must_react_lambda` had **zero** teacher-agreement effect (rain: +13.7pp). Rain (fast tailwind) has
many must-react flips; trickroom (slow) decisions are clear-cut.

## Caveats (read before shipping)

1. **vs `max_damage` only.** `max_damage` literally plays worst-case, so conservatism matching it is
   expected to help; the sun 66% is `max_damage`-specific. Against varied/human opponents, more
   conservatism may not help — high `must_react_lambda` can turtle into Protect and lose tempo (the
   `policy.py` docstring's original warning). **Generality is unproven.**
2. **Held-out is the real gate, and it was NOT spent** (user-gated). This dev-strength GO greenlights a
   held-out run on `must_react_lambda=0.8` (or a milder 0.7); it does not itself justify shipping.
3. **1.0 not tested** — deliberately, to avoid over-fitting the `max_damage` optimum. The direction and
   the 0.8-GO are the findings; the exact value needs held-out / varied opponents.

## Methodological headline (broader than this slice)

**Offline teacher-agreement is not a reliable winrate proxy — it can be optimistic, panel-specific, and
inverted.** The 2c-0b aggregation-retuning-via-teacher-agreement direction is a **dead end** as a decision
metric (the probe is bit-exact-sound; its *signal* just doesn't predict winrate). Future tuning should gate
on **winrate/McNemar** (the T5 `eval-report` machinery) and the outcome-grounded labels from the new
**outcome-join** (Spec-04, built the same night), not teacher-agreement. This also cautions any 2b reranker
training that distills the same teacher.

## Recommendation for the user

1. **Run the held-out gate on `must_react_lambda=0.8`** (varied/held-out opponents) to decide whether the
   `max_damage` dev-GO generalizes. If it holds → ship `SHOWDOWN_MUST_REACT_LAMBDA=0.8` (or the held-out-best
   value); a pure-heuristic, no-ML winrate improvement.
2. Treat the 2c-0b offline probe as a **diagnostic/telemetry tool, not a decision metric.**
3. Consider the same inversion for `risk_lambda` (NEUTRAL mode) — env-tunability added this session; a
   `risk_lambda↑` A/B is the natural next check.

## Tooling delivered (reusable, this slice)

- `tools/kaggle/env_ab_kernel.py` + `kernel_payload.run_devstrength_env_ab` — a **generic paired
  dev-strength env-A/B** Kaggle kernel (any `SHOWDOWN_*` knob, `BASELINE_ENV`/`CANDIDATE_ENV`), reusing the
  T5 pairing + McNemar. 27 tests.
- `SHOWDOWN_RISK_LAMBDA` env-tunability for `risk_lambda` (parity with `must_react_lambda`), so the
  secondary NEUTRAL lever is A/B-able with no further code.

## Provenance (Kaggle, all on `REPO_SHA=c40159b`, held-out untouched)

- `sb-2c1-mustreact-strength` (0.3 vs 0.6): NO-GO / regression. `kaggle_out/2c1-mustreact/paired-report/`.
- `sb-2c1-mustreact08-strength` (0.8 vs 0.6): GO. `kaggle_out/2c1-mustreact08/paired-report/`.
- Schedule `2b4_devstrength_v001` (panel_split=dev; held-out ledger never touched). Baseline/candidate pair
  by `battle_id` (differing `config_hash`, as required).

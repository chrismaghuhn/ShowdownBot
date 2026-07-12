# 2c Search-Spine — Slice 1: NEUTRAL CVaR aggregation (off-by-default, winrate-gated)

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-cvar-neutral` (off local `main 8cadb3e`) · **Status:** design, user-approved ("passt so")

## Goal

Replace the **variance** downside in the `NEUTRAL` aggregation operator with a **CVaR (worst-case-tail)** downside, behind an off-by-default env toggle, and prove or refute it on **winrate** (McNemar), not teacher-agreement. This is the first, smallest increment of the 2c search spine (per `TestBOtpläne/02-decision-engine.md §3` + `ADR-0004`): the CVaR risk-aggregation axis, applied to the **existing 1-ply opponent responses** — no world-sampling, no lookahead (those are later axes).

## Motivation (and an honest bound on it)

`aggregate_scores` (`battle/policy.py`) is mode-dependent:
- `MUST_REACT` → `wmean − must_react_lambda·(wmean − min)` — a worst-case downside.
- `NEUTRAL` → `wmean − risk_lambda·wvar` — a **variance** downside.
- `AHEAD` → `wmean`.

The 2c-1 investigation (2026-07-12, live on Kaggle) found:
- Raising the MUST_REACT worst-case weight helped vs `max_damage` (dev-strength +11.3pp; held-out did not generalize, so it was **not shipped** — the fixed global scalar is the wrong vehicle).
- Raising the NEUTRAL **variance** weight (`risk_lambda` 0.5→0.75) **regressed −12.67pp** (p=0.0002).

So the variance downside is the suspect term, and worst-case is the direction that helped elsewhere. **Honest bound:** the live evidence proves only that *raising* the variance penalty hurts vs a worst-case opponent — it does **not** prove that a CVaR/worst-case downside is *better* than variance, nor better than simply dropping the downside (`risk_lambda=0`, i.e. NEUTRAL = mean). Therefore this slice is a **winrate-gated hypothesis test**, and its gate includes a `NEUTRAL = mean` comparison arm so we can tell "CVaR helps" apart from "any-non-variance helps".

**Why CVaR and not just min:** over the current ≤5 fixed responses, CVaR_α (α≈0.25) ≈ the worst 1–2 responses — close to `min`, only softer. Its real payoff is later: the **same** operator, once +Sampling supplies many worlds, takes the tail of a rich distribution. Building it now (over 5 responses) banks the NEUTRAL fix *and* is the exact operator +Sampling will reuse — no rework.

## Scope

**In:** the `NEUTRAL` branch of `aggregate_scores` only; a weighted-CVaR helper; three env knobs; decision-layer wiring; tests.
**Out (non-goals):** MUST_REACT and AHEAD operators (untouched — MUST_REACT is the term with positive evidence, do not perturb it); world-sampling; depth>1; the reranker-as-prior; any value head; any change to the default policy (toggle is **off** by default).

## Design

### 1. Weighted CVaR helper (`battle/policy.py`)

```python
def cvar_lower(scores: list[float], weights: list[float] | None, alpha: float) -> float:
    """Lower-tail CVaR (expected shortfall) of a discrete distribution: the
    probability-weighted mean of the worst `alpha`-mass of `scores`.

    - `alpha` is clamped to (0, 1]. alpha >= 1 -> the full weighted mean.
    - `weights` None or unusable (len mismatch / non-positive sum) -> uniform.
    - Sort ascending by score (worst first); accumulate normalized weight until
      `alpha` mass is reached, clipping the straddling response to the residual
      mass so exactly `alpha` mass is averaged; divide the accumulated
      weight*score by alpha.
    - Empty `scores` -> 0.0 (mirrors aggregate_scores' empty guard).

    At n responses with alpha small this approaches min(scores); at alpha=1 it
    equals the weighted mean. Deterministic, pure, no RNG."""
```

Reference implementation (exact, not pseudo):

```python
def cvar_lower(scores, weights=None, alpha=0.25):
    if not scores:
        return 0.0
    alpha = max(1e-9, min(1.0, alpha))
    n = len(scores)
    if weights is not None and len(weights) == n and sum(weights) > 0:
        total = sum(weights)
        pairs = [(s, w / total) for s, w in zip(scores, weights)]
    else:
        pairs = [(s, 1.0 / n) for s in scores]
    pairs.sort(key=lambda sw: sw[0])  # ascending: worst first
    acc_w = 0.0
    acc_sw = 0.0
    for s, w in pairs:
        take = min(w, alpha - acc_w)
        if take <= 0:
            break
        acc_sw += take * s
        acc_w += take
        if acc_w >= alpha:
            break
    return acc_sw / acc_w if acc_w > 0 else pairs[0][0]
```

### 2. NEUTRAL operator change (`aggregate_scores`)

Only the NEUTRAL branch changes, and only when the toggle is on:

```python
# NEUTRAL branch (weighted + unweighted paths):
if _neutral_cvar_enabled():
    tail = cvar_lower(scores, weights_or_None, _cvar_alpha())
    return wmean - _cvar_lambda() * (wmean - tail)
else:
    return wmean - risk_lambda * wvar        # unchanged current behavior
```

`wmean` is the same weighted/unweighted mean already computed in that branch. MUST_REACT and AHEAD branches are byte-for-byte unchanged.

### 3. Env knobs (`eval/config_env.py`, all BEHAVIOR_AFFECTING — Python-side)

| env var | default | effect |
|---|---|---|
| `SHOWDOWN_NEUTRAL_CVAR` | `0`/unset (off) | off → current variance NEUTRAL (byte-identical); on (`1`/`true`) → CVaR downside |
| `SHOWDOWN_CVAR_ALPHA` | `0.25` | CVaR tail mass, clamped (0,1] |
| `SHOWDOWN_CVAR_LAMBDA` | `0.5` | downside weight (matches the historic `risk_lambda` default, so "on with defaults" is a pure operator swap, not also a strength retune) |

Readers mirror `_risk_lambda`/`_must_react_lambda` exactly (private `_x()` + public `x()`), same clamp/try-except discipline. When `SHOWDOWN_NEUTRAL_CVAR` is unset, **none** of the three are read on the hot path → config_hash and `/choose` are byte-identical to `main` (the off-invariant).

### 4. Wiring (`battle/decision.py`)

The NEUTRAL-CVaR toggle/alpha/lambda are read where `risk_lambda` is already resolved (the None-sentinel pattern added in 2c-1). No new call sites in the hot loop beyond the existing aggregate path.

## Invariants

- **INV-off-byte-identical:** with `SHOWDOWN_NEUTRAL_CVAR` unset, a run is byte-identical to `main` (config_hash equal, same `/choose`, same results.jsonl). Proven by a config_hash test + a decision-parity test.
- **INV-anytime (INV-3):** no change to the fallback chain; CVaR is O(n log n) over ≤5 items — no latency risk, no new failure mode.
- **INV-ablation (INV-4):** the whole change hides behind one toggle, default-off; ships only after a winrate gate.

## Gate (winrate, not teacher-agreement)

Reuse the retargetable env-A/B kernel (`tools/kaggle/env_ab_kernel.py`, built in 2c-1) + `eval-report --mode gate` McNemar. **Three arms**, all via env (no new kernel code — the arms are just env dicts):

| arm | env | NEUTRAL operator |
|---|---|---|
| baseline (variance) | *(none)* | `wmean − 0.5·wvar` (current default) |
| CVaR | `SHOWDOWN_NEUTRAL_CVAR=1` | `wmean − 0.5·(wmean − CVaR_0.25)` |
| mean (control) | `SHOWDOWN_NEUTRAL_CVAR=1 SHOWDOWN_CVAR_LAMBDA=0` | `wmean` (downside dropped) |

- **Dev-strength** McNemar (150-game `2b4_devstrength_v001`, vs `max_damage`) for CVaR-vs-baseline and mean-vs-baseline. GO only if CVaR beats baseline **and** (ideally) beats the mean control — else the win is "drop the penalty", not CVaR.
- **Held-out** (`t6_heldout_v001`, varied opponents) is the ship gate, **user-gated** — spent only if dev-strength is a clear GO. (Held-out is small/underpowered by design; a GO there is required but a null repeats the 2c-1 lesson.)
- Latency: non-issue for this slice; formal p95<1000ms pin deferred to the +Sampling slice.

## Files

- Modify `showdown_bot/src/showdown_bot/battle/policy.py` — `cvar_lower()` helper + NEUTRAL branch toggle + `_neutral_cvar_enabled()/_cvar_alpha()/_cvar_lambda()` readers.
- Modify `showdown_bot/src/showdown_bot/eval/config_env.py` — classify the 3 env vars as BEHAVIOR_AFFECTING.
- Modify `showdown_bot/src/showdown_bot/battle/decision.py` — wire the toggle into the NEUTRAL aggregate call (sentinel pattern).
- Create `showdown_bot/tests/test_cvar_lower.py` — the CVaR math.
- Modify `showdown_bot/tests/test_policy.py` — NEUTRAL-CVaR operator behavior + off-parity.
- Modify `showdown_bot/tests/test_config_env.py` — the 3 env vars classified + config_hash toggling.

## Testing

- **`cvar_lower` unit tests:** empty→0; single→that value; alpha≥1→weighted mean; alpha→0→min; uniform vs weighted tail; straddle-clipping (exactly α mass averaged); monotonic in alpha; determinism (same input→same output).
- **Operator tests:** toggle-off NEUTRAL == current `wmean − risk_λ·wvar` exactly; toggle-on == `wmean − cvar_λ·(wmean − CVaR_α)`; `cvar_λ=0` → pure `wmean`; MUST_REACT/AHEAD unaffected by any CVaR env var.
- **config_env tests:** the 3 vars in BEHAVIOR_AFFECTING (Python-side, not server); `behavior_env` includes them when set; config_hash changes when `SHOWDOWN_NEUTRAL_CVAR` toggled, unchanged when unset.
- **Off-parity:** a decision trace with the toggle unset is identical to `main` on a fixed fixture (guards the byte-identical invariant).

## Risks / open notes

- **Hypothesis, not a banked fix** (see Motivation): the 3-arm gate is what makes the result interpretable; do not ship CVaR unless it beats *both* variance and the mean control on dev-strength.
- **CVaR≈min at n≤5:** expected; the operator's larger value arrives with +Sampling, which reuses this exact helper.
- **No MUST_REACT change:** deliberate — it has positive evidence; touching it risks the one term that works.

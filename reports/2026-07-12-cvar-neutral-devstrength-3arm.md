# 2c NEUTRAL CVaR — 3-arm dev-strength gate — Verdict

**Date:** 2026-07-12 · **Branch:** `feat/slice-2c-cvar-neutral` · **Kaggle:** `sb-cvar-strength` + `sb-cvarmean-strength` @ `REPO_SHA ada75eb` · schedule `2b4_devstrength_v001` (150 games/arm vs `max_damage`, seed_base `2c-cvar-v001`)

## TL;DR — the win is "the NEUTRAL variance penalty is harmful", NOT "CVaR is good"

The 3-arm design (variance baseline vs CVaR vs mean-control) paid off. Both non-variance arms crush the variance baseline by ~+35pp — but **CVaR does not beat the mean-control** (they are statistically equal). So the improvement comes from *dropping/replacing the NEUTRAL variance penalty*, not from CVaR specifically. Per the spec's criterion ("GO only if CVaR beats **both** variance and mean"), this is **not a CVaR-specific GO**. The real, cheapest candidate is **`SHOWDOWN_RISK_LAMBDA=0`** (NEUTRAL = mean, no new code).

## Numbers (both vs the SAME variance baseline `{}` = 16%, 24/150)

| candidate | env | winrate | Δ vs variance | p | per-cell rain / sun / trickroom |
|---|---|---:|---:|---:|---|
| **CVaR** | `SHOWDOWN_NEUTRAL_CVAR=1` | 50.67% (76/150) | **+34.67pp** | 0.0000 | 6% / 50% / 96% |
| **mean-control** | `SHOWDOWN_NEUTRAL_CVAR=1, SHOWDOWN_CVAR_LAMBDA=0` | 52.00% (78/150) | **+36.00pp** | 0.0000 | 52% / 10% / 94% |

n_discordant 56 (CVaR) / 86 (mean); both safety-gate-clean, byte-repro. The two variance baselines are identical (16%, same config+seeds) — consistency check passes. **mean (52%) vs CVaR (50.67%) = 2 games = noise → statistically equal.**

## Interpretation

- **The NEUTRAL variance penalty (`risk_lambda·variance`, default 0.5) is actively harmful vs `max_damage`** — dropping it (mean) or replacing it with a CVaR worst-case tail both recover ~+35pp. This is the large-magnitude confirmation of the 2c-1 finding (`risk_lambda↑` regressed −12.67pp); the mean-control now tests `risk_lambda→0` live and it is a **huge GO** — so for `risk_lambda`, offline (↓ helps) and live agree (no inversion, as predicted).
- **CVaR is not CVaR-specific-better:** the worst-case-tail downside ≈ no downside (mean), and both ≫ the variance downside. So it is specifically the *variance form* that is bad, not "having a downside penalty".
- **Per-cell, CVaR and mean trade cells** (CVaR wins sun, loses rain; mean wins rain, loses sun; both ~95% trickroom) → neither is uniformly best; net equal. CVaR's rain/fast-board weakness (6%) makes mean the safer candidate for the held-out panel (balance + tailwind teams).
- **The 3-arm design prevented a misattribution:** the naive 2-arm read (CVaR +34.67pp GO) would have shipped CVaR; the control shows the win is dropping the variance penalty.

## The mega-caveat (read before any ship)

**This is vs `max_damage` only.** Same shape as 2c-1's `must_react_lambda=0.8` (+11.3pp dev-GO → **held-out NO-GO, did not generalize**). `max_damage` plays worst-case; the trickroom 94-96% smells like a `max_damage`-specific setup sweep. **+36pp dev is not a ship claim.** The held-out gate (varied opponents, user-gated) is the real test; the base rate for "big max_damage dev win generalizes" is currently 0/1.

## Decision

- **Not a CVaR-specific GO.** The CVaR slice's hypothesis (CVaR beats variance *because* worst-case) is not supported as CVaR-specific; the CVaR machinery is not needed.
- **Candidate to validate = `SHOWDOWN_RISK_LAMBDA=0`** (NEUTRAL = mean): biggest dev signal, simplest, robust across the held-out archetypes.
- **Next: held-out gate on `risk_lambda=0` vs default** (user-authorized). If it holds → ship `risk_lambda=0` (a one-env-var, no-ML strength gain). If not → the variance-drop is `max_damage`-specific, and 2/2 big dev wins failing held-out becomes a load-bearing methodological verdict about the dev panel itself.
- The CVaR slice stays **default-off** (byte-identical); keep it as available tooling (it is the reusable operator for the future +Sampling axis), do not merge as a default change.

## Held-out result (2026-07-12) — NO-GO, the win does NOT generalize

Held-out gate `SHOWDOWN_RISK_LAMBDA=0` vs default (`sb-heldout-riskzero`, `t6_heldout_v001`, 34 games/arm, 5 varied opponents, balance+tailwind teams): both arms **7/34 = 20.6%**, McNemar n10=4 / n01=4, **delta = 0.0000**, p=1.0, n_discordant=8. UNDERPOWERED, but the point estimate is *exactly* zero (not a hidden positive). Even the held-out `max_damage` games (on balance/tailwind teams) give only 10% — so the +36pp dev win was specific to the **dev team archetypes** (rain/sun/**trickroom**), which the held-out panel does not contain; it is inert on other teams even vs `max_damage`.

**=> NO-GO. Keep the default (`risk_lambda=0.5`).** Two append-only ledger entries logged (`heldout-riskzero-v1`, config_hashes `23351717`/`69daaa70`).

## Methodological verdict (load-bearing)

**2/2 big `max_damage` dev wins → exactly zero held-out effect:** `must_react_lambda=0.8` (+11.3pp dev, sun-specific) and `risk_lambda=0` (+36pp dev, trickroom/rain-specific) both collapse to delta 0 on held-out. The aggregation-scalar wins are **team-archetype-specific** vs `max_damage` and do not generalize to other teams/opponents. **Global aggregation-scalar tuning is exhausted as a source of shippable, general strength.** This re-confirms the strategic thesis: the lever is the **search spine** (per-position adaptation), not global scalar tuning. The CVaR *operator* stays useful — as the reusable risk-aggregation for the future **+Sampling** axis (CVaR over many sampled worlds), not as a global default.

## Provenance

- Kaggle `sb-cvar-strength` (`{}` vs `SHOWDOWN_NEUTRAL_CVAR=1`) + `sb-cvarmean-strength` (`{}` vs `SHOWDOWN_NEUTRAL_CVAR=1,SHOWDOWN_CVAR_LAMBDA=0`), `REPO_SHA ada75eb`, both fresh arms same kernel/server (clean 1-var delta). Reports: `scratchpad/kaggle_out/cvar-strength/` + `cvar-mean/`.

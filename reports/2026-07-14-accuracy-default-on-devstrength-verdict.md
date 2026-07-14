# Accuracy Default-On — Dev-Strength A/B Verdict

**Date:** 2026-07-14  
**Verdict:** **SAFETY-PASS** · Strength **UNDERPOWERED** · **directional warning** (no strength claim)  
**Commit:** `a956b6b` · **seed_base:** `accuracy-default-on-v001`  
**Spec:** `docs/superpowers/specs/2026-07-14-accuracy-default-on-strength-measurement.md`  
**Artifacts:** `data/eval/accuracy-default-on/devstrength-ab/` (results, seedlogs, manifests, paired report)

## Safety readout

**SAFETY-PASS** on both arms (`eval-report --mode gate`). All hard gates passed on A and B:
rows 150/150, crashes 0, invalid_choices 0, end_reason normal, dirty none, latency p95
within 1000 ms budget (A worst 482 ms, B worst 251 ms).

## Paired verdict

**UNDERPOWERED** — `n_discordant = 6` (< `N_DISCORDANT_CLAIM_MIN = 10`).

**No strength claim** is supported: the predeclared underpowered floor blocks GO, NO-GO,
equivalence, and any formal regression or improvement claim.

Directional readout is unfavorable (0 A-only wins, 6 B-only wins) and should be treated as
a follow-up risk signal, but the run is underpowered by the predeclared rule and therefore
does not support a regression or improvement claim.

| Metric | Value | Notes |
|--------|------:|-------|
| Winrate A (default-on) | 13.3% (20/150) | candidate, `{}` env |
| Winrate B (explicit off) | 17.3% (26/150) | baseline, `SHOWDOWN_ACCURACY_MODE=0` |
| McNemar n10 (A win, B lose) | 0 | |
| McNemar n01 (B win, A lose) | 6 | all discordants favor off |
| n_discordant | 6 | below claim minimum 10 |
| exact p | 0.03125 | not actionable under UNDERPOWERED |
| Automated verdict | UNDERPOWERED | not GO, not equivalence, not regression proven |

## What this does and does not support

| Supports | Does not support |
|----------|------------------|
| Default-on path runs safely on live dev-strength panel (implicit cap 6) | Default-on improves or preserves winrate vs explicit off |
| Explicit opt-out pairs cleanly at `a956b6b` | Held-out / varied-opponent generalization |
| Latency margin on candidate arm (p95 482 ms << 1000 ms) | **GO on strength** |
| Follow-up risk signal: discordants all favor off | **Equivalence** or **regression proven** |

## Caveats

- Opponents: **`max_damage` only** (trickroom / sun / rain dev cells).
- Not pairable with archived `13795ab` / `2b4-devstrength-v001` (different seed_base).
- Import-audit / VGC-Bench / HolidayOugi: **not started** — execution not approved (`1251dd6` PROPOSED).

## Next steps (user-gated)

1. Decide whether the next step is a **larger strength re-run** (power the discordant floor)
   or **Champions-readiness** work — not predetermined here.
2. Import-audit execution remains blocked until explicitly approved.
3. Do not cite this run as equivalence or as proof that default-on regressed.

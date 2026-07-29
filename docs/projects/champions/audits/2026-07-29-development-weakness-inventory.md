# Development weakness inventory — extracted from existing evidence

**Issue:** #127 · **Base:** `main @ 2c526bfb` · **Date:** 2026-07-29
**Type:** audit. Read-only. No production code was changed, no battle was run, no experiment was
started.

---

## 1. Scope and exclusion rules

### What this is

A structured inventory of bot weaknesses reconstructed **only** from evidence that already exists
in this repository, ranked by expected strength relevance.

### What this is not

This is **not** a candidate comparison and **not** a solution choice. That is #128. A weakness
ranking says *where the evidence points*, not *what to build*. Nothing here authorises an
implementation.

### Exclusion rule, and how it was applied

The sealed-holdout contract forbids using held-out results for candidate development or
prioritisation. Applied here **more broadly than the issue's literal wording**, and deliberately:

- The issue names the **Gate B** holdout (six sealed Champions teams, `gbh_*`).
- The repository also has an **older, separate** held-out set: the T6 evaluation panel v001, two
  held-out teams, sharing `config/eval/heldout_ledger.jsonl`.
- The issue's stated *reason* — "the independent holdout must not be used for candidate
  development or prioritization" — applies to both. Using T6 held-out outcomes to rank weaknesses
  would be candidate prioritisation informed by held-out data just as much as using Gate B's.

**Therefore: no held-out result from either set is reproduced or used as a ranking input.** Where a
source contains both, only the development portion was extracted and the held-out portion is named
but not quoted. No holdout game IDs, cell results, p-values, effect sizes, directions, matchups or
flips appear below.

One consequence worth stating: `docs/ROADMAP.md` records a strategic conclusion that is itself
derived from held-out outcomes. That conclusion is **excluded from the ranking**. The ranking below
rests on development evidence alone and would stand unchanged if that conclusion did not exist.

---

## 2. Source matrix

Every source consulted, with its classification. "Development evidence" = usable. "Technical /
operational" = real, but about correctness or infrastructure, not play strength. "Excluded" = not
used for content.

| # | Source | Class | What was taken |
|---|---|---|---|
| S1 | `reports/2026-07-11-teacher-disagreement-atlas.md` | Development | Full bucket breakdowns, 3302 decisions over 299 dev games |
| S2 | `reports/2026-07-11-fast-board-protect-discipline.md` | Development | Paired rain A/B, mechanism decomposition of the `tailwind_both` bucket |
| S3 | `reports/2026-07-12-2c-slice-1-mustreact-verdict.md` | Development | Dev winrates, the offline/winrate inversion and its mechanism |
| S4 | `reports/2026-07-14-accuracy-default-on-devstrength-verdict.md` | Development | Dev winrates, safety readout, underpowered verdict |
| S5 | `reports/2026-07-11-diagnostics-v0.md` | Development | Three log detectors and their counts on the 2b-4 dev archive |
| S6 | `reports/2026-07-11-2b2b-tera-used-diagnosis.md` | Development | Structural non-capture of Tera; two confirmed root causes |
| S7 | `showdown_bot/src/showdown_bot/battle/actions.py`, `battle/decision.py` | Development (code, re-verified today) | Current action-space and Tera-overlay behaviour |
| S8 | `showdown_bot/config/formats/*.yaml` | Development (config) | Which formats enable Tera |
| S9 | `docs/ROADMAP.md` §"Scalar-aggregation experiments" | **Mixed** | Dev-strength column only. Held-out column and the net conclusion drawn from it: **excluded** |
| S10 | `docs/ROADMAP.md` §P1 | Development (planning) | The stated absence of a dev-generalization panel |
| S11 | `docs/projects/champions/specs/2026-07-20-champions-both-foe-slots-diagnosis.md` | Technical / operational | Evidence-coverage defect, not a play weakness |
| S12 | `docs/projects/champions/audits/2026-07-23-gate-b-trapped-switch-defect-diagnosis.md` | Technical / operational | Legality defect, since fixed |
| S13 | `docs/projects/champions/audits/2026-07-27-mega-reconcile-*.md` | Technical / operational | Reconciliation defect |
| S14 | `docs/projects/champions/reports/2026-07-29-live-path-degradation-closeout.md` | Technical / operational | Live evidence now recordable; none recorded yet |
| S15 | Gate B holdout artifacts, verdicts, per-cell results, ledger entries | **Excluded** | Nothing |
| S16 | `reports/2026-07-12-heldout-mustreact08-verdict.md`, `reports/2026-07-12-cvar-neutral-devstrength-3arm.md` held-out sections | **Excluded** | Dev sections reached via S3/S9 only |

**Excluded for contamination:** S15 entirely; the held-out portions of S9 and S16.

---

## 3. A finding that governs the whole ranking

Before the inventory, because it changes how much weight every atlas-derived item deserves.

**The offline teacher-agreement metric has been demonstrated to invert against winrate.**

S3 records it with a mechanism, not as noise: the rollout teacher's `counterfactual_value` is a
weighted **mean over opponent responses**, so it favours mean-aggregation. The dev evaluation
opponent, `max_damage`, plays the **worst-case damage move**. Worst-case-conservative aggregation
therefore models that opponent correctly and won on winrate — while the mean-teacher rated it
worst. S3's words: *"The teacher is blind to the opponent's actual policy, so its preferred
direction was exactly backwards vs winrate."*

Measured on the same lever, same panel: `must_react_lambda` 0.3 → **−11.3pp**, 0.8 → **+11.3pp**,
symmetric and monotonic (S3). The offline probe had preferred the losing direction.

**Consequence for this inventory.** S1, the atlas, is the richest weakness evidence available and
it is *entirely* teacher-disagreement-based. Its buckets locate **where the heuristic and the
teacher differ** — which is not the same as where games are lost, and on at least one lever it was
demonstrably the opposite. S1 says so itself: *"a strict disagreement here is NOT a proven play
error"*.

Every atlas-derived item below is therefore capped at **medium** evidence confidence for
*strength* relevance, however large its disagreement rate. This is not hedging; it is the one
place where this repository has already measured the metric being wrong.

---

## 4. Weakness inventory

### W1 — Terastallization is never an enumerated candidate

| | |
|---|---|
| **Observed pattern** | The joint-action space contains no Tera action. Tera is applied only as a post-hoc overlay to the single already-chosen non-Tera winner, and only if it beats that line by a margin. |
| **Sources** | S6; **re-verified in current code today**: `actions.py:112` *"Tera stripped (overlay only) -> ~4x smaller space"*; `actions.py:103` `enumerate_my_actions`; `decision.py:1550` `_maybe_tera`, which iterates only `best_ja.slot0`/`best_ja.slot1`. |
| **Affected decisions** | Every turn in a Tera-enabled format where the best line requires Tera **on a move or target that is not already the non-Tera winner**. Such a line is structurally unreachable — no margin setting can recover it. |
| **Mechanism (inference)** | Enumeration prunes ~4× for cost. The overlay restores only the one-dimensional case "same line, plus Tera". The two-dimensional case "different line, because Tera" is outside the search space entirely. |
| **Strength relevance** | Tera is a once-per-battle strategic resource in VGC. Unknown magnitude — see frequency. |
| **Frequency** | **`unknown`.** `tera_used` is `False` in 17458/17458 dataset rows (S6), but S6 shows that is partly a *export* artifact: the heuristic does occasionally Tera, and those decisions are dropped from the export by a separate structural mechanism. The dataset therefore cannot measure how often this costs anything. No number is invented here. |
| **Evidence confidence** | **High** for the structural fact (read in today's code, not inferred). **Unknown** for impact. |
| **Overlap** | Independent of W2–W5. |
| **Scope limit that a solution must respect** | `gen9championsvgc2026regma` sets `tera: false` (S8), and `_maybe_tera` returns early on it. **On the current Champions front-track format this weakness is moot.** It applies to `gen9vgc2024regg`, `gen9vgc2025regi`, and to the default `gen9vgc2025regg`, which has no format config at all — so `format_config` is `None` and the overlay guard does not fire. |
| **Boundaries** | Enlarging the action space touches the live decision path: INV-1 (live-path allowlist), INV-3 (anytime/abortable) and the I8-D latency budget all bind. A ~4× space increase is exactly what the pruning bought. |

### W2 — `tailwind_both` boards: highest regret of any decision context, and depth-bound

| | |
|---|---|
| **Observed pattern** | When both sides have Tailwind up, the heuristic disagrees with the teacher on **91.97%** of decisions (126/137) at mean regret **9.19** — the worst of every `speed_control_state` bucket. Next worst with meaningful n is `tailwind_ours` at 53.96%, regret 5.57 (S1). |
| **Sources** | S1 `speed_control_state`; S2 for stability and mechanism. |
| **Affected decisions** | Fast boards where both sides outspeed their base order. 137/3302 ≈ **4.1%** of dev decisions. |
| **Mechanism (inference, but decomposed in S2 rather than guessed)** | Of 126 disagreements: **93 are move→move** (different move or target) and **33 are heuristic-attacks → teacher-switches-one**. Only a minority are Protect-spam. The dominant line is the teacher's H-step **pivot-to-best-attacker**, whose payoff accrues over later turns a one-ply resolver cannot see. |
| **Counter-evidence, actively sought and found** | A targeted fix was **already tried and failed**. An env-gated wasted-Protect penalty on fast boards moved the bucket 91.7% → 90.2% (−1.5pp on n=132, i.e. a few decisions) and made mean regret **worse**, 9.26 → 9.44 (S2). Every other bucket was frozen. This is strong evidence that the bucket is *not* reachable by one-ply valuation tuning. |
| **Strength relevance** | Regret is concentrated here, but regret is teacher-defined — see §3. |
| **Frequency** | 4.1% of decisions. Games lost: **`unknown`** — no development evidence links this bucket to game outcomes. |
| **Evidence confidence** | **High** that the pattern is real and panel-stable (full panel 92%/n=137 ≈ rain subset 91.7%/n=132). **High** that it is not valuation-tunable. **Medium** for strength relevance, per §3. |
| **Overlap** | Shares the depth-bound mechanism with W3. A depth or belief change would plausibly move both; a valuation change moves neither. |
| **Boundaries** | INV-3 (anytime/abortable) and INV-4 (one layer at a time behind an ablation gate). The I8-D 1000 ms p95 budget is the hard operational constraint on any depth increase. |

### W3 — `MUST_REACT` mode: second-highest disagreement, and the axis where the offline metric was proven backwards

| | |
|---|---|
| **Observed pattern** | In `MUST_REACT`, the heuristic disagrees on **78.85%** of decisions (425/539) at mean regret 3.37 — versus `AHEAD` 45.30% and `NEUTRAL` 51.23% (S1). |
| **Sources** | S1 `game_mode`; S3 for the lever behaviour on the same axis. |
| **Affected decisions** | 539/3302 ≈ **16.3%** of dev decisions — four times the exposure of W2. |
| **Mechanism (inference)** | `MUST_REACT` is precisely where the aggregation lever `must_react_lambda` operates, and S3 shows that axis is genuinely winrate-sensitive: ±0.2 produced ∓11.3pp symmetrically. So the mode is both high-disagreement *and* demonstrably load-bearing for outcomes. |
| **Counter-evidence** | Its mean regret (3.37) is the **lowest** of the three modes — `NEUTRAL` is 5.38 and `AHEAD` 4.32. High disagreement rate, low regret per disagreement. And this is the exact axis on which teacher preference was measured to be backwards (§3). |
| **Strength relevance** | The only weakness here with *direct* dev-winrate evidence on its own axis. But that same evidence shows the current setting is already in the direction that wins. |
| **Frequency** | 16.3% of decisions. Games lost: **`unknown`**. |
| **Evidence confidence** | **Medium.** The disagreement rate is high-confidence; its interpretation as a weakness is not, given the low regret and the demonstrated inversion. |
| **Overlap** | Overlaps W2 in mechanism (depth), and overlaps the exhausted-lever constraint below. |
| **Boundaries** | Any re-tuning here is a scalar-aggregation change — see the constraint in §5. |

### W4 — Attacking into type or ability immunities

| | |
|---|---|
| **Observed pattern** | The `IMMUNITY_PUNISHED` detector — an opponent-targeting move immediately negated by `\|-immune\|` — fired **12 times** for the baseline heuristic across a 150-seed dev archive. The reranker-override candidate on the same battles produced **6** (S5). |
| **Sources** | S5. |
| **Affected decisions** | Attack selection against a target with a relevant immunity. |
| **Mechanism (inference)** | The move-selection path does not fully account for target immunity. That the reranker roughly halved it suggests the information is learnable from features already present, i.e. the gap is in the heuristic's own scoring rather than in missing state. |
| **Detector validation — why 12 is credible and not a silent detector** | Aggregated over **both** sides the same run shows **911** `ATTACK_INTO_PROTECT` and **273** `IMMUNITY_PUNISHED` events across 150 battles, *nearly all on the p2 side* — the `max_damage` villain (S5). The detectors fire loudly on a known-reckless policy and almost never on the hero. `parse_skipped: 0` across all 300 battles. So the hero-side 12 is a low count from a working detector, not a detector that fails to fire. |
| **Counter-evidence / limits** | The v0 detector's own documented approximation: with no move-dex, "attacking move" = "targets an opponent slot", which **can over-count an opponent-targeting status move**. So 12 is an upper bound. Single archive, one opponent policy. S5 itself calls 12 vs 6 *"a directional tactical signal, not a significance claim"*. |
| **Strength relevance** | Directly wasted turns — the most legible loss mechanism in this inventory. |
| **Frequency** | 12 occurrences / 150 games ≈ **0.08 per game**, upper-bounded by the over-count caveat. Games lost: **`unknown`**. |
| **Evidence confidence** | **Medium.** Log-observed and countable, but one archive, a v0 detector, and an acknowledged over-count. |
| **Overlap** | Independent of W1–W3. |
| **Boundaries** | Touches the live decision path (INV-1). Any move-dex dependency must not reach the live path as a new heavy import. |

### W5 — Low absolute winrate against `max_damage` on the development panel

| | |
|---|---|
| **Observed pattern** | Baseline heuristic winrate vs `max_damage`: **18.0%** (S3, `must_react_lambda=0.6` baseline, n=150). Independently, **13.3%** and **17.3%** on the two arms of a later A/B (S4, n=150 each). |
| **Sources** | S3, S4. |
| **Affected decisions** | None specifically — this is a level, not a mechanism. |
| **Mechanism (inference)** | Not identified. The number is consistent across two independent slices and two configurations, so it is a property of the bot-panel-opponent triple, not of one run. |
| **Counter-evidence / limits** | **Opponents are `max_damage` only**, on dev cells (trickroom / sun / rain) (S4 caveats). `max_damage` is not a weak opponent in every matchup, and the panel has only 4 archetypes with a coarse LOTO test (S10). This is not a ladder-strength statement. |
| **Strength relevance** | High as a *level* signal: it bounds how much headroom exists. |
| **Frequency** | Not applicable. |
| **Evidence confidence** | **High** for the measurement, **low** for any causal reading. It tells us the bot loses most of these games; it does not tell us why. |
| **Overlap** | Aggregate of everything, including causes not in this inventory. |
| **Boundaries** | Must never be quoted as a ladder or held-out strength statement. |

---

## 5. Constraints on any solution — not weaknesses, but binding

**C-a — global scalar aggregation tuning is exhausted on the development side.** Dev-side only
(S3, S9 dev column): `must_react_lambda` is monotonic and symmetric at ±11.3pp, so the current
setting already sits in the winning direction; `risk_lambda` 0.5→0.75 was an outright **−12.67pp**
dev regression. A further global scalar tweak is not an untried lever.

**C-b — the offline teacher metric cannot be used as the acceptance gate.** §3. It can aim work; it
cannot judge it.

**C-c — two plausible weaknesses were looked for and NOT found.** `ATTACK_INTO_PROTECT` = **0**
and `PANIC_SWITCHING` = **0** on the baseline heuristic across the 150-seed archive, and S5 states
it directly: *"the heuristic already avoids attacking into Protect and does not panic-switch"*.
This is not a silent-detector artifact — the same detectors recorded 911 and 273 events on the
opponent side of the same battles. Whatever is wrong, on that archive it is not these two.
Reported because absent evidence against a plausible hypothesis is worth as much as evidence for
one, and because "the bot Protect-spams" is the intuition this repository's own data contradicts.

**C-d — Protect-spam is a minority mechanism in the worst bucket.** S2's decomposition: 93 of 126
`tailwind_both` disagreements are move→move, not Protect. A Protect-focused fix addresses the
minority, and one was already tried and failed (W2).

---

## 6. Ranking by expected strength relevance

Ranked on **development evidence only**. This is a weakness ranking, not a solution choice.

| Rank | Weakness | Evidence confidence | Implementation effort | Regression risk | Exposure |
|---|---|---|---|---|---|
| 1 | **W4** immunity-punished attacks | Medium | **Low–Medium** — scoring change, no new state | **Low** — narrow, testable, no search-space change | 0.08/game (upper bound) |
| 2 | **W2** `tailwind_both` depth-bound gap | Medium (High for the pattern) | **High** — needs depth or belief, not tuning | **High** — INV-3, INV-4, I8-D latency budget | 4.1% of decisions |
| 3 | **W1** Tera never enumerated | High (structural) / Unknown (impact) | **Medium–High** — ~4× action space | **High** — live path, latency, INV-1/INV-3 | Unknown; **zero on the Champions format** |
| 4 | **W3** `MUST_REACT` disagreement | Medium | Low if scalar — but see C-a | Medium — the axis is proven winrate-sensitive in both directions | 16.3% of decisions |
| 5 | **W5** low absolute dev winrate | High (measurement) / Low (causal) | Not actionable directly | — | Whole panel |

### Why this order

**W4 first, despite being the smallest number.** It is the only item whose loss mechanism is
directly observable in battle logs rather than inferred from a teacher, so it is the one item §3's
inversion caveat does not touch. It is also the cheapest to attempt and the easiest to falsify —
the detector that found it can measure whether a fix removed it. Ranking it first is a statement
about *evidence quality and testability*, not about expected effect size, which is unknown.

**W2 second.** The strongest and most stable pattern in the inventory, with a mechanism already
decomposed and a failed fix already recorded — that failure is itself valuable, because it rules
out the cheap explanation. It ranks below W4 only because its evidence is teacher-derived and its
remedy is expensive and risky.

**W1 third.** Highest evidence confidence of all — verified in today's code, not inferred. It ranks
third only because its impact is genuinely `unknown` and because it is **moot on the format the
front-track currently runs**. If the front-track moves to a Tera-enabled format, this should move
up.

**W4 above W3 despite W3's four-times-larger exposure.** W3 has the lowest mean regret of the three
game modes, sits on the one axis where the offline metric was *measured* to point the wrong way,
and its obvious remedy is the scalar tuning that C-a marks exhausted. Exposure alone does not make
a weakness actionable.

**W5 last**, because it is a level rather than a mechanism. It belongs in the inventory as the
headroom bound, not as something to fix.

---

## 7. Open evidence gaps

These are gaps demonstrated by the sources, not speculation.

1. **No dev-generalization panel exists as run data.** S10 states it plainly: the analyzer and
   planner exist, the actual matrix does not. Every number above comes from a panel with **4
   archetypes** and a coarse LOTO test.
2. **One opponent policy.** Every dev-strength number is versus `max_damage` (S4). No development
   evidence describes behaviour against a varied opponent population.
3. **No decision→outcome attribution anywhere.** Not one source links a decision bucket to games
   won or lost. This is why every **games-lost** figure above is `unknown`. Where a `Frequency` row
   does carry a number it is an *exposure or occurrence count* derived by arithmetic from exact
   counts in the source — 137/3302, 539/3302, 12 events over 150 games — never an attributed loss
   and never an estimate. A games-lost figure could be manufactured from disagreement counts, and
   it would be fiction.
4. **Diagnostics cover 3 of ~30 taxonomy buckets** (S5). Belief, damage-roll, recovery and
   joint-action buckets need capabilities that do not exist yet.
5. **No live-path evidence exists at all.** #125 landed the recording only on 2026-07-29 (S14).
   Exactly one battle has been recorded, and it was a smoke run in a format with no spread book,
   so every decision in it is `not_applicable`. The first real ladder evidence is still to come.
6. **The Tera export gap blocks its own measurement** (S6). Tera'd decisions are dropped from the
   dataset, so the dataset cannot quantify W1.

---

## 8. Non-claims

- **No causal claim.** Nothing here establishes that any listed weakness *causes* losses. Every
  frequency is exposure or occurrence count, never attributed loss.
- **No strength-improvement claim.** No fix is proposed, and no fix is asserted to help. A weakness
  being real does not make its remedy positive.
- **No implementation authorisation.** This audit authorises nothing. Candidate comparison and
  selection are #128.
- **No use of the sealed holdout.** No Gate B result, game ID, cell result, p-value, effect size,
  direction or derived diagnostic appears above. The older T6 held-out results were excluded on the
  same principle.
- **No ladder or generalisation claim.** Every number is development-panel, `max_damage`-only.
- **The ranking is evidence-based, not effect-size-based.** Where effect size is unknown it is
  written `unknown`. Rank 1 is not a prediction that W4 is the largest problem — it is a statement
  that W4 is the best-evidenced and most falsifiable one.

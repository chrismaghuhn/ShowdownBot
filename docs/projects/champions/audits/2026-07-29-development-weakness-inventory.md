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
| S14 | `docs/projects/champions/reports/2026-07-29-live-path-degradation-closeout.md` | Technical / operational | Live-path recording landed; **one** battle recorded (a smoke), none of it applicable to weakness analysis — see gap 5 |
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

Measured on the same lever, same panel, from a baseline of 0.6: `must_react_lambda` **0.3**
(a step of −0.3) → **−11.3pp**, and **0.8** (a step of +0.2) → **+11.3pp**. What is symmetric is the
*winrate delta*, not the parameter distance — the steps are unequal and the outcome deltas came out
equal and opposite anyway, which is what makes the monotonicity notable rather than a coincidence
of spacing. The offline probe had preferred the losing direction.

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

**Four weaknesses (W1, W2, W4, W5) and one contested surface (C1).** C1 is listed here because
the evidence about it is real and worth recording, but it is deliberately not counted as a
weakness and does not appear in §6a — see its own entry for why.

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
| **Scope limit that a solution must respect** | `gen9championsvgc2026regma` sets `tera: false` (S8), and `_maybe_tera` returns early on it. **On the current Champions front-track format this weakness is moot.** It applies to the Tera-enabled configured formats, `gen9vgc2024regg` and `gen9vgc2025regi`. **Correction:** an earlier revision of this audit reasoned that the default `gen9vgc2025regg` also exercises the overlay, because it has no format config and so the guard cannot fire. That is a non-sequitur, and the code says the opposite — with no format config `_get_book` returns `None` (`runner.py`), so `handle_battle_message` takes the `else` branch to `choose_for_request`, which `decision.py:138` documents as the *"legacy random agent"*. `choose_with_fallback` is never called and `_maybe_tera` is never reached. A guard that does not fire on an unreachable path proves nothing. |
| **Boundaries** | Enlarging the action space touches the live decision path: INV-1 (live-path allowlist), INV-3 (anytime/abortable) and the I8-D latency budget all bind. A ~4× space increase is exactly what the pruning bought. |

### W2 — `tailwind_both` boards: highest regret of any decision context, and depth-bound

| | |
|---|---|
| **Observed pattern** | When both sides have Tailwind up, the heuristic disagrees with the teacher on **91.97%** of decisions (126/137) at mean regret **9.19** — the worst of every `speed_control_state` bucket. Next worst with meaningful n is `tailwind_ours` at 53.96%, regret 5.57 (S1). |
| **Sources** | S1 `speed_control_state`; S2 for stability and mechanism. |
| **Affected decisions** | Fast boards where both sides outspeed their base order. 137/3302 ≈ **4.1%** of dev decisions. |
| **Mechanism (inference, but decomposed in S2 rather than guessed)** | Of 126 disagreements: **93 are move→move** (different move or target) and **33 are heuristic-attacks → teacher-switches-one**. Only a minority are Protect-spam. The dominant line is the teacher's H-step **pivot-to-best-attacker**, whose payoff accrues over later turns a one-ply resolver cannot see. |
| **Counter-evidence, actively sought and found** | A targeted fix was **already tried and failed**. An env-gated wasted-Protect penalty on fast boards moved the bucket 91.7% → 90.2% (−1.5pp on n=132, i.e. a few decisions) and made mean regret **worse**, 9.26 → 9.44 (S2). Every other bucket was frozen. This is one intervention at one value; S2's own caveat says a larger penalty is not expected to help *because the mechanism decomposition shows the gap is dominated by non-Protect disagreements* — that reasoning, not the single A/B, is what carries the depth hypothesis. |
| **Strength relevance** | Regret is concentrated here, but regret is teacher-defined — see §3. |
| **Frequency** | 4.1% of decisions. Games lost: **`unknown`** — no development evidence links this bucket to game outcomes. |
| **Evidence confidence** | **High** that the pattern is real and panel-stable (full panel 92%/n=137 ≈ rain subset 91.7%/n=132). **Medium** on the depth hypothesis: what is demonstrated is that *this* intervention — one wasted-Protect penalty at one value, −3.0 — did not move the bucket, which is consistent with the depth explanation and with S2's mechanism decomposition but does not prove the whole bucket is beyond every valuation change. **Medium** for strength relevance, per §3. |
| **Overlap** | Independent of C1, and an earlier revision was wrong to link them. It claimed both share a depth mechanism and that "a valuation change moves neither" — but C1's own source records a *scalar valuation* change moving that surface by ±11.3pp. The two behave oppositely under the same class of intervention, which is the opposite of a shared mechanism. |
| **Boundaries** | INV-3 (anytime/abortable) and INV-4 (one layer at a time behind an ablation gate). The I8-D 1000 ms p95 budget is the hard operational constraint on any depth increase. |

### C1 — `MUST_REACT`: a load-bearing, contested decision surface — **not a demonstrated weakness**

Reclassified. An earlier revision of this audit ranked this first among weaknesses. That was wrong,
and the correction matters more than the ranking: **what is measured here is that the axis is
winrate-sensitive and that the shipped direction beats the tested alternative below it. Neither
fact establishes a defect in the current bot.** Mode frequency plus parameter sensitivity is not
evidence of a weakness. It is labelled `C1` rather than `W6` so it is not counted as one.

| | |
|---|---|
| **Observed pattern** | In `MUST_REACT`, the heuristic disagrees with the teacher on **78.85%** of decisions (425/539) at mean regret 3.37 — versus `AHEAD` 45.30% and `NEUTRAL` 51.23% (S1). It is 539/3302 ≈ **16.3%** of dev decisions. |
| **Sources** | S1 `game_mode`; S3 for the lever behaviour on the same axis; `policy.py:17` for the shipped default. |
| **Why this is not a demonstrated weakness** | The high disagreement rate comes from the teacher, and §3 shows the teacher's preference on **this exact axis** was measured pointing the wrong way. So the one per-decision error indicator available here is the one indicator known to invert here. Removing it leaves mode frequency and parameter sensitivity, and neither says the current policy is choosing badly. |
| **What IS established** | The axis moves outcomes. From the shipped baseline 0.6: **0.3 → −11.3pp**, **0.8 → +11.3pp** (S3). Aggregation weighting in `MUST_REACT` is load-bearing for winrate, not cosmetic. |
| **A development-side fact worth recording** | The shipped default is still **0.6** (`policy.py:17`, `SHOWDOWN_MUST_REACT_LAMBDA` default). The dev-measured better value, 0.8, is **not** the shipped one. **Why it was not adopted rests on evidence this audit excludes**, so no conclusion about that is drawn here — only the code fact is recorded. |
| **Counter-evidence** | Its mean regret (3.37) is the **lowest** of the three game modes — `NEUTRAL` 5.38, `AHEAD` 4.32. High disagreement rate, low regret per disagreement. |
| **Evidence confidence** | **High** that the axis is winrate-sensitive. **Low** that current `MUST_REACT` play is defective — that claim has no clean supporting evidence in this repository. |
| **Overlap** | Distinct from W2. See the correction under W2's overlap row: this surface responded strongly to a scalar valuation change, which is exactly what W2's bucket did not. |
| **Boundaries** | Any move here is a scalar-aggregation change — see C-a. |

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
| **Overlap** | Independent of W1, W2 and C1. |
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

**C-a — global scalar aggregation tuning is a well-explored lever on the development side.**
Dev-side only (S3, S9 dev column): from baseline 0.6, `must_react_lambda` at 0.3 and 0.8 produced
−11.3pp and +11.3pp — equal and opposite winrate deltas from unequal parameter steps, i.e.
monotonic over the tested range; `risk_lambda` 0.5→0.75 was an outright **−12.67pp** dev
regression. The current setting already sits on the winning side of the tested range. A further
global scalar tweak is not an untried lever.

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

## 6. Ranking

Two separate questions, kept separate on purpose. An earlier revision merged them and was wrong to:
it ranked by "expected strength relevance" while its stated reasons were evidence quality,
testability, effort and regression risk. Those are #128's selection criteria, not #127's.

**Four weaknesses are ranked. `MUST_REACT` is not among them** — it was demoted to C1, a contested
surface, because mode frequency plus parameter sensitivity does not establish a defect in the
current bot, and the only per-decision error indicator on that axis is the one indicator measured
to invert there.

### 6a. Ranking by expected strength relevance — this is what #127 asks for

Ranked **only** on what the development evidence suggests is at stake in strength terms: exposure,
concentration of regret, and any measured link to winning or losing. Effort, risk and testability
are deliberately **not** inputs here.

| Rank | Weakness | Exposure | What the evidence says is at stake | Evidence confidence |
|---|---|---|---|---|
| 1 | **W2** `tailwind_both` | 4.1% of decisions | Highest mean regret of any bucket — **9.19** against 5.57 for the next-largest — and stable across two independent panel subsets | Medium (High for the pattern) |
| 2 | **W5** low absolute dev winrate | Whole panel | Bounds total headroom: ~18% vs `max_damage` means most of the panel is lost | High (measurement) / Low (causal) |
| 3 | **W1** Tera never enumerated | `unknown`; **zero** on the front-track format | A once-per-battle strategic resource sits outside the search space — magnitude unmeasured | High (structural) / Unknown (impact) |
| 4 | **W4** immunity-punished attacks | 0.08/game (upper bound) | Directly wasted turns, but the smallest measured occurrence rate here | Medium |

**Why this order.**

**W2 first.** It is the largest concentration of measured regret anywhere in the atlas, and the only
weakness verified stable across two independent subsets (full panel 92%/n=137, rain subset
91.7%/n=132). Its ceiling is set by §3: the regret is teacher-defined and nothing links it to game
outcomes, so "highest regret" is not "most games lost".

**W5 second.** It bounds how much strength is available to recover at all, which is real relevance —
but it names no mechanism, so it cannot be acted on directly. It ranks above W1 because it is
measured on the whole panel while W1's magnitude is unmeasured.

**W1 third**, despite carrying the highest evidence confidence in the inventory. Confidence in a
*structural fact* is not strength relevance: the impact is `unknown`, the dataset that would measure
it drops exactly the rows needed, and **on the format the front-track actually runs the weakness
does not exist**. If the front-track moves to a Tera-enabled format this should move up.

**W4 last on relevance.** 0.08 occurrences per game is the smallest quantified effect here. That it
ranks last on this axis and first on the next is the most useful single fact in this audit.

### 6b. Suggested investigation order — NOT a ranking of strength relevance, NOT a selection

Input to #128, explicitly **not** an answer to #127. It reorders 6a by tractability: how good the
evidence is, how cheaply a hypothesis can be tested, and what a wrong answer would cost. **Nothing
here selects a candidate or authorises work.**

| Order | Item | Evidence quality | Implementation effort | Regression risk | Falsifiable how? |
|---|---|---|---|---|---|
| 1 | **W4** | Log-observed, not teacher-derived | Low–Medium — scoring change, no new state | **Low** — narrow, no search-space change | The detector that found it can measure whether a fix removed it |
| 2 | **W2** | Teacher-derived, but panel-stable and mechanism-decomposed | High — depth or belief, not tuning | **High** — INV-3, INV-4, I8-D latency budget | Atlas bucket re-measure; but see §3 on that metric |
| 3 | **C1** *(contested surface, not a weakness)* | Winrate-measured on its own axis; no clean defect evidence | Low if scalar — but see C-a | Medium — the axis moves winrate in both directions | Paired dev A/B, the method already used on it |
| 4 | **W1** | Structural, verified in today's code | Medium–High — ~4× action space | **High** — live path, INV-1/INV-3, latency | Hard: the dataset drops Tera'd decisions, so its own measurement is blocked |
| 5 | **W5** | High as a measurement | Not directly actionable | — | Not applicable — it is a bound, not a lever |

C1 appears here and not in 6a on purpose: it is tractable to investigate precisely *because* its axis
is winrate-measurable, while remaining unproven as a defect. Tractability and relevance are
different questions, and this is the clearest case of the two coming apart.

**The disagreement between 6a and 6b is the finding, not a flaw.** W4 is last on strength relevance
and first on tractability. Whether to attack the largest measured effect or the best-evidenced one
is a judgement about method and risk appetite — it belongs to #128, with the tension stated rather
than hidden inside a single blended number.

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
5. **No *applicable* live-path evidence exists.** Live-path recording landed only on 2026-07-29
   (S14), and exactly one battle has been recorded. That smoke run **is** live-path evidence and it
   validated the recorder — but it is not usable for weakness analysis: it ran
   `gen9randomdoublesbattle`, which has no spread book, so the heuristic path was never entered and
   all 14 decisions are `not_applicable` with `is_degraded: null`. No real ladder or challenge
   evidence exists yet.
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
- **`MUST_REACT` is not claimed as a weakness.** It is recorded as C1, a contested surface. The
  audit states what is measured — the axis moves winrate — and states plainly that this does not
  establish a defect in the current policy.
- **Two rankings, and only one of them answers #127.** §6a ranks by expected strength relevance
  and is the deliverable. §6b reorders by tractability and is **input to #128, not an answer to
  #127 and not a selection**. They disagree — W4 is last on relevance and first on tractability —
  and that disagreement is reported rather than blended into one number.
- **Where effect size is unknown it is written `unknown`.** No rank position asserts a magnitude
  that the evidence does not carry.

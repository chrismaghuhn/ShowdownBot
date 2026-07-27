# Gate B — justified repeat on a consumed holdout budget

**Status:** DECIDED (owner), 2026-07-27. Written and committed **before** any run of the new
attempt exists.
**Scope:** this note records a *reason*. It runs nothing, freezes nothing, and authorises nothing.
**Champions Strength remains NO-GO.**

The strength holdout carries a one-attempt budget per configuration. Ledger entry 6
(`purpose: champions-strength-holdout-v0`, `config_hash 594295543f13a55d`) is consumed and carries
`justification: null`. A second attempt on that same `config_hash` is therefore a *repeat*, and a
repeat is only legitimate if the reason is written down in advance and can be judged later. This is
that reason.

## 1. The ledger string

The combine CLI's `--ledger-justification` must be passed exactly this string. It is quoted here
verbatim so the ledger entry and this note cannot drift apart:

```
repeat after fail-closed SAFETY-FAIL that rendered no strength verdict; defect fixed and live-verified; schedule/panel/teams/thresholds unchanged — rationale: docs/projects/champions/decisions/2026-07-27-gate-b-justified-repeat.md
```

If the owner rewords it, the shipped string and the block above must be updated together.

## 2. Trigger

The consumed attempt ended in a **fail-closed SAFETY-FAIL**, not in a disappointing result:

- `invalid_choices` — Arm A (heuristic, the candidate) = **1**, Arm B (max_damage, the baseline) = **0**
- one illegal action across 180 seed-fixed holdout matchups
- frozen at `git_sha bc2d6df1fcfa61c7a8bda9fe52a6899f93d27aee`, `candidate_identity 32f79b8e52444aa3`

An illegal move is a correctness defect. It is not a signal that the candidate is weak, and it is
not a number anyone could have wanted to improve.

## 3. Why this is not "iterate until the holdout passes"

This is the load-bearing argument, and it rests on how the gate is built rather than on intent.

Gate B evaluates safety **before** it renders a strength verdict, and a safety failure
short-circuits the strength claim on every axis — including the p-value.
`render_strength_holdout_verdict` records `exact_p=(exact_p if safety_pass else None)`, and the
frozen combine verdict shows exactly that: `safety_pass: false`, `exact_p: null`,
`verdict: "SAFETY-FAIL"`.

So for this holdout **no strength verdict was ever produced**. The strength question is
**unanswered**, not *answered unsatisfyingly*. The one-attempt budget exists to stop a team from
re-rolling a holdout until the answer is the one they wanted; there is no answer here to be
dissatisfied with, and therefore nothing to re-roll toward.

That distinction is what makes this repeat defensible, and it is also the boundary: a second
SAFETY-PASS run that returns a null or unfavourable strength result would be an **answer**, and a
third attempt on the same configuration would not have this argument available to it.

## 4. What changed between the attempts

Exhaustively, and none of it touches how the bot chooses a move in a legal position:

**The B1 legality fix** — the defect itself. `_voluntary_switches` now treats a slot's
`maybeTrapped` flag the way the server means it: for an ability trap the server reports
`maybeTrapped` purely so it does not leak which foe ability is trapping, but the Pokémon really is
trapped, so offering a switch there is an illegal action rather than a probe. The guard is on the
**voluntary** switch path only; the **forced** replacement path after a faint is still legal while
trapped and is deliberately untouched.

That fix is **CONFIRMED live-effective**, not merely reviewed. A clean A/B on throwaway teams with
no holdout content, calc proven answering in both runs:

| run | `invalid_choices` | `maybeTrapped` occurrences | Mega surface |
|---|---|---|---|
| pre-B1 (`bc2d6df` loaded) | **5 / 30** | 46 in 29 logs | 30 / 30 battles |
| B1 loaded | **0 / 30** | 49 in 29 logs | 30 / 30 battles |

The adversarial surface was exercised in both arms — that matters, because a bare
`invalid_choices = 0` from a run that never produced the legality surface proves nothing.

**Two verdict-integrity fixes.** Calc degradation is now visible, per-seat and fail-closed (before,
a dead calc backend could silently produce clean-looking rows); and `invalid_choices` is gated
**per seat** instead of summed, so one seat's violation can no longer be diluted by the other's
clean record.

**The seed-log preflight**, plus test-only guards.

**No threshold, schedule, panel, team, baseline, or decision-behaviour change.** Stated explicitly
because it is the claim that makes the repeat comparable at all: the new attempt faces the same
sealed teams, the same schedule, the same thresholds and the same baseline as the consumed one.

## 5. Contamination assessment

Honest version, including the part that does not help.

**What is known from the consumed attempt.** The descriptive paired numbers are known and are
recorded in frozen evidence: `n_total = 180`, `n_discordant = 100`, `delta = +0.044444`, raw
head-to-head heuristic 89 wins / max_damage 81 wins, `exact_p: null`. Whoever writes the next fix
has seen these. Pretending otherwise would be the defensive version of this section.

**Why the fix is nonetheless not derived from them.** The B1 defect was diagnosed from **one
battle's frozen server log** plus static analysis of the switch-enumeration code, and the repair is
a pure legality guard: it removes an illegal option from an enumeration. There is no threshold, no
weight and no tunable in it. It cannot be aimed at a holdout outcome, because it does not express a
preference between legal actions — it only stops one illegal action from being offered.

**Residual risk.** Small, not zero. The descriptive numbers were visible to the people who chose
what to fix, and "which defect do we chase first" is a decision that visibility can influence, even
when the fix itself is untunable. This note does not argue that risk away; it records it so a later
reader can weigh it.

## 6. Independence of the holdout set

The sealed holdout set was manually reviewed for near-duplicate overlap against the dev panel and
the engineered coverage teams, and **ACCEPTED** by the owner (disjointness review,
`docs/projects/champions/audits/2026-07-23-gate-b-holdout-near-duplicate-disjointness-review.md`,
sign-off recorded 2026-07-23; PR #56).

The acceptance carries a recorded caveat that belongs here too, because it constrains how any
strength result from this holdout may be read: **`H4` and `H5` are species-identical** (the only
off-diagonal pair at Jaccard 1.0). Effective **archetype** diversity is therefore about **5, not
6**, and that archetype occupies 2 of 6 teams — **60 of the 180 schedule battle-keys, one third**
of the strength schedule, effectively double-weighted. This is an interpretation caveat, not a
leakage finding.

## 7. Pre-registered expectation

Recorded now, before the run, because a null result must not later be re-read as a reason for a
third attempt.

Carrying the consumed attempt's descriptive numbers forward (`n_discordant = 100`, `delta =
+0.044444` over 180 ⇒ `n10 = 54`, `n01 = 46`), the two-sided exact binomial McNemar p-value would
be **p ≈ 0.4841**.

**The expected outcome of the new attempt is therefore a valid but most likely NON-significant
verdict.** That is what this repeat is for: converting an unanswered question into an answer, not
into a favourable answer. A null result is the *expected* outcome and is **not** grounds for a
third repeat on this configuration.

> **Correction, 2026-07-27 (appended; the section above is left as written).** The projection above
> **cannot stand as a calibrated expectation** for the new attempt.
>
> It was built by carrying forward the descriptive numbers of the `bc2d6df` run. Those numbers are
> now known to come from a run contaminated by the mega-reconcile defect — in **59 of 180 battles
> in Arm A and 57 of 180 in Arm B**, decisions fell to the blind chooser on both seats. See
> `docs/projects/champions/audits/2026-07-27-mega-reconcile-actor-mismatch-diagnosis.md` §5. Inputs
> from roughly a third of the battles are not what either arm's policy produced, so a projection
> resting on them cannot calibrate anything.
>
> **What this does NOT say, precisely.** No measured p-value was invalidated, because there never
> was one: the frozen combine verdict carries `exact_p: null` — the SAFETY-FAIL short-circuits the
> strength statement on every axis — and the section above says the p-value "would be", marking it
> as the recomputation it is. What is unusable is a *projection from contaminated inputs*, not a
> measurement that turned out wrong.
>
> **No replacement, and no direction.** This correction derives no new p-value, no corrected point
> estimate and no revised expectation: the same contaminated run cannot support one either. It
> carries no directional claim — "the prior projection is unusable" means neither that a larger
> effect is now plausible nor that a smaller one is. The new attempt is simply un-predicted.
>
> **The commitment stands, unchanged.** A null result is still **not** grounds for a third repeat
> on this configuration. That commitment never rested on the projection: it follows from §3 — the
> repeat is justified because the strength question was left *unanswered* by a fail-closed
> SAFETY-FAIL, and any valid verdict, null included, is an **answer**. Removing the calibration
> does not remove the argument. Read the closing sentence above accordingly: the word *expected*
> in it no longer carries any calibration — per "the new attempt is simply un-predicted" above,
> what survives there is the **commitment** (no third repeat), never a surviving **prediction**.
>
> **Scope.** This correction touches §7 only. §5's contamination assessment and its residual-risk
> passage remain true exactly as written — they describe what was *known* to whoever chose the fix
> and how *visible* it was, not what the numbers predict. Nothing here invalidates the rest of the
> document.

## 8. This authorises nothing

The run still requires, each separately authorised by the owner:

1. the **full three-gate sequence** — I8-D → coverage → combine,
2. on **one fresh candidate identity**,
3. with **no commits between** the gates.

I8-D currently stands at FAIL (p95 1110.213 ms > the 1000 ms budget), so the sequence cannot start
until the latency-reduction slice lands and I8-D is repeated unchanged under its own authorisation.

> **Correction, 2026-07-27 (same day, before any run).** The paragraph above is **wrong** and is
> left standing rather than rewritten, because this note is a pre-registration and silently editing
> it would defeat the point.
>
> `p95 1110.213 ms / FAIL` was the **first** of four I8-D runs. The frozen evidence records:
> `i8d-live` FAIL 1110.213 ms → `i8d-live-post-lever-a` FAIL 1160.515 ms → `i8d-live-post-lever-b`
> **PASS** 850.245 ms → `i8d-live-post-coverage-harness` **PASS** 864.940 ms (merged, PR #39); the
> I8-D run accompanying the Gate B attempt also PASSed at 873.762 ms (external, unfrozen). The
> latency-reduction work (Lever A, Lever B) has long since landed, and the 1000 ms blocker is
> **closed** for the candidates that were measured.
>
> **The conclusion survives, for a different reason.** An I8-D PASS binds to the candidate identity
> that produced it and does not transfer to a new `git_sha` (the approved spec's shared-candidate-
> identity requirement). Every PASS above belongs to an earlier candidate. The current candidate
> therefore has **no I8-D result at all** — the blocker is an *unestablished* latency precondition,
> not a failed one, and the sequence still begins with a fresh, separately authorised I8-D run.

> **Completion note, 2026-07-27 (a second, separate correction — appended, nothing above
> reworded).** The block above lists four I8-D runs plus the external 873.762 ms PASS. There is a
> **fifth**, and leaving the understatement standing in a pre-registration is worse than a longer
> record: `i8d-live-post-guard-hardening`, **p95 890.6084999907762 ms — PASS** against the 1000 ms
> budget, frozen on the `evidence/i8d-live-0390668` branch (60 active-valid decisions from 45
> distinct battles, `stop_reason=exposure_floor_met`, `seed_log_verified`).
>
> It strengthens rather than changes the block's conclusion: **five** recorded I8-D runs, the last
> three of them PASSes, and the 1000 ms blocker is closed for every candidate that was measured.
> The reason the sequence must still begin with a fresh I8-D run is unchanged and is not about
> latency at all — that PASS binds to candidate identity `111cf0d16a4f8a59`, and several commits
> have moved `git_sha` since.

## 9. Pre-registration attestation

This note was written and committed **before** any run of the new attempt. At the time of writing,
no result of the new attempt exists.

The code cannot enforce that ordering. Nothing in the combine CLI checks whether a justification
was authored before or after the run it justifies — `--ledger-justification` accepts any string at
any time. This is therefore a **process commitment**, not a technical guarantee, which is exactly
why it is committed in advance: the commit timestamp and the absence of any new run artifact at
that commit are the only evidence a later reader will have.

# #128 — prioritisation design: correctness slices, not heuristic weights

**Issue:** #128 · **Base:** `main @ 34bc98dc` · **Date:** 2026-07-29
**Type:** design. No production code is changed by this document and none is authorised by it.

---

## 1. What changed about #128, and why

#128 was written to score weaknesses by "estimated games recovered, implementation effort, risk of
regression" and return improvement candidates. On the evidence now on `main` that framing does not
survive contact with two facts.

**Fact 1 — the outcome metric #128 was going to score with does not exist.**
"Games recovered" is not derivable from anything in this repository. §7 gap 3 of the #127 inventory
states it without hedging: *"No decision→outcome attribution anywhere. Not one source links a
decision bucket to games won or lost … A games-lost figure could be manufactured from disagreement
counts, and it would be fiction."* Gap 5 adds that the only live-path evidence on `main` is a single
smoke battle on `gen9randomdoublesbattle`, whose 14 decisions are all `not_applicable`. Any number
in that column would be invented, so this document has no such column — §4 states that as a binding
constraint on the ranking.

**Fact 2 — the decision path contains confirmed defects that would corrupt any candidate
evaluation run through it.**
[`2026-07-29-static-correctness-audit.md`](../audits/2026-07-29-static-correctness-audit.md)
confirms **24 independent defects** on `main @ 34bc98dc`, of which **13 are on the decision path,
current-panel exposed, and reachable on the shipped default configuration** — among them: turn order
ignores abilities, secondary-chance flinch is guaranteed, unresolved status is applied anyway,
screens do not exist, Fake Out freshness is wrong, own abilities never reach state, switch destroys
combatant knowledge, and an `adjacentAlly` move can emit an illegal choice.

Tuning a weight against that path measures the weight *and* the defects together, and cannot
separate them. Correctness is therefore not a competitor to the weakness work — it is a
precondition for being able to read it.

**#128's outcome is restated:** a reasoned shortlist of **two to three correctness slices**, ranked,
with rationale. Not weights, not thresholds, not heuristic tuning.

### Explicit relation to #127

#127 is unaffected. Its inventory answers *where the recorded development evidence says games are
lost*; this document answers *what must be true of the code before any such candidate can be
measured*. Neither replaces the other, and no finding in the static audit revises W1/W2/W4/C1/B1.
The weakness work resumes after the correctness precondition is met — that sequencing is the whole
of the change.

---

## 2. Scope

### In scope

Workstreams **A**, **B** and **C** from the static audit's §7, and only those:

| WS | Scope |
|---|---|
| **A — State truth** | persistent combatant identity; ability / item / move / HP knowledge; dynamic action order |
| **B — Legal actions & authoritative transitions** | legality, switch execution, one shared transition contract |
| **C — Resolved move effects** | move and ability effects that are format- and panel-relevant today |

### Out of scope, and staying out

| WS | Why it is not ranked here |
|---|---|
| **D — Depth-2 correctness** (items 10, 11) | requires `SHOWDOWN_SEARCH_DEPTH >= 2`, which defaults to 1 (`battle/decision.py:66-72`). Off by default, stays off, and stays a separate track. Nothing here activates Depth 2. |
| **E — Runner / operations** (items 4, 5, 6, 7, 12, 13) | reliability and lifecycle, not decision correctness. Own track. Item 12 is genuinely blocking for multi-battle live evidence, which is an argument for scheduling that track — not for merging it into this one. |

A, B, C, D and E are not to be combined into one slice. That separation is the point of the
workstream split.

### Non-goals

- No production code change.
- No new battle, gauntlet or experiment.
- No access to sealed Gate B holdout results, and none used.
- No strength or production-readiness claim.
- No activation of Depth 2.
- No merging of correctness, search and operations slices.
- No implementation before this document and the static audit are reviewed and approved.

---

## 3. Candidate slices

Five candidates, formed by grouping confirmed findings along their actual dependency and contract
boundaries rather than by finding count. (A sixth, S4, was dissolved in review — see below. The
identifiers S1–S3, S5, S6 are kept stable so review history stays readable.)

| ID | Slice | Findings | Blockers covered | Workstream |
|---|---|---|---|---|
| **S1** | Persistent combatant state + dynamic action order | 3, 8, 15, 20, 23 | 3, 8, 15, 20, 23 | A |
| **S2** | Legal action + authoritative switch transition | 1a, 1b, 1c, 9, 22 | 1b, 9 | B |
| **S3** | Resolved effects + attacker-aware mechanics and calc binding | 2, 14, 16, 17, 24-residual, 25 | 2, 14, 16, 17, 24, 25 | C |
| **S5** | Ally targeting only (1a–1c, carved out of S2) | 1a, 1b, 1c | 1b | B |
| **S6** | Screens as a standalone state + calc binding (carved out of S3) | 17 | 17 | C |

S5 and S6 are deliberately narrow carve-outs, considered so the shortlist is a choice and not a
restatement of the grouping.

### Closure against the audit's blocker set — corrected in review

An earlier revision of this document had a sixth candidate, **S4** ("attacker-aware mechanics and
calc binding": items 2, 21, 25), which was then excluded from the shortlist as "folding into S1 and
S3". That was wrong twice over: the fold was asserted rather than performed, and it dropped **items
2 and 25 — both on the audit's 13-defect blocker list — out of the shortlist entirely**. A
prioritisation that leaves two of its own stated blockers unassigned does not close its correctness
boundary.

**S4 is dissolved and its findings are placed explicitly:**

- **Item 2** (`hits_foe` omits `any`, so Protect never blocks an `any` move) → **S3**. It is a
  Protect-predicate question and belongs with the resolved-effect contract, not in a separate slice.
- **Item 25** (current HP absent from calc requests) → **S3**. Its repair is the *same seam* as item
  17's: both add fields the pinned `@smogon/calc` already accepts but `CalcMon.to_payload()` /
  `showdown_bot/tools/calc/calc.mjs` do not send. S3 is therefore defined to include the calc-binding
  half, which is why its title now names it.
- **Item 21** (Unseen Fist vs Protect) → **explicitly deferred**, not folded. It is the one member
  of former S4 that is *not* a blocker: no Urshifu on the hero or dev panel teams. It must be
  repaired before Urshifu appears in strength evidence, and it is recorded here as a named,
  out-of-shortlist item rather than silently dropped.

**Closure check.** The audit's 13 blockers are 1b, 2, 3, 8, 9, 14, 15, 16, 17, 20, 23, 24, 25.
S1 covers 3, 8, 15, 20, 23 · S2 covers 1b, 9 · S3 covers 2, 14, 16, 17, 24, 25. Union = all 13, with
no blocker assigned twice and none left over. Non-blocking findings 1a, 1c and 22 ride along inside
S1–S3; only item 21 sits outside, deliberately and by name.

---

## 4. Ranking by strength relevance

**Inputs — the five approved axes, unchanged:** current Champions/panel exposure; **decision
frequency**; error severity (how wrong the modelled result is when it fires); concentration of
possible regret; and any existing development-outcome link.

**Effort, dependencies, testability, regression risk and reversibility are not inputs to this
ranking.** They are §5. A slice does not move up because it is easy or down because it is risky.

There is no `games recovered` column and there will not be one: §1, Fact 1.

### `decision frequency` is `unknown`, and it is not substituted — corrected in review

An earlier revision of this document **removed** the approved `decision frequency` axis and put
`structural position` in its place. That was a unilateral change to a ranking contract this document
does not own, and the substitution smuggled in exactly what the first correction had removed: an
axis-shaped argument standing where a measurement should be.

Both errors are fixed as follows.

1. **`decision frequency` is restored as an axis and its value is `unknown` for every candidate.**
   Audit §8 gap 1 records why: nothing here measures how often any defect fires per decision, and
   #127 §7 gap 3 explains that no decision→outcome attribution exists at all. `unknown` is the
   honest entry, and it is entered for all five candidates so the axis cannot silently separate any
   pair.
2. **Structural position and trigger presence are kept, but as *supporting* columns, not as the
   frequency axis.** Structural position is read from the code; trigger presence is counted from the
   committed team files. Neither is a firing rate and neither is offered as a proxy for one.

| Rank | Slice | Panel exposure — trigger presence (counted; unit named) | **Decision frequency** | Error severity | Regret concentration | Dev-outcome link | *Structural position (supporting)* |
|---|---|---|---|---|---|---|---|
| **1–2 (tied)** | **S1** state truth + action order | order-abilities (Gale Wings, Sand Rush, Unburden, Intimidate, Levitate, Blaze) on **3 of 4 teams**; Fake Out on **3 of 4 teams** | **unknown** | **highest**: a wrong order inverts KO-before-act and flinch-before-act, so the error is in the frame, not in one line | maximal *when it fires*: one wrong ordering mis-scores the whole candidate set for that turn | none measured | upstream of every other slice; `sort_actions` fixes the order in which S2's transitions and S3's effects are applied |
| **1–2 (tied)** | **S3** resolved effects + calc binding | Rock Slide **4 mons / 3 teams**; Will-O-Wisp **3 mons / 3 teams**; Aurora Veil **1 mon / 1 team**; Blaze Delphox **1 / 1**; Acrobatics **1 / 1**; six unexecuted effect families | **unknown** | high and **two-directional**: flinch over-valued, screens/status/HP-conditional damage under-valued | broad rather than concentrated: many moves, each moderately mis-valued | **weak, and an adjacency only**: #127's W2 (`tailwind_both`, highest mean regret of any bucket) is a fast-board Protect/tempo context, which is where flinch and screens are decided. **Not** a demonstrated cause. | inside the turn: wrong effect values on an otherwise correct frame |
| **3** | **S2** legality + switch transition | Helping Hand **1 mon / 1 team**; switch candidates enumerated on **4 of 4 teams** | **unknown** | **severe when it fires**: an illegal choice is rejected outright and triggers the item-5 fan-out; a mis-resolved switch damages the wrong Pokémon | concentrated in few but high-stakes decisions | none measured | inside the turn, and **reachability-restricted**: the transition defect cannot reach a candidate line that contains no switch |
| **4** | **S6** screens standalone | Aurora Veil **1 mon / 1 team** | **unknown** | moderate | narrow | none | inside the turn, one mechanic |
| **5** | **S5** ally targeting standalone | 1b: Helping Hand **1 mon / 1 team**. 1a: **23 mons / 4 teams** — see the unit note below | **unknown** | 1b severe when it fires; 1a's omissions are of **unmeasured** value (audit §8 gap 2) | very narrow | none | enumeration only; additive, corrupts no present action's score |

**Unit note.** Every cell above counts **mons and teams**. Audit §4.1a additionally reports item 1a
as *55 moveset occurrences / 32 distinct names*; those are a different and much larger unit and are
deliberately **not** carried into this table, because comparing "55 occurrences" against "4 mons"
would inflate S5 by unit choice alone.

### Why S1 and S3 are tied, not ordered

An earlier revision ranked S1 above S3 on a containment argument: S3's effects are evaluated inside a
turn whose order S1 determines, so a correct flinch in the wrong order is still wrong. **That
argument is sound about *dependency* and does not establish *strength relevance*.** A defect that is
structurally upstream but fires rarely can matter less than a downstream one that fires constantly —
and which of those describes S1 versus S3 is precisely what `decision frequency` would have told us,
and precisely what is unknown.

With the deciding axis unknown, the remaining four axes do not separate them either: S1 is higher on
error severity and regret concentration; S3 is higher on counted trigger presence and is the only one
of the two with even a weak dev-outcome adjacency. That is a split, not an ordering.

**So S1 and S3 share rank 1–2, and the tie is recorded rather than broken.** Breaking it would mean
choosing which unmeasured quantity to assume, which is the failure mode §1 Fact 1 rejects.

**This changes no decision.** The execution order in §6 is set by the dependency chain, which is a
fact about the code and belongs to neither ranking — S1 precedes S3 there because S3's repair is
evaluated inside S1's frame, not because S1 outranks it. The tie removes an unsupported claim; it
does not remove a conclusion.

**Why S2, S6 and S5 sit below the tied band** — and this too rests on structure and counts, never on
frequency. S2's transition defect is **reachability-restricted**: it cannot reach a candidate line
containing no switch, which is a code fact rather than a rate estimate. S6 is one mechanic on one
mon. S5's blocker (1b) is one mon on one team, and its larger component (1a) has unmeasured value.
None of these is separated from the band by a frequency claim.

**Why S5 is last, and how far that rank is defended.** Not "few": audit §4.1a establishes that item
1a touches 23 mons across all 4 teams. The rank rests on two things — S5's *blocker* (1b) is one mon
on one team, and the value of 1a's omitted ally-directed actions is **unmeasured**, with 4× Sitrus
Berry a concrete counterexample category that an earlier "dominated" claim overlooked. So S5 is last
on a **counted blocker footprint plus an acknowledged unknown**, not on a demonstration that the
omitted actions are worthless. If those actions turn out to matter, this rank is not defended — and
S5's place in §6 does not depend on it, because it is sequenced there on availability.

---

## 5. Ranking by feasibility — separate, and deliberately different

**Inputs, and only these:** dependencies; testability; implementation effort; regression risk;
reversibility. Strength relevance is not an input.

**One total order over the same five candidates as §4.** An earlier revision printed S5 at rank 6 in
this table while §6 called it rank 1, and printed S2 at rank 1 in both places — two candidates
sharing a rank and one contradicting itself. That is corrected: the order below is the only
feasibility order in this document, and §6 quotes it verbatim.

| Rank | Slice | Dependencies | Testability | Effort | Regression risk | Reversibility |
|---|---|---|---|---|---|---|
| **1** | **S5** ally targeting standalone | **none** — `_slot_move_actions` already receives `active_index` and simply does not pass it to `_move_targets` | **highest**: a pure function of request and actor slot | **smallest** in the set | very low: additive to enumeration | very high |
| **2** | **S2** legality + switch transition | the *legality* half has none; the *transition* half needs S1's identity contract | high: legality is decidable per request, and a transition contract is directly assertable | legality small; transition medium | moderate — must **replace** the item-22 Choice guard rather than delete it, and change `tests/test_legal_actions.py:118-126`, which currently asserts the defect | high: enumeration changes are local and revertible |
| **3** | **S6** screens standalone | none beyond a `FieldState` extension and the calc-bridge field copy | good: replay for state, golden payload for the bridge | small | low | high |
| **4** | **S1** state truth + action order | needs its own two ability sources (log `\|-ability\|`, request `ability`/`baseAbility`) before ordering can read them | high: replay-based, deterministic, no calc needed | large — identity, two ability sources, and activation predicates (full HP, weather, item consumption) | **highest**: order is upstream of everything, so every scored line moves at once | low: the whole decision path shifts together |
| **5** | **S3** resolved effects + calc binding | needs an **unapproved** effect-event taxonomy; carries item 17's `FieldState` work and items 17/25's calc-bridge changes | mixed: flinch branches are testable, a general effect model is not testable before it is specified | **largest**, and partly unscoped | high, spread across resolver, rollout and calc binding | low |

S1 moved from 2 to 4 in this revision. Nothing about S1 changed — S5 and S6 were previously ranked
below it by carrying the "carve-out" label rather than by their actual dependency, testability and
risk profile, which are better than S1's on all three.

**Where the two orders disagree.** Relevance gives **{S1, S3} tied at 1–2, then S2, S6, S5**;
feasibility gives **S5, S2, S6, S1, S3** — a strict order, because dependencies, effort and risk are
knowable here where firing rates are not. The two are close to reversed: the tied relevance band
holds the two candidates that sit 4th and 5th on feasibility, and S5 is last on relevance and first
on feasibility. No candidate holds the same rank on both.

The disagreement is not resolved by averaging — averaging would put S2 first, and S2 cannot go first
because half of it depends on S1. It is resolved by the dependency chain in §6, which is a fact about
the code and belongs to neither ranking.

---

## 6. The shortlist

The starting hypothesis under test was:

1. Persistent Combatant State + Dynamic Action Order
2. Legal Action + Authoritative Switch Transition
3. Resolved Effects — Current Panel Core

**Adopted, with one substantive correction and one addition.**

### Adopted as-is: the composition of all three

Each of the three names a real, current, default-path group of confirmed defects, and together they
cover **all 13** of the audit's blockers with none assigned twice and none left over — the closure
check in §3. S3 carries the two blockers that an earlier revision lost with the dissolved S4
(items 2 and 25).

### Correction: the order is a dependency order, not the strength order

The hypothesis presents S1 → S2 → S3 as a ranking. It is not one, on either axis:

- On **strength relevance** S1 and **S3 are tied** at 1–2 and **S2** is third (§4). The tie is not
  a formality: `decision frequency` is `unknown`, and it is the axis that would have separated them.
- On **feasibility** the order is **S2**, S1, S3 among these three — and **S5, S2, S6, S1, S3**
  across all five candidates (§5).

Neither produces S1 → S2 → S3. What does produce it is the dependency chain, which is a third thing:

> Item 9's transition contract requires `PlannedAction` to carry a switch target; naming a switch
> target is meaningless while switch-in destroys the identity being named (item 8). And S3's
> effects are evaluated *inside* a turn whose order S1 determines — correct effects in the wrong
> order are still wrong.

So **S1 → S2 → S3 is correct as an execution order** and is adopted as such. Presenting it as a
strength ranking would misstate why. This distinction is the correction.

### Addition: S5 is carved out of S2 and sequenced first

S2's legality half (findings 1a–1c) has **no dependency on S1**, is the smallest item in the set,
and closes a current-panel path that today emits an illegal choice from the left active
(`teams/panel_champions_v0/trick_room.txt`, Helping Hand) and thereby triggers the item-5 fan-out
into unrelated rooms. `_slot_move_actions` already receives `active_index` and simply does not pass
it to `_move_targets`.

It is **last on strength relevance (5 of 5) and first on feasibility (1 of 5)** — precisely the
profile that must not be promoted on relevance grounds. It is proposed **as a pre-slice**, not as a
shortlist member, on availability alone: it is independently landable while S1 is specified, and it
removes an active illegal-action path.

Its one blocker, item 1b, is **also covered by S2**, so skipping the pre-slice loses nothing but
time. Item 1a rides along in both; audit §4.1a establishes that it touches 23 mons across all four
teams, and audit §8 gap 2 records that the value of those omitted ally-directed actions is
**unmeasured**. S5's last relevance rank therefore rests on its blocker footprint plus an
acknowledged unknown — not on a demonstration that the omissions are worthless. Its sequencing here
is on availability and does not depend on that rank.

### Resulting shortlist

Ranks are quoted verbatim from §4 and §5 over the same five candidates. No rank appears twice.

| Order | Slice | Blockers covered | Rank on relevance | Rank on feasibility | Gate to start |
|---|---|---|---|---|---|
| **0** (pre-slice, optional) | **S5** ally targeting | 1b | 5 of 5 | **1 of 5** | none — independent |
| **1** | **S1** persistent combatant state + dynamic action order | 3, 8, 15, 20, 23 | **1–2 of 5 (tied with S3)** | 4 of 5 | approval of this document |
| **2** | **S2** legal action + authoritative switch transition | 1b, 9 | 3 of 5 | 2 of 5 | S1's identity contract landed |
| **3** | **S3** resolved effects + attacker-aware mechanics and calc binding | 2, 14, 16, 17, 24, 25 | **1–2 of 5 (tied with S1)** | 5 of 5 | S1 landed **and** an approved effect taxonomy |

**S1 before S3 is not the relevance ranking.** They are tied there (§4). The order between them is
the dependency chain below, and nothing in this document claims S1 is the more strength-relevant of
the two.

**Blocker closure: S1 ∪ S2 ∪ S3 = all 13** (§3). S5's single blocker is already inside S2, so the
pre-slice is optional in the strict sense — skipping it costs time, not coverage.

**S3 carries an unmet precondition** and must not be started on the strength of this document alone:
its event taxonomy does not exist. That is a design slice of its own, and it is why S3 ranks **last**
on feasibility while ranking second on relevance — the sharpest single disagreement between the two
orders.

**Not shortlisted, each for a stated reason — no candidate is dropped by hand-wave:**

| Candidate | Disposition |
|---|---|
| **S4** (former) | **Dissolved**, §3. Items 2 and 25 moved into S3; item 21 explicitly deferred. An earlier revision excluded S4 as "folding into S1 and S3" without performing the fold, which silently dropped two blockers out of the shortlist. |
| **S6** | **Subsumed by S3** (item 17). Kept in both ranking tables so its profile is visible: it is 3rd on feasibility and 4th on relevance, and it is the natural fallback if S3's taxonomy work stalls — screens are the one part of S3 that needs no new event model. |
| **Item 21** (Unseen Fist) | **Deferred by name**, not folded. Not a blocker: no Urshifu on the hero or dev panel teams. Must be repaired before Urshifu enters strength evidence. |

---

## 7. What this does not decide

- It does not authorise implementation. Each shortlisted slice still needs its own spec and plan.
- It does not claim any of these repairs improves strength. None has a measured outcome effect, and
  the static audit's §8 says so.
- It does not settle S3's effect taxonomy, which is an open design question.
- It does not resolve audit item 19 — that needs the pinned Showdown server source, which is not in
  this repository.
- It does not schedule workstreams D or E, and it does not activate Depth 2.
- It does not re-open #127, whose ranking stands unchanged.

---

## 8. Acceptance criteria for #128, restated

- [x] Shortlist of 2–3 candidates documented — three, plus an optional independent pre-slice.
- [x] Each candidate has stated relevance, feasibility and risk — §4, §5, §6.
- [x] Ranking rationale is explicit, with the two rankings kept separate and their disagreement
      named rather than averaged. Feasibility is a single total order; relevance is a total order
      with one recorded tie (S1 = S3), and §4 states what the tie rests on.
- [x] All five approved relevance axes are present. `decision frequency` is retained and entered as
      **`unknown`** for every candidate — neither dropped nor substituted — §4.
- [x] No invented outcome metric, and no unmeasured quantity doing load-bearing work: the one
      ordering that had rested on an unmeasured axis (S1 over S3) is now a recorded tie — §1 Fact 1,
      §4.
- [x] The shortlist closes its own correctness boundary: all 13 audit blockers are assigned, none
      twice, none left over — §3 closure check, restated in §6.

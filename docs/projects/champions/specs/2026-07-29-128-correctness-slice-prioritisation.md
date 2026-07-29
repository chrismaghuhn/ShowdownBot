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

Six candidates, formed by grouping confirmed findings along their actual dependency and contract
boundaries rather than by finding count.

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

**Inputs, and only these:** current Champions/panel exposure; structural position in the decision
path; error severity (how wrong the modelled result is when it fires); concentration of possible
regret; and any existing development-outcome link.

**Effort, dependencies, testability, regression risk and reversibility are not inputs to this
ranking.** They are §5. A slice does not move up because it is easy or down because it is risky.

There is no `games recovered` column and there will not be one: §1, Fact 1.

### What replaced "decision frequency", and why — corrected in review

An earlier revision ranked partly on *decision frequency*, with cells reading "every turn" for S1 and
"fires on most turns" for S3. **Those were not established and are withdrawn.** What is verifiable is
that `sort_actions` is *called* for every candidate line — a fact about the code. Whether the
ability-order defect *fires* on a given turn depends on whether an ability-order Pokémon is on the
field with its activation predicate met, and **no measurement of that exists in this repository**.
The same applies to S3: "most turns" was an assertion about candidate composition that nothing here
measures. Using either to order S1 and S3 would have been the same error #1 Fact 1 rejects — an
unmeasured quantity doing load-bearing work.

The column is replaced by two that can be checked:

- **Structural position** — where in the pipeline the defect sits, and what is downstream of it.
  Read from the code.
- **Trigger presence** — how much of the panel carries the precondition. Counted from the committed
  hero and dev team files.

Neither is a firing rate, and neither is presented as one.

| Rank | Slice | Trigger presence (counted) | Structural position (read from code) | Error severity | Regret concentration | Dev-outcome link |
|---|---|---|---|---|---|---|
| **1** | **S1** state truth + action order | Gale Wings, Sand Rush, Unburden, Intimidate, Levitate, Blaze across **3 of 4** teams; Fake Out on **3 of 4** | **upstream of every other slice**: `sort_actions` fixes the order in which S2's transitions and S3's effects are applied, and every successor state is built from that order | **highest**: a wrong order inverts KO-before-act and flinch-before-act, so the error is in the frame, not in one line | maximal *when it fires*: one wrong ordering mis-scores the whole candidate set for that turn | none measured |
| **2** | **S3** resolved effects + calc binding | Rock Slide on **4 mons / 3 teams**; Will-O-Wisp on **3 teams**; Aurora Veil **1**; Blaze Delphox **1**; Acrobatics **1**; six unexecuted effect families across the panel | **inside the turn**: wrong effect values on an otherwise correct frame | high and **two-directional**: flinch over-valued, screens/status/HP-conditional damage under-valued | broad rather than concentrated: many moves, each moderately mis-valued | **weak, and an adjacency only**: #127's W2 (`tailwind_both`, highest mean regret of any bucket) is a fast-board Protect/tempo context, which is where flinch and screens are decided. **Not** a demonstrated cause. |
| **3** | **S2** legality + switch transition | Helping Hand **1 team** (illegal choice from the left slot); switch candidates enumerated on every team | **inside the turn**, but conditional: the transition defect reaches only lines that contain a switch | **severe when it fires**: an illegal choice is rejected outright and triggers the item-5 fan-out; a mis-resolved switch damages the wrong Pokémon | concentrated in few but high-stakes decisions | none measured |
| 4 | **S6** screens standalone | Aurora Veil **1 team** | inside the turn, one mechanic | moderate | narrow | none |
| 5 | **S5** ally targeting standalone | 1b: Helping Hand **1 team**. 1a: **32 panel moves** — but every omitted action is ally-directed and dominated on this team set (audit §4.1a) | enumeration only, upstream of scoring but additive | 1b severe when it fires; 1a's omissions are dominated options | very narrow | none |

**Why S1 outranks S3 — a containment argument, not a frequency one.** S1 is upstream of S3 in the
literal sense that S3's effects are evaluated inside a turn whose order S1 determines. A correctly
modelled Rock Slide flinch applied in the wrong turn order is still the wrong answer; a correct order
with one wrong effect is wrong only for that effect. The relation is asymmetric and readable from the
code, which is why it can carry the ranking where a frequency claim cannot.

**Why S3 outranks S2.** By counted trigger presence: S3's preconditions appear on all four teams and
across six effect families; S2's non-conditional half is one move on one team, and its transition
half reaches only candidate lines containing a switch. S2's per-occurrence severity is higher — which
is exactly why it is close, and why §5 reverses it.

**Why S5 is last, on the corrected exposure.** An earlier revision justified S5's last place with
"Helping Hand, 1 team", which understated it: audit §4.1a establishes that item 1a's exposure is 32
panel moves, not one. The rank survives the correction for a different reason — those 32 omissions
are all ally-directed options that are dominated on this panel (no ally-heal move, no ally-trigger
item). S5 is last because the missing actions are *worthless here*, not because they are *few*. That
distinction matters: add one ally-heal to a future panel and this ranking changes.

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

**Where the two orders disagree.** Relevance gives **S1, S3, S2, S6, S5**; feasibility gives
**S5, S2, S6, S1, S3**. The two are close to reversed. S1 is 1st and 4th; S3 is 2nd and last; S5 is
last and 1st. No candidate holds the same rank on both.

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

- On **strength relevance** the order is S1, **S3**, **S2** (§4).
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
time. Item 1a rides along in both; audit §4.1a establishes that its 32 panel-move omissions are
dominated on this team set, which is why it does not lift S5's relevance rank.

### Resulting shortlist

Ranks are quoted verbatim from §4 and §5 over the same five candidates. No rank appears twice.

| Order | Slice | Blockers covered | Rank on relevance | Rank on feasibility | Gate to start |
|---|---|---|---|---|---|
| **0** (pre-slice, optional) | **S5** ally targeting | 1b | 5 of 5 | **1 of 5** | none — independent |
| **1** | **S1** persistent combatant state + dynamic action order | 3, 8, 15, 20, 23 | **1 of 5** | 4 of 5 | approval of this document |
| **2** | **S2** legal action + authoritative switch transition | 1b, 9 | 3 of 5 | 2 of 5 | S1's identity contract landed |
| **3** | **S3** resolved effects + attacker-aware mechanics and calc binding | 2, 14, 16, 17, 24, 25 | 2 of 5 | 5 of 5 | S1 landed **and** an approved effect taxonomy |

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
- [x] Ranking rationale is explicit, with the two rankings kept separate, each a single total order,
      and their disagreement named rather than averaged.
- [x] No invented outcome metric, and no unmeasured firing rate doing load-bearing work — §1 Fact 1,
      §4 ("What replaced *decision frequency*").
- [x] The shortlist closes its own correctness boundary: all 13 audit blockers are assigned, none
      twice, none left over — §3 closure check, restated in §6.

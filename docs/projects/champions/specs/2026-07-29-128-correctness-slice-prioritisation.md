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

| ID | Slice | Findings | Workstream |
|---|---|---|---|
| **S1** | Persistent combatant state + dynamic action order | 8, 3, 20, 15, 23 | A |
| **S2** | Legal action + authoritative switch transition | 9, 1a, 1b, 1c, 22 | B |
| **S3** | Resolved effects — current panel core | 14, 16, 17, 24-residual | C |
| **S4** | Attacker-aware mechanics and calc binding | 2, 21, 25 | C |
| **S5** | Ally targeting only (1a–1c, carved out of S2) | 1a, 1b, 1c | B |
| **S6** | Screens as a standalone state + calc binding | 17 | C |

S5 and S6 exist as deliberately narrow carve-outs, considered so the shortlist is a choice and not
a restatement of the grouping.

---

## 4. Ranking by strength relevance

**Inputs, and only these:** current Champions/panel exposure; decision frequency; error severity
(how wrong the modelled result is when it fires); concentration of possible regret; and any
existing development-outcome link.

**Effort, dependencies, testability, regression risk and reversibility are not inputs to this
ranking.** They are §5. A slice does not move up because it is easy or down because it is risky.

There is no `games recovered` column and there will not be one: §1, Fact 1.

| Rank | Slice | Panel exposure | Decision frequency | Error severity | Regret concentration | Dev-outcome link |
|---|---|---|---|---|---|---|
| **1** | **S1** state truth + action order | Gale Wings, Sand Rush, Unburden, Intimidate, Levitate, Blaze; Fake Out on 3 of 4 teams | **every turn** — order is computed for every action of every candidate | **highest**: wrong order inverts KO-before-act, flinch-before-act and every successor state built from it | maximal: one wrong ordering mis-scores the entire candidate set for that turn, not one line | none measured |
| **2** | **S3** resolved effects — panel core | Rock Slide on 4 mons; Will-O-Wisp on 3 teams; Aurora Veil on 1; six unexecuted effect families | high — fires whenever such a move is a candidate, which is most turns | high, and **two-directional**: flinch is over-valued, screens and status are under-valued | broad rather than concentrated: many moves, each moderately mis-valued | **weak but present**: #127's W2 (`tailwind_both`, highest mean regret of any bucket) is a fast-board Protect/tempo context, which is exactly where flinch and screens are decided. This is an adjacency, **not** a demonstrated cause. |
| **3** | **S2** legality + switch transition | Helping Hand on `trick_room` (illegal choice from the left slot); switch scoring on every team | moderate — voluntary switches are a minority of turns; the illegal-choice path is rarer still | **severe when it fires**: an illegal choice is rejected outright and triggers the item-5 fan-out; a mis-resolved switch damages the wrong Pokémon | concentrated in few but high-stakes decisions | none measured |
| 4 | S4 attacker-aware mechanics | Blaze Delphox (HP); Acrobatics vs Protect | moderate | moderate: wrong damage on specific pairings | narrow | none |
| 5 | S6 screens standalone | Aurora Veil, 1 team | low in isolation | moderate | narrow | none |
| 6 | S5 ally targeting standalone | Helping Hand, 1 team | low | severe when it fires | very narrow | none |

**Why S1 outranks S3 on strength relevance alone.** S3 touches more moves; S1 touches more
decisions. Turn order is computed for every action of every candidate on every turn, and it is
upstream of the effects S3 fixes — a correctly-modelled Rock Slide flinch evaluated in the wrong
turn order is still the wrong answer. Frequency and upstream position beat breadth here.

**Why S3 outranks S2 on strength relevance alone.** S2's defects are more severe per occurrence, but
they fire on a minority of turns; S3's fire on most. This is the one place the two rankings disagree
sharply, and §5 flips it.

---

## 5. Ranking by feasibility — separate, and deliberately different

**Inputs, and only these:** dependencies; testability; implementation effort; regression risk;
reversibility. Strength relevance is not an input.

| Rank | Slice | Dependencies | Testability | Effort | Regression risk | Reversibility |
|---|---|---|---|---|---|---|
| **1** | **S2** legality + switch transition | needs S1's identity for the *transition* half; the *legality* half (1a–1c) has **none** | **highest**: legality is decidable per request; a transition contract is directly assertable | legality small; transition medium | moderate — must **replace** the item-22 Choice guard, not delete it, and change a test that currently freezes the defect | high: enumeration changes are local and revertible |
| **2** | **S1** state truth + action order | needs its own two sources (log `\|-ability\|`, request `ability`/`baseAbility`) before ordering can read them | high: replay-based, deterministic, no calc needed | large — identity, two ability sources, activation predicates (full HP, weather, item consumption) | **highest**: turn order is upstream of everything; every scored line moves | low: the whole decision path shifts at once |
| **3** | **S3** resolved effects — panel core | needs an **unapproved** resolved-effect event taxonomy; item 17 also needs `FieldState` extension and a calc-bridge change | mixed: flinch branches are testable; a general effect model is not testable before it is specified | large and partly unscoped | high, and spread across resolver, rollout and calc binding | low |
| 4 | S4 attacker-aware mechanics | needs S1's ability truth (item 25 compounds with item 20) | good | medium | medium | medium |
| 5 | S6 screens standalone | none beyond `FieldState` + bridge | good | small | low | high |
| 6 | S5 ally targeting standalone | none — `_slot_move_actions` already has `active_index` | **highest**: a pure function of request and actor slot | **smallest** in the set | very low | very high |

**Where the two orders disagree, and what that means.** S2 is first on feasibility and third on
strength relevance; S1 is first on strength relevance and second on feasibility; S3 is second on
relevance and third on feasibility. S5 is last on relevance and first on feasibility — the clearest
illustration that the two axes must not be collapsed.

The disagreement is not resolved by averaging. It is resolved by the dependency in §6, which is a
fact about the code and belongs to neither ranking.

---

## 6. The shortlist

The starting hypothesis under test was:

1. Persistent Combatant State + Dynamic Action Order
2. Legal Action + Authoritative Switch Transition
3. Resolved Effects — Current Panel Core

**Adopted, with one substantive correction and one addition.**

### Adopted as-is: the composition of all three

Each of the three names a real, current, default-path group of confirmed defects, and the audit's
de-duplication (§5 there) supports the grouping — S3's umbrella item 24 genuinely subsumes its
sub-gaps rather than adding a fourth slice.

### Correction: the order is a dependency order, not the strength order

The hypothesis presents S1 → S2 → S3 as a ranking. It is not one, on either axis:

- On **strength relevance** the order is S1, **S3**, **S2** (§4).
- On **feasibility** the order is **S2**, S1, S3 (§5).

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

It is last on strength relevance and first on feasibility — precisely the profile that should not be
promoted on relevance grounds. It is proposed **as a pre-slice**, not as a shortlist member, on
availability alone: it is independently landable while S1 is specified, and it removes an active
illegal-action path.

### Resulting shortlist

| Order | Slice | Rank on relevance | Rank on feasibility | Gate to start |
|---|---|---|---|---|
| **0** (pre-slice, optional) | **S5** ally targeting | 6 of 6 | 1 of 6 | none — independent |
| **1** | **S1** persistent combatant state + dynamic action order | **1** | 2 | approval of this document |
| **2** | **S2** legal action + authoritative switch transition | 3 | **1** | S1's identity contract landed |
| **3** | **S3** resolved effects — current panel core | 2 | 3 | S1 landed; an **approved** effect taxonomy |

**S3 carries an unmet precondition** and must not be started on the strength of this document alone:
its event taxonomy does not exist. That is a design slice of its own, and §5 records it as the
reason S3 is third on feasibility despite being second on relevance.

**Not shortlisted:** S4 (folds into S1 and S3 once ability truth exists — sequencing it separately
would duplicate the ability plumbing), S6 (subsumed by S3's item 17).

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
      named rather than averaged.
- [x] No invented outcome metric — §1 Fact 1, §4.

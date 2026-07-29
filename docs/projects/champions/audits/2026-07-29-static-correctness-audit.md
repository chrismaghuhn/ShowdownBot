# Static correctness audit — four strategic passes, verified against `main`

**Base:** `main @ 34bc98dc` · **Date:** 2026-07-29 · **Feeds:** #128
**Type:** audit. Read-only. No production code was changed, no battle was run, no experiment was
started, no held-out artifact was opened.

---

## 1. What this is, and what it is not

Four static-analysis passes produced 25 numbered claims about correctness defects on the current
decision path. This document is the **verified, versioned record** of those claims.

It is **not** the passes' output. The passes collected their claims in a temporary scratch inbox
(`showdownbot-static-audit-2026-07-29.md`) which is explicitly marked *"provisional collection
only. Not a repository artifact, approved diagnosis, issue, priority decision, or implementation
authorization."* That file has no authority. **Every claim below was re-derived against the code on
`main @ 34bc98dc` before being recorded here**, and the re-derivation changed several of them —
four exposure statements (§4.1a, §4.1, §4.2, §4.8), one severity framing (§4.3), one classification
(§4.7) and one status (§4.6). Those changes are marked in place.

**Two later revisions correct this document's own errors**, all found in review rather than by the
passes:

- **Rev 2** — `SHOWDOWN_ACCURACY_MODE` was described as default-off when the production default is
  **on** (§3); item 1a was recorded as `Panel: none` while the same register confirmed `any` moves
  on the panel (§4.1a). Neither changes the 13-defect blocker set, and §5 says so with the check
  rather than by assumption.
- **Rev 3** — §4.1a's replacement claim, that the omitted ally actions are "dominated" on this
  panel, was **itself broader than its evidence** and is withdrawn; 4× Sitrus Berry is a
  counterexample category the check missed. The exposure unit is now named (occurrences ≠ mons ≠
  teams) with a warning against cross-unit comparison, and the item count is corrected from four
  Mega stones to **five**. §8 is new and records what remains unmeasured.
- **Rev 4** — item 1a's blocker status moves from `no` to **`unresolved`**. The `no` rested on
  "a missing action does not corrupt the scoring of the actions that are present", which conflates
  scoring correctness with selection correctness: selection is an argmax over the action space, so
  removing an element can change the output even when every remaining score is right. The item
  inventory is also completed — 23 items on 23 mons, **1 mon carrying none**.

Rev 2 and rev 3 share one failure mode — a correction stated more strongly than the check that
produced it. Rev 4 is a different one: not an overstatement but a wrong inference, and it survived
two review rounds because it *sounded* like a scoping rule. Both are called out rather than smoothed
over, because the register's value depends on the gap between a claim and its evidence staying
visible.

It is also **not** a strength statement, a prioritisation, or an authorisation. Prioritisation is
[`docs/projects/champions/specs/2026-07-29-128-correctness-slice-prioritisation.md`](../specs/2026-07-29-128-correctness-slice-prioritisation.md).

### Relationship to #127

**These findings are not part of #127 and must not be read back into it.** #127 asked a different
question — *what does the existing development evidence say about where the bot loses games* — and
answered it from play-quality reports and dev-strength A/Bs in
[`2026-07-29-development-weakness-inventory.md`](2026-07-29-development-weakness-inventory.md).
That inventory stands unchanged.

This audit asks *where is the code wrong*. The two are different in kind:

| | #127 inventory | This audit |
|---|---|---|
| Method | outcome/behaviour evidence from recorded dev games | static code reading + direct reproduction |
| Answers | where games appear to be lost | where the implementation contradicts the rules |
| Says nothing about | whether a code defect costs games | whether a behavioural pattern has a code cause |

A confirmed defect here is **not** evidence that it costs games, and W2/W4 in #127 are **not**
explained by anything below. Nothing in this document revises #127's ranking.

---

## 2. Verification method, and its limits

For each claim: locate the production path, read it on `main @ 34bc98dc`, and where the claim
depends on data rather than control flow, reproduce it directly against the committed generated
data and committed teams.

**Run locally for this audit:**

- `python -m pytest -q` over eleven test files under `showdown_bot/tests/`: `test_legal_actions.py`,
  `test_battle_state.py`, `test_resolve.py`, `test_rollout.py`, `test_rollout_adapter.py`,
  `test_rollout_switch_regression.py`, `test_search_depth2.py`, `test_speed.py`, `test_moves.py`,
  `test_conditions.py`, `test_client_runner_io.py` → **121 passed**. Every one of these passes on unrepaired code, which is the coverage datum: the
  suite does not encode the counterexamples below. It is *not* a claim that no other test does —
  the full offline suite was not run for this docs-only audit.
- Direct metadata reproduction through `engine.moves.get_move_meta` and
  `battle.legal_actions._move_targets` for the target/secondary/effect claims.
- Committed team files read for exposure: hero `teams/fixed_champions_v0.txt` and the three **dev**
  panel teams in `teams/panel_champions_v0/`.

**Limits, stated so they are not mistaken for verification:**

1. **The pinned Showdown server source is not in this repository.** Commit
   `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` appears in evidence manifests, and
   `tools/eval/patches/` holds only a patch. Claims about what the *server* does — the `switchIn`
   position swap, `getLockedMove`, `activeMoveActions`, Unseen Fist's `onModifyMove` — could not be
   re-derived here. Where a finding rests on one, it is marked **server-side unverified in-repo**,
   and only the *bot-side* half is recorded as confirmed.
2. **Held-out material was not used.** Exposure was determined from the hero team and the three dev
   panel teams only. The two `panel_champions_v0` held-out teams and the Gate B sealed teams were
   not opened. Exposure statements are therefore lower bounds on the panel.
3. **Reported numeric magnitudes were not re-run.** Where a pass reported a calc figure or a
   probability leaf, the *code fact* is confirmed and the *number* is marked reported-only.

**Path convention.** Unqualified module paths below are relative to
`showdown_bot/src/showdown_bot/`. Everything else — `showdown_bot/tools/`, `showdown_bot/tests/`,
`teams/`, `config/`, `docs/` — is written out.

### Status vocabulary

| Status | Meaning |
|---|---|
| **Confirmed** | re-derived on `main @ 34bc98dc`; the named path behaves as claimed |
| **Confirmed, corrected** | the defect is real; some load-bearing detail in the claim was wrong and is restated |
| **Overlap** | real, but not independent — it is an instance or elaboration of another entry |
| **Reclassified** | the code fact holds; the claim's *category* does not |
| **Rejected** | the claim does not hold |
| **Not sufficiently evidenced here** | cannot be settled from this repository |

The `Blocks #128` column takes three values: `yes`, `no`, and **`unresolved`** — the last for a
defect that is panel-exposed and default-reachable but whose effect on candidate *selection* is
unmeasured. Exactly one entry carries it (item 1a, §4.1a).

---

## 3. Finding register

`Default?` = reachable on the **shipped default configuration**: `SHOWDOWN_SEARCH_DEPTH` unset → 1
(`battle/decision.py:66-72`), `SHOWDOWN_ROLLOUT_HORIZON` unset → 2 (`:47-50`),
`SHOWDOWN_ACCURACY_MODE` unset → **on** (`:100-108` — `_accuracy_mode()` returns `True` when the key
is absent, with an explicit off-list). `Panel` = exposure on the hero team plus the three dev
Champions teams. `Blocks` = blocks #128 ranking a strength candidate whose evaluation would run
through the defect.

Accuracy being default-**on** does not move any entry into or out of the `Default?` column — only
items 10 and 11 are gated to `no`, and they are gated by `SHOWDOWN_SEARCH_DEPTH`, not by accuracy.
It does make items 14 and 16 *more* active than a default-off reading would suggest: the hit/miss
branch expansion is live on every default decision, so item 14's flinch runs on every accuracy leaf
and item 16's missing `attempted_hits` for non-damaging moves is a gap inside machinery that is
actually executing.

| # | Finding | Status | Primary path | Default? | Panel | Blast radius | Existing tests | Blocks #128 | WS |
|---|---|---|---|---|---|---|---|---|---|
| 1a | `normal`/`any` never offer an ally target | **Confirmed, corrected** | `battle/legal_actions.py:45-58` | yes | **yes — 23 mons / 4 teams** (55 moveset occurrences, 32 distinct names; §4.1a, note the unit) | missing legal actions, all ally-directed; **their value is unmeasured** (§8 gap 2) | none | **unresolved** — §4.1a | B |
| 1b | `adjacentAlly` hardcodes `-1`, not actor-slot aware | **Confirmed, corrected** | `battle/legal_actions.py:53-54` | yes | **yes** (Helping Hand, `trick_room`) | illegal choice from the left slot → server reject | none | **yes** | B |
| 1c | Pollen Puff unselectable as an ally heal | Confirmed | as 1a | yes | no (`panel_v001` dev only) | missing legal action | none | no | B |
| 1d | Resolver lacks Pollen Puff ally-heal semantics | Overlap → 24 | `battle/resolve.py:293-295` | yes | no | mis-scored line | none | no | C |
| 2 | `MoveMeta.hits_foe` omits `any` → Protect never blocks an `any` move | **Confirmed, corrected** | `engine/moves.py:87-88`, `:215` | yes | **yes** (Acrobatics vs panel-wide Protect) | wrong damage/Protect value both directions | none | **yes** | C |
| 3 | `\|-ability\|` never parsed → revealed abilities never reach state | Confirmed | `engine/log_parser.py:111-364` | yes | yes | ability blind for damage, redirect, order | none | **yes** | A |
| 4 | 4 s outer timeout does not stop the worker; per-decision calc backends never closed | Confirmed | `battle/decision.py:1666-1682`, `:435`; `engine/calc/client.py:235` | yes | n/a | latency and process growth, not scoring | none | no | E |
| 5 | Unattributed Invalid-Choice PM fans a default choice out to every active room | Confirmed | `client/runner.py:254-267` | yes | n/a | corrupts unrelated concurrent battles | none | no | E |
| 6 | `run_smoke_battle()` does not reset format globals | Confirmed | `client/runner.py:375-397` | yes | n/a | Champions state leaks into Random Doubles in one process | none | no | E |
| 7 | `_get_priors()` swallows every load failure silently | Confirmed | `client/runner.py:115-128` | yes | n/a | silent loss of response weighting | none | no | E |
| 8 | Switch destroys all accumulated combatant knowledge | Confirmed | `engine/state.py:153-168` | yes | yes | belief, damage, hypotheses | none | **yes** | A |
| 9 | Three divergent switch contracts, each wrong | Confirmed | `battle/resolve.py:272-275`; `battle/search.py:28-45`; `learning/simulator.py:72-73` | yes (1-ply) | yes | voluntary-switch scoring | keying only | **yes** | B |
| 10 | Depth-2 terminal states scored as ordinary positions | Confirmed | `battle/search.py:217-226`; `battle/policy.py:65-66` | **no** (depth 2 opt-in) | yes | terminal value wrong both directions | smoke only | no (D) | D |
| 11 | Depth-2 generates our actions from public `move_names` | Confirmed | `engine/state.py:385-386`; `battle/opponent.py:138` | **no** | yes | our own depth-2 actions are fictional | none | no (D) | D |
| 12 | `--max-battles > 1` has no requeue | Confirmed | `client/runner.py:345,370,299-303` | yes | n/a | run hangs after battle 1 | none | no | E |
| 13 | Synchronous decide blocks the asyncio loop | Confirmed (overlaps 4) | `client/runner.py:141-174`; `battle/decision.py:1673` | yes | n/a | all rooms stall for up to the outer timeout | none | no | E |
| 14 | Secondary-chance flinch collapsed to guaranteed-on-hit | Confirmed | `battle/resolve.py:223` | yes | **yes** (Rock Slide ×4 mons) | over- and under-valued lines | none | **yes** | C |
| 15 | No ability-driven speed or priority anywhere | Confirmed | `engine/speed.py:57-68`; `battle/resolve.py:112-139` | yes | **yes** (Gale Wings, Sand Rush, Unburden) | turn order → everything downstream | none | **yes** | A |
| 16 | Rollout applies planned status that never resolved | Confirmed | `battle/evaluate.py:352-355`; `battle/rollout_adapter.py:58-77` | **yes** (horizon 2) | **yes** (Will-O-Wisp ×3 teams) | status value on a dead or blocked move | none | **yes** | C |
| 17 | Screens and Aurora Veil absent from state and calc binding | **Confirmed, corrected** | `engine/state.py:89-93,143-146`; `battle/rollout_adapter.py:35-56`; `showdown_bot/tools/calc/calc.mjs:50-51` | yes | **yes** (Aurora Veil, `tailwind_offense`) | damage both directions; setting the screen is worth nothing | none | **yes** | C |
| 18 | Depth-2 frontier caps share one `config_hash` | **Reclassified** — documented, approved, compensated | `eval/config_env.py:157-166` | n/a | n/a | provenance identity at depth 2 | drift tests | no | — |
| 19 | Request active-order does not track field slots | **Not sufficiently evidenced here** | `models/request.py:56-66`; `engine/state.py:363-378` | yes | yes | slot mapping, if the assumption is false | none | unresolved | A |
| 20 | Own `ability`/`baseAbility` dropped from request truth | Confirmed (elaborates 15) | `models/request.py:56-66`; `engine/state.py:348-401` | yes | **yes** (six panel abilities) | own-side ability blind | none | **yes** | A |
| 21 | Unseen Fist contact moves still blocked by Protect | Confirmed bot-side | `engine/moves.py:210-219`; `battle/resolve.py:203` | yes | **no** | wrong Protect outcome | none | no | C |
| 22 | Choice-item possession treated as an existing move lock | Confirmed bot-side | `battle/legal_actions.py:103-117` | yes | **no** | legal action removed | **freezes the defect** | no | B |
| 23 | Fake Out freshness tracks `\|move\|`, not consumed opportunities | Confirmed bot-side | `engine/state.py:73,193-198`; `engine/log_parser.py` (no `cant`) | yes | **yes** (Fake Out ×3 teams) | wasted turn offered and scored as live | none | **yes** | A |
| 24 | Resolved move effects broadly absent | Confirmed umbrella | `engine/moves.py:61-76` vs `battle/resolve.py:188-350` | yes | **yes** (six effect families) | most non-damage move value | none | **yes** | C |
| 25 | Current HP omitted from calc requests | Confirmed | `engine/calc/models.py:7-40` vs `showdown_bot/tools/calc/calc.mjs:41` | yes | **yes** (Blaze Delphox) | HP-conditional mechanics silently off | none | **yes** | C |

---

## 4. Confirmed defects — detail where the re-derivation added or changed something

Entries whose scratch statement was accurate and needs no elaboration are covered by the register
above. What follows is the material that changed, or that a repair will have to respect.

### 4.1a Item 1a — panel-wide exposure, near-zero value: correcting an earlier `Panel: none`

An earlier revision of this register recorded item 1a as `Panel: none`. **That was wrong**, and the
error was self-contradictory: the same register confirms under item 2 that `any` is mishandled and
names Acrobatics as a current-panel `any` move. A defect in how `any` is targeted cannot have no
panel exposure while `any` moves are on the panel.

Counted across the hero team and the three dev panel teams, in a unit stated explicitly because it
is **not** the unit other rows of this register use:

> **55 moveset occurrences** — 32 distinct move names, on 23 of the 24 mons, across all 4 teams —
> take a target that `_move_targets` restricts to the two foe slots.

30 of the names are `normal` (Close Combat, Will-O-Wisp, Fake Out, Encore, Knock Off, Thunder Wave,
Taunt, Parting Shot, …) and 2 are `any` (**Acrobatics**, **Dark Pulse**). In doubles both target
classes legally include the ally; `_move_targets` returns `[1, 2]` for all of them
(`battle/legal_actions.py:51-52`). Exposure is therefore **panel-wide, not absent**.

**Unit warning.** Every other exposure cell in this register counts *mons* or *teams* (e.g. "Rock
Slide on 4 mons / 3 teams"). Occurrence counts are a different and much larger unit — 55 occurrences
is not comparable to "4 mons", and nothing in this document may compare them directly. Where item
1a's exposure is used in a ranking, the mon/team figures (23 mons, 4 teams) are the comparable ones.

### What is *not* established: that the omitted actions are worthless

An earlier revision of this section said the omitted ally-directed actions are "dominated" on this
panel and therefore worthless. **That claim is withdrawn — it was broader than the check behind it.**
What was actually checked was two categories: ally-heal moves, and items that a friendly hit would
usefully trigger. Neither check licenses a universal claim over all board states and all tactical
friendly-fire uses, and one concrete counterexample category was missed:

- **Sitrus Berry is on 4 of the 24 panel mons** (hero Garchomp, `goodstuff` Incineroar,
  `tailwind_offense` Garchomp, `trick_room` Gyarados). Deliberately dropping one's own Sitrus holder
  below 50% to trigger the heal is a real technique. It is situational and its value here is
  unquantified — but it is not nothing, and "dominated" asserted that it was.

What the check *does* support, and all it supports:

- **no ally-heal move** on these teams (Pollen Puff is on `panel_v001` — item 1c);
- **no stat-trigger item** that a friendly hit would set off. The full inventory across the 24 mons
  is **23 items on 23 mons, with 1 mon carrying no item at all** (`tailwind_offense` Talonflame):
  4× Sitrus Berry, 3× Leftovers, 2× Chople Berry, 2× Haban Berry, 2× White Herb, 2× Focus Sash,
  1× Choice Scarf, 1× Black Glasses, 1× Mental Herb, and **five** Mega stones — Scovillainite,
  Aerodactylite, Delphoxite, Froslassite, Tyranitarite. No Weakness Policy, no Absorb Bulb, no
  Berry Juice. (The itemless mon cannot be a damage-trigger target at all, which narrows the
  category by one further.)
- **no obviously friendly use** among the 30 `normal` status names — but "obviously" is doing real
  work in that sentence, and it is not an enumeration of board states.

So the supportable statement is: **no *demonstrated high-value* ally-target use exists on this
panel, and no measurement of the omitted actions' value exists at all.** That is weaker than
"dominated", and §8 of this document now carries it as an open evidence gap.

### Blocker status: `unresolved`, not `no` — corrected in review

An earlier revision recorded item 1a as **not** a blocker, on the reasoning that "a missing action
does not corrupt the scoring of the actions that are present". **That reasoning is wrong and is
withdrawn.** Candidate selection is an argmax over the enumerated action space
(`battle/policy.py:93-106`). Removing an element from that space cannot change the *scores* of the
remaining elements, but it can absolutely change the *argmax* — which is the output. Scoring
correctness and selection correctness are not the same property, and I conflated them.

So the question is not whether the omitted actions are scored correctly (they are absent, so the
question does not arise) but whether any of them would ever have won the argmax. That is exactly the
quantity §8 gap 2 records as unmeasured, and 4× Sitrus Berry shows the category is not empty.

**Item 1a's blocker status is therefore `unresolved`.** Not `yes` — no board state has been
demonstrated in which an omitted ally target would be selected. Not `no` — that would assert the
absence of such a state, which is unproven. `unresolved` is a distinct status from item 19's: item
19 is *unverifiable from this repository*, item 1a is *unquantified*. Settling it needs a bounded
piece of work — enumerate whether any omitted ally action can win the argmax on the current panel —
not a slice.

### 4.1 Item 1b — the ally-target defect is current-panel exposed, and the scratch understated it

`_move_targets` returns `[-1]` for every `adjacentAlly` move regardless of which of our two actives
is choosing (`battle/legal_actions.py:53-54`). In doubles the ally of the left active is `-2` and
the ally of the right active is `-1`, so the encoding is correct for exactly one of the two slots.

The scratch justified this item with **Pollen Puff**, which is on `panel_v001` dev teams and **not**
on the Champions panel. Re-derivation found a stronger case it missed: **Helping Hand is on
`teams/panel_champions_v0/trick_room.txt` (Gyarados)**, `target=adjacentAlly`, and `_move_targets`
gives it `[-1]`. Whenever Gyarados is the left active and the policy selects Helping Hand, the
choice is rejected by the server.

`_slot_move_actions` already receives `active_index` (`legal_actions.py:72-73`); it simply does not
pass it down. That makes the repair small and the defect current, not hypothetical.

This is also where item 1b meets item 5: a rejected choice produces the Invalid-Choice PM whose
fan-out corrupts every other active room.

### 4.2 Item 2 — the `any` gap is current-panel exposed

`hits_foe` lists `normal, adjacentFoe, allAdjacentFoes, allAdjacent, randomNormal` and omits `any`
(`engine/moves.py:87-88`). `blocks_move` returns `False` for anything that is not `hits_foe`
(`:215`). Reproduced: `acrobatics` has `target="any"`, `hits_foe == False`.

**Acrobatics is Talonflame's attack on `teams/panel_champions_v0/tailwind_offense.txt`**, and
Protect is on **20 of the 24** hero + dev-panel movesets. The scratch left exposure open; it is
current.

The repair shape is genuinely open, as the scratch said: `hits_foe` is one predicate serving both
"can this be Protected" and "does this target the opposing side", and `any` answers those
differently. That is a contract question for workstream C, not a one-line edit.

### 4.3 Item 17 — the correction: the screen model is live, not dormant

The scratch called `screen_modifier()` a *dormant* implementation. It is not dormant. `rollout()`
calls it twice per actor per turn (`battle/rollout.py:125,151`) and the default rollout horizon is
**2**, so it runs on every default decision.

What is missing is its input. `FieldState` has no screen fields (`engine/state.py:89-93`),
`apply_event` handles only Tailwind under `sidestart`/`sideend` (`:143-146`), and
`conditions_from_battle` copies only tailwind, weather and terrain (`battle/rollout_adapter.py:35-56`).
`screen_modifier` therefore returns the neutral `1.0` on every call
(`engine/conditions.py:159-168`). Independently, the Node bridge copies only `weather` and `terrain`
into `@smogon/calc` (`showdown_bot/tools/calc/calc.mjs:50-51`) although the pinned calc exposes per-side screen
fields.

The correction matters for sequencing: the repair is a **state-population** slice, not an
implement-the-mechanic slice, and it touches two independent consumers (rollout and calc binding).

### 4.4 Item 16 — active by default, unlike its depth-2 neighbours

`_rollout_value()` calls `apply_line_effects(cstate, all_actions)` on the **planned** actions
(`battle/evaluate.py:352-355`), while `TurnOutcome` contributes only `hp_delta`. A move that never
resolved — user KO'd first, Protect, immunity, miss — still applies its status. Non-damaging moves
never enter `apply_hit()` at all (`battle/resolve.py:293-295`), so they produce no `attempted_hits`
and the accuracy branches cannot represent their failure either.

`SHOWDOWN_ROLLOUT_HORIZON` defaults to `"2"` (`battle/decision.py:47-50`). **This is on by default**,
in contrast to items 10 and 11, which need `SHOWDOWN_SEARCH_DEPTH >= 2` and default to 1
(`battle/decision.py:66-72`). That asymmetry is why item 16 sits in workstream C and items 10–11 sit
in D.

### 4.5 Items 8, 9 — the two that constrain everything else

**Item 8.** `apply_event` for `switch` constructs a fresh `PokemonState` and assigns it to the slot
(`engine/state.py:153-168`). Revealed moves, `item_known`, `item_lost`, ability, types, boosts and
base identity are discarded. State is keyed by *slot*, never by combatant, so re-entry is
indistinguishable from a first appearance. `hypothesis_from_state` reads `item_known` directly
(`engine/belief/hypotheses.py:132-139`) and has no `item_lost` concept, so an item observed to be
consumed becomes unknown again and its presets are re-admitted.

**Item 9.** Three consumers, three different wrong contracts:

- `PlannedAction` has no switch-target field at all (`battle/resolve.py:27-46`); `resolve_turn`
  records a flag and continues, leaving the outgoing mon in the slot to receive the incoming attack
  (`:272-275`).
- `approx_turn2_state` states in its own docstring that it does not model switches
  (`battle/search.py:28-45`).
- `apply_outcome_to_state` runs `_apply_hp` then `_apply_switches`, and `_apply_switches` replaces
  the slot with a fresh deep copy from the roster — so damage booked against the outgoing mon
  vanishes (`learning/simulator.py:72-73`, `:37-49`).

The dependency is one-directional and load-bearing for sequencing: **a shared authoritative
transition cannot be written before `PlannedAction` can name a switch target, and naming one is
meaningless while switch-in destroys the identity being named.** 8 precedes 9.

### 4.6 Item 19 — what is confirmed, and what is not

The fourth pass *rejected* an incoming claim that request-side ordering diverges from field-slot
order, on the strength of the pinned server's `switchIn`/`getRequestData`. **That rejection could
not be re-derived here** — the server source is not in this repository (§2, limit 1).

What *is* confirmed is the bot's dependence on the assumption. `merge_request` maps actives to slots
`a, b, c` in request listing order when species lookup misses (`engine/state.py:363-378`), and
`_active_mon_fainted` indexes `[p for p in req.side.pokemon if p.active]` positionally
(`battle/legal_actions.py:61-69`). If the assumption is false, both mis-map.

Recorded as **unresolved**, not as rejected and not as a defect. Settling it needs the pinned server
source, which is a bounded lookup — not a slice.

### 4.7 Item 18 — reclassified: a documented decision, not a discovery

The code fact reproduces: `SHOWDOWN_SEARCH_TOPN` and `SHOWDOWN_SEARCH_TOPM` are in
`EXCLUDED_BY_REASON`, so `behavior_env` omits them unconditionally — including at depth 2, where
they do change which candidates are expanded (`eval/config_env.py:157-166`).

But this is not an undiscovered defect. It is an **approved decision with a compensating
mechanism**, recorded in at least three places on `main`:

- `docs/projects/learning/plans/2026-07-12-2c-depth2-derisk.md:201` — *"do **NOT** add them to
  `BEHAVIOR_AFFECTING` … the gate records them in its own run manifest"*;
- `docs/projects/champions/specs/2026-07-16-champions-i8-latency-design.md:669,707` — `arm_params`
  carries them per arm, outside `behavior_env`;
- `docs/projects/accuracy/specs/2026-07-12-accuracy-hit-probability-design.md:304,348` — names it as
  a known pattern and deliberately does *not* repeat it for `SHOWDOWN_ACCURACY_BRANCH_CAP`, a
  decision echoed in the code comment at `eval/config_env.py:76-81`.

It therefore belongs in §6 as an architecture/provenance risk, not in the defect register. Any
change must be forward-only and must not reopen the Attempt-6 freeze, whose evidence chain used the
per-row cap checks by design.

### 4.8 Items 21, 22, 23 — bot-side confirmed, server-side unverified, and two are deliberate

For all three, the bot-side fact is confirmed and the server-side justification is not re-derivable
here (§2, limit 1).

Two of them are **not oversights**, which changes what a repair has to deliver:

- **Item 22.** The Choice filter is a deliberate guard with a stated rationale — clicking Protect
  with a Choice item locks the mon into it forever (`battle/legal_actions.py:103-106`). It is frozen
  by `tests/test_legal_actions.py:118-126`, whose docstring states the rationale. It is still a
  legality misstatement: item possession is not a lock. A repair must therefore *replace* the guard
  (read the request's per-move `disabled`, and express the anti-lock preference in scoring) rather
  than delete it, and must change a test that currently asserts the defect.
- **Item 23.** `drop_first_turn` is likewise a deliberate filter against observed Fake Out spam
  (`battle/legal_actions.py:118-124`), fed from `PokemonState.moved_since_switch`
  (`battle/decision.py:461-464`, `battle/actions.py:107-131`). The defect is the *freshness
  predicate*, not the filter: `moved_since_switch` is set only by a parsed `|move|`
  (`engine/state.py:193-198`) and the parser has no `cant` event, so a flinched or paralysed turn
  leaves Fake Out looking fresh in both enumeration and the resolver (`battle/resolve.py:281-286`).

Item 22 has **no current-panel exposure**: the only Choice holder across the hero and dev teams is
Basculegion @ Choice Scarf, whose four moves are all damaging. Item 21 likewise has none — no
Urshifu on those teams. Both exposure corrections match the fourth pass's own corrections and were
re-derived independently here.

### 4.9 Item 24 — the umbrella, and what is genuinely new in it

`MoveMeta` imports `status`, `volatile_status`, `side_condition`, `slot_condition`, `weather`,
`terrain`, `boosts`, `self_effect`, `secondary`, `drain`, `recoil`, `multihit` and a curated
`effect_classes` overlay (`engine/moves.py:61-76`). `resolve_turn` consumes damage/KO, the binary
`flinch` flag, Protect/redirection and a generic `status:` flag string, and executes none of the
structured effects (`battle/resolve.py:188-350`).

Reproduced on the current panel:

| Effect family | Move (panel team) | What the data carries | What the resolver does |
|---|---|---|---|
| self stat drops | Close Combat (hero, `goodstuff`, `tailwind_offense`) | `self={'boosts': {'def': -1, 'spd': -1}}` | nothing |
| self stat drops | Draco Meteor (`trick_room`), Overheat (`trick_room`, hero) | `self` boosts | nothing |
| ally amplification | Helping Hand (`trick_room`) | `effect_classes=('disruption',)` | generic `status:` flag |
| healing | Life Dew (`trick_room`) | `target='allies'` status move | generic `status:` flag |
| foe debuff + pivot | Parting Shot (`goodstuff`) | `effect_classes=('pivot','debuff_foe')` | generic `status:` flag |
| drain | Matcha Gotcha (`trick_room`) | `drain=(1,2)` | nothing |
| recoil | Flare Blitz (`goodstuff`, `tailwind_offense`) | `recoil=(33,100)` | nothing |

The umbrella is **not** an independent finding: pivot transition is item 9, probabilistic
secondaries item 14, outcome-derived status item 16, side conditions item 17. What is new and
confirmed here is the remaining set — healing, self boosts/drops, foe debuffs, ally amplification,
recoil, drain. Any resolved-effect event taxonomy is a design question, not an approved schema.

### 4.10 Item 25 — code fact confirmed, magnitude reported only

`CalcMon` has no `cur_hp` field and `to_payload()` cannot emit one (`engine/calc/models.py:7-40`),
while the bridge accepts `spec.curHP` (`showdown_bot/tools/calc/calc.mjs:41`). An omitted current HP therefore
behaves as full HP, and Blaze/Overgrow/Blaze-class activation is silently suppressed. Delphox with
Blaze is on `teams/panel_champions_v0/goodstuff.txt`.

The reported figures (`120-144` omitted vs `180-212` at `curHP=1`) were **not re-run here**; only
the code fact is confirmed. The defect compounds with item 20 — the ability itself is also absent
from own-side truth, so repairing HP alone would still leave activation wrong.

---

## 5. Overlaps, so nothing is counted twice

| Entry | Subsumed by / elaborates | Consequence |
|---|---|---|
| 1d | 24 (healing family) | do not slice separately |
| 3 | independent, but a **prerequisite** of 15 and a sibling of 20 | one ability-truth contract, two sources |
| 13 | 4 (same decision-executor / calc-lifecycle boundary) | one slice, not two |
| 20 | 15 (named there as a dependency) | own-side ability truth is part of the ordering repair |
| 21, 24-pivot | 9 (transition), 2 (Protect predicate) | repair order matters more than count |
| 24-secondaries | 14 | 14 is the concrete instance |
| 24-status | 16 | 16 is the concrete instance |
| 24-side-conditions | 17 | 17 is the concrete instance |

**Count, enumerated so it can be checked.** 28 register rows, minus 2 that are not defects (18
reclassified, 19 unresolved) = **26 confirmed defects**; minus 2 that are not independent (1d folded
into 24, 13 folded into 4) = **24 independent confirmed defects**:

- **19 on the decision path** — 1a, 1b, 1c, 2, 3, 8, 9, 10, 11, 14, 15, 16, 17, 20, 21, 22, 23,
  24-residual, 25.
- **5 on the operational path** — 4 (with 13), 5, 6, 7, 12.

Item 20 is kept as independent despite elaborating 15: it is a second, separate code path (the
request model) for the same contract, and it must be repaired on its own terms.

The 19 decision-path defects split three ways on blocker status — 13 `yes`, 1 `unresolved`, 5 `no`:

**`yes` (13): 1b, 2, 3, 8, 9, 14, 15, 16, 17, 20, 23, 24, 25.** Each is current-panel exposed *and*
reachable on the shipped default configuration.

**`unresolved` (1): 1a.** Panel-exposed and default-reachable, but whether an omitted ally action
would ever win the argmax is unmeasured — §4.1a, §8 gap 2. Recorded as neither `yes` nor `no`
because both would assert something unproven.

**`no` (5), for two different and non-interchangeable reasons:**

| Excluded | Why |
|---|---|
| 10, 11 | depth 2 is **off by default** (`SHOWDOWN_SEARCH_DEPTH` → 1) |
| 1c, 21 | **no current-panel exposure** — Pollen Puff is on `panel_v001`; no Urshifu on hero or dev teams |
| 22 | **no current-panel exposure** — the only Choice holder is Basculegion @ Choice Scarf, whose four moves are all damaging, so the filter removes nothing here. Note this is an *exposure* argument, not the withdrawn "a missing action cannot change selection" argument: item 22 also shrinks the action space, and would be `unresolved` on the same footing as 1a if any panel mon held a Choice item alongside a status move. |

The `SHOWDOWN_ACCURACY_MODE` correction above was checked against this set and changes nothing in
it: accuracy gates no entry's `Default?` value.

---

## 6. Architecture and operational risks — real, but not defects for #128

- **Item 18**, reclassified in §4.7: an approved, compensated provenance limitation. Forward-only if
  it is ever changed; the Attempt-6 freeze stays valid.
- **Item 19**, unresolved in §4.6: a bounded lookup against the pinned server, not a slice.
- **Items 4, 13** are a lifecycle/concurrency boundary, not a scoring defect. They cost latency and
  process footprint, and they can stall unrelated rooms — but they do not change which action a
  completed decision returns.
- **Items 5, 6, 7, 12** are reliability defects on the live runner. Item 12 in particular means a
  `--max-battles N > 1` run cannot autonomously reach `N` today, which bounds how live evidence can
  be gathered at all.

---

## 7. Mapping to the #128 workstreams

| WS | Scope | Confirmed entries |
|---|---|---|
| **A — State truth** | persistent combatant identity; ability/item/move/HP knowledge; dynamic action order | 3, 8, 15, 20, 23 (+19 unresolved) |
| **B — Legal actions & authoritative transitions** | legality, switch execution, one shared transition contract | 1a, 1b, 1c, 9, 22 |
| **C — Resolved move effects** | format- and panel-relevant move/ability effects | 2, 14, 16, 17, 21, 24, 25 (+1d) |
| **D — Depth-2 correctness** | terminal values, private own actions, depth-2-specific correctness | 10, 11 |
| **E — Runner / operations** | requeue, event-loop blocking, live operational defects | 4, 5, 6, 7, 12, 13 |

D stays separate and off by default. E is a separate reliability track. Neither is ranked with A–C.

---

## 8. Open evidence gaps

Gaps demonstrated by the verification, not speculation. Each one bounds a statement made above.

1. **No firing rate exists for any defect.** Every exposure figure here is a *presence* count over
   committed team files — how many mons or teams carry the precondition. Nothing in this repository
   measures how often a defect actually fires per decision, and #127 §7 gap 3 records why: there is
   no decision→outcome attribution anywhere. Any ranking that needs a frequency must record it as
   **unknown**, not substitute a proxy for it.
2. **The value of item 1a's omitted actions is unmeasured** (§4.1a). No ally-heal move and no
   damage-trigger item is a checked fact; "worthless" is not, and 4× Sitrus Berry is a concrete
   counterexample category. Any rank that rests on those actions being low-value rests on an
   assumption. **This is what holds item 1a's blocker status at `unresolved`**, and closing it is a
   bounded question — can any omitted ally action win the argmax on the current panel? — not a
   slice. Item 22 sits behind the same question and is answered only by the accident that no panel
   mon pairs a Choice item with a status move.
3. **The pinned Showdown server source is not in this repository** (§2 limit 1), so items 19, 21, 22
   and 23 are recorded bot-side only.
4. **Held-out team contents were not read** (§2 limit 2), so every exposure figure is a lower bound
   on the full panel.
5. **Reported calc magnitudes were not re-run** (§2 limit 3, item 25).
6. **Test coverage was sampled, not enumerated.** 121 tests over eleven files pass on unrepaired
   code; the full offline suite was not run, so "no existing test covers this" is a statement about
   those eleven files.

---

## 9. Non-claims

- No claim that any defect here costs games. None of the 25 has a measured outcome effect.
- No claim that repairing any of them improves strength.
- No claim that #127's W2 or W4 is explained by anything above.
- No claim about the pinned server's behaviour beyond what §2 limit 1 permits.
- No claim that any exposure figure is a firing rate. See §8 gap 1.
- No claim of exhaustiveness. Four passes over selected paths are not a complete audit; the register
  is what those passes reached and this document could re-derive.
- No claim that the targeted 121-test run is suite coverage. The full offline suite was not run.
- No production-readiness statement, and no authorisation to implement anything.

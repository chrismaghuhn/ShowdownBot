# S1 — Persistent combatant state, ability truth, and dynamic action order

**Issue:** #129 · **Base:** `main @ 4e9ebcf2` · **Date:** 2026-07-29
**Type:** design / spec. **No production code is changed by this document and none is authorised by
it.** The implementation plan is a separate artifact requiring separate approval.

**Revision 3 (post-review).** Rev 2 fixed five contract rules and introduced six new gaps of its
own — an over-general conclusion, a truncated enumeration, a half-applied rule, an unimplementable
split, an invariant that contradicted existing constructors, and a decision deferred to the plan that
belongs here. All six were raised in review, all six re-derived here, and §0 records what changed
across both revisions.

**The pinned Showdown source is readable on this machine** at
`C:/Users/chris/.cache/showdownbot/pokemon-showdown`, `git rev-parse HEAD` =
`f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` — the pin in `config/eval/provenance.yaml`. Only
`server/ladders.ts` and `server/rooms.ts` are modified (the eval patch); **`data/` and `sim/` are
byte-clean**, verified with `git status --short -- data sim`. Every server claim below was read
there. This lifts audit §2 limit 1 for the paths cited here — the limit said the source was not *in
the repository*, which is still true and is no longer the same as unavailable.

**Feeds from:** [`2026-07-29-static-correctness-audit.md`](../audits/2026-07-29-static-correctness-audit.md)
(items 3, 8, 15, 20, 23) and
[`2026-07-29-128-correctness-slice-prioritisation.md`](2026-07-29-128-correctness-slice-prioritisation.md)
(slice **S1**, relevance band 1–2, feasibility 4 of 5).

---

## 0. What revisions 2 and 3 changed, and why

### Revision 2

| # | Rev 1 said | Verified on the pin | Rev 2 |
|---|---|---|---|
| 1 | Unburden's predicate "is precisely `item_lost`" | `data/abilities.ts:5227-5245`: Unburden is a **volatile** (`addVolatile('unburden')`), `onEnd` removes it, and its `onModifySpe` additionally requires `!pokemon.item` | §5.2.1 — a separate `unburden_active` volatile that **resets on switch**, plus a current-item check. `item_lost` survives for belief; the boost does not. |
| 2 | one `ability` field; ignore `\|-ability\|…\|[from]` | `sim/SIM-PROTOCOL.md:512` — `[from]` is explicitly *"has been **changed**"*; without `[from]` it is a switch-in **announcement**. `sim/pokemon.ts:1528` (`clearVolatile`) sets `this.ability = this.baseAbility` | §4 — **two** fields: `base_ability` (persistent) and `effective_ability` (on-field, reset to base on switch-in). |
| 3 | `combatants` / `active_slots` introduced, no word on `sides` | 94 production and 323 test references to `.sides[…]` / `.side(…)`; `learning/simulator.py:47` replaces slot entries; `engine/mega_projection.py:46-51` **rebuilds `sides` with per-mon deepcopies after a full state deepcopy** | §3.1 — `sides` stays the canonical mutable store; `combatants` is an **alias registry**, with a stated invariant and a named test for the `copy_battle_state` hazard. |
| 4 | "every `\|cant\|` sets the flag" | `data/abilities.ts:215,864,3716` — Armor Tail / Dazzling / Queenly Majesty log the **ability holder** as the event's Pokémon, not the prevented mover | §5.1 — a verified two-class taxonomy. Third-party blocks set nothing. |
| 5 | collision counter compares `base_species_id` to incoming details | `sim/pokemon.ts:1447-1449` — a Mega `formeChange` is `isPermanent`, rewriting `baseSpecies` and `details` | §3.5 — comparison resolves through form metadata; a Mega-re-entry test is added. |

**Two further findings rev 2 added, from the same reading:**

- **§5.1a — on the front-track format the server disables Fake Out itself.**
  `data/mods/champions/moves.ts:331-338` overrides `fakeout` with
  `onDisableMove(pokemon) { if (pokemon.activeMoveActions) pokemon.disableMove('fakeout'); }`, and
  `battle/legal_actions.py:112-113` already honours `disabled`.
- **§5.1b — the prevented mover *does* consume its opportunity even under a third-party block.**
  `sim/battle-actions.ts:217` increments `activeMoveActions` at the very top of `runMove`, before any
  `TryMove` event, and `sim/pokemon.ts:249-250` states the contract.

### Revision 3

| # | Rev 2 said | Verified | Rev 3 |
|---|---|---|---|
| 1 | remove `drop_first_turn` from the own-side path — the server disables Fake Out | base gen 9 uses `onTry` at execution (`data/moves.ts:5096`, `:5482`), **never** `disabled`; `_FIRST_TURN_MOVES` is `{fakeout, firstimpression}`; **2 of 3** supported formats are base gen 9 | §5.1a — `drop_first_turn` is **kept and re-fed**. A disjunction: `disabled` ∨ (first-turn move ∧ `had_move_opportunity`). No format detection. |
| 2 | seven self-class `cant` reasons; unknown → third-party | the full gen-9 + Champions list is **sixteen**; `data/moves.ts` contributes nine (`Attract`, `Disable`, `Focus Punch`, `Shell Trap`, `move: Gravity`/`Heal Block`/`Imprison`/`Taunt`/`Throat Chop`) | §5.1b — complete list, **three** outcome classes, and a distinct `cant_unknown` counter |
| 3 | form change updates `base_ability` "only for the intrinsic value" | Aerodactyl-Mega has Tough Claws; leaving `effective_ability` at Unnerve poisons every later calc and speed predicate | §4.3 — form change sets **both**, atomically; §7 pins both halves |
| 4 | consumer split: calc takes effective, belief takes base | `hypothesis_from_state` writes **one** `ability` into `SetHypothesis` and `_to_calc_mon` forwards that same value — the split is unreachable by renaming `PokemonState` fields | §4.2a — `SetHypothesis` splits too |
| 5 | ALIAS-1 over every bound slot; "existing consumers are untouched" | `eval/accuracy_gate_a.py:58-79` and `eval/profile_fixtures.py:99-149` build states with direct `sides[...] = PokemonState(...)`, which the invariant forbade | §3.1a — ALIAS-1 scoped to **registry-bound** slots, with explicit legacy adoption; the two fixture builders need no change |
| 6 | v3's `ability` meaning "is a decision the plan must make" | the question exists only because rev 2 left version selection ambiguous | §6.3 — the version is a **pure function of the switch**: off → v3 only, on → v4 only. No v3 mapping is needed, and a test asserts no v3 row can be written while on. |

**Also corrected in rev 3:** the §4.2 consumer table justified the speed row with *"Sand Rush
suppressed by Neutralizing Gas"* — unreachable, because §4.5 correctly records that suppression is
**not** modelled. The row is justified by ability *change* instead.

**One review claim I checked and did not accept.** The review states that First Impression is not
disabled even in the Champions mod. `data/mods/champions/moves.ts:364-372` overrides it with the same
`onDisableMove` shape as Fake Out. The finding stands anyway — it rests on base gen 9, where neither
move is disabled — but the reason is recorded correctly (§5.1a).

**Two errors of mine that this table should not disguise.** Rev 2's `cant` list was incomplete
because I read a `head -40`-truncated grep as a complete enumeration, and rev 2's own-side conclusion
was global because I generalised from the one format I had checked. Both are the same failure:
treating a partial look as a finished one.

---

## 1. Problem, stated exactly

Five confirmed defects on `main @ 4e9ebcf2`, all current-panel exposed and all reachable on the
shipped default configuration. They are one slice because they share one root: **the bot has no
concept of a combatant that persists across a switch, and no source of ability truth at all.**

| Item | Defect | Verified at |
|---|---|---|
| **8** | A `switch` event constructs a fresh `PokemonState` and replaces the slot entry. Revealed moves, `item_known`, `item_lost`, ability, types, boosts and base identity are discarded. | `engine/state.py:153-168` |
| **3** | `\|-ability\|` is not a parsed event, so an opponent's revealed ability never reaches state. | `engine/log_parser.py:111-364` (no handler) |
| **20** | `PokemonSlot` models neither `ability` nor `baseAbility`, so Pydantic drops both from our own request; `merge_request` never sets `mon.ability`. | `models/request.py:56-66`, `engine/state.py:348-401` |
| **15** | `move_priority()` takes no actor and `speed_modifiers_from_state()` reads no ability, hard-coding `booster_speed=False`. No ability affects turn order anywhere. | `engine/moves.py:165-170`, `engine/speed.py:57-68` |
| **23** | `moved_since_switch` is set only by a parsed `\|move\|`; the parser has no `cant` event, so a prevented turn leaves Fake Out looking fresh. | `engine/state.py:73,193-198` |

### What the code inspection added beyond the audit

Four findings that change the design and were not in the audit register.

**1.1 — `mon.ability` is already written, from a dex guess.**
The audit says ability never reaches state. That is true of *observed* ability; it is not true of the
field. `apply_event` writes `mon.ability = form_meta.ability_slot0` on `detailschange`
(`engine/state.py:222`) and `_apply_mega_reconcile` does the same (`:320`). `ability_slot0` is the
dex's **slot-0 ability** for the species (`engine/species_meta.py:59`) — a default, not an
observation. So today `PokemonState.ability` holds one of two things: `None`, or *a guess written
after a form change*, and nothing distinguishes them. This is load-bearing because that value flows
to the damage calculator: `hypothesis_from_state` → `SetHypothesis.ability` → `CalcMon.ability` →
the calc payload (`engine/belief/hypotheses.py:136,116`; `engine/calc/models.py:28-29`). **The
design must therefore introduce provenance on the ability field, not merely populate it.**

**1.2 — a third identity-loss site exists.**
`engine/validate.py:236-253` (`_copy_mon`) rebuilds a `PokemonState` field by field and silently
drops `consecutive_protect`, `moved_since_switch`, `item_lost` and `base_species_id`. Any
field added by this slice will be dropped there too unless that function is addressed.

**1.3 — the belief layer already knows about the reset, and compensates by forgetting.**
`BeliefTracker._resync_side` deletes hypotheses for slots "no longer present (e.g. after a switch
reset)" (`engine/belief/tracker.py:47-50`). The comment names the defect. Belief is keyed by
`(side, slot)` throughout, so it inherits whatever identity model state has.

**1.4 — an identity key already exists in this repository, on the learning side.**
`learning/belief_builder.py:71-83` keys its roster, movesets, stats and quality maps by the **ident
suffix** — `slot.ident.split(": ", 1)[-1]` — explicitly "matching the `target_ident` convention from
`actions.py`". `showdown_bot/tests/test_rollout_switch_regression.py:72-127` freezes that
convention. **S1 must adopt this key rather than invent a second one**, or the two halves of the
codebase will disagree about what a combatant is.

---

## 2. Scope

### In scope

Audit items **3, 8, 15, 20, 23**, and the two code-inspection findings 1.1 and 1.2 that fall out of
them.

### Non-goals, each with its owner

| Excluded | Where it belongs |
|---|---|
| Switch **execution** in the resolver / `PlannedAction` switch targets (item 9) | S2 |
| Legality, `adjacentAlly` targeting, Choice-lock (items 1a, 1b, 1c, 22) | S2 / S5 |
| Resolved move effects, secondaries, screens, calc field binding (items 2, 14, 16, 17, 24, 25) | S3 |
| Depth-2 terminal values and private own actions (items 10, 11) | D — off by default, stays off |
| Runner, requeue, executor, calc lifecycle (items 4, 5, 6, 7, 12, 13) | E |
| Audit item 1a's argmax question | separate small investigation, per the standing instruction |
| Item 19 (request active-order) | needs the pinned server source, which is not in this repository |

**No production code change. No new battle or experiment. No sealed-holdout access. No strength or
production-readiness claim. Depth 2 is not activated. No implementation before this design and its
plan are separately approved.**

---

## 3. Contract A — combatant identity, active slots, re-entry

### 3.1 The three-level model

Today `BattleState.sides` is `{side: {slot: PokemonState}}` and a slot is the *only* addressable
thing. The contract introduces a middle level **beside** it, not instead of it.

```
BattleState
  .sides        : {side: {slot: PokemonState}}          # UNCHANGED — canonical, mutable, aliased
  .combatants   : {side: {combatant_key: PokemonState}} # NEW — registry of every combatant seen
  .active_slots : {side: {slot: combatant_key | None}}  # NEW — who is standing where
```

- A **combatant** is one Pokémon for the whole battle. It is created once, on first observation, and
  is never replaced.
- A **switch** rebinds `active_slots[side][slot]` and points `sides[side][slot]` at the **same
  object** already in `combatants`. It **must not** construct a `PokemonState` for a combatant that
  already exists.

### 3.1a Why `sides` stays, and the invariant that makes it safe

Rev 1 introduced the registry without saying what happens to `sides`. That was the largest gap in it:
`.sides[…]` / `.side(…)` is referenced **94 times in production and 323 times in tests** (measured
with `grep -rn "state\.sides\|\.sides\[\|\.side(" --include="*.py"` over `src/` and `tests/`).
Removing or shadowing it is not a slice, it is a rewrite.

**Decision: `sides` remains the canonical mutable store. `combatants` holds the *same objects*.**
Existing consumers are untouched and see exactly what they see today — the only difference is that
after a re-entry they see a *reused* object rather than a fresh one.

**Invariant ALIAS-1.** For every slot that the registry has bound,
`sides[side][slot] is combatants[side][active_slots[side][slot]]` — **object identity, not equality.**

**ALIAS-1 is scoped to registry-bound slots, and that scope is load-bearing.** Rev 2 stated it over
*every* bound slot and claimed "existing consumers are untouched". Both cannot be true: `sides` is a
plain `dict`, so a direct `sides[side][slot] = PokemonState(...)` cannot update the registry, and
those writers exist:

| Writer | What it does |
|---|---|
| `learning/simulator.py:37-49` `_apply_switches` | assigns a roster mon into `sides` directly |
| `engine/mega_projection.py:46-51` `copy_battle_state` | rebuilds `sides` wholesale after a deepcopy |
| `eval/accuracy_gate_a.py:58-79` | builds fixture states with `sides[...] = PokemonState(...)` |
| `eval/profile_fixtures.py:99-149` | same |

Under rev 2's wording those last two produce states that **violate the invariant by construction**.

**Contract — legacy adoption, not universal enforcement.**

1. **Registry-bound** slots satisfy ALIAS-1. A slot becomes bound only through the switch/rebind path
   or through explicit registration.
2. **Unregistered** slots are legal. `active_slots[side][slot]` is `None` and the slot has no
   `combatants` entry. Reads behave exactly as today; re-entry knowledge simply does not accumulate,
   which is precisely today's behaviour and therefore not a regression.
3. **Adoption is lazy and explicit.** The first `switch` event for a side adopts any pre-existing
   `sides` entries for that side into the registry, keyed by §3.2, preserving object identity. A
   fixture that never replays a switch stays unregistered forever and never needs to change.
4. **`_resync`-style consumers read `sides`**, never `combatants`, so an unregistered slot is
   invisible to them.

This is what makes "existing consumers are untouched" true as stated: the two eval fixture builders
need **no change**, and the two production writers are migrated because they are on the live and
learning paths, not because the invariant forces every writer to be.

**Rejected alternative:** making `sides` a registering `MutableMapping` so that any assignment
updates the registry. It would enforce ALIAS-1 universally and remove the unregistered case — but it
replaces a plain dict on a hot path used 94 times in production, and a `__setitem__` that mutates two
other structures is exactly the hidden-state coupling this contract exists to avoid. The plan may
revisit it; this design does not adopt it.

Three consumers must be migrated and tested, because each can break ALIAS-1 in a different way:

| Path | Hazard | Required handling |
|---|---|---|
| `engine/mega_projection.py:46-51` `copy_battle_state` | full `deepcopy(state)` **then overwrites** `copied.sides` with per-mon `copy.deepcopy(mon)` from the *original*. Under a registry this yields two independent object sets: `combatants` from the first deepcopy, `sides` from the second. **ALIAS-1 breaks silently.** | must rebuild `combatants` and `active_slots` from the same copies, or stop overwriting `sides` |
| `learning/simulator.py:37-49` `_apply_switches` | assigns `state.sides[side][slot] = new_mon` directly from the roster, bypassing the registry | must go through the same rebind path, registering the roster mon as a combatant |
| `learning/simulator.py:20-21` `clone_state` | plain `copy.deepcopy(state)` — **safe**: one deepcopy call shares a memo, so aliases survive | no change; a test pins that it stays safe |

`eval/decision_capture.py` reads `sides` and is unaffected by the registry, but is affected by §6.3.

**Deliberately not in this slice:** removing `sides`, or making `combatants` the primary and `sides`
a computed view. Either is a legitimate later refactor; neither is needed for the five defects, and
both would put a 400-call-site change inside a correctness slice.

### 3.2 `combatant_key` — definition and derivation

```
combatant_key := (side, ident_suffix)
ident_suffix  := the part of the protocol ident after ": "   # "p1a: Chomp" → "Chomp"
```

This is the key `learning/belief_builder.py` already uses and `actions.py` already emits as
`target_ident`. Adopting it means the state layer and the learning layer address combatants
identically, and the existing switch-target plumbing needs no translation.

**Why not species.** Species is not stable: `detailschange` and Mega both rewrite `mon.species`
(`engine/state.py:218`, `:315`). Keying by species makes a Mega Evolution look like a different
combatant, which is exactly the identity break this contract exists to prevent.

**Why not nickname alone.** Nicknames are per-side; the same nickname can occur on both sides. The
key is a `(side, ident_suffix)` pair, never a bare string.

**Known limitation, stated rather than hidden.** Showdown's ident suffix is the nickname, and a
player may give two Pokémon the same nickname. In that case two combatants collapse into one and
their knowledge merges. This is:

- **not new** — `learning/belief_builder.py` and every `target_ident` switch already have it;
- **not present on the current panel** — all four committed team files use bare species names, all
  distinct within a team;
- **detectable** — §3.5 requires a diagnostic counter when a `switch` binds an existing key whose
  recorded identity disagrees with the incoming details. That comparison must go through form
  metadata, **not** a raw `base_species_id`-vs-species string test — see §3.5.

A stronger key (e.g. ident + first-seen details) is deliberately **not** adopted in this slice: it
would diverge from `target_ident` and break the learning-side lookup for a case with no current
exposure. The counter exists so the decision can be revisited on evidence.

### 3.3 Re-entry semantics — what survives, what resets

The rule is: **what the Pokémon *is* survives; what its *current turn on the field* is resets.**

| Field | On re-entry | Why |
|---|---|---|
| revealed `moves`, `move_names` | **survive** | knowledge, not board state |
| `item`, `item_known`, `item_lost` | **survive** | a consumed item stays consumed — this is the leak that lets a spent item become a live preset hypothesis again |
| `base_ability` + `base_ability_source` (§4.2) | **survive** | knowledge — what the Pokémon *is* |
| `types`, `base_species_id`, `tera_type`, `terastallized` | **survive** | identity |
| `level`, `gender`, `nickname` | **survive** | identity |
| `hp`, `max_hp`, `status`, `fainted` | **overwritten from the switch event** | the event is authoritative |
| `boosts` | **reset to `{}`** | Showdown clears stat stages on switch-out |
| `consecutive_protect` | **reset to `0`** | the Protect chain breaks on switch-out |
| `had_move_opportunity` | **reset to `False`** | that is the field's meaning (§5.1c) |
| `effective_ability` (§4.2) | **reset to `base_ability`** | `sim/pokemon.ts:1528`, inside `clearVolatile()`: `this.ability = this.baseAbility` |
| `unburden_active` (§5.2.1a) | **reset to `False`** | `data/abilities.ts` — Unburden's `onEnd` removes the volatile on switch-out |
| `species` | **overwritten from the switch event's details** | a form may have reverted while off-field |

**Volatiles are out of scope beyond the three transients named above** (`consecutive_protect`,
`had_move_opportunity`, `unburden_active`). Anything else Showdown clears on switch-out is not
tracked today and is not added here. The contract must not be read as claiming full switch-out
semantics.

**The shape of this table is the actual contract**, and rev 2 is where it earned that status: two of
the three review findings were *misplacements in it* — `effective_ability` and `unburden_active` were
absent, so rev 1 would have let an ability change and an Unburden boost persist across a switch that
the server clears. Anything added to `PokemonState` later must be classified here, in this table,
before it is added.

### 3.4 Faint, and why it is not the same as switch-out

A fainted combatant keeps its entry in `combatants` with `fainted=True`. Its slot binding is set to
`None` when the replacement switches in. Knowledge about a fainted Pokémon stays available — the
opponent's dead Incineroar's revealed Fake Out is still evidence about their team.

### 3.5 Required diagnostics, and the false alarm rev 1 would have shipped

Three counters, exposed for tests and for the decision profile, all **non-behavioural**:

- `combatant_created` — a `switch` produced a new key;
- `combatant_rebound` — a `switch` bound an existing key (the case that is broken today);
- `combatant_key_conflict` — a `switch` bound an existing key whose identity disagrees with the
  incoming details.

**The conflict test must resolve through form metadata.** Rev 1 specified a direct comparison of the
stored `base_species_id` against the incoming species, and that fires on a perfectly legitimate
re-entry:

> A Mega Evolution is a **permanent** forme change on the pinned server — `runMegaEvo` calls
> `formeChange(speciesid, item, true)` (`sim/battle-actions.ts:1906`) and `isPermanent` rewrites
> `baseSpecies` **and** `details` (`sim/pokemon.ts:1447-1449`). Meanwhile
> `_apply_mega_reconcile` sets our `base_species_id = to_id(event.base_species)` — the family base,
> `"aerodactyl"` (`engine/state.py:316`). So a Mega'd Aerodactyl that switches out and back returns
> with details `Aerodactyl-Mega`, and `"aerodactyl" != "aerodactylmega"` reports a conflict for the
> same combatant.

**Contract.** Resolve the incoming details through `get_species_form_meta(...)` and compare
`base_species_id` to `base_species_id` — the same family-granularity comparison
`_apply_mega_reconcile` already performs and already documents as the correct granularity
(`engine/state.py:264-277`). An unknown species falls back to the stored id, i.e. to no conflict,
which is the fail-quiet direction for a diagnostic counter.

§7 group 1 adds `test_mega_evolved_combatant_reentry_is_not_a_conflict`.

---

## 4. Contract B — ability truth: intrinsic vs. effective

### 4.1 The distinction rev 1 collapsed

Rev 1 used one field and one precedence ladder. That cannot work, because the pinned server keeps two
different things and our two input channels report *different ones*:

- **`baseAbility`** — what the Pokémon intrinsically has. Persistent.
- **`ability`** — what is in effect right now. `sim/pokemon.ts:1528`, inside `clearVolatile()` — the
  switch-out path — resets it: `this.ability = this.baseAbility`.

Rev 1 preferred the request's current `ability` over `baseAbility` for our side, while treating a
public reveal as intrinsic for the other side. `mon.ability` would then have meant *effective* on one
side and *intrinsic* on the other, and neither would have survived a switch correctly.

The protocol makes the same split explicit (`sim/SIM-PROTOCOL.md:512-524`):

| Line | Meaning per the pinned protocol doc | Maps to |
|---|---|---|
| `\|-ability\|POKEMON\|ABILITY\|[from]EFFECT` | *"The ABILITY of the POKEMON has been **changed** due to a move/ability EFFECT."* | **effective** only |
| `\|-ability\|POKEMON\|ABILITY` | *"POKEMON has just switched-in, and its ability ABILITY is being announced to have a long-term effect"* (Mold Breaker, Neutralizing Gas) | **intrinsic** (and therefore also effective) |

Rev 1 proposed **ignoring** `[from]` lines. That is wrong in the other direction: they are the only
public signal that an ability changed, and dropping them leaves Trace/Skill-Swap/Role-Play boards
silently modelled with the wrong ability in play.

### 4.2 The field contract

`PokemonState` carries two abilities and one provenance marker for the intrinsic one:

```
base_ability        : str | None     # intrinsic; survives switch-out (§3.3)
base_ability_source : "unknown" | "assumed" | "revealed" | "request"
effective_ability   : str | None     # in play right now; RESET TO base_ability on switch-in
```

`effective_ability` needs no provenance: it is always either `base_ability` or a value set by an
observed `[from]` change.

**`PokemonState.ability` is retired as a name.** Leaving a field called `ability` meaning one of the
two would reproduce exactly the ambiguity this section exists to remove. Every consumer is updated
explicitly, which is a small, enumerable set (`engine/belief/hypotheses.py:116,136`,
`engine/validate.py:247,264`, `eval/decision_capture.py:66`, `engine/calc/models.py:28-29` via
`CalcMon`).

**Which one each consumer wants** — this is a decision, not a mechanical rename:

| Consumer | Uses | Why |
|---|---|---|
| damage calc (`CalcMon.ability`) | **effective** | the calc must model the ability actually modifying damage now — after a Trace or a Mega, not before |
| speed / priority predicates (§5.2) | **effective** | a Traced or swapped Sand Rush should double speed; the pre-swap ability should not |
| `SetHypothesis` preset filtering | **intrinsic** | belief is about what this Pokémon *is*; a Traced ability tells us nothing about its set |

**Correction to rev 2's justification.** Rev 2 argued the speed row with *"Sand Rush suppressed by
Neutralizing Gas must not double speed"*. That contradicts §4.5, which correctly records that
**suppression is not modelled** — there is no `suppressed` state, so `effective_ability` cannot
express it and the example was unreachable. The row is justified by *ability change* (Trace, Skill
Swap, Role Play, Mega), which `effective_ability` does express. Suppression remains a stated
limitation, not a benefit.

### 4.2a `SetHypothesis` must split too — the contract rev 2 left unimplementable

Rev 2 stated the consumer split and stopped. It is not reachable by renaming `PokemonState` fields,
because the two consumers share one object:

- `hypothesis_from_state()` writes a single `ability` into `SetHypothesis`
  (`engine/belief/hypotheses.py:136`, field at `:88`);
- `_to_calc_mon()` passes that same value straight into `CalcMon.ability` (`:116`), and
  `as_attacker()` / `as_defender()` are thin wrappers over it.

So whatever single value `SetHypothesis` carries reaches **both** preset filtering and the calc. A
`PokemonState`-only change gives the calc whichever one belief chose, or the reverse — never both.

**Contract.** `SetHypothesis` carries both, and the split is made where the object is built:

```
SetHypothesis.base_ability      : str | None    # preset filtering / belief
SetHypothesis.effective_ability : str | None    # passed to CalcMon.ability
```

- `hypothesis_from_state()` copies both from the combatant.
- `_to_calc_mon()` emits `effective_ability` into `CalcMon.ability`, falling back to `base_ability`
  when it is `None`.
- Preset and item-candidate logic reads `base_ability` only.

`engine/validate.py:247,264` (`_mon_from_known`) is on the same path and takes `effective_ability`
for the same reason as the calc.

**Why not a call-site override instead.** An `effective_ability=` keyword threaded through
`as_attacker()` / `as_defender()` would work, but every caller would have to remember to pass it, and
a forgotten one silently reverts to the old behaviour. Carrying both on the object makes the split
structural. The plan may propose the override form; it must then say how a missed call site is
detected.

### 4.3 Precedence for `base_ability`

Strictly monotonic: `request` ≥ `revealed` > `assumed` > `unknown`. A lower-confidence source never
overwrites a higher one.

| Source | Reaches state via | Rank |
|---|---|---|
| our request's `baseAbility` | `merge_request` | `request` |
| `\|-ability\|` **without** `[from]` | `apply_event` | `revealed` |
| `species_meta.ability_slot0` after a form change | `detailschange`, `_apply_mega_reconcile` | `assumed` |

**Form changes remain the one legitimate override — and they set *both* fields, atomically.**
Rev 2 said "only for the intrinsic value". **That was wrong**: a Mega Evolution changes what is in
play *and* what the Pokémon is. Aerodactyl-Mega has Tough Claws; leaving `effective_ability` at
Unnerve would make every damage calculation and every speed predicate read a pre-Mega ability for
the rest of the battle — a defect introduced by the very rule meant to keep the fields honest.

**Contract.** `detailschange` and `_apply_mega_reconcile` set

```
base_ability      ← form_meta.ability_slot0   (rank `assumed`, overriding any higher rank)
effective_ability ← form_meta.ability_slot0
```

as a single update. This is the sole place a higher rank is overwritten, and it is the sole place
`effective_ability` is set to something other than an observed change or `base_ability`. §7 pins
both halves — rev 2's test asserted `base_ability` only, which is exactly how the gap survived.

### 4.4 Own-side plumbing (item 20)

`PokemonSlot` gains **both** `ability` and `base_ability` (aliases `ability`, `baseAbility`).
`merge_request` writes:

- `base_ability` ← request `baseAbility`, rank `request`;
- `effective_ability` ← request `ability` when present, else `base_ability`.

That is the correct direction and the exact inverse of rev 1's rule.

**Packed-team ability is deliberately not used** (staleness rules are their own design question; the
request is authoritative for our side and arrives every turn).

### 4.5 Public plumbing (item 3)

`engine/log_parser.py` gains a `-ability` handler that **records whether a `[from]` tag was
present** — the tag is the discriminator, so a parser that drops it cannot implement §4.1.

- no `[from]` → set `base_ability` at `revealed` rank, and set `effective_ability` to match;
- with `[from]` → set `effective_ability` only; `base_ability` is untouched.

**Still out of scope, and now for a stated reason rather than by omission:** `-endability` and
ability *suppression* (Gastro Acid, Neutralizing Gas) change whether an ability applies at all, which
needs a third state (`suppressed`) rather than a third value. §5.2 therefore reads
`effective_ability` and cannot see suppression — recorded as a known limitation, not modelled.
Skill Swap between allies emits nothing at all (`SIM-PROTOCOL.md:516-518`), so no parser can catch
it; that is a property of the protocol, not a gap in this design.

## 5. Contract C — first-turn-move freshness and dynamic order

### 5.1a Our own side: `disabled` where the server sets it, `had_move_opportunity` everywhere else

Rev 2 said "our own side reads `move.disabled`; `drop_first_turn` is removed from the own-side
enumeration path rather than repaired". **That was a global conclusion from a format-local premise
and is withdrawn.**

What the pin actually shows:

| | base gen 9 (`data/moves.ts`) | Champions mod (`data/mods/champions/moves.ts`) |
|---|---|---|
| Fake Out | `onTry` at `:5096-5099` — checked at **execution**, never marked `disabled` | `onDisableMove` at `:331-338` — marked `disabled` in the request |
| First Impression | `onTry` at `:5482-5487` — checked at **execution** | `onDisableMove` at `:364-372` — marked `disabled` in the request |

Two consequences rev 2 missed:

1. **`_FIRST_TURN_MOVES` is `{"fakeout", "firstimpression"}`** (`battle/resolve.py:18`), not Fake Out
   alone. Rev 2 discussed only Fake Out.
2. **Two of the three supported formats are base gen 9** — `config/formats/` holds
   `gen9championsvgc2026regma`, `gen9vgc2024regg` and `gen9vgc2025regi`. On the latter two **neither**
   move is ever `disabled`, so a global removal of `drop_first_turn` re-offers a stale Fake Out *and*
   a stale First Impression on two thirds of the formats this bot supports.

**Contract.** Per slot, per move, the own-side first-turn filter is:

```
drop  ⟺  move.disabled                      # authoritative wherever the server sets it
      ∨  (move.id ∈ _FIRST_TURN_MOVES ∧ had_move_opportunity)   # repaired fallback
```

- `disabled` is honoured first and needs no format knowledge (`legal_actions.py:112-113` already
  does this).
- The fallback is the **repaired** predicate from §5.1c — never the broken `moved_since_switch`.
- **No format detection.** The rule is a disjunction, correct on every format: where the server
  disables, the first clause fires and the second is redundant but harmless; where it does not, the
  second carries it.

So `drop_first_turn` is **kept and re-fed**, not removed. What rev 2 got right and this keeps: on
Champions the server's answer is authoritative and arrives every turn, which is why the fallback
never has to be exactly right there.

**One correction to the review, verified.** The review states that First Impression is not disabled
even in the Champions mod. That is false: `data/mods/champions/moves.ts:364-372` overrides it with
the same `onDisableMove` shape as Fake Out. The finding stands regardless — it rests on base gen 9,
where neither move is disabled.

### 5.1b The opponent side: the complete `cant` taxonomy

For the opponent there is no request, so log-derived freshness is the only source.

**Rev 2's allowlist was incomplete, and the cause was mine.** I enumerated with
`grep -rn "add('cant'" sim/ data/ | head -40` and read a truncated result as complete — the old-gen
mods filled the window and `data/moves.ts` never appeared. Re-run without truncation and scoped to
gen 9 plus the Champions mod, the full picture is:

**Self class — the named Pokémon lost its own action:**

| Reason token | Source |
|---|---|
| `par`, `slp`, `frz`, `flinch`, `recharge` | `data/conditions.ts:42,76,103,203,369` |
| `par`, `frz` (mod overrides) | `data/mods/champions/conditions.ts:6,53` |
| `nopp` | `sim/battle-actions.ts:283` |
| `ability: Truant` | `data/abilities.ts:5183` |
| `Attract` | `data/moves.ts:746` |
| `Disable` | `:3700` |
| `Focus Punch` | `:6017` |
| `Shell Trap` | `:16299` |
| `move: Gravity` | `:7822, 7828, 10870, 17703, 19140` |
| `move: Heal Block` | `:8312, 8318, 8331, 13587` |
| `move: Imprison` | `:9516` |
| `move: Taunt` | `:19018` |
| `move: Throat Chop` | `:19424, 19430` |

**Third-party class — the named Pokémon *blocked someone else*:**

| Reason token | Source |
|---|---|
| `ability: Armor Tail` | `data/abilities.ts:225` |
| `ability: Damp` | `:805` |
| `ability: Dazzling` | `:864` |
| `ability: Queenly Majesty` | `:3716` |

**Contract — three outcomes, not two.**

| Reason | Effect | Counter |
|---|---|---|
| in the **self** list | sets `had_move_opportunity` | `cant_self` |
| in the **third-party** list | sets nothing | `cant_third_party` |
| **in neither** | sets nothing | **`cant_unknown`** |

Rev 2 had only two buckets and routed everything unrecognised to `cant_third_party`. That was wrong
twice: it mislabels the diagnostic, and — because the unknown bucket was silently the third-party
one — a future or missed reason would have looked like a known, handled case. **An unknown reason is
its own counter.**

**The list is complete for gen 9 base + the Champions mod, and that is the claim.** It is not a
claim about other mods or future server versions; `cant_unknown` is what makes the boundary
observable rather than silent.

**A limitation the enumeration exposes.** Some self-class reasons fire from inside `runMove` (so the
opportunity is genuinely consumed — `activeMoveActions` increments at `sim/battle-actions.ts:217`,
before any `TryMove`), while others may fire at selection time. This slice treats every self-class
reason as consuming, because that is the fail-closed direction for a first-turn move: it can make
Fake Out look *stale* when it was fresh, never fresh when it was stale. Rev 1's stronger claim that
this is therefore "safe" stays withdrawn — removing an action can change the argmax; the direction is
merely the less bad one.

**The third-party gap, unchanged from rev 2.** The prevented mover *does* consume its opportunity,
but the third-party event names the blocker and the move's target, never that mover. The bot cannot
attribute it, and this slice counts rather than guesses. Review has accepted a diagnostic counter as
sufficient for S1.

### 5.1c The field

```
had_move_opportunity : bool   # a move action was consumed since this combatant switched in
```

Set by `|move|` (as today) and by a **self-class** `|cant|` (§5.1b). Reset to `False` on switch-in
(§3.3). It replaces `moved_since_switch`, whose name asserted something narrower than what both the
enumerator (§5.1a fallback) and the resolver (`battle/resolve.py:281-286`) need.

### 5.2 Dynamic action order (item 15)

**5.2.1 Ability speed modifiers.** `speed_modifiers_from_state()` gains the actor's **effective**
ability (§4.2) and derives its modifiers from it, instead of hard-coding `booster_speed=False`. The
function's own docstring already anticipates the signal.

| Ability | Panel exposure | Predicate, as verified on the pin |
|---|---|---|
| Sand Rush | `trick_room` Excadrill | `field.weather` is sand. **No immunity condition** — sand immunity governs sandstorm *damage*, not this ability. (Rev 1 invented one.) |
| Unburden | `goodstuff`, `tailwind_offense` Sneasler | **see 5.2.1a — not `item_lost`** |
| Gale Wings | `tailwind_offense` Talonflame | priority, not speed — 5.2.2 |
| Protosynthesis / Quark Drive | not on the current panel | needs a booster-active signal that does not exist; **out of scope**, contributes nothing |

**5.2.1a Unburden is volatile, and rev 1 got it wrong.**
Rev 1 said the predicate "is precisely `item_lost`", and used that as its argument for sequencing §3
before §5. The pin says otherwise (`data/abilities.ts:5227-5245`):

```ts
unburden: {
  onAfterUseItem(item, pokemon) { /* ... */ pokemon.addVolatile('unburden'); },
  onTakeItem(item, pokemon)     { pokemon.addVolatile('unburden'); },
  onEnd(pokemon)                { pokemon.removeVolatile('unburden'); },
  condition: { onModifySpe(spe, pokemon) {
    if (!pokemon.item && !pokemon.ignoringAbility()) return this.chainModify(2);
  } },
}
```

Unburden is a **volatile**, granted when the item is lost *while the ability is active* and removed
by `onEnd` — which fires on switch-out. Its condition additionally requires **no current item**.

Rev 1's rule would have given a re-entered, still-itemless Sneasler permanent double Speed. That is a
**new state defect**, worse than the one being fixed, because it would have been introduced
deliberately and documented as correct.

**Contract.** A separate transient field:

```
unburden_active : bool   # granted on item loss while Unburden is the effective ability
                         # RESET TO False on switch-in (see §3.3)
```

The speed modifier requires `unburden_active` **and** `effective_ability == "Unburden"` **and** no
current item. `item_lost` is untouched: it survives re-entry for belief (§3.3) and is no longer the
Unburden predicate.

**The dependency argument survives, in corrected form.** Unburden still argues for §3 before §5 — not
because it reads `item_lost`, but because `unburden_active` is a per-combatant transient that needs a
combatant to live on and a switch hook to reset it, and neither exists today.

**5.2.2 Ability priority.** `move_priority(meta, field)` gains an optional actor:
`move_priority(meta, field, actor=None)`. With `actor=None` it returns exactly today's value, so
every existing call site and every golden stays byte-identical. `sort_actions` passes the actor.

Scope is **one ability: Gale Wings** — predicate: full HP **and** a Flying-type move **and**
`effective_ability == "Gale Wings"`. No other priority ability has current-panel exposure, and a
general priority-modifier framework is not justified by one case.

**5.2.3 Where the predicates live — a new config surface, verified absent today.**
`config/species/speciesdata.json` carries only `abilities: {"0","1","H"}` — *names*. There is **no**
ability-effect data anywhere in `config/` (`moves/` and `items/` each have an effect-class overlay;
abilities have none). The predicates cannot be data-driven from what exists, so this slice must
introduce the surface:

- a **small curated table** covering exactly the abilities named above and no others;
- an **unknown ability is a no-op**, never a guess — today's behaviour, and the safe default;
- if it is a file whose bytes are hashed it needs a `text eol=lf` rule in `.gitattributes` in the
  same commit (§6.4); if it is a Python constant it does not. The plan must state which and why;
- follow the shape of `config/moves/effect_classes.yaml` or `config/items/item_effect_classes.yaml`
  rather than inventing a third.

**Explicitly out of scope for 5.2:** speed ties, Trick Room beyond the existing sort flip, item order
effects other than Choice Scarf, Prankster, and ability *suppression* (§4.5).

## 6. Invariants, migration and compatibility

### 6.1 Project invariants

| INV | Bearing on S1 |
|---|---|
| **INV-1** live-path allowlist | S1 adds no new action source. Enumeration is unchanged except that §5.1 fixes *when* Fake Out is dropped. The heuristic safety floor and the fallback chain are untouched. |
| **INV-2** memory = priors only | Ability truth is **observation**, not memory, and it enters the same state the log already builds. It changes probabilities via `SetHypothesis`; it never picks an action. |
| **INV-3** anytime/abortable | No new blocking work on the turn path. All of S1 is state application and pure functions; no calc call, no I/O. |
| **INV-4** one layer at a time + ablation gate before default-on | **Binding and load-bearing — see §6.2.** |
| **INV-5** no LLM | not touched |
| **INV-6** no label leakage | `FEATURE_COLUMNS` is not extended by this slice |
| **INV-7** model-artifact safety | no model artifact is produced |

### 6.2 INV-4: the ablation gate, and the honest problem with it

S1 must ship behind an env switch, default **off**, be proven byte-identical when off, and become
default-on only through an ablation gate against the previous configuration. The existing pattern is
`SHOWDOWN_ACCURACY_MODE` with `eval/accuracy_gate_a.py`.

**The problem this design must not paper over.** S1 is a *correctness* repair, not a strength lever.
An ablation gate answers "does this play better", and #128 §1 Fact 1 establishes that this repository
cannot currently answer that: there is no decision→outcome attribution, and the only live-path
evidence is one smoke battle. So the gate can report a dev-strength delta, and that delta cannot be
attributed.

The design's position, stated so the plan cannot quietly drop it:

- The switch is `SHOWDOWN_STATE_TRUTH_V1`, **BEHAVIOR_AFFECTING**, default **off** at merge.
- Off must be **byte-identical** to `main`, proven by a golden decision-trace comparison — this is
  the gate that actually protects the repository, and it is fully decidable here.
- Turning it **on by default is out of S1's scope.** It requires its own decision record naming what
  evidence would justify the flip, and that decision is the honest place to confront the
  attribution gap — not a strength number produced inside this slice.

An implementation plan that treats "dev-strength A/B looked better" as sufficient for the flip
contradicts this section.

### 6.3 Persisted-schema migration — the hard constraint

`eval/decision_capture.py:55-76` serialises the **complete** `PokemonState` field set into the
versioned decision trace (`TRACE_SCHEMA_VERSION = "decision-trace-v3"`, `:24`), with
`SUPPORTED_TRACE_SCHEMA_VERSIONS` gating readers (`:25-26, 563`). This slice changes that payload in
four ways: `ability` is **replaced** by `base_ability` + `base_ability_source` +
`effective_ability` (§4.2), `moved_since_switch` becomes `had_move_opportunity` (§5.1c), and
`unburden_active` is added (§5.2.1a).

**Contract — and rev 2's open question is closed here, not delegated.**

Rev 2 wrote that "which value v3's `ability` carries when the switch is on is a decision the plan
must make". That was wrong to defer: #129 requires a *defined* schema migration, and the question
only exists because rev 2 left the version selection ambiguous. It is closed by removing the
ambiguity rather than by choosing a mapping.

1. **The schema version is a pure function of the switch.**
   `SHOWDOWN_STATE_TRUTH_V1` **off → v3 only**; **on → v4 only**. There is no configuration in which
   the new fields exist and a v3 row is written, so **no v3 `ability` mapping is needed and none is
   defined**. Any code path that could emit v3 while the switch is on is a defect, and §7 test 37
   is the assertion.
2. **v4 mints the new field set**: `base_ability`, `base_ability_source`, `effective_ability`,
   `had_move_opportunity`, `unburden_active`. The v3 keys `ability` and `moved_since_switch` do not
   appear in v4 — a reader that wants "the ability" must choose which one it means, which is the
   whole point of §4.
3. **v3 stays readable, unchanged, forever.** `SUPPORTED_TRACE_SCHEMA_VERSIONS` gains v4 and keeps
   v1–v3.
4. **While off, writes are v3 and byte-identical.** The version bump is tied to the switch, not to
   the merge.
5. **Frozen evidence is never rewritten.** No artifact under `data/eval/` is touched; the Gate B and
   Attempt-6 freezes stay valid because their rows are v3 and v3 readers survive.

**The consequence, stated rather than buried:** a consumer that reads both v3 and v4 rows sees
`ability` on the old ones and two fields on the new ones, and must decide per row. That is correct —
the fields genuinely mean different things — but it is a real cost of the split and it belongs in
this contract rather than in a reader's assumptions.

### 6.4 Byte-stability

This slice adds no file whose bytes are hashed. If the plan introduces a fixture or config file that
`format_config_hash` / `file_content_hash` / `_sha256_file` reads, it needs a `text eol=lf` rule in
`.gitattributes` **in the same commit**.

### 6.5 The three identity-loss sites must be fixed together

`engine/state.py:153-168` (switch), `engine/state.py:363-378` (`merge_request` species fallback) and
`engine/validate.py:236-253` (`_copy_mon`). Fixing the first two and leaving `_copy_mon` field-by-field
reintroduces the bug on the validation path the moment a field is added. The plan must either make
`_copy_mon` a real copy or delete it in favour of `copy.deepcopy`.

### 6.6 Degradation and rollback

- **Rollback** is unsetting `SHOWDOWN_STATE_TRUTH_V1`. Because off is byte-identical and v3 writes
  continue, rollback needs no data migration.
- **An unknown ability** (no request field, no reveal, no form change) leaves `base_ability=None`,
  `base_ability_source="unknown"` and `effective_ability=None`, and every consumer behaves exactly as
  today. The slice never guesses to fill a gap.
- **An unrecognised `\|cant\|` reason** (§5.1b) — one in neither the self nor the third-party list —
  sets nothing and increments the third-party counter. Fail-quiet: the allowlist is derived from a
  pinned server, and a future reason should surface as a counter rather than as a silent state
  mutation.
- **A `combatant_key_conflict`** (§3.5) must not crash a live turn. It increments the counter, logs,
  and takes the incoming details as authoritative for `species`/`types` while keeping the existing
  combatant. Fail-open here is correct: a wrong merge costs accuracy, a raised exception costs the
  battle, and INV-1's safety floor exists to keep turns alive.

---

## 7. Acceptance tests (TDD order)

Each test is written and seen to fail before its implementation. A group may not start before the one
above it is green. Tests marked **[rev2]** exist because a rev-1 contract rule was wrong; each pins
the corrected rule against the pinned server.

### Group 1 — identity, re-entry, and the alias invariant (§3)

1. `test_switch_out_and_back_preserves_revealed_moves`
2. `test_switch_out_and_back_preserves_item_lost` — an `|-enditem|` before switch-out leaves
   `item_lost=True` on re-entry. **The widest blast radius**: this is what lets a consumed item
   become an eligible preset hypothesis again via `hypothesis_from_state`.
3. `test_switch_resets_boosts_and_protect_chain`
4. `test_switch_takes_hp_and_status_from_the_event`
5. `test_fainted_combatant_knowledge_survives`
6. `test_active_slots_rebind_without_constructing_a_new_combatant` — asserts **object identity**,
   not field equality. This is the test that actually pins §3.1.
7. `test_alias_invariant_holds_after_every_switch` **[rev2]** — ALIAS-1 over registry-bound slots.
7a. `test_unregistered_slot_is_legal_and_reads_as_today` **[rev3]** — a fixture built with a direct
    `sides[...] = PokemonState(...)` (the `eval/accuracy_gate_a.py` / `eval/profile_fixtures.py`
    shape) is valid, has no `combatants` entry, and behaves exactly as on `main` (§3.1a rule 2).
7b. `test_first_switch_adopts_preexisting_slots_preserving_identity` **[rev3]** — lazy adoption
    (§3.1a rule 3), asserted on object identity.
8. `test_copy_battle_state_preserves_alias_invariant` **[rev2]** — the `engine/mega_projection.py:46-51`
   hazard: a full `deepcopy` followed by a per-mon `deepcopy` overwrite of `sides` must not leave
   `combatants` and `sides` holding different objects.
9. `test_clone_state_preserves_alias_invariant` **[rev2]** — `learning/simulator.py:20-21`; plain
   `deepcopy` is safe today, and this pins that it stays safe.
10. `test_simulator_switch_registers_the_roster_mon_as_a_combatant` **[rev2]** —
    `learning/simulator.py:37-49` currently assigns into `sides` directly.
11. `test_combatant_key_conflict_counts_and_does_not_raise` — duplicate nicknames (§3.2).
12. `test_mega_evolved_combatant_reentry_is_not_a_conflict` **[rev2]** — a Mega'd Aerodactyl switches
    out and back with details `Aerodactyl-Mega` while `base_species_id` is `"aerodactyl"`. Must
    **not** raise the conflict counter (§3.5).
13. `test_belief_tracker_does_not_drop_hypotheses_on_re_entry` — the `_resync_side` deletion path.

### Group 2 — ability truth (§4)

14. `test_request_ability_and_base_ability_parse` — `PokemonSlot` retains both.
15. `test_merge_request_maps_base_to_base_and_current_to_effective` **[rev2]** — the exact inverse of
    rev 1's rule.
16. `test_dash_ability_without_from_sets_base_at_revealed_rank` **[rev2]**
17. `test_dash_ability_with_from_sets_effective_only` **[rev2]** — `|-ability|p2a: X|Intimidate|[from]
    ability: Trace` changes `effective_ability` and leaves `base_ability` untouched
    (`sim/SIM-PROTOCOL.md:512`).
18. `test_switch_in_resets_effective_ability_to_base` **[rev2]** — `sim/pokemon.ts:1528`.
19. `test_detailschange_does_not_overwrite_revealed_base_ability` — the monotonicity rule, and a
    behaviour change from today.
20. `test_mega_reconcile_sets_base_and_effective_ability` **[rev3]** — both fields, atomically.
    Rev 2's test asserted `base_ability` only, which is how the gap survived: Aerodactyl-Mega would
    have kept Unnerve in play for the rest of the battle (§4.3).
20a. `test_detailschange_sets_base_and_effective_ability` **[rev3]** — the same rule on the
     non-Mega forme-change path.
21. `test_calc_receives_effective_ability_and_belief_receives_base` **[rev2]** — the split in §4.2's
    consumer table; without this the two-field design is indistinguishable from a rename.
21a. `test_set_hypothesis_carries_both_abilities` **[rev3]** — `SetHypothesis` splits too (§4.2a).
     Without this the consumer split is unimplementable: `hypothesis_from_state` writes one value
     and `_to_calc_mon` forwards that same value to `CalcMon`.
21b. `test_mon_from_known_uses_effective_ability` **[rev3]** — `engine/validate.py:247,264`, the same
     path.
22. `test_unknown_ability_reaches_calc_as_none` — no guessing.

### Group 3 — freshness (§5.1)

23. `test_own_side_first_turn_move_dropped_when_request_disabled` **[rev2]** — the Champions path,
    for **both** `fakeout` and `firstimpression` (`data/mods/champions/moves.ts:331-338, 364-372`).
24. `test_own_side_first_turn_move_dropped_by_fallback_when_not_disabled` **[rev3]** — the base-gen-9
    path, where the server uses `onTry` and never marks `disabled`. Covers **both** moves in
    `_FIRST_TURN_MOVES`. This is the regression rev 2 would have shipped on two of the three
    supported formats.
24a. `test_first_turn_filter_needs_no_format_detection` **[rev3]** — the §5.1a disjunction holds on
     both format shapes without branching on format id.
25. `test_cant_self_reasons_consume_the_opportunity` **[rev3]** — table-driven over the **complete**
    §5.1b self list: `par`, `slp`, `frz`, `flinch`, `recharge`, `nopp`, `ability: Truant`, `Attract`,
    `Disable`, `Focus Punch`, `Shell Trap`, `move: Gravity`, `move: Heal Block`, `move: Imprison`,
    `move: Taunt`, `move: Throat Chop`. Rev 2's list had seven of sixteen.
26. `test_cant_third_party_reasons_set_nothing_and_count` **[rev2]** — `ability: Armor Tail`,
    `ability: Damp`, `ability: Dazzling`, `ability: Queenly Majesty`. The named Pokémon is the
    **blocker**; a rev-1 handler would have frozen the flag on the wrong combatant.
26a. `test_unrecognised_cant_reason_counts_as_unknown` **[rev3]** — a reason in neither list sets
     nothing and increments `cant_unknown`, **not** `cant_third_party` (§5.1b). Rev 2 routed unknown
     reasons into the third-party bucket, which would have made a missed reason look handled.
27. `test_opponent_flinch_cant_marks_fake_out_stale` — the audit's original counterexample, on the
    side where the log is the only source.
28. `test_switch_in_resets_had_move_opportunity`

### Group 4 — order (§5.2), only after Groups 1–2 are green

29. `test_sand_rush_doubles_speed_only_in_sand` — and **no** immunity condition.
30. `test_unburden_requires_active_volatile_and_no_item` **[rev2]**
31. `test_unburden_does_not_survive_a_switch` **[rev2]** — a re-entered itemless Sneasler is **not**
    boosted. This is the defect rev 1 would have introduced; it is the single most important test in
    this group.
32. `test_gale_wings_priority_requires_full_hp_and_flying_move`
33. `test_move_priority_without_actor_is_unchanged` — pins the default-arg compatibility.
34. `test_speed_and_priority_read_effective_not_base_ability` **[rev2]**
35. `test_protosynthesis_does_not_set_booster_speed` — the explicit out-of-scope.

### Group 5 — gates

36. `test_state_truth_off_is_byte_identical` — golden decision-trace comparison against `main`, switch
    off. **This is the merge gate.**
37. `test_trace_v3_payload_unchanged_when_off`, `test_trace_v4_carries_new_fields_when_on`, and
    `test_no_v3_row_is_ever_written_while_the_switch_is_on` **[rev3]** — the last one is what makes
    §6.3's "no v3 `ability` mapping is needed" true rather than assumed.
38. `test_env_var_is_behavior_affecting` — `SHOWDOWN_STATE_TRUTH_V1` classified in
    `eval/config_env.py`, so it lands in `config_hash`; the drift test enforces classification.
39. Full offline suite — `python -m pytest` — run and reported, not inferred from CI.

### Existing tests — checked, not assumed

An earlier draft asserted that `showdown_bot/tests/test_battle_state.py` contains assertions written
against the reset semantics that would have to be rewritten. **I checked, and it does not.** Its
switch lines are fixture setup; `test_enditem_marks_item_lost` and `test_item_event_clears_item_lost`
both assert within a single switch-in and are unaffected.

Two standing rules survive that finding, because it is an expectation and not a guarantee:

- **No test may be deleted to make an S1 test pass.** If one does assert the defect, it is rewritten
  with the reason recorded in the commit message.
- The audit's 121-test targeted set and the full offline suite are both run. The audit recorded that
  those 121 pass on *unrepaired* code, so any of them turning red under S1 is a signal to read, not
  to silence.

(The one test known to freeze a defect — `test_legal_actions.py:118-126`, the Choice-item rule —
belongs to **S2**, not to this slice.)

## 8. Open questions for review

Rewritten each revision rather than appended to, so a reader never has to reconstruct which still
stand.

**Settled in review:**

1. **`combatant_key` granularity** — ident suffix with a collision counter, accepted for the current
   panel.
2. **Default-on gate** — its own decision record, not this slice. §6.2 unchanged.
3. **The blanket `cant` rule** — rejected; replaced by §5.1b's verified taxonomy, now complete.
4. **Gale Wings scope** — one priority ability rather than a framework, accepted.
5. **Third-party `cant`** — a diagnostic counter is sufficient for S1, accepted, **provided unknown
   reasons are not classified as third-party**. §5.1b now gives them their own counter.
6. **Retiring the name `ability`** — accepted, conditional on the v3 mapping and `SetHypothesis`
   being closed unambiguously. §6.3 closes the first by making the version a pure function of the
   switch; §4.2a closes the second by splitting `SetHypothesis`.

**Still open — one, and it is a scoping question rather than a defect:**

7. **The `sides` registering-mapping alternative** (§3.1a, "Rejected alternative"). This design keeps
   `sides` a plain dict and accepts unregistered slots, because a `__setitem__` that mutates two
   other structures is the hidden coupling the contract exists to avoid. The cost is that ALIAS-1
   holds over a subset rather than universally. If review prefers universal enforcement, that is a
   larger change and should be said now rather than during implementation.

## 9. Non-claims

- No claim that S1 improves strength. None of items 3, 8, 15, 20, 23 has a measured outcome effect,
  and §6.2 states why this slice cannot supply one.
- **Server claims in this document are verified**, against the pinned checkout named in the header
  (`f8ac1400…`, `data/` and `sim/` byte-clean). This is a change from rev 1, which marked them
  unverified under audit §2 limit 1. That limit said the source was not *in the repository*, which
  remains true — it is not the same as unavailable, and rev 2 stopped treating it as if it were.
  **The audit's four `server-side unverified in-repo` markers (items 19, 21, 22, 23) are now
  liftable**; doing so is a separate change to a merged document and is not made here.
- No claim of complete switch-out semantics: volatiles beyond the three transients in §3.3 are
  untracked.
- No claim that ability *suppression* is modelled — Gastro Acid and Neutralizing Gas need a third
  state, not a third value (§4.5), so §5.2's predicates cannot see them.
- No claim of complete turn-order correctness: speed ties, Prankster and item order effects are out
  of scope (§5.2).
- No authorisation to implement. The plan is separate and needs separate approval.

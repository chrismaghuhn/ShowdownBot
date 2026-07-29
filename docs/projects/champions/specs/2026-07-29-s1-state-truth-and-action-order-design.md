# S1 — Persistent combatant state, ability truth, and dynamic action order

**Issue:** #129 · **Base:** `main @ 4e9ebcf2` · **Date:** 2026-07-29
**Type:** design / spec. **No production code is changed by this document and none is authorised by
it.** The implementation plan is a separate artifact requiring separate approval.

**Feeds from:** [`2026-07-29-static-correctness-audit.md`](../audits/2026-07-29-static-correctness-audit.md)
(items 3, 8, 15, 20, 23) and
[`2026-07-29-128-correctness-slice-prioritisation.md`](2026-07-29-128-correctness-slice-prioritisation.md)
(slice **S1**, relevance band 1–2, feasibility 4 of 5).

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
thing. The contract introduces a middle level.

```
side  →  combatants   : {combatant_key: PokemonState}    # every combatant seen this battle
      →  active_slots : {slot: combatant_key | None}     # "a", "b" → who is standing there now
```

- A **combatant** is one Pokémon for the whole battle. It is created once, on first observation, and
  is never replaced.
- An **active slot** is a position on the field. It holds a *reference*, not a Pokémon.
- A **switch** rebinds `active_slots[slot]`. It **must not** construct a `PokemonState` for a
  combatant that already exists.

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
  recorded `base_species_id` differs from the incoming details. That is the collision signature.

A stronger key (e.g. ident + first-seen details) is deliberately **not** adopted in this slice: it
would diverge from `target_ident` and break the learning-side lookup for a case with no current
exposure. The counter exists so the decision can be revisited on evidence.

### 3.3 Re-entry semantics — what survives, what resets

The rule is: **what the Pokémon *is* survives; what its *current turn on the field* is resets.**

| Field | On re-entry | Why |
|---|---|---|
| revealed `moves`, `move_names` | **survive** | knowledge, not board state |
| `item`, `item_known`, `item_lost` | **survive** | a consumed item stays consumed — this is the leak that lets a spent item become a live preset hypothesis again |
| `ability` + its provenance (§4) | **survive** | knowledge |
| `types`, `base_species_id`, `tera_type`, `terastallized` | **survive** | identity |
| `level`, `gender`, `nickname` | **survive** | identity |
| `hp`, `max_hp`, `status`, `fainted` | **overwritten from the switch event** | the event is authoritative |
| `boosts` | **reset to `{}`** | Showdown clears stat stages on switch-out |
| `consecutive_protect` | **reset to `0`** | the Protect chain breaks on switch-out |
| `moved_since_switch` | **reset to `False`** | that is the field's meaning (§5) |
| `species` | **overwritten from the switch event's details** | a form may have reverted while off-field |

**Volatiles are out of scope.** This slice does not model volatile conditions beyond the two counters
above; anything else that Showdown clears on switch-out is not tracked today and is not added here.
The contract must not be read as claiming full switch-out semantics.

### 3.4 Faint, and why it is not the same as switch-out

A fainted combatant keeps its entry in `combatants` with `fainted=True`. Its slot binding is set to
`None` when the replacement switches in. Knowledge about a fainted Pokémon stays available — the
opponent's dead Incineroar's revealed Fake Out is still evidence about their team.

### 3.5 Required diagnostics

Three counters, exposed for tests and for the decision profile, all **non-behavioural**:

- `combatant_created` — a `switch` produced a new key;
- `combatant_rebound` — a `switch` bound an existing key (the case that is broken today);
- `combatant_key_conflict` — a `switch` bound an existing key whose `base_species_id` disagrees with
  the incoming details (§3.2's collision signature).

---

## 4. Contract B — ability truth, public and private

### 4.1 Three sources, three confidence levels

| Source | Reaches state via | Confidence | Applies to |
|---|---|---|---|
| **Private request** — `active[].ability`, `side.pokemon[].baseAbility` | `merge_request` | **certain** | our side only |
| **Public reveal** — `\|-ability\|p2a: X\|Intimidate` | `apply_event` | **certain** | either side |
| **Dex default** — `species_meta.ability_slot0` | `detailschange`, `_apply_mega_reconcile` | **assumed** | either side |

Today only the third exists, and it is indistinguishable from the first two because the field is a
bare `str | None` (§1.1).

### 4.2 The field contract

`PokemonState.ability` gains a companion:

```
ability          : str | None
ability_source   : "unknown" | "assumed" | "revealed" | "request"
```

`ability_source == "unknown"` iff `ability is None`.

**Precedence, strictly monotonic:** `request` ≥ `revealed` > `assumed` > `unknown`. A lower-confidence
source **never** overwrites a higher one. Concretely:

- a `detailschange` on a mon whose ability is `request`- or `revealed`-sourced updates `species` and
  `types` but **leaves `ability` alone** — this is a behaviour change from today, and it is the
  point;
- a `-ability` reveal overwrites an `assumed` value;
- `request` and `revealed` cannot conflict in practice (one is ours, one is observed) and are treated
  as equal rank; if they ever disagree the request wins, because it is our own side's ground truth.

**Form changes are the one legitimate override.** A Mega Evolution genuinely changes the ability
(Aerodactyl's Unnerve → Tough Claws). So `_apply_mega_reconcile` may set an ability at
`assumed` rank **and** override a higher rank — but only because the *form* changed, and only from
the new form's dex entry. This is a deliberate, single, named exception; it is the sole place a
higher rank is overwritten, and §7 requires a test that pins it.

### 4.3 Own-side plumbing (item 20)

`PokemonSlot` gains `ability` and `base_ability` (aliases `ability`, `baseAbility`), both
`str | None`. `ActiveSlot` is untouched — the per-mon fields on `side.pokemon` cover the whole team,
including the bench, which is what belief needs.

`merge_request` sets `mon.ability` with `ability_source="request"`, preferring current `ability` over
`baseAbility` when both are present, because a suppressed or swapped ability is what is actually in
play.

**Packed-team ability is deliberately not used.** `team/pack.py` skips packed field 3 and
`apply_own_team_knowledge` restores item truth only. Adding a packed-team fallback would introduce a
fourth source whose staleness rules are their own design question; the request is authoritative for
our own side and is present every turn.

### 4.4 Public reveal (item 3)

`engine/log_parser.py` gains a `-ability` handler producing `type="ability"` with the ability name in
`value`. `apply_event` applies it at `revealed` rank.

**Deliberately not in this slice:** `-endability`, `-ability` with `[from]` (Trace, Skill Swap,
Role Play), and ability *suppression* (Gastro Acid, Neutralizing Gas). Those change what the ability
*does*, not what it *is*, and each needs its own semantics. Parsing them incorrectly would be worse
than not parsing them. The parser must therefore **ignore** `-ability` lines carrying a `[from]`
tag rather than record them as a plain reveal — recording a Traced ability as the Tracer's own is a
false certainty, and a `revealed`-rank false value is unrecoverable under §4.2's monotonicity.

---

## 5. Contract C — Fake Out freshness and dynamic order

### 5.1 Fake Out freshness (item 23)

**The defect is the predicate, not the filter.** Dropping a dead Fake Out from enumeration
(`battle/legal_actions.py:118-124`) is a deliberate guard against observed Fake Out spam and stays.
What is wrong is `moved_since_switch`, which is set only by a parsed `|move|`
(`engine/state.py:193-198`) while the parser has no `cant` event — so a flinched, paralysed or
sleeping turn leaves the flag `False` and Fake Out looks fresh next turn.

**Contract.** The field is renamed to what it actually has to mean:

```
had_move_opportunity : bool   # a move action was consumed since this combatant switched in
```

It becomes `True` when the combatant **consumes a move opportunity**, whether or not the move
resolved. Two protocol triggers:

- `|move|` — as today;
- `|cant|` — new parser event, `type="cant"`, carrying the reason in `value`.

It resets to `False` on switch-in (§3.3).

This mirrors the pinned server's own contract: `runMove()` increments `activeMoveActions` at the top,
before any `BeforeMove` prevention. **That statement is from the audit's fourth pass and is
server-side unverified in this repository** (audit §2 limit 1) — the bot-side defect is verified
independently and does not depend on it.

`|cant|` reasons that are *not* a consumed opportunity — being fully paralysed is, but a disabled
move rejected at choice time is not — are a known edge. The contract is: **every `|cant|` for this
combatant sets the flag.** That is fail-closed in the safe direction: it can only make Fake Out look
*stale* when it might be fresh, costing a legal option, never offering a guaranteed-wasted turn.

### 5.2 Dynamic action order (item 15)

Two independent gaps, and the design keeps them separate because they have different shapes.

**5.2.1 Ability speed modifiers.** `speed_modifiers_from_state()` gains the actor's ability and
returns `booster_speed` and a new multiplier set derived from it, rather than the hard-coded
`False`. The function's own docstring already anticipates this: *"not knowable from state alone;
assume off unless a future signal sets it."* §4 is that signal.

**Activation predicates are part of the contract, not a lookup.** A name-only table would be wrong
for every panel-relevant case:

| Ability | Panel exposure | Predicate |
|---|---|---|
| Sand Rush | `trick_room` Excadrill | `field.weather` is sand. (No immunity condition — sand immunity governs sandstorm *damage*, not this ability. An earlier draft of this section invented one.) |
| Unburden | `goodstuff`, `tailwind_offense` Sneasler | the holder **has lost** an item — precisely `item_lost` (§3.3), which is exactly what the switch reset destroys today |
| Gale Wings | `tailwind_offense` Talonflame | priority, not speed — see 5.2.2; predicate is full HP |
| Protosynthesis / Quark Drive | not on the current panel | needs a booster-active signal that does not exist; **out of scope**, `booster_speed` stays `False` for them |

Unburden is the clearest argument for doing §3 before §5: its predicate reads a field that today is
erased on every switch.

**5.2.3 Where the predicates live — a new config surface, verified absent today.**
`config/species/speciesdata.json` carries only `abilities: {"0", "1", "H"}` per species — *names*.
There is **no** ability-effect data anywhere in `config/` (no `abilitydata.json`, no
`ability_effect_classes.yaml`; `moves/` and `items/` each have an effect-class overlay, abilities
have none). So the predicates above cannot be data-driven from what exists, and this slice must
introduce the surface.

Contract for it:

- A **small curated table**, hand-written and reviewed, covering exactly the abilities named in
  5.2.1–5.2.2 and no others. Not a generated dump: the value here is the predicates, and those are
  not in `@pkmn/dex` in a form this code can consume.
- An **unknown ability is a no-op**, never a guess. A name absent from the table contributes no
  speed or priority modifier, which is today's behaviour and therefore the safe default.
- If the table is a file whose bytes are hashed by `format_config_hash` / `file_content_hash`, it
  needs a `text eol=lf` rule in `.gitattributes` **in the same commit** (§6.4). If it is a Python
  constant it does not — the plan must state which and why.
- The curated overlay pattern already exists twice (`config/moves/effect_classes.yaml`,
  `config/items/item_effect_classes.yaml`); the plan should follow whichever of those two shapes it
  matches, rather than inventing a third.

**5.2.2 Ability priority.** `move_priority(meta, field)` gains an optional actor:
`move_priority(meta, field, actor=None)`. With `actor=None` it returns exactly today's value —
this keeps every existing call site and every golden byte-identical. `sort_actions` passes the actor
from the `PlannedAction`.

Scope is **one ability: Gale Wings** (Talonflame, `tailwind_offense`), predicate: full HP **and** the
move is Flying-type. No other priority ability has current-panel exposure, and a general
priority-modifier framework is not justified by one case.

**Explicitly out of scope for 5.2:** speed *ties*, Trick Room interactions beyond the existing sort
flip, item-based order effects other than the Choice Scarf already modelled, and Prankster. The
audit's item 15 mentions turn order broadly; this slice fixes the ability half of it on the current
panel and says so.

---

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
`SUPPORTED_TRACE_SCHEMA_VERSIONS` gating readers (`:25-26, 563`). Adding `ability_source` and
renaming `moved_since_switch` changes that payload.

**Contract:**

1. New fields **do not** enter the v3 payload. `decision-trace-v4` is minted; v3 stays readable and
   frozen evidence stays valid. `SUPPORTED_TRACE_SCHEMA_VERSIONS` gains v4.
2. While `SHOWDOWN_STATE_TRUTH_V1` is off, writes stay **v3 and byte-identical**. The version bump
   is tied to the switch, not to the merge.
3. `had_move_opportunity` is serialised under its new name in v4 only; v3 continues to emit
   `moved_since_switch`.
4. **Frozen evidence is never rewritten.** No existing artifact under `data/eval/` is touched. The
   Gate B and Attempt-6 freezes remain valid because their rows are v3 and v3 readers survive.

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
- **An unknown ability** (no request field, no reveal, no form change) leaves `ability=None` /
  `ability_source="unknown"`, and every consumer behaves exactly as today. The slice never guesses to
  fill a gap.
- **A `combatant_key_conflict`** (§3.5) must not crash a live turn. It increments the counter, logs,
  and takes the incoming details as authoritative for `species`/`types` while keeping the existing
  combatant. Fail-open here is correct: a wrong merge costs accuracy, a raised exception costs the
  battle, and INV-1's safety floor exists to keep turns alive.

---

## 7. Acceptance tests (TDD order)

Each test is written and seen to fail before its implementation. Grouped in dependency order; a group
may not start before the one above it is green.

### Group 1 — identity and re-entry (§3)

1. `test_switch_out_and_back_preserves_revealed_moves` — replay switch-in, `|move|`, switch-out,
   switch-in; the returning combatant still carries the revealed move id.
2. `test_switch_out_and_back_preserves_item_lost` — an `|-enditem|` before switch-out leaves
   `item_lost=True` on re-entry. **This is the leak with the widest blast radius**: it is what lets a
   consumed item become an eligible preset hypothesis again via `hypothesis_from_state`.
3. `test_switch_resets_boosts_and_protect_chain` — `boosts == {}` and `consecutive_protect == 0`.
4. `test_switch_takes_hp_and_status_from_the_event`.
5. `test_fainted_combatant_knowledge_survives`.
6. `test_active_slots_rebind_without_constructing_a_new_combatant` — asserts object identity, not
   just field equality; this is the test that actually pins §3.1.
7. `test_combatant_key_conflict_counts_and_does_not_raise` — duplicate nicknames (§3.2).
8. `test_belief_tracker_does_not_drop_hypotheses_on_re_entry` — the `_resync_side` deletion path.

### Group 2 — ability truth (§4)

9. `test_request_ability_and_base_ability_parse` — `PokemonSlot` retains both.
10. `test_merge_request_sets_ability_at_request_rank`.
11. `test_dash_ability_line_sets_revealed_rank`.
12. `test_ability_from_tag_is_ignored` — `|-ability|p2a: X|Intimidate|[from] ability: Trace` must
    **not** produce a `revealed` value (§4.4).
13. `test_detailschange_does_not_overwrite_revealed_ability` — the monotonicity rule, and a
    behaviour change from today.
14. `test_mega_reconcile_may_override_ability` — the single named exception (§4.2).
15. `test_unknown_ability_reaches_calc_as_none` — no guessing.

### Group 3 — freshness (§5.1)

16. `test_cant_event_parses`.
17. `test_flinch_cant_consumes_the_move_opportunity` — the audit's counterexample: switch-in,
    `|cant|` flinch, next turn Fake Out is **not** offered and the resolver does not treat it as
    fresh.
18. `test_switch_in_resets_had_move_opportunity`.

### Group 4 — order (§5.2), only after Groups 1–2 are green

19. `test_sand_rush_doubles_speed_only_in_sand`.
20. `test_unburden_requires_item_lost` — **depends on Group 1 test 2**; it cannot pass while the
    switch reset erases `item_lost`, which is the dependency argument made concrete.
21. `test_gale_wings_priority_requires_full_hp_and_flying_move`.
22. `test_move_priority_without_actor_is_unchanged` — pins the default-arg compatibility.
23. `test_protosynthesis_does_not_set_booster_speed` — the explicit out-of-scope.

### Group 5 — gates

24. `test_state_truth_off_is_byte_identical` — golden decision-trace comparison against `main`,
    switch off. **This is the merge gate.**
25. `test_trace_v3_payload_unchanged_when_off` and `test_trace_v4_carries_new_fields_when_on` (§6.3).
26. `test_env_var_is_behavior_affecting` — `SHOWDOWN_STATE_TRUTH_V1` classified in
    `eval/config_env.py`, so it lands in `config_hash`. The drift test enforces classification.
27. Full offline suite — `python -m pytest` — run and reported, not inferred from CI.

### Existing tests — checked, not assumed

An earlier draft of this section asserted that `showdown_bot/tests/test_battle_state.py` contains
assertions written against the reset semantics that would have to be rewritten. **I checked, and it
does not.** That file's switch lines are fixture setup; no test asserts that knowledge is lost across
a switch, and `test_enditem_marks_item_lost` / `test_item_event_clears_item_lost` both assert within
a single switch-in and are unaffected.

So the current expectation is that **no existing test asserts this defect**. Two standing rules
survive that finding, because it is an expectation and not a guarantee:

- **No test may be deleted to make an S1 test pass.** If one does turn out to assert the defect, it
  is rewritten with the reason recorded in the commit message.
- The 121-test targeted set from the audit and the full offline suite are both run; the audit
  recorded that those 121 pass on *unrepaired* code, so any of them turning red under S1 is a signal
  to read, not to silence.

(The one test in this repository known to freeze a defect — `test_legal_actions.py:118-126`, the
Choice-item rule — belongs to **S2**, not to this slice.)

---

## 8. Open questions for review

1. **`combatant_key` granularity** (§3.2) — adopt the existing ident-suffix convention with a
   collision counter, or a stronger key that diverges from `target_ident`? The design takes the
   former; the counter exists so it can be revisited on evidence.
2. **Default-on gate** (§6.2) — is a decision record the right home for the flip criterion, given
   that a strength gate cannot answer a correctness question with the evidence now available?
3. **`|cant|` over-triggering** (§5.1) — the contract sets the flag for every `|cant|`. Accepted as
   fail-closed in the safe direction, but it is a real over-approximation.
4. **Scope of 5.2.2** — one priority ability (Gale Wings) rather than a framework. Correct for the
   current panel; it will need reopening when the panel changes.

## 9. Non-claims

- No claim that S1 improves strength. None of items 3, 8, 15, 20, 23 has a measured outcome effect,
  and §6.2 states why this slice cannot supply one.
- No claim about the pinned Showdown server beyond audit §2 limit 1 — §5.1's `runMove()` reference is
  server-side unverified here.
- No claim of complete switch-out semantics: volatiles beyond two counters are untracked (§3.3).
- No claim of complete turn-order correctness: speed ties, Prankster and item order effects are out
  of scope (§5.2).
- No authorisation to implement. The plan is separate and needs separate approval.

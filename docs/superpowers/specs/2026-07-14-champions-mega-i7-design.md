# I7 — Champions Mega Evolution Design (MegaProjection / I7a / I7b)

**Status:** APPROVED — I7a implemented and merged; I7b implementation planning allowed, I7b not implemented
**Date:** 2026-07-16 (Rev. 10 correction accepted)
**Design input:** protocol audit commit `fc4f251` on `main`
**Artifact:** `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md` (commit hash recorded at merge)

**Verdict gates (binding):**
- **I7a alone:** own-side Mega + projection + trace-v3 + full consumer wiring (`max_damage` mandatory) — **no Strength claim**; **not** “full panel mega support” while Scovillain fail-closed
- **I7b required:** Champions **Strength NO-GO — opponent Mega response modeling missing** until I7b
- **Strength overall:** blocked until **I7b + latency profile**

**Rev. 10 correction log (binding — Codex/maintainer sign-off 2026-07-16):**
1. **T26 test 1 weather-winner rule corrected.** §2.5's own general branch rule (line 202 below) already states the winner order-based ("last weather-setting ability wins within that branch"), and real pinned-Showdown mechanics (`sim/battle-actions.ts::runMegaEvo`, `sim/pokemon.ts::setAbility`, `data/abilities.ts`; checkout `f8ac140`) confirm weather-setting abilities unconditionally overwrite `field.weather` with no "only if not already set" guard — so the LATER-processed (slower pre-mega) activator's weather is what remains active. T26 test 1's former prose ("faster activator's weather wins") contradicted both of these; the binding expectation is "later (= slower, since faster activates first per line 199) activator's weather wins". This does not change test 2 (TR-reversed: the slower-under-TR activator now activates first, so the fast-under-TR one activates last and its weather wins) or test 3 (true tie: unaffected, already order/permutation-based).

**Rev. 9 correction log (binding):**
1. Mega activation order — Trick-Room-aware via `mega_activation_order_key`; T26 extended (no TR / TR / tie).
2. Foe post-mega move speed — `predict_responses` replans mega-evolved foe `PlannedAction.speed` per branch; **T51**.
3. Candidate key v2 — exact slot schema, no unknown fields, per-slot overlay mutual exclusion; **T52–T54**.
4. Slice test assignment — I7a PASS excludes I7b-only tests T19/T26/T29/T32/T51.

**Rev. 8 correction log (binding):**
1. Reducer output type — `ReducedLogEvent = LogEvent | MegaReconcileEvent`; no synthetic `LogEvent(type="mega_reconcile")`; `apply_event` accepts both.
2. Reducer finalization — `flush_pending()` after last input in `reduce_log_events` and at end of `BeliefTracker.feed`; runner/gauntlet use `from_log` only.
3. Dual-mega tie — `compose_mega_projection_branches` → `list[WeightedMegaProjection]`; weighted scoring in ranking/K-world/I7b.
4. One expansion — trace reuses the post-filter `ScoredMegaVariant` list from `_choose_best` / `max_damage_choice`; no separate trace expansion.

**Rev. 7 correction log (binding):**
1. Standalone spec — full §1–7 restored; no “prior revs authoritative” deferral.
2. Parser-aligned reconcile — `parse_log_line` emits `detailschange`/`-mega`; `MegaReconcileReducer` pairs compatible lines atomically; same reducer for `from_log` and `BeliefTracker`.
3. Trace-v3 — `_validate_v3_row` validates **every** `candidates[].candidate_key` (v2 + `mega_evolve`); v1 keys rejected in v3 rows.
4. `max_candidates` — fail-closed after eligibility discovery `R`, before expansion/truncation (runtime parameter; no startup check).

---

## 0. Problem statement and verified baseline

Mega Evolution in Champions M-A is **on** and **not Tera-isomorphic**. A Mega click changes species/form, base stats, types, ability, and field weather **before** the chosen move resolves.

**Verified today (code @ `main`):**

| Fact | Location |
|------|----------|
| `DamageModel` binds `state`, `field`, `hyps` at construction | `evaluate.py:201–233` |
| Spread lookup uses `mon.species` display name | `evaluate.py:229`; `spreads.py:40–48` |
| `joint_action_key` version 1, no `mega_evolve` | `candidate_identity.py:20–36` |
| Trace writes v2 only | `decision_capture.py:391` |
| `parse_log_line` returns `None` for `detailschange`/`-mega` | `log_parser.py:233` |
| `BattleState.apply_event` has no mega handlers | `state.py:96–190` |
| `BeliefTracker.update` calls `state.apply_event` per event | `tracker.py:57–67` |
| `SpeciesDex` only `types()` | `opponent.py:33–67` |
| `PokemonState` has no `stats` field | `state.py:45–65` |
| `_plan_my_actions` reads request `stats["spe"]` | `decision.py:199–204` |
| `_slot_actions` strips Tera only | `actions.py:82–86` |
| `predict_responses` truncates before weighting | `opponent.py:268` vs `270–287` |
| Genuine tie 0.5/0.5 scoring | `evaluate.py:366–382` |
| `SpeedOracle.effective_speed` has **no** Trick Room inversion | `speed.py` — inversion in `resolve.sort_actions` |
| `predict_responses` plans foe speed before projection | `opponent.py` (pre-mega base form today) |
| `@pkmn/dex` pin **0.10.11** | `tools/gen/package.json`; `itemdata.json` `source_version` |

**Architecture:** one format-generic **MegaProjection** module; **I7a** (own + trace-v3) and **I7b** (foe response). No Champions yaml table in decision core.

---

## 1. Metadata: generators, loaders, DTOs

### 1.1 Build-time pin

**`@pkmn/dex` 0.10.11** (matches `showdown_bot/tools/gen/package.json`).

### 1.2 Artifacts

| Artifact | Path | Generator |
|----------|------|-----------|
| Item → form map | `showdown_bot/config/items/itemdata.json` → `megaStone` | `tools/gen/gen_movedata.mjs` `itemRecord()` |
| Form metadata | `showdown_bot/config/species/speciesdata.json` | same npm script |

**Item record extension:**

```javascript
megaStone: it.megaStone ?? null,
```

**Species record shape:**

```json
{
  "aerodactylmega": {
    "id": "aerodactylmega",
    "name": "Aerodactyl-Mega",
    "baseSpecies": "Aerodactyl",
    "types": ["Rock", "Flying"],
    "baseStats": {"hp": 80, "atk": 135, "def": 85, "spa": 70, "spd": 95, "spe": 150},
    "abilities": {"0": "Tough Claws"},
    "requiredItem": "Aerodactylite"
  }
}
```

Header: `source_version`, `generation`, `data_hash` (same pattern as `movedata.json`).

### 1.3 Runtime DTOs

```python
@dataclass(frozen=True)
class SpeciesFormMeta:
    form_species_id: str
    form_species_name: str
    base_species_id: str
    base_species_name: str
    types: tuple[str, ...]
    base_stats: dict[str, int]   # includes spe
    ability_slot0: str
    required_item: str | None

@dataclass(frozen=True)
class MegaForm:
    base_species_id: str
    form_species_id: str
    form_species_name: str
    stone_item_id: str
```

**Loader:** `engine/species_meta.py`

```python
def get_species_form_meta(name_or_id: str) -> SpeciesFormMeta | None
def species_meta_table() -> dict[str, SpeciesFormMeta]
```

Fail-closed if file `data_hash` stale vs generator `--check`.

### 1.4 `mega_form_for(base_species_name, item_id, *, item_table, species_meta) -> MegaForm | None`

1. `to_id` normalize ids.
2. `item_table[item_id].megaStone[base_species_name]` → form display name.
3. Load `SpeciesFormMeta`; build `MegaForm`.
4. Miss → `None`. Mega Rayquaza out of v0 scope.

Request `canMegaEvo: true` (boolean) confirms eligibility only (GT `showdown_ground_truth.json`); form id **only** from `mega_form_for`.

---

## 2. MegaProjection

### 2.1 Module

`showdown_bot/src/showdown_bot/engine/mega_projection.py` — pure; no decision-core format branches.

### 2.2 `copy_battle_state(state) -> BattleState`

Deep copy: `sides`, mon objects, `field`, `side_mega_spent`, `turn`. No nested aliasing.

### 2.3 `MegaProjectionResult`

```python
@dataclass(frozen=True)
class MegaProjectionResult:
    mega_form: MegaForm
    projected_state: BattleState
    mega_slot: str              # "a" | "b"
    own_mega_slot: int | None   # 0 | 1 | None (trace/context)
    effective_speed: int
```

### 2.4 `project_mega(state, side, slot, mega_form, *, species_meta, speed_oracle, spread_lookup, calc_profile) -> MegaProjectionResult`

1. `projected_state = copy_battle_state(state)`.
2. Load `SpeciesFormMeta`; copy mon at `(side, slot)`.
3. Update mon: `species` (mega form name), `types`, `ability`; **preserve** `base_species_id`, **preserve** `item` (stone stays held).
4. `projected_state.side_mega_spent[side] = True` (branch-local).
5. Apply immediate field effects per §11 ability table (Drought/Sand Stream/Snow Warning only where listed).
6. Speed via `speed_for_species()` §5.
7. Return result. **Never** mutates input `state`.

### 2.5 `compose_mega_projection_branches` (dual activation)

A speed tie cannot be represented by a single `BattleState`. Dual (or multi) activation uses explicit weighted branches.

```python
@dataclass(frozen=True)
class WeightedMegaProjection:
    projected_state: BattleState
    weight: float
    activation_order: tuple[tuple[str, str], ...]  # (side, slot) in apply order

def compose_mega_projection_branches(
    state: BattleState,
    activations: list[tuple[str, str, MegaForm]],  # (side, slot, form) — at most one per side
    *,
    speed_oracle, spread_resolver, species_meta, calc_profile,
) -> list[WeightedMegaProjection]:
```

**Showdown ordering (pinned `f8ac140`):**
- Mega queue actions use **order 104** (`battle-queue.ts:184–186`), same priority tier.
- `Battle.comparePriority` breaks ties by **pre-mega speed** (`battle.ts:404–410`).

**Branch rules:**
- Compute each activation’s **pre-mega** `effective_speed` (from `SpeedOracle` — **no** Trick Room inversion in this value).
- Sort activations by `mega_activation_order_key(pre_mega_speed, field)` **descending** (same speed direction as `resolve.sort_actions` for mega queue order 104):
  - **No Trick Room:** higher pre-mega speed activates first.
  - **Trick Room active:** lower pre-mega speed activates first.
- **Unequal pre-mega speeds:** one branch, `weight=1.0`, single activation order.
- **Equal pre-mega speed (tie):** two branches, each `weight=0.5`, one per permutation; apply `project_mega` steps sequentially on each branch’s `projected_state` copy; last weather-setting ability wins **within that branch**.
- **No** merging tie permutations into one state; **no** Showdown RNG seed.

**Mandatory test T26** (I7b): Froslass-Mega (Snow Warning) vs Tyranitar-Mega (Sand Stream):
1. **Unequal pre-mega speed, no Trick Room** — the LATER-activating side's weather wins, i.e. the SLOWER pre-mega activator (binding Rev. 10 correction; matching this section's own "last weather-setting ability wins within that branch" rule and real Showdown mechanics); weighted score = branch score.
2. **Same speeds, Trick Room on** — activation order **reversed** vs (1); weather order reversed accordingly (i.e. under TR the slower-under-normal-rules side now activates first, so the OTHER side activates last and its weather wins).
3. **Equal pre-mega speed tie** — two branches at 0.5; assert per-branch weather **and** weighted final candidate value `0.5×score(A)+0.5×score(B)`.

Single-slot own mega (I7a) uses `project_mega` directly (implicit branch weight `1.0`).

### 2.6 Fail-closed derivation

| Condition | Behavior |
|-----------|----------|
| `format_config.mega is False` | skip |
| `can_mega_evo` but `mega_form_for` → `None` | no `mega_evolve=True` candidates |
| `mega_evolve=True` but projection fails | exclude candidate |
| `side_mega_spent[side]` | slot ineligible |
| Unsupported material ability (§11) | exclude or Strength-block |

---

## 3. Protocol / action / encoder interfaces

### 3.1 Request model

```python
class ActiveSlot(BaseModel):
    can_mega_evo: bool = Field(default=False, alias="canMegaEvo")
```

### 3.2 SlotAction / JointAction

```python
@dataclass(frozen=True)
class SlotAction:
    ...
    mega_evolve: bool = False

class JointAction:
    def with_mega(self, slot_index: int) -> JointAction: ...
    def with_tera(self, slot_index: int) -> JointAction: ...  # unchanged
```

### 3.3 Encoder (`protocol/encoder.py`)

```python
if action.mega_evolve:
    parts.append("mega")
```

After optional target; never combined with `terastallize` on same slot.

### 3.4 Legal enumeration (`legal_actions.py`)

When `req.active[i].can_mega_evo` and not side spent: for each legal move, emit clone with `mega_evolve=True`.

`enumerate_slot_pairs`: reject double-mega; reject `terastallize and mega_evolve` on same slot.

### 3.5 Policy strip (`actions.py`)

`_slot_actions` filters **both** `terastallize` and `mega_evolve` (mirror Tera). `enumerate_my_actions` yields **base joints only**.

### 3.6 Variant expansion — single owner, single evaluated list

**Layer responsibilities:**

| Layer | Mega in output? |
|-------|-----------------|
| `legal_actions._slot_move_actions` | **Yes** — full protocol legality |
| `actions._slot_actions` | **No** — filter `terastallize` **and** `mega_evolve` |
| `enumerate_my_actions` | **No mega in joints** — base joints only |
| **`expand_mega_variants`** | **Yes — sole expansion site** |

**Module:** `battle/mega_variants.py`

```python
@dataclass(frozen=True)
class ScoredMegaVariant:
    joint: JointAction
    own_mega_slot: int | None

def expand_mega_variants(
    base_joints: list[JointAction],
    req: BattleRequest,
    state: BattleState,
    our_side: str,
) -> list[ScoredMegaVariant]:

def filter_projectable_variants(
    variants: list[ScoredMegaVariant],
    req: BattleRequest,
    state: BattleState,
    our_side: str,
    *,
    species_meta, calc_profile,
) -> list[ScoredMegaVariant]:
    """Drop variants where project_mega fails or ability gate is fail-closed."""
```

Per `base_joint`:
- `(joint, None)`
- `(joint.with_mega(0), 0)` if slot 0 legal
- `(joint.with_mega(1), 1)` if slot 1 legal

**Expansion consumers (each expands exactly once per decision):**
- `decision._choose_best`
- `baselines.max_damage_choice`

**Pipeline (binding, both consumers):**
1. `variants = expand_mega_variants(base_joints, ...)`
2. `evaluated_variants = filter_projectable_variants(variants, ...)`
3. Build `MegaEvaluationContext`(s) and score **only** `evaluated_variants`
4. Trace assembly receives **`evaluated_variants` unchanged** — **no** second `expand_mega_variants` call

A request-legal mega variant that fails projection or an ability gate appears in **neither** ranking nor trace.

**Tests T27:** exact variant count for fixture; **no duplicate** `joint_action_key` values; `legal_actions` mega count ≠ scored variant count (layers differ by design).

**Test T50:** Scovillainite (Spicy Spray fail-closed) — variant in `expand_mega_variants` output is absent from `evaluated_variants`, ranking, and trace; every evaluated variant appears exactly once in trace.

### 3.7 `BattleState.side_mega_spent`

```python
side_mega_spent: dict[str, bool] = field(default_factory=lambda: {"p1": False, "p2": False})
```

### 3.8 `PlannedAction.is_mega: bool`

Parallel to `is_tera`; set in `_plan_my_actions` from slot action.

---

## 4. Spread identity (`base_species_id`)

### 4.1 Field and lookup table

```python
base_species_id: str = ""
```

**Backfill:** on `PokemonState` construction, if empty → `base_species_id = to_id(species)`. Legacy callers unchanged.

| Lookup | Key | Calc species string |
|--------|-----|---------------------|
| `our_spreads` | `base_species_id` | `species` = mega form name |
| `opp_sets` / SpreadBook | `to_id(base_species_id)` | same |
| Speed nature/EV | preset from above | mega form for stat formula |

Projection sets `species` to mega form display name, updates types/ability, **keeps** `base_species_id`, **keeps** `item` (stone held).

### 4.2 Canonical accessor (`engine/spread_lookup.py` or `team/spreads.py`)

```python
def spread_lookup_key(mon: PokemonState) -> str:
    return mon.base_species_id or to_id(mon.species)

def lookup_our_spreads(our_spreads, mon) -> SpeciesSpreads | None:
    key = spread_lookup_key(mon)
    if key in our_spreads: return our_spreads[key]
    if mon.species in our_spreads: return our_spreads[mon.species]  # legacy alias
    return None

def lookup_opp_set(opp_sets, mon): ...
```

**All** consumers (`DamageModel`, `speed_for_species`, `apply_own_team_knowledge`) use accessor only.

### 4.3 `our_spreads_from_packed` migration

Write both `out[to_id(species)]` and `out[species]` during transition.

### 4.4 Projection / reconcile

- Projection copies preserve `base_species_id`.
- Mega reconcile sets from `-mega` arg1 base species (`to_id`), never mega form id.

---

## 5. Speed interface

### 5.1 Public API (`engine/speed.py`)

```python
def speed_for_species(
    self,
    *,
    species_name: str,        # mega form for stat formula
    base_species_id: str,
    side: str,
    mon: PokemonState,
    field: FieldState,
    our_spreads: dict | None,
    opp_sets: dict | None,
    book: SpreadBook | None,
    is_ours: bool,
) -> int:
```

- **Own:** nature/EV from `lookup_our_spreads(our_spreads, mon)` using `base_species_id`. Missing spread when mega legal → **fail-closed** (exclude mega variants; trace diagnostic `own_spread_missing`).
- **Foe:** `lookup_opp_set` / SpreadBook via `base_species_id`.
- **No** external use of private `_base_speed`.
- Non-mega path may continue using request `stats["spe"]` in `_plan_my_actions`.

### 5.2 Pre-mega vs post-mega speed (binding)

| Phase | Speed source | Trick Room |
|-------|--------------|------------|
| **Mega activation order** | Pre-mega `effective_speed` + `mega_activation_order_key` | Inversion via sort key only |
| **Move order after mega** | Post-mega `speed_for_species` on projected form | Normal `resolve.sort_actions` path |

```python
def mega_activation_order_key(pre_mega_speed: int, field: FieldState) -> int:
    """Same speed direction as resolve.sort_actions for mega queue order 104."""
    return pre_mega_speed if not field.trick_room else -pre_mega_speed
```

Sort activations by this key **descending**. `compose_mega_projection_branches` uses this exclusively for activation ordering — not raw `effective_speed` alone.

---

## 6. `MegaEvaluationContext`

### 6.1 DTO

```python
@dataclass
class MegaEvaluationContext:
    context_id: str
    projected_state: BattleState
    own_mega_slot: int | None
    foe_mega_slot: int | None
    branch_weight: float              # 1.0 default; 0.5 per tie branch
    activation_order: tuple[tuple[str, str], ...] | None
    field: FieldState
    plans: dict[JointAction, list[PlannedAction]]
    damage_model: DamageModel
```

### 6.2 Construction

One context per `WeightedMegaProjection` branch (weight copied to `branch_weight`). Single-slot `project_mega` paths use `branch_weight=1.0`.

`DamageModel(projected_state, …, field=projected_state.field)` with spread accessor on `base_species_id`. Shared `DamageOracle`: enqueue all contexts' plan groups → **one** `flush()`.

### 6.3 Scoring loop (I7a)

1. `base_joints = enumerate_my_actions(req)`
2. `evaluated_variants = filter_projectable_variants(expand_mega_variants(...), ...)`
3. Distinct contexts per own mega slot `{None, 0, 1}` (each `branch_weight=1.0` in I7a-only paths).
4. Per variant: build context, `_plan_my_actions` with projected speed/species, `evaluate_line` with **that** `damage_model.damage_fn` and `projected_state`.
5. Variant aggregate score: if multiple contexts apply (I7b dual-mega branches), `sum(ctx.branch_weight × score_ctx(variant))`.

### 6.4 K-world

Context key **`(world_id, own_mega_slot, foe_mega_slot, branch_index)`** — not world alone. Tie branches get distinct `branch_index` values.

### 6.5 Depth-2

Turn-1 leaf receives candidate's `MegaEvaluationContext`, not base-state model.

### 6.6 Damage-path test T28

Assert projected **Fire** move from Meganium-Mega (Mega Sol) reaches `DamageRequest` with mega attacker species **and** Mega Sol ability semantics; assert own Water move weakened vs neutral baseline; **partner/foe moves unchanged** by global field sun (Mega Sol does not set weather).

---

## 7. I7a — ranking and Tera interaction

### 7.1 Full variant grid

For each `ScoredMegaVariant`, score aggregate value. `argmax` selects winner. **Forbidden:** score best base then overlay mega only.

**T17:** fixture where no-mega A wins vs no-mega B but B+mega beats A — must pick B+mega.

### 7.2 Tera overlay (Reg-I)

After mega winner selected (or on formats without mega): `_maybe_tera` unchanged on **non-mega** base overlay semantics.

**Mutual exclusion:** if chosen joint has `mega_evolve` on any slot, skip Tera overlay. If Tera chosen, `mega_evolve` false.

Champions (`tera: false`): Tera path inactive.

### 7.3 Consumers (I7a PASS)

| Consumer | Requirement |
|----------|-------------|
| `_choose_best` | expand → filter → score `evaluated_variants`; pass same list to trace |
| `max_damage_choice` | **same pipeline** — mandatory |
| depth-2 / export | inherit contexts |

`MegaNotImplementedError` — dev guard only; not I7a PASS path.

---

## 8. Same-turn timing and ground truth

### 8.1 Proven in `showdown_ground_truth.json` (`f8ac140`)

| Claim | In JSON? |
|-------|----------|
| `canMegaEvo: true` boolean | Yes |
| `detailschange` + 3-arg `-mega` before move | Yes (lines listed) |
| Post-mega species, ability, types, speed 122 | Yes |
| Post-mega weather / `-weather` line | **No** |

### 8.2 Weather from Showdown source (`data/abilities.ts`)

| Ability | `onStart` |
|---------|-----------|
| Drought | `sunnyday` |
| Sand Stream | `sandstorm` |
| Snow Warning | `snowscape` |

Mega runs at queue order 104 (`battle-queue.ts`); `comparePriority` uses **pre-mega speed** (`battle.ts:404–410`).

**Projection** applies same weather ids to `projected_state.field` for those abilities. Charizard GT speed 122; sun from source rule not JSON.

### 8.3 Call-site matrix

| Site | Hook |
|------|------|
| `models/request.py` | `can_mega_evo` |
| `models/actions.py` | `mega_evolve` |
| `legal_actions.py` | mega duplicates; filters |
| `actions._slot_actions` | strip mega |
| `mega_variants.expand_mega_variants` | sole expansion |
| `encoder.py` | `mega` token |
| `decision._plan_my_actions` | projected speed/species |
| `decision._choose_best` | variant grid + contexts; trace list = `evaluated_variants` |
| `eval/decision_capture` trace write | receives `evaluated_variants` from caller — no expansion |
| `baselines.max_damage_choice` | same |
| `evaluate.DamageModel` | per-context |
| `search.depth2_value` | context threading |
| `opponent.predict_responses` | §9 |
| `decision` trace | §13 |
| `log_parser` / reducer | §12 |
| `spread_lookup` | §4 |

**P0:** projection before `PlannedAction.speed` assignment.

---

## 9. I7b — opponent mega

### 9.1 Sources (v0)

| Source | Use |
|--------|-----|
| Revealed mega stone item | hypothesis eligible |
| `likely_sets.yaml` / `opp_sets` | hypothesis eligible |
| OTS | **out of v0** |
| Simulator team | **forbidden** |

### 9.2 Click rate env

**`SHOWDOWN_OPP_MEGA_CLICK_RATE`**
- float, **0.0–1.0** inclusive; invalid → fail-closed parse error at env load
- default **0.35** — **judgment-call prior**, not data-fitted
- pre-Strength sensitivity: **0.20 / 0.35 / 0.50**
- in config manifest

Revealed stone ⇒ eligible, **not** deterministic click. Always keep no-mega twin.

### 9.3 Weight split

Family weight `W` after protect prior. `p = SHOWDOWN_OPP_MEGA_CLICK_RATE` when slot has hypothesis else `0`.

| Slots | no-mega | mega |
|-------|---------|------|
| One eligible slot S | `W×(1−p)` | `W×p` on S |
| Two eligible foe slots | `W×(1−p)` | `W×p` split **50/50** between slot-0 and slot-1 mega variants |

`response_id = f"{label}|mega={none|0|1}"` — unique, stable sort.

### 9.4 Pipeline

1. Build base families + weights
2. Expand mega/no-mega twins
3. Normalize to sum 1.0
4. **Coverage-preserving truncate** (§9.5)
5. Renormalize returned list to sum 1.0

### 9.5 Coverage-preserving truncation

Classes `R = {no_mega} ∪ {legal mega slots}`.

**Binding:** after eligibility discovery of legal mega classes `R`, **before** response expansion/truncation: if `format_config.mega` and `len(R) > max_candidates` → raise **`OpponentResponseCapError`** (fail-closed). No startup validation (parameter is per-call).

Default `max_candidates=5`, `|R|≤3` in doubles — OK.

Algorithm when cap sufficient:
1. Reserve highest-weight response per class in `R` (tie: `response_id` lexicographic)
2. Fill remaining slots by weight among unreserved
3. Renormalize final list

**T32:** many heavy no-mega responses cannot eliminate mega class representative.

### 9.6 Scoring and foe post-mega speed

**Today:** `predict_responses` builds foe `PlannedAction.speed` from base form **before** projection.

**Binding (I7b):**
1. After `project_mega` / per `WeightedMegaProjection` branch, **replan or clone** the mega-evolved foe slot’s `PlannedAction` with **post-mega** speed from `speed_for_species` on the projected mon (same path as own-side `_plan_my_actions`).
2. **Activation order** uses pre-mega speed + `mega_activation_order_key` (§5.2).
3. **Move order** within `evaluate_line` uses post-mega speeds via the normal resolver / Trick Room path — not the pre-projection base-form speed.

Own-side post-mega replan is already specified via `_plan_my_actions` on projected state; I7b must mirror this for foe responses.

**Test T51 (I7b):** foe mega changes move order vs base-form plan; `evaluate_line` receives post-mega `PlannedAction.speed`, not the pre-projection base value.

Foe mega responses use `compose_mega_projection_branches` (or `project_mega` for single activation); build one `MegaEvaluationContext` per branch; score with `branch_weight`.

**Until I7b ships:** ROADMAP states `Champions Strength NO-GO — opponent Mega response modeling missing`.

---

## 10. Dual-mega speed tie (weighted branches)

When `compose_mega_projection_branches` returns multiple branches:

- Each branch is a distinct `WeightedMegaProjection` with its own `projected_state` and `activation_order`.
- Activation ordering uses `mega_activation_order_key` (§5.2) — Trick-Room-aware.
- Build one `MegaEvaluationContext` per branch (`branch_weight` from `WeightedMegaProjection.weight`).
- Variant/response score: `sum(branch.weight × score_on_branch(variant))`.
- Ranking, K-world, and I7b all use this weighted sum — **no** single-state merge.

**T26 (I7b):** see §2.5 — unequal/no-TR, same speeds/TR-reversed, and true tie branches.

Unequal pre-mega speeds: one branch, weight `1.0`.

---

## 11. Panel mega matrix and ability gates

### 11.1 Seven panel megas (@pkmn/dex 0.10.11)

| Stone | Form | Types | Ability | Immediate field | v0 modeling |
|-------|------|-------|---------|-----------------|-------------|
| Scovillainite | Scovillain-Mega | Grass/Fire | Spicy Spray | — | **I7a fail-closed** |
| Aerodactylite | Aerodactyl-Mega | Rock/Flying | Tough Claws | — | calc |
| Lucarionite | Lucario-Mega | Fighting/Steel | Adaptability | — | calc |
| Delphoxite | Delphox-Mega | Fire/Psychic | Levitate | — | calc + typing |
| Meganiumite | Meganium-Mega | Grass/Fairy | Mega Sol | no global sun | hook + T28 |
| Froslassite | Froslass-Mega | Ice/Ghost | Snow Warning | snowscape | field hook |
| Tyranitarite | Tyranitar-Mega | Rock/Dark | Sand Stream | sandstorm | field hook |

GT reference: Charizardite Y → Charizard-Mega-Y, Drought, speed 122.

### 11.2 Ability classification (v0)

| Ability | Mechanism | v0 |
|---------|-----------|-----|
| Drought / Sand Stream / Snow Warning | `projected_state.field.weather` | Modeled |
| Adaptability / Tough Claws | calc ability on mon | Modeled |
| Levitate | calc + typing | Modeled |
| Mega Sol | effectiveWeather sunny for **own** moves only | Modeled **after T28** |
| Spicy Spray | `onDamagingHit` burn same turn | **I7a fail-closed** — not in I7a scope |

**Growth** under Mega Sol: fail-closed until tested.

### 11.3 I7a smoke

Default hero Scovillainite must show Scovillain-Mega path **unavailable**, not silent base-form scoring (**T31**).

---

## 12. Log reconciliation (parser-aligned)

### 12.1 Current architecture (unchanged entry points)

- `parse_log_line(prefix, args)` → `LogEvent | None`
- `parse_log(raw)` → `list[LogEvent]`
- `BattleState.from_log(events)` → sequential apply
- `BeliefTracker.update(event)` → `state.apply_event(event)`

**Today:** `detailschange` and `-mega` not parsed (`log_parser.py:233`).

### 12.2 Parse layer additions

**`parse_log_line`:**

```python
if prefix == "detailschange":
    return LogEvent(type="detailschange", pokemon=PokemonId.parse(positional[0]),
                    details=positional[1] if len(positional) > 1 else None, raw=raw)

if prefix == "-mega":
    # args: ident | baseSpecies | stoneDisplayName (3-arg GT)
    return LogEvent(type="mega", pokemon=PokemonId.parse(positional[0]),
                    value=positional[1], details=positional[2], raw=raw)
```

Non-mega `detailschange` (forme without following `-mega` for same ident within reducer window) → normal form change handler only.

### 12.3 Reducer types and `MegaReconcileReducer`

**Module:** `engine/mega_reconcile.py`

**Binding output type (no ambiguous `value`/`details` reuse for mega triple):**

```python
@dataclass(frozen=True)
class MegaReconcileEvent:
    pokemon: PokemonId
    mega_species_details: str   # from detailschange
    base_species: str             # from -mega arg1
    stone_display: str            # from -mega arg2

ReducedLogEvent = LogEvent | MegaReconcileEvent

class MegaReconcileReducer:
    pending_detailschange: dict[str, LogEvent]  # key: side+slot

    def feed(self, event: LogEvent) -> list[ReducedLogEvent]:
        """Emit 0+ events; may hold pending without emitting."""

    def flush_pending(self) -> list[ReducedLogEvent]:
        """Finalize batch: orphaned pending detailschange → ordinary LogEvent(type='detailschange')."""

def reduce_log_events(
    events: list[LogEvent],
    reducer: MegaReconcileReducer | None = None,
) -> list[ReducedLogEvent]:
    """Feed all events, then flush_pending(). Used by BattleState.from_log."""
```

**Call sites (binding):**

| Site | Signature / behavior |
|------|---------------------|
| `MegaReconcileReducer.feed` | `LogEvent` in → `list[ReducedLogEvent]` out |
| `MegaReconcileReducer.flush_pending` | `list[ReducedLogEvent]` — required at batch end |
| `reduce_log_events` | feeds all, calls `flush_pending()` |
| `BattleState.apply_event` | accepts `ReducedLogEvent` (`isinstance` dispatch) |
| `BeliefTracker.update` | `feed(event)` → apply emitted events; **does not** `flush_pending()` |
| `BeliefTracker.feed` | feed each event in batch, then `flush_pending()`, apply all emitted |

**Pairing rule (`feed`):**

1. On `detailschange` for ident X: store in `pending`.
2. On `-mega` for same ident X: if pending exists, validate coherence → emit `MegaReconcileEvent`; clear pending.
3. On `-mega` without pending: **fail-closed** — emit diagnostic or raise; **no mutation**.
4. On unrelated event for different ident while pending exists: flush that pending entry via `flush_pending` logic for that key only (ordinary `detailschange` form update).

**No** bundling of `-weather`/ability lines — separate `LogEvent`s after reconcile apply.

### 12.4 `apply_event` dispatch (atomic mega reconcile)

```python
def apply_event(self, event: ReducedLogEvent) -> None:
    if isinstance(event, MegaReconcileEvent):
        _apply_mega_reconcile(self, event)
        return
    # existing LogEvent branches unchanged
```

```python
def _apply_mega_reconcile(state, event: MegaReconcileEvent) -> None:
    snapshot = copy_battle_state(state)  # or slot-level snapshot
    try:
        _validate_coherence(mon, event)  # uses event.base_species, event.stone_display, event.mega_species_details
        _apply_form_from_details(mon, event.mega_species_details)
        mon.base_species_id = to_id(event.base_species)
        # item: known match keep; unknown set stone; conflict → raise
        state.side_mega_spent[side] = True
        reload types/ability from speciesdata
    except ReconcileError:
        restore snapshot fields for affected mon + side_mega_spent
        raise
```

**Item rules:**

| Case | Action |
|------|--------|
| Known, matches stone | keep |
| Unknown | set stone from `-mega` arg2, `item_known=True` |
| Known conflict | `ReconcileError`, **no partial mutation** |

**No synthetic weather** at reconcile.

### 12.5 Integration points

| Consumer | Change |
|----------|--------|
| `BattleState.from_log` / `from_log_text` | `reduced = reduce_log_events(parse_log(text))`; apply each `ReducedLogEvent` |
| `BeliefTracker.feed(events)` | owns `MegaReconcileReducer` instance; feed batch + `flush_pending()`; apply emitted |
| `BeliefTracker.update(event)` | feed single event; apply emitted; pending may remain until next `feed` or `flush_pending()` |
| `runner` / `gauntlet` | **no** per-room reducer instance — both rebuild state via `BattleState.from_log_text(...)` on full room log; reducer lives inside `from_log` path only |

**T44 executable:** standalone trailing `detailschange` flushed by `reduce_log_events` → `flush_pending()` → ordinary form apply, no `side_mega_spent`.

### 12.6 Reconcile tests

| ID | Case |
|----|------|
| T41 | item conflict → no spend, state unchanged |
| T42 | full room log rebuild applies mega |
| T43 | `BeliefTracker.feed` batch + `flush_pending` same result as full rebuild |
| T44 | `detailschange` without `-mega` → form only, no spend |
| T45 | `-mega` without pending `detailschange` → fail-closed |
| T46 | wrong ident pairing / wrong actor → no mutation |

---

## 13. Trace-v3 (complete)

### 13.1 Constants

```python
TRACE_SCHEMA_VERSION_V3 = "decision-trace-v3"
SUPPORTED_TRACE_SCHEMA_VERSIONS = frozenset({V1, V2, V3})
TRACE_SCHEMA_VERSION = TRACE_SCHEMA_VERSION_V3  # all new writes
```

### 13.2 Candidate key version 2

```python
def _slot_payload(sa: SlotAction) -> dict:
    return {
        "kind": sa.kind,
        "move_index": sa.move_index,
        "target": sa.target,
        "target_ident": sa.target_ident,
        "terastallize": sa.terastallize,
        "mega_evolve": sa.mega_evolve,
    }

def joint_action_key(ja) -> str:
    payload = {"version": 2, "slots": [_slot_payload(ja.slot0), _slot_payload(ja.slot1)]}
    ...
```

### 13.3 Mega vs Tera trace semantics

| Overlay | `candidate_key` in trace list | Chosen slot field |
|---------|------------------------------|-------------------|
| **Mega** | full key with `mega_evolve` flags | `chosen_mega_slot` |
| **Tera** | pre-Tera key (`terastallize: false` all slots) | `chosen_tera_slot` |

Chosen action: **`chosen_mega_slot` and `chosen_tera_slot` mutually exclusive**.

### 13.4 v3 row fields

All `_REQUIRED_TRACE_FIELDS` plus **mandatory keys on every v3 row** (value may be JSON `null`):

- `chosen_candidate_key`
- `chosen_mega_slot`
- `chosen_tera_slot`

Loaders reject v3 rows missing any of these keys. `null` means overlay not chosen.

### 13.5 Validators

**`_validate_candidate_key_v2(key: str)`** — used for **every** `candidates[].candidate_key` and `chosen_candidate_key`:

- valid canonical JSON
- top-level keys exactly: `version`, `slots` — **no unknown keys**
- `version == 2`
- exactly two slot dicts
- per slot, keys exactly: `kind`, `move_index`, `target`, `target_ident`, `terastallize`, `mega_evolve` — **no unknown keys**
- types:
  - `kind`: `"move"` | `"switch"` | `"pass"`
  - `move_index`: `int` | `null`
  - `target`: `int` | `null`
  - `target_ident`: `str` | `null`
  - `terastallize`: `bool`
  - `mega_evolve`: `bool`
- per slot: reject `terastallize and mega_evolve` both `true`
- unique among candidates in row

**`_validate_v3_row(row)`:**

- runs `_validate_v2_row` base checks where applicable
- asserts `chosen_candidate_key`, `chosen_mega_slot`, `chosen_tera_slot` **keys present** (values may be `null`)
- validates **every** candidate key via `_validate_candidate_key_v2`
- rejects v1 keys or missing/non-bool `mega_evolve` in v3 rows
- `_validate_mutual_exclusion_v3` on chosen slots + normalized_action
- `_validate_v3_mega_key_consistency` on chosen key
- `_validate_v2_tera_overlay` when `chosen_tera_slot` set

**v1/v2 loaders:** unchanged code paths.

### 13.6 `/choose` normalization

```python
_MOVE_RE = re.compile(
    r"^move (?P<index>\d+)(?: (?P<target>-?\d+))?(?: (?P<overlay>terastallize|mega))?$"
)
```

### 13.7 Resolver

`resolve_chosen_candidate` unchanged order; v3 requires chosen key match with mega flags when `chosen_mega_slot` set.

### 13.8 Negative trace tests

| ID | Case |
|----|------|
| T33 | both chosen slots set |
| T34 | chosen mega key mismatch |
| T35 | normalized vs chosen_mega_slot mismatch |
| T36 | v2 fixture unchanged |
| T37 | v1 fixture unchanged |
| T47 | v3 candidate with key version 1 → reject |
| T48 | v3 candidate missing `mega_evolve` → reject |
| T49 | duplicate candidate keys in v3 row → reject |
| T52 | v3 candidate key: `terastallize` wrong type (non-bool) → reject |
| T53 | v3 candidate key: unknown slot field → reject |
| T54 | v3 candidate key: both `terastallize` and `mega_evolve` true on same slot → reject |

---

## 14. Provenance

Mega depends on **both** `itemdata.json` and `speciesdata.json`.

| Site | Fields |
|------|--------|
| `build_config_manifest` | `itemdata_hash`, `speciesdata_hash` (optional keys like `movedata_hash`) |
| `config_provenance_for_format` | compute both file content hashes |
| `cli.py`, `gauntlet`, `run_accuracy_baseline_freeze.py`, `run_cap_action_capture.py` | pass into manifest |
| Tests | config hash changes when either file changes; loader `data_hash` fail-closed |

---

## 15. Tests T1–T54 (binding index)

**Slice assignment (binding):**

| Slice | Tests |
|-------|-------|
| **I7a PASS** (no I7b dependency) | T1–T18, T20–T25, T27–T28, T30–T31, T33–T37, T38–T46, T47–T50, T52–T54 |
| **I7b** | T19, T26, T29, T32, T51 |

| ID | Topic |
|----|-------|
| T1 | parse `canMegaEvo` |
| T2 | encoder `move N T mega` |
| T3 | double-mega rejected |
| T4 | mega+tera same slot rejected |
| T5 | projection immutability |
| T6 | Charizard-Y GT projection |
| T7–T13 | seven panel megas metadata/projection |
| T14 | damage uses mega species |
| T15 | plan speed before evaluate |
| T16 | live state unchanged after projections |
| T17 | ranking counterproof |
| T18 | stone held + side spend |
| T19 | I7b weights sum 1 |
| T20 | trace v3 roundtrip |
| T21 | v1/v2 loaders green |
| T22 | Reg-I byte identity no mega |
| T23 | unresolved form fail-closed |
| T24 | unsupported ability fail-closed |
| T25 | max_damage mega wiring |
| T26 | dual-mega branches: no-TR, TR-reversed, tie weighted score **(I7b)** |
| T27 | variant count / no duplicate keys |
| T28 | Mega Sol DamageRequest |
| T29 | post-truncate weights sum 1 **(I7b)** |
| T30 | spread identity mega form |
| T31 | Scovillain fail-closed smoke |
| T32 | coverage-preserving truncate **(I7b)** |
| T33–T37 | trace chosen-field negatives |
| T38–T40 | spread accessor / backfill |
| T41–T46 | reconcile reducer / rollback |
| T47–T49 | per-candidate key v3 negatives |
| T50 | fail-closed variant absent from ranking and trace |
| T51 | foe post-mega speed replan changes move order **(I7b)** |

---

## 16. Non-goals

- No runtime `@pkmn/ps` / `@pkmn/client` dependency
- No full PS client rewrite
- No generic Tera/Mega/Dynamax engine
- No Strength claim at I7a/I7b alone
- No latency budget change
- No `SHOWDOWN_MEGA_MARGIN` env knob in v0
- No OTS in I7b v0
- No Spicy Spray resolve in I7a
- No implementation plan in this document

---

## 17. Implementation slice order (design-only)

1. **I7a** — metadata, projection, variants, contexts, speed API (`mega_activation_order_key`), spread accessor, trace-v3, reconcile reducer, max_damage.
   - **I7a PASS tests:** T1–T18, T20–T25, T27–T28, T30–T31, T33–T37, T38–T46, T47–T50, T52–T54 — **must not** depend on I7b shipping.
2. **I7b** — response pipeline, `compose_mega_projection_branches`, click-rate sensitivity, foe post-mega speed replan.
   - **I7b tests:** T19, T26, T29, T32, T51.
3. **Champions latency**
4. **Strength** — after I7b + latency PASS

---

## Sign-off rev. 10

| Check | Status |
|-------|--------|
| Trick-Room-aware mega activation order | Yes |
| Foe post-mega speed replan (T51) | Yes |
| Exact candidate key v2 schema (T52–T54) | Yes |
| I7a / I7b test slice split | Yes |
| Prior rev. 8 architecture retained | Yes |
| T26 weather winner matches pinned Showdown activation order | Yes — later/slower setter wins outside Trick Room |

**Current artifacts:** I7a is merged on `main`; I7b remains design/plan-only in `docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md` and `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md`.

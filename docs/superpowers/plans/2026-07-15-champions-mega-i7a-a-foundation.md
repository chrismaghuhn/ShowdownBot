# Champions Mega I7a-A Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic Champions Mega metadata, pure own-side projection, protocol encoding, and exactly one evaluated-variant expansion layer without changing decision ranking.

**Architecture:** Build-time `@pkmn/dex` data supplies item-to-form and form metadata. Runtime lookup and projection preserve base-species spread identity while changing the projected form, typing, ability, weather, and speed on a copied state. Protocol legality may expose Mega actions, but the policy enumerator strips them and `battle/mega_variants.py` is the sole expansion owner.

**Tech Stack:** Python 3.11+, Pydantic, pytest, Node.js, `@pkmn/dex` 0.10.11, existing `SpeedOracle` and pinned gen-0 calc.

---

**Status:** APPROVED. Start from `d3dde25` plus the committed split-plan documents. No decision-core integration belongs in this slice.

## File ownership

**Create:**

- `showdown_bot/config/species/speciesdata.json`
- `showdown_bot/src/showdown_bot/engine/species_meta.py`
- `showdown_bot/src/showdown_bot/engine/mega_form.py`
- `showdown_bot/src/showdown_bot/engine/spread_lookup.py`
- `showdown_bot/src/showdown_bot/engine/mega_projection.py`
- `showdown_bot/src/showdown_bot/battle/mega_variants.py`
- `showdown_bot/tests/i7a/conftest.py`
- `showdown_bot/tests/i7a/test_i7a_foundation.py`
- `showdown_bot/tests/fixtures/i7a_charizard_mega_y_gt.json`
- `showdown_bot/tests/fixtures/i7a_charizard_mega_y_gt.PROVENANCE.md`

**Modify:**

- `showdown_bot/tools/gen/gen_movedata.mjs`
- `showdown_bot/config/items/itemdata.json`
- `showdown_bot/src/showdown_bot/engine/items.py`
- `showdown_bot/src/showdown_bot/engine/state.py`
- `showdown_bot/src/showdown_bot/engine/speed.py`
- `showdown_bot/src/showdown_bot/models/request.py`
- `showdown_bot/src/showdown_bot/models/actions.py`
- `showdown_bot/src/showdown_bot/battle/actions.py`
- `showdown_bot/src/showdown_bot/battle/legal_actions.py`
- `showdown_bot/src/showdown_bot/battle/resolve.py`
- `showdown_bot/src/showdown_bot/protocol/encoder.py`
- focused existing tests for those modules

**Forbidden in this slice:** `battle/decision.py`, `battle/baselines.py`, `eval/decision_capture.py`, `engine/log_parser.py`, `engine/belief/tracker.py`, provenance manifests, schedules, and eval artifacts.

### Task 1: Generate and pin Mega metadata

**Files:** generator, item/species JSON, `tests/test_movedata.py`.

- [ ] **Step 1: Add failing artifact-shape tests**

```python
def test_itemdata_exposes_mega_stone_target():
    items = _load("items/itemdata.json")["items"]
    assert items["aerodactylite"]["megaStone"] == "Aerodactyl-Mega"


def test_speciesdata_exposes_mega_form_metadata():
    row = _load("species/speciesdata.json")["species"]["aerodactylmega"]
    assert row["baseSpecies"] == "Aerodactyl"
    assert row["baseStats"]["spe"] == 150
    assert row["abilities"]["0"] == "Tough Claws"
    assert row["requiredItem"] == "Aerodactylite"
```

- [ ] **Step 2: Run the tests and confirm the artifact is absent/stale**

Run from `showdown_bot/`:

```powershell
python -m pytest tests/test_movedata.py -q
```

Expected: the new checks fail before generator changes.

- [ ] **Step 3: Extend the generator with deterministic records**

`itemRecord()` must add `megaStone: it.megaStone ?? null`. Add a species pack whose record contains exactly `id`, `name`, `baseSpecies`, `types`, `baseStats`, `abilities`, and `requiredItem`. Use the existing `pack()` function so `source_version`, `generation`, and embedded `data_hash` follow the movedata/itemdata convention.

```javascript
function speciesRecord(species) {
  return {
    id: species.id,
    name: species.name,
    baseSpecies: species.baseSpecies,
    types: species.types,
    baseStats: species.baseStats,
    abilities: species.abilities,
    requiredItem: species.requiredItem ?? null,
  };
}

const species = dex.species.all()
  .filter((entry) => entry.exists !== false)
  .map(speciesRecord)
  .sort((a, b) => a.id.localeCompare(b.id));

const targets = [
  ['moves/movedata.json', pack('moves', moves)],
  ['items/itemdata.json', pack('items', items)],
  ['species/speciesdata.json', pack('species', species)],
];
```

Create `config/species/` in the same write loop as the existing move/item directories. `--check` must compare all three generated artifacts and fail if any embedded `data_hash` differs.

- [ ] **Step 4: Regenerate, verify freshness, and rerun tests**

```powershell
npm --prefix tools/gen ci
npm --prefix tools/gen run gen
npm --prefix tools/gen run check
python -m pytest tests/test_movedata.py tests/test_items.py -q
```

Expected: generator check and tests pass.

- [ ] **Step 5: Commit generated metadata**

```powershell
git add tools/gen/gen_movedata.mjs config/items/itemdata.json config/species/speciesdata.json tests/test_movedata.py
git commit -m "feat(champions): generate Mega form metadata"
```

### Task 2: Add runtime metadata loaders and the ground-truth fixture

**Files:** `engine/items.py`, new `engine/species_meta.py`, `engine/mega_form.py`, fixture/provenance, `tests/i7a/*`.

- [ ] **Step 1: Write failing loader, hash, form-resolution, and stale-data tests**

The fixture root in `tests/i7a/conftest.py` is:

```python
from pathlib import Path
import pytest

SHOWDOWN_BOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]

@pytest.fixture
def charizard_y_gt():
    import json
    return json.loads((SHOWDOWN_BOT_ROOT / "tests/fixtures/i7a_charizard_mega_y_gt.json").read_text())
```

Tests must prove `ItemMeta.mega_stone == "Charizard-Mega-Y"`, `get_species_form_meta("Charizard-Mega-Y")`, `mega_form_for("Charizard", "Charizardite Y")`, unknown item returns `None`, and tampering with either embedded `data_hash` raises the loader-specific stale-data error after clearing its cache.

- [ ] **Step 2: Run the focused RED tests**

```powershell
python -m pytest tests/i7a/test_i7a_foundation.py -k "metadata or form or hash" -q
```

Expected: imports or assertions fail because the loaders do not exist.

- [ ] **Step 3: Implement exact DTOs and content hashes**

```python
@dataclass(frozen=True)
class SpeciesFormMeta:
    form_species_id: str
    form_species_name: str
    base_species_id: str
    base_species_name: str
    types: tuple[str, ...]
    base_stats: dict[str, int] = field(compare=False)
    ability_slot0: str = ""
    required_item: str | None = None


@dataclass(frozen=True)
class MegaForm:
    base_species_id: str
    form_species_id: str
    form_species_name: str
    stone_item_id: str
```

Expose `itemdata_content_hash()` and `speciesdata_content_hash()` as the embedded 16-hex `data_hash` after re-computing it with the same canonical JSON contract used by the generator. Never fall back to a file hash when the embedded hash is stale.

The Python verifier mirrors `JSON.stringify(data)` by retaining decoded insertion order and using compact separators without `sort_keys`:

```python
def _embedded_hash(raw: dict, table_key: str) -> str:
    payload = json.dumps(
        raw[table_key],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
```

The form resolver has one exact contract:

```python
def mega_form_for(
    base_species_name: str,
    item_id: str,
    *,
    item_table: dict[str, ItemMeta] | None = None,
    species_meta: dict[str, SpeciesFormMeta] | None = None,
) -> MegaForm | None:
    items = _item_table() if item_table is None else item_table
    forms = species_meta_table() if species_meta is None else species_meta
    base_id = to_id(base_species_name)
    item = items.get(to_id(item_id))
    if item is None or not item.mega_stone:
        return None
    form = forms.get(to_id(item.mega_stone))
    if form is None or form.base_species_id != base_id:
        return None
    return MegaForm(base_id, form.form_species_id, form.form_species_name, item.id)
```

- [ ] **Step 4: Verify loaders and fixture provenance**

The provenance document pins Showdown `f8ac140`, the exact protocol lines, source path, and SHA-256 of the committed JSON fixture. Run:

```powershell
python -m pytest tests/test_items.py tests/i7a/test_i7a_foundation.py -k "metadata or form or hash" -q
```

- [ ] **Step 5: Commit runtime metadata**

```powershell
git add src/showdown_bot/engine/items.py src/showdown_bot/engine/species_meta.py src/showdown_bot/engine/mega_form.py tests/i7a tests/fixtures/i7a_charizard_mega_y_gt.*
git commit -m "feat(champions): load Mega form metadata"
```

### Task 3: Preserve base-species spread identity

**Files:** `engine/state.py`, new `engine/spread_lookup.py`, team spread consumers, focused tests.

- [ ] **Step 1: Add failing base-id and dual-key lookup tests**

```python
def test_projected_species_uses_base_species_spread_key():
    mon = PokemonState(species="Aerodactyl-Mega", base_species_id="aerodactyl")
    spreads = {"aerodactyl": object(), "Aerodactyl": object()}
    assert lookup_our_spreads(spreads, mon) is spreads["aerodactyl"]


def test_legacy_state_backfills_base_species_id():
    assert PokemonState(species="Aerodactyl").base_species_id == "aerodactyl"
```

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_foundation.py -k "spread or base_species" -q
```

- [ ] **Step 3: Implement the only spread accessors**

```python
def spread_lookup_key(mon: PokemonState) -> str:
    return mon.base_species_id or to_id(mon.species)


def lookup_our_spreads(our_spreads, mon):
    if not our_spreads:
        return None
    key = spread_lookup_key(mon)
    return our_spreads.get(key) or our_spreads.get(mon.species)


def lookup_opp_set(opp_sets, mon):
    if not opp_sets:
        return None
    return opp_sets.get(spread_lookup_key(mon)) or opp_sets.get(to_id(mon.species))
```

Add `base_species_id: str = ""` and a `PokemonState.__post_init__` backfill. Migrate `DamageModel`, `apply_own_team_knowledge`, and the packed-team loader to the accessors; the loader temporarily writes normalized base id and display-name aliases.

- [ ] **Step 4: Run spread and damage regressions**

```powershell
python -m pytest tests/i7a/test_i7a_foundation.py tests/test_spreads.py tests/test_evaluate.py -q
```

- [ ] **Step 5: Commit spread identity**

```powershell
git add src/showdown_bot/engine/state.py src/showdown_bot/engine/spread_lookup.py src/showdown_bot/team/spreads.py src/showdown_bot/battle/evaluate.py tests
git commit -m "feat(champions): preserve base species spread identity"
```

### Task 4: Add pure own-side projection and public species speed

**Files:** new `engine/mega_projection.py`, `engine/speed.py`, foundation tests.

- [ ] **Step 1: Add failing immutability, seven-form, weather, stone, spend, and speed tests**

Required assertions: live input state remains byte-equivalent; projected form keeps `base_species_id` and item; branch-local `side_mega_spent[p1]` is true; Aerodactyl gen-0 speed is `222`; Drought/Sand Stream/Snow Warning set only copied field; Mega Sol leaves global weather unchanged; Spicy Spray is reported unsupported.

- [ ] **Step 2: Run RED after calc preflight**

```powershell
npm --prefix tools/calc ci
python -m pytest tests/i7a/test_i7a_foundation.py -k "projection or speed or weather" -q
```

- [ ] **Step 3: Add the public speed API and pure projection**

```python
def speed_for_species(self, *, species_name, base_species_id, side, mon, field,
                      our_spreads, opp_sets, book, is_ours) -> int:
    if is_ours:
        preset = lookup_our_spreads(our_spreads, mon)
        if preset is None:
            raise MissingMegaSpreadError(base_species_id)
        base = self._base_speed(species_name, preset.offense.nature, preset.offense.evs)
        return effective_speed_from_state(base, mon, field, side)
    # opponent branch uses lookup_opp_set/book and remains format-neutral
```

Define `MissingMegaSpreadError` in `engine/speed.py`. `copy_battle_state()` must deep-copy `sides`, every mon, `field`, `side_mega_spent`, and `turn`.

The own-side projection signature is:

```python
def project_mega(
    state: BattleState,
    side: str,
    slot: str,
    mega_form: MegaForm,
    *,
    species_meta: dict[str, SpeciesFormMeta],
    speed_oracle: SpeedOracle,
    spread_lookup: dict,
    calc_profile: CalcProfile,
) -> MegaProjectionResult:
    """Project one own Mega; spread_lookup is the our_spreads mapping."""
```

`project_mega()` must never mutate its input and must raise a typed projection/ability error for unsupported material abilities rather than returning a partially projected state.
Before calculating projected speed, assert `speed_oracle.profile == calc_profile`; a cross-format oracle is a fail-closed configuration error, not a reason to reuse gen-9 stats.

- [ ] **Step 4: Run projection and speed suites**

```powershell
python -m pytest tests/i7a/test_i7a_foundation.py tests/test_speed.py -q
```

- [ ] **Step 5: Commit projection**

```powershell
git add src/showdown_bot/engine/mega_projection.py src/showdown_bot/engine/speed.py tests/i7a/test_i7a_foundation.py tests/test_speed.py
git commit -m "feat(champions): project own Mega forms without mutating state"
```

### Task 5: Add protocol legality and the sole variant-expansion owner

**Files:** request/action DTOs, encoder, legal/policy enumeration, `battle/mega_variants.py`, `resolve.py`, tests.

- [ ] **Step 1: Add failing T1–T4, T23, T24, T27, and T50 foundation tests**

Tests must parse `canMegaEvo`, encode `move 1 2 mega`, reject double Mega and same-slot Mega+Tera, strip both overlays from `enumerate_my_actions`, emit exactly one no-Mega plus each eligible slot variant per base joint, preserve enumeration order, and filter unresolved/Spicy-Spray variants.

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/test_request_models.py tests/test_legal_actions.py tests/i7a/test_i7a_foundation.py -k "mega or variant" -q
```

- [ ] **Step 3: Implement DTO, encoder, legality, and expansion contracts**

```python
class ActiveSlot(BaseModel):
    can_mega_evo: bool = Field(default=False, alias="canMegaEvo")

@dataclass(frozen=True)
class SlotAction:
    kind: Literal["move", "switch", "pass"]
    move_index: int | None = None
    target: int | None = None
    terastallize: bool = False
    target_ident: str | None = None
    mega_evolve: bool = False

@dataclass(frozen=True)
class ScoredMegaVariant:
    joint: JointAction
    own_mega_slot: int | None


def filter_projectable_variants(
    variants: list[ScoredMegaVariant],
    req: BattleRequest,
    state: BattleState,
    our_side: str,
    *,
    species_meta: dict[str, SpeciesFormMeta],
    speed_oracle: SpeedOracle,
    our_spreads: dict,
    calc_profile: CalcProfile,
) -> list[ScoredMegaVariant]:
    """Keep no-Mega variants and Mega slots whose full own projection succeeds."""
```

`format_slot_action` raises `ValueError` if both overlays are true and otherwise appends `mega` after the optional target. `_slot_actions` strips Mega and Tera. `expand_mega_variants` is the only policy expansion site. `filter_projectable_variants` resolves the active item/form and calls `project_mega` once per distinct eligible slot; a missing spread or unsupported ability removes that slot's Mega variants. Add `PlannedAction.is_mega` but do not populate it until I7a-B.

- [ ] **Step 4: Run the complete I7a-A gate**

```powershell
python -m pytest tests/test_movedata.py tests/test_items.py tests/test_request_models.py tests/test_legal_actions.py tests/test_actions.py tests/test_encoder.py tests/test_battle_state.py tests/test_speed.py tests/test_spreads.py tests/test_evaluate.py tests/i7a/test_i7a_foundation.py -q
git diff --check
```

Expected: all pass; no file forbidden by this slice is modified.

- [ ] **Step 5: Commit protocol/variant foundation**

```powershell
git add src/showdown_bot/models src/showdown_bot/protocol/encoder.py src/showdown_bot/battle/actions.py src/showdown_bot/battle/legal_actions.py src/showdown_bot/battle/mega_variants.py src/showdown_bot/battle/resolve.py tests
git commit -m "feat(champions): enumerate projectable own Mega variants"
```

## I7a-A completion gate

- Generator `check` passes from a fresh `npm ci`.
- Tests T1–T13, T18, T23–T24, T27, T30, T38–T40, and foundation half of T50 pass.
- `_choose_best`, `max_damage_choice`, trace schemas, log parsing, manifests, schedules, and eval data have no diff.
- Different Mega variants have deterministic distinct structural actions once key-v2 is added in I7a-B; this slice does not change the current v1 key.
- No commit or message claims decision quality, latency, or Strength.

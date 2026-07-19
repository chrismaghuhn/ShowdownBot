# Phase A — Move/Item Daten-Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` (inline). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Die 25-Move-Handtabelle durch datengetriebene Move-/Item-Metadaten aus `@pkmn/dex` ersetzen, plus eine kuratierte Effekt-Klassen-Schicht — ohne bestehendes Verhalten zu brechen.

**Architecture:** Build-time Node-Generator (`@pkmn/dex`) → eingecheckte JSON-Daten → Python-Loader baut angereichertes `MoveMeta`/`ItemMeta`. Kuratierte YAML-Schicht liefert die Semantik (`effect_class`).

**Tech Stack:** Node `@pkmn/dex`/`@pkmn/data`, Python (PyYAML, json, dataclasses, pytest).

**Backward-Compat-Vertrag (darf NICHT brechen):** `engine/moves.py` wird konsumiert von `battle/resolve.py` (uncommitted!), `battle/decision.py` (uncommitted!) und `tests/test_moves.py`. `MoveMeta` muss alle bestehenden Felder/Properties behalten: `id, name, priority, category("physical"|"special"|"status"), target, base_power, move_type, flags(frozenset), terrain_priority`, Properties `is_damaging/is_spread/hits_foe`, Modulfunktionen `get_move_meta/move_priority/blocks_move/can_redirect`. `resolve.py` prüft `"flinch" in move.flags` und `"protect" in move.flags` → der Generator muss den synthetischen `flinch`-Flag aus `secondary.volatileStatus=="flinch"` erzeugen.

---

### Task A1: Generator-Setup (sauber getrennt von calc)

**Files:**
- Create: `showdown_bot/tools/gen/package.json`
- Create: `showdown_bot/tools/gen/gen_movedata.mjs`
- Revert: `showdown_bot/tools/calc/package.json`, `package-lock.json` (die @pkmn-devDeps gehören nicht in den Damage-Bridge)

- [ ] **Step 1: calc-Verzeichnis wieder rein machen**

```bash
cd "showdown_bot/tools/calc" && git checkout package.json package-lock.json
```

- [ ] **Step 2: gen-Paket anlegen + installieren**

`showdown_bot/tools/gen/package.json`:
```json
{
  "name": "showdown-bot-gen",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "description": "Build-time generator: @pkmn/dex -> movedata.json/itemdata.json. NOT a runtime dependency.",
  "dependencies": { "@pkmn/dex": "^0.9.0", "@pkmn/data": "^0.9.0" }
}
```
```bash
cd "showdown_bot/tools/gen" && npm install --no-audit --no-fund
```

- [ ] **Step 3: @pkmn/dex Move/Item-Shape proben** (exakte Feldnamen verifizieren, v.a. `terrain`, `secondaries`, `multihit`, `condition.duration`)

Throwaway `tools/gen/_probe.mjs`, ausführen, löschen. Notiere die real vorhandenen Felder; nur diese im Generator erfassen.

- [ ] **Step 4: Generator schreiben** (`gen_movedata.mjs`)

```js
import { Dex } from '@pkmn/dex';
import { createHash } from 'node:crypto';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const GEN = 9;
const FORMAT = 'gen9vgc2024regg';
const here = dirname(fileURLToPath(import.meta.url));
const configDir = resolve(here, '../../config');
const dex = Dex.forGen(GEN);

const sourceVersion =
  JSON.parse(readFileSyncSafe(resolve(here, 'node_modules/@pkmn/dex/package.json')))?.version ?? 'unknown';

function readFileSyncSafe(p) { try { return require('node:fs').readFileSync(p, 'utf8'); } catch { return null; } }

function flinchSynth(m) {
  const secs = m.secondaries ? m.secondaries : (m.secondary ? [m.secondary] : []);
  return secs.some(s => s && s.volatileStatus === 'flinch');
}

function moveRecord(m) {
  const flags = Object.keys(m.flags || {});
  if (flinchSynth(m)) flags.push('flinch');
  return {
    id: m.id, name: m.name,
    basePower: m.basePower, category: m.category, type: m.type,
    priority: m.priority, target: m.target,
    status: m.status ?? null, volatileStatus: m.volatileStatus ?? null,
    sideCondition: m.sideCondition ?? null, slotCondition: m.slotCondition ?? null,
    weather: m.weather ?? null, terrain: m.terrain ?? null,
    boosts: m.boosts ?? null, self: m.self ?? null,
    secondary: m.secondary ?? null, secondaries: m.secondaries ?? null,
    drain: m.drain ?? null, recoil: m.recoil ?? null, multihit: m.multihit ?? null,
    flags: flags.sort(),
  };
}

function itemRecord(it) {
  return {
    id: it.id, name: it.name,
    isBerry: !!it.isBerry, isChoice: !!it.isChoice,
    boosts: it.boosts ?? null, naturalGift: it.naturalGift ?? null,
    fling: it.fling ?? null, shortDesc: it.shortDesc ?? it.desc ?? '',
  };
}

function dump(kind, records) {
  const data = Object.fromEntries(records.map(r => [r.id, r]));
  const hash = createHash('sha256').update(JSON.stringify(data)).digest('hex').slice(0, 16);
  return { source_version: sourceVersion, generation: GEN, format: FORMAT, data_hash: hash, [kind]: data };
}

const moves = dex.moves.all().map(moveRecord).sort((a, b) => a.id.localeCompare(b.id));
const items = dex.items.all().map(itemRecord).sort((a, b) => a.id.localeCompare(b.id));

mkdirSync(resolve(configDir, 'moves'), { recursive: true });
mkdirSync(resolve(configDir, 'items'), { recursive: true });
const write = (p, obj) => writeFileSync(p, JSON.stringify(obj, null, 1) + '\n');

const checkOnly = process.argv.includes('--check');
const moveOut = dump('moves', moves), itemOut = dump('items', items);
if (checkOnly) {
  // Compare data_hash against checked-in files; exit 1 on mismatch.
  const fs = await import('node:fs');
  for (const [p, fresh] of [['moves/movedata.json', moveOut], ['items/itemdata.json', itemOut]]) {
    const cur = JSON.parse(fs.readFileSync(resolve(configDir, p), 'utf8'));
    if (cur.data_hash !== fresh.data_hash) { console.error(`STALE: ${p}`); process.exit(1); }
  }
  console.log('fresh'); process.exit(0);
}
write(resolve(configDir, 'moves/movedata.json'), moveOut);
write(resolve(configDir, 'items/itemdata.json'), itemOut);
console.log(`wrote ${moves.length} moves, ${items.length} items`);
```

*(Hinweis: `require` in ESM via `createRequire` falls nötig — beim Proben klären.)*

- [ ] **Step 5: Generator ausführen**

```bash
cd "showdown_bot/tools/gen" && node gen_movedata.mjs
```
Expected: `wrote 954 moves, 583 items`; Dateien `showdown_bot/config/moves/movedata.json`, `showdown_bot/config/items/itemdata.json` existieren mit `data_hash`-Header.

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/tools/gen/package.json showdown_bot/tools/gen/gen_movedata.mjs \
        showdown_bot/config/moves/movedata.json showdown_bot/config/items/itemdata.json
git commit -m "feat(data): @pkmn/dex generator for move/item metadata"
```

---

### Task A2: Python lädt + Freshness-Test

**Files:**
- Test: `showdown_bot/tests/test_movedata.py`

- [ ] **Step 1: Struktur-Test schreiben**

```python
import json, subprocess, shutil
from pathlib import Path
import pytest

CONFIG = Path(__file__).resolve().parents[1] / "config"

def _load(name):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))

def test_movedata_has_version_and_known_moves():
    data = _load("moves/movedata.json")
    assert data["generation"] == 9 and data["data_hash"]
    moves = data["moves"]
    assert len(moves) > 800
    assert moves["willowisp"]["status"] == "brn"
    assert moves["tailwind"]["sideCondition"] == "tailwind"
    assert moves["swordsdance"]["boosts"] == {"atk": 2}
    assert "flinch" in moves["fakeout"]["flags"]      # synthetic flag preserved

def test_itemdata_known_items():
    items = _load("items/itemdata.json")["items"]
    assert items["leftovers"]["name"] == "Leftovers"
    assert items["choicescarf"]["isChoice"] is True
```

- [ ] **Step 2: Test laufen lassen** — `cd showdown_bot && python -m pytest tests/test_movedata.py -q` → PASS.

- [ ] **Step 3: Freshness-Test ergänzen** (skippt ohne node)

```python
def test_generated_data_is_fresh():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    gen = CONFIG.parent / "tools" / "gen"
    if not (gen / "node_modules").exists():
        pytest.skip("generator deps not installed")
    r = subprocess.run(["node", "gen_movedata.mjs", "--check"], cwd=gen,
                        capture_output=True, text=True)
    assert r.returncode == 0, f"generated data is stale: {r.stdout}{r.stderr}"
```

- [ ] **Step 4: Lauf + Commit** — Test grün, dann `git add tests/test_movedata.py && git commit -m "test(data): movedata structure + freshness"`.

---

### Task A3: Angereichertes `MoveMeta` (backward-compatible)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/engine/moves.py`
- Modify: `showdown_bot/tests/test_moves.py` (nur additive Assertions)

- [ ] **Step 1: Bestehenden Vertrag lesen** — `tests/test_moves.py` und die Nutzung in `resolve.py` (`"flinch"/"protect" in flags`, `is_spread`, `terrain_priority`) durchgehen, damit nichts bricht.

- [ ] **Step 2: Failing test** (neues Verhalten) in `test_moves.py`:

```python
def test_get_move_meta_enriched_from_data():
    m = get_move_meta("Will-O-Wisp")
    assert m.category == "status" and m.status == "brn"
    t = get_move_meta("Tailwind")
    assert t.side_condition == "tailwind"
    f = get_move_meta("Fake Out")
    assert "flinch" in f.flags and f.priority == 3        # behavior preserved
    eq = get_move_meta("Earthquake")
    assert eq.is_spread and eq.target == "allAdjacent"
```

- [ ] **Step 3: `moves.py` umbauen** — JSON beim Import cachen; `MoveMeta` um Felder erweitern (`status, volatile_status, side_condition, slot_condition, weather, terrain, boosts, secondary, drain, recoil, multihit, effect_classes`), alle Altfelder/Properties behalten, `category` lowercasen, `get_move_meta` liest aus Cache (Fallback 80-BP-physical bei unbekannt). `_TABLE` entfällt. `terrain_priority` per Overlay aus Task A4 (vorerst aus kleinem Dict `{"grassyglide":"Grassy"}`).

- [ ] **Step 4: Volle Suite** — `cd showdown_bot && python -m pytest -q` → **147 alte + neue grün**. Bei rot: Vertrag verletzt, fixen.

- [ ] **Step 5: Commit** — `git add src/showdown_bot/engine/moves.py tests/test_moves.py && git commit -m "feat(moves): data-driven enriched MoveMeta"`.

---

### Task A4: Kuratierte `effect_classes.yaml` + Schema-Test

**Files:**
- Create: `showdown_bot/config/moves/effect_classes.yaml`
- Modify: `showdown_bot/src/showdown_bot/engine/moves.py` (Overlay-Loader)
- Test: `showdown_bot/tests/test_effect_classes.py`

- [ ] **Step 1: YAML schreiben** — v1-Set aus Spec §7.4. Form:

```yaml
# move_id: { classes: [...], params: {...} }
willowisp:   { classes: [status_infliction], params: { status: brn } }
spore:       { classes: [status_infliction], params: { status: slp } }
tailwind:    { classes: [speed_control, field_setter], params: { side_condition: tailwind, duration: 4 } }
trickroom:   { classes: [speed_control, field_setter], params: { field: trickroom, duration: 5 } }
reflect:     { classes: [field_setter], params: { side_condition: reflect, duration: 5 } }
lightscreen: { classes: [field_setter], params: { side_condition: lightscreen, duration: 5 } }
auroraveil:  { classes: [field_setter], params: { side_condition: auroraveil, duration: 5 } }
swordsdance: { classes: [setup_self], params: { boosts: { atk: 2 } } }
nastyplot:   { classes: [setup_self], params: { boosts: { spa: 2 } } }
dragondance: { classes: [setup_self], params: { boosts: { atk: 1, spe: 1 } } }
calmmind:    { classes: [setup_self], params: { boosts: { spa: 1, spd: 1 } } }
snarl:       { classes: [debuff_foe], params: { boosts: { spa: -1 } } }
icywind:     { classes: [speed_control, debuff_foe], params: { boosts: { spe: -1 } } }
partingshot: { classes: [pivot, debuff_foe], params: { boosts: { atk: -1, spa: -1 } } }
protect:     { classes: [protect] }
detect:      { classes: [protect] }
wideguard:   { classes: [protect] }
quickguard:  { classes: [protect] }
spikyshield: { classes: [protect], params: { contact_damage: 0.125 } }
followme:    { classes: [redirect] }
ragepowder:  { classes: [redirect], params: { powder: true } }
uturn:       { classes: [pivot] }
voltswitch:  { classes: [pivot] }
flipturn:    { classes: [pivot] }
helpinghand: { classes: [disruption], params: { ally_damage_mult: 1.5 } }
taunt:       { classes: [disruption], params: { volatile: taunt, duration: 3 } }
encore:      { classes: [disruption], params: { volatile: encore, duration: 3 } }
haze:        { classes: [disruption], params: { reset_boosts: true } }
leechseed:   { classes: [volatile_inflict, recovery], params: { volatile: leechseed } }
grassyglide: { classes: [], params: { terrain_priority: Grassy } }
```

- [ ] **Step 2: Loader-Overlay** in `moves.py` — YAML einlesen, `effect_classes`/`params` in `MoveMeta` mergen; `terrain_priority` aus `params.terrain_priority` ziehen (ersetzt das Dict aus A3).

- [ ] **Step 3: Schema-Test schreiben**

```python
KNOWN_CLASSES = {"speed_control","status_infliction","setup_self","debuff_foe",
  "protect","redirect","pivot","field_setter","disruption","recovery",
  "damage_modifier","volatile_inflict"}

def test_effect_classes_reference_real_moves_and_known_classes():
    data = json.loads((CONFIG/"moves/movedata.json").read_text("utf-8"))["moves"]
    ec = yaml.safe_load((CONFIG/"moves/effect_classes.yaml").read_text("utf-8"))
    for mid, entry in ec.items():
        assert mid in data, f"unknown move_id {mid}"
        for c in entry.get("classes", []):
            assert c in KNOWN_CLASSES, f"unknown class {c} on {mid}"
```

- [ ] **Step 4: Lauf + Commit** — grün, dann `git add config/moves/effect_classes.yaml src/showdown_bot/engine/moves.py tests/test_effect_classes.py && git commit -m "feat(moves): curated v1 effect classes + schema test"`.

---

### Task A5: `items.py` + `item_effect_classes.yaml`

**Files:**
- Create: `showdown_bot/src/showdown_bot/engine/items.py`
- Create: `showdown_bot/config/items/item_effect_classes.yaml`
- Test: `showdown_bot/tests/test_items.py`

- [ ] **Step 1: Failing test**

```python
from showdown_bot.engine.items import get_item_meta
def test_item_meta_classes():
    lo = get_item_meta("Life Orb")
    assert "damage_stat" in lo.classes and lo.params.get("recoil") == 0.1
    s = get_item_meta("Sitrus Berry")
    assert "threshold_heal" in s.classes and s.params["frac"] == 0.25
    sc = get_item_meta("Choice Scarf")
    assert "speed" in sc.classes and sc.params["mult"] == 1.5
```

- [ ] **Step 2: YAML schreiben** (`item_effect_classes.yaml`)

```yaml
leftovers:     { classes: [residual_heal], params: { frac: 0.0625 } }
blacksludge:   { classes: [residual_heal], params: { frac: 0.0625 } }
sitrusberry:   { classes: [threshold_heal], params: { frac: 0.25, at: 0.5 } }
lumberry:      { classes: [status_cure] }
focussash:     { classes: [pinch_trigger], params: { survive_at_full: true } }
choicescarf:   { classes: [speed], params: { mult: 1.5 } }
lifeorb:       { classes: [damage_stat, residual_self], params: { dmg_mult: 1.3, recoil: 0.1 } }
boosterenergy: { classes: [activation_item], params: { stat_overlay: highest } }
safetygoggles: { classes: [effect_block], params: { blocks: [powder, weather_chip] } }
covertcloak:   { classes: [effect_block], params: { blocks: [secondary] } }
clearamulet:   { classes: [effect_block], params: { blocks: [stat_drop] } }
mentalherb:    { classes: [status_cure], params: { cures: [taunt, encore, disable] } }
rockyhelmet:   { classes: [contact_punish], params: { frac: 0.1667 } }
weaknesspolicy:{ classes: [pinch_trigger], params: { on: super_effective, boosts: { atk: 2, spa: 2 } } }
```

- [ ] **Step 3: `items.py` implementieren** — `ItemMeta(id, name, is_berry, is_choice, classes, params, ...)`, lädt `itemdata.json` + `item_effect_classes.yaml`, `get_item_meta(name)` mit `to_id`-Normalisierung; unbekannt → leere Klassen.

- [ ] **Step 4: Schema-Test** analog A4 (jede item_id in itemdata; Klassen bekannt).

- [ ] **Step 5: Lauf + Commit** — grün, dann `git add src/showdown_bot/engine/items.py config/items/item_effect_classes.yaml tests/test_items.py && git commit -m "feat(items): ItemMeta + curated v1 item effect classes"`.

---

## Phase-A-Exit

- `python -m pytest -q` grün (147 alt + neue).
- `get_move_meta` liefert reiche Daten für alle 954 Moves; `get_item_meta` für 583 Items.
- Freshness- + Schema-Tests grün.
- Keine Berührung von `state.py`/`decision.py`/`resolve.py`/`evaluate.py` (alle uncommitted oder Phase C).

## Self-Review (nach dem Schreiben)

- **Spec-Abdeckung:** §4 (Pipeline) ✓, §4.2 (effect classes) ✓, §5.1 (item classes) ✓, §11 (freshness/schema tests) ✓. ConditionEngine/Rollout → Phase B/C.
- **Platzhalter:** Step 3 in A1 ist ein echter Probe-Schritt (Feldnamen verifizieren), kein TODO.
- **Typkonsistenz:** `MoveMeta`-Felder in A3 == in A4 referenziert (`side_condition`, `effect_classes`, `terrain_priority`); `ItemMeta.classes/params` in A5 konsistent mit Test.

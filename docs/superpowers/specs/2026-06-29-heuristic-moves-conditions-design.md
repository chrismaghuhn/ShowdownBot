# HeuristicBot — Move-Effekt- & Condition-System (Reg G) — Design Spec

**Datum:** 2026-06-29
**Status:** Entwurf (Review ausstehend)
**Phase:** Erweiterung der Phase-2-Heuristik (`docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md`)
**Scope:** Move-Semantik, Items, Conditions und Multi-Turn-Condition-Rollout für den Ein-Ply-HeuristicBot (Format `gen9vgc2024regg`)

---

## 1. Ziel & Nicht-Ziele

Heute kennt der HeuristicBot nur ~25 Moves konkret (Handtabelle in `engine/moves.py`); jeder unbekannte Move wird als generischer 80-BP-Physikangriff behandelt. Laufende Conditions (Burn, Paralyse, Wetter, Screens, Tailwind …) werden zwar im State getrackt, aber im Resolver und beim Scoring ignoriert. Dieses Dokument schließt diese Lücke.

**Leitsatz (Scope-Ehrlichkeit):**

> Ziel ist **nicht**, Pokémon Showdown vollständig nachzubauen, sondern alle relevanten **VGC-Reg-G-Movefamilien und Conditions** so zu modellieren, dass der HeuristicBot taktisch bessere Entscheidungen trifft. Unklassifizierte Moves behalten korrekte Rohmechanik und fallen auf generische Bewertung zurück.

**Nicht-Ziele:**

- Keine vollständige Battle-Engine / kein PS-Klon.
- Kein Multi-Ply-Entscheidungsbaum beider Spieler (siehe Invariante I-2).
- Kein exakter Damage-Nachbau im Rollout (siehe Invariante I-4).
- Long-Tail-Mechaniken (Perish Song, Instruct, After You, Quash, Wonder/Magic Room, Hazards) sind in v1 bewusst ausgeklammert.

---

## 2. Design-Invarianten (harte Regeln)

Diese gelten dokumentübergreifend und dürfen von keiner Komponente verletzt werden.

| ID | Invariante |
|----|------------|
| **I-1** | **Datenquellen-Trennung.** `movedata.json`/`itemdata.json` (Mechanik & Semantik) werden aus Pokémon-Showdown-Daten (`@pkmn/dex`) generiert. `@smogon/calc` bleibt **ausschließlich** Damage-Quelle. |
| **I-2** | **Multi-turn condition rollout under fixed follow-up policy — not full multi-ply search.** Die Aktionswahl bleibt 1-Ply; nach dem gewählten Zug werden nur *Conditions* mehrere Züge vorwärtsgerollt, ohne Entscheidungsbaum beider Spieler. |
| **I-3** | **Effekte ändern den Zustand, nicht direkt den Score.** Der Wert eines Effekts entsteht **emergent** aus dem Werten des gerollten Zukunftszustands (KO/Schaden/Tempo) — nicht aus Condition-spezifischen Score-Konstanten. |
| **I-4** | **Rollout-Schaden ist bewusst approximiert.** Exakte Calc-Calls bleiben auf Zug 0 / prefetched tactical lines begrenzt. Der Rollout gilt nie als vollständige PS-Damage-Simulation. |
| **I-5** | **Keine Doppelzählung Calc ↔ State.** `@smogon/calc` berechnet *nur* Damage-Modifikation; ConditionEngine/Resolver aktualisiert *danach* den Zustand. Rollout-Modifikatoren sind **relativ** zum bereits gecalcten Ausgangszustand (Ratio-Modell, §6.2). |
| **I-6** | **Der Rollout erzeugt keine beliebigen neuen Damage-Calcs.** Nur der feste Prefetch-Satz wird gecalct; jeder gerollte Zug rechnet rein arithmetisch darauf. Bei Budgetüberschreitung Fallback auf `score_0`. |
| **I-7** | **Additivität.** Heuristik *ohne* Rollout und *mit* `Rollout(H=0)` liefern identische Entscheidungen. Rollout ist ein Bonus, kein Pflichtpfad. |

---

## 3. Architektur

Wir trennen *„was ein Move/Item mechanisch tut"* (auto-importiert) von *„was er der Heuristik wert ist"* (kuratierte Effekt-Klassen) und bewerten beides über eine **ConditionEngine**, die den Zustand mehrere Züge vorwärtsrollt.

### Bausteine

| Baustein | Datei (neu/geändert) | Aufgabe |
|----------|---------------------|---------|
| **Daten-Generator** | `tools/gen_movedata.mjs` (neu) | Liest `@pkmn/dex` → `movedata.json` + `itemdata.json` (mit Versions-Metadaten). |
| **Move-/Item-Rohdaten** | `config/moves/movedata.json`, `config/items/itemdata.json` (neu) | Eingecheckte Mechanik; Laufzeit braucht kein Node fürs Nachschlagen. |
| **Effekt-Klassen** | `config/moves/effect_classes.yaml`, `config/items/item_effect_classes.yaml` (neu) | Kuratierte Semantik-Schicht (`id → effect_class(es) + Parameter`). |
| **MoveMeta / ItemMeta** | `engine/moves.py` (geändert), `engine/items.py` (neu) | Laden Rohdaten + Effekt-Klassen, liefern angereicherte Metadaten. |
| **ConditionEngine** | `engine/conditions.py` (neu) | Modelliert alle v1-Conditions: Dauer, Abklingen, Residual, Stat-/Speed-/Aktions-Modifikatoren. Kern: `step(state) → state'`. |
| **Multi-Turn-Rollout** | `battle/rollout.py` (neu) | Rollt nach dem gewählten Zug H Züge unter fester Policy vorwärts, liefert Horizont-Wert + `RolloutTrace`. |

### Datenfluss pro Entscheidung

```
Request + Log
     │
     ▼
BattleState  ──(Conditions aus Log geseedet: sidestart/fieldstart/-status, Switch-in-Abilities)
     │
     ▼
enumerate_my_actions  ×  predict_responses                 (unverändert)
     │
     ▼
für jede Linie:
   resolve_turn          → Zug-1-Taktik (KO, Tempo, Protect, Redirect …)   (unverändert)
   Rollout über H Züge (feste Policy, ConditionEngine.step)                 (NEU)
     │
     ▼
score = score_0  +  Σ_{t=1..H} γ^t · score_t               (NEU)
     │
     ▼
pick_best  →  encode_choose                                (unverändert)
```

**Unverändert:** Die Entscheidungs-Schicht (`battle/decision.py`) wählt weiterhin 1-Ply die beste Joint-Action — nur der *Wert* einer Linie enthält jetzt den Rollout. Der Fallback-Chain (heuristic → max_damage → random → first legal) und das 4-s-Hardtimeout bleiben.

**Kernprinzip der Schichtung:** `movedata.json` = Mechanik · `effect_classes.yaml` = Semantik · `ConditionEngine` = wie Zustände sich entwickeln · `Rollout` = was sie wert sind. Jede Schicht ist einzeln testbar.

---

## 4. Move-Daten-Pipeline

### 4.1 Generator (`tools/gen_movedata.mjs`)

Quelle ist `@pkmn/dex` (kanonischer Mirror von PS `data/moves.ts` / `data/items.ts`), **nicht** `@smogon/calc` (Invariante I-1). Export pro Move: `id, name, basePower, category, type, priority, target, flags, secondary(s), volatileStatus, status, sideCondition, weather, terrain, boosts, self, drain, recoil, multihit, ...`. Analog für Items.

**Versions-Metadaten** im Kopf jeder generierten Datei:

```json
{
  "source_version": "<@pkmn/dex Version>",
  "generation": 9,
  "format": "gen9vgc2024regg",
  "data_hash": "<sha256 über den Datenblock>",
  "moves": { ... }
}
```

So ist später prüfbar, ob die Daten zu Showdown/Reg-G passen.

### 4.2 Effekt-Klassen (`config/moves/effect_classes.yaml`)

Kuratierte Zuordnung `move_id → [effect_class, …] + Parameter`. Jeder Move bekommt null bis mehrere Klassen. Klein, handgepflegt, Reg-G-priorisiert. Familien:

| Familie | Beispiele | Wirkung |
|---------|-----------|---------|
| `speed_control` | Tailwind, Trick Room, Icy Wind, Thunder Wave | Speed-Order im Rollout ändern |
| `status_infliction` | Will-O-Wisp, Spore, Nuzzle, Toxic | Status auf Ziel (→ ConditionEngine) |
| `setup_self` | Swords Dance, Nasty Plot, Dragon Dance, Calm Mind | Boosts auf User → höherer Rollout-Schaden |
| `debuff_foe` | Snarl, Parting Shot, Fake Tears | Boosts beim Gegner senken |
| `protect` | Protect, Spiky Shield, Wide/Quick Guard, King's Shield | Zug-1-Block + Folgeschaden (Spiky/Bulwark) |
| `redirect` | Follow Me, Rage Powder | Ziel umlenken (vorhanden) |
| `pivot` | U-turn, Volt Switch, Flip Turn, Parting Shot, Teleport | Schaden + Switch-out |
| `field_setter` | Wetter, Terrains, Reflect/Light Screen/Aurora Veil, Räume | Field/Side-Condition setzen |
| `disruption` | Taunt, Encore, Disable, Haze, Roar, Feint, Helping Hand | Gegner-Optionen/Boosts/Turn-Order beeinflussen |
| `recovery` | Recover, Roost, Wish, Drain-Moves, Leech Seed | Heilung über Zeit |
| `damage_modifier` | Multi-Hit, Recoil, Two-Turn, Fixed, Self-KO, Recharge | Resolver-/Rollout-Sonderpfad |
| `volatile_inflict` | Confuse Ray, Leech Seed, Substitute, Yawn | Volatile auf Ziel/Self |

Neue Klasse = ein YAML-Eintrag. Unklassifizierte Moves sind nicht *falsch* — sie haben dank Auto-Import korrekte Rohmechanik, nur (noch) keinen semantischen Bonus.

---

## 5. Items

Items sind eine dritte Datenquelle **parallel zu Moves** — kein neues Subsystem; sie klinken sich in bestehende Schichten ein.

### 5.1 Item-Effekt-Klassen

| Klasse | Beispiele | Wo behandelt |
|--------|-----------|--------------|
| `damage_stat` | Choice Band/Specs, Life Orb, Assault Vest, Eviolite, Gems | `@smogon/calc` |
| `speed` | Choice Scarf, Iron Ball | `SpeedOracle` |
| `residual_heal` | Leftovers, Black Sludge | ConditionEngine `on_residual` |
| `threshold_heal` | Sitrus Berry, Figy/Aguav | ConditionEngine (HP-Schwelle) |
| `status_cure` | Lum Berry, Persim | ConditionEngine `on_apply` |
| `activation_item / stat_overlay` | **Booster Energy** | Trigger bei Aktivierung → Stat-Overlay-Zustand (meist Speed), verbraucht |
| `pinch_trigger` | Weakness Policy, Focus Sash, Resist-Berries | Resolver/ConditionEngine-Trigger |
| `effect_block` (`apply_effect`-Hook) | Safety Goggles, Covert Cloak, Clear Amulet, Mental Herb | Effekt-/Resolver-Layer, **nicht** über Damage |
| `contact_punish` | Rocky Helmet | ConditionEngine/Resolver on-contact |

**`apply_effect`-Hooks im Detail:**

- **Safety Goggles** → blockt Powder/Spore/Rage-Powder-Wirkung.
- **Covert Cloak** → blockt Sekundäreffekte gegnerischer Moves.
- **Clear Amulet** → blockt Stat-Drops durch den Gegner.
- **Mental Herb** → heilt Taunt/Encore/Disable-artige Einschränkung einmalig.

### 5.2 Keine Doppelzählung (Invariante I-5)

`@smogon/calc` berechnet *nur* die Damage-Modifikation; State-Update passiert *danach*, nie beides für denselben Effekt:

| Item | Calc (Damage) | State *danach* |
|------|---------------|----------------|
| Life Orb | ×1.3 | Recoil −1/10 abziehen |
| Resist-Berry | ×0.5 | Berry als verbraucht markieren |
| Focus Sash | — | bei vollem HP Schaden auf 1 HP clampen, Sash verbraucht |
| Sitrus Berry | normal | bei HP-Schwelle Heilung + verbraucht |
| Choice Scarf | — | Speed via `SpeedOracle`; Choice-Lock = später Volatile |

### 5.3 Hidden Info / Belief

Items sind verdeckt. **Eigene** Items: voll modelliert (Request kennt sie). **Gegner**-Items: modelliert, sobald durch `|-item|`/`|-enditem|` aufgedeckt (macht `engine/state.py` bereits), oder via Item-Prior aus dem Belief-Layer.

> Unbekannte Gegner-Items werden grundsätzlich neutral behandelt, **außer** für wenige high-impact defensive/speed/disruption Items, die als Belief-Kandidaten mit geringer Prior-Wahrscheinlichkeit geführt werden: **Focus Sash, Choice Scarf, Booster Energy, Safety Goggles, Covert Cloak, Resist-Berries, Clear Amulet.**

So rennt der Bot nicht blind in Sash/Scarf/Goggles/Cloak-Lines, übergewichtet sie aber auch nicht. `PokemonState.item_known` steuert die Unterscheidung.

### 5.4 Verwandte Dimension: Abilities (v1 minimal)

Abilities folgen demselben Muster (verdeckt, datengetrieben). v1 modelliert nur die **zustandssetzenden** beim Switch-in, weil sie den ConditionEngine-Startzustand prägen: **Intimidate** (Atk-Drop) und Wetter/Terrain-Abilities (Drought, Drizzle, Sand Stream, Snow Warning, Grassy/Electric/Psychic/Misty Surge). Der Rest → später, gleiche Architektur.

---

## 6. Multi-Turn Condition Rollout

### 6.1 Feste Folgepolitik

Nach `resolve_turn` (Zug 0) wird der Zustand H Züge weitergerollt. Jeder lebende Mon nutzt pro gerolltem Zug eine **feste, billige Aktion**: bester **Damage-Move** vs. bestes Ziel, mit KO-Priorität (*max-damage-with-KO-priority / heuristic-lite*). Keine Switches, keine neuen Statuszüge, kein Protect im Rollout — der Rollout misst *Konsequenzen*, nicht neue Taktik.

### 6.2 Ratio-Modell für Rollout-Schaden (Invariante I-4, I-5)

`base_damage_0` enthält bereits den Ausgangszustand (Field/Weather/Terrain, ggf. Boosts), weil der `DamageOracle` ihn so calc't. Deshalb **Ratio statt absolut**:

```
rollout_damage_estimate = base_damage_0 × modifier_ratio(state_0 → state_t)
```

`modifier_ratio` ist das Produkt der Whitelist-Modifikatoren, jeweils als `effect(state_t) / effect(state_0)`:

| Whitelist-Modifikator | Greift nur wenn | Ratio-Beispiel |
|---|---|---|
| `boost_modifier` | User/Ziel-Boosts ändern sich | +2 Atk neu ⇒ ×2.0; unverändert ⇒ 1.0 |
| `burn_modifier` | Status=Burn **und** Kategorie=physisch | Burn neu ⇒ ×0.5; war schon ⇒ 1.0 |
| `screen_modifier(screen, game_type, category)` | passende Screen + Kategorie | Reflect läuft aus ⇒ inverser Effekt; neu ⇒ Effekt |
| `weather_modifier` | Move-Typ matcht Wetter, Angreifer nicht immun | Sonne+Feuer neu ⇒ ×1.5 |
| `terrain_modifier` | Angreifer geerdet + Typ matcht Terrain | Grassy+Grass neu ⇒ ×1.3 |
| `helping_hand_modifier` | HH diesen Zug aktiv | ×1.5 |

> **Screens nicht pauschal ×0.5:** `screen_modifier` ist eine Funktion. In Doubles reduzieren Reflect/Light Screen/Aurora Veil nur ~×2/3 (kategorieabhängig: Reflect→physisch, Light Screen→speziell, Aurora Veil→beide). Verhindert systematische Überbewertung von Screens.

Effekte **außerhalb** der Whitelist werden im Rollout **konservativ ignoriert** oder als qualitative Tempo-/Survival-Änderung gewertet — nie als Pseudo-Calc in Python nachgebaut. Unveränderte Effekte tragen Ratio 1.0 und fallen damit raus, sodass nichts doppelt gezählt wird.

### 6.3 `action_risk` als Erwartungswert (kein Sampling)

Conditions mit Handlungs-Risiko verzweigen **nicht**, sondern skalieren den Damage-Output des betroffenen Mons:

| Condition | Output-Skalierung |
|-----------|-------------------|
| Paralyse (25 % Full-Para) | ×0.75 |
| Schlaf | ×P(wach) gemäß Sleep-Counter |
| Confusion (33 % Selbsttreffer) | ×0.67 |
| Freeze | ×P(auftauen) |

So bleibt der Rollout eine einzige deterministische Linie (Erwartungswert), keine Wahrscheinlichkeits-Verzweigung — wichtig fürs Budget und für Determinismus.

### 6.4 Rollout-Loop (pro gerolltem Zug t)

```
1. Speed-Order  neu aus SpeedOracle           ← hier wirkt Tailwind/TR/Para/Scarf
2. Aktion/Mon  = feste Policy (bester Damage-Move vs. bestes Ziel, KO-Priorität)
3. Damage      = base_damage_0 × modifier_ratio(state_0 → state_t);  action_risk skaliert Output
4. Post-Damage-Trigger (strikt nach Damage, nie doppelt):
                 Sash-Clamp→1HP, Berry/Orb/Sitrus verbrauchen, Sitrus-Heal, Orb-Recoil
5. ConditionEngine.step():  Residuals (Wetter/Burn/Tox/Leech/Leftovers), Dauern −1, Expiry
6. score_t = score_outcome(Deltas dieses Zuges)     ← gleiche Währung wie Zug 0
```

### 6.5 Horizont-Wert

```
V = score_0  +  Σ_{t=1..H}  γ^t · score_t
```

Default **H = 2**, **γ = 0.7**. H = 3 ist experimentell (budget-abhängig). Kein Condition-Sonderkonstant: Tailwind/Burn/Screens/Setup bekommen ihren Wert **nur** dadurch, dass `score_t` in den gerollten Zügen mehr/weniger KOs, Schaden und Tempo sieht (Invariante I-3).

**Emergenz-Beispiele:**

- **Tailwind:** `step()` hält Speed ×2 → `SpeedOracle` dreht Order → fester KO landet *vor* dem Gegner → erscheint als `ko`/`tempo_prevent` in Zug t.
- **Will-O-Wisp auf Physiker:** Ratio ×0.5 Atk → halbierter gerollter Schaden gegen uns + Burn-Chip-Residual → weniger `dmg_taken`, mehr `dmg_dealt`.
- **Swords Dance:** +2 Atk im Zustand → höhere `boost_modifier`-Ratio → mehr KOs im Rollout.
- **Screens:** eingehender gerollter Schaden ×2/3 (Doubles) → weniger `dmg_taken` über H Züge.

### 6.6 Budget (Invariante I-6)

```
RolloutBudget:
  max_rollout_horizon           = 2   (3 experimentell)
  max_followup_actions_per_side = 2
  max_rollout_damage_pairs      = fixer Prefetch-Satz (kein Wachstum über H)
  max_rollout_ms                = ~500 ms (im äußeren Decision-Budget)
  → bei Überschreitung: return score_0 only
```

**Prefetch deckt den Rollout mit ab:** Die feste Policy nutzt einen kleinen, vorhersehbaren Satz Paare (bester Move jedes Mons × jedes lebende Ziel). Diese werden zur bestehenden `DamageModel.prefetch`-Batch hinzugefügt → **ein** Node-Roundtrip wie heute. Über H Züge wachsen die Paare nicht; nur die Ratios ändern sich.

### 6.7 `RolloutTrace` (Debuggbarkeit)

Der Rollout gibt eine **JSON-serialisierbare** Zeitleiste zurück (pro Zug: aktive Conditions, Speed-Order, HP-Deltas, KOs, `score_t`). Erfüllt das Phase-2-Exitkriterium „debuggable turns" und erlaubt, schlechte Entscheidungen als Golden Fixtures zu speichern. Auf Debug-Level geloggt.

---

## 7. ConditionEngine

### 7.1 Drei Scopes

- **Pokémon:** Major-Status (brn/par/slp[Züge]/psn/tox[Stufe]/frz), Volatiles (confusion[Züge], leechseed, substitute[HP], taunt, encore, disable, yawn, two-turn/charge, roost), Boosts (vorhanden).
- **Side:** tailwind[Z], reflect/lightscreen/auroraveil[Z], safeguard, mist, wide/quick guard + redirection (Zug-1).
- **Field:** weather[Z], terrain[Z], trickroom[Z], gravity.

### 7.2 Einheitlicher Descriptor

Gleiche Form für jede Condition → einzeln testbar:

```
ConditionDescriptor:
  scope:        pokemon | side | field
  duration:     int | None          # None = bis geheilt (Major-Status)
  on_residual:  HP-Delta/Zug         # Burn −1/16, Tox eskalierend, Leech-Seed-Transfer, Wetter-Chip, Leftovers, Grassy-Heal
  stat_mod:     mult. Modifikator    # Burn ×0.5 Atk, Para ×0.5 Spe, Tailwind ×2 Spe, Screen via screen_modifier
  action_risk:  P(kann nicht handeln) # Schlaf/Freeze/Full-Para/Confusion → Erwartungswert im Rollout
  on_apply:     Hook (z.B. Lum/Mental-Herb-Heilung)
  on_expire:    Cleanup
```

### 7.3 `step(state) → state'` Reihenfolge

Showdown-nahe Residual-Reihenfolge (vereinfacht):

1. Field-Dauern ↓ & Wetter-Chip → Expiry
2. Side-Dauern ↓ (Tailwind, Screens, Safeguard) → Expiry
3. Status/Volatile-Residuals nach Speed-Order (Burn, Tox, Leech Seed, Ingrain/Aqua Ring, Grassy-Heal, Leftovers)
4. Volatile-Dauern ↓ (Confusion, Taunt, Encore, Disable, Yawn→Schlaf) → Expiry/Trigger
5. Zug-1-Volatiles zurücksetzen (Flinch, Protect, Wide Guard, Redirection)

### 7.4 v1-Condition-Set

**v1 unbedingt:** Major-Status burn/paralysis/sleep/poison/toxic (*freeze optional, geringer ROI*) · Tailwind · Trick Room · Screens/Aurora Veil · Terrain · Weather · Setup (Swords Dance, Nasty Plot, Dragon Dance, Calm Mind) · Debuff (Snarl, Icy Wind, Parting Shot, Intimidate-Switch) · Protect-Familie · Redirection · Pivot · Helping Hand · Taunt · Haze · Encore · Spore/Sleep Powder · Leech Seed.

**Später (Long Tail):** Perish Song, Instruct, After You, Quash, Wonder/Magic Room, Hazards, exotische Volatiles, breite Ability-Modellierung.

---

## 8. State-Erweiterungen & Belief-Integration

- `PokemonState`: Volatile-Dict + Condition-Dauern; `consumed_item`-Flag fürs Rollout-Item-Tracking.
- `FieldState`: Screens (reflect/lightscreen/auroraveil[Z]), trickroom[Z], gravity, Weather/Terrain mit Restdauer.
- Side-Conditions als eigene Struktur (tailwind/safeguard/mist + Dauern).
- **Seeding aus Log:** Dauern werden aus `|-sidestart|`, `|-fieldstart|`, `|-weather|`, `|-status|` sowie Switch-in-Abilities (Intimidate/Wetter/Terrain) initialisiert, wo bekannt; sonst aus Default-Dauer.
- Gegner-Boosts/Items/Conditions speisen sich aus dem bestehenden Belief-Layer (`engine/belief/`), inkl. der high-impact Item-Belief-Kandidaten (§5.3).

---

## 9. Scoring-Integration

`evaluate_line` (in `battle/evaluate.py`) gibt künftig `V = score_0 + Σ γ^t · score_t` zurück. `score_outcome` und die `EvalWeights` bleiben die *einzige* Wert-Währung (KO/faint/dmg/tempo/protect/speed_control) — über alle gerollten Züge hinweg angewandt. Es kommen **keine** neuen Condition-Score-Konstanten hinzu (Invariante I-3).

**Einzige dokumentierte Ausnahme:** rein disruptive Effekte, die die feste Folgepolitik strukturell nicht „nutzen" kann (z.B. Taunt schaltet einen Move ab, den die simple Policy ohnehin nicht wählt), bekommen einen *kleinen, explizit markierten* Prior. Bewusst minimal gehalten und in `effect_classes.yaml` als solcher gekennzeichnet.

---

## 10. Datei-Impact

| Datei | Art | Inhalt |
|---|---|---|
| `tools/gen_movedata.mjs` | neu | Generator `@pkmn/dex` → `movedata.json` + `itemdata.json` (mit Versions-Metadaten) |
| `config/moves/movedata.json`, `config/items/itemdata.json` | neu | Eingecheckte Roh-Mechanik |
| `config/moves/effect_classes.yaml`, `config/items/item_effect_classes.yaml` | neu | Kuratierte Semantik |
| `engine/moves.py` | geändert | lädt JSON+YAML, erweitertes `MoveMeta`; 25er-Handtabelle entfällt |
| `engine/items.py` | neu | `ItemMeta` + Item-Effekt-Klassen |
| `engine/conditions.py` | neu | `ConditionEngine`, `ConditionDescriptor`, `step()` |
| `engine/state.py` | geändert | Volatiles + Dauern (Pokémon/Side/Field), Seeding aus Log |
| `engine/speed.py` | geändert | Scarf/Tailwind/TR/Para speisen Per-Zug-Speed-Recompute |
| `battle/rollout.py` | neu | Rollout-Loop, `RolloutBudget`, feste Policy, `rollout_damage_estimate` + Whitelist, `RolloutTrace` |
| `battle/evaluate.py` | geändert | `evaluate_line` → `score_0 + Σγ^t·score_t`; Prefetch um Rollout-Paare erweitert |
| `battle/decision.py` | geändert | minimal: Linienwert enthält jetzt Horizont |

---

## 11. Tests

**ConditionEngine-Unit:** Burn −1/16, Tox-Eskalation, Tailwind expired nach 4, Screens-Decay, Leech-Seed-Transfer, Sleep-Counter, Wetter-Chip+Expiry, `screen_modifier`-Doubles-Werte.

**Item-Unit:** Sitrus-Schwelle+Verbrauch, Sash-Clamp+Verbrauch, Life-Orb-Recoil *nach* Damage (keine Doppelzählung), Goggles blockt Spore, Covert Cloak blockt Sekundär, Mental Herb heilt Taunt.

**Rollout:**
- *Determinismus:* gleicher Input → gleiche `RolloutTrace` (kein RNG); `action_risk`-Skalierung exakt.
- *No-new-calcs-Garantie:* Assertion, dass der Rollout **0** zusätzliche Oracle-Requests über den Prefetch-Satz hinaus erzeugt.
- *Budget-Fallback:* Budgetüberschreitung → `score_0 only`.
- *Ratio-Korrektheit:* state_0 == state_t ⇒ `modifier_ratio == 1.0` (kein Doppelzählen).

**Daten-Integrität:**
- `test_generated_data_is_fresh`: Generator laufen lassen, **kein Diff** zu eingecheckten JSONs.
- YAML-Schema-Test: jede `move_id`/`item_id` existiert in den Rohdaten, jede `effect_class` bekannt, Required-Params vorhanden, keine unbekannten Felder (fängt `speed_controll`).

**Regression / Additivität:**
- Bestehende Zug-1-Tests (`test_resolve.py`, `test_baselines.py`, `test_decision_replay.py`) bleiben grün.
- **Additivitäts-Beweis:** Heuristik ohne Rollout und mit `Rollout(H=0)` liefern identische Entscheidungen (Invariante I-7).

**Golden-Replay:** `test_decision_replay.py` um condition-entscheidende Reg-G-Turns erweitern (Will-O auf Physiker, Tailwind ermöglicht KO, Sash-Survival).

---

## 12. Erfolgskriterien

1. **Mechanik korrekt:** ConditionEngine reproduziert Residual/Dauer für das v1-Set vs. handverifizierte Fälle.
2. **Kein Calc-Blowup:** Rollout = 0 zusätzliche Node-Roundtrips über den einen Prefetch-Flush; Entscheidung bei H=2 unter dem 4-s-Budget.
3. **Verhalten (Kernmetrik):** Auf einer kuratierten Suite condition-entscheidender Turns wählt der Bot den condition-bewussten Zug, wo Zug-1-Scoring naiv Max-Damage wählte. Konkret muss der Bot zeigen:
   - Will-O-Wisp auf physischen Angreifer schlägt stumpfen Schaden.
   - Tailwind ist gut, *wenn* daraus konkrete First-Move-KOs entstehen.
   - Focus Sash wird respektiert.
   - Screens werden **nicht** pauschal überbewertet.
   - Taunt/Encore/Haze haben nur Wert, wenn sie relevante Linien verhindern.
4. **Live/Ladder ist kein Gate dieses Specs.** Optionaler Smoke-Indikator: keine Regression gegenüber der aktuellen Phase-2-Heuristik in lokalen Gauntlets und privaten Testkämpfen.

---

## 13. Zukünftige Erweiterungen

- **Tiefe-2-Suche:** `ConditionEngine.step` ist exakt das Übergangsmodell, das eine spätere echte 2-Ply-Suche bräuchte — additiv, kein verlorener Aufwand.
- **Breite Ability-Modellierung** (über Switch-in-Setter hinaus), gleiche Datenpipeline wie Items.
- **Long-Tail-Conditions:** Perish Song, Instruct/After You/Quash, Wonder/Magic Room, Hazards.
- **Choice-Lock als Volatile** (Scarf/Band/Specs-Move-Lock im Rollout).

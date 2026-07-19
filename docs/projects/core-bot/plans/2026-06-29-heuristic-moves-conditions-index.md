# HeuristicBot Move-Effekt- & Condition-System — Plan-Index

> **For agentic workers:** Implementiere phasenweise. Jede Phase produziert eigenständig getestete Software. REQUIRED SUB-SKILL beim Ausführen: `superpowers:executing-plans` (inline) — Subagenten nur, wenn der User es ausdrücklich will.

**Spec:** `docs/projects/core-bot/specs/2026-06-29-heuristic-moves-conditions-design.md`

**Goal:** Den Ein-Ply-HeuristicBot von 25 handcodierten Moves auf datengetriebene Move-/Item-/Condition-Abdeckung mit Multi-Turn-Condition-Rollout heben (Reg G priorisiert).

**Architektur:** Drei Schichten — (1) auto-importierte Rohmechanik aus `@pkmn/dex`, (2) kuratierte Effekt-Klassen, (3) `ConditionEngine` + `Rollout`, die den Wert emergent aus dem gerollten Zukunftszustand ableiten. `@smogon/calc` bleibt Damage-only.

**Tech Stack:** Python 3.11+ (pydantic, PyYAML, pytest), Node `@pkmn/dex`/`@pkmn/data` (build-time Generator), bestehendes `@smogon/calc`-Bridge.

---

## Verifizierte Vorbedingungen (vor dem Planen geprüft)

- Test-Baseline grün: **147 Tests** (`cd showdown_bot && python -m pytest -q`).
- `@smogon/calc`-Move-Daten haben **keine** Semantik-Felder → als Semantik-Quelle ungeeignet (bestätigt).
- `@pkmn/dex` installiert + verifiziert: liefert `status/volatileStatus/sideCondition/weather/terrain/boosts/secondary/flags/priority/target` für 954 Moves, 583 Items.
- Constraint: 17 uncommittete Phase-2-Dateien des Users im Arbeitsbaum; **`engine/state.py` und `battle/decision.py` darunter** → Phase C (Integration) zuletzt, vorsichtig.

---

## Phasen

| Phase | Plan | Liefert | Berührt User-Dateien? | Exit |
|-------|------|---------|----------------------|------|
| **A — Daten-Pipeline** | `2026-06-29-phaseA-move-item-data-pipeline.md` | Generator + `movedata.json`/`itemdata.json` + angereichertes `MoveMeta` + `ItemMeta` + kuratierte `effect_classes.yaml`/`item_effect_classes.yaml` | nein | `get_move_meta` liefert reiche Daten für alle 954 Moves; 147 Alt-Tests grün; Freshness-/Schema-Tests grün |
| **B — ConditionEngine** | `2026-06-29-phaseB-condition-engine.md` (folgt) | `engine/conditions.py` (`ConditionDescriptor`, `ConditionEngine.step`), State-Erweiterungen für **neue** Strukturen | minimal (nur additive Felder) | Residual/Dauer/Stat-Mods für v1-Set vs. handverifizierte Fälle korrekt; deterministisch |
| **C — Rollout & Integration** | `2026-06-29-phaseC-rollout-integration.md` (folgt) | `battle/rollout.py` (Ratio-Modell, `RolloutBudget`, `RolloutTrace`), `evaluate.py`-Scoring, Wiring in `decision.py` | **ja** (`state.py`, `decision.py`, `evaluate.py`, `speed.py`) | `Rollout(H=0)` == ohne Rollout (Additivität); No-new-calcs-Assertion; condition-entscheidende Golden-Turns |

**Ausführungsreihenfolge:** A → B → C. A und B berühren die uncommitteten User-Dateien nicht und werden autonom umgesetzt. C wartet idealerweise, bis der User seine offenen Änderungen committet hat (sonst Verheddern); bis dahin werden Cs neue Module (rollout.py) standalone gebaut und nur das Wiring zurückgehalten.

---

## Locked Decisions (aus Spec)

- Datenquelle: `@pkmn/dex` (Semantik) + `@smogon/calc` (Damage). [I-1]
- Rollout = condition-only, fixed follow-up policy, kein Multi-Ply-Baum. [I-2]
- Effekte ändern State, nicht direkt Score (emergenter Wert). [I-3]
- Rollout-Schaden approximiert via **Ratio-Modell** `base_damage_0 × modifier_ratio(state_0→state_t)`. [I-4, I-5]
- Keine neuen Calcs im Rollout; hartes Budget. [I-6]
- Additivität: `Rollout(H=0)` == ohne Rollout. [I-7]

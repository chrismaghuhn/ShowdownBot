# Phase B — ConditionEngine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` (inline). TDD per step.

**Goal:** Eine entkoppelte `ConditionEngine`, die alle v1-Conditions mit Dauer, Abklingen (Residual), Stat-/Speed-Mods und `action_risk` korrekt modelliert — testbar in Isolation, ohne `state.py` zu berühren.

**Architecture:** Eigene `ConditionState` (mons/sides/field) + `ConditionDescriptor`-Registry. `step(cstate, hp)` wendet Residuals an, dekrementiert Dauern, liefert `ResidualEvent`-Liste (für `RolloutTrace` in Phase C). Phase C komponiert `ConditionState` in `BattleState` und seedet aus dem Log.

**Entkopplung (wichtig):** `step` nimmt eine `hp: dict[(side,slot)->float]` und mutiert sie; Major-Status liegt in `MonConditions.status`. Keine Abhängigkeit von `PokemonState`/`BattleState` → Phase B fasst die uncommitteten User-Dateien nicht an.

---

### Task B1: ConditionState + ConditionDescriptor + Major-Status-Residuals

**Files:** Create `engine/conditions.py`, `tests/test_conditions.py`

Datenmodell:
```python
SlotId = tuple[str, str]

@dataclass
class ConditionInstance:
    name: str
    duration: int | None        # remaining turns; None = until cured/removed
    params: dict = field(default_factory=dict)

@dataclass
class MonConditions:
    status: str | None = None   # brn|par|slp|psn|tox|frz
    status_counter: int = 0     # toxic stage / sleep turns remaining
    volatiles: dict[str, ConditionInstance] = field(default_factory=dict)

@dataclass
class ConditionState:
    mons: dict[SlotId, MonConditions] = field(default_factory=dict)
    sides: dict[str, dict[str, ConditionInstance]] = field(default_factory=dict)
    field: dict[str, ConditionInstance] = field(default_factory=dict)

@dataclass
class ResidualEvent:
    key: SlotId
    source: str          # "brn" | "psn" | "tox" | "leechseed" | "sand" | "grassyterrain" | "leftovers"
    delta: float         # HP fraction change (negative = damage)
```

TDD-Schritte:
- [ ] **B1.1 RED** `test_burn_residual_chips_one_sixteenth`: ConditionState mit `mons[("p1","a")].status="brn"`, `hp={("p1","a"):1.0}`; nach `step` ist `hp` ~0.9375, Event `source=="brn"`.
- [ ] **B1.2 GREEN** minimal: `STATUS_RESIDUAL = {"brn": -1/16, "psn": -1/8}`; `step` iteriert `mons`, zieht ab, klemmt bei 0, sammelt Events.
- [ ] **B1.3 RED** `test_toxic_escalates`: `status="tox"`, `status_counter=1` → -1/16; nach step counter=2; erneuter step → -2/16.
- [ ] **B1.4 GREEN** Tox-Sonderfall (counter-basiert, inkrementiert in step).
- [ ] **B1.5 Commit** `feat(conditions): ConditionState + major-status residuals`.

### Task B2: Dauern + Side/Field-Conditions + Expiry

- [ ] **B2.1 RED** `test_tailwind_expires_after_4`: `sides["p1"]["tailwind"]=ConditionInstance("tailwind",4)`; 4×step → noch da am Ende des 4., danach entfernt. (Showdown: gesetzt-Turn zählt; 4 volle Züge.)
- [ ] **B2.2 GREEN** Dauer-Dekrement + Entfernen bei 0 für sides/field.
- [ ] **B2.3 RED** `test_sand_chips_non_immune` / `test_grassy_heals_grounded`: field weather/terrain Residual über `hp`. (Immunität/Grounded vorerst per param-Flag am Aufrufer; v1 hält es simpel.)
- [ ] **B2.4 GREEN** Wetter/Terrain-Residual.
- [ ] **B2.5 RED** `test_leech_seed_transfers`: leechseed-Volatile zieht -1/8 vom Ziel; Event `source=="leechseed"`.
- [ ] **B2.6 GREEN** + **Commit** `feat(conditions): durations, side/field conditions, leech seed`.

### Task B3: Modifier-Abfragen (stat/speed/action_risk) — read-only

- [ ] **B3.1 RED** `test_modifiers`: `speed_multiplier(cstate, ("p1","a"))` == 2.0 bei Tailwind, 0.5 bei Para; `atk_multiplier` 0.5 bei Burn; `action_act_probability` 0.75 bei Para, 0.0 bei Schlaf.
- [ ] **B3.2 GREEN** reine Query-Funktionen über `ConditionState` (kein Mutieren). Diese liefern Phase C die Ratio-Bausteine (Tailwind→Speed-Order, Burn→Damage-Ratio).
- [ ] **B3.3 Commit** `feat(conditions): stat/speed/action_risk query API`.

### Task B4: Determinismus + step-Reihenfolge

- [ ] **B4.1 RED** `test_step_is_deterministic`: zweimal gleicher Input → gleiche Events/HP.
- [ ] **B4.2 RED** `test_step_order`: field vor side vor mon-Residual (Spec §7.3).
- [ ] **B4.3 GREEN/Refactor** Reihenfolge fixieren. **Commit**.

## Phase-B-Exit
- v1-Condition-Mechanik (Residual/Dauer/Mods) vs. handverifizierte Fälle korrekt; deterministisch; `state.py` unangetastet; volle Suite grün.

# Phase 3 Slice 1c-A: `apply_outcome_to_state` + state clone — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The foundational simulator primitive — clone a `BattleState` and apply a
`TurnOutcome` (+ the turn's actions/roster) to produce the next `BattleState`, applying
ONLY what the outcome encodes. Pure, deterministic, no Node.

**Architecture:** New `learning/simulator.py` (depends on `battle/`/`engine/` types;
`learning → battle`, allowed). `clone_state` = `deepcopy`. `apply_outcome_to_state`
applies HP/faint, field (only `resolve_turn`-emitted status flags), and switches (via an
authoritative `roster_by_side`, fail-fast on a missing target, deep-copy on switch-in).
No end-of-turn simulation. The H-loop/decide/limited-view are 1c-B/C/D.

**Tech Stack:** Python stdlib (`copy`). Spec:
`docs/projects/core-bot/specs/2026-06-30-1c-simulator-design.md`. Types:
`engine/state.py` (`BattleState`, `PokemonState` — `hp_fraction` is a *property* `hp/max_hp`;
`FieldState` — `weather/terrain/trick_room/tailwind`), `battle/resolve.py` (`TurnOutcome` —
`hp_delta` fraction `[-1,1]`, `flags: set`, `my_kos/my_faints`), `battle/actions.py`
(`JointAction.slot0/slot1`), `models/actions.py` (`SlotAction.kind/target_ident`). Run
tests from `showdown_bot/`.

---

## File Structure
- Create: `src/showdown_bot/learning/simulator.py`.
- Test: `tests/test_simulator.py`.

## Pinned facts (from the spec, verified in source)
- `hp_delta` is a **fraction** `[-1.0, 1.0]` (`resolve.py:311`). Apply once:
  `new_frac = clamp(cur_frac + delta, 0, 1)`.
- `PokemonState.hp_fraction` is a **derived property** (`hp/max_hp`); update `mon.hp`. If
  `max_hp is None`, set synthetic `max_hp = 100` first.
- Faint = `new_frac <= 0` (there is no explicit per-mon faint flag; `resolve` only *counts*
  faints).
- Field flags are `status:<move_id>:<owner>` (`resolve.py:259`), `owner` = `side+slot`
  (e.g. `p1a`). v1 supports `tailwind`, `trickroom`; unknown move_ids ignored.
- `actions_by_side: dict[str, JointAction]`; `slot0`↔`"a"`, `slot1`↔`"b"`; only
  `kind=="switch"` switches.

---

## Task 1: `clone_state` + skeleton + no-input-mutation

**Files:** Create `src/showdown_bot/learning/simulator.py`; Test `tests/test_simulator.py`.

- [ ] **Step 1: failing tests**

```python
# tests/test_simulator.py
import copy
from showdown_bot.engine.state import BattleState, PokemonState, FieldState
from showdown_bot.battle.resolve import TurnOutcome
from showdown_bot.learning.simulator import clone_state, apply_outcome_to_state


def _state():
    s = BattleState()
    s.sides["p1"] = {"a": PokemonState(species="Incineroar", hp=200, max_hp=200)}
    s.sides["p2"] = {"a": PokemonState(species="Flutter Mane", hp=100, max_hp=100)}
    return s


def test_clone_is_deep_and_independent():
    s = _state()
    c = clone_state(s)
    c.sides["p1"]["a"].hp = 1
    assert s.sides["p1"]["a"].hp == 200          # original untouched


def test_apply_returns_new_state_and_does_not_mutate_input():
    s = _state()
    before = copy.deepcopy(s)
    out = TurnOutcome()
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt is not s
    # input unchanged (deep compare on the mutated fields)
    assert s.sides["p1"]["a"].hp == before.sides["p1"]["a"].hp
    assert s.sides["p2"]["a"].hp == before.sides["p2"]["a"].hp
```

- [ ] **Step 2: run → FAIL.** `cd showdown_bot && python -m pytest tests/test_simulator.py -q`

- [ ] **Step 3: implement the skeleton**

```python
"""Internal turn-simulator primitive (Phase 3 slice 1c-A).

clone_state + apply_outcome_to_state: produce the next BattleState from a resolved
TurnOutcome + the turn's actions/roster. Applies ONLY what the outcome encodes — no
end-of-turn simulation (no residual/weather-chip/status-tick/duration/PP/item, no forced
replacement). The H-loop/decide/limited-view are slices 1c-B/C/D.
"""

from __future__ import annotations

import copy

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.resolve import TurnOutcome
from showdown_bot.engine.state import BattleState

_SLOTS = ("a", "b")


def clone_state(state: BattleState) -> BattleState:
    return copy.deepcopy(state)


def apply_outcome_to_state(
    state: BattleState, outcome: TurnOutcome, actions_by_side: dict[str, JointAction],
    *, roster_by_side: dict,
) -> BattleState:
    """Return a NEW BattleState; never mutate the input. (HP/field/switch filled in
    Tasks 2-4.)"""
    nxt = clone_state(state)
    return nxt
```

- [ ] **Step 4: run → PASS** + full suite (+2). **Step 5: commit** `feat(learning): simulator clone_state + apply skeleton (no input mutation)`.

---

## Task 2: HP / faint application

**Files:** Modify `simulator.py`; Test `tests/test_simulator.py`.

- [ ] **Step 1: failing tests**

```python
def test_hp_delta_fraction_applied_and_clamped():
    s = _state()  # p1a hp 200/200 (1.0), p2a 100/100 (1.0)
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40, ("p1", "a"): -0.25})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert abs(nxt.sides["p2"]["a"].hp_fraction - 0.60) < 1e-9   # 1.0 - 0.40
    assert nxt.sides["p2"]["a"].hp == 60
    assert abs(nxt.sides["p1"]["a"].hp_fraction - 0.75) < 1e-9   # 1.0 - 0.25

def test_hp_unit_075_minus_040():
    s = _state()
    s.sides["p2"]["a"].hp = 75  # 0.75 of 100
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.sides["p2"]["a"].hp == 35                          # 0.75 -> 0.35

def test_hp_clamp_and_faint():
    s = _state()
    out = TurnOutcome(hp_delta={("p2", "a"): -1.5})   # over-kill clamps to 0 + faint
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.sides["p2"]["a"].hp == 0 and nxt.sides["p2"]["a"].fainted is True

def test_hp_synthetic_maxhp_when_unknown():
    s = _state()
    s.sides["p2"]["a"].max_hp = None   # unrevealed -> synthetic 100
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.sides["p2"]["a"].max_hp == 100
    assert abs(nxt.sides["p2"]["a"].hp_fraction - 0.60) < 1e-9
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement `_apply_hp` + call it in `apply_outcome_to_state` (after clone)**

```python
def _apply_hp(state: BattleState, outcome: TurnOutcome) -> None:
    for (side, slot), delta in outcome.hp_delta.items():
        mon = state.sides.get(side, {}).get(slot)
        if mon is None:
            continue
        if mon.max_hp is None:
            mon.max_hp = 100  # synthetic denominator so the fraction is representable (v1)
        new_frac = max(0.0, min(1.0, mon.hp_fraction + delta))
        mon.hp = round(new_frac * mon.max_hp)
        if new_frac <= 0.0:
            mon.fainted = True
```
Call `_apply_hp(nxt, outcome)` in `apply_outcome_to_state`.

- [ ] **Step 4: run → PASS** + full suite (+4). **Step 5: commit** `feat(learning): simulator HP/faint application (fractional delta, clamp, synthetic max_hp)`.

---

## Task 3: field flag application + unknown ignored

**Files:** Modify `simulator.py`; Test `tests/test_simulator.py`.

- [ ] **Step 1: failing tests**

```python
def test_field_tailwind_and_trickroom():
    s = _state()
    out = TurnOutcome(flags={"status:tailwind:p1a", "status:trickroom:p2a"})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert nxt.field.tailwind["p1"] is True
    assert nxt.field.trick_room is True            # toggled on from default False

def test_unknown_flag_is_ignored():
    s = _state()
    out = TurnOutcome(flags={"status:bogusmove:p1a", "wasted_move", "protect:p1a"})
    nxt = apply_outcome_to_state(s, out, {}, roster_by_side={})   # no crash
    assert nxt.field.tailwind["p1"] is False and nxt.field.trick_room is False
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement `_apply_field` + call it**

```python
def _apply_field(state: BattleState, outcome: TurnOutcome) -> None:
    for flag in outcome.flags:
        parts = flag.split(":")
        if parts[0] != "status" or len(parts) != 3:
            continue
        move_id, owner = parts[1], parts[2]
        side = owner[:2]   # "p1a" -> "p1"
        if move_id == "tailwind":
            state.field.tailwind[side] = True
        elif move_id == "trickroom":
            state.field.trick_room = not state.field.trick_room
        # any other move_id: ignored (no invented weather/terrain parsing in 1c-A)
```
Call `_apply_field(nxt, outcome)` (after HP).

- [ ] **Step 4: run → PASS** + full suite (+2). **Step 5: commit** `feat(learning): simulator field-flag application (tailwind/trickroom, unknown ignored)`.

---

## Task 4: switch application + no aliasing + missing-target error

**Files:** Modify `simulator.py`; Test `tests/test_simulator.py`.

- [ ] **Step 1: failing tests**

```python
import pytest
from showdown_bot.battle.actions import JointAction
from showdown_bot.models.actions import SlotAction


def test_switch_replaces_active_slot_from_roster():
    s = _state()
    bench = PokemonState(species="Rillaboom", hp=180, max_hp=180, moved_since_switch=True)
    roster = {"p1": {"p1: Rillaboom": bench}}
    ja = JointAction(slot0=SlotAction(kind="switch", target_ident="p1: Rillaboom"),
                     slot1=SlotAction(kind="pass"))
    nxt = apply_outcome_to_state(s, TurnOutcome(), {"p1": ja}, roster_by_side=roster)
    assert nxt.sides["p1"]["a"].species == "Rillaboom"
    assert nxt.sides["p1"]["a"].moved_since_switch is False   # reset on switch-in

def test_switch_does_not_alias_roster():
    s = _state()
    bench = PokemonState(species="Rillaboom", hp=180, max_hp=180)
    roster = {"p1": {"p1: Rillaboom": bench}}
    ja = JointAction(slot0=SlotAction(kind="switch", target_ident="p1: Rillaboom"),
                     slot1=SlotAction(kind="pass"))
    nxt = apply_outcome_to_state(s, TurnOutcome(), {"p1": ja}, roster_by_side=roster)
    nxt.sides["p1"]["a"].hp = 1
    assert bench.hp == 180                                    # roster entry untouched

def test_switch_missing_target_raises():
    s = _state()
    ja = JointAction(slot0=SlotAction(kind="switch", target_ident="p1: Nope"),
                     slot1=SlotAction(kind="pass"))
    with pytest.raises(ValueError, match="not in roster"):
        apply_outcome_to_state(s, TurnOutcome(), {"p1": ja}, roster_by_side={"p1": {}})
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement `_apply_switches` + call it**

```python
def _apply_switches(state, outcome, actions_by_side, roster_by_side) -> None:
    for side, ja in actions_by_side.items():
        for i, sa in enumerate((ja.slot0, ja.slot1)):
            if sa.kind != "switch":
                continue
            slot = _SLOTS[i]
            target = sa.target_ident
            roster = roster_by_side.get(side, {})
            if target not in roster:
                raise ValueError(f"switch target {target!r} not in roster for side {side!r}")
            new_mon = copy.deepcopy(roster[target])   # no shared ref with the roster
            new_mon.moved_since_switch = False
            state.sides.setdefault(side, {})[slot] = new_mon
```
Call `_apply_switches(nxt, outcome, actions_by_side, roster_by_side)` AFTER `_apply_hp`
(HP hits the pre-switch occupant; the switched-in mon keeps its roster HP — the leaving
mon's HP change is not tracked in v1, documented). Field after switches is fine (field is
slot-independent).

- [ ] **Step 4: run → PASS** + full suite (+3). **Step 5: commit** `feat(learning): simulator switch application (authoritative roster, no aliasing, fail-fast)`.

---

## Task 5: determinism + full-primitive integration

**Files:** Test `tests/test_simulator.py` (no new impl — proves the assembled primitive).

- [ ] **Step 1: tests**

```python
def test_determinism_same_inputs_same_next_state():
    s = _state()
    out = TurnOutcome(hp_delta={("p2", "a"): -0.40}, flags={"status:tailwind:p1a"})
    a = apply_outcome_to_state(s, out, {}, roster_by_side={})
    b = apply_outcome_to_state(s, out, {}, roster_by_side={})
    assert a.sides["p2"]["a"].hp == b.sides["p2"]["a"].hp
    assert a.field.tailwind["p1"] == b.field.tailwind["p1"]

def test_combined_hp_field_switch_one_turn():
    s = _state()
    bench = PokemonState(species="Landorus-Therian", hp=180, max_hp=180)
    roster = {"p2": {"p2: Landorus": bench}}
    ja_p2 = JointAction(slot0=SlotAction(kind="switch", target_ident="p2: Landorus"),
                        slot1=SlotAction(kind="pass"))
    out = TurnOutcome(hp_delta={("p1", "a"): -0.30}, flags={"status:trickroom:p1a"})
    nxt = apply_outcome_to_state(s, out, {"p2": ja_p2}, roster_by_side=roster)
    assert abs(nxt.sides["p1"]["a"].hp_fraction - 0.70) < 1e-9   # our mon took damage
    assert nxt.sides["p2"]["a"].species == "Landorus-Therian"     # opp switched (via roster)
    assert nxt.field.trick_room is True
```

- [ ] **Step 2: run → PASS** + full suite (+2). **Step 5: commit** `test(learning): simulator determinism + combined HP/field/switch primitive`.

---

## Self-Review notes
- **Spec coverage:** clone + no-mutation (T1); HP unit/clamp/faint/synthetic-max_hp (T2);
  field tailwind/trickroom + unknown-ignored (T3); switch roster/no-alias/fail-fast (T4);
  determinism + combined (T5). All 8 spec tests present.
- **Apply order:** clone → HP → switches → field. HP hits the pre-switch occupant; switch
  then replaces it (v1: leaving mon's HP change not tracked). Field is slot-independent.
- **No end-of-turn sim** (residual/weather-chip/status-tick/duration/PP/item/forced-
  replacement) — only what `TurnOutcome` encodes.
- **Deferred:** state-driven `decide` (1c-B), H-loop teacher wiring (1c-C), roster
  source + opponent belief + limited-view safety (1c-D).

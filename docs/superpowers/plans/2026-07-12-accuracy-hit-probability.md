# Accuracy / Hit-Probability-Weighted Move Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `resolve_turn`/`evaluate_line`'s implicit always-hit assumption with a
probability-weighted hit/miss model, so risky moves are no longer scored as guaranteed to connect.

**Architecture:** A generated `accuracy` field flows from `@pkmn/dex` through `movedata.json` into
`MoveMeta`. A new `hit_probability()` function (base accuracy + boost stages + two pinned weather
rules) feeds a recursive branch-and-fork resolver (`resolve_turn_branches`) that re-discovers newly
revealed accuracy events after every partial resolve — not a one-shot fixed event list, which was
proven wrong for KO-order-dependent lines. `resolve_turn_branches` also records, per fork on the
path to the all-hit leaf, that fork's miss-sibling subtree — needed for `miss_punish_value` (§7).
`evaluate_line` gains an off-by-default `accuracy_mode`/`accuracy_branch_cap` pair of parameters;
`battle/decision.py` computes both once per decision and threads them into every `evaluate_line`
call site that participates in that same live decision (ranking, tera-overlay, report, trace) —
not just the two that feed the ranking — so the report/trace/tera outputs never silently show a
legacy-scored line for a decision that was actually accuracy-aware.

**Tech Stack:** Python 3 (dataclasses), pytest, Node.js (`@pkmn/dex`) for the data generator.

**Spec:** `docs/superpowers/specs/2026-07-12-accuracy-hit-probability-design.md` — read it before
starting; this plan implements it section by section (§2→Task 1, §3→Task 2, §4→Task 3,
§5→Task 4, §6/§9→Task 5, §7→Task 6, §8→Task 7, §10/§11→Task 8/9).

**Scope note (Task 5), revised after plan review:** `evaluate_line` is called from 8 sites inside
`battle/decision.py`'s `_choose_best_ja`/`_maybe_tera` — all 8 belong to the SAME live decision
(candidate ranking, the K-world/+Sampling ranking variant, the depth-2 turn-1 frontier score, the
tera-overlay re-score that can directly overwrite the chosen action, the human-readable report
line, and the `DecisionTrace` breakdown that becomes training data). All 8 get the same
`accuracy_mode`/`accuracy_branch_cap` values, computed once per call to `_choose_best_ja` — an
earlier draft of this plan wired only 2 of the 8 and left the rest silently on legacy scoring,
which would have made the tera-decision accuracy-blind (a live decision bug, not a reporting
cosmetic) and let `DecisionTrace`'s exported breakdown mismatch the score that actually ranked the
candidates (a training-data integrity bug). The ONE deliberate boundary that remains: `depth2_value`
(`battle/search.py`, Depth-2's turn-2 backup evaluation) is untouched — that is explicitly out of
scope per spec §12 ("Depth-2 Stage 3" is a separate, later slice), and this plan does not reach
into `search.py`.

---

### Task 1: Generator `accuracy` field + `MoveMeta.accuracy`

**Files:**
- Modify: `showdown_bot/tools/gen/gen_movedata.mjs:34-60` (`moveRecord`)
- Modify: `showdown_bot/src/showdown_bot/engine/moves.py:34-145` (`MoveMeta`, `_meta_from_record`, `_move_table`)
- Regenerate: `showdown_bot/config/moves/movedata.json`
- Test: `showdown_bot/tests/test_moves.py`

- [ ] **Step 1: Write the failing Python tests for `MoveMeta.accuracy` and the fail-closed loader**

Append to `showdown_bot/tests/test_moves.py`:

```python
def test_movedata_has_accuracy_for_every_move():
    import json
    from pathlib import Path
    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "config" / "moves" / "movedata.json")
        .read_text(encoding="utf-8")
    )
    for mid, rec in raw["moves"].items():
        assert "accuracy" in rec, f"{mid} missing accuracy key"


def test_thunder_and_hurricane_base_accuracy_is_70():
    assert get_move_meta("Thunder").accuracy == 70
    assert get_move_meta("Hurricane").accuracy == 70


def test_always_hit_move_accuracy_is_none():
    # Swift/Aura Sphere are @pkmn/dex accuracy===true moves -> normalized to null/None.
    assert get_move_meta("Swift").accuracy is None
    assert get_move_meta("Aura Sphere").accuracy is None


def test_move_table_raises_on_record_missing_accuracy_key(monkeypatch, tmp_path):
    import json
    from showdown_bot.engine import moves as moves_mod

    bad = {
        "source_version": "x", "generation": 9, "format": "f", "data_hash": "h",
        "moves": {"tackle": {"id": "tackle", "name": "Tackle", "category": "Physical",
                              "basePower": 40, "target": "normal"}},  # no "accuracy" key
    }
    bad_path = tmp_path / "movedata.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(moves_mod, "_MOVEDATA", bad_path)
    moves_mod._move_table.cache_clear()
    try:
        with pytest.raises(KeyError):
            moves_mod._move_table()
    finally:
        moves_mod._move_table.cache_clear()
```

Add `import pytest` to the top of `showdown_bot/tests/test_moves.py` if not already present (check
the existing imports first — the current file only imports from `showdown_bot.engine.moves`/`.state`).

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_moves.py -v -k "accuracy or move_table_raises"`
Expected: `test_movedata_has_accuracy_for_every_move` and the base-accuracy tests FAIL with
`KeyError` or `AttributeError: 'MoveMeta' object has no attribute 'accuracy'` (field doesn't exist
yet); `test_move_table_raises_on_record_missing_accuracy_key` FAILS because `_move_table()` doesn't
currently raise (it uses `.get()` everywhere).

- [ ] **Step 3: Add the fail-closed `accuracy` field to the generator**

In `showdown_bot/tools/gen/gen_movedata.mjs`, add this function above `moveRecord` (after the
existing `hasFlinch` function, before line 34):

```js
// resolve.py's hit_probability() distinguishes "no accuracy field at all" (data error) from
// "accuracy is the normalized always-hit sentinel" (legitimate null). @pkmn/dex represents
// always-hit moves as accuracy===true; everything else is a number 1-100. A move with
// accuracy===undefined would silently collapse into the null case if we didn't check first,
// hiding a real @pkmn/dex data gap as a fully legitimate "this move can't miss".
function accuracyRecord(m) {
  if (m.accuracy === undefined) {
    throw new Error(`move ${m.id} has no accuracy field from @pkmn/dex`);
  }
  return m.accuracy === true ? null : m.accuracy;
}
```

Then add `accuracy: accuracyRecord(m),` as a new line inside the `moveRecord` function's returned
object, immediately after the existing `name: m.name,` line (so the object reads
`id`, `name`, `accuracy`, `basePower`, ... — insert it right after `name`).

- [ ] **Step 4: Regenerate `movedata.json`**

Run:
```bash
cd "showdown_bot/tools/gen"
node gen_movedata.mjs
```
Expected output: `wrote <N> moves, <M> items` (N/M match the current checked-in counts — this is a
regeneration, not a move-list change).

Verify the regenerated file is internally consistent:
```bash
node gen_movedata.mjs --check
```
Expected: `fresh` (exit 0).

- [ ] **Step 5: Add `accuracy` to `MoveMeta` and fix the loader to fail closed**

In `showdown_bot/src/showdown_bot/engine/moves.py`, add `accuracy: int | None = None` to the
`MoveMeta` dataclass (`moves.py:34-70`) — insert it right after the `base_power: int = 0` line so
it sits with the other mechanical fields (before `move_type`):

```python
    base_power: int = 0
    accuracy: int | None = None
    move_type: str | None = None
```

In `_meta_from_record` (`moves.py:84-107`), replace the `id=rec["id"],` / `name=rec["name"],`
opening with an explicit presence check, and add the `accuracy=` line:

```python
def _meta_from_record(rec: dict) -> MoveMeta:
    if "accuracy" not in rec:
        raise KeyError(f"move record {rec.get('id', '<unknown>')} is missing 'accuracy' — "
                        f"regenerate movedata.json (tools/gen/gen_movedata.mjs)")
    return MoveMeta(
        id=rec["id"],
        name=rec["name"],
        priority=int(rec.get("priority") or 0),
        category=(rec.get("category") or "Physical").lower(),
        target=rec.get("target") or "normal",
        base_power=int(rec.get("basePower") or 0),
        accuracy=rec["accuracy"],
        move_type=rec.get("type"),
        flags=frozenset(rec.get("flags") or ()),
        terrain_priority=_TERRAIN_PRIORITY.get(rec["id"]),
        status=rec.get("status"),
        volatile_status=rec.get("volatileStatus"),
        side_condition=rec.get("sideCondition"),
        slot_condition=rec.get("slotCondition"),
        weather=rec.get("weather"),
        terrain=rec.get("terrain"),
        boosts=rec.get("boosts"),
        self_effect=rec.get("self"),
        secondary=rec.get("secondary"),
        drain=_tuple(rec.get("drain")),
        recoil=_tuple(rec.get("recoil")),
        multihit=_tuple(rec.get("multihit")),
    )
```

This raises `KeyError` (caught and asserted with `pytest.raises(KeyError)` in Step 1's test)
whenever a record lacks the key — `_meta_from_record` is called once per move inside `_move_table`
(`moves.py:119-134`), so a single bad record fails the whole table load, which is the intended
fail-closed behavior (no silent per-move default).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_moves.py -v`
Expected: all tests PASS, including the 4 new ones.

- [ ] **Step 7: Run the full existing test suite to check for regressions**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, same count as before this task (adding a field with a default doesn't change any
existing `MoveMeta`-equality-sensitive test, since `accuracy` is excluded from neither `compare`
nor `hash` by default — check this: the dataclass is `frozen=True` with no explicit
`field(compare=False)` on `accuracy`, so `accuracy` DOES participate in `MoveMeta.__eq__`/`__hash__`
via the default dataclass behavior. If any existing test constructs a `MoveMeta` by hand and
compares it to `get_move_meta(...)`'s result, it will now need an explicit `accuracy=` to match —
if Step 7 turns up such a failure, fix the failing test's manual `MoveMeta(...)` construction to
include the correct `accuracy=` value rather than loosening the dataclass's equality semantics.)

- [ ] **Step 8: Commit**

```bash
git add showdown_bot/tools/gen/gen_movedata.mjs showdown_bot/config/moves/movedata.json \
        showdown_bot/src/showdown_bot/engine/moves.py showdown_bot/tests/test_moves.py
git commit -m "feat(accuracy): generate + load move accuracy, fail closed on missing field"
```

---

### Task 2: `hit_probability()` core function

**Files:**
- Modify: `showdown_bot/src/showdown_bot/engine/moves.py`
- Test: `showdown_bot/tests/test_moves.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_moves.py`:

```python
from showdown_bot.engine.state import PokemonState


def _mon(**boosts):
    m = PokemonState(species="Test", hp=100, max_hp=100)
    m.boosts.update(boosts)
    return m


def test_hit_probability_always_hit_move_is_none():
    swift = get_move_meta("Swift")
    assert hit_probability(swift, _mon(), _mon(), FieldState()) is None


def test_hit_probability_base_accuracy_no_stages():
    thunder = get_move_meta("Thunder")  # accuracy 70
    p = hit_probability(thunder, _mon(), _mon(), FieldState())
    assert abs(p - 0.70) < 1e-9


def test_hit_probability_positive_accuracy_stage_raises_it():
    thunder = get_move_meta("Thunder")
    p = hit_probability(thunder, _mon(accuracy=1), _mon(), FieldState())
    assert abs(p - 0.93) < 1e-9  # int(70 * 4/3) / 100 = int(93.33)/100 = 0.93


def test_hit_probability_negative_evasion_stage_raises_it():
    # Target evasion DOWN raises the attacker's effective hit chance (stage = acc - evasion,
    # so evasion=-1 contributes the same +1 as attacker accuracy=+1 would).
    thunder = get_move_meta("Thunder")
    p = hit_probability(thunder, _mon(), _mon(evasion=-1), FieldState())
    assert abs(p - 0.93) < 1e-9  # int(70 * 4/3)/100 == same formula as the accuracy=+1 case


def test_hit_probability_stage_clamped_at_plus_six():
    # A low-accuracy synthetic move so the clamp is provably at the BOOST-STAGE level, not
    # just masked by the final [0,1] probability clamp: at stage=6 (3x multiplier) 30 accuracy
    # gives 0.90, well under 1.0 -- an unclamped stage=9 (4x multiplier) would give 1.0, a
    # different value, so this distinguishes "stage clamped to 6" from "stage never clamped".
    low_acc = MoveMeta(id="lowacc", name="LowAcc", accuracy=30, base_power=100,
                        category="physical", target="normal")
    p_six = hit_probability(low_acc, _mon(accuracy=6), _mon(), FieldState())
    p_beyond = hit_probability(low_acc, _mon(accuracy=9), _mon(), FieldState())
    assert abs(p_six - 0.90) < 1e-9
    assert p_six == p_beyond  # clamp(9) == clamp(6)


def test_hit_probability_blizzard_guaranteed_in_snow():
    blizzard = get_move_meta("Blizzard")
    assert hit_probability(blizzard, _mon(), _mon(), FieldState(weather="Snow")) is None


def test_hit_probability_blizzard_not_guaranteed_outside_snow():
    blizzard = get_move_meta("Blizzard")
    p = hit_probability(blizzard, _mon(), _mon(), FieldState(weather="Sandstorm"))
    assert p is not None
    assert abs(p - (blizzard.accuracy / 100.0)) < 1e-9


def test_hit_probability_thunder_guaranteed_in_rain_stage_independent():
    thunder = get_move_meta("Thunder")
    p_no_stage = hit_probability(thunder, _mon(), _mon(), FieldState(weather="RainDance"))
    p_with_stage = hit_probability(thunder, _mon(), _mon(evasion=4), FieldState(weather="RainDance"))
    assert p_no_stage is None and p_with_stage is None  # unconditional, stage never applies


def test_hit_probability_thunder_sun_reduces_to_50_then_applies_stages():
    # Pinned against sim/battle-actions.ts:709-722 at the pinned commit
    # (config/eval/provenance.yaml): sun sets move.accuracy=50, a PLAIN NUMBER that then
    # goes through the SAME stage-multiplier pipeline as any base accuracy — not a flat 0.5.
    thunder = get_move_meta("Thunder")
    p_no_stage = hit_probability(thunder, _mon(), _mon(), FieldState(weather="SunnyDay"))
    assert abs(p_no_stage - 0.50) < 1e-9
    p_with_stage = hit_probability(thunder, _mon(accuracy=2), _mon(), FieldState(weather="SunnyDay"))
    assert abs(p_with_stage - 0.83) < 1e-9  # trunc(50 * 5/3)/100 = trunc(83.33)/100 = 0.83
    assert p_with_stage != 0.50  # the exact bug the earlier design got wrong


def test_hit_probability_clamped_to_one_when_stage_pushes_above_100():
    tackle_like = get_move_meta("Tackle")  # accuracy 100
    p = hit_probability(tackle_like, _mon(accuracy=6), _mon(), FieldState())
    assert p == 1.0
```

Add the necessary imports to the top of `showdown_bot/tests/test_moves.py`:

```python
from showdown_bot.engine.moves import MoveMeta, get_move_meta, hit_probability
from showdown_bot.engine.state import FieldState
```
(merge with the existing import lines rather than duplicating them — `get_move_meta` is already
imported by the current file, so only add `MoveMeta` and `hit_probability` to that line.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_moves.py -v -k hit_probability`
Expected: FAIL with `ImportError: cannot import name 'hit_probability'`.

- [ ] **Step 3: Implement `hit_probability`**

In `showdown_bot/src/showdown_bot/engine/moves.py`, add `PokemonState` to the existing state
import (line 11) and add the function after `move_priority` (after `moves.py:154-159`, before
`blocks_move`):

```python
from showdown_bot.engine.state import FieldState, PokemonState
```

```python
def hit_probability(
    meta: MoveMeta, attacker: PokemonState, target: PokemonState, field: FieldState | None,
) -> float | None:
    """Probability this move connects. ``None`` means unconditionally guaranteed to hit
    (no branching needed): either ``meta.accuracy is None`` (the normalized @pkmn/dex
    always-hit sentinel) or a weather rule that bypasses the stage pipeline entirely
    (Blizzard in Snow, Thunder/Hurricane in Rain).

    v1 scope only: base accuracy, accuracy/evasion boost stages, and exactly the two weather
    rules below -- verified against the pinned pokemon-showdown server commit
    (config/eval/provenance.yaml), not assumed. Ability/item/field modifiers beyond these are
    a documented v1.1 limitation (spec Sec.3), not silently ignored.
    """
    if meta.accuracy is None:
        return None
    weather = (field.weather or "").lower() if field is not None else ""
    base = meta.accuracy
    if meta.id in ("thunder", "hurricane"):
        if "rain" in weather:
            return None  # move.accuracy = true in PS -> stage pipeline bypassed entirely
        if "sun" in weather:
            base = 50  # move.accuracy = 50 in PS -> a NUMBER, still goes through stages below
    elif meta.id == "blizzard" and "snow" in weather:
        return None
    acc_stage = max(-6, min(6, attacker.boosts.get("accuracy", 0)))
    stage = max(-6, min(6, acc_stage - target.boosts.get("evasion", 0)))
    if stage > 0:
        raw = base * (3 + stage) / 3
    elif stage < 0:
        raw = base * 3 / (3 - stage)
    else:
        raw = base
    p = int(raw) / 100.0  # sim/battle-actions.ts truncates the intermediate accuracy to an int
    return max(0.0, min(1.0, p))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_moves.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/moves.py showdown_bot/tests/test_moves.py
git commit -m "feat(accuracy): hit_probability() with base/stage/weather rules, pinned to real PS mechanics"
```

---

### Task 3: `forced_miss`, `apply_hit` ordering, new `TurnOutcome` fields

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/resolve.py`
- Test: `showdown_bot/tests/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_resolve.py`:

```python
def test_attempted_hits_recorded_even_with_no_forced_miss():
    st = _state()
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out = resolve_turn(st, [atk], dmg, our_side="p1")
    assert len(out.attempted_hits) == 1
    assert out.attempted_hits[0].attacker == ("p1", "a")
    assert out.attempted_hits[0].target == ("p2", "a")
    assert out.missed_hits == []


def test_forced_miss_prevents_damage_and_records_missed_hit():
    st = _state()
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out = resolve_turn(
        st, [atk], dmg, our_side="p1", forced_miss=frozenset({(("p1", "a"), ("p2", "a"))}),
    )
    assert out.hp_delta[("p2", "a")] == 0.0
    assert len(out.missed_hits) == 1
    assert out.missed_hits[0] == MissedHit(("p1", "a"), ("p2", "a"), moon.id)


def test_forced_miss_default_is_todays_exact_behavior():
    st = _state()
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out_default = resolve_turn(st, [atk], dmg, our_side="p1")
    out_explicit_empty = resolve_turn(st, [atk], dmg, our_side="p1", forced_miss=frozenset())
    assert out_default.hp_delta == out_explicit_empty.hp_delta


def test_protect_blocked_hit_not_reclassified_as_missed_even_if_also_forced_miss():
    st = _state()
    protect = get_move_meta("Protect")
    moon = get_move_meta("Moonblast")
    prot = PlannedAction("p1", "a", "protect", speed=50, move=protect, is_ours=True)
    atk = PlannedAction("p2", "a", "move", speed=200, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 0.8

    out = resolve_turn(
        st, [prot, atk], dmg, our_side="p1",
        forced_miss=frozenset({(("p2", "a"), ("p1", "a"))}),
    )
    assert len(out.protected_hits) == 1
    assert out.missed_hits == []  # protect check comes first; never reaches the miss check


def test_spread_move_partial_forced_miss_hits_one_target_misses_other():
    st = _doubles_state()
    eq = get_move_meta("Earthquake")
    atk = PlannedAction("p1", "a", "move", speed=100, move=eq, is_ours=True)
    others = [
        PlannedAction("p1", "b", "pass", speed=1, is_ours=True),
        PlannedAction("p2", "a", "pass", speed=1, is_ours=False),
        PlannedAction("p2", "b", "pass", speed=1, is_ours=False),
    ]

    def dmg(action, target):
        return 0.3

    out = resolve_turn(
        st, [atk] + others, dmg, our_side="p1",
        forced_miss=frozenset({(("p1", "a"), ("p2", "a"))}),
    )
    assert out.hp_delta[("p2", "a")] == 0.0  # forced miss
    assert out.hp_delta[("p2", "b")] < 0.0   # still hit
    assert len(out.missed_hits) == 1
    assert len(out.attempted_hits) == 2  # both targets attempted, one missed
```

Add `MissedHit` to the existing import from `showdown_bot.battle.resolve` at the top of
`showdown_bot/tests/test_resolve.py` (currently `from showdown_bot.battle.resolve import
PlannedAction, resolve_turn, sort_actions` — extend it).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_resolve.py -v -k "forced_miss or attempted_hits or protect_blocked_hit_not_reclassified or spread_move_partial"`
Expected: FAIL with `ImportError: cannot import name 'MissedHit'` and/or
`TypeError: resolve_turn() got an unexpected keyword argument 'forced_miss'`.

- [ ] **Step 3: Add `AttemptedHit`/`MissedHit` dataclasses and the new `TurnOutcome` fields**

In `showdown_bot/src/showdown_bot/battle/resolve.py`, add two new dataclasses right after
`RedirectedHit` (`resolve.py:56-61`):

```python
@dataclass
class AttemptedHit:
    attacker: SlotId
    target: SlotId
    move_id: str


@dataclass
class MissedHit:
    attacker: SlotId
    target: SlotId
    move_id: str
```

Add two new fields to `TurnOutcome` (`resolve.py:72-85`), after `redirected_hits`:

```python
    redirected_hits: list[RedirectedHit] = field(default_factory=list)
    attempted_hits: list[AttemptedHit] = field(default_factory=list)
    missed_hits: list[MissedHit] = field(default_factory=list)
```

- [ ] **Step 4: Add `forced_miss` to `resolve_turn` and wire it into `apply_hit`**

In `showdown_bot/src/showdown_bot/battle/resolve.py`, add the new keyword-only parameter to
`resolve_turn`'s signature (`resolve.py:118-126`):

```python
def resolve_turn(
    state: BattleState,
    actions: list[PlannedAction],
    damage_fn: DamageFn,
    *,
    our_side: str = "p1",
    field: FieldState | None = None,
    tie_break: str = "ours_last",
    forced_miss: frozenset[tuple[SlotId, SlotId]] = frozenset(),
) -> TurnOutcome:
```

Modify `apply_hit` (`resolve.py:173-186`) to insert the new bookkeeping and miss check right after
the existing `tgt_mon is None` guard, before the existing damage computation:

```python
    def apply_hit(attacker_key: SlotId, attacker_action: PlannedAction, tgt_key: SlotId, spread: bool) -> None:
        move = attacker_action.move
        if tgt_key in protected and blocks_move(move, field):
            outcome.protected_hits.append(ProtectedHit(attacker_key, tgt_key, move.id))
            return
        tgt_mon = state.sides.get(tgt_key[0], {}).get(tgt_key[1])
        if tgt_mon is None:
            return
        outcome.attempted_hits.append(AttemptedHit(attacker_key, tgt_key, move.id))
        if (attacker_key, tgt_key) in forced_miss:
            outcome.missed_hits.append(MissedHit(attacker_key, tgt_key, move.id))
            return
        act_for_dmg = (
            attacker_action
            if attacker_action.target == tgt_key
            else replace(attacker_action, target=tgt_key)
        )
        dealt = max(0.0, float(damage_fn(act_for_dmg, tgt_mon)))
```

(The rest of `apply_hit`'s body — everything from `dealt = ...` onward — is unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_resolve.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full suite**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, no regressions (the new fields default to empty lists, and `forced_miss` defaults
to an empty frozenset, so every existing call site is unaffected).

- [ ] **Step 7: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/resolve.py showdown_bot/tests/test_resolve.py
git commit -m "feat(accuracy): forced_miss plumbing in resolve_turn/apply_hit, attempted/missed hit tracking"
```

---

### Task 4: `resolve_turn_branches` — recursive accuracy expansion (core piece)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/resolve.py`
- Test: `showdown_bot/tests/test_resolve.py`

This is the highest-risk task in the plan — it fixes a real correctness bug an earlier revision of
the design had (a fixed, one-shot "discover events from a single all-hit run" approach silently
treats KO-order-dependent events as always-hit). Read spec §5 in full before starting.

- [ ] **Step 1: Write the regression test FIRST** (this is the test that would have caught the bug)

Append to `showdown_bot/tests/test_resolve.py`:

```python
from showdown_bot.battle.resolve import resolve_turn_branches
from showdown_bot.engine.moves import MoveMeta


def test_resolve_turn_branches_discovers_ko_dependent_event():
    """Regression test: X's uncertain move KOs slower Y in the all-hit run, so Y never
    reaches apply_hit there and Y's own uncertain move is invisible to any event list
    built from that run alone. The recursive expansion must discover it in the branch
    where X's move misses and Y survives to act."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Fast", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Slow", hp=100, max_hp=100)
    x_move = MoveMeta(id="xmove", name="X", accuracy=70, base_power=100,
                       category="physical", target="normal")
    y_move = MoveMeta(id="ymove", name="Y", accuracy=50, base_power=100,
                       category="physical", target="normal")
    x = PlannedAction("p1", "a", "move", speed=200, move=x_move, target=("p2", "a"), is_ours=True)
    y = PlannedAction("p2", "a", "move", speed=50, move=y_move, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 1.0  # any hit is lethal

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [x, y], dmg, our_side="p1", field=FieldState(), tie_break="ours_last", branch_cap=8,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 3  # X-hit (Y never acts); X-miss+Y-hit; X-miss+Y-miss
    total_weight = sum(w for w, _ in leaves)
    assert abs(total_weight - 1.0) < 1e-9

    x_hit_weight, x_hit_out = leaves[0]  # depth-first hit-first -> leaves[0] is the all-hit leaf
    assert abs(x_hit_weight - 0.7) < 1e-9
    assert x_hit_out.opp_kos == 1
    assert not any(ah.attacker == ("p2", "a") for ah in x_hit_out.attempted_hits)

    # The other two leaves are exactly the event a one-shot discovery pass would have missed:
    # Y surviving X's miss and taking its OWN uncertain-accuracy action.
    for w, out in leaves[1:]:
        assert any(ah.attacker == ("p2", "a") for ah in out.attempted_hits)
    remaining_weight = sum(w for w, _ in leaves[1:])
    assert abs(remaining_weight - 0.3) < 1e-9

    # fork_records: exactly one fork lies on the path to leaves[0] (X's pair). Its recorded
    # miss-sibling subtree must be exactly leaves[1:] (the two branches where X missed) --
    # this is the structure miss_punish_value (Task 6, spec Sec.7) depends on.
    assert len(fork_records) == 1
    fork_pair, miss_subtree = fork_records[0]
    assert fork_pair == (("p1", "a"), ("p2", "a"))
    assert len(miss_subtree) == 2
    assert abs(sum(w for w, _ in miss_subtree) - 0.3) < 1e-9


def test_resolve_turn_branches_all_hit_leaf_when_no_uncertainty():
    st = _state()
    swift = get_move_meta("Swift")  # always-hit
    atk = PlannedAction("p1", "a", "move", speed=100, move=swift, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.3

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [atk], dmg, our_side="p1", field=FieldState(), tie_break="ours_last", branch_cap=4,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 1
    assert abs(leaves[0][0] - 1.0) < 1e-9
    assert fork_records == []  # no uncertainty -> no fork points at all


def test_resolve_turn_branches_two_independent_events_four_leaves():
    st = _doubles_state()
    m1 = MoveMeta(id="m1", name="M1", accuracy=60, base_power=100, category="physical", target="normal")
    m2 = MoveMeta(id="m2", name="M2", accuracy=40, base_power=100, category="physical", target="normal")
    a1 = PlannedAction("p1", "a", "move", speed=150, move=m1, target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=m2, target=("p2", "b"), is_ours=True)
    others = [
        PlannedAction("p2", "a", "pass", speed=1, is_ours=False),
        PlannedAction("p2", "b", "pass", speed=1, is_ours=False),
    ]

    def dmg(action, target):
        return 0.1  # non-lethal -> both events are independent, no KO interaction

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [a1, a2] + others, dmg, our_side="p1", field=FieldState(), tie_break="ours_last",
        branch_cap=8,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 4
    total = sum(w for w, _ in leaves)
    assert abs(total - 1.0) < 1e-9
    weights = sorted(round(w, 6) for w, _ in leaves)
    expected = sorted(round(w, 6) for w in
                       [0.6 * 0.4, 0.6 * 0.6, 0.4 * 0.4, 0.4 * 0.6])
    assert weights == expected


def test_resolve_turn_branches_cap_produces_per_branch_fallback_not_whole_line():
    st = _doubles_state()
    # Four independent uncertain events (2 per side) -> a cap of 2 forces exactly one fork,
    # so at least one leaf must stop expanding early while its sibling still resolves fully.
    moves = [MoveMeta(id=f"u{i}", name=f"U{i}", accuracy=50, base_power=100,
                       category="physical", target="normal") for i in range(2)]
    a1 = PlannedAction("p1", "a", "move", speed=150, move=moves[0], target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=moves[1], target=("p2", "b"), is_ours=True)
    others = [
        PlannedAction("p2", "a", "pass", speed=1, is_ours=False),
        PlannedAction("p2", "b", "pass", speed=1, is_ours=False),
    ]

    def dmg(action, target):
        return 0.1

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [a1, a2] + others, dmg, our_side="p1", field=FieldState(), tie_break="ours_last",
        branch_cap=2,
    )
    assert fallback_leaves >= 1  # at least one path exhausted the cap before fully resolving
    total = sum(w for w, _ in leaves)
    assert abs(total - 1.0) < 1e-9  # weight is still fully conserved despite the cap
    # fork_records only ever records forks that were actually reached and split before the cap
    # fired -- each one's miss-sibling subtree is non-empty with positive total weight.
    for _pair, miss_subtree in fork_records:
        assert len(miss_subtree) >= 1
        assert sum(w for w, _ in miss_subtree) > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_resolve.py -v -k resolve_turn_branches`
Expected: FAIL with `ImportError: cannot import name 'resolve_turn_branches'`.

- [ ] **Step 3: Implement `resolve_turn_branches`**

In `showdown_bot/src/showdown_bot/battle/resolve.py`, add `hit_probability` to the existing import
from `engine.moves` (line 6):

```python
from showdown_bot.engine.moves import MoveMeta, blocks_move, can_redirect, hit_probability, move_priority
```

Add the new function after `resolve_turn` (after `resolve.py`'s final `return outcome` line, i.e.
at the end of the file):

```python
ForkRecord = tuple[tuple[SlotId, SlotId], list[tuple[float, TurnOutcome]]]


def resolve_turn_branches(
    state: BattleState,
    actions: list[PlannedAction],
    damage_fn: DamageFn,
    *,
    our_side: str = "p1",
    field: FieldState | None = None,
    tie_break: str = "ours_last",
    branch_cap: int = 4,
) -> tuple[list[tuple[float, TurnOutcome]], int, list[ForkRecord]]:
    """Recursively fork ``resolve_turn`` on genuinely uncertain accuracy events, re-discovering
    newly-revealed events after every partial resolve (spec Sec.5).

    A fixed, one-shot "discover events from a single all-hit resolve_turn call" list is WRONG
    whenever a hit/miss outcome changes who gets to act at all (KO-before-act) or who gets
    targeted (redirection): an action that never reaches ``apply_hit`` in one branch's resolve
    is invisible to a list built from that branch alone, so a sibling branch that revives it
    would otherwise be silently scored as if that action always hits.

    Returns ``(leaves, fallback_leaves, fork_records)``:

    - ``leaves``: a probability-weighted list of ``(weight, TurnOutcome)`` pairs whose weights
      sum to 1.0 exactly; ``leaves[0]`` is always the fully-resolved "everything hits" leaf
      (hit-branches are explored before miss-branches, and recursion is depth-first).
    - ``fallback_leaves``: how many recursion paths hit ``branch_cap`` before fully resolving --
      each such leaf keeps its own remaining pending events implicitly hit (today's legacy
      resolution), affecting only that specific subtree.
    - ``fork_records``: for every fork point encountered ON THE PATH TO ``leaves[0]`` (i.e. while
      every earlier decision along the way was the "hit" side), the ``(pair, miss_subtree)`` pair
      where ``miss_subtree`` is that fork's own miss-sibling's full leaf list. This is exactly
      the input ``miss_punish_value`` (spec Sec.7) needs -- the tree structure a flat leaf list
      alone cannot reconstruct after the fact.
    """
    actions_by_key = {a.key: a for a in actions}
    calls = 0
    fallback_leaves = 0
    fork_records: list[ForkRecord] = []

    def expand(miss_set, decided_hit, weight, on_hit_path):
        nonlocal calls, fallback_leaves
        calls += 1
        out = resolve_turn(
            state, actions, damage_fn, our_side=our_side, field=field,
            tie_break=tie_break, forced_miss=miss_set,
        )
        decided = miss_set | decided_hit
        pending: list[tuple[tuple[SlotId, SlotId], float]] = []
        for ah in out.attempted_hits:
            pair = (ah.attacker, ah.target)
            if pair in decided:
                continue
            attacker_action = actions_by_key.get(ah.attacker)
            if attacker_action is None or attacker_action.move is None:
                continue
            attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
            target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
            if attacker_mon is None or target_mon is None:
                continue
            p = hit_probability(attacker_action.move, attacker_mon, target_mon, field)
            if p is not None and 0.0 < p < 1.0:
                pending.append((pair, p))
        if not pending:
            return [(weight, out)]
        if calls >= branch_cap:
            fallback_leaves += 1
            return [(weight, out)]
        pair, p = pending[0]  # deterministic: first attempted-hit order
        hit_leaves = expand(miss_set, decided_hit | {pair}, weight * p, on_hit_path)
        miss_leaves = expand(miss_set | {pair}, decided_hit, weight * (1.0 - p), False)
        if on_hit_path:
            fork_records.append((pair, miss_leaves))
        return hit_leaves + miss_leaves

    leaves = expand(frozenset(), frozenset(), 1.0, True)
    return leaves, fallback_leaves, fork_records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_resolve.py -v`
Expected: all PASS, including all 4 `resolve_turn_branches` tests.

- [ ] **Step 5: Run the full suite**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, no regressions (this is a wholly new function; nothing calls it yet).

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/resolve.py showdown_bot/tests/test_resolve.py
git commit -m "feat(accuracy): resolve_turn_branches recursive expansion, KO-dependent-event regression test"
```

---

### Task 5: `evaluate_line` integration + `SHOWDOWN_ACCURACY_MODE`/`SHOWDOWN_ACCURACY_BRANCH_CAP`

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/evaluate.py`
- Modify: `showdown_bot/src/showdown_bot/battle/decision.py`
- Modify: `showdown_bot/src/showdown_bot/eval/config_env.py`
- Test: `showdown_bot/tests/test_evaluate.py`
- Test: `showdown_bot/tests/test_config_env.py`

- [ ] **Step 1: Write the failing tests for `evaluate_line`'s new parameters**

Append to `showdown_bot/tests/test_evaluate.py`:

```python
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.moves import MoveMeta
from showdown_bot.engine.state import BattleState, PokemonState


def _doubles_state_for_eval():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    return st


def test_evaluate_line_accuracy_mode_off_is_byte_identical_to_default():
    st = _doubles_state_for_eval()
    moon = get_move_meta("Moonblast")  # accuracy 100, still deterministic here
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    s_default, out_default = evaluate_line(st, [mine], [], dmg, our_side="p1")
    s_explicit_off, out_explicit_off = evaluate_line(
        st, [mine], [], dmg, our_side="p1", accuracy_mode=False,
    )
    assert s_default == s_explicit_off
    assert out_default.hp_delta == out_explicit_off.hp_delta


def test_evaluate_line_accuracy_mode_on_weights_hit_and_miss():
    st = _doubles_state_for_eval()
    risky = MoveMeta(id="risky", name="Risky", accuracy=70, base_power=100,
                      category="physical", target="normal")
    mine = PlannedAction("p1", "a", "move", speed=100, move=risky, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    w = EvalWeights()
    s_on, _out_on = evaluate_line(st, [mine], [], dmg, our_side="p1", accuracy_mode=True, weights=w)

    # hand-computed: hit branch (p=0.7) deals 0.5 dmg dealt; miss branch (p=0.3) deals 0 dmg.
    hit_score = w.dmg_dealt * 0.5
    miss_score = 0.0
    expected = 0.7 * hit_score + 0.3 * miss_score
    assert abs(s_on - expected) < 1e-9


def test_evaluate_line_tight_accuracy_branch_cap_increments_telemetry():
    st = _doubles_state_for_eval()
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    u1 = MoveMeta(id="u1", name="U1", accuracy=50, base_power=100, category="physical", target="normal")
    u2 = MoveMeta(id="u2", name="U2", accuracy=50, base_power=100, category="physical", target="normal")
    a1 = PlannedAction("p1", "a", "move", speed=150, move=u1, target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=u2, target=("p2", "b"), is_ours=True)

    def dmg(action, target):
        return 0.1

    _s, out_capped = evaluate_line(
        st, [a1, a2], [], dmg, our_side="p1", accuracy_mode=True, accuracy_branch_cap=1,
    )
    assert out_capped.accuracy_branch_cap_hits >= 1
```

Add `EvalWeights`/`get_move_meta` to the existing import block at the top of
`showdown_bot/tests/test_evaluate.py` if not already imported (check the current import — it
already imports `EvalWeights` and `evaluate_line` from `showdown_bot.battle.evaluate`, but not
`get_move_meta`; add `from showdown_bot.engine.moves import get_move_meta`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_evaluate.py -v -k accuracy_mode`
Expected: FAIL with `TypeError: evaluate_line() got an unexpected keyword argument 'accuracy_mode'`.

- [ ] **Step 3: Add `accuracy_mode`/`accuracy_branch_cap` to `evaluate_line` and wire `_one(tb)`**

In `showdown_bot/src/showdown_bot/battle/evaluate.py`, change the existing import at line 8 from

```python
from showdown_bot.battle.resolve import PlannedAction, TurnOutcome, resolve_turn
```
to
```python
from showdown_bot.battle.resolve import PlannedAction, TurnOutcome, resolve_turn, resolve_turn_branches
```

Modify `evaluate_line`'s signature (`evaluate.py:366-380`) to add the two new keyword-only
parameters after `fast_board: bool = False,`:

```python
def evaluate_line(
    state: BattleState,
    my_actions: list[PlannedAction],
    opp_actions: list[PlannedAction],
    damage_fn,
    *,
    our_side: str,
    weights: EvalWeights | None = None,
    field: FieldState | None = None,
    rollout_horizon: int = 0,
    rollout_gamma: float = 0.7,
    endgame: bool = False,
    fast_board: bool = False,
    accuracy_mode: bool = False,
    accuracy_branch_cap: int = 4,
    _force_tie_break: str | None = None,
) -> tuple[float, TurnOutcome]:
```

Replace the `_one(tb)` closure body (`evaluate.py:384-392`) with a mode branch:

```python
    def _one(tb: str) -> tuple[float, TurnOutcome]:
        def _scored(out: TurnOutcome) -> float:
            sc = score_outcome(out, our_side, weights, endgame=endgame, fast_board=fast_board)
            if rollout_horizon > 0:
                sc += _rollout_value(
                    state, all_actions, out, our_side, weights or EvalWeights(),
                    field, rollout_horizon, rollout_gamma,
                )
            return sc

        if not accuracy_mode:
            out = resolve_turn(state, all_actions, damage_fn, our_side=our_side, field=field, tie_break=tb)
            return _scored(out), out

        leaves, fallback_leaves, _fork_records = resolve_turn_branches(
            state, all_actions, damage_fn, our_side=our_side, field=field,
            tie_break=tb, branch_cap=accuracy_branch_cap,
        )
        total = sum(w * _scored(out) for w, out in leaves)
        representative = leaves[0][1]
        representative.accuracy_branch_cap_hits = fallback_leaves
        return total, representative
```

`evaluate_line`'s own return contract stays `(float, TurnOutcome)` (many `decision.py` call sites
unpack `[0]`), so `_fork_records` is intentionally discarded here — a caller that wants full
`AccuracyDiagnostics` (Task 6), including `miss_punish_value`, calls `resolve_turn_branches`
directly instead of going through `evaluate_line`.

- [ ] **Step 4: Add `accuracy_branch_cap_hits` to `TurnOutcome`**

In `showdown_bot/src/showdown_bot/battle/resolve.py`, add one more field to `TurnOutcome`
(after `missed_hits`, added in Task 3):

```python
    missed_hits: list[MissedHit] = field(default_factory=list)
    accuracy_branch_cap_hits: int = 0
```

- [ ] **Step 5: Run the `evaluate_line` tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_evaluate.py -v`
Expected: all PASS.

- [ ] **Step 6: Add the env-reading functions with an explicit boolean parser**

In `showdown_bot/src/showdown_bot/battle/decision.py`, add two new functions after `_search_topm`
(after `decision.py:79-88`):

```python
def _accuracy_mode() -> bool:
    """``SHOWDOWN_ACCURACY_MODE``: on/off switch for hit/miss branching in evaluate_line.
    Off (default/unset/""/"0"/"false", case-insensitive) -> today's exact always-hit
    resolve_turn path, byte-identical output. Uses an EXPLICIT off-list, not
    ``bool(os.environ.get(...))`` -- that shortcut (used elsewhere in this codebase for
    presence-only flags, e.g. SHOWDOWN_RERANKER_SHADOW) treats the STRING "0" or "false" as
    truthy, which is wrong here: this flag needs "0"/"false" to explicitly mean off, not just
    unset, so Task 9's off-path verification can set it either way."""
    raw = os.environ.get("SHOWDOWN_ACCURACY_MODE", "").strip().lower()
    return raw not in ("", "0", "false")


def _accuracy_branch_cap() -> int:
    """Max resolve_turn calls per resolve_turn_branches expansion
    (SHOWDOWN_ACCURACY_BRANCH_CAP). Default 4, clamped >=1. Only consulted when
    _accuracy_mode() is on."""
    try:
        v = int(os.environ.get("SHOWDOWN_ACCURACY_BRANCH_CAP", "4"))
    except ValueError:
        return 4
    return max(1, v)
```

**Thread `accuracy_mode`/`accuracy_branch_cap` through every `evaluate_line` call that belongs to
the SAME live decision — revised after plan review.** An earlier draft of this task wired only
`score_plan`/`score_plan_with_outcome` and left `_maybe_tera` (which can directly overwrite the
chosen action) and the report/trace call sites (which populate `DecisionTrace`, later used as
training data) on the legacy always-hit path. That would have made tera-or-not decisions
accuracy-blind — a live decision bug, not a reporting cosmetic — and let the exported trace
breakdown silently disagree with the score that actually ranked the candidates. Fixed by computing
`accuracy_mode`/`accuracy_branch_cap` once per `_choose_best` call and threading the same two
values into every `evaluate_line` call site within `_choose_best`/`_maybe_tera`. The one
deliberate, unchanged boundary: `depth2_value` (`battle/search.py`, Depth-2's turn-2 backup) stays
untouched — out of scope per spec §12, a later slice.

In `_choose_best` (`decision.py:226-...`), resolve the two values once, right after the existing
`risk_lambda = _risk_lambda()` line (`decision.py:264`):

```python
    if risk_lambda is None:
        risk_lambda = _risk_lambda()
    accuracy_mode = _accuracy_mode()
    accuracy_branch_cap = _accuracy_branch_cap()
```

Add `accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,` to every
`evaluate_line(...)` call inside `_choose_best`, immediately after each call's existing
`weights=weights, field=state.field,` (or, for the two calls that don't already pass
`rollout_horizon`/`endgame`/`fast_board` — the K-world path and `_maybe_tera` — after
`field=state.field,` directly). Concretely:

```python
        # K-world / +Sampling path (decision.py:378-388)
        def score_plan(my_plan: list[PlannedAction]) -> list[float]:
            out: list[float] = []
            for _w, resps_k, model_k in world_ctx:
                targets = [r.actions for r in resps_k] if resps_k else [[]]
                for opp_actions in targets:
                    out.append(evaluate_line(
                        state, my_plan, opp_actions, model_k.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                    )[0])
            return out
```

```python
        # single-world path (decision.py:415-431)
        def score_plan(my_plan: list[PlannedAction]) -> list[float]:
            if opp_resps:
                return [
                    evaluate_line(
                        state, my_plan, r.actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                    )[0]
                    for r in opp_resps
                ]
            return [
                evaluate_line(
                    state, my_plan, [], model.damage_fn,
                    our_side=our_side, weights=weights, field=state.field,
                    rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                    accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                )[0]
            ]

        if _search_depth() > 1 and world_samples() <= 1:
            def score_plan_with_outcome(my_plan: list[PlannedAction]) -> list[tuple[float, object]]:
                targets = [r.actions for r in opp_resps] if opp_resps else [[]]
                return [
                    evaluate_line(
                        state, my_plan, opp_actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                    )
                    for opp_actions in targets
                ]
```

```python
        # report "metrics" line (decision.py:521-528)
        chosen_plan = _plan_my_actions(
            req, best_ja, state=state, our_side=our_side, opp_side=opp_side, speed_oracle=speed_oracle
        )
        rep_resp = opp_resps[0].actions if opp_resps else []
        _, out = evaluate_line(
            state, chosen_plan, rep_resp, model.damage_fn,
            our_side=our_side, weights=weights, field=state.field, rollout_horizon=0,
            accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
        )
```

```python
        # trace breakdowns (decision.py:559-572)
        def _breakdowns_for(plan):
            out = []
            for ra in rep_resps:
                _, oc = evaluate_line(
                    state, plan, ra, model.damage_fn, our_side=our_side,
                    weights=weights, field=state.field, rollout_horizon=0,
                    endgame=endgame, fast_board=fast_board,
                    accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                )
                out.append(
                    score_outcome_with_breakdown(
                        oc, our_side, weights, endgame=endgame, fast_board=fast_board
                    )[1]
                )
            return out
```

Finally, `_maybe_tera` (`decision.py:763-800`) gains the two parameters on its signature and
threads them into both its `evaluate_line` calls; `_choose_best`'s call to `_maybe_tera`
(`decision.py:499-503`) passes the two values through:

```python
def _maybe_tera(
    req, best_ja, best_val, mode, state, our_side, opp_side,
    speed_oracle, opp_resps, model, weights, risk_lambda, tera_margin, resp_weights=None,
    *, endgame: bool = False, fast_board: bool = False,
    accuracy_mode: bool = False, accuracy_branch_cap: int = 4,
) -> JointAction:
    """Overlay: only spend Tera if it beats the non-Tera line by a margin."""
    from showdown_bot.battle.policy import aggregate_scores

    best = best_ja
    best_overlay_val = best_val
    for i, sa in enumerate((best_ja.slot0, best_ja.slot1)):
        if sa.kind != "move":
            continue
        if i >= len(req.active) or not req.active[i].can_terastallize:
            continue
        tera_ja = best_ja.with_tera(i)
        plan = _plan_my_actions(
            req, tera_ja, state=state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
        )
        if opp_resps:
            scores = [
                evaluate_line(state, plan, r.actions, model.damage_fn,
                              our_side=our_side, weights=weights, field=state.field,
                              endgame=endgame, fast_board=fast_board,
                              accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap)[0]
                for r in opp_resps
            ]
        else:
            scores = [
                evaluate_line(state, plan, [], model.damage_fn,
                              our_side=our_side, weights=weights, field=state.field,
                              endgame=endgame, fast_board=fast_board,
                              accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap)[0]
            ]
        val = aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights)
        if val > best_overlay_val and tera_decision(best_val, val, margin=tera_margin):
            best = tera_ja
            best_overlay_val = val
    return best
```

```python
    best_ja = _maybe_tera(
        req, best_ja, best_val, mode, state, our_side, opp_side,
        speed_oracle, opp_resps, model, weights, risk_lambda, tera_margin, resp_weights,
        endgame=endgame, fast_board=fast_board,
        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
    )
```

- [ ] **Step 7: Add the two new env vars to `BEHAVIOR_AFFECTING`**

In `showdown_bot/src/showdown_bot/eval/config_env.py`, add two entries to the `BEHAVIOR_AFFECTING`
frozenset (`config_env.py:23-72`), after the existing `SHOWDOWN_FAST_BOARD_PROTECT_PENALTY` entry:

```python
    # [accuracy-slice] On/off switch for hit/miss branching in evaluate_line -- directly
    # changes which candidate's score is used (always-hit vs probability-weighted) -> config_hash.
    # Off/unset = byte-identical.
    "SHOWDOWN_ACCURACY_MODE",
    # [accuracy-slice] Max resolve_turn_branches expansion depth. A different cap can change
    # which lines hit the per-branch fallback and therefore which candidate scores highest --
    # deliberately UNCONDITIONAL here (not excluded when SHOWDOWN_ACCURACY_MODE is off), to
    # avoid repeating the SHOWDOWN_SEARCH_TOPN/TOPM conditional-exclusion bug the project's
    # audit found.
    "SHOWDOWN_ACCURACY_BRANCH_CAP",
```

- [ ] **Step 8: Write the config_env tests**

Append to `showdown_bot/tests/test_config_env.py`:

```python
# --- accuracy mode + branch cap (accuracy-slice) ----------------------------------------

def test_accuracy_mode_is_behavior_affecting_and_classified():
    assert "SHOWDOWN_ACCURACY_MODE" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_ACCURACY_MODE" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_ACCURACY_MODE")


def test_accuracy_branch_cap_is_behavior_affecting_and_classified():
    assert "SHOWDOWN_ACCURACY_BRANCH_CAP" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_ACCURACY_BRANCH_CAP" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_ACCURACY_BRANCH_CAP")


def test_config_hash_changes_when_accuracy_mode_toggled():
    h_off = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h_on = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_ACCURACY_MODE": "1"})))
    assert h_off != h_on


def test_config_hash_changes_when_accuracy_branch_cap_differs_with_mode_on():
    h_cap4 = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_ACCURACY_MODE": "1", "SHOWDOWN_ACCURACY_BRANCH_CAP": "4"})))
    h_cap8 = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_ACCURACY_MODE": "1", "SHOWDOWN_ACCURACY_BRANCH_CAP": "8"})))
    assert h_cap4 != h_cap8


# --- _accuracy_mode() explicit boolean parser -------------------------------------------
# Regression coverage for the bug caught in plan review: bool(os.environ.get(...)) would
# treat the STRINGS "0" and "false" as truthy. These six cases are the exact matrix that
# must hold for Task 9's off-path verification (which explicitly sets "0"/"false") to mean
# anything.

@pytest.mark.parametrize(("raw", "expected"), [
    (None, False),      # unset
    ("", False),
    ("0", False),
    ("false", False),
    ("False", False),   # case-insensitive
    ("1", True),
    ("true", True),
])
def test_accuracy_mode_parser_matrix(monkeypatch, raw, expected):
    from showdown_bot.battle.decision import _accuracy_mode

    if raw is None:
        monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)
    else:
        monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", raw)
    assert _accuracy_mode() is expected
```

Add `import pytest` to the top of `showdown_bot/tests/test_config_env.py` if it isn't already
imported (check the current imports — the existing `test_search_depth_is_behavior_affecting_and_clamped`
test already uses `monkeypatch` as a fixture argument without a top-level import, since pytest
fixtures are auto-injected; `@pytest.mark.parametrize` does need `import pytest` at module level —
add it if missing).

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_config_env.py tests/test_evaluate.py -v`
Expected: all PASS.

- [ ] **Step 10: Run the full suite**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, no regressions — `accuracy_mode` defaults to `False` on `evaluate_line`, and
`_accuracy_mode()` returns `False` when the env var is unset (or explicitly `""`/`"0"`/`"false"`),
so every one of the 8 `evaluate_line` call sites now threaded through `_choose_best`/`_maybe_tera`
behaves exactly as before when the flag is off. `depth2_value`/`search.py` (untouched, out of
scope per spec §12) is the only accuracy-blind evaluate_line consumer left, and that is a
deliberate, documented boundary, not an oversight.

- [ ] **Step 11: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/src/showdown_bot/battle/resolve.py \
        showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/src/showdown_bot/eval/config_env.py \
        showdown_bot/tests/test_evaluate.py showdown_bot/tests/test_config_env.py
git commit -m "feat(accuracy): wire resolve_turn_branches into evaluate_line + all 8 live-decision call sites, off-by-default"
```

---

### Task 6: Derived diagnostics (`ko_probability`, `survival_probability`, `accuracy_required`, `miss_punish_value`)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/evaluate.py`
- Test: `showdown_bot/tests/test_evaluate.py`

**Revised after plan review — all 4 diagnostics from spec §7, not 2.** An earlier draft of this
task implemented only `ko_probability`/`survival_probability` while its own self-review claimed
full §7 coverage — a real gap between the claim and the code, caught in review before any subagent
touched it. This revision implements all four, using the `fork_records` Task 4 now returns for
`miss_punish_value` (spec §7's definition — "the weighted-average score of that fork's miss
sibling subtree minus score(leaves[0])" — cannot be reconstructed from a flat leaf list; it needs
the tree structure `fork_records` preserves).

**KO-detection bug fixed in this revision too:** an earlier draft checked
`out.hp_delta.get(target, 0.0) <= -1.0`. `hp_delta` is FRACTIONAL (`new_frac - start_frac`, per
`_rollout_value`'s own docstring in this file) — a target at 30% starting HP is KO'd by
`hp_delta=-0.3`, not `-1.0`. The flat `-1.0` check would silently report `ko_probability=0` for a
real, already-happened KO on any target that started below full HP. Fixed by computing each
target's actual starting `hp_fraction` from `state` and checking the FINAL fraction against ~0,
not the raw delta against a constant.

**Trace-wiring scope (explicit follow-up, not silent):** the spec (§7) describes these as
populating "a trace." This task implements them as a standalone, independently-testable pure
function over `resolve_turn_branches`'s output — a caller (e.g. `decision.py`'s `trace is not
None` block) that wants `AccuracyDiagnostics` calls `resolve_turn_branches` directly and passes
its result in; nothing in this task calls it automatically. Wiring the result into the live
`DecisionTrace` dataclass/schema is explicitly NOT done in this task — that file
(`battle/decision_trace.py`) has not been read in this plan, and guessing at an unverified schema
is worse than leaving a clean, tested, unused-by-default function. **Follow-up required before
this is considered closed:** a short, separate task (or the start of the Depth-2 Stage 3 slice,
whichever comes first) must either wire `AccuracyDiagnostics` into `DecisionTrace` with clearly
separated field names (e.g. an `accuracy_diagnostics: AccuracyDiagnostics | None = None` field,
`None` when `accuracy_mode` is off) or explicitly re-confirm it's still not needed. Record this
as an open item in Task 9's closeout report, not just in this task's own note.

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_evaluate.py`:

```python
from showdown_bot.battle.evaluate import AccuracyDiagnostics, accuracy_diagnostics
from showdown_bot.battle.resolve import ForkRecord, TurnOutcome


def _diag_state_full_hp():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Attacker", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Target", hp=100, max_hp=100)
    return st


def test_accuracy_diagnostics_ko_and_survival_probability():
    target = ("p2", "a")
    st = _diag_state_full_hp()
    leaves = [
        (0.7, TurnOutcome(opp_kos=1, hp_delta={target: -1.0})),
        (0.3, TurnOutcome(opp_kos=0, hp_delta={target: 0.0})),
    ]
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert isinstance(diag, AccuracyDiagnostics)
    assert abs(diag.ko_probability[target] - 0.7) < 1e-9
    assert abs(diag.survival_probability[target] - 0.3) < 1e-9


def test_accuracy_diagnostics_single_leaf_is_certain():
    target = ("p2", "a")
    st = _diag_state_full_hp()
    leaves = [(1.0, TurnOutcome(opp_kos=1, hp_delta={target: -1.0}))]
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert diag.ko_probability[target] == 1.0
    assert diag.survival_probability[target] == 0.0


def test_accuracy_diagnostics_ko_probability_uses_starting_hp_not_flat_minus_one():
    """Regression test: a target at 30% starting HP is KO'd by hp_delta=-0.3, not -1.0. A
    naive `hp_delta <= -1.0` check silently reports 0% KO probability for this real, already-
    happened KO -- this is the exact bug an earlier draft had."""
    target = ("p2", "a")
    st = BattleState()
    st.sides["p2"]["a"] = PokemonState(species="Weak", hp=30, max_hp=100)  # 30% HP
    leaves = [(1.0, TurnOutcome(opp_kos=1, hp_delta={target: -0.3}))]
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert diag.ko_probability[target] == 1.0
    assert diag.survival_probability[target] == 0.0


def test_accuracy_diagnostics_ko_probability_not_triggered_by_partial_damage():
    # Same starting HP as above, but damage this time leaves the target alive (10% HP left).
    target = ("p2", "a")
    st = BattleState()
    st.sides["p2"]["a"] = PokemonState(species="Weak", hp=30, max_hp=100)  # 30% HP
    leaves = [(1.0, TurnOutcome(hp_delta={target: -0.2}))]  # 30% -> 10%, survives
    diag = accuracy_diagnostics(leaves, targets=[target], state=st, actions=[], field=None)
    assert diag.ko_probability[target] == 0.0
    assert diag.survival_probability[target] == 1.0


def test_accuracy_diagnostics_accuracy_required_and_miss_punish_value():
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.battle.resolve import AttemptedHit, PlannedAction
    from showdown_bot.engine.moves import MoveMeta

    st = _diag_state_full_hp()
    risky = MoveMeta(id="risky", name="Risky", accuracy=70, base_power=100,
                      category="physical", target="normal")
    action = PlannedAction("p1", "a", "move", speed=100, move=risky, target=("p2", "a"), is_ours=True)
    pair = (("p1", "a"), ("p2", "a"))
    w = EvalWeights()

    hit_out = TurnOutcome(hp_delta={("p2", "a"): -0.5}, attempted_hits=[AttemptedHit(*pair, "risky")])
    miss_out = TurnOutcome(hp_delta={("p2", "a"): 0.0}, attempted_hits=[AttemptedHit(*pair, "risky")])
    leaves = [(0.7, hit_out), (0.3, miss_out)]
    fork_records: list[ForkRecord] = [(pair, [(0.3, miss_out)])]

    diag = accuracy_diagnostics(
        leaves, targets=[("p2", "a")], state=st, actions=[action], field=FieldState(),
        fork_records=fork_records, weights=w, our_side="p1",
    )
    assert abs(diag.accuracy_required[pair] - 0.70) < 1e-9
    # miss_punish_value = score(miss subtree) - score(leaves[0]) = (0 - w.dmg_dealt*0.5) < 0
    expected = 0.0 - (w.dmg_dealt * 0.5)
    assert abs(diag.miss_punish_value[pair] - expected) < 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_evaluate.py -v -k accuracy_diagnostics`
Expected: FAIL with `ImportError: cannot import name 'AccuracyDiagnostics'`.

- [ ] **Step 3: Implement `AccuracyDiagnostics` and `accuracy_diagnostics`**

In `showdown_bot/src/showdown_bot/battle/evaluate.py`, add `ForkRecord` to the import line Task 5
Step 3 modified, so it reads:

```python
from showdown_bot.battle.resolve import (
    ForkRecord, PlannedAction, SlotId, TurnOutcome, resolve_turn, resolve_turn_branches,
)
```

Add a new import for `hit_probability`:

```python
from showdown_bot.engine.moves import hit_probability
```

Add near the top of the file (after the existing dataclass/import section, before `evaluate_line`):

```python
@dataclass
class AccuracyDiagnostics:
    ko_probability: dict[SlotId, float]
    survival_probability: dict[SlotId, float]
    accuracy_required: dict[tuple[SlotId, SlotId], float | None]
    miss_punish_value: dict[tuple[SlotId, SlotId], float]


def _final_hp_fraction(state: BattleState, target: SlotId, out: TurnOutcome) -> float:
    mon = state.sides.get(target[0], {}).get(target[1])
    start = mon.hp_fraction if mon is not None else 0.0
    return max(0.0, start + out.hp_delta.get(target, 0.0))


def accuracy_diagnostics(
    leaves: list[tuple[float, TurnOutcome]],
    *,
    targets: list[SlotId],
    state: BattleState,
    actions: list[PlannedAction],
    field: FieldState | None,
    fork_records: list[ForkRecord] = (),
    weights: EvalWeights | None = None,
    our_side: str = "p1",
    endgame: bool = False,
    fast_board: bool = False,
) -> AccuracyDiagnostics:
    """Derived from the leaf list (and fork structure) resolve_turn_branches already returns --
    no extra resolve_turn calls. ko_probability uses each target's STARTING hp_fraction (from
    ``state``) plus the leaf's fractional hp_delta -- a target already below full HP can be KO'd
    by an hp_delta well above -1.0; checking against a flat -1.0 threshold silently misses that."""
    ko_probability: dict[SlotId, float] = {t: 0.0 for t in targets}
    for weight, out in leaves:
        for t in targets:
            if _final_hp_fraction(state, t, out) <= 1e-9:
                ko_probability[t] += weight
    survival_probability = {t: 1.0 - p for t, p in ko_probability.items()}

    actions_by_key = {a.key: a for a in actions}
    accuracy_required: dict[tuple[SlotId, SlotId], float | None] = {}
    for ah in leaves[0][1].attempted_hits:
        pair = (ah.attacker, ah.target)
        if pair in accuracy_required:
            continue
        attacker_action = actions_by_key.get(ah.attacker)
        if attacker_action is None or attacker_action.move is None:
            continue
        attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
        target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
        if attacker_mon is None or target_mon is None:
            continue
        accuracy_required[pair] = hit_probability(attacker_action.move, attacker_mon, target_mon, field)

    def _scored(out: TurnOutcome) -> float:
        return score_outcome(out, our_side, weights, endgame=endgame, fast_board=fast_board)

    leaves0_score = _scored(leaves[0][1])
    miss_punish_value: dict[tuple[SlotId, SlotId], float] = {}
    for pair, miss_subtree in fork_records:
        subtree_weight = sum(w for w, _ in miss_subtree)
        if subtree_weight <= 0.0:
            continue
        weighted_avg = sum(w * _scored(out) for w, out in miss_subtree) / subtree_weight
        miss_punish_value[pair] = weighted_avg - leaves0_score

    return AccuracyDiagnostics(
        ko_probability=ko_probability, survival_probability=survival_probability,
        accuracy_required=accuracy_required, miss_punish_value=miss_punish_value,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_evaluate.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/tests/test_evaluate.py
git commit -m "feat(accuracy): AccuracyDiagnostics (ko/survival/accuracy_required/miss_punish_value), fixed KO-detection"
```

---

### Task 7: `movedata_hash` provenance wiring

**Files:**
- Modify: `showdown_bot/src/showdown_bot/engine/moves.py`
- Modify: `showdown_bot/src/showdown_bot/eval/config_env.py`
- Modify: `showdown_bot/src/showdown_bot/cli.py`
- Test: `showdown_bot/tests/test_config_env.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_config_env.py`:

```python
def test_build_config_manifest_includes_movedata_hash_when_provided():
    m = build_config_manifest(
        agent="heuristic", format_id="f", priors_hash="p", spreads_hash="s",
        movedata_hash="mv1", env={},
    )
    assert m["movedata_hash"] == "mv1"


def test_build_config_manifest_movedata_hash_absent_when_not_provided():
    m = build_config_manifest(
        agent="heuristic", format_id="f", priors_hash="p", spreads_hash="s", env={},
    )
    assert "movedata_hash" not in m


def test_config_hash_changes_when_movedata_hash_differs():
    m1 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s",
                                movedata_hash="mv1", env={})
    m2 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s",
                                movedata_hash="mv2", env={})
    assert make_config_hash(m1) != make_config_hash(m2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "showdown_bot" && python -m pytest tests/test_config_env.py -v -k movedata_hash`
Expected: FAIL with `TypeError: build_config_manifest() got an unexpected keyword argument 'movedata_hash'`.

- [ ] **Step 3: Add `movedata_hash` to `build_config_manifest`**

In `showdown_bot/src/showdown_bot/eval/config_env.py`, modify `build_config_manifest`
(`config_env.py:167-185`):

```python
def build_config_manifest(*, agent, format_id, priors_hash, spreads_hash, env=None,
                          model_hash=None, model_manifest_hash=None, movedata_hash=None) -> dict:
    """Assemble the effective-config manifest that ``make_config_hash`` hashes.

    ``env`` defaults to ``behavior_env()``. ``model_hash``/``model_manifest_hash`` are
    included ONLY when provided (i.e. when the reranker is enabled), so a reranker-off run
    and a reranker-on run never collide. ``movedata_hash`` is a content hash of
    ``config/moves/movedata.json`` -- included whenever provided (unconditionally by the
    caller, mirroring ``priors_hash``/``spreads_hash``, not gated behind
    ``SHOWDOWN_ACCURACY_MODE``), so two runs with different accuracy data never share a
    config lineage even when the accuracy feature itself is off."""
    manifest = {
        "agent": agent,
        "format_id": format_id,
        "priors_hash": priors_hash,
        "spreads_hash": spreads_hash,
        "env": behavior_env() if env is None else env,
    }
    if model_hash is not None:
        manifest["model_hash"] = model_hash
    if model_manifest_hash is not None:
        manifest["model_manifest_hash"] = model_manifest_hash
    if movedata_hash is not None:
        manifest["movedata_hash"] = movedata_hash
    return manifest
```

- [ ] **Step 4: Run the config_env tests to verify they pass**

Run: `cd "showdown_bot" && python -m pytest tests/test_config_env.py -v`
Expected: all PASS.

- [ ] **Step 5: Add `movedata_path()` accessor to `engine/moves.py`**

In `showdown_bot/src/showdown_bot/engine/moves.py`, add a public accessor after the existing
`_MOVEDATA` constant definition (`moves.py:14`):

```python
def movedata_path() -> Path:
    """Public accessor for the generated move-data file path, for provenance hashing
    (config_hash) -- avoids reaching across modules for the private _MOVEDATA constant."""
    return _MOVEDATA
```

- [ ] **Step 6: Wire `movedata_hash` into `cli.py`'s config_hash computation**

In `showdown_bot/src/showdown_bot/cli.py`, find the block that computes `priors_hash`/
`spreads_hash` (`cli.py:133-150`, the `_config_hash_for` closure). Add the `movedata_path` import
near the top of the function (alongside the existing `from showdown_bot.eval.config_env import
behavior_env, build_config_manifest` at `cli.py:105`):

```python
        from showdown_bot.eval.config_env import behavior_env, build_config_manifest
        from showdown_bot.eval.result_jsonl import BattleResultWriter, make_battle_id, make_config_hash
        from showdown_bot.eval.run_manifest import (
            build_run_manifest,
```
(this import block is unchanged — `movedata_path` is imported separately, next to the existing
`_file_content_hash` usage below.)

Modify the `_config_hash_for` closure body (`cli.py:133-150`) to compute and pass `movedata_hash`:

```python
        def _config_hash_for(agent, format_id):
            key = (agent, format_id)
            if key not in _cfg_hash_cache:
                from showdown_bot.engine.moves import movedata_path

                priors_hash = spreads_hash = None
                try:
                    from showdown_bot.engine.format_config import load_format_config

                    cfg = load_format_config(format_id)
                    priors_hash = _file_content_hash(cfg.meta_path("protect_priors"))
                    spreads_hash = _file_content_hash(cfg.meta_path("default_spreads"))
                except Exception:  # noqa: BLE001 - provenance best-effort; missing config -> None
                    pass
                movedata_hash = _file_content_hash(movedata_path())
                manifest = build_config_manifest(
                    agent=agent, format_id=format_id,
                    priors_hash=priors_hash, spreads_hash=spreads_hash, env=_behavior_env,
                    model_hash=_model_hash, model_manifest_hash=_model_manifest_hash,
                    movedata_hash=movedata_hash,
                )
                _cfg_hash_cache[key] = make_config_hash(manifest)
```

- [ ] **Step 7: Run the full suite**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/moves.py showdown_bot/src/showdown_bot/eval/config_env.py \
        showdown_bot/src/showdown_bot/cli.py showdown_bot/tests/test_config_env.py
git commit -m "feat(accuracy): wire movedata.json content hash into config_hash, mirroring priors/spreads_hash"
```

---

### Task 8: Latency micro-benchmark to pin `SHOWDOWN_ACCURACY_BRANCH_CAP`'s default

**Files:**
- Create: `scratchpad/bench_accuracy_latency.py` (this project's scratchpad, not a repo path — see
  the "Scratchpad Directory" note in the environment section, or place it at
  `showdown_bot/scratchpad/bench_accuracy_latency.py` if the repo's own convention differs; check
  for an existing `scratchpad/` directory at the repo root first — `reports/2026-07-12-2c-depth2-derisk-verdict.md`
  references `scratchpad/bench_depth2_latency.py` as its precedent, at the repo root)
- Create: `reports/2026-07-12-accuracy-slice-latency-gate.md`

This task follows the exact methodology of `reports/2026-07-12-2c-depth2-derisk-verdict.md`'s
Stage 1 (read that report in full first) — persistent calc backend, warmup runs, p50/p95/max,
gate against a wall-clock budget. Do **not** invent a different methodology.

- [ ] **Step 1: Locate the depth-2 latency bench script to copy its harness shape**

Run: `find . -iname "bench_depth2_latency.py"` (or check `scratchpad/` at the repo root per the
report's citation). Read it in full before writing the new script — reuse its exact pattern for
setting `SHOWDOWN_CALC_BACKEND=persistent`, constructing a fresh `DamageOracle` per decision, and
timing `heuristic_choose_for_request` (or the equivalent entry point this repo currently exposes —
verify the function name is still current by grepping for it, since the report is from earlier in
this same day's work and may already be slightly stale by the time this task runs).

- [ ] **Step 2: Write the benchmark script**

Create `scratchpad/bench_accuracy_latency.py` (or the repo-root-relative path found in Step 1),
adapting the depth-2 script's structure to this slice: instead of varying
`SHOWDOWN_SEARCH_DEPTH`/`(TOPN, TOPM)`, vary `SHOWDOWN_ACCURACY_MODE` (off baseline vs on) ×
`SHOWDOWN_ACCURACY_BRANCH_CAP` ∈ `{2, 4, 6, 8}`, on a realistic doubles board that includes at
least one spread move with `accuracy < 100` on each side (to actually exercise multi-event
branching, not just the trivial 0-event case). Use the same board-construction helper the depth-2
script used if one already exists and is importable; otherwise construct a comparable board
directly with `PlannedAction`/`BattleState` following this plan's own test fixtures as a template.
Measure n=25 per config after 5 warmups, report p50/p95/max in milliseconds and the observed
`accuracy_branch_cap_hits` rate at each cap value.

- [ ] **Step 3: Run the benchmark**

Run: `cd "showdown_bot" && SHOWDOWN_CALC_BACKEND=persistent python ../scratchpad/bench_accuracy_latency.py`
(adjust the path to match wherever Step 2 actually created the script). Record the raw output.

- [ ] **Step 4: Pick the default `SHOWDOWN_ACCURACY_BRANCH_CAP` value from the real numbers**

Using the depth-2 precedent's gate (p95 < 1000 ms leaves comfortable headroom under a
5×-heavier-Kaggle-board multiplier), pick the largest cap value from Step 2's table whose p95 stays
under roughly 300-400 ms locally (mirroring how the depth-2 report scaled its local numbers to the
Kaggle margin). Update the default in `showdown_bot/src/showdown_bot/battle/decision.py`'s
`_accuracy_branch_cap()` (Task 5, Step 6) from `"4"` to the chosen value if the measured numbers
justify a different default than the placeholder — do not leave `4` unexamined if the data says
otherwise.

- [ ] **Step 5: Write the latency-gate report**

Create `reports/2026-07-12-accuracy-slice-latency-gate.md` following
`reports/2026-07-12-2c-depth2-derisk-verdict.md`'s structure (TL;DR, method, results table,
verdict). State explicitly which `SHOWDOWN_ACCURACY_BRANCH_CAP` default was chosen and why.

- [ ] **Step 6: Commit**

```bash
git add scratchpad/bench_accuracy_latency.py reports/2026-07-12-accuracy-slice-latency-gate.md \
        showdown_bot/src/showdown_bot/battle/decision.py
git commit -m "docs(accuracy): local latency micro-bench, pin SHOWDOWN_ACCURACY_BRANCH_CAP default"
```

---

### Task 9: Off-path byte-identity verification + closeout report

**Files:**
- Test: full suite
- Create: `reports/2026-07-12-accuracy-slice-closeout.md`

- [ ] **Step 1: Run the full suite one more time, clean**

Run: `cd "showdown_bot" && python -m pytest -q`
Expected: PASS, full green, no skips introduced by this slice.

- [ ] **Step 2: Verify off-path byte-identity explicitly**

Write a small standalone check (can be a scratch script, not a committed test — the committed
tests in Tasks 3-5 already cover this at the unit level) that runs a handful of representative
`heuristic_choose_for_request` decisions twice: once with `SHOWDOWN_ACCURACY_MODE` unset, once with
it explicitly set to `"0"`/`"false"`, and confirms identical chosen actions and identical
`config_hash` values (via the same `_config_hash_for` path exercised in Task 7). This is a final
end-to-end sanity check beyond the unit-level `accuracy_mode=False` tests already in the suite.

- [ ] **Step 3: Regenerate `movedata.json` once more and confirm it's still fresh**

Run:
```bash
cd "showdown_bot/tools/gen"
node gen_movedata.mjs --check
```
Expected: `fresh` (exit 0) — confirms nothing in Tasks 1-8 caused the checked-in `movedata.json` to
drift from what the (now-modified) generator would produce.

- [ ] **Step 4: Write the closeout report**

Create `reports/2026-07-12-accuracy-slice-closeout.md` summarizing: what shipped (accuracy field
generation, `hit_probability`, `resolve_turn_branches` with fork-record tracking, `evaluate_line`
integration threaded through all 8 live-decision `evaluate_line` call sites in
`_choose_best`/`_maybe_tera`, all 4 `AccuracyDiagnostics` fields, `movedata_hash` provenance, the
latency-pinned branch cap default), the off-by-default guarantee and how it was verified, and the
fallback-rate figures from Task 8's benchmark (this is the artifact spec §10's later default-on
gate will need — the report should state the number, not act on it).

State the explicit scope boundaries, and list this ONE item as an **open follow-up, not a closed
decision**: `AccuracyDiagnostics` is implemented and tested as a standalone function
(`battle/evaluate.py::accuracy_diagnostics`) but is NOT wired into the live `DecisionTrace`
schema — no caller in this slice invokes it automatically. Per the Task 6 revision note, this
needs either a short follow-up task that adds an `accuracy_diagnostics: AccuracyDiagnostics | None`
field to `DecisionTrace` (clearly `None` when `accuracy_mode` is off) or an explicit, later
re-confirmation that it's still not needed — do not let this item silently disappear once this
slice merges. The other boundaries ARE closed decisions for this slice: `rollout.py` untouched,
ability/item accuracy modifiers not modeled (documented v1.1), risk-priority fork ordering not
implemented (deterministic attempted-hit order is v1 baseline), `depth2_value`/`battle/search.py`
untouched (Depth-2 Stage 3 is a separate, later slice per spec §12).

- [ ] **Step 5: Commit**

```bash
git add reports/2026-07-12-accuracy-slice-closeout.md
git commit -m "docs(accuracy): closeout report, off-path byte-identity verification"
```

---

## Self-Review

**This is the second self-review pass**, after a plan-review round caught 4 real issues in the
first draft (wrong env-flag parser, incomplete §7 coverage despite a claim of completeness, a
flat-threshold KO-detection bug, and 6 of 8 live `evaluate_line` call sites left silently
inconsistent). All 4 are fixed above; this pass re-checks the plan as it now stands, not as it was
originally drafted — the earlier draft's self-review claims (e.g. "§7 → Task 6 ✅") are superseded
by what's actually written now, not trusted at face value.

**Spec coverage:**
- §2 (generator + MoveMeta accuracy, fail-closed) → Task 1. ✅
- §3 (`hit_probability`, weather rules pinned to real PS source) → Task 2. ✅
- §4 (`forced_miss`, ordering, new `TurnOutcome` fields) → Task 3. ✅
- §5 (`resolve_turn_branches` recursive expansion + fork_records, KO-dependent regression test) →
  Task 4. ✅
- §6 (branch cap, per-branch fallback, telemetry, unconditional provenance) → Task 5 (cap +
  provenance + threading through all 8 live call sites) + Task 6 (telemetry field) + Task 8
  (empirical default). ✅
- §7 (derived diagnostics — all 4: `ko_probability`, `survival_probability`, `accuracy_required`,
  `miss_punish_value`) → Task 6. ✅ VERIFIED THIS PASS: all four are implemented and each has its
  own test, not just the two the first draft actually built. Standalone function, not wired into a
  live `DecisionTrace` — an explicit, named open follow-up (Task 6's revision note + Task 9's
  closeout report), not a silent gap.
- §8 (`movedata_hash` provenance) → Task 7. ✅
- §9 (ablation gate, both env vars behavior-affecting, explicit boolean parser) → Task 5. ✅
  VERIFIED THIS PASS: `_accuracy_mode()` now has a dedicated 6-case test matrix
  (`test_accuracy_mode_parser_matrix`) instead of relying on an untested `bool(...)` shortcut.
- §10 (fallback-rate go/no-go before default-on) → Task 8/9 produce the artifact; the gate decision
  itself is explicitly NOT this plan's job (spec is clear this is a later, separate decision). ✅
- §11 (testing strategy) → every listed test type has a concrete task/test above, including the
  new KO-detection regression test and the `miss_punish_value`/`accuracy_required` tests added
  this pass. ✅
- §12 (out of scope) → `rollout.py` untouched throughout; ability/item modifiers not built; fork
  ordering stays deterministic (not risk-priority); `depth2_value`/`battle/search.py` (Depth-2
  Stage 3) untouched — the ONE call-site boundary that remains after widening Task 5 from 2 to 8
  sites, and it's the correct one per spec §12, not a leftover oversight. ✅

**Placeholder scan:** no TBD/TODO; every step has complete code; no "similar to Task N" references.

**Type consistency (re-verified after the redesign):** `AttemptedHit`/`MissedHit` (Task 3) →
consumed identically in `resolve_turn_branches` (Task 4) → consumed identically in
`evaluate_line`'s `_one(tb)` (Task 5). `hit_probability`'s exact signature from Task 2 is called
identically in Task 4 and again in Task 6's `accuracy_required` computation.
`resolve_turn_branches`'s return type changed from a 2-tuple to
`tuple[list[tuple[float, TurnOutcome]], int, list[ForkRecord]]` partway through this plan (Task 4)
— every consumer was updated to match: Task 4's own 4 tests all unpack 3 values now, Task 5's
`_one(tb)` unpacks 3 and discards `fork_records` (documented why), Task 6's tests construct
`ForkRecord`-shaped fixtures directly. `accuracy_branch_cap_hits: int = 0` is declared on
`TurnOutcome` in Task 5 Step 4 (populated by the Task 5 integration, not Task 3's plumbing) — a
deliberate ordering choice. `accuracy_mode`/`accuracy_branch_cap` are threaded with IDENTICAL
parameter names through every one of `evaluate_line`'s 8 call sites in Task 5 (computed once,
reused, not re-read from `os.environ` at each site).

**Task 8 file-path caveat (unchanged from the first pass):** the scratchpad path for the benchmark
script needs verification against the actual repo-root convention at execution time — Task 8
Step 1 explicitly tells the implementer to locate the real precedent file first rather than guess.

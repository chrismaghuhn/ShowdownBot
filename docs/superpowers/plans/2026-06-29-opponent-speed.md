# Opponent Speed (Slice 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model a curated opponent's speed from its likely set (Scarf-aware point) instead of always-Jolly-252-Scarf max.

**Architecture:** `SpeedOracle.likely_speed` computes a cached point speed from a curated spread + an `item_for_speed`. In `opponent.py`, `_item_for_speed` (revealed/`item_lost` beats curated) and `_opponent_speed` (curated → likely, else `opponent_range.max`, gated by `SHOWDOWN_OPP_SPEED`) replace the inner `opp_speed`'s body. `opp_sets` is threaded into `predict_responses` from the decision.

**Tech Stack:** Python, pytest; spec `docs/superpowers/specs/2026-06-29-opponent-speed-design.md`. Run tests from `showdown_bot/`. `CalcMon(species, level, nature, evs, ivs)`; `effective_speed`/`speed_modifiers_from_state` in `engine/speed.py`; `to_id` already imported in `opponent.py`.

---

## File Structure
- `src/showdown_bot/engine/speed.py` — add `SpeedOracle.likely_speed` + a base-speed cache.
- `src/showdown_bot/battle/opponent.py` — add `_item_for_speed` + `_opponent_speed`; rewire `opp_speed`; `predict_responses` gains `opp_sets`.
- `src/showdown_bot/battle/decision.py` — pass `opp_sets` into `predict_responses`.
- Tests: `tests/test_speed.py` (create or append), `tests/test_opponent.py`.

---

## Task 1: `SpeedOracle.likely_speed` + base-speed cache

**Files:**
- Modify: `src/showdown_bot/engine/speed.py`
- Test: `tests/test_speed.py` (create if absent)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_speed.py
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import FieldState, PokemonState
from showdown_bot.engine.belief.hypotheses import SpreadPreset


class FakeBackend:
    def __init__(self, spe):
        self.spe = spe
        self.calls = 0

    def stats_batch(self, specs):
        self.calls += 1
        return [{"spe": self.spe} for _ in specs]

    def types_batch(self, species):
        return [["Normal"] for _ in species]


def test_likely_speed_reads_scarf_only_from_item_for_speed():
    oracle = SpeedOracle(stats_backend=FakeBackend(spe=100))
    mon, field = PokemonState(species="Incineroar"), FieldState()
    preset = SpreadPreset(nature="Careful", evs={"hp": 252}, items=["Sitrus Berry"])
    assert oracle.likely_speed(mon, field, "p2", preset, "Choice Scarf") == 150   # scarf x1.5
    assert oracle.likely_speed(mon, field, "p2", preset, "Booster Energy") == 100  # booster != scarf speed
    assert oracle.likely_speed(mon, field, "p2", preset, None) == 100


def test_base_speed_is_cached():
    fb = FakeBackend(spe=100)
    oracle = SpeedOracle(stats_backend=fb)
    mon, field = PokemonState(species="Incineroar"), FieldState()
    preset = SpreadPreset(nature="Careful", evs={"hp": 252}, items=[])
    oracle.likely_speed(mon, field, "p2", preset, None)
    oracle.likely_speed(mon, field, "p2", preset, None)
    assert fb.calls == 1  # second call hit the cache
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_speed.py -q`
Expected: FAIL with `AttributeError: 'SpeedOracle' object has no attribute 'likely_speed'`

- [ ] **Step 3: Implement** — in `engine/speed.py`, `SpeedOracle.__init__` currently ends with `self.backend = stats_backend`. Add the cache right after it:

```python
        self.backend = stats_backend
        self._spe_cache: dict = {}
```
Then add these two methods to `SpeedOracle` (e.g. after `our_speed`):

```python
    def _base_speed(self, species: str, nature: str, evs: dict) -> int:
        """Final Speed stat (no in-battle mods) for a spread, cached. VGC level
        50, IVs 31 for any stat the set doesn't specify."""
        key = (species, nature, tuple(sorted(evs.items())))
        cached = self._spe_cache.get(key)
        if cached is None:
            spec = CalcMon(species=species, level=50, nature=nature, evs=dict(evs), ivs={"spe": 31})
            cached = self.backend.stats_batch([spec])[0]["spe"]
            self._spe_cache[key] = cached
        return cached

    def likely_speed(self, mon, field, side, preset, item_for_speed) -> int:
        """Realistic point Speed from a curated set. ONLY Choice Scarf is read
        from the item; everything else (boosts/Tailwind/para/booster) comes from
        observed state -- a curated Booster Energy never inflates speed here."""
        base = self._base_speed(mon.species, preset.nature, preset.evs)
        mods = speed_modifiers_from_state(mon, field, side)
        mods["scarf"] = item_for_speed in ("Choice Scarf", "choicescarf")
        return effective_speed(base, **mods)
```

- [ ] **Step 4: Run tests then the full suite**

Run: `cd showdown_bot && python -m pytest tests/test_speed.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (suite was 233; expect 235).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/speed.py showdown_bot/tests/test_speed.py
git commit -m "feat(speed): SpeedOracle.likely_speed (cached, scarf-from-item-only)"
```

---

## Task 2: `_item_for_speed` + `_opponent_speed` + thread `opp_sets`

**Files:**
- Modify: `src/showdown_bot/battle/opponent.py`, `src/showdown_bot/battle/decision.py`
- Test: `tests/test_opponent.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_opponent.py`)

```python
def test_item_for_speed_precedence():
    from showdown_bot.battle.opponent import _item_for_speed
    from showdown_bot.engine.state import PokemonState
    assert _item_for_speed(PokemonState(species="Landorus-Therian"), ["Choice Scarf"]) == "Choice Scarf"  # unknown -> curated
    revealed = PokemonState(species="Landorus-Therian", item="Sitrus Berry", item_known=True)
    assert _item_for_speed(revealed, ["Choice Scarf"]) == "Sitrus Berry"                                   # revealed wins
    lost = PokemonState(species="Landorus-Therian", item=None, item_known=True, item_lost=True)
    assert _item_for_speed(lost, ["Choice Scarf"]) is None                                                 # known-lost -> None


class _SpeFake:
    def stats_batch(self, specs):
        return [{"spe": 100} for _ in specs]

    def types_batch(self, species):
        return [["Normal"] for _ in species]


def test_opponent_speed_curated_vs_fallback(monkeypatch):
    from showdown_bot.battle.opponent import _opponent_speed
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.engine.state import PokemonState, FieldState
    from showdown_bot.engine.belief.hypotheses import (
        SpeciesSpreads, SpreadPreset, load_spread_book,
    )
    from showdown_bot.engine.format_config import load_format_config

    oracle = SpeedOracle(stats_backend=_SpeFake())
    book = load_spread_book(load_format_config("gen9vgc2026regi").meta_path("default_spreads"))
    p = SpreadPreset(nature="Careful", evs={"hp": 252}, items=["Sitrus Berry"])  # non-scarf, no spe
    opp_sets = {"incineroar": SpeciesSpreads(offense=p, defense=p)}
    field = FieldState()
    inc = PokemonState(species="Incineroar")        # curated
    tor = PokemonState(species="Tornadus")          # un-curated

    monkeypatch.setenv("SHOWDOWN_OPP_SPEED", "1")
    curated = _opponent_speed(inc, field, "p2", speed_oracle=oracle, book=book, opp_sets=opp_sets)
    fallback = _opponent_speed(tor, field, "p2", speed_oracle=oracle, book=book, opp_sets=opp_sets)
    monkeypatch.setenv("SHOWDOWN_OPP_SPEED", "0")
    knob_off = _opponent_speed(inc, field, "p2", speed_oracle=oracle, book=book, opp_sets=opp_sets)

    assert curated == 100      # likely, non-scarf
    assert fallback == 150     # un-curated -> opponent_range.max (base 100, scarf assumed -> x1.5)
    assert knob_off == 150     # knob off -> always max
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_opponent.py::test_item_for_speed_precedence -q`
Expected: FAIL with `ImportError: cannot import name '_item_for_speed'`

- [ ] **Step 3: Add `import os`** to `opponent.py` (not currently imported). It must go AFTER the `from __future__ import annotations` line (that line must stay first) and before the `from dataclasses import ...` line:
```python
from __future__ import annotations

import os

from dataclasses import dataclass, field
```

- [ ] **Step 4: Add the two helpers** to `opponent.py` (module level, e.g. just above `def predict_responses`):

```python
def _item_for_speed(mon, curated_items):
    """Item that determines Scarf speed. Revealed item / known-absence beats the
    curated item; the curated item is used only when the item is unknown."""
    if getattr(mon, "item_lost", False):
        return None
    if mon.item_known:
        return mon.item
    return curated_items[0] if curated_items else None


def _opponent_speed(mon, field, opp_side, *, speed_oracle, book, opp_sets):
    """Resolver speed for an opponent mon: the realistic likely-set point for a
    curated species (Scarf-aware), else the pessimistic opponent_range.max."""
    use_likely = (
        os.environ.get("SHOWDOWN_OPP_SPEED", "1") != "0"
        and opp_sets
        and to_id(mon.species) in opp_sets
    )
    if use_likely:
        preset = opp_sets[to_id(mon.species)].defense
        return speed_oracle.likely_speed(
            mon, field, opp_side, preset, _item_for_speed(mon, preset.items)
        )
    return speed_oracle.opponent_range(mon, field, opp_side, book=book).max
```

- [ ] **Step 5: Add `opp_sets` to `predict_responses`** — its signature ends with `threatened_slots: set[str] | None = None,`. Add after it:
```python
    opp_sets: dict | None = None,
```
And replace the inner `opp_speed` closure body. It currently reads:
```python
    def opp_speed(slot: str) -> int:
        if speed_oracle is None or book is None:
            return 0
        return speed_oracle.opponent_range(opp_mons[slot], field, opp_side, book=book).max
```
with:
```python
    def opp_speed(slot: str) -> int:
        if speed_oracle is None or book is None:
            return 0
        return _opponent_speed(
            opp_mons[slot], field, opp_side, speed_oracle=speed_oracle, book=book, opp_sets=opp_sets
        )
```

- [ ] **Step 6: Thread `opp_sets` from the decision** — in `decision.py` the `predict_responses(...)` call currently reads:
```python
    opp_resps = predict_responses(
        state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
        dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
    )
```
Add `opp_sets=opp_sets,`:
```python
    opp_resps = predict_responses(
        state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
        dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
        opp_sets=opp_sets,
    )
```

- [ ] **Step 7: Run the new tests then the full suite**

Run: `cd showdown_bot && python -m pytest tests/test_opponent.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (suite was 235; expect 237).

- [ ] **Step 8: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/opponent.py showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/tests/test_opponent.py
git commit -m "feat(opponent): realistic curated speed (item precedence + SHOWDOWN_OPP_SPEED gate)"
```

---

## Task 3: A/B guardrail gauntlet

- [ ] **Step 1: A/B (local server up on :8000), opp-speed on vs off** — `OPP_SETS` on for both; reuse the scratchpad `ab_run.py` pattern:

```bash
cd showdown_bot && SHOWDOWN_OPP_SPEED=1 python <ab_run.py> 16 <on.log>
cd showdown_bot && SHOWDOWN_OPP_SPEED=0 python <ab_run.py> 16 <off.log>
```
Aggregate winrate + diagnostic metrics; read whether the bot now treats its fast mons as outspeeding (speed-control value, more committed first-move lines) — metrics, not just winrate (mirror is a guardrail; see spec).

- [ ] **Step 2: Record the result** in session notes / memory. No code change.

---

## Self-Review notes
- **Spec coverage:** likely_speed + cache + level50/ivs31 (T1); item precedence guardrail 1 + `_item_for_speed` (T2); Booster-not-blind guardrail 2 (likely_speed reads only Scarf — T1 Booster assertion); cache guardrail 3 (T1); knob guardrail 5 + fallback (T2); threading (T2); A/B (T3). All spec tests covered.
- **Type consistency:** `likely_speed(mon, field, side, preset, item_for_speed)`, `_base_speed(species, nature, evs)`, `_item_for_speed(mon, curated_items)`, `_opponent_speed(mon, field, opp_side, *, speed_oracle, book, opp_sets)`, `predict_responses(..., opp_sets=None)` — consistent across tasks.
- **Note:** Booster-not-blind is verified by T1's `"Booster Energy" -> 100` assertion (only Choice Scarf sets `scarf=True`); the state-driven `booster_speed` is untouched.

# Opponent Likely-Sets (Slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model curated common opponents with one probable spread+item in the damage calc instead of worst-case max-offense AND max-bulk, cutting false threat.

**Architecture:** A curated `likely_sets.yaml` → `load_likely_sets` (canonical keys, fail-loud validation) → an `opp_sets` override in `DamageModel` that mirrors the Stage-C `our_spreads` path. Revealed info still wins (the existing `item_known` gate), un-curated species stay worst-case, and `SHOWDOWN_OPP_SETS` gates a clean A/B.

**Tech Stack:** Python (PyYAML, pytest); spec at `docs/superpowers/specs/2026-06-29-opponent-likely-sets-design.md`. Run tests from `showdown_bot/`. `to_id` lives in `engine/state.py`; the calc backend's `types_batch([species])` returns `[]` for an unknown species (used as the species validator).

---

## File Structure

- `src/showdown_bot/engine/belief/hypotheses.py` — add `load_likely_sets(path, *, is_valid_species=None)` next to `load_spread_book`.
- `src/showdown_bot/battle/evaluate.py` — `DamageModel` gains `opp_sets` (sibling of `our_spreads`), keyed by `to_id(species)`.
- `src/showdown_bot/battle/decision.py` — thread `opp_sets` through `heuristic_choose_for_request`.
- `config/formats/meta/likely_sets.yaml` — curated sets (the 6 fixed-team species; extend later).
- `config/formats/gen9vgc2024regg.yaml`, `config/formats/gen9vgc2026regi.yaml` — register the `likely_sets` meta path.
- `src/showdown_bot/client/gauntlet.py`, `src/showdown_bot/client/runner.py` — load `opp_sets` (knob + backend validator), thread it.
- Tests: `tests/test_likely_sets.py`, `tests/test_evaluate.py`.

---

## Task 1: `load_likely_sets` loader (canonical keys + fail-loud validation)

**Files:**
- Modify: `src/showdown_bot/engine/belief/hypotheses.py`
- Test: `tests/test_likely_sets.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_likely_sets.py
from pathlib import Path

import pytest

from showdown_bot.engine.belief.hypotheses import load_likely_sets

_YAML = """
species:
  Incineroar:
    set_id: bulky_support
    nature: Careful
    evs: {hp: 252, atk: 4, spd: 252}
    item: Sitrus Berry
  Landorus-Therian:
    nature: Jolly
    evs: {atk: 252, spe: 252}
    # item omitted -> no item prior
"""


def _write(tmp_path, text):
    p = tmp_path / "likely_sets.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_per_species_spreads_keyed_by_id(tmp_path):
    sets = load_likely_sets(_write(tmp_path, _YAML))
    inc = sets["incineroar"]                       # keyed by to_id
    assert inc.offense == inc.defense              # single set, both roles
    assert inc.defense.nature == "Careful"
    assert inc.defense.evs == {"hp": 252, "atk": 4, "spd": 252}
    assert inc.defense.items == ["Sitrus Berry"]


def test_omitted_item_means_no_item_prior(tmp_path):
    sets = load_likely_sets(_write(tmp_path, _YAML))
    assert sets["landorustherian"].defense.items == []   # item omitted


def test_missing_file_is_empty(tmp_path):
    assert load_likely_sets(tmp_path / "nope.yaml") == {}


def test_invalid_species_key_fails_validation(tmp_path):
    bad = "species:\n  Landorus-T:\n    nature: Jolly\n    evs: {atk: 252}\n"
    known = {"Incineroar", "Landorus-Therian"}
    with pytest.raises(ValueError, match="unknown species"):
        load_likely_sets(_write(tmp_path, bad), is_valid_species=lambda s: s in known)


def test_valid_keys_pass_injected_validator(tmp_path):
    known = {"Incineroar", "Landorus-Therian"}
    sets = load_likely_sets(_write(tmp_path, _YAML), is_valid_species=lambda s: s in known)
    assert set(sets) == {"incineroar", "landorustherian"}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_likely_sets.py -q`
Expected: FAIL with `ImportError: cannot import name 'load_likely_sets'`

- [ ] **Step 3: Implement the loader** (append to `engine/belief/hypotheses.py`; `yaml`, `Path`, `SpreadPreset`, `SpeciesSpreads` are already imported there)

```python
def load_likely_sets(path: Path, *, is_valid_species=None) -> dict[str, SpeciesSpreads]:
    """Curated probable opponent sets. Returns {to_id(species): SpeciesSpreads}
    with both presets = the single likely set. Keys are canonicalized via to_id;
    when ``is_valid_species`` is given, an unknown species key raises (fail loud).
    Missing file -> empty. nature/evs are required; item is optional (no prior)."""
    from showdown_bot.engine.state import to_id

    if not Path(path).exists():
        return {}
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, SpeciesSpreads] = {}
    for name, entry in (data.get("species") or {}).items():
        if is_valid_species is not None and not is_valid_species(name):
            raise ValueError(f"likely_sets: unknown species key {name!r}")
        if "nature" not in entry or "evs" not in entry:
            raise ValueError(f"likely_sets: {name!r} missing nature/evs")
        item = entry.get("item")
        preset = SpreadPreset(
            nature=entry["nature"],
            evs={k: int(v) for k, v in (entry.get("evs") or {}).items()},
            items=[item] if item else [],
        )
        out[to_id(name)] = SpeciesSpreads(offense=preset, defense=preset)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/test_likely_sets.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/belief/hypotheses.py showdown_bot/tests/test_likely_sets.py
git commit -m "feat(belief): load_likely_sets - canonical keys, fail-loud species validation"
```

---

## Task 2: `opp_sets` override in DamageModel + decision threading

**Files:**
- Modify: `src/showdown_bot/battle/evaluate.py` (`DamageModel`), `src/showdown_bot/battle/decision.py` (`heuristic_choose_for_request`)
- Test: `tests/test_evaluate.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_evaluate.py`; `DamageModel`, `load_spread_book`, `load_format_config`, `PokemonState`, `BattleState`, `get_move_meta` are already imported)

```python
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset


def _opp_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def _likely_incin():
    p = SpreadPreset(nature="Careful", evs={"hp": 252, "atk": 4, "spd": 252}, items=["Sitrus Berry"])
    return {"incineroar": SpeciesSpreads(offense=p, defense=p)}


def test_opp_sets_overrides_opponent_hypothesis():
    st = _opp_state()
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    real = DamageModel(st, "p1", "p2", book=book, opp_sets=_likely_incin())
    # opponent (p2) defender now uses the likely set, not the worst-case book preset
    d = real.hyps[("p2", "a")].as_defender()
    assert d.nature == "Careful"
    assert d.evs == {"hp": 252, "atk": 4, "spd": 252}   # the likely set, not the book preset


def test_opp_sets_none_is_unchanged():
    st = _opp_state()
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    a = DamageModel(st, "p1", "p2", book=book)
    b = DamageModel(st, "p1", "p2", book=book, opp_sets=None)
    assert a.hyps[("p2", "a")].as_defender().nature == b.hyps[("p2", "a")].as_defender().nature


def test_revealed_item_beats_likely_item():
    st = _opp_state()
    st.sides["p2"]["a"].item = "Assault Vest"
    st.sides["p2"]["a"].item_known = True
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    model = DamageModel(st, "p1", "p2", book=book, opp_sets=_likely_incin())
    # likely set says Sitrus, but the revealed Assault Vest wins
    assert model.hyps[("p2", "a")].as_defender().item == "Assault Vest"


def test_uncurated_opponent_stays_worstcase():
    st = _opp_state()
    st.sides["p2"]["a"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)  # not curated here
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    base = DamageModel(st, "p1", "p2", book=book)
    real = DamageModel(st, "p1", "p2", book=book, opp_sets=_likely_incin())
    assert real.hyps[("p2", "a")].as_defender().nature == base.hyps[("p2", "a")].as_defender().nature
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_evaluate.py::test_opp_sets_overrides_opponent_hypothesis -q`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'opp_sets'`

- [ ] **Step 3: Add `to_id` to evaluate.py's state import**

Change `from showdown_bot.engine.state import BattleState, FieldState` to:
```python
from showdown_bot.engine.state import BattleState, FieldState, to_id
```

- [ ] **Step 4: Add the `opp_sets` param + override** (`DamageModel.__init__`)

Change the signature line `our_spreads: dict | None = None,` to add a sibling:
```python
        our_spreads: dict | None = None,
        opp_sets: dict | None = None,
```
And replace the hypothesis-building loop body so the opponent branch is a sibling of the our-side branch:
```python
        self.hyps = {}
        for side, slots in state.sides.items():
            for slot, mon in slots.items():
                hyp = hypothesis_from_state(mon, book)
                if side == our_side and our_spreads and mon.species in our_spreads:
                    hyp.spreads = our_spreads[mon.species]
                elif side == opp_side and opp_sets and to_id(mon.species) in opp_sets:
                    hyp.spreads = opp_sets[to_id(mon.species)]
                self.hyps[(side, slot)] = hyp
```

- [ ] **Step 5: Thread `opp_sets` through the decision** (`decision.py`)

In `heuristic_choose_for_request`, add the parameter (after `our_spreads: dict | None = None,`):
```python
    our_spreads: dict | None = None,
    opp_sets: dict | None = None,
```
And pass it into the `DamageModel(...)` construction (which currently passes `our_spreads=our_spreads`):
```python
    model = DamageModel(
        state, our_side, opp_side, book=book, oracle=oracle, field=state.field,
        our_spreads=our_spreads, opp_sets=opp_sets,
    )
```

- [ ] **Step 6: Run the new tests then the full suite**

Run: `cd showdown_bot && python -m pytest tests/test_evaluate.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (suite was 223; expect ~227).

- [ ] **Step 7: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/tests/test_evaluate.py
git commit -m "feat(eval): opp_sets override for opponent mons (mirrors our_spreads; revealed item wins)"
```

---

## Task 3: curated `likely_sets.yaml` + register the meta path

**Files:**
- Create: `config/formats/meta/likely_sets.yaml`
- Modify: `config/formats/gen9vgc2024regg.yaml`, `config/formats/gen9vgc2026regi.yaml`
- Test: `tests/test_likely_sets.py`

- [ ] **Step 1: Create `config/formats/meta/likely_sets.yaml`** (the 6 fixed-team species; extend to more common Reg-G species later — same schema)

```yaml
# Curated probable opponent sets for common Reg-G species. nature/evs = spread
# (used when the species is curated + the field is unknown); item = optional
# separate prior (a revealed item always wins). Keys must be canonical dex species
# names. set_id/source/confidence/item_confidence are debug metadata only.
species:
  Incineroar:
    set_id: bulky_support
    nature: Careful
    evs: {hp: 252, atk: 4, spd: 252}
    item: Sitrus Berry
    item_confidence: medium
    source: curated_reg_g
    confidence: high
  Rillaboom:
    set_id: av_grassy
    nature: Adamant
    evs: {hp: 252, atk: 252, spd: 4}
    item: Assault Vest
    item_confidence: medium
    source: curated_reg_g
    confidence: medium
  Flutter Mane:
    set_id: booster_fast
    nature: Timid
    evs: {spa: 252, spd: 4, spe: 252}
    item: Booster Energy
    item_confidence: low
    source: curated_reg_g
    confidence: high
  Landorus-Therian:
    set_id: scarf_physical
    nature: Jolly
    evs: {atk: 252, def: 4, spe: 252}
    item: Choice Scarf
    item_confidence: low
    source: curated_reg_g
    confidence: medium
  Tornadus:
    set_id: tailwind_support
    nature: Timid
    evs: {hp: 252, spa: 4, spe: 252}
    item: Covert Cloak
    item_confidence: low
    source: curated_reg_g
    confidence: medium
  Urshifu-Rapid-Strike:
    set_id: sash_offense
    nature: Jolly
    evs: {atk: 252, def: 4, spe: 252}
    item: Focus Sash
    item_confidence: low
    source: curated_reg_g
    confidence: medium
```

- [ ] **Step 2: Register the meta path** — add this line under `meta_paths:` in BOTH `config/formats/gen9vgc2024regg.yaml` and `config/formats/gen9vgc2026regi.yaml`:

```yaml
  likely_sets: meta/likely_sets.yaml
```

- [ ] **Step 3: Add a test that the curated file loads + has the team species** (append to `tests/test_likely_sets.py`)

```python
def test_curated_file_loads_and_has_team_species():
    from showdown_bot.engine.format_config import load_format_config
    path = load_format_config("gen9vgc2024regg").meta_path("likely_sets")
    sets = load_likely_sets(path)
    for sid in ("incineroar", "rillaboom", "fluttermane", "landorustherian",
                "tornadus", "urshifurapidstrike"):
        assert sid in sets
    assert sets["fluttermane"].defense.evs == {"spa": 252, "spd": 4, "spe": 252}
```

- [ ] **Step 4: Run it + full suite**

Run: `cd showdown_bot && python -m pytest tests/test_likely_sets.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/config/formats/meta/likely_sets.yaml showdown_bot/config/formats/gen9vgc2024regg.yaml showdown_bot/config/formats/gen9vgc2026regi.yaml showdown_bot/tests/test_likely_sets.py
git commit -m "feat(data): curated likely_sets.yaml (fixed-team species) + register meta path"
```

---

## Task 4: load + knob + validator in gauntlet & runner

**Files:**
- Modify: `src/showdown_bot/client/gauntlet.py`, `src/showdown_bot/client/runner.py`

A small shared loader keeps it DRY. The species validator uses the calc backend
(`types_batch([s])` returns `[]` for an unknown species).

- [ ] **Step 1: Add a loader helper** (append to `engine/belief/hypotheses.py`)

```python
def load_opp_sets_for_format(format_id: str):
    """Load curated opponent likely-sets for a format, validating species against
    the calc backend. Returns {} (off, worst-case) when SHOWDOWN_OPP_SETS=0, the
    file is missing, or anything fails -- a broken prior never silently activates."""
    import os

    from showdown_bot.engine.format_config import load_format_config

    if os.environ.get("SHOWDOWN_OPP_SETS", "1") == "0":
        return {}
    try:
        path = load_format_config(format_id).meta_path("likely_sets")
        from showdown_bot.engine.calc.client import SubprocessCalcBackend

        backend = SubprocessCalcBackend()

        def is_valid(species: str) -> bool:
            return bool(backend.types_batch([species])[0])

        return load_likely_sets(path, is_valid_species=is_valid)
    except Exception:  # noqa: BLE001 - missing/invalid file or backend -> off
        return {}
```

- [ ] **Step 2: Wire it into the gauntlet** (`gauntlet.py`)

Import it at the top (next to the existing `load_spread_book` import):
```python
from showdown_bot.engine.belief.hypotheses import SpreadBook, load_opp_sets_for_format, load_spread_book
```
In `run_local_gauntlet`, after `book = load_spread_book(...)`, add:
```python
        opp_sets = load_opp_sets_for_format(format_id)
```
Pass `opp_sets=opp_sets` into BOTH `_Client(...)` constructions, store it in `_Client.__init__` (`self.opp_sets = opp_sets`), and in `handle_request` add `opp_sets=self.opp_sets` to the `agent_choose(...)` call. In `agent_choose`, add an `opp_sets: dict | None = None` parameter and pass `opp_sets=opp_sets` into the `choose_with_fallback(...)` call (it already forwards `our_spreads`). Give `_Client.__init__` an `opp_sets=None` keyword parameter.

- [ ] **Step 3: Wire it into the runner** (`runner.py`)

Add a module global `_opp_sets: dict | None = None` (next to `_our_spreads`), set it in `run_ladder_search` and `run_challenge` after `_our_spreads = ...`:
```python
    _opp_sets = load_opp_sets_for_format(settings.format_id)
```
(add `_opp_sets` to each function's `global` statement and import `load_opp_sets_for_format`). In `handle_battle_message`, add `opp_sets=_opp_sets` to the `choose_with_fallback(...)` call.

- [ ] **Step 4: Run the full suite**

Run: `cd showdown_bot && python -m pytest -q`
Expected: PASS (no behavior change in unit tests; gauntlet/runner aren't unit-exercised here).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/belief/hypotheses.py showdown_bot/src/showdown_bot/client/gauntlet.py showdown_bot/src/showdown_bot/client/runner.py
git commit -m "feat(client): load opponent likely-sets (SHOWDOWN_OPP_SETS knob + backend-validated)"
```

---

## Task 5: A/B guardrail gauntlet

- [ ] **Step 1: Sanity that opp_sets loads + validates against the backend** (server need not be up)

Run: `cd showdown_bot && python -c "from showdown_bot.engine.belief.hypotheses import load_opp_sets_for_format; s=load_opp_sets_for_format('gen9vgc2024regg'); print(sorted(s)[:6], len(s))"`
Expected: prints the 6 canonical ids, count 6 (validation passed — no exception).

- [ ] **Step 2: A/B (local server up on :8000), opp_sets on vs off** — reuse the scratchpad `ab_run.py` pattern:

```bash
cd showdown_bot && SHOWDOWN_OPP_SETS=1 python <ab_run.py> 16 <on.log>
cd showdown_bot && SHOWDOWN_OPP_SETS=0 python <ab_run.py> 16 <off.log>
```
Aggregate winrate + the diagnostic metrics (predicted-incoming, must_react%, Protect%, targeted%). **Read the metrics, not just winrate** — the question is whether realistic opponent modeling lowers false threat / commits to more attacks. The mirror winrate is a guardrail only (it rewards recklessness; see spec).

- [ ] **Step 3: Record the result** in the session notes / memory. No code change from this step.

---

## Self-Review notes

- **Spec coverage:** data file + canonical/validated loader (T1, T3); opp_sets override mirroring our_spreads + revealed-item-wins precedence + worst-case fallback (T2); threading + knob + backend validator + default-on-only-if-valid (T4); A/B guardrail (T5); all spec tests present (loader, override, revealed-item-wins, fallback, canonicalization/invalid-key, opp_sets=None bit-identical).
- **Type consistency:** `load_likely_sets(path, *, is_valid_species=None)`, `load_opp_sets_for_format(format_id)`, `DamageModel(..., opp_sets=None)`, `heuristic_choose_for_request(..., opp_sets=None)`, opp_sets keyed by `to_id` and looked up via `to_id(mon.species)` — consistent across tasks.
- **Note:** `gen9vgc2024regg.yaml` is currently untracked in git; Task 3 Step 5 stages it (committing it is fine — it's the format the gauntlet uses).

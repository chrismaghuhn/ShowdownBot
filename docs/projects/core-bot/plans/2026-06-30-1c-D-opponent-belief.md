# Phase 3 Slice 1c-D: limited-view-safe opponent belief — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the limited-view-safe opponent belief for the rollout teacher: two explicit
builders (`build_known_side` / `build_opponent_belief`) + a thin `build_belief_for_side`
dispatcher producing the `roster`/`movesets`/`stats` triple, plus a new `move_priors` data
source — so the rollout opponent plays a prior-based belief, never hidden ground truth.

**Architecture:** The opponent builder is a separate function whose signature proves it can't
read our team or hidden bench (no `known_team` param; reads only revealed active slots + public
priors). A `BeliefSide` DTO carries the triple + `quality` provenance flags. New
`move_priors.yaml` (species → ordered moves), kept separate from `likely_sets` (spreads).

**Tech Stack:** Python stdlib + PyYAML. Spec: `docs/projects/core-bot/specs/2026-06-30-1c-D-opponent-belief-design.md`.
Reuses: `engine/belief/hypotheses.py` (`load_likely_sets`, `load_opp_sets_for_format`,
`SpeciesSpreads`/`SpreadPreset`), `engine/speed.py` (`SpeedOracle.likely_speed(mon, field,
side, preset, item_for_speed)`), `engine/state.py` (`to_id`, `PokemonState`, `state.sides`),
`models/request.py` (`PokemonSlot`: ident/details/condition/active/stats/moves/item),
`learning/decide_adapter.py` + `learning/rollout.py` (consumers). Run tests from `showdown_bot/`.

**Grounded facts (verified):** belief triple shape = `roster:{ident→PokemonState}` (bench
only), `movesets:{ident|species→[move_id]}`, `stats:{ident|species→{"spe":int}}` (from
`tests/test_decide_adapter.py`). Active slots are `"a"`/`"b"`; **`state.side(side)` returns
`self.sides[side]` RAW (no active-filter)** → the opp builder must iterate the literal tuple
`("a","b")`, never the raw dict, so injected extra keys can't be read as bench.

---

## File Structure
- Create: `engine/belief/move_priors.py` — `load_move_priors` + `load_move_priors_for_format`.
- Create: a curated `move_priors.yaml` in the format meta dir (mirror where `likely_sets.yaml` lives).
- Create: `learning/belief_builder.py` — `BeliefSide`, `_quality`, `FALLBACK_BELIEF_MOVE`,
  `build_known_side`, `build_opponent_belief`, `build_belief_for_side`.
- Tests: `tests/test_move_priors.py`, `tests/test_belief_builder.py`.

---

## Task D1: `move_priors` loader + curated data

**Files:** Create `engine/belief/move_priors.py`, the `move_priors.yaml`; Test `tests/test_move_priors.py`.

- [ ] **Step 1: explore** — read `engine/belief/hypotheses.py` `load_likely_sets` (lines ~152)
  and `load_opp_sets_for_format` (lines ~179) to MIRROR their structure exactly: `to_id` import
  from `showdown_bot.engine.state`, the `yaml.safe_load` + `data.get("species")` shape, the
  `meta_path("likely_sets")` pattern (you will use `meta_path("move_priors")`), and where the
  real `likely_sets.yaml` file lives (put `move_priors.yaml` beside it).

- [ ] **Step 2: failing tests** (`tests/test_move_priors.py`)

```python
from pathlib import Path
from showdown_bot.engine.belief.move_priors import load_move_priors


def test_missing_file_returns_empty(tmp_path):
    assert load_move_priors(tmp_path / "nope.yaml") == {}


def test_keys_and_moves_are_to_id_normalized(tmp_path):
    p = tmp_path / "mp.yaml"
    p.write_text("species:\n  Flutter Mane:\n    - Moonblast\n    - Shadow Ball\n", encoding="utf-8")
    out = load_move_priors(p)
    assert out == {"fluttermane": ["moonblast", "shadowball"]}


def test_duplicate_moves_deduped_in_order(tmp_path):
    p = tmp_path / "mp.yaml"
    p.write_text("species:\n  Incineroar:\n    - Fake Out\n    - Fake Out\n    - Knock Off\n", encoding="utf-8")
    assert load_move_priors(p) == {"incineroar": ["fakeout", "knockoff"]}


def test_load_for_format_delegates_and_missing_is_empty(tmp_path, monkeypatch):
    # the REAL runtime path: format_config.meta_path("move_priors") -> load_move_priors.
    # Mirror how test_*opp_sets* (likely_sets) tests exercise load_opp_sets_for_format;
    # monkeypatch load_format_config so a missing resolved file returns {}.
    import showdown_bot.engine.belief.move_priors as mod
    # (ground the exact monkeypatch target from load_opp_sets_for_format's import site)
    ...  # assert load_move_priors_for_format(<fmt>) == {} when meta_path points at a missing file
```

- [ ] **Step 3: run → FAIL.** `cd showdown_bot && python -m pytest tests/test_move_priors.py -q`

- [ ] **Step 4: implement** `engine/belief/move_priors.py`:

```python
from __future__ import annotations
from pathlib import Path
import yaml


def load_move_priors(path: Path) -> dict[str, list[str]]:
    """Curated per-species move priors. {to_id(species): [to_id(move), ...]} with
    deterministic dedupe (first occurrence wins). Missing file -> {}. SEPARATE from
    likely_sets (which carries spreads); move_priors carries only ordered move ids."""
    from showdown_bot.engine.state import to_id

    if not Path(path).exists():
        return {}
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, list[str]] = {}
    for name, moves in (data.get("species") or {}).items():
        seen: set[str] = set()
        ordered: list[str] = []
        for m in moves or []:
            mid = to_id(m)
            if mid not in seen:
                seen.add(mid)
                ordered.append(mid)
        out[to_id(name)] = ordered
    return out


def load_move_priors_for_format(format_id: str):
    """Mirror load_opp_sets_for_format: resolve meta_path('move_priors') for the format.
    Missing -> {}."""
    # Ground the EXACT body against load_opp_sets_for_format in hypotheses.py and copy its
    # format-config + meta_path pattern, calling load_move_priors(path).
    ...
```
Ground `load_move_priors_for_format` against the real `load_opp_sets_for_format` (copy its
`load_format_config(format_id).meta_path(...)` pattern). Create a small `move_priors.yaml`
beside `likely_sets.yaml` with 2-3 curated species (enough for the D2/D3 tests).

- [ ] **Step 5: run → PASS** + full suite (`cd showdown_bot && python -m pytest -q`, baseline
  365). **Step 6: commit** `feat(belief): load_move_priors + curated move_priors.yaml (separate from likely_sets)`.

---

## Task D2a: `BeliefSide` + `_quality` + `build_known_side`

**Files:** Create `learning/belief_builder.py`; Test `tests/test_belief_builder.py`.

- [ ] **Step 1: explore** — `models/request.py` `PokemonSlot` (confirm `ident`, `details`,
  `condition`, `active`, `stats`, `moves`); how species is parsed from `details` (e.g.
  `"Incineroar, L50, M"` → `"Incineroar"`); and how `engine/state.py` builds a `PokemonState`
  from a slot/condition (reuse that parse for the bench PokemonState — species + hp/max_hp).

- [ ] **Step 2: failing tests** (`tests/test_belief_builder.py`)

```python
from showdown_bot.learning.belief_builder import BeliefSide, _quality, build_known_side


def test_quality_ok_when_no_flags():
    assert _quality() == ("ok",)


def test_quality_sorted_deduped_flags():
    assert _quality("weak_speed_fallback", "no_move_prior", "no_move_prior") == \
        ("no_move_prior", "weak_speed_fallback")


def test_build_known_side_includes_full_team(known_team_slots):
    # known_team_slots = a request's side.pokemon (active + bench)
    bs = build_known_side(known_team_slots)
    assert isinstance(bs, BeliefSide)
    # bench mons (active=False) present in roster; movesets/stats cover ALL team mons
    assert bs.roster and all(not _is_active(slot) for slot in <bench>)
    assert all(q == ("ok",) for q in bs.quality.values())   # our team fully known
```
(Build `known_team_slots` from a real request fixture — reuse whatever fixture the 1b/1c tests
use to get a `BattleRequest`; `req.side.pokemon` is the list. If none exists, construct a couple
of `PokemonSlot`s directly.)

- [ ] **Step 3: run → FAIL. Step 4: implement** in `learning/belief_builder.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from showdown_bot.engine.state import PokemonState, to_id

FALLBACK_BELIEF_MOVE = "tackle"   # MUST exist in _move_table() + pass enumerate_my_actions (verify in D2b)


@dataclass(frozen=True)
class BeliefSide:
    # frozen protects the bindings, NOT the inner containers; builders return FRESH
    # dicts/lists and callers treat BeliefSide as immutable (no shared mutation).
    roster: dict[str, PokemonState]        # bench only (opponent: always {})
    movesets: dict[str, list[str]]         # ident|species -> ordered move ids
    stats: dict[str, dict[str, int]]       # ident|species -> {"spe": int}
    quality: dict[str, tuple[str, ...]]    # key -> belief-quality flags


def _quality(*flags: str) -> tuple[str, ...]:
    return ("ok",) if not flags else tuple(sorted(set(flags)))


def build_known_side(team_slots) -> BeliefSide:
    """Our side: the full known team. team_slots = req.side.pokemon (list[PokemonSlot])."""
    roster: dict[str, PokemonState] = {}
    movesets: dict[str, list[str]] = {}
    stats: dict[str, dict[str, int]] = {}
    quality: dict[str, tuple[str, ...]] = {}
    for slot in team_slots:
        ident = slot.ident
        movesets[ident] = list(slot.moves)
        stats[ident] = {"spe": int(slot.stats["spe"])}   # ground exact stats access (dict vs attr)
        quality[ident] = _quality()                       # fully known
        if not slot.active:
            roster[ident] = <PokemonState from the bench slot>   # ground species/hp parse
    return BeliefSide(roster, movesets, stats, quality)
```
Ground the `PokemonSlot` species/stats/condition access + the bench `PokemonState`
construction against the real models. **Step 5:** PASS + suite. **Step 6: commit**
`feat(learning): BeliefSide DTO + _quality helper + build_known_side (full known team)`.

---

## Task D2b: `build_opponent_belief` (active-only, prior-based, limited-view-safe)

**Files:** Modify `learning/belief_builder.py`; Test `tests/test_belief_builder.py`.

- [ ] **Step 1: verify** `FALLBACK_BELIEF_MOVE = "tackle"` is in `_move_table()` (from
  `engine/moves.py`); if not, pick another universal move that is, and update the constant. Read
  `SpeedOracle.likely_speed(mon, field, side, preset, item_for_speed)` (engine/speed.py:103) +
  `SpeciesSpreads`/`SpreadPreset` (a preset has `.nature`, `.evs`, `.items`).

- [ ] **Step 2: failing tests**

```python
def test_opp_roster_is_empty_and_keys_are_active_only(opp_state):
    bs = build_opponent_belief(opp_state, "p2", likely_sets={}, move_priors={})
    assert bs.roster == {}                              # empty bench
    # only the revealed active opp mons are keyed
    assert set(bs.movesets) == {<species of p2 actives>}


def test_revealed_moves_first_then_prior_fill_dedupe_cap4(opp_state_with_revealed):
    # active opp mon revealed ["fakeout"]; prior = [fakeout, knockoff, flareblitz, partingshot, uturn]
    mp = {"incineroar": ["fakeout", "knockoff", "flareblitz", "partingshot", "uturn"]}
    bs = build_opponent_belief(opp_state_with_revealed, "p2", likely_sets={}, move_priors=mp)
    assert bs.movesets["Incineroar"] == ["fakeout", "knockoff", "flareblitz", "partingshot"]  # revealed first, cap 4


def test_no_prior_no_revealed_uses_fallback_and_flags(opp_state_no_moves):
    from showdown_bot.learning.belief_builder import FALLBACK_BELIEF_MOVE
    bs = build_opponent_belief(opp_state_no_moves, "p2", likely_sets={}, move_priors={})
    sp = <species of the opp active>
    assert bs.movesets[sp] == [FALLBACK_BELIEF_MOVE]
    assert "no_move_prior" in bs.quality[sp]


def test_hidden_bench_like_entry_is_ignored(opp_state):
    # inject a non-active/bench-like key; the builder must NOT read it (only "a"/"b")
    opp_state.sides["p2"]["c"] = <a PokemonState>
    bs = build_opponent_belief(opp_state, "p2", likely_sets={}, move_priors={})
    assert all(k != <species of injected mon> for k in bs.movesets)


def test_build_opponent_belief_has_no_known_team_param():
    import inspect
    params = inspect.signature(build_opponent_belief).parameters
    assert "known_team" not in params and "team" not in params and "full_roster" not in params


def test_opp_belief_keys_are_consistent(opp_state):
    # PINNED: movesets, stats, quality all keyed by the SAME stable key (species, since
    # PokemonState has no ident). Same key set across all three dicts.
    bs = build_opponent_belief(opp_state, "p2", likely_sets={}, move_priors={})
    assert set(bs.movesets) == set(bs.stats) == set(bs.quality)
```

- [ ] **Step 3: run → FAIL. Step 4: implement** (append):

```python
def _merge_moveset(revealed, prior):
    flags: list[str] = []
    merged, seen = [], set()
    for m in [*revealed, *prior]:          # revealed FIRST (wins), then prior fill
        mid = to_id(m)
        if mid not in seen:
            seen.add(mid)
            merged.append(mid)
        if len(merged) == 4:               # cap 4
            break
    if not merged:                          # no prior AND no revealed -> weak fallback
        merged = [FALLBACK_BELIEF_MOVE]
        flags.append("no_move_prior")
    return merged, flags


def _belief_speed(mon, field, side, spreads, speed_oracle):
    # spreads = likely_sets.get(to_id(species)) : SpeciesSpreads | None
    if speed_oracle is not None and spreads is not None:
        preset = spreads.offense
        item = preset.items[0] if preset.items else None
        return speed_oracle.likely_speed(mon, field, side, preset, item), None
    if speed_oracle is not None:
        from showdown_bot.engine.belief.hypotheses import SpreadPreset
        return speed_oracle.likely_speed(mon, field, side, SpreadPreset("Hardy", {}), None), "weak_speed_fallback"
    return 0, "weak_speed_fallback"


def build_opponent_belief(state, opp_side, *, likely_sets, move_priors,
                          dex=None, book=None, speed_oracle=None) -> BeliefSide:
    """Opponent side: active-only, prior-based. Reads ONLY revealed active state + public
    priors. No known_team, no hidden bench. roster is always {}."""
    roster: dict[str, PokemonState] = {}            # empty bench (limited view)
    movesets: dict[str, list[str]] = {}
    stats: dict[str, dict[str, int]] = {}
    quality: dict[str, tuple[str, ...]] = {}
    field = state.field
    for slot in ("a", "b"):                          # ONLY the two active slots; ignore other keys
        mon = state.sides.get(opp_side, {}).get(slot)
        if mon is None:
            continue
        species = mon.species
        sid = to_id(species)
        # PokemonState.moves is a set[str] (unordered) -> sort for DETERMINISM. PokemonState
        # has NO ident field, so the stable key for all three dicts is `species` (pinned).
        merged, flags = _merge_moveset(sorted(mon.moves), move_priors.get(sid, []))
        spe, spe_flag = _belief_speed(mon, field, opp_side, likely_sets.get(sid), speed_oracle)
        if spe_flag:
            flags.append(spe_flag)
        movesets[species] = merged
        stats[species] = {"spe": spe}
        quality[species] = _quality(*flags)
    return BeliefSide(roster, movesets, stats, quality)
```
**Speed-flag note (judgment call, flag for the user):** this flags `"weak_speed_fallback"`
whenever `likely_sets` lacks the species (neutral-base path) OR no oracle — slightly stronger
than the literal "flag only the 0 case", because the whole point of `quality` is to mark when a
belief leaned on a weak prior. **Step 5:** PASS + suite. **Step 6: commit**
`feat(learning): build_opponent_belief - active-only prior-based belief (empty bench, 6-step merge, speed chain)`.

---

## Task D3: `build_belief_for_side` dispatcher + safety + integration

**Files:** Modify `learning/belief_builder.py`; Test `tests/test_belief_builder.py`.

- [ ] **Step 1: failing tests**

```python
def test_dispatcher_routes_to_known_for_our_side(state, known_team_slots):
    bs = build_belief_for_side(state, "p1", our_side="p1", known_team=known_team_slots,
                               likely_sets={}, move_priors={})
    assert bs.roster or bs.movesets           # known builder path (full team)


def test_dispatcher_routes_to_opponent_for_opp_side(state):
    bs = build_belief_for_side(state, "p2", our_side="p1", known_team=<our slots>,
                               likely_sets={}, move_priors={})
    assert bs.roster == {}                     # opponent builder path (empty bench)


def test_determinism(state, known_team_slots):
    a = build_belief_for_side(state, "p2", our_side="p1", known_team=known_team_slots, likely_sets={}, move_priors={})
    b = build_belief_for_side(state, "p2", our_side="p1", known_team=known_team_slots, likely_sets={}, move_priors={})
    assert a == b


def test_belief_feeds_rollout_labels(state, known_team_slots, move_meta, deps):
    # the deliverable: BeliefSide -> per-side dicts -> decide/rollout_labels accepts it.
    # NO export-swap, NO training: just prove the triple is consumable.
    from showdown_bot.learning.decide_adapter import decide
    us = build_belief_for_side(state, "p1", our_side="p1", known_team=known_team_slots, likely_sets={}, move_priors={})
    opp = build_opponent_belief(state, "p2", likely_sets={}, move_priors={}, speed_oracle=deps.get("speed_oracle"))
    roster = {"p1": us.roster, "p2": opp.roster}
    movesets = {"p1": us.movesets, "p2": opp.movesets}
    stats = {"p1": us.stats, "p2": opp.stats}
    ja = decide(state, "p1", roster=roster, movesets=movesets, stats=stats, move_meta=move_meta, deps=deps)
    assert ja is not None                       # the synthesized request was enumerable
```

- [ ] **Step 2: run → FAIL. Step 3: implement** (append):

```python
def build_belief_for_side(state, side, *, our_side, known_team, likely_sets, move_priors,
                          dex=None, book=None, speed_oracle=None) -> BeliefSide:
    """Thin dispatcher. our_side -> build_known_side; otherwise -> build_opponent_belief
    (which never receives known_team)."""
    if side == our_side:
        return build_known_side(known_team)
    return build_opponent_belief(state, side, likely_sets=likely_sets, move_priors=move_priors,
                                 dex=dex, book=book, speed_oracle=speed_oracle)
```
Note the dispatcher passes `known_team` ONLY to the known builder — the opponent builder's call
site has no `known_team` argument (structural limited-view). **Step 4:** PASS + full suite.
**Step 5: commit** `feat(learning): build_belief_for_side dispatcher + limited-view safety + rollout_labels integration`.

---

## Self-Review notes
- **Spec coverage:** move_priors data+loader (D1); BeliefSide+quality+known builder (D2a);
  opponent builder = empty bench + 6-step merge + speed chain + active-only (D2b); dispatcher +
  the 10 safety/integration tests (D3). The `inspect.signature` API guard, the literal-`("a","b")`
  hidden-bench test, and the `rollout_labels` integration are all in D2b/D3.
- **Pins concretized:** `FALLBACK_BELIEF_MOVE="tackle"` (verified in D2b step 1); `build_known_side`
  input = `req.side.pokemon` (list[PokemonSlot]); opp builder iterates literal `("a","b")` (because
  `state.side` is unfiltered); `_quality` deterministic (`sorted(set(...))`, `("ok",)` only when
  empty); speed chain likely_sets→neutral-base→0 with the flag note.
- **Grounded determinism/key fixes:** `PokemonState.moves` is a `set[str]` → opp builder uses
  `sorted(mon.moves)` (a raw `list()` would be non-deterministic). `PokemonState` has **no
  `ident`** → opp belief keys all three dicts (movesets/stats/quality) by **`species`**; the
  consistency is a test. `load_move_priors_for_format` has its own delegation/missing-file test.
- **Immutability:** `frozen=True` + builders return fresh containers; documented as convention.
- **Limited-view structural:** `build_opponent_belief` has no `known_team`/`team`/`full_roster`
  param (API-guard test) and reads only `state.sides[opp]["a"|"b"]`.
- **Non-goals:** no export-swap (stub-h0 stays), no training, no seen-memory, no curated full
  team, no hidden-state use.
- **One judgment call to confirm:** the speed-flag marks neutral-base as `weak_speed_fallback`
  (stronger than the literal "0-only" rule) — serves the quality-hook intent; revertable.

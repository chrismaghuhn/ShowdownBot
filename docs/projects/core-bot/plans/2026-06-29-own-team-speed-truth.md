# Own-Team Speed Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the bot use its own team's item truth (esp. Choice Scarf) and treat speed ties as expected value, instead of under-rating its own speed and losing every tie by fiat.

**Architecture:** Fix A adds an `item_lost` flag, a tri-state request-item rule, and one central `apply_own_team_knowledge(state, request, our_spreads)` called in decision setup so item truth reaches speed + damage + everything. Fix B adds a `tie_break` parameter through `sort_actions`/`resolve_turn` and averages two resolver passes in `evaluate_line` on a genuine our-vs-opp tie, reusing the prefetched oracle cache (no new calcs).

**Tech Stack:** Python (pydantic, pytest); spec at `docs/projects/core-bot/specs/2026-06-29-own-team-speed-truth-design.md`. Run tests from `showdown_bot/`.

---

## File Structure

- `src/showdown_bot/engine/state.py` — add `PokemonState.item_lost`; set it in the `item`/`enditem` log branches; correct `merge_request` docstring.
- `src/showdown_bot/models/request.py` — `PokemonSlot.item` becomes tri-state (`str | None`).
- `src/showdown_bot/team/spreads.py` — add `apply_own_team_knowledge(state, request, our_spreads)` (own-team item truth: request tri-state + packed-team fallback).
- `src/showdown_bot/battle/decision.py` — call `apply_own_team_knowledge` once in `heuristic_choose_for_request` before plan/damage/eval.
- `src/showdown_bot/battle/resolve.py` — `tie_break` param on `sort_actions` + `resolve_turn`.
- `src/showdown_bot/battle/evaluate.py` — `_has_genuine_tie` + tie-EV averaging in `evaluate_line`.
- Tests: `tests/test_battle_state.py`, `tests/test_spreads.py`, `tests/test_resolve.py`, `tests/test_evaluate.py`.

---

## Task A1: `item_lost` flag on PokemonState

**Files:**
- Modify: `src/showdown_bot/engine/state.py:64` (add field), `:181-186` (`item`/`enditem` branches)
- Test: `tests/test_battle_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_battle_state.py
from showdown_bot.engine.state import BattleState


def test_enditem_marks_item_lost():
    log = "\n".join([
        "|switch|p1a: Incineroar|Incineroar, L50, M|150/150",
        "|-enditem|p1a: Incineroar|Sitrus Berry|[eat]",
    ])
    st = BattleState.from_log_text(log)
    mon = st.sides["p1"]["a"]
    assert mon.item is None
    assert mon.item_known is True
    assert mon.item_lost is True


def test_item_event_clears_item_lost():
    log = "\n".join([
        "|switch|p1a: Incineroar|Incineroar, L50, M|150/150",
        "|-item|p1a: Incineroar|Choice Scarf",
    ])
    st = BattleState.from_log_text(log)
    mon = st.sides["p1"]["a"]
    assert mon.item == "Choice Scarf"
    assert mon.item_known is True
    assert mon.item_lost is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/test_battle_state.py::test_enditem_marks_item_lost -q`
Expected: FAIL with `AttributeError: 'PokemonState' object has no attribute 'item_lost'`

- [ ] **Step 3: Add the field** (state.py, after line 64 `moved_since_switch`)

```python
    moved_since_switch: bool = False  # has acted since last switch-in (Fake Out gate)
    item_lost: bool = False  # item consumed / removed / knocked / activated -> known absent
```

- [ ] **Step 4: Set it in the log branches** (state.py, replace the `item`/`enditem` block at 181-186)

```python
        elif et == "item":
            mon.item = event.value
            mon.item_known = True
            mon.item_lost = False
        elif et == "enditem":
            mon.item = None
            mon.item_known = True
            mon.item_lost = True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/test_battle_state.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/state.py showdown_bot/tests/test_battle_state.py
git commit -m "feat(state): item_lost flag set on enditem/item log events"
```

---

## Task A2: Tri-state request item (`PokemonSlot.item`)

The pydantic default `item: str = ""` cannot tell a *missing* field from a *present-but-empty* one. Make it `str | None = None` so `None` = missing (no assertion), `""` = present-empty (item known absent), non-empty = item held.

**Files:**
- Modify: `src/showdown_bot/models/request.py:31`
- Test: `tests/test_request_item_tristate.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_request_item_tristate.py
from showdown_bot.models.request import BattleRequest

_BASE = {
    "rqid": 1,
    "side": {"name": "P1", "id": "p1", "pokemon": [
        {"ident": "p1: Landorus", "details": "Landorus-Therian, L50, M",
         "condition": "179/179", "active": True,
         "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
         "moves": ["earthpower"], "baseTypes": ["Ground", "Flying"], "item": "choicescarf"},
    ]},
}


def test_item_present_nonempty():
    req = BattleRequest.model_validate(_BASE)
    assert req.side.pokemon[0].item == "choicescarf"


def test_item_present_empty_vs_missing():
    empty = {**_BASE, "side": {**_BASE["side"], "pokemon": [{**_BASE["side"]["pokemon"][0], "item": ""}]}}
    missing = {**_BASE, "side": {**_BASE["side"], "pokemon": [{k: v for k, v in _BASE["side"]["pokemon"][0].items() if k != "item"}]}}
    assert BattleRequest.model_validate(empty).side.pokemon[0].item == ""      # present-empty
    assert BattleRequest.model_validate(missing).side.pokemon[0].item is None  # missing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/test_request_item_tristate.py::test_item_present_empty_vs_missing -q`
Expected: FAIL (missing field yields `""`, not `None`)

- [ ] **Step 3: Change the model field** (request.py:31)

```python
    item: str | None = None
```

- [ ] **Step 4: Verify consumers tolerate None** — confirm `legal_actions.py::_active_item_id` already does `(actives[active_index].item or "")` (it does). No other change needed.

- [ ] **Step 5: Run tests**

Run: `cd showdown_bot && python -m pytest tests/test_request_item_tristate.py tests/test_legal_actions.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/models/request.py showdown_bot/tests/test_request_item_tristate.py
git commit -m "feat(request): tri-state PokemonSlot.item (None=missing, ''=present-empty)"
```

---

## Task A3: `apply_own_team_knowledge` (the central entry point)

**Files:**
- Modify: `src/showdown_bot/team/spreads.py` (add function)
- Test: `tests/test_spreads.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_spreads.py  (append)
from showdown_bot.team.spreads import apply_own_team_knowledge, our_spreads_from_packed
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest


def _state_with(species, **kw):
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species=species, hp=100, max_hp=100, **kw)
    return st


def _req(item, *, species="Landorus-Therian", drop_item=False):
    poke = {"ident": f"p1: {species}", "details": f"{species}, L50, M", "condition": "179/179",
            "active": True, "stats": {"spe": 100}, "moves": ["earthpower"], "baseTypes": ["Ground"]}
    if not drop_item:
        poke["item"] = item
    return BattleRequest.model_validate({"rqid": 1, "side": {"name": "P1", "id": "p1", "pokemon": [poke]}})


def test_request_item_nonempty_sets_known():
    st = _state_with("Landorus-Therian")
    apply_own_team_knowledge(st, _req("choicescarf"), None)
    mon = st.sides["p1"]["a"]
    assert mon.item == "choicescarf" and mon.item_known and not mon.item_lost


def test_request_item_empty_marks_lost():
    st = _state_with("Landorus-Therian")
    apply_own_team_knowledge(st, _req(""), None)
    mon = st.sides["p1"]["a"]
    assert mon.item is None and mon.item_known and mon.item_lost


def test_fallback_sets_only_when_unknown_and_not_lost():
    sp = our_spreads_from_packed("Incineroar||sitrusberry|intimidate|fakeout|Adamant|252,,,,,||||50|")
    # unknown + request item missing -> fallback sets it
    st = _state_with("Incineroar")
    apply_own_team_knowledge(st, _req(None, species="Incineroar", drop_item=True), sp)
    assert st.sides["p1"]["a"].item == "sitrusberry"


def test_fallback_never_resurrects_lost_item():
    sp = our_spreads_from_packed("Incineroar||sitrusberry|intimidate|fakeout|Adamant|252,,,,,||||50|")
    st = _state_with("Incineroar", item=None, item_known=True, item_lost=True)  # already consumed
    apply_own_team_knowledge(st, _req(None, species="Incineroar", drop_item=True), sp)
    assert st.sides["p1"]["a"].item is None  # NOT restored to sitrusberry
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_spreads.py::test_request_item_empty_marks_lost -q`
Expected: FAIL with `ImportError: cannot import name 'apply_own_team_knowledge'`

- [ ] **Step 3: Implement the function** (append to `team/spreads.py`)

```python
from showdown_bot.engine.state import BattleState, parse_details
from showdown_bot.models.request import BattleRequest


def apply_own_team_knowledge(
    state: BattleState, request: BattleRequest, our_spreads: dict | None
) -> None:
    """Single source of own-team item truth, run once in decision setup before
    speed / damage / enumeration / evaluation.

    Precedence: live request item (tri-state) > protocol events (already in
    state.py, which set item_lost) > packed-team fallback. A lost item is never
    resurrected by the fallback.
    """
    our_side = request.side.id or "p1"
    side = state.sides.get(our_side, {})
    by_species = {mon.species: mon for mon in side.values()}

    # Rule 1: live request item, tri-state.
    for poke in request.side.pokemon:
        species = parse_details(poke.details).species
        mon = by_species.get(species)
        if mon is None:
            continue
        raw = poke.item
        if raw is None:
            continue  # field missing -> no assertion
        if raw != "":
            mon.item, mon.item_known, mon.item_lost = raw, True, False
        else:
            mon.item, mon.item_known, mon.item_lost = None, True, True

    # Rule 3: packed-team fallback only when still unknown AND not lost.
    if our_spreads:
        for mon in side.values():
            if mon.item_known or mon.item_lost:
                continue
            spreads = our_spreads.get(mon.species)
            items = spreads.defense.items if spreads else []
            if items:
                mon.item, mon.item_known = items[0], True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/test_spreads.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/team/spreads.py showdown_bot/tests/test_spreads.py
git commit -m "feat(team): apply_own_team_knowledge - item precedence (request tri-state + fallback)"
```

---

## Task A4: Wire it into the decision; verify Scarf speed

**Files:**
- Modify: `src/showdown_bot/battle/decision.py` (call it in `heuristic_choose_for_request`), `src/showdown_bot/engine/state.py:201` (correct `merge_request` docstring)
- Test: `tests/test_spreads.py` (integration via SpeedOracle)

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_spreads.py  (append)
from showdown_bot.engine.speed import effective_speed_from_state


def test_known_scarf_multiplies_our_speed():
    from showdown_bot.engine.state import FieldState
    st = _state_with("Landorus-Therian")
    apply_own_team_knowledge(st, _req("Choice Scarf"), None)
    mon = st.sides["p1"]["a"]
    spe = effective_speed_from_state(100, mon, FieldState(), "p1")
    assert spe == 150  # 100 * 1.5 (Scarf now known)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/test_spreads.py::test_known_scarf_multiplies_our_speed -q`
Expected: FAIL — `our_speed` returns 100 (Scarf not applied) before the item is set… actually it PASSES here because `apply_own_team_knowledge` already set the item in Task A3. Confirm it FAILS only if A3 is reverted; otherwise this test documents the end-to-end path. If it passes immediately, that is acceptable (A3 made it true) — proceed.

- [ ] **Step 3: Call it in the decision** (decision.py — insert immediately before the `side_mons = state.side(our_side)` line added for moved_since_switch)

```python
    from showdown_bot.team.spreads import apply_own_team_knowledge

    apply_own_team_knowledge(state, req, our_spreads)

    side_mons = state.side(our_side)
```

- [ ] **Step 4: Correct the misleading docstring** (state.py:201, `merge_request`)

```python
    """Merge our own private knowledge (moves, exact HP) from a request.

    Item truth is owned by apply_own_team_knowledge (team/spreads.py), not here.
    The requesting side is identified by ``req.side.id``. Active team members are
    mapped to active slots (a, b, ...) in listing order; revealed move ids and
    condition are merged into the existing log-derived state where possible.
    """
```

- [ ] **Step 5: Run the full suite**

Run: `cd showdown_bot && python -m pytest -q`
Expected: PASS (all green)

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/src/showdown_bot/engine/state.py showdown_bot/tests/test_spreads.py
git commit -m "feat(decision): apply own-team item truth before speed/damage; fix merge_request docstring"
```

- [ ] **Step 7: Guardrail replay check (manual)** — Run one local gauntlet game with trace on and confirm our Landorus-T is treated as Scarf-fast (no crash, invalid_choices=0):

```bash
cd showdown_bot && SHOWDOWN_TURN_TRACE=1 python -m showdown_bot gauntlet --games 2 --format gen9vgc2024regg 2>&1 | tail -5
```
Expected: `2/2` games complete, `invalid_choices=0 crashes=0`.

---

## Task B1: `tie_break` parameter on `sort_actions`

**Files:**
- Modify: `src/showdown_bot/battle/resolve.py:93-110`
- Test: `tests/test_resolve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resolve.py  (append; reuse existing PlannedAction import)
from showdown_bot.battle.resolve import sort_actions, PlannedAction
from showdown_bot.engine.moves import get_move_meta


def _atk(side, slot, speed, ours):
    return PlannedAction(side, slot, "move", speed=speed, move=get_move_meta("Tackle"),
                         target=("p2" if ours else "p1", "a"), is_ours=ours)


def test_tie_break_orders_both_ways():
    ours = _atk("p1", "a", 100, True)
    opp = _atk("p2", "a", 100, False)
    last = sort_actions([opp, ours], tie_break="ours_last")
    first = sort_actions([opp, ours], tie_break="ours_first")
    assert last[0] is opp and last[1] is ours      # ours acts last (default)
    assert first[0] is ours and first[1] is opp     # ours acts first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/test_resolve.py::test_tie_break_orders_both_ways -q`
Expected: FAIL with `TypeError: sort_actions() got an unexpected keyword argument 'tie_break'`

- [ ] **Step 3: Add the parameter** (resolve.py, replace `sort_actions`)

```python
def sort_actions(
    actions: list[PlannedAction], field: FieldState | None = None, *, tie_break: str = "ours_last"
) -> list[PlannedAction]:
    """Approximate PS action queue: order asc, then priority desc, then speed.

    Speed is DESC normally, ASC under Trick Room. ``tie_break`` decides equal-key
    ties: ``ours_last`` (default, pessimistic) or ``ours_first`` -- the two
    orderings the tie-EV averages over.
    """
    tr = bool(field and field.trick_room)

    def keyfn(a: PlannedAction):
        pr = move_priority(a.move, field) if (a.kind == "move" and a.move) else (
            4 if a.kind == "protect" else 0
        )
        speed_sort = a.speed if tr else -a.speed
        if tie_break == "ours_first":
            tie = 0 if a.is_ours else 1
        else:
            tie = 1 if a.is_ours else 0  # ours loses ties (pessimistic default)
        return (_order_rank(a), -pr, speed_sort, tie)

    return sorted(actions, key=keyfn)
```

- [ ] **Step 4: Run tests**

Run: `cd showdown_bot && python -m pytest tests/test_resolve.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/resolve.py showdown_bot/tests/test_resolve.py
git commit -m "feat(resolve): tie_break param on sort_actions (ours_first|ours_last)"
```

---

## Task B2: Thread `tie_break` through `resolve_turn`

**Files:**
- Modify: `src/showdown_bot/battle/resolve.py` (`resolve_turn` signature + its `sort_actions` call at :197)
- Test: covered by Task B3.

- [ ] **Step 1: Add the parameter to `resolve_turn`** (its signature, after `field`)

```python
def resolve_turn(
    state: BattleState,
    actions: list[PlannedAction],
    damage_fn: DamageFn,
    *,
    our_side: str = "p1",
    field: FieldState | None = None,
    tie_break: str = "ours_last",
) -> TurnOutcome:
```

- [ ] **Step 2: Pass it to `sort_actions`** (resolve.py:197)

```python
    for idx, action in enumerate(sort_actions(actions, field, tie_break=tie_break)):
```

- [ ] **Step 3: Run the suite to confirm nothing broke**

Run: `cd showdown_bot && python -m pytest tests/test_resolve.py tests/test_evaluate.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/resolve.py
git commit -m "feat(resolve): thread tie_break through resolve_turn"
```

---

## Task B3: Tie-EV averaging in `evaluate_line` (+ guardrail)

**Files:**
- Modify: `src/showdown_bot/battle/evaluate.py` (add `_has_genuine_tie`; branch in `evaluate_line`)
- Test: `tests/test_evaluate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_evaluate.py  (append)
from showdown_bot.battle.evaluate import evaluate_line
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.state import BattleState, PokemonState


def _mirror_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def _move(side, ours):
    return PlannedAction(side, "a", "move", speed=100, move=get_move_meta("Flare Blitz"),
                         target=("p2" if ours else "p1", "a"), is_ours=ours)


def test_tie_ev_averages_two_orderings():
    st = _mirror_state()
    seen = {"resolves": 0}

    def damage_fn(action, target_mon):
        return 0.5  # both KO-relevant numbers identical -> isolates ordering effect

    ours = [_move("p1", True)]
    opp = [_move("p2", False)]
    # With a genuine tie present, evaluate_line must resolve BOTH orderings.
    score, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1")
    score_last, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_last")
    score_first, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_first")
    assert abs(score - 0.5 * (score_first + score_last)) < 1e-9


def test_no_tie_is_bit_identical():
    st = _mirror_state()

    def damage_fn(action, target_mon):
        return 0.4

    ours = [PlannedAction("p1", "a", "move", speed=130, move=get_move_meta("Flare Blitz"),
                          target=("p2", "a"), is_ours=True)]   # faster -> no tie
    opp = [PlannedAction("p2", "a", "move", speed=80, move=get_move_meta("Flare Blitz"),
                         target=("p1", "a"), is_ours=False)]
    score_ev, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1")
    score_plain, _ = evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_last")
    assert score_ev == score_plain  # no tie -> single pass, unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_evaluate.py::test_tie_ev_averages_two_orderings -q`
Expected: FAIL with `TypeError: evaluate_line() got an unexpected keyword argument '_force_tie_break'`

- [ ] **Step 3: Add the tie detector** (evaluate.py, above `evaluate_line`)

```python
def _has_genuine_tie(all_actions: list[PlannedAction], field: FieldState | None) -> bool:
    """True iff an our-action and an opp-action share the full ordering key
    (order rank, dynamic priority, effective speed) -- i.e. a real speed tie, not
    just an equal raw number. Detected after pruning, before sequential exec."""
    from showdown_bot.battle.resolve import _order_rank, move_priority

    tr = bool(field and field.trick_room)

    def base_key(a: PlannedAction):
        pr = move_priority(a.move, field) if (a.kind == "move" and a.move) else (
            4 if a.kind == "protect" else 0
        )
        return (_order_rank(a), -pr, a.speed if tr else -a.speed)

    ours = [base_key(a) for a in all_actions if a.is_ours]
    opp = [base_key(a) for a in all_actions if not a.is_ours]
    return any(k in opp for k in ours)
```

- [ ] **Step 4: Branch in `evaluate_line`** (replace the body from `all_actions = ...` through `return score, outcome`)

```python
    field = field or state.field
    all_actions = my_actions + opp_actions

    def _one(tb: str) -> tuple[float, TurnOutcome]:
        out = resolve_turn(state, all_actions, damage_fn, our_side=our_side, field=field, tie_break=tb)
        sc = score_outcome(out, our_side, weights, endgame=endgame)
        if rollout_horizon > 0:
            sc += _rollout_value(
                state, all_actions, out, our_side, weights or EvalWeights(),
                field, rollout_horizon, rollout_gamma,
            )
        return sc, out

    if _force_tie_break is not None:
        return _one(_force_tie_break)
    if _has_genuine_tie(all_actions, field):
        # Tie EV: average both orderings. Same prefetched oracle cache -> no new calcs.
        s_first, _ = _one("ours_first")
        s_last, out_last = _one("ours_last")
        return 0.5 * (s_first + s_last), out_last
    return _one("ours_last")
```

- [ ] **Step 5: Add the `_force_tie_break` keyword to `evaluate_line`'s signature** (after `endgame`)

```python
    endgame: bool = False,
    _force_tie_break: str | None = None,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/test_evaluate.py -q`
Expected: PASS

- [ ] **Step 7: Add the oracle guardrail test** (proves the 2nd pass makes no new calcs)

```python
# tests/test_evaluate.py  (append)
from showdown_bot.battle.oracle import DamageOracle


def test_tie_ev_makes_no_new_oracle_calls(monkeypatch):
    st = _mirror_state()
    calls = {"n": 0}

    def damage_fn(action, target_mon):
        calls["n"] += 1   # counts resolver damage lookups, not Node batches
        return 0.5

    ours = [_move("p1", True)]
    opp = [_move("p2", False)]
    evaluate_line(st, ours, opp, damage_fn, our_side="p1")
    two_pass = calls["n"]
    calls["n"] = 0
    evaluate_line(st, ours, opp, damage_fn, our_side="p1", _force_tie_break="ours_last")
    one_pass = calls["n"]
    # Two passes call damage_fn ~2x, but a real oracle dedupes identical requests
    # to its cache -> zero extra Node batches. Assert two-pass == 2x one-pass
    # exactly (no hidden extra requests).
    assert two_pass == 2 * one_pass
```

- [ ] **Step 8: Run the full suite**

Run: `cd showdown_bot && python -m pytest -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/tests/test_evaluate.py
git commit -m "feat(evaluate): speed-tie expected value (first genuine tie, two passes, cache-reuse guardrail)"
```

---

## Task B4: Guardrail gauntlet (measure, do not tune)

- [ ] **Step 1: Run a short local gauntlet** (server up on :8000)

Run: `cd showdown_bot && python -m showdown_bot gauntlet --games 16 --format gen9vgc2024regg`
Expected: completes, `invalid_choices=0 crashes=0`. Winrate is a guardrail only (not an optimization target — the mirror-vs-max_damage benchmark rewards recklessness; see spec).

- [ ] **Step 2: Note the result** in the session log / memory. No code change expected from this step.

---

## Self-Review notes

- **Spec coverage:** Fix A (item_lost A1; tri-state request A2; precedence + fallback A3; central wiring + docstring A4) and Fix B (tie_break B1/B2; genuine-tie detection + EV averaging + guardrail B3; guardrail gauntlet B4) all map to tasks.
- **Type consistency:** `apply_own_team_knowledge(state, request, our_spreads)`, `item_lost`, `tie_break: str`, `_force_tie_break: str | None`, `_has_genuine_tie(all_actions, field)` are used identically across tasks.
- **Known nuance:** Task A4 Step 2's test may already pass because A3 set the item — acceptable (it documents the end-to-end path); the genuine RED was in A3.

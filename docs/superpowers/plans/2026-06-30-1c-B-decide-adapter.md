# Phase 3 Slice 1c-B: state-driven `decide` adapter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `decide(state, side, ...) -> JointAction` adapter that drives the existing
heuristic from a raw `BattleState`, for either side, with no duplicated decision logic and
no wire-format decoding.

**Architecture:** (1) Behavior-preserving extraction of `_choose_best_ja` from
`battle/decision.py` (the heuristic now returns its `JointAction`; the public function is a
thin encode wrapper). (2) `learning/decide_adapter.py` with `synthesize_request` (a minimal
request-shaped view from the state + caller-supplied roster/movesets/stats — belief-
agnostic) and `decide` (synthesize → core). No H-loop (1c-C), no opponent belief (1c-D).

**Tech Stack:** Python stdlib + pydantic models. Spec:
`docs/superpowers/specs/2026-06-30-1c-B-decide-adapter-design.md`. Types: `models/request.py`
(`BattleRequest`, `SideInfo`, `PokemonSlot`, `ActiveSlot`, `MoveSlot`), `battle/actions.py`
(`JointAction`), `engine/moves.py` (`MoveMeta.target`). Run tests from `showdown_bot/`.

---

## File Structure
- Modify (behavior-preserving): `src/showdown_bot/battle/decision.py` (extract `_choose_best_ja`).
- Create: `src/showdown_bot/learning/decide_adapter.py` (`synthesize_request`, `decide`).
- Tests: `tests/test_decide_core_equivalence.py`, `tests/test_decide_adapter.py`.

---

## Task 1: extract `_choose_best_ja` (behavior-preserving) + equivalence gate

The riskiest task: a pure refactor of `heuristic_choose_for_request` that must NOT change
any chosen action. The current function ends with
`return encode_choose(best_ja.as_pair(), rqid=req.rqid)` (decision.py:441); the
`team_preview` early-return is at the top (~line 170-171).

**Files:** Modify `src/showdown_bot/battle/decision.py`; Test `tests/test_decide_core_equivalence.py`.

- [ ] **Step 1: write the equivalence test** (reuse the existing `decision_fixture` from `tests/conftest.py`)

```python
# tests/test_decide_core_equivalence.py
from showdown_bot.battle.decision import heuristic_choose_for_request, _choose_best_ja
from showdown_bot.protocol.encoder import encode_choose


def test_core_encode_equals_public_choice(decision_fixture):
    req, kw = decision_fixture
    public = heuristic_choose_for_request(req, **kw)              # the wire string
    best_ja = _choose_best_ja(req, **kw)                          # the JointAction
    assert encode_choose(best_ja.as_pair(), rqid=req.rqid) == public

def test_core_is_deterministic(decision_fixture):
    req, kw = decision_fixture
    assert _choose_best_ja(req, **kw).as_pair() == _choose_best_ja(req, **kw).as_pair()
```

- [ ] **Step 2: run → FAIL** (`_choose_best_ja` doesn't exist). `cd showdown_bot && python -m pytest tests/test_decide_core_equivalence.py -q`

- [ ] **Step 3: extract the core.** In `decision.py`:
  - Rename the existing `heuristic_choose_for_request` body to `def _choose_best_ja(req, *, state, ...) -> JointAction:` keeping ALL current params and `state`. Move the `team_preview` early-return OUT (to the wrapper). Replace the final
    `return encode_choose(best_ja.as_pair(), rqid=req.rqid)` with `return best_ja`. Everything
    else (the `rollout_horizon` default, `apply_own_team_knowledge`, `enumerate_my_actions`,
    `predict_responses`, `DamageModel`, `pick_best`, `_maybe_tera`, and the `report=`/`trace=`
    blocks) stays INSIDE `_choose_best_ja` unchanged.
  - Add the thin public wrapper:
    ```python
    def heuristic_choose_for_request(req, *, state, ...same params...):
        if req.team_preview:
            return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)
        best_ja = _choose_best_ja(req, state=state, ...same params...)
        return encode_choose(best_ja.as_pair(), rqid=req.rqid)
    ```
  Keep `choose_with_fallback` calling `heuristic_choose_for_request` exactly as today.

- [ ] **Step 4: run the equivalence test + the FULL suite.** `cd showdown_bot && python -m pytest tests/test_decide_core_equivalence.py -q` then `cd showdown_bot && python -m pytest -q` (was 341; +2). **ALL existing decision/gauntlet/trace tests must stay green** — that is the behaviour-preservation proof. If any regress, the extraction changed behaviour: fix it, don't adjust the test.

- [ ] **Step 5: commit** `refactor(decision): extract _choose_best_ja core; heuristic_choose_for_request wraps + encodes (behavior-preserving)`.

---

## Task 2: `synthesize_request` (belief-agnostic, minimal schema)

`synthesize_request(state, side, *, roster, movesets, stats, move_meta) -> BattleRequest`.
Populate ONLY the fields the heuristic reads (Part 2 of the spec). Belief-agnostic: never
read a hidden opponent bench/set from `state`.

**Files:** Create `src/showdown_bot/learning/decide_adapter.py`; Test `tests/test_decide_adapter.py`.

- [ ] **Step 1: failing tests** (build a small state + a fake roster/movesets/stats; assert the
  synthesized request is *accepted by the heuristic*: `enumerate_my_actions` yields actions)

```python
# tests/test_decide_adapter.py
import pytest
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.learning.decide_adapter import synthesize_request
from showdown_bot.battle.legal_actions import enumerate_my_actions


def _state():
    s = BattleState()
    s.sides["p1"] = {"a": PokemonState(species="Incineroar", hp=200, max_hp=200,
                                       moves={"fakeout", "knockoff", "flareblitz", "partingshot"})}
    s.sides["p2"] = {"a": PokemonState(species="Flutter Mane", hp=100, max_hp=100)}
    return s


def test_synthesized_request_is_enumerable():
    s = _state()
    roster = {"p1": {}}        # no bench needed for this case
    stats = {"p1": {"Incineroar": {"spe": 90}}}
    movesets = {"p1": {"Incineroar": ["fakeout", "knockoff", "flareblitz", "partingshot"]}}
    req = synthesize_request(s, "p1", roster=roster, movesets=movesets, stats=stats, move_meta=<map>)
    assert req.side.id == "p1"
    assert req.active and req.active[0] is not None and len(req.active[0].moves) >= 1
    assert enumerate_my_actions(req, moved_since_switch=[False, False])   # >=1 legal action

def test_force_switch_for_fainted_active():
    s = _state()
    s.sides["p1"]["a"].fainted = True
    s.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=200, max_hp=200, fainted=False,
                                      moves={"fakeout"})
    req = synthesize_request(s, "p1", roster={"p1": {}}, movesets={...}, stats={...}, move_meta=<map>)
    assert req.force_switch and req.force_switch[0] is True   # fainted slot forces a switch

def test_rqid_is_deterministic_synthetic():
    s = _state()
    r1 = synthesize_request(s, "p1", roster={"p1": {}}, movesets={...}, stats={...}, move_meta=<map>)
    r2 = synthesize_request(s, "p1", roster={"p1": {}}, movesets={...}, stats={...}, move_meta=<map>)
    assert r1.rqid == r2.rqid   # e.g. f"rollout-{turn}-{side}" or 0

def test_no_hidden_roster_read():
    # opponent side with NO caller-supplied roster/movesets/stats must not read hidden truth
    s = _state()
    with pytest.raises((ValueError, KeyError)):
        synthesize_request(s, "p2", roster={}, movesets={}, stats={}, move_meta=<map>)
```
(Adapt `<map>` to a real/fake `move_meta` and the `{...}` to the matching fake inputs while
implementing; report what you used.)

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement** `synthesize_request` in `decide_adapter.py`. Build, from `state` +
  caller inputs, the minimal `BattleRequest` (using `models/request.py` constructors):
  - `side = SideInfo(id=side, pokemon=[...])`; one `PokemonSlot(ident, details=species, condition,
    active, stats={"spe": ...}, moves=[...])` per active mon (from `state.sides[side]`, slots a/b)
    and per bench mon (from `roster[side]`, in roster order). `condition` = `f"{hp}/{max_hp}"`, or
    `"0 fnt"` when fainted.
  - `active = [ActiveSlot(moves=[MoveSlot(move=mid, id=mid, pp=1, maxpp=1,
    target=move_meta[mid].target, disabled=False) for mid in movesets[side][species]],
    can_terastallize=...) for each active living mon]` (None for an empty/fainted active slot if
    the heuristic expects that — mirror how live requests encode it).
  - `force_switch = [mon is fainted for each active slot]` (True forces switch-only for that slot;
    reuse `enumerate_my_actions`' existing handling — do NOT invent pass/no-op).
  - `rqid = f"rollout-{state.turn}-{side}"` (deterministic synthetic). `team_preview = False`.
  - **Belief guard:** if `side` has no entry in `roster`/`movesets`/`stats` (and the side isn't
    fully known from `state`), raise `ValueError` — never read a hidden opponent bench/set.

- [ ] **Step 4: run → PASS** + full suite. **Step 5: commit** `feat(learning): synthesize_request (minimal belief-agnostic request from BattleState)`.

---

## Task 3: `decide` adapter + full test suite

**Files:** Modify `src/showdown_bot/learning/decide_adapter.py`; Test `tests/test_decide_adapter.py`.

- [ ] **Step 1: failing tests**

```python
def test_decide_returns_jointaction_accepted_by_resolve_turn(decision_fixture):
    # reuse the fixture's real state + deps; decide must return a JointAction resolve_turn accepts
    from showdown_bot.learning.decide_adapter import decide
    from showdown_bot.battle.actions import JointAction
    req, kw = decision_fixture
    state = kw["state"]; side = kw.get("our_side", "p1")
    ja = decide(state, side, roster=<from fixture>, movesets=<from fixture>, stats=<from fixture>,
                move_meta=<map>, deps=<kw subset the core needs>)
    assert isinstance(ja, JointAction)
    # resolve_turn accepts it (no raise) — plan it via _plan_my_actions + resolve_turn or a smoke

def test_decide_both_sides(decision_fixture):
    # our side (known) + opponent side (a FAKE roster/movesets/stats) both yield a JointAction
    ...

def test_decide_is_deterministic(decision_fixture):
    ... identical inputs -> identical JointAction ...
```
(Wire `deps` = the keyword args the core needs — `book`, `calc`/`oracle`, `speed_oracle`, `dex`,
`our_spreads`, `opp_sets`, etc. — from the fixture. Adapt and report.)

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement `decide`**

```python
def decide(state, side, *, roster, movesets, stats, move_meta, deps) -> "JointAction":
    from showdown_bot.battle.decision import _choose_best_ja
    req = synthesize_request(state, side, roster=roster, movesets=movesets, stats=stats, move_meta=move_meta)
    return _choose_best_ja(req, state=state, our_side=side, **deps)
```

- [ ] **Step 4: run → PASS** + full suite. **Step 5: commit** `feat(learning): decide(state, side) adapter -> JointAction via _choose_best_ja (both sides, belief-agnostic)`.

---

## Self-Review notes
- **Spec coverage:** core extraction + equivalence gate (T1); synthesize_request minimal
  schema + force_switch + synthetic rqid + no-hidden-read (T2); decide both-sides +
  resolve_turn-accepts + determinism (T3).
- **Behaviour preservation** is the T1 gate: existing tests + `encode(_choose_best_ja(req)) ==
  heuristic_choose_for_request(req)`.
- **Negative scope held:** belief-agnostic inputs; opponent hidden bench/sets never read from
  `state` (raises without caller inputs). The opponent belief source = 1c-D.
- **Deferred:** H-loop teacher wiring (1c-C), opponent belief/likely_sets roster (1c-D).

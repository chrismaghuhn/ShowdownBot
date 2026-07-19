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
`docs/projects/core-bot/specs/2026-06-30-1c-B-decide-adapter-design.md`. Types: `models/request.py`
(`BattleRequest`, `SideInfo`, `PokemonSlot`, `ActiveSlot`, `MoveSlot`), `battle/actions.py`
(`JointAction`), `engine/moves.py` (`MoveMeta.target`). Run tests from `showdown_bot/`.

---

## File Structure
- Modify (behavior-preserving): `src/showdown_bot/battle/decision.py` (extract `_choose_best_ja`).
- Create: `src/showdown_bot/learning/decide_adapter.py` (`synthesize_request`, `decide`).
- Tests: `tests/test_decide_core_equivalence.py`, `tests/test_decide_adapter.py`.

## Pinned input shapes (use these exact types; no loose pseudocode)
```python
roster_by_side:   dict[str, dict[str, PokemonState]]   # side -> stable-ordered ident -> PokemonState
movesets_by_side: dict[str, dict[str, list[str]]]      # side -> ident|species -> ordered move ids
stats_by_side:    dict[str, dict[str, dict[str, int]]] # side -> ident|species -> {"spe": int}
```
- **Lookup order for a mon's moveset/stats:** (1) by `ident`, (2) by `species`, (3) **raise
  `ValueError`**. Prefer `ident` (duplicate species are possible; species-keyed is fragile).
- **Bench dedupe (pin):** `side.pokemon = active slots first, then roster entries that are NOT
  currently active by ident` — an active mon must never appear twice in the request.

## `deps` is sanitized, never a raw `**kw` (pin)
`decide` must not splat an arbitrary dict into the core (a stray `state`/`our_side`/`trace`
key → `TypeError`). Use an explicit allow-list / sanitizer:
```python
_CORE_DEP_KEYS = {"book", "calc", "oracle", "speed_oracle", "dex", "priors", "weights",
                  "risk_lambda", "tera_margin", "rollout_horizon", "our_spreads", "opp_sets"}
def _core_deps(deps: dict) -> dict:
    return {k: v for k, v in deps.items() if k in _CORE_DEP_KEYS}
```
(`state`, `our_side`, `trace`, `report` are passed explicitly, never via `deps`. Confirm the
allow-list against `_choose_best_ja`'s real signature and adjust.)

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

def test_core_rejects_team_preview_request(decision_fixture):
    import pytest
    req, kw = decision_fixture
    req.team_preview = True
    with pytest.raises(ValueError, match="team preview"):
        _choose_best_ja(req, **kw)

def test_trace_preserved_via_public_and_core(decision_fixture):
    # the refactor must NOT break 1b capture: trace= still fills via the public wrapper AND the core
    from showdown_bot.battle.decision_trace import DecisionTrace
    req, kw = decision_fixture
    kw2 = {k: v for k, v in kw.items() if k != "trace"}
    tr_pub = DecisionTrace(); heuristic_choose_for_request(req, trace=tr_pub, **kw2)
    tr_core = DecisionTrace(); _choose_best_ja(req, trace=tr_core, **kw2)
    assert tr_pub.chosen_candidate_id is not None and len(tr_pub.candidates) >= 1
    assert tr_core.chosen_candidate_id == tr_pub.chosen_candidate_id   # same population

def test_report_preserved_if_fixture_supports_it(decision_fixture):
    req, kw = decision_fixture
    kw2 = {k: v for k, v in kw.items() if k != "report"}
    rep: list[str] = []
    heuristic_choose_for_request(req, report=rep, **kw2)
    assert rep   # report= still populated through the wrapper -> core
```

- [ ] **Step 2: run → FAIL** (`_choose_best_ja` doesn't exist). `cd showdown_bot && python -m pytest tests/test_decide_core_equivalence.py -q`

- [ ] **Step 3: extract the core.** In `decision.py`:
  - Rename the existing `heuristic_choose_for_request` body to `def _choose_best_ja(req, *, state, ...) -> JointAction:` keeping ALL current params and `state` (including `trace=`/`report=` — they thread into the core unchanged). Move the `team_preview` early-return OUT (to the wrapper) and add a **defensive guard** at the top of the core: `if req.team_preview: raise ValueError("_choose_best_ja does not handle team preview")`. Replace the final
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

- [ ] **Step 0: ground the request model (discovery — do NOT guess).** Read
  `models/request.py` and one real `BattleRequest` fixture (e.g. in `tests/` or a captured
  log). Pin the EXACT constructor field names + defaults for `BattleRequest`, `SideInfo`,
  `PokemonSlot`, `ActiveSlot`, `MoveSlot`, and `force_switch`. **Critically:** `active` is
  `list[ActiveSlot | None]` (request.py:45) — a fainted/empty active slot is `None`, not an
  empty `ActiveSlot`. Pin: a fainted active mon ⇒ `active[i] = None` AND `force_switch[i] =
  True`. Write a one-line note of the confirmed field names in the module docstring.

- [ ] **Step 1: failing tests** (build a small state + a fake roster/movesets/stats per the
  Pinned input shapes above; assert the synthesized request is *accepted by the heuristic*:
  `enumerate_my_actions` yields actions)

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
    # the REAL gate: enumeration produces switch-only (no move-actions) for the fainted slot,
    # not merely force_switch[0] is True
    s = _state()
    s.sides["p1"]["a"].fainted = True
    bench = PokemonState(species="Rillaboom", hp=200, max_hp=200, moves={"fakeout"})
    roster = {"p1": {"p1: Rillaboom": bench}}
    movesets = {"p1": {"p1: Rillaboom": ["fakeout"]}}
    stats = {"p1": {"p1: Rillaboom": {"spe": 85}}}
    req = synthesize_request(s, "p1", roster=roster, movesets=movesets, stats=stats, move_meta=<map>)
    assert req.force_switch[0] is True
    acts = enumerate_my_actions(req, moved_since_switch=[False, False])
    slot0_kinds = {ja.slot0.kind for ja in acts}
    assert "move" not in slot0_kinds          # fainted slot 0: switch-only, no move actions

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
def test_decide_both_sides_feed_resolve_turn(decision_fixture):
    # BOTH sides decide from the state, then their JointActions plan + resolve_turn (the 1c goal).
    from showdown_bot.learning.decide_adapter import decide
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.battle.decision import _plan_my_actions
    from showdown_bot.battle.resolve import resolve_turn
    req, kw = decision_fixture
    state = kw["state"]
    our = {"roster": <our roster>, "movesets": <our movesets>, "stats": <our stats>,
           "move_meta": <map>, "deps": <kw>}
    opp = {"roster": <fake opp roster>, "movesets": <fake opp movesets>, "stats": <fake opp stats>,
           "move_meta": <map>, "deps": <kw>}
    ja_p1 = decide(state, "p1", **our)
    ja_p2 = decide(state, "p2", **opp)
    assert isinstance(ja_p1, JointAction) and isinstance(ja_p2, JointAction)
    # plan both sides' JointActions and resolve a real turn (no raise -> a TurnOutcome)
    p1_plan = _plan_my_actions(<synth p1 req>, ja_p1, state=state, our_side="p1", opp_side="p2", speed_oracle=<oracle>)
    p2_plan = _plan_my_actions(<synth p2 req>, ja_p2, state=state, our_side="p2", opp_side="p1", speed_oracle=<oracle>)
    outcome = resolve_turn(state, p1_plan + p2_plan, <damage_fn>, ...)   # ground the real signature
    assert outcome is not None

def test_decide_is_deterministic(decision_fixture):
    from showdown_bot.learning.decide_adapter import decide
    req, kw = decision_fixture
    our = {"roster": <our roster>, "movesets": <our movesets>, "stats": <our stats>,
           "move_meta": <map>, "deps": <kw>}
    a = decide(kw["state"], "p1", **our); b = decide(kw["state"], "p1", **our)
    assert a.as_pair() == b.as_pair()
```
(Wire `deps` = the keyword args the core needs — `book`, `calc`/`oracle`, `speed_oracle`, `dex`,
`our_spreads`, `opp_sets`, etc. — from the fixture. Adapt and report.)

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement `decide`**

```python
def decide(state, side, *, roster, movesets, stats, move_meta, deps: dict) -> "JointAction":
    from showdown_bot.battle.decision import _choose_best_ja
    req = synthesize_request(state, side, roster=roster, movesets=movesets, stats=stats, move_meta=move_meta)
    # state/our_side passed explicitly; deps SANITIZED (never splat state/our_side/trace/report)
    return _choose_best_ja(req, state=state, our_side=side, **_core_deps(deps))
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
- **Review patches in:** team-preview guard on the core (+ test); trace/report preservation
  tests (refactor must not break 1b capture); pinned `roster/movesets/stats` shapes +
  ident→species→ValueError lookup + bench dedupe; `deps` sanitizer (`_core_deps`, never raw
  `**kw`); force-switch test asserts enumeration is switch-only (not just the flag); the
  resolve_turn smoke decides BOTH sides → plans → resolves; T2 Step-0 discovery grounds the
  exact request-model fields (incl. `active[i]=None` for a fainted slot — request.py:45).
- **Deferred:** H-loop teacher wiring (1c-C), opponent belief/likely_sets roster (1c-D).

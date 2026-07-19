# Depth-2 de-risk (cheap approximate 2-ply) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an off-by-default, cheap approximate depth-2 adversarial search that wraps the existing 1-ply decision core, to test whether search depth breaks the 1-ply ceiling — byte-identical when the toggle is off.

**Architecture:** A new `battle/search.py` holds the turn-2 state approximation + the `depth2_value` recursion (reusing the existing `predict_responses`/`DamageModel`/`evaluate_line`/`aggregate_scores` 1-ply machinery). `_choose_best` (single-world path only) selects the top-N candidates by their 1-ply value and replaces their leaf values with the depth-2 backup, behind `SHOWDOWN_SEARCH_DEPTH`.

**Tech Stack:** Python 3.11+ stdlib (`copy`, `os`), the existing `showdown_bot.battle`/`engine` modules, pytest. No new deps.

## Design references

- Spec: `docs/projects/learning/specs/2026-07-12-2c-depth2-derisk-design.md` (read it first).
- Seam facts (verified on `main f6715c8`): `_choose_best` single-world path = decision.py ~350-384 (`opp_resps = predict_responses(...)`; `model = DamageModel(...)`; `model.prefetch(groups)`; `score_plan(my_plan) -> list[float]`; `items = [(ja, score_plan(plan)) ...]`; `best_ja, best_val = pick_best(items, mode, risk_lambda=..., weights=resp_weights)`). `evaluate_line(state, my_actions, opp_actions, damage_fn, *, our_side, weights, field, rollout_horizon, endgame, fast_board) -> tuple[float, TurnOutcome]`. `FieldState` has NO turn counters (weather/terrain/trick_room booleans, tailwind `{p1,p2}` bools) → field persists across the approximation. `PokemonState`: `.hp:int`, `.max_hp`, `.fainted:bool`, `.hp_fraction`. `BattleState`: `@dataclass`, `.sides`, `.field`, `.turn`; deep-copyable via `copy.deepcopy`. The +Sampling `DamageModel.enqueue(action_groups)` + `oracle.flush()` single-flush is on `main`.

## File structure

- Create `showdown_bot/src/showdown_bot/battle/search.py` — `approx_turn2_state(...)` + `depth2_value(...)`.
- Modify `showdown_bot/src/showdown_bot/battle/decision.py` — the depth-2 wrap in `_choose_best` single-world path (guarded).
- Modify `showdown_bot/src/showdown_bot/eval/config_env.py` — classify `SHOWDOWN_SEARCH_DEPTH` BEHAVIOR_AFFECTING.
- Tests: `showdown_bot/tests/test_search_depth2.py`, extend `tests/test_config_env.py`.

---

### Task 1: `SHOWDOWN_SEARCH_DEPTH` toggle (BEHAVIOR_AFFECTING) + reader

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/config_env.py`
- Modify: `showdown_bot/src/showdown_bot/battle/decision.py` (add `_search_depth()` near `_world_samples`/`_risk_lambda`)
- Test: `showdown_bot/tests/test_config_env.py`

- [ ] **Step 1: Failing test** — add to `test_config_env.py`, mirroring the existing `SHOWDOWN_WORLD_SAMPLES` test:

```python
def test_search_depth_is_behavior_affecting_and_clamped(monkeypatch):
    from showdown_bot.eval.config_env import BEHAVIOR_AFFECTING, config_hash
    from showdown_bot.battle.decision import _search_depth
    assert "SHOWDOWN_SEARCH_DEPTH" in BEHAVIOR_AFFECTING
    monkeypatch.delenv("SHOWDOWN_SEARCH_DEPTH", raising=False)
    base = config_hash()
    assert _search_depth() == 1
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2"); assert _search_depth() == 2
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "5"); assert _search_depth() == 2   # clamp
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "0"); assert _search_depth() == 1
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "x"); assert _search_depth() == 1
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    assert config_hash() != base   # set -> hash changes
```

- [ ] **Step 2: Run → RED** (`SHOWDOWN_SEARCH_DEPTH` not in BEHAVIOR_AFFECTING / `_search_depth` missing).
Run: `cd showdown_bot && python -m pytest tests/test_config_env.py -q`

- [ ] **Step 3: Implement.** In `config_env.py` add `"SHOWDOWN_SEARCH_DEPTH"` to the `BEHAVIOR_AFFECTING` collection right after `"SHOWDOWN_WORLD_SAMPLES"`. In `decision.py`, next to `_world_samples`/the other readers, add:

```python
def _search_depth() -> int:
    """Search depth (SHOWDOWN_SEARCH_DEPTH), clamped to {1, 2}. Default/unparsable
    -> 1 (verbatim 1-ply = byte-identical). >=2 -> approximate depth-2."""
    try:
        return 2 if int(os.environ.get("SHOWDOWN_SEARCH_DEPTH", "1")) >= 2 else 1
    except ValueError:
        return 1
```

- [ ] **Step 4: Run → GREEN.** `cd showdown_bot && python -m pytest tests/test_config_env.py -q`
- [ ] **Step 5: Commit** — `feat(2c-depth2): classify SHOWDOWN_SEARCH_DEPTH behavior-affecting`

---

### Task 2: turn-2 state approximation (`battle/search.py::approx_turn2_state`)

The load-bearing, honestly-limited core. **The tests below are the exact spec.** Reuses the line's damage via the same `damage_fn` the model exposes; mutates a deep copy.

**Files:**
- Create: `showdown_bot/src/showdown_bot/battle/search.py`
- Test: `showdown_bot/tests/test_search_depth2.py`

- [ ] **Step 1: Failing tests** (exact behavior):

```python
# tests/test_search_depth2.py
import copy
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.battle.search import approx_turn2_state


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.field.trick_room = True
    st.turn = 3
    return st


def _dmg(fraction_by_target):
    # damage_fn stand-in: returns expected HP damage for (attacker_slot, target_slot)
    def fn(our_side, my_actions, opp_actions):
        return dict(fraction_by_target)
    return fn


def test_transition_subtracts_damage_marks_faint_advances_turn():
    st = _state()
    # opponent deals 200 to our Incineroar(150) -> faint; we deal 50 to Flutter Mane(131)
    nxt = approx_turn2_state(st, our_side="p1",
        applied_damage={("p1", "a"): 200, ("p2", "a"): 50})
    assert nxt is not st and nxt.side("p1")["a"] is not st.side("p1")["a"]  # deep copy
    assert nxt.side("p1")["a"].hp == 0 and nxt.side("p1")["a"].fainted is True
    assert nxt.side("p2")["a"].hp == 81 and nxt.side("p2")["a"].fainted is False
    assert nxt.turn == 4                      # turn advanced
    assert nxt.field.trick_room is True       # field persists (no counters in FieldState)
    assert st.side("p1")["a"].hp == 150        # original untouched


def test_transition_clamps_hp_nonnegative():
    st = _state()
    nxt = approx_turn2_state(st, our_side="p1", applied_damage={("p2", "a"): 9999})
    assert nxt.side("p2")["a"].hp == 0 and nxt.side("p2")["a"].fainted is True
```

- [ ] **Step 2: Run → RED** (ImportError for `search`).
- [ ] **Step 3: Implement** — the precise algorithm:

```python
# battle/search.py
from __future__ import annotations

import copy

from showdown_bot.engine.state import BattleState


def approx_turn2_state(state: BattleState, *, our_side: str,
                       applied_damage: dict[tuple[str, str], float]) -> BattleState:
    """Coarse turn-2 successor: deep-copy `state`, subtract `applied_damage`
    (expected HP by (side, slot)) clamped >=0, mark 0-HP mons fainted, advance the
    turn. The FieldState (weather/trick_room/tailwind) has no turn counters, so it
    PERSISTS (a documented approximation). Does NOT model move secondary effects,
    switches beyond the applied damage, or item/ability triggers — that is the
    'coarse' in coarse-depth-2 (see the design spec)."""
    nxt = copy.deepcopy(state)
    for (side, slot), dmg in applied_damage.items():
        mon = nxt.sides.get(side, {}).get(slot)
        if mon is None:
            continue
        mon.hp = max(0, int(mon.hp - dmg))
        if mon.hp == 0:
            mon.fainted = True
    nxt.turn = (nxt.turn or 0) + 1
    return nxt
```

- [ ] **Step 4: Run → GREEN.** `cd showdown_bot && python -m pytest tests/test_search_depth2.py -q`
- [ ] **Step 5: Commit** — `feat(2c-depth2): coarse turn-2 state approximation`

---

### Task 3: `depth2_value` recursion (reuse the 1-ply machinery)

Given a turn-1 line and its applied damage, build the approx turn-2 state and compute a 1-ply value there (my best turn-2 action vs the opponent's top-M turn-2 responses, aggregated by the SAME `aggregate_scores`). Returns the depth-2 leaf value for that (my turn-1, opp turn-1) pair.

**Files:** Modify `search.py`; extend `test_search_depth2.py`.

- [ ] **Step 1: Failing test** — with fake `predict_responses`/`DamageModel`/`aggregate_scores` collaborators injected (keep `depth2_value` dependency-injected so it is unit-testable without the calc):

```python
def test_depth2_value_is_turn2_aggregate(monkeypatch):
    from showdown_bot.battle import search
    # fake turn-2 world: one opp response, evaluate_line returns fixed values,
    # aggregate returns the max over my turn-2 actions.
    monkeypatch.setattr(search, "predict_responses", lambda *a, **k: [
        type("R", (), {"actions": [], "weight": 1.0})()])
    my_turn2 = {"A": [1.0], "B": [3.0]}     # B is better at turn 2
    monkeypatch.setattr(search, "_score_turn2_plans",
                        lambda *a, **k: [("A", my_turn2["A"]), ("B", my_turn2["B"])])
    monkeypatch.setattr(search, "aggregate_scores", lambda scores, *a, **k: max(scores))
    monkeypatch.setattr(search, "pick_best",
                        lambda items, *a, **k: max(items, key=lambda it: max(it[1])))
    v = search.depth2_value(_state(), our_side="p1", applied_damage={},
                            mode="NEUTRAL", risk_lambda=0.5, top_m=2,
                            book=None, oracle=None, predict_kwargs={}, model_kwargs={},
                            eval_kwargs={})
    assert v == 3.0     # my best turn-2 action's value
```

(The exact collaborator seam — a private `_score_turn2_plans` that enumerates my turn-2 actions, builds the turn-2 `DamageModel`/`evaluate_line` score vectors, mirroring the single-world `score_plan` — is developed here against this test. Reuse `enumerate_my_actions`, `_plan_my_actions`, `DamageModel`, `evaluate_line`, and `aggregate_scores`/`pick_best` exactly as `_choose_best` does, but on the approx turn-2 state, capped to `top_m` opponent responses.)

- [ ] **Step 2: RED.** - [ ] **Step 3: Implement** `depth2_value` + `_score_turn2_plans` reusing the 1-ply seam on `approx_turn2_state(...)`, opponent responses capped to `top_m`, damage enqueued into the passed shared `oracle` (NOT flushed here — Task 4 flushes once). - [ ] **Step 4: GREEN.** - [ ] **Step 5: Commit** — `feat(2c-depth2): depth2_value recursion over the approx turn-2 state`

---

### Task 4: wire the depth-2 wrap into `_choose_best` (single-world path, guarded) + shared-oracle cache reuse

**CORRECTED against the built `depth2_value` (Task 3, `b7ea7d5`) — the original plan had three API-mismatch errors; the real design is below. Read `battle/search.py` and decision.py 358-393 first.**

**Key facts the implementer MUST honor (verified against code):**
- **`depth2_value` returns the leaf value directly** — it evaluates internally (its `_score_turn2_plans` → `evaluate_line` → `damage_fn` → `oracle.get()`, and `DamageOracle.get` auto-flushes any pending request, oracle.py:56-57). There is **NO** "enqueue-only, flush-once, read-back" split. Call it per (selected line, selected response); it comes back with the value. The shared `oracle` buys **cache reuse** across turn-1 and turn-2 calcs (identical calcs dedupe), NOT a single Node round trip. Whether N×M1 auto-flushes fit the budget is precisely what the Task 6 stage-1 latency gate measures — do the simple thing here.
- **`applied_damage` bridge (load-bearing — get this wrong and depth-2 is silently a no-op):** the per-slot turn-1 damage comes from `evaluate_line(...)[1]` (a `TurnOutcome`, resolve.py:73). `TurnOutcome.hp_delta[(side,slot)]` is a **fraction** (`new_frac − start_frac`, ≤0 for damage), NOT absolute HP. `approx_turn2_state` wants **absolute HP**. Convert with the exact helper below (verified to reconstruct the outcome's resulting HP: `mon.hp − (−delta·max_hp) = new_frac·max_hp`). Note the 1-ply `score_plan` discards `[1]` — so the depth-2 branch must capture it (a `score_plan` variant returning `(score, outcome)`), NOT re-run `evaluate_line`.
- **Vector-length alignment:** the 1-ply score vector for a candidate is length-R (one entry per `opp_resps`), aligned with `resp_weights` (length R). Depth-2 must **replace only the top-M1 response *slots*** of a selected candidate (keeping length R), so `pick_best(items, …, weights=resp_weights)` stays aligned. Do NOT hand `pick_best` a shorter vector.
- **Three distinct caps:** **N** = how many of *my* turn-1 candidate lines get depth-2 (`_search_topn()`, default 2); **M1** = how many of *that line's* `opp_resps` slots get expanded to depth-2 (`_search_topm()`, default 2, the highest-weight response indices — the SAME indices for every candidate since `opp_resps` is action-independent); **M2** = `depth2_value`'s own `top_m` (turn-2 opponent leaf cap, pass 2). `_search_topn`/`_search_topm` read `SHOWDOWN_SEARCH_TOPN`/`SHOWDOWN_SEARCH_TOPM` (default 2); do **NOT** add them to `BEHAVIOR_AFFECTING` (they are unused at depth=1, so keeping them out preserves byte-identical-off even if someone exports them; the gate records them in its own run manifest).

**Files:** Modify `decision.py` (single-world branch only, and add `_search_topn`/`_search_topm` + `_applied_damage_from_outcome`); extend `test_search_depth2.py`.

- [ ] **Step 1: Failing tests** — (a) **off-parity**: with `SHOWDOWN_SEARCH_DEPTH` unset, the single-world decision on a fixed fake-calc fixture (reuse `test_decision_trace.py`'s fixture) returns the SAME choice + trace as before; (b) **bridge**: `_applied_damage_from_outcome(outcome, state)` on a hand-built `TurnOutcome(hp_delta={("p2","a"): -0.5})` with a 150-max_hp mon → `{("p2","a"): 75.0}` (and a `+0.1` heal delta → absent/0); (c) **depth-2 fires + frontier bound**: with `SHOWDOWN_SEARCH_DEPTH=2` + `SHOWDOWN_WORLD_SAMPLES` unset, monkeypatch `decision.depth2_value` to a spy returning a fixed float; assert it is called **exactly N×M1 times** (only the top-N candidates × their top-M1 response slots), the decision returns a legal choice, and a non-selected candidate's score vector is byte-unchanged from its 1-ply value.

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement.** Add the bridge helper to `decision.py`:

```python
def _applied_damage_from_outcome(outcome, state) -> dict[tuple[str, str], float]:
    """Absolute-HP damage per (side, slot) from a turn-1 TurnOutcome, for
    approx_turn2_state. hp_delta is FRACTIONAL (new_frac - start_frac, <=0 for
    damage); convert to abs HP via the CURRENT (turn-1) max_hp. Heals (delta>=0)
    contribute no subtraction."""
    dmg: dict[tuple[str, str], float] = {}
    for (side, slot), delta in outcome.hp_delta.items():
        if delta >= 0:
            continue
        mon = state.sides.get(side, {}).get(slot)
        if mon is not None:
            dmg[(side, slot)] = -delta * mon.max_hp
    return dmg
```

In the **single-world path only**, AFTER building `opp_resps`/`resp_weights`/`model` and ONLY inside `if _search_depth() > 1 and _world_samples() <= 1:` (else the verbatim `score_plan`/`items` block runs → byte-identical):
  1. score with a variant that keeps outcomes: `full = {ja: [(evaluate_line(state, plan, r.actions, model.damage_fn, our_side=our_side, weights=weights, field=state.field, rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board)) for r in opp_resps] for ja, plan in plans.items()}` (each entry is `(score, outcome)`; handle the empty-`opp_resps` case exactly as the 1-ply path does). Build `items = [(ja, [s for s, _o in vec]) for ja, vec in full.items()]` — identical numbers to the 1-ply vectors.
  2. rank `items` by `aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights)`; take the top-**N** `ja`s. Determine the top-**M1** response indices once: the M1 highest-weight indices of `opp_resps` (if `resp_weights` is None, the first M1).
  3. for each selected `ja` and each selected response index `i`: `ad = _applied_damage_from_outcome(full[ja][i][1], state)`; `v = depth2_value(state, our_side=our_side, applied_damage=ad, mode=mode, risk_lambda=risk_lambda, top_m=2, book=book, oracle=model.oracle, predict_kwargs={...}, model_kwargs={...}, eval_kwargs={...})`; overwrite that candidate's score-vector slot: `items[<ja>][1][i] = v`. Keep every other slot (and every non-selected candidate) at its 1-ply value. **Pass only side-neutral collaborators in `predict_kwargs`/`model_kwargs`** (e.g. `dex`, `speed_oracle`; `our_spreads`/`opp_sets` for the model) — do NOT pass `opp_sets`/`threatened_slots`/`priors` into the role-reversed my-side `predict_responses`, they are side-specific (see search.py `_score_turn2_plans` docstring). For the de-risk, minimal kwargs are correct; the coarse leaf only needs to move decisions, not be exact.
  4. `best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)` — unchanged aggregator, unchanged shape.
- [ ] **Step 4: GREEN** + run the decision-trace + K-world guard suites to prove no interaction:
  `cd showdown_bot && python -m pytest tests/test_search_depth2.py tests/test_decision_trace.py tests/test_world_sampling_decision.py -q`
- [ ] **Step 5: Commit** — `feat(2c-depth2): guarded depth-2 wrap in _choose_best (off=verbatim)`

---

### Task 5: off-parity + config_hash + full-suite green

- [ ] **Step 1** Confirm INV-off-byte-identical: a decision-parity fixture (`SHOWDOWN_SEARCH_DEPTH` unset == `main`), config_hash unchanged when unset / changed when 2. - [ ] **Step 2** Run the full suite unset: `cd showdown_bot && python -m pytest -q` → expect the pre-slice pass count (byte-identical-off). - [ ] **Step 3** Run a K=2/depth=2 smoke to confirm no crash. - [ ] **Step 4: Commit** — `test(2c-depth2): off-parity + full-suite green`.

---

### Task 6 (Controller): stage-1 latency gate + stage-2 offline decision-diff (the de-risk)

Not code — the de-risk ladder. **Stage 1 latency:** local micro-bench (like the +Sampling gate) OR Kaggle env-A/B `SHOWDOWN_SEARCH_DEPTH∈{1,2}` on a depth-bound board (`tailwind_both`): p95<1000ms, find max (N, M); prove byte-identical-off. **Stage 2 kill-switch:** reuse the Spec-01 `decision-diff` + the disagreement atlas — does depth-2 CHANGE decisions in the depth-bound buckets vs depth-1? If ~none → STOP (depth moot here, ~0 Kaggle). **Stage 3 (only if stage 2 positive):** small Kaggle winrate probe (depth-1 vs depth-2) analyzed on 05's measurement wall. Write a short verdict report.

---

## Self-review

- **Spec coverage:** toggle (T1), transition (T2), recursion (T3), wrap+single-flush+expectimax backup (T4), off-parity/determinism (T4/T5), de-risk ladder (T6). Covered.
- **Placeholders:** T2's tests are exact; T3/T4 are TDD with exact tests + the precise reuse-seam (the exact turn-2 `_score_turn2_plans` mirrors the verified `score_plan` seam) — deliberately test-driven for the research-y recursion, not vague.
- **Type consistency:** `applied_damage: dict[(side,slot)->float]` threads T2→T3→T4; `depth2_value` returns a float leaf value; `pick_best`/`aggregate_scores` signatures match `_choose_best`.
- **Ambiguity:** N/M defaults (2/2) are explicit + confirmed by the stage-1 latency gate.

## Execution handoff

Subagent-driven (recommended): fresh Sonnet per task, Fable reviews the diff+tests between each (project norm). T2–T4 are the code-heavy core; T4 is the intricate one (review carefully). T6 is controller/Fable.

# 2c +Sampling machinery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Wrap the 1-ply per-candidate eval in a loop over K sampled opponent-set worlds, behind `SHOWDOWN_WORLD_SAMPLES` (off/≤1 → byte-identical), reusing the aggregator; find the max K under the latency budget.

**Architecture:** A pure `world_sampler` (crude 2-point distribution from existing `SpreadBook`+curated `opp_sets`, seeded/stratified). A `DamageModel.enqueue`/`flush` split so K models share ONE oracle flush. A guarded K-world branch in `_choose_best` that builds a flat (world×response) score vector + weights and passes them to the unchanged `pick_best`. Off path runs the existing code verbatim.

**Tech Stack:** Python 3.12, pytest. `PYTHONPATH=showdown_bot/src python -m pytest ...` from the worktree root (`.claude/worktrees/2c-sampling`). Branch `feat/slice-2c-sampling`. NOTE: run `npm ci` in `showdown_bot/tools/calc` once before calc-dependent tests (fresh worktree lacks node_modules).

---

## File Structure

- `showdown_bot/src/showdown_bot/engine/belief/world_sampler.py` — NEW: `world_samples()` reader, `world_seed()`, `build_world_dist()`, `sample_worlds()`. Pure, no I/O, no battles.
- `showdown_bot/src/showdown_bot/battle/evaluate.py` — MODIFY `DamageModel`: split `prefetch` into `enqueue` + `flush`.
- `showdown_bot/src/showdown_bot/battle/decision.py` — MODIFY `_choose_best`: guarded K-world branch around the score_plan region.
- `showdown_bot/src/showdown_bot/eval/config_env.py` — MODIFY: classify `SHOWDOWN_WORLD_SAMPLES` BEHAVIOR_AFFECTING.
- Tests: `test_world_sampler.py` (new), `test_evaluate_enqueue.py` (new), extend `test_config_env.py`, `test_decision_world_sampling.py` (new: K=1 equivalence + off-parity + K≥2 structure with fakes).

---

### Task 1: world_sampler (reader + seed + distribution + sampler)

**Files:** Create `showdown_bot/src/showdown_bot/engine/belief/world_sampler.py`; Test `showdown_bot/tests/test_world_sampler.py`.

- [ ] **Step 1: Write the failing tests**

Create `showdown_bot/tests/test_world_sampler.py`:

```python
import pytest
from showdown_bot.engine.belief.hypotheses import SpreadPreset, SpeciesSpreads, SpreadBook
from showdown_bot.engine.belief import world_sampler as ws


def _spreads(nature):
    p = SpreadPreset(nature=nature, evs={"hp": 4}, items=[])
    return SpeciesSpreads(offense=p, defense=p)


def _book():
    d = _spreads("Hardy")
    return SpreadBook(default=d, species={"incineroar": _spreads("Adamant")})


def test_world_samples_default_is_one(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    assert ws.world_samples() == 1


def test_world_samples_clamps(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "8"); assert ws.world_samples() == 8
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "0"); assert ws.world_samples() == 1
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "999"); assert ws.world_samples() == 32
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "nan"); assert ws.world_samples() == 1


def test_world_seed_deterministic():
    a = ws.world_seed("base", 3, "boardkey")
    b = ws.world_seed("base", 3, "boardkey")
    c = ws.world_seed("base", 4, "boardkey")
    assert a == b and a != c and isinstance(a, int)


def test_build_world_dist_two_point_when_curated_differs():
    book = _book()
    curated = _spreads("Timid")  # differs from book's Adamant incineroar
    opp_sets = {"incineroar": curated}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    assert "incineroar" in dist
    sets = [s for s, w in dist["incineroar"]]
    assert curated in sets and book.get("Incineroar") in sets
    assert abs(sum(w for _, w in dist["incineroar"]) - 1.0) < 1e-9


def test_build_world_dist_omits_fixed_mons():
    # no curated set -> single candidate -> omitted (world never varies this mon)
    dist = ws.build_world_dist([("incineroar", "Incineroar")], _book(), {})
    assert dist == {}


def test_sample_worlds_k1_is_most_likely_only():
    book = _book()
    opp_sets = {"incineroar": _spreads("Timid")}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    worlds = ws.sample_worlds(dist, 1, seed=123)
    assert len(worlds) == 1
    w0, weight = worlds[0]
    assert w0["incineroar"] == opp_sets["incineroar"]  # curated = argmax
    assert weight == pytest.approx(1.0)


def test_sample_worlds_stratified_and_normalized():
    book = _book()
    opp_sets = {"incineroar": _spreads("Timid")}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    worlds = ws.sample_worlds(dist, 4, seed=7)
    assert len(worlds) == 4
    assert worlds[0][0]["incineroar"] == opp_sets["incineroar"]  # most-likely first
    assert abs(sum(w for _, w in worlds) - 1.0) < 1e-9


def test_sample_worlds_deterministic():
    book = _book(); opp_sets = {"incineroar": _spreads("Timid")}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    assert ws.sample_worlds(dist, 4, seed=7) == ws.sample_worlds(dist, 4, seed=7)


def test_empty_dist_returns_one_empty_world():
    worlds = ws.sample_worlds({}, 4, seed=7)
    assert worlds == [({}, 1.0)]
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_world_sampler.py -q`
Expected: FAIL — `ModuleNotFoundError`/`AttributeError` (module not present).

- [ ] **Step 3: Implement `world_sampler.py`**

Create `showdown_bot/src/showdown_bot/engine/belief/world_sampler.py`:

```python
"""K-world opponent-set sampling for the +Sampling decision axis (2c).

A "world" = a dict ``{to_id(species) -> SpeciesSpreads}`` (opp_sets shape) that
DamageModel/predict_responses already consume. This builds a CRUDE placeholder
distribution from existing data (curated likely-sets vs worst-case book) and
samples K joint worlds deterministically. Pure, no I/O, no RNG globals."""
from __future__ import annotations

import hashlib
import os
import random

from showdown_bot.engine.belief.hypotheses import SpreadBook, SpeciesSpreads
from showdown_bot.engine.state import to_id

_CURATED_WEIGHT = 0.6
_WORSTCASE_WEIGHT = 0.4


def world_samples() -> int:
    """Number of sampled opponent worlds K (SHOWDOWN_WORLD_SAMPLES), clamped to
    [1, 32]. Default/unparsable/<=0 -> 1 (single most-likely world = byte-identical)."""
    try:
        return max(1, min(32, int(os.environ.get("SHOWDOWN_WORLD_SAMPLES", "1"))))
    except ValueError:
        return 1


def world_seed(seed_base: str, turn: int, board_key: str) -> int:
    """Deterministic per-decision seed via the eval/seeding.py sha256 convention.
    Same (seed_base, turn, board_key) -> same seed -> same worlds."""
    h = hashlib.sha256(f"{seed_base}:{turn}:{board_key}".encode()).hexdigest()
    return int(h[:16], 16)


def build_world_dist(
    opp_mons: list[tuple[str, str]],
    book: SpreadBook,
    opp_sets: dict[str, SpeciesSpreads],
) -> dict[str, list[tuple[SpeciesSpreads, float]]]:
    """Per opponent mon (given as ``(to_id, species_name)``), a weighted candidate
    list of ``SpeciesSpreads``. CRUDE 2-point: curated (if present AND != book
    worst-case) weighted _CURATED_WEIGHT vs the book worst-case _WORSTCASE_WEIGHT,
    renormalized. Mons with a single distinct candidate are OMITTED (they never
    vary -> DamageModel uses its default, same as today)."""
    dist: dict[str, list[tuple[SpeciesSpreads, float]]] = {}
    for tid, species_name in opp_mons:
        wc = book.get(species_name)
        curated = opp_sets.get(tid)
        if curated is not None and curated != wc:
            total = _CURATED_WEIGHT + _WORSTCASE_WEIGHT
            dist[tid] = [(curated, _CURATED_WEIGHT / total), (wc, _WORSTCASE_WEIGHT / total)]
    return dist


def sample_worlds(
    dist: dict[str, list[tuple[SpeciesSpreads, float]]],
    k: int,
    *,
    seed: int,
) -> list[tuple[dict[str, SpeciesSpreads], float]]:
    """K joint worlds + normalized weights. World 0 is always the most-likely
    (each mon's highest-weight set). Worlds 1..K-1 are i.i.d. draws. Empty dist ->
    a single empty world (weight 1.0) = no variation."""
    if not dist:
        return [({}, 1.0)]
    tids = sorted(dist)  # stable order
    # most-likely world (stratified index 0)
    most_likely = {tid: max(dist[tid], key=lambda sw: sw[1])[0] for tid in tids}
    raw: list[tuple[dict, float]] = [(most_likely, _world_prob(most_likely, dist))]
    rng = random.Random(seed)
    for _ in range(max(0, k - 1)):
        world = {tid: _draw(dist[tid], rng) for tid in tids}
        raw.append((world, _world_prob(world, dist)))
    total_w = sum(w for _, w in raw) or 1.0
    return [(world, w / total_w) for world, w in raw]


def _draw(candidates: list[tuple[SpeciesSpreads, float]], rng: random.Random) -> SpeciesSpreads:
    r = rng.random()
    acc = 0.0
    for spreads, w in candidates:
        acc += w
        if r <= acc:
            return spreads
    return candidates[-1][0]


def _world_prob(world: dict[str, SpeciesSpreads], dist: dict) -> float:
    p = 1.0
    for tid, spreads in world.items():
        p *= next((w for s, w in dist[tid] if s == spreads), 0.0)
    return p
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_world_sampler.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/engine/belief/world_sampler.py showdown_bot/tests/test_world_sampler.py
git commit -m "feat(2c-sampling): world_sampler (crude dist + seeded stratified K-world sampling)"
```

---

### Task 2: Classify `SHOWDOWN_WORLD_SAMPLES` BEHAVIOR_AFFECTING

**Files:** Modify `showdown_bot/src/showdown_bot/eval/config_env.py`; Test `showdown_bot/tests/test_config_env.py`.

- [ ] **Step 1: Append the failing tests** to `showdown_bot/tests/test_config_env.py` (the referenced helpers are already imported there):

```python
# --- +Sampling world count (2c-sampling) -----------------------------------------------

def test_world_samples_behavior_affecting_and_classified():
    assert "SHOWDOWN_WORLD_SAMPLES" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_WORLD_SAMPLES" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_WORLD_SAMPLES")


def test_config_hash_changes_when_world_samples_set():
    h_off = make_config_hash(_manifest(behavior_env({})))
    h_on = make_config_hash(_manifest(behavior_env({"SHOWDOWN_WORLD_SAMPLES": "4"})))
    assert h_off != h_on
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_config_env.py -q -k world_samples`
Expected: FAIL — name not in BEHAVIOR_AFFECTING.

- [ ] **Step 3: Add to `BEHAVIOR_AFFECTING`** in `config_env.py`, immediately after the `SHOWDOWN_NEUTRAL_CVAR`/`SHOWDOWN_CVAR_*` block (or after `SHOWDOWN_RISK_LAMBDA` if that block is absent on this branch — this branch is off main, which has neither CVaR nor risk-only additions beyond the merged set; add after `SHOWDOWN_RISK_LAMBDA`):

```python
    # [2c-sampling] K sampled opponent-set worlds in _choose_best -> changes which
    # candidate wins (aggregation over sampled worlds) -> config_hash. Off/<=1 = 1
    # world = byte-identical.
    "SHOWDOWN_WORLD_SAMPLES",
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_config_env.py -q`
Expected: PASS (incl. the `test_behavior_affecting_flags_are_actually_read_in_source` hardening test — `world_samples()` in world_sampler.py reads `os.environ.get("SHOWDOWN_WORLD_SAMPLES")`, so it is "read in source" once Task 1 is committed; Task 1 precedes Task 2, so this is green).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/config_env.py showdown_bot/tests/test_config_env.py
git commit -m "feat(2c-sampling): classify SHOWDOWN_WORLD_SAMPLES behavior-affecting"
```

---

### Task 3: `DamageModel.enqueue`/`flush` split (shared-oracle single flush)

**Files:** Modify `showdown_bot/src/showdown_bot/battle/evaluate.py` (`DamageModel.prefetch`); Test `showdown_bot/tests/test_evaluate_enqueue.py` (new).

- [ ] **Step 1: Write the failing test** — `showdown_bot/tests/test_evaluate_enqueue.py`:

```python
# Enqueue must NOT flush; prefetch must enqueue THEN flush. Uses a fake oracle to
# count flushes without any Node/calc.
from showdown_bot.battle.evaluate import DamageModel


class _FakeOracle:
    def __init__(self): self.requests = 0; self.flushes = 0
    def request(self, req): self.requests += 1
    def flush(self): self.flushes += 1
    def get(self, req): return 0.0


def _model(monkeypatch):
    # Bypass __init__'s hyp building: construct a bare model with a controllable oracle.
    m = DamageModel.__new__(DamageModel)
    m.oracle = _FakeOracle()
    m.hyps = {}
    return m


def test_enqueue_does_not_flush(monkeypatch):
    m = _model(monkeypatch)
    m.enqueue([])            # empty groups -> no requests, but MUST NOT flush
    assert m.oracle.flushes == 0


def test_prefetch_flushes_once(monkeypatch):
    m = _model(monkeypatch)
    m.prefetch([])
    assert m.oracle.flushes == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_evaluate_enqueue.py -q`
Expected: FAIL — `DamageModel` has no `enqueue`.

- [ ] **Step 3: Split `prefetch`** in `evaluate.py`. Replace the current `prefetch` method (the one that ends with `self.oracle.flush()`) with:

```python
    def enqueue(self, action_groups: Iterable[list[PlannedAction]]) -> None:
        """Enqueue every damaging calc across all candidate lines into the oracle
        WITHOUT flushing -- so K models sharing one oracle can be flushed once."""
        for actions in action_groups:
            for a in actions:
                if a.kind != "move" or not a.move or not a.move.is_damaging:
                    continue
                if (a.side, a.slot) not in self.hyps:
                    continue
                for tgt in self._candidate_targets(a):
                    if tgt in self.hyps:
                        self.oracle.request(self._request(a, tgt))

    def prefetch(self, action_groups: Iterable[list[PlannedAction]]) -> None:
        """Enqueue then flush -- a single Node round trip per decision (unchanged)."""
        self.enqueue(action_groups)
        self.oracle.flush()
```

- [ ] **Step 4: Run to verify it passes + no calc regression**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_evaluate_enqueue.py showdown_bot/tests/test_hypotheses.py showdown_bot/tests/test_calc_persistent.py -q`
Expected: PASS (the calc tests confirm `prefetch` behavior is byte-identical; needs `npm ci` in tools/calc first).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/tests/test_evaluate_enqueue.py
git commit -m "feat(2c-sampling): DamageModel.enqueue/flush split (single flush across K models)"
```

---

### Task 4: K-world branch in `_choose_best` (the hot path — guarded)

**Files:** Modify `showdown_bot/src/showdown_bot/battle/decision.py` (the region currently lines ~282-315, from `opp_resps = predict_responses(...)` through `best_ja, best_val = pick_best(...)`); Test in Task 5.

- [ ] **Step 1: Read the current region** — confirm lines 282-315 match the block below (the `else` branch preserves them verbatim). Add the import near the top of decision.py (with the other belief imports):

```python
from showdown_bot.engine.belief.world_sampler import (
    build_world_dist, sample_worlds, world_samples, world_seed,
)
from showdown_bot.engine.state import to_id
```
(If `to_id` is already imported in decision.py, do not duplicate.)

- [ ] **Step 2: Replace** the current block (from `opp_resps = predict_responses(` at ~line 282 through the `best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)` at ~line 315) with the guarded version:

```python
    if world_samples() > 1:
        # --- K-world opponent-set sampling (2c +Sampling) ---
        opp_mons = [(to_id(mon.species), mon.species)
                    for mon in state.side(opp_side).values()]
        dist = build_world_dist(opp_mons, book, opp_sets or {})
        seed = world_seed(os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "world"),
                          getattr(state, "turn", 0) or 0, _board_key(state, opp_side))
        worlds = sample_worlds(dist, world_samples(), seed=seed)
        shared_oracle = oracle or DamageOracle()
        world_ctx = []  # (world_weight, opp_resps_k, model_k)
        for world_sets, world_w in worlds:
            merged_sets = {**(opp_sets or {}), **world_sets}
            resps_k = predict_responses(
                state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
                dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
                opp_sets=merged_sets,
            )
            model_k = DamageModel(
                state, our_side, opp_side, book=book, oracle=shared_oracle,
                field=state.field, our_spreads=our_spreads, opp_sets=merged_sets,
            )
            model_k.enqueue(list(plans.values()) + [r.actions for r in resps_k])
            world_ctx.append((world_w, resps_k, model_k))
        shared_oracle.flush()

        def score_plan(my_plan: list[PlannedAction]) -> list[float]:
            out: list[float] = []
            for _w, resps_k, model_k in world_ctx:
                targets = [r.actions for r in resps_k] if resps_k else [[]]
                for opp_actions in targets:
                    out.append(evaluate_line(
                        state, my_plan, opp_actions, model_k.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                    )[0])
            return out

        resp_weights = []
        for world_w, resps_k, _model_k in world_ctx:
            if priors is not None and resps_k:
                resp_weights.extend(world_w * r.weight for r in resps_k)
            else:
                resp_weights.append(world_w)
        items = [(ja, score_plan(plan)) for ja, plan in plans.items()]
        best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)
    else:
        # --- single-world path (unchanged; byte-identical when world_samples()<=1) ---
        opp_resps = predict_responses(
            state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
            dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
            opp_sets=opp_sets,
        )
        resp_weights = [r.weight for r in opp_resps] if (priors is not None and opp_resps) else None

        model = DamageModel(
            state, our_side, opp_side, book=book, oracle=oracle, field=state.field,
            our_spreads=our_spreads, opp_sets=opp_sets,
        )
        groups = list(plans.values()) + [r.actions for r in opp_resps]
        model.prefetch(groups)

        def score_plan(my_plan: list[PlannedAction]) -> list[float]:
            if opp_resps:
                return [
                    evaluate_line(
                        state, my_plan, r.actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                    )[0]
                    for r in opp_resps
                ]
            return [
                evaluate_line(
                    state, my_plan, [], model.damage_fn,
                    our_side=our_side, weights=weights, field=state.field,
                    rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                )[0]
            ]

        items = [(ja, score_plan(plan)) for ja, plan in plans.items()]
        best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)
```

- [ ] **Step 3: Add the `_board_key` helper** near the other module-level helpers in decision.py:

```python
def _board_key(state, opp_side: str) -> str:
    """A stable per-decision string for seeding the world sampler: opponent species
    + hp buckets + field. Same board -> same worlds (determinism)."""
    parts = []
    for slot, mon in sorted(state.side(opp_side).items()):
        parts.append(f"{slot}:{mon.species}:{int((mon.hp_fraction or 0) * 20)}")
    field = getattr(state, "field", None)
    return "|".join(parts) + "#" + str(field)
```

- [ ] **Step 4: Verify import/syntax + full-file load**

Run: `PYTHONPATH=showdown_bot/src python -c "import showdown_bot.battle.decision"`
Expected: no error (imports resolve, syntax valid).

- [ ] **Step 5: Commit** (tests land in Task 5)

```bash
git add showdown_bot/src/showdown_bot/battle/decision.py
git commit -m "feat(2c-sampling): guarded K-world branch in _choose_best (off=verbatim single-world)"
```

---

### Task 5: Off-parity + K=1 equivalence + full-suite verification

**Files:** Test `showdown_bot/tests/test_decision_world_sampling.py` (new).

- [ ] **Step 1: Write the equivalence/parity tests.** Create `showdown_bot/tests/test_decision_world_sampling.py`. Use the SAME fixture the existing decision tests use (look in `showdown_bot/tests/` for a helper that builds a `Request`/`BattleState` for `heuristic_choose_for_request` or `_choose_best_ja`; reuse it). The two load-bearing tests:

```python
import showdown_bot.battle.decision as decision
# Reuse an existing decision fixture. Find one in the repo, e.g. from
# test_decision*.py: a function returning a (request/state, kwargs) that
# heuristic_choose_for_request accepts. Import and reuse it here rather than
# hand-rolling a BattleState.

def test_world_samples_off_matches_baseline(monkeypatch, <fixture>):
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    choice_off = <call heuristic_choose_for_request on the fixture>
    # Baseline is the same call; this asserts the guard's else-branch is the live path.
    assert choice_off == <expected baseline choice from the fixture's existing test>


def test_world_samples_k1_equals_off(monkeypatch, <fixture>):
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    off = <call on fixture>
    # Forcing the K-world branch at K=1 must equal the off path (most-likely world
    # == opp_sets). We reach the branch via world_samples()>1, so test K=2 with a
    # fixture whose opponent has NO curated set that differs -> dist empty -> single
    # empty world -> identical choice:
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    k_empty = <call on a fixture with no curated opp sets>
    assert k_empty == off
```

(If no reusable decision fixture exists, this task's implementer must first extract the minimal fixture the existing `test_decision*.py` uses into a shared helper and import it — do NOT hand-build a `BattleState`.)

- [ ] **Step 2: Run the new tests**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_decision_world_sampling.py -q`
Expected: PASS. (If `test_world_samples_k1_equals_off` fails, the K-world branch diverges from the single-world path when it should not — fix the branch, do not weaken the test.)

- [ ] **Step 3: Full suite**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests -q` (after `npm ci` in tools/calc)
Expected: prior green count + the new tests, 0 failures. Any failure in decision/policy/evaluate is in scope — fix it; unrelated calc failures only if node_modules missing.

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/tests/test_decision_world_sampling.py
git commit -m "test(2c-sampling): off-parity + K=1 equivalence for the world-sampling branch"
```

- [ ] **Step 5: Closeout note** — the gate is out of band (controller, Kaggle): env-A/B on `2b4_devstrength_v001` at `SHOWDOWN_WORLD_SAMPLES` ∈ {1,2,4,8}, measure latency p95 (find max K < 1000 ms), confirm byte-identical when off (results == main baseline), no winrate regression, determinism. NOT a winrate GO. No held-out.

---

## Self-Review

**Spec coverage:** sampler+seed+dist (T1) ✓; env classified (T2) ✓; shared-oracle single flush (T3) ✓; guarded K-world branch, flat weights = world×response, aggregator unchanged (T4) ✓; off-byte-identical + K=1 equivalence (T5) ✓; latency/no-regression/determinism gate (T5 closeout, out-of-band) ✓. Crude distribution refined to 2-point per spec's intent (documented in T1).

**Placeholder scan:** T5 intentionally references "an existing decision fixture" rather than inventing a `BattleState` — this is a *reuse instruction*, not a placeholder; the implementer must locate + reuse the real fixture (hand-building state would be wrong). All code steps have concrete code.

**Type consistency:** `world_samples()/world_seed()/build_world_dist()/sample_worlds()` signatures identical across T1 def, T4 calls, and tests. A "world" is `dict[to_id -> SpeciesSpreads]` throughout; `merged_sets = {**opp_sets, **world_sets}` keeps non-varying mons at their curated/default set. `enqueue`/`prefetch` names consistent T3↔T4.

**Risk note for the controller:** T4 is the hot-path change. Review its diff line-by-line; the `else` branch MUST be the current code verbatim (byte-identical-off depends on it). The Kaggle byte-identical-off proof (results == main with the toggle unset) is the final guarantee before any use.

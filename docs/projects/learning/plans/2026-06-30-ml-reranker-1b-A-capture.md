# Phase 3 Slice 1b-A: Decision capture (battle/) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the real decision emit a read-only, fully-populated `DecisionTrace`
(top-K candidates, score vectors, per-response `OutcomeBreakdown`s) without changing
any chosen action.

**Architecture:** Additive only. `evaluate.py` gains an `OutcomeBreakdown` DTO and a
`score_outcome_with_breakdown` wrapper that `score_outcome` delegates to (single
source, no drift). `decision.py` gains a `trace=` out-param (mirrors `report=`) that,
when present, fills `battle/decision_trace.py` DTOs. `trace=None` ⇒ bit-identical.

**Tech Stack:** Python stdlib + dataclasses + pytest. Spec:
`docs/projects/learning/specs/2026-06-30-ml-reranker-1b-feature-extraction-export-design.md`.
Run tests from `showdown_bot/`. The learning/ feature-extraction + JSONL export
consume this trace in **Plan 1b-B**.

---

## File Structure
- Create: `src/showdown_bot/battle/decision_trace.py` — `CandidateTrace`, `DecisionTrace` (plain DTOs).
- Modify: `src/showdown_bot/battle/evaluate.py` — `OutcomeBreakdown` + `score_outcome_with_breakdown`; `score_outcome` delegates.
- Modify: `src/showdown_bot/battle/decision.py` — `trace=` param on `heuristic_choose_for_request` (+ thread through `choose_with_fallback`); populate when not None.
- Tests: `tests/test_outcome_breakdown.py`, `tests/test_decision_trace.py`.

---

## Task 1: `OutcomeBreakdown` + `score_outcome_with_breakdown`

`OutcomeBreakdown` carries ONLY what `score_outcome` actually computes (total_score,
in/out damage, the protect penalties, KOs/faints). KO-secured / survives counts are
`DamageModel` *queries* (not `score_outcome` internals) and belong to Plan 1b-B.

**Files:**
- Modify: `src/showdown_bot/battle/evaluate.py`
- Test: `tests/test_outcome_breakdown.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_outcome_breakdown.py
from showdown_bot.battle.evaluate import (
    EvalWeights, score_outcome, score_outcome_with_breakdown,
)
# Build outcomes the same way the existing evaluate tests do. Find the helper /
# TurnOutcome construction in tests/test_evaluate.py (or battle/resolve.py) and reuse it.
from tests.helpers_outcome import make_outcome  # if no helper exists, build TurnOutcome inline as resolve.py defines it


def test_total_score_equals_scalar_score_outcome():
    oc = make_outcome(our_side="p1", hp_delta={("p2", "a"): -40, ("p1", "a"): -20}, my_kos=0, my_faints=0)
    w = EvalWeights()
    score, bd = score_outcome_with_breakdown(oc, "p1", w)
    assert bd.total_score == score                 # the invariant anchor
    assert score == score_outcome(oc, "p1", w)     # delegation: old API unchanged


def test_breakdown_damage_split():
    oc = make_outcome(our_side="p1", hp_delta={("p2", "a"): -40, ("p1", "a"): -20}, my_kos=0, my_faints=0)
    _, bd = score_outcome_with_breakdown(oc, "p1", EvalWeights())
    assert bd.predicted_outgoing_damage == 40
    assert bd.predicted_incoming_damage == 20


def test_breakdown_protect_stall_penalty():
    # our Protect that blocked nothing -> protect_stall penalty recorded
    oc = make_outcome(our_side="p1", hp_delta={}, my_kos=0, my_faints=0,
                      flags=["protect:p1a"], protected_hits=[])
    w = EvalWeights()
    _, bd = score_outcome_with_breakdown(oc, "p1", w)
    assert bd.protect_stall_penalty == w.protect_stall
    assert bd.partner_abandon_penalty == 0.0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_outcome_breakdown.py -q`
Expected: FAIL with `ImportError: cannot import name 'score_outcome_with_breakdown'`

- [ ] **Step 3: Implement the breakdown + delegate** — in `evaluate.py`, add the DTO above `score_outcome`, add the wrapper carrying the SAME logic, and make `score_outcome` delegate:

```python
@dataclass
class OutcomeBreakdown:
    total_score: float = 0.0
    predicted_outgoing_damage: float = 0.0
    predicted_incoming_damage: float = 0.0
    my_kos: int = 0
    my_faints: int = 0
    protect_stall_penalty: float = 0.0
    endgame_protect_penalty: float = 0.0
    partner_abandon_penalty: float = 0.0


def score_outcome_with_breakdown(
    outcome: TurnOutcome, our_side: str, weights: EvalWeights | None = None, *, endgame: bool = False
) -> tuple[float, OutcomeBreakdown]:
    w = weights or EvalWeights()
    bd = OutcomeBreakdown(my_kos=outcome.my_kos, my_faints=outcome.my_faints)
    s = 0.0
    s += w.ko * outcome.my_kos
    s += w.faint * outcome.my_faints
    for key, delta in outcome.hp_delta.items():
        lost = -delta
        if lost <= 0:
            continue
        if key[0] == our_side:
            s -= w.dmg_taken * lost
            bd.predicted_incoming_damage += lost
        else:
            s += w.dmg_dealt * lost
            bd.predicted_outgoing_damage += lost
    for prevented in outcome.prevented_actions:
        s += w.tempo_lost if prevented.side == our_side else w.tempo_prevent
    for ph in outcome.protected_hits:
        s += w.protect_block if ph.target[0] == our_side else w.wasted_into_protect
    for flag in outcome.flags:
        parts = flag.split(":")
        if parts[0] == "status" and len(parts) == 3:
            move_id, owner = parts[1], parts[2]
            if move_id in ("tailwind", "trickroom") and owner.startswith(our_side):
                s += w.speed_control
        elif flag == "wasted_move":
            s += w.wasted_move
        elif parts[0] == "switch" and len(parts) == 2 and parts[1].startswith(our_side):
            s += w.switch_cost
    if any(f.startswith(f"protect:{our_side}") for f in outcome.flags):
        blocked = any(ph.target[0] == our_side for ph in outcome.protected_hits)
        if not blocked:
            s += w.protect_stall
            bd.protect_stall_penalty = w.protect_stall
        if endgame:
            s += w.endgame_protect
            bd.endgame_protect_penalty = w.endgame_protect
        if outcome.my_faints > 0:
            s += w.partner_abandon
            bd.partner_abandon_penalty = w.partner_abandon
    bd.total_score = s
    return s, bd


def score_outcome(
    outcome: TurnOutcome, our_side: str, weights: EvalWeights | None = None, *, endgame: bool = False
) -> float:
    return score_outcome_with_breakdown(outcome, our_side, weights, endgame=endgame)[0]
```

Delete the old `score_outcome` body (its logic now lives in the wrapper). `dataclass`
is already imported in `evaluate.py`.

- [ ] **Step 4: Run the new tests + the full suite** (the existing `score_outcome` tests must still pass — behaviour is identical by delegation)

Run: `cd showdown_bot && python -m pytest tests/test_outcome_breakdown.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (was 259; +3).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/tests/test_outcome_breakdown.py
git commit -m "feat(evaluate): OutcomeBreakdown + score_outcome_with_breakdown (score_outcome delegates)"
```

---

## Task 2: `decision_trace.py` DTOs

**Files:**
- Create: `src/showdown_bot/battle/decision_trace.py`
- Test: `tests/test_decision_trace.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_decision_trace.py
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown


def test_dtos_construct_with_defaults():
    dt = DecisionTrace()
    assert dt.candidates == [] and dt.opponent_responses == []
    ct = CandidateTrace(candidate_id="x", joint_action=None, rank=0,
                        aggregate_score=1.0, score_vector=[1.0],
                        outcome_breakdowns=[OutcomeBreakdown()],
                        aggregate_breakdown=OutcomeBreakdown())
    assert ct.candidate_id == "x" and ct.rank == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/test_decision_trace.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `src/showdown_bot/battle/decision_trace.py`** (plain DTOs, no logic, no learning import)

```python
"""Read-only decision artifacts for ML capture (Phase 3 slice 1b).

Plain DTOs only: no logic, no JSONL, no learning import. battle/ populates these;
learning/features.py reads them (learning -> battle, never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from showdown_bot.battle.evaluate import OutcomeBreakdown


@dataclass
class CandidateTrace:
    candidate_id: str
    joint_action: Any
    rank: int                                   # 0 = heuristic's top (by aggregate score)
    aggregate_score: float
    score_vector: list[float]                   # one score per opponent response (parallel to R)
    outcome_breakdowns: list[OutcomeBreakdown]  # parallel to opponent responses
    aggregate_breakdown: OutcomeBreakdown


@dataclass
class DecisionTrace:
    game_mode: str | None = None
    chosen_candidate_id: str | None = None
    opponent_responses: list[Any] = field(default_factory=list)
    opponent_response_weights: list[float] = field(default_factory=list)
    candidates: list[CandidateTrace] = field(default_factory=list)  # ONLY exported top-K, rank-sorted
```

- [ ] **Step 4: Run it + suite**

Run: `cd showdown_bot && python -m pytest tests/test_decision_trace.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (+1).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/decision_trace.py showdown_bot/tests/test_decision_trace.py
git commit -m "feat(battle): DecisionTrace + CandidateTrace read-only DTOs"
```

---

## Task 3: populate the trace in `decision.py` (`trace=` param)

Add `trace: DecisionTrace | None = None` to `heuristic_choose_for_request` AND thread
it through `choose_with_fallback` (which already has `report=` — mirror it exactly).
When `trace is not None`, after `best_ja` is decided, fill the DTOs. **The decision
path is unchanged when `trace is None`.**

The per-response `OutcomeBreakdown`s reuse prefetched calcs via
`evaluate_line(..., rollout_horizon=0)` exactly as the existing `metrics` block in
`heuristic_choose_for_request` already does for the chosen line — extend that pattern
to all top-K candidates × responses. `aggregate_breakdown` = the **weighted mean** of
the per-response breakdowns (see Findings: every game-mode's aggregation is
mean-based; there is no single "selected" response).

**Files:**
- Modify: `src/showdown_bot/battle/decision.py`
- Test: `tests/test_decision_trace.py` (append integration tests)

- [ ] **Step 1: Write the failing tests** (append; reuse whatever fixture the existing decision tests use to build a real `BattleRequest` + `BattleState` + a fake/recorded oracle — see `tests/test_decision*.py`)

```python
def test_trace_off_equivalence(decision_fixture):
    # populating the trace must NOT change the chosen action
    req, kw = decision_fixture
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    choice_a = heuristic_choose_for_request(req, trace=None, **kw)
    choice_b = heuristic_choose_for_request(req, trace=DecisionTrace(), **kw)
    assert choice_a == choice_b


def test_trace_is_populated(decision_fixture):
    req, kw = decision_fixture
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    assert tr.game_mode is not None
    assert tr.chosen_candidate_id is not None
    assert len(tr.candidates) >= 1
    # candidates are rank-sorted (0 = best aggregate score)
    assert [c.rank for c in tr.candidates] == sorted(c.rank for c in tr.candidates)
    top = tr.candidates[0]
    assert len(top.score_vector) == len(top.outcome_breakdowns)        # parallel to R
    assert len(tr.opponent_responses) == len(tr.opponent_response_weights or tr.opponent_responses)


def test_aggregate_breakdown_is_weighted_mean(decision_fixture):
    # The aggregate breakdown must be a WEIGHTED MEAN over responses (not response[0]).
    # Pin rollout_horizon=0 so per-response base scores == the heuristic score_vector;
    # then aggregate_breakdown.total_score must equal the weighted mean of score_vector
    # (it does NOT equal aggregate_score under MUST_REACT's min-blend, by design).
    req, kw = decision_fixture
    kw = {k: v for k, v in kw.items() if k != "rollout_horizon"}
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, rollout_horizon=0, **kw)
    top = tr.candidates[0]
    ws = tr.opponent_response_weights or [1.0] * len(top.score_vector)
    wmean = sum(s * w for s, w in zip(top.score_vector, ws)) / (sum(ws) or 1.0)
    assert abs(top.aggregate_breakdown.total_score - wmean) < 1e-9
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_decision_trace.py -q`
Expected: FAIL (`heuristic_choose_for_request` has no `trace` kwarg)

- [ ] **Step 3: Implement** — add `trace: DecisionTrace | None = None` to both
`heuristic_choose_for_request` and `choose_with_fallback` signatures (thread it
through the call, beside `report=`). Add this block in `heuristic_choose_for_request`
**after** `best_ja` is finalized (right where the `if report is not None:` block is),
reusing `aggregate_scores`, `_label_ja`, and the prefetched `model`:

```python
    if trace is not None:
        from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace  # noqa
        from showdown_bot.battle.evaluate import score_outcome_with_breakdown
        from showdown_bot.battle.policy import aggregate_scores

        rep_resps = [r.actions for r in opp_resps] if opp_resps else [[]]

        def _breakdowns_for(plan):
            bds = []
            for ra in rep_resps:
                _, oc = evaluate_line(
                    state, plan, ra, model.damage_fn, our_side=our_side,
                    weights=weights, field=state.field, rollout_horizon=0, endgame=endgame,
                )
                bds.append(score_outcome_with_breakdown(oc, our_side, weights, endgame=endgame)[1])
            return bds

        def _weighted_mean_breakdown(bds):
            ws = resp_weights or [1.0] * len(bds)
            tot = sum(ws) or 1.0
            agg = OutcomeBreakdown()
            for f in ("total_score", "predicted_outgoing_damage", "predicted_incoming_damage",
                      "my_kos", "my_faints", "protect_stall_penalty",
                      "endgame_protect_penalty", "partner_abandon_penalty"):
                setattr(agg, f, sum(getattr(b, f) * w for b, w in zip(bds, ws)) / tot)
            return agg

        scored = [
            (ja, scores, aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights))
            for ja, scores in items
        ]
        scored.sort(key=lambda t: (-t[2], _label_ja(req, t[0])))   # rank order, stable
        top_k = scored[:TOP_K_TRACE_CANDIDATES]
        cands = []
        for rank, (ja, scores, agg) in enumerate(top_k):
            bds = _breakdowns_for(plans[ja])
            cands.append(CandidateTrace(
                candidate_id=_label_ja(req, ja), joint_action=ja, rank=rank,
                aggregate_score=agg, score_vector=list(scores),
                outcome_breakdowns=bds, aggregate_breakdown=_weighted_mean_breakdown(bds),
            ))
        trace.game_mode = getattr(mode, "name", str(mode))
        trace.chosen_candidate_id = _label_ja(req, best_ja)
        trace.opponent_responses = [r.actions for r in opp_resps]
        trace.opponent_response_weights = resp_weights or []
        trace.candidates = cands
```

Import `OutcomeBreakdown` at the top of the trace block (`from
showdown_bot.battle.evaluate import OutcomeBreakdown`). Add a module-level constant
near the top of `decision.py`: `TOP_K_TRACE_CANDIDATES = 6` (candidates captured per
decision). `evaluate_line`, `plans`, `items`, `opp_resps`, `resp_weights`, `model`,
`mode`, `endgame`, `weights`, `risk_lambda` are all already in scope at that point.

- [ ] **Step 4: Run the trace tests + the full suite** (trace-off equivalence is the safety gate)

Run: `cd showdown_bot && python -m pytest tests/test_decision_trace.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (+2). If the existing tests have no reusable decision fixture, add a minimal one in `tests/conftest.py` mirroring `tests/test_decision*.py` setup.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/tests/test_decision_trace.py showdown_bot/tests/conftest.py
git commit -m "feat(decision): read-only trace= out-param populates DecisionTrace (bit-identical when None)"
```

---

## Self-Review notes + findings surfaced by grounding

**Spec coverage (1b-A = capture):** `OutcomeBreakdown` + delegation (T1); trace DTOs
(T2); `trace=` populate with top-K, score vectors, per-response + aggregate
breakdowns, trace-off equivalence (T3). **Deferred to Plan 1b-B:** `FeatureContext`,
`extract_features` (4 groups + sentinels), `DatasetExporter` (IDs, sampling, sorted
JSONL), the `client/` hook, the hermetic E2E, the stub label.

**Three findings the real code surfaced (decide before/with 1b-B):**
1. **`aggregate_breakdown` reduction:** `aggregate_scores` is mean-based in *every*
   mode (MUST_REACT = `mean − λ(mean − min)`, a blend — not a pure worst-response
   selection). So the cleanest reduction is the **weighted mean** of per-response
   breakdowns for **all** modes; the worst-case/variance shape lives in the scalar
   `score_vector` + the Group-4 risk features. This **revises** the spec's 3-case
   rule (which assumed a selectable worst response).
2. **`OutcomeBreakdown` scope:** `score_outcome` does NOT compute `ko_secured_count`
   / `ko_threatened_count` / `survives_for_sure_count` — those are `DamageModel`
   *queries* (`secures_ko`/`has_ko_chance`/`survives_for_sure`). They are sourced in
   1b-B (from the model handle), not the breakdown.
3. **Two schema columns have no current source:** `fakeout_invalid_penalty` (Fake Out
   is *pruned* in `enumerate_my_actions`, never penalized in scoring) and
   `action_economy_score` (no such term exists). In 1b-B these become documented v1
   **sentinels** (`0.0`) — or we add the terms — your call when 1b-B is specced.

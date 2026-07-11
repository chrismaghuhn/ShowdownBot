# 2c-Slice-0b — Mode-Aware Full-Fidelity Aggregation Export + Probe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Export the true per-candidate × per-opponent-response scores + weights + exact mode + both aggregation lambdas for a bounded run, then re-run the aggregation probe at full fidelity, mode-split, with a self-consistency pin — separating risk_lambda / must_react_lambda / response-weighting before any live change.

**Architecture:** Additive off-by-default telemetry records the exact `mode`/`risk_lambda`/`must_react_lambda` on the already-built `DecisionTrace`; a research-only sidecar writer (mirroring Spec-01 `eval/decision_capture.py`) persists the full per-response score matrix; a mode-aware probe replays `battle/policy.py::aggregate_scores` EXACTLY per game_mode and asserts it reproduces every exported aggregate. Live decision output is byte-identical when the export gate is unset.

**Tech stack:** Python 3.11+, existing repo, pytest. **Constraint:** Tasks 1–4 = local, NO battles (run only touched test files). Task 5 = a bounded Kaggle run (controller). Reuse Spec-01 `normalize_choose` + sidecar patterns and the audit's deterministic-report discipline.

---

## File structure

- Modify `showdown_bot/src/showdown_bot/battle/decision_trace.py` — 3 optional decision-level telemetry fields.
- Modify `showdown_bot/src/showdown_bot/battle/policy.py` — public accessor for the must-react lambda.
- Modify `showdown_bot/src/showdown_bot/battle/decision.py` — set the 3 fields where the trace is populated.
- Create `showdown_bot/src/showdown_bot/research/aggregation_trace.py` — agg-trace row schema, writer, loader.
- Modify `showdown_bot/src/showdown_bot/client/gauntlet.py`, `cli.py` — off-by-default `--agg-trace-out` wiring.
- Modify `showdown_bot/src/showdown_bot/research/aggregation_probe.py` — add the full-fidelity mode-aware probe + report.
- Tests: `test_decision_trace.py`, `test_aggregation_trace.py`, `test_gauntlet_dispatch.py`, `test_aggregation_probe.py`.

---

### Task 1: Record exact aggregation params as DecisionTrace telemetry (Sonnet)

**Files:** Modify `battle/decision_trace.py`, `battle/policy.py`, `battle/decision.py`; Test `tests/test_decision_trace.py`, `tests/test_actions_force_phase.py`.

- [ ] **Step 1 — failing test** in `test_decision_trace.py`:
```python
def test_aggregation_params_default_to_none():
    t = DecisionTrace()
    assert t.aggregation_mode is None
    assert t.risk_lambda is None
    assert t.must_react_lambda is None
```
And in `test_actions_force_phase.py`, pin that a real heuristic decision populates them (using the existing `decision_fixture`): after `heuristic_choose_for_request(..., trace=trace)`, `trace.aggregation_mode` is a non-empty str, `trace.risk_lambda` is a float, `trace.must_react_lambda` is a float.

- [ ] **Step 2 — run red:** `python -m pytest tests/test_decision_trace.py::test_aggregation_params_default_to_none -q` → FAIL (no such attribute).

- [ ] **Step 3 — DecisionTrace fields.** In `battle/decision_trace.py`, add to `DecisionTrace` (after `fallback_reason`), pure side-effect telemetry:
```python
    # Exact aggregation context used by policy.aggregate_scores at this decision
    # (research-only; never read to make a decision). Set by decision.py.
    aggregation_mode: str | None = None
    risk_lambda: float | None = None
    must_react_lambda: float | None = None
```

- [ ] **Step 4 — public accessor** in `battle/policy.py`. `_must_react_lambda()` is private; add right after it:
```python
def must_react_lambda() -> float:
    """Public read of the current MUST_REACT worst-case weight (env-configurable)."""
    return _must_react_lambda()
```

- [ ] **Step 5 — populate in decision.py.** In `battle/decision.py::_choose_best`, immediately AFTER `best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)` (~line 310), add (guarded, additive, no control-flow change):
```python
    if trace is not None:
        from showdown_bot.battle.policy import must_react_lambda as _mrl
        trace.aggregation_mode = mode.value if hasattr(mode, "value") else str(mode)
        trace.risk_lambda = float(risk_lambda)
        trace.must_react_lambda = float(_mrl())
```
Do NOT alter `best_ja`, `best_val`, or any returned string.

- [ ] **Step 6 — run green:** `python -m pytest tests/test_decision_trace.py tests/test_actions_force_phase.py tests/test_gauntlet_dispatch.py -q` → PASS; existing choice-string assertions unchanged.

- [ ] **Step 7 — commit:** `git commit -m "feat(2c): record exact aggregation mode + lambdas as decision telemetry"`

### Task 2: Full-fidelity agg-trace sidecar writer (Sonnet)

**Files:** Create `research/aggregation_trace.py`, `tests/test_aggregation_trace.py`.

Mirror `eval/decision_capture.py` (Spec-01) exactly for the writer/loader mechanics — same gzip-aware `_open_text`, per-battle key dedup, per-battle count+sha `finish_battle`, canonical `json.dumps(sort_keys=True, separators=(",",":"))`, missing-or-empty output guard, fail-closed `validate_agg_row`. Reuse `normalize_choose` from `eval.decision_capture` for `action_key`/`response_key`.

- [ ] **Step 1 — failing tests** (`test_aggregation_trace.py`): a `build_agg_row(context, trace, request, choose, decision_index)` from a `DecisionTrace` with 2 candidates × 3 responses produces a row whose `candidates[i].response_scores` has length == len(`response_keys`) == 3; whose per-candidate `exported_aggregate_score` equals the trace's `CandidateTrace.aggregate_score`; that carries `aggregation_mode`/`risk_lambda`/`must_react_lambda`; and a leakage test that the row JSON contains no `game_outcome`/`winner`/`teacher_trace`. Writer binds count+sha; refuses a duplicate `(battle_id, decision_index, our_side)`.

- [ ] **Step 2 — run red** → module missing.

- [ ] **Step 3 — implement.** Row schema (exact keys), `AggTraceContext` (battle_id, seed_index, our_side, config_id, config_hash, schedule_hash, format_id, git_sha), `build_agg_row`:
```python
AGG_TRACE_SCHEMA_VERSION = "agg-trace-v1"

def build_agg_row(*, context, trace, request, choose, decision_index):
    resp_keys = [normalize_choose_opp(r) for r in trace.opponent_responses]  # see note
    row = {
        "agg_trace_schema_version": AGG_TRACE_SCHEMA_VERSION,
        "battle_id": context.battle_id, "seed_index": context.seed_index,
        "decision_index": decision_index, "our_side": context.our_side,
        "config_hash": context.config_hash, "schedule_hash": context.schedule_hash,
        "format_id": context.format_id, "git_sha": context.git_sha,
        "game_mode": trace.game_mode,
        "aggregation_mode": trace.aggregation_mode,
        "risk_lambda": trace.risk_lambda,
        "must_react_lambda": trace.must_react_lambda,
        "selected_action_key": normalize_choose(choose, request)["action_key"]
                               if choose else None,
        "response_keys": resp_keys,
        "response_weights": list(trace.opponent_response_weights),
        "candidates": [
            {"action_key": c.candidate_id,
             "exported_aggregate_score": float(c.aggregate_score),
             "response_scores": [float(x) for x in c.score_vector]}
            for c in trace.candidates
        ],
    }
    validate_agg_row(row)
    return row
```
Note on `response_key`: opponent responses are `list[PlannedAction]`-shaped; add a small local `_response_key(actions) -> str` that canonicalizes them (sorted, deterministic) — do NOT reuse `/choose` parsing (these are internal action objects, not choose strings). `validate_agg_row` requires: parallel lengths (`response_scores` len == `response_keys` len for every candidate; `response_weights` len == `response_keys` len), finite scores/weights, sha256-hex provenance where applicable, unknown-field rejection. `teacher_best_action_keys` is written as `[]` here (joined from the datagen teacher in Task 5's run, or left empty — the probe tolerates empty by skipping teacher metrics for that decision).

- [ ] **Step 4 — run green** → PASS. **Step 5 — commit:** `git commit -m "feat(2c): full-fidelity aggregation trace writer"`

### Task 3: Wire the export into gauntlet/cli, off-by-default (Sonnet)

**Files:** Modify `client/gauntlet.py`, `cli.py`; Test `tests/test_gauntlet_dispatch.py`, `tests/test_cli_run_schedule_export.py`.

Mirror Spec-01 Task 4 (the `decision_trace_writer`/`decision_trace_context` wiring) EXACTLY, with a second independent optional writer `agg_trace_writer` + context, gated by `--agg-trace-out` (CLI) / `SHOWDOWN_AGG_TRACE_OUT`. The capture-OFF invariant is identical: writer unset ⇒ no `AggTraceWriter`, no file, byte-identical dispatch. The agg-trace needs `trace_obj` built, so extend the existing `capture_wants_trace`-style predicate to also fire when `agg_trace_writer is not None` (independent trigger; never widen the export/shadow condition).

- [ ] **Step 1 — failing golden** in `test_gauntlet_dispatch.py`: `test_agg_trace_off_is_byte_identical` — with `agg_trace_writer=None`, `AggTraceWriter` is never constructed (monkeypatch to raise) and `conn.sent` is unchanged. Plus a CLI-contract test: `--agg-trace-out` requires `--result-out`.
- [ ] **Step 2 — run red.** **Step 3 — implement** (mirror Spec-01 Task 4 code, second writer). **Step 4 — green:** `python -m pytest tests/test_gauntlet_dispatch.py tests/test_cli_run_schedule_export.py -q`. **Step 5 — commit:** `git commit -m "feat(2c): wire off-by-default aggregation trace export into schedule runs"`

### Task 4: Mode-aware full-fidelity probe (Sonnet)

**Files:** Modify `research/aggregation_probe.py`; Test `tests/test_aggregation_probe.py`.

- [ ] **Step 1 — failing tests.** `replay_aggregate(scores, mode, *, risk_lambda, must_react_lambda, weights)` must byte-match `battle/policy.py::aggregate_scores` for all three modes incl. the single-score and no-weights edges:
```python
import pytest
from showdown_bot.battle.policy import aggregate_scores
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.research.aggregation_probe import replay_aggregate

@pytest.mark.parametrize("mode", [GameMode.AHEAD, GameMode.NEUTRAL, GameMode.MUST_REACT])
@pytest.mark.parametrize("weights", [None, [0.5, 0.3, 0.2]])
def test_replay_matches_policy(mode, weights):
    scores = [1.0, -2.0, 3.0]
    got = replay_aggregate(scores, mode, risk_lambda=0.5, must_react_lambda=0.6, weights=weights)
    assert got == pytest.approx(aggregate_scores(scores, mode, risk_lambda=0.5, weights=weights))
```
(The MUST_REACT case must pass `must_react_lambda=0.6` to match the default `_must_react_lambda()`; the test monkeypatches `SHOWDOWN_MUST_REACT_LAMBDA=0.6` or asserts under the default.) Plus a self-consistency test on a built agg-row: replaying with the row's own mode/lambdas/weights reproduces every candidate `exported_aggregate_score` within `1e-9`.

- [ ] **Step 2 — run red.**

- [ ] **Step 3 — implement `replay_aggregate` EXACTLY mirroring policy.py** (do not paraphrase the formula):
```python
import math
def replay_aggregate(scores, mode, *, risk_lambda, must_react_lambda, weights=None):
    from showdown_bot.engine.belief.game_mode import GameMode
    if not scores:
        return 0.0
    use_weights = weights is not None and len(weights) == len(scores) and sum(weights) > 0
    if mode == GameMode.MUST_REACT:
        worst = min(scores)
        if use_weights:
            wsum = sum(weights); avg = sum(s*w for s, w in zip(scores, weights))/wsum
        else:
            avg = sum(scores)/len(scores)
        return avg - must_react_lambda * (avg - worst)
    if use_weights:
        wsum = sum(weights); wmean = sum(s*w for s, w in zip(scores, weights))/wsum
        if mode == GameMode.AHEAD:
            return wmean
        wvar = sum(w*(s-wmean)**2 for s, w in zip(scores, weights))/wsum
        return wmean - risk_lambda * wvar
    if mode == GameMode.AHEAD:
        return sum(scores)/len(scores)
    if len(scores) == 1:
        return scores[0]
    m = sum(scores)/len(scores)
    return m - risk_lambda * (sum((s-m)**2 for s in scores)/len(scores))
```
Then `run_full_fidelity_probe(agg_trace_rows)`: for each decision, self-consistency-check ALL candidates (fatal on mismatch), classify by `aggregation_mode`, apply mode-appropriate variants — NEUTRAL: risk_lambda ∈ {0,0.1,0.25,0.5,0.75,1.0} + unweighted + flatten/sharpen; MUST_REACT: must_react_lambda ∈ {0,0.3,0.6,1.0} + unweighted; AHEAD: weighted-vs-unweighted mean only — re-rank (candidate-index tie-break), compute the metrics from probe 0a PLUS `mode_sample_count`, `mode_changed_action_rate`, and split the report by mode + global. Teacher via `teacher_best_action_keys` (skip teacher metrics for rows with an empty set). Deterministic JSON+MD (reuse the 0a formatters' style).

- [ ] **Step 4 — green:** `python -m pytest tests/test_aggregation_probe.py -q`. **Step 5 — commit:** `git commit -m "feat(2c): mode-aware full-fidelity aggregation probe with policy self-consistency pin"`

### Task 5: Bounded Kaggle run + full-fidelity probe + verdict (Controller)

- [ ] Run a **small** datagen schedule (e.g. the existing rain panel or smaller) on Kaggle with `SHOWDOWN_AGG_TRACE_OUT` set (reuse the datagen kernel + EXTRA_ENV passthrough); join `teacher_best_action_keys` from the run's teacher labels; pull the agg-trace sidecar.
- [ ] Run `run_full_fidelity_probe` on it → deterministic report; verify the self-consistency pin passes on real data (fatal otherwise).
- [ ] Apply the spec's **pre-registered decision rules** (per mode) → verdict: which of {live risk_lambda A/B, live must_react_lambda A/B, resp_weights audit, park CVaR, go to bounded depth-1} is the actual first 2c lever.

### Task 6: Closeout (Controller)

- [ ] Full offline suite (green + known xfail; `npm ci --prefix tools/calc` if needed). `git diff --check`; placeholder scan on the new files.
- [ ] Report `reports/2026-07-11-2c-slice-0b-full-fidelity.md` (the mode-split numbers + the decision-rule verdict). Merge decision (off-by-default export + probe merge regardless of the verdict; the verdict drives the NEXT slice, not this merge).

## Self-review

- Spec coverage: export (Tasks 1–3), mode-aware probe + self-consistency (Task 4), bounded run + mode-split verdict (Task 5), decision rules (Task 5), closeout (Task 6). ✓
- Byte-identical-off: Tasks 1 (additive telemetry) + 3 (capture-off golden). ✓
- `replay_aggregate` is a verbatim mirror of `policy.py::aggregate_scores` (pinned by `test_replay_matches_policy` + the self-consistency pin). ✓
- No RNG anywhere; deterministic report. ✓
- Naming consistent: `aggregation_mode`/`risk_lambda`/`must_react_lambda`, `AggTraceWriter`, `replay_aggregate`, `run_full_fidelity_probe` across tasks. ✓

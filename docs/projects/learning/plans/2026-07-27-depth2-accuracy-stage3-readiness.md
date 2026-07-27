# Stage-3 Readiness: Accuracy-Configuration Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing off-by-default coarse Depth-2 path use the same resolved accuracy
configuration at both plies, in both non-Mega and Mega scoring paths, and make the executed
method observable via decision-profile-v4.

**Architecture:** Two `d2_eval_kwargs` dicts (one in `decision.py:686`, one in `mega_scoring.py:837`)
currently omit `accuracy_mode` and `accuracy_branch_cap`. Adding those two keys to each dict threads
the once-resolved accuracy configuration through the existing `eval_kwargs -> **eval_kwargs` seam in
`search.py:_score_turn2_plans`. A new optional in-memory `Depth2ReadinessCounts` dataclass accumulates
per-ply accuracy leaf/cap counters at origin. A v4 profile schema persists them alongside the existing
shape/transport/outcome fields.

**Tech Stack:** Python 3.12, pytest, monkeypatch spies, JSONL profile sidecar

**Spec:** `docs/projects/learning/specs/2026-07-27-depth2-accuracy-stage3-readiness-design.md`

**Delivery sequence follows spec §12 exactly.**

---

## File Map

| File | Role |
|---|---|
| `showdown_bot/src/showdown_bot/battle/decision.py` | Modify: add 2 keys to `d2_eval_kwargs` (line 686) |
| `showdown_bot/src/showdown_bot/battle/mega_scoring.py` | Modify: add 2 keys to `d2_eval_kwargs` (line 837) |
| `showdown_bot/src/showdown_bot/eval/decision_profile.py` | Modify: add v4 schema, fields, field set, validator rules |
| `showdown_bot/src/showdown_bot/eval/depth2_readiness.py` | Create: `Depth2ReadinessCounts` dataclass (the optional in-memory sink) |
| `showdown_bot/src/showdown_bot/client/gauntlet.py` | Modify: allocate sink, pass through, join into profile row |
| `showdown_bot/tests/test_depth2_accuracy_wiring.py` | Create: forwarding, consumption, resolution, non-expansion tests |
| `showdown_bot/tests/test_depth2_readiness_telemetry.py` | Create: sink increment, trace-isolation, profile-off tests |
| `showdown_bot/tests/test_decision_profile_v4.py` | Create: v4 field set, cross-field invariant, backward-compat tests |

No new file touches `search.py`, `evaluate.py`, or the chooser/frontier/state-transition code. The
compatibility change is entirely in two 2-key dict additions and the telemetry infrastructure.

---

## Task 1: Reproduce the inconsistency (red test)

**Files:**
- Create: `showdown_bot/tests/test_depth2_accuracy_wiring.py`

This task proves the gap exists before fixing it: with `SHOWDOWN_ACCURACY_MODE=1` and
`SHOWDOWN_SEARCH_DEPTH=2`, the Turn-2 `evaluate_line` calls currently receive `accuracy_mode=False`
(the function default) instead of `True`.

- [ ] **Step 1: Write the failing inconsistency-reproducing test**

```python
"""Accuracy × Depth-2 consistency tests (spec §10.1, §10.2).

Proves the once-resolved accuracy configuration reaches every Turn-2 evaluation
call through both the non-Mega and Mega Depth-2 paths.
"""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle import evaluate as evaluate_module
from showdown_bot.battle import search as search_module
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.engine.state import BattleState, PokemonState

FIXTURES = Path(__file__).parent / "fixtures"


def _install_eval_recorder(monkeypatch):
    """Wrap ``_evaluate_line_details`` to record accuracy kwargs on every call.
    Same pattern as test_accuracy_mode_wiring.py."""
    calls: list[dict] = []
    real = evaluate_module._evaluate_line_details

    def _wrapped(*args, **kwargs):
        calls.append({
            "accuracy_mode": kwargs.get("accuracy_mode", False),
            "accuracy_branch_cap": kwargs.get("accuracy_branch_cap", 4),
        })
        return real(*args, **kwargs)

    monkeypatch.setattr(evaluate_module, "_evaluate_line_details", _wrapped)
    return calls


# --- Fixtures (reuse test_search_depth2.py's board) ---

def _d2_req():
    from showdown_bot.models.request import BattleRequest
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    return BattleRequest.model_validate(data)


def _d2_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


class _FakeCalc:
    backend = None
    def damage_batch(self, requests):
        from showdown_bot.engine.calc.models import DamageResult
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracleD2:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)
    def get(self, key):
        from showdown_bot.engine.calc.models import DamageResult
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)
    def damage(self, req):
        from showdown_bot.engine.calc.models import DamageResult
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)
    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100
    def opponent_range(self, mon, field, side, *, book):
        from showdown_bot.engine.speed import SpeedRange
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def _d2_book():
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.format_config import load_format_config
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _d2_kwargs():
    return dict(
        state=_d2_state(), book=_d2_book(), our_side="p1",
        calc=_FakeCalc(), oracle=_FakeOracleD2(),
        speed_oracle=_FakeSpeed(), dex=_FakeDex(),
    )


# ---- §10.1 Test 1: accuracy resolvers called exactly once per decision ----

def test_accuracy_resolvers_called_once_per_decision(monkeypatch):
    """Patch _accuracy_mode and _accuracy_branch_cap with call-count spies;
    one scored decision calls each exactly once (spec §10.1 test 1)."""
    from showdown_bot.battle import decision as decision_module

    mode_calls = []
    cap_calls = []
    real_mode = decision_module._accuracy_mode
    real_cap = decision_module._accuracy_branch_cap

    def _spy_mode():
        result = real_mode()
        mode_calls.append(result)
        return result

    def _spy_cap():
        result = real_cap()
        cap_calls.append(result)
        return result

    monkeypatch.setattr(decision_module, "_accuracy_mode", _spy_mode)
    monkeypatch.setattr(decision_module, "_accuracy_branch_cap", _spy_cap)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(mode_calls) == 1, f"_accuracy_mode called {len(mode_calls)} times"
    assert len(cap_calls) == 1, f"_accuracy_branch_cap called {len(cap_calls)} times"


# ---- §10.1 Test 2: non-Mega Depth-2 forwarding ----

def test_depth2_accuracy_forwarded_nonmega(monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=1 and SHOWDOWN_SEARCH_DEPTH=2, every
    evaluate_line call (including Turn-2 via depth2_value) receives
    accuracy_mode=True and accuracy_branch_cap=6.

    THIS TEST SHOULD FAIL before the fix: Turn-2 calls currently receive
    accuracy_mode=False (the evaluate_line default)."""
    calls = _install_eval_recorder(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(calls) >= 5, (
        f"expected Turn-1 calls + Turn-2 calls, got {len(calls)}"
    )
    assert all(c["accuracy_mode"] is True for c in calls), (
        f"not all calls got accuracy_mode=True: {calls}"
    )
    assert all(c["accuracy_branch_cap"] == 6 for c in calls), (
        f"not all calls got accuracy_branch_cap=6: {calls}"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py::test_depth2_accuracy_forwarded_nonmega -v`
Expected: FAIL — some calls have `accuracy_mode=False` (the Turn-2 calls via `search.py`).

The resolver spy test should PASS (it's testing existing behavior that already works).

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py::test_accuracy_resolvers_called_once_per_decision -v`
Expected: PASS

- [ ] **Step 3: Commit the red tests**

```bash
git add showdown_bot/tests/test_depth2_accuracy_wiring.py
git commit -m "test(red): reproduce accuracy × depth-2 inconsistency

The forwarding test proves that with SHOWDOWN_ACCURACY_MODE=1 and
SHOWDOWN_SEARCH_DEPTH=2, Turn-2 evaluate_line calls receive the
function default (accuracy_mode=False) instead of the resolved value.
Spec §10.1 tests 1-2."
```

---

## Task 2: Fix the non-Mega Depth-2 path (green)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/decision.py:678-689`

- [ ] **Step 1: Add accuracy keys to `d2_eval_kwargs` in `decision.py`**

In `decision.py`, replace lines 678-689:

```python
            # [accuracy-slice] Deliberately does NOT include accuracy_mode/accuracy_branch_cap.
            # depth2_value's turn-2 refinement (search.py) is out of scope for the accuracy slice
            # (spec Sec.12, Depth-2 Stage 3 is separate, later work) -- if SHOWDOWN_ACCURACY_MODE
            # and SHOWDOWN_SEARCH_DEPTH=2 are ever both on, the top-N/top-M candidates' scores get
            # overwritten by depth2_value with legacy always-hit values, mixing methodologies
            # inside one decision's comparison set. Not exercised by the accuracy-slice latency
            # bench (scratchpad/bench_accuracy_latency.py) or tests -- known, accepted gap until
            # Depth-2 Stage 3 threads these two kwargs through search.py.
            d2_eval_kwargs = {
                "weights": weights, "rollout_horizon": rollout_horizon,
                "endgame": endgame, "fast_board": fast_board,
            }
```

with:

```python
            d2_eval_kwargs = {
                "weights": weights, "rollout_horizon": rollout_horizon,
                "endgame": endgame, "fast_board": fast_board,
                "accuracy_mode": accuracy_mode,
                "accuracy_branch_cap": accuracy_branch_cap,
            }
```

- [ ] **Step 2: Run the forwarding test to verify it passes**

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py::test_depth2_accuracy_forwarded_nonmega -v`
Expected: PASS — all calls now carry the resolved accuracy values.

- [ ] **Step 3: Run existing Depth-2 and accuracy tests to check for regressions**

Run: `pytest showdown_bot/tests/test_search_depth2.py showdown_bot/tests/test_accuracy_mode_wiring.py -v`
Expected: all 10 pass.

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/decision.py
git commit -m "fix: forward accuracy config through non-Mega depth-2 path

Add accuracy_mode and accuracy_branch_cap to d2_eval_kwargs in
_choose_best. The values flow through depth2_value -> _score_turn2_plans
-> evaluate_line via the existing **eval_kwargs seam in search.py.
Closes the documented accuracy-slice gap (spec §6.2)."
```

---

## Task 3: Fix the Mega Depth-2 path (green)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/mega_scoring.py:833-840`

- [ ] **Step 1: Add accuracy keys to `d2_eval_kwargs` in `mega_scoring.py`**

In `mega_scoring.py`, replace lines 833-840:

```python
        # [accuracy-slice parity] Deliberately excludes accuracy_mode/
        # accuracy_branch_cap -- same known, accepted gap as decision.py's
        # non-Mega depth-2 wrap (see its own comment there): depth-2
        # refinement is out of scope for the accuracy slice.
        d2_eval_kwargs = {
            "weights": weights, "rollout_horizon": rollout_horizon,
            "endgame": endgame, "fast_board": fast_board,
        }
```

with:

```python
        d2_eval_kwargs = {
            "weights": weights, "rollout_horizon": rollout_horizon,
            "endgame": endgame, "fast_board": fast_board,
            "accuracy_mode": accuracy_mode,
            "accuracy_branch_cap": accuracy_branch_cap,
        }
```

Note: `accuracy_mode` and `accuracy_branch_cap` are already parameters of `score_evaluated_variants`
(lines 399-400), received from `_choose_best_mega`. They are already forwarded to all Turn-1
`_evaluate_line_details` calls (lines 718-719, 763-764). This change only adds them to the Depth-2
`eval_kwargs` dict that was previously missing them.

- [ ] **Step 2: Write the Mega forwarding test**

Append to `showdown_bot/tests/test_depth2_accuracy_wiring.py`:

```python
# ---- §10.1 Test 3: Mega Depth-2 forwarding ----

def test_depth2_accuracy_forwarded_mega(monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=1, SHOWDOWN_SEARCH_DEPTH=2, and a Mega-capable
    board, depth2_value_for_mega_context receives the resolved accuracy values
    in eval_kwargs (spec §10.1 test 3).

    Uses the mega_decision_fixture from conftest.py if available; otherwise
    verifies the seam at the score_evaluated_variants level by spying on
    depth2_value_for_mega_context's eval_kwargs."""
    d2_calls: list[dict] = []
    real_d2 = search_module.depth2_value_for_mega_context

    def _spy(*args, **kwargs):
        ek = kwargs.get("eval_kwargs") or {}
        d2_calls.append({
            "accuracy_mode": ek.get("accuracy_mode", "MISSING"),
            "accuracy_branch_cap": ek.get("accuracy_branch_cap", "MISSING"),
        })
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(search_module, "depth2_value_for_mega_context", _spy)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)

    try:
        from showdown_bot.tests.conftest import mega_decision_fixture_data
        req, kw = mega_decision_fixture_data()
        _choose_best(req, **kw)
    except (ImportError, AttributeError):
        pytest.skip("mega_decision_fixture not available")

    if not d2_calls:
        pytest.skip("no depth-2 calls in mega path (board may not trigger depth-2)")

    for c in d2_calls:
        assert c["accuracy_mode"] is True, f"d2 mega call missing accuracy_mode: {c}"
        assert c["accuracy_branch_cap"] == 6, f"d2 mega call wrong cap: {c}"
```

Add `import pytest` and `from showdown_bot.battle import search as search_module` to the imports
at the top of the file if not already present.

- [ ] **Step 3: Run the test**

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py::test_depth2_accuracy_forwarded_mega -v`
Expected: PASS (or skip if no mega fixture available — the fix is verified structurally).

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/mega_scoring.py showdown_bot/tests/test_depth2_accuracy_wiring.py
git commit -m "fix: forward accuracy config through Mega depth-2 path

Same 2-key fix as the non-Mega path, applied to score_evaluated_variants'
d2_eval_kwargs. accuracy_mode and accuracy_branch_cap already arrive as
parameters; this closes the parity gap (spec §6.3)."
```

---

## Task 4: Equality and behavioral counterproof tests

**Files:**
- Modify: `showdown_bot/tests/test_depth2_accuracy_wiring.py`

These tests prove the fix is consumed (not just forwarded), that Depth-1 behavior is unchanged,
and that the representative-leaf pin holds.

- [ ] **Step 1: Write the Depth-1 equality control test (spec §8.1)**

Append to `test_depth2_accuracy_wiring.py`:

```python
# ---- §8.1: Depth-1 deterministic projection is unchanged ----

def test_depth1_projection_unchanged(monkeypatch):
    """With SHOWDOWN_SEARCH_DEPTH unset (=1), the deterministic decision projection
    matches the pre-slice golden exactly (spec §8.1)."""
    for var in ("SHOWDOWN_SEARCH_DEPTH", "SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM",
                "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)

    from showdown_bot.battle.decision import heuristic_choose_for_request

    req = _d2_req()
    tr = DecisionTrace()
    choice = heuristic_choose_for_request(req, trace=tr, **_d2_kwargs())

    assert choice == "/choose move 3, move 3|2"
    assert tr.chosen_candidate_id == "(Protect, Protect)"
    assert tr.game_mode == "NEUTRAL"
    assert len(tr.candidates) == 6
    assert tr.candidates[0].score_vector == [5.4, 5.4, 3.6, 1.8, 3.6]
    assert tr.candidates[0].aggregate_score == 3.0528
```

- [ ] **Step 2: Write the Accuracy-off Depth-2 equality control test (spec §8.2)**

Append to `test_depth2_accuracy_wiring.py`:

```python
# ---- §8.2: Accuracy-off Depth-2 projection is unchanged ----

def test_accuracy_off_depth2_unchanged(monkeypatch):
    """With SHOWDOWN_ACCURACY_MODE=0 and SHOWDOWN_SEARCH_DEPTH=2, passing
    explicit False/cap through eval_kwargs must not change evaluate_line's
    legacy accuracy-off behavior (spec §8.2).

    Captures the decision with ACCURACY_MODE=0 pre-fix (should match post-fix
    because explicit False == the default False). Verifies frontier, score
    vectors, and chosen action match."""
    from showdown_bot.battle import decision as decision_module
    from showdown_bot.battle.actions import JointAction

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "0")
    for var in ("SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM", "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)

    d2_calls = []
    real_d2 = decision_module.depth2_value

    def _spy(*args, **kwargs):
        ek = kwargs.get("eval_kwargs") or {}
        d2_calls.append({
            "accuracy_mode": ek.get("accuracy_mode"),
            "accuracy_branch_cap": ek.get("accuracy_branch_cap"),
        })
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(decision_module, "depth2_value", _spy)

    choice_ja, _ = _choose_best(_d2_req(), **_d2_kwargs())

    assert len(d2_calls) == 4, f"expected 4 depth2_value calls, got {len(d2_calls)}"
    for c in d2_calls:
        assert c["accuracy_mode"] is False
        assert c["accuracy_branch_cap"] is not None
```

- [ ] **Step 3: Write the consumption counterproof test (spec §10.2 test 1)**

Append to `test_depth2_accuracy_wiring.py`:

```python
# ---- §10.2 Test 1: consumption counterproof ----

def test_accuracy_on_changes_turn2_value(monkeypatch):
    """A controlled scenario where a low-accuracy move produces a different
    refined value between Accuracy-off and Accuracy-on, proving the parameter
    is consumed rather than merely forwarded (spec §10.2 test 1).

    We compare the depth2_value spy output under MODE=0 vs MODE=1. If accuracy
    is truly consumed, at least one Turn-2 value must differ."""
    from showdown_bot.battle import decision as decision_module

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.delenv("SHOWDOWN_SEARCH_TOPN", raising=False)
    monkeypatch.delenv("SHOWDOWN_SEARCH_TOPM", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    def _run_with_mode(mode_val):
        values = []
        real_d2 = decision_module.depth2_value

        def _capture(*args, **kwargs):
            v = real_d2(*args, **kwargs)
            values.append(v)
            return v

        monkeypatch.setattr(decision_module, "depth2_value", _capture)
        monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", mode_val)
        _choose_best(_d2_req(), **_d2_kwargs())
        return values

    off_values = _run_with_mode("0")
    on_values = _run_with_mode("1")

    assert len(off_values) == len(on_values) == 4
    assert off_values != on_values, (
        "accuracy_mode=True produced the same Turn-2 values as accuracy_mode=False — "
        "the parameter is forwarded but not consumed"
    )
```

- [ ] **Step 4: Write the representative-leaf non-expansion test (spec §6.4 / §10.2 test 4)**

Append to `test_depth2_accuracy_wiring.py`:

```python
# ---- §6.4 / §10.2 Test 4: one Turn-2 successor per selected slot ----

def test_one_successor_per_selected_slot(monkeypatch):
    """Multiple Turn-1 accuracy leaves still produce exactly one Depth-2 successor
    per selected (candidate, response slot). The Depth-2 call count must remain
    bounded by the frontier (N * M), never multiplied by the number of Turn-1
    accuracy leaves (spec §6.4)."""
    from showdown_bot.battle import decision as decision_module

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    d2_calls = []
    real_d2 = decision_module.depth2_value

    def _spy(*args, **kwargs):
        d2_calls.append(1)
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(decision_module, "depth2_value", _spy)

    _choose_best(_d2_req(), **_d2_kwargs())

    top_n = 2  # default SHOWDOWN_SEARCH_TOPN
    top_m = 2  # default SHOWDOWN_SEARCH_TOPM
    assert len(d2_calls) == top_n * top_m, (
        f"expected {top_n * top_m} depth2_value calls but got {len(d2_calls)} — "
        "Turn-1 accuracy leaves may have expanded into Turn-2"
    )
```

- [ ] **Step 5: Write the K-world suppression parity test (spec §10.2 test 5)**

Append to `test_depth2_accuracy_wiring.py`:

```python
# ---- §10.2 Test 5: K-world active suppresses Depth-2 ----

def test_kworld_suppresses_depth2_with_accuracy(monkeypatch):
    """With SHOWDOWN_WORLD_SAMPLES=2, depth2_value must NOT fire even when
    SHOWDOWN_SEARCH_DEPTH=2 and SHOWDOWN_ACCURACY_MODE=1 (spec §10.2 test 5)."""
    from showdown_bot.battle import decision as decision_module

    d2_calls = []
    real_d2 = decision_module.depth2_value

    def _spy(*args, **kwargs):
        d2_calls.append(1)
        return real_d2(*args, **kwargs)

    monkeypatch.setattr(decision_module, "depth2_value", _spy)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")

    _choose_best(_d2_req(), **_d2_kwargs())

    assert len(d2_calls) == 0, "depth2_value fired with K-world sampling active"
```

- [ ] **Step 6: Write the no-new-env-reads test (spec §10.1 test 4)**

Append to `test_depth2_accuracy_wiring.py`:

```python
# ---- §10.1 Test 4: no new accuracy env reads downstream ----

def test_no_accuracy_env_reads_in_search(monkeypatch):
    """Neither search.py::depth2_value nor search.py::_score_turn2_plans
    reads SHOWDOWN_ACCURACY_MODE or SHOWDOWN_ACCURACY_BRANCH_CAP from the
    environment (spec §10.1 test 4). They receive values only via eval_kwargs."""
    import os
    from showdown_bot.battle import search

    original_getenv = os.environ.get
    forbidden = {"SHOWDOWN_ACCURACY_MODE", "SHOWDOWN_ACCURACY_BRANCH_CAP"}
    violations = []

    def _guarded_get(key, *args):
        if key in forbidden:
            import traceback
            tb = traceback.format_stack()
            if any("search.py" in frame for frame in tb):
                violations.append(key)
        return original_getenv(key, *args)

    monkeypatch.setattr(os.environ, "get", _guarded_get)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")

    _choose_best(_d2_req(), **_d2_kwargs())

    assert violations == [], f"search.py read forbidden env vars: {violations}"
```

- [ ] **Step 7: Run all new tests**

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add showdown_bot/tests/test_depth2_accuracy_wiring.py
git commit -m "test: equality, consumption, and non-expansion counterproofs

Spec §8.1 Depth-1 projection unchanged, §8.2 accuracy-off Depth-2
unchanged, §10.2 consumption counterproof (accuracy changes Turn-2
values), §6.4 one-successor-per-slot pin, §10.2 K-world suppression
parity, §10.1 no downstream env reads."
```

---

## Task 5: Create the `Depth2ReadinessCounts` in-memory sink

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/depth2_readiness.py`
- Create: `showdown_bot/tests/test_depth2_readiness_telemetry.py`

The spec (§6.5) requires a dedicated optional in-memory sink for at-origin work counters. It is
allocated only when the decision-profile writer is enabled. It records what actually happened at
the scoring call sites.

- [ ] **Step 1: Write the failing sink tests**

Create `showdown_bot/tests/test_depth2_readiness_telemetry.py`:

```python
"""Depth2ReadinessCounts sink tests (spec §6.5, §10.3)."""
from __future__ import annotations

from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts


def test_initial_state():
    """All counters start at zero."""
    c = Depth2ReadinessCounts()
    assert c.search_depth == 1
    assert c.search_topn_requested == 0
    assert c.search_topm_requested == 0
    assert c.depth2_candidates_selected == 0
    assert c.depth2_response_slots_eligible == 0
    assert c.accuracy_mode is False
    assert c.accuracy_branch_cap == 0
    assert c.turn1_accuracy_leaf_count == 0
    assert c.turn1_accuracy_cap_hits == 0
    assert c.turn2_accuracy_leaf_count == 0
    assert c.turn2_accuracy_cap_hits == 0


def test_increment_turn1():
    """Turn-1 leaf/cap counters increment additively."""
    c = Depth2ReadinessCounts()
    c.add_turn1_accuracy(leaf_count=3, cap_hits=1)
    c.add_turn1_accuracy(leaf_count=2, cap_hits=0)
    assert c.turn1_accuracy_leaf_count == 5
    assert c.turn1_accuracy_cap_hits == 1


def test_increment_turn2():
    """Turn-2 leaf/cap counters increment additively."""
    c = Depth2ReadinessCounts()
    c.add_turn2_accuracy(leaf_count=4, cap_hits=2)
    c.add_turn2_accuracy(leaf_count=1, cap_hits=0)
    assert c.turn2_accuracy_leaf_count == 5
    assert c.turn2_accuracy_cap_hits == 2


def test_cap_fallback_derived():
    """Cap-fallback booleans are derived, not stored."""
    c = Depth2ReadinessCounts()
    assert c.turn1_accuracy_cap_fallback is False
    assert c.turn2_accuracy_cap_fallback is False
    c.add_turn1_accuracy(leaf_count=6, cap_hits=1)
    assert c.turn1_accuracy_cap_fallback is True
    assert c.turn2_accuracy_cap_fallback is False
    c.add_turn2_accuracy(leaf_count=6, cap_hits=3)
    assert c.turn2_accuracy_cap_fallback is True


def test_to_dict():
    """to_dict produces the exact field set expected by profile v4."""
    c = Depth2ReadinessCounts()
    c.search_depth = 2
    c.search_topn_requested = 3
    c.search_topm_requested = 3
    c.depth2_candidates_selected = 2
    c.depth2_response_slots_eligible = 5
    c.accuracy_mode = True
    c.accuracy_branch_cap = 6
    c.add_turn1_accuracy(leaf_count=10, cap_hits=2)
    c.add_turn2_accuracy(leaf_count=8, cap_hits=0)

    d = c.to_dict()
    assert d == {
        "search_depth": 2,
        "search_topn_requested": 3,
        "search_topm_requested": 3,
        "depth2_candidates_selected": 2,
        "depth2_response_slots_eligible": 5,
        "accuracy_mode": True,
        "accuracy_branch_cap": 6,
        "turn1_accuracy_leaf_count": 10,
        "turn1_accuracy_cap_hits": 2,
        "turn1_accuracy_cap_fallback": True,
        "turn2_accuracy_leaf_count": 8,
        "turn2_accuracy_cap_hits": 0,
        "turn2_accuracy_cap_fallback": False,
    }
```

- [ ] **Step 2: Run the tests to verify they fail (module not found)**

Run: `pytest showdown_bot/tests/test_depth2_readiness_telemetry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'showdown_bot.eval.depth2_readiness'`

- [ ] **Step 3: Implement `Depth2ReadinessCounts`**

Create `showdown_bot/src/showdown_bot/eval/depth2_readiness.py`:

```python
"""Optional in-memory sink for Depth-2 readiness telemetry (spec §6.5).

Allocated only when the decision-profile writer is enabled. Records work
where it actually happens: at the real scoring call sites. The sink performs
no file I/O and no environment reads.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Depth2ReadinessCounts:
    search_depth: int = 1
    search_topn_requested: int = 0
    search_topm_requested: int = 0
    depth2_candidates_selected: int = 0
    depth2_response_slots_eligible: int = 0
    accuracy_mode: bool = False
    accuracy_branch_cap: int = 0
    turn1_accuracy_leaf_count: int = 0
    turn1_accuracy_cap_hits: int = 0
    turn2_accuracy_leaf_count: int = 0
    turn2_accuracy_cap_hits: int = 0

    @property
    def turn1_accuracy_cap_fallback(self) -> bool:
        return self.turn1_accuracy_cap_hits > 0

    @property
    def turn2_accuracy_cap_fallback(self) -> bool:
        return self.turn2_accuracy_cap_hits > 0

    def add_turn1_accuracy(self, *, leaf_count: int, cap_hits: int) -> None:
        self.turn1_accuracy_leaf_count += leaf_count
        self.turn1_accuracy_cap_hits += cap_hits

    def add_turn2_accuracy(self, *, leaf_count: int, cap_hits: int) -> None:
        self.turn2_accuracy_leaf_count += leaf_count
        self.turn2_accuracy_cap_hits += cap_hits

    def to_dict(self) -> dict:
        return {
            "search_depth": self.search_depth,
            "search_topn_requested": self.search_topn_requested,
            "search_topm_requested": self.search_topm_requested,
            "depth2_candidates_selected": self.depth2_candidates_selected,
            "depth2_response_slots_eligible": self.depth2_response_slots_eligible,
            "accuracy_mode": self.accuracy_mode,
            "accuracy_branch_cap": self.accuracy_branch_cap,
            "turn1_accuracy_leaf_count": self.turn1_accuracy_leaf_count,
            "turn1_accuracy_cap_hits": self.turn1_accuracy_cap_hits,
            "turn1_accuracy_cap_fallback": self.turn1_accuracy_cap_fallback,
            "turn2_accuracy_leaf_count": self.turn2_accuracy_leaf_count,
            "turn2_accuracy_cap_hits": self.turn2_accuracy_cap_hits,
            "turn2_accuracy_cap_fallback": self.turn2_accuracy_cap_fallback,
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest showdown_bot/tests/test_depth2_readiness_telemetry.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/depth2_readiness.py showdown_bot/tests/test_depth2_readiness_telemetry.py
git commit -m "feat: add Depth2ReadinessCounts in-memory telemetry sink

Dataclass with additive per-ply accuracy counters and derived
cap-fallback properties. Allocated only when profiling is on.
Spec §6.5."
```

---

## Task 6: Wire the sink into decision scoring paths

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/decision.py`
- Modify: `showdown_bot/src/showdown_bot/battle/mega_scoring.py`
- Modify: `showdown_bot/tests/test_depth2_accuracy_wiring.py`

The sink must be populated at the real scoring call sites. `_choose_best` allocates and populates
it; the Mega path receives it through `score_evaluated_variants`. Turn-1 accuracy counts come
from the `TieOrderEvaluation` objects returned by `_evaluate_line_details`; Turn-2 counts come
from the same objects returned inside `_score_turn2_plans`.

**Implementation note:** The sink is passed via a new optional `readiness_sink` kwarg on
`_choose_best` (and `_choose_best_mega`/`score_evaluated_variants`). It is `None` when profiling
is off. The actual counter increments happen at the existing scoring call sites inside `_choose_best`
and `score_evaluated_variants`, NOT inside `search.py` or `evaluate.py`.

This task is more complex than the others because the wiring touches multiple call sites. The
implementer should:

1. Add `readiness_sink: Depth2ReadinessCounts | None = None` as a parameter to `_choose_best`,
   `_choose_best_mega`, and `score_evaluated_variants`.
2. In `_choose_best`, after resolving accuracy and search settings, populate
   `readiness_sink.search_depth`, `.search_topn_requested`, `.search_topm_requested`,
   `.accuracy_mode`, `.accuracy_branch_cap` from the already-resolved locals.
3. After each Turn-1 `evaluate_line` / `_evaluate_line_details` call that is a real scoring call
   (not a trace recomputation), extract the `LineEvaluation`'s `tie_order_details` and add
   `sum(t.accuracy_leaf_count for t in details)` and `sum(t.accuracy_branch_cap_hits for t in details)`
   to the sink via `add_turn1_accuracy`.
4. For Turn-2: `search.py::_score_turn2_plans` calls `evaluate_line` which returns
   `(score, outcome)` — it discards the `LineEvaluation` object. To get Turn-2 leaf counts
   without modifying `search.py`, the implementer should extract them by wrapping the
   `evaluate_line` call in `_score_turn2_plans` — OR more simply, by counting Turn-2 accuracy
   work at the `_choose_best` level by wrapping `depth2_value` with a recording layer when
   `readiness_sink is not None`. **The spec allows either approach**, but the simpler one is to
   have `_choose_best`/`score_evaluated_variants` record Turn-2 counts by wrapping
   `_evaluate_line_details` with a temporary recorder scoped to the depth-2 block.

   **Recommended approach:** In `_choose_best` and `score_evaluated_variants`, when
   `readiness_sink is not None` and depth-2 is active, wrap `evaluate_module._evaluate_line_details`
   with a temporary recorder (exactly like the test recorder) for the duration of the depth-2
   block, then restore it. The wrapper extracts `accuracy_leaf_count` and `cap_hits` from the
   returned `LineEvaluation.tie_order_details`. This approach avoids modifying `search.py`.

   **Alternative approach:** Pass the sink into `depth2_value` -> `_score_turn2_plans` and have
   it extract leaf counts there. This would require adding an optional `readiness_sink` param to
   `search.py` functions. Either approach is acceptable as long as the sink only increments on
   real scoring calls and trace recomputation does not touch it.

5. After the depth-2 loop, set `readiness_sink.depth2_candidates_selected` and
   `.depth2_response_slots_eligible` from the actual frontier selection.

The implementer must read the actual code to determine the exact insertion points and choose the
approach that requires the fewest changes while staying within the spec's §13 file constraint.

- [ ] **Step 1: Write the failing telemetry wiring tests**

Append to `showdown_bot/tests/test_depth2_accuracy_wiring.py`:

```python
# ---- §10.3: Telemetry wiring ----

def test_readiness_sink_populated_depth2(monkeypatch):
    """With profiling conceptually on and SHOWDOWN_SEARCH_DEPTH=2, the
    readiness sink is populated with correct search/accuracy settings
    and non-zero Turn-1 accuracy counts (spec §10.3 tests 1-3)."""
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    sink = Depth2ReadinessCounts()
    _choose_best(_d2_req(), readiness_sink=sink, **_d2_kwargs())

    assert sink.search_depth == 2
    assert sink.search_topn_requested == 2
    assert sink.search_topm_requested == 2
    assert sink.accuracy_mode is True
    assert sink.accuracy_branch_cap == 6
    assert sink.turn1_accuracy_leaf_count > 0
    assert sink.depth2_candidates_selected > 0
    assert sink.depth2_response_slots_eligible > 0


def test_readiness_sink_none_does_not_crash(monkeypatch):
    """With readiness_sink=None (profiling off), the decision runs
    identically with no allocation or crash (spec §10.3 test 4)."""
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")

    choice, _ = _choose_best(_d2_req(), readiness_sink=None, **_d2_kwargs())
    assert choice is not None


def test_readiness_sink_depth1_zeros(monkeypatch):
    """With SHOWDOWN_SEARCH_DEPTH=1, Turn-2 and depth2 counters are all zero."""
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.delenv("SHOWDOWN_SEARCH_DEPTH", raising=False)
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")

    sink = Depth2ReadinessCounts()
    _choose_best(_d2_req(), readiness_sink=sink, **_d2_kwargs())

    assert sink.search_depth == 1
    assert sink.depth2_candidates_selected == 0
    assert sink.depth2_response_slots_eligible == 0
    assert sink.turn2_accuracy_leaf_count == 0
    assert sink.turn2_accuracy_cap_hits == 0
    assert sink.turn1_accuracy_leaf_count > 0  # Turn-1 still counted


def test_trace_recomputation_does_not_alter_counts(monkeypatch):
    """Passing trace= and report= to _choose_best triggers _breakdowns_for
    recomputation inside the trace path. That recomputation must NOT increment
    the readiness sink's counters (spec §10.3 test 2).

    Runs two decisions with the same board: one with trace/report (which triggers
    recomputation), one without. The sink counts must be identical."""
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    sink_no_trace = Depth2ReadinessCounts()
    _choose_best(_d2_req(), readiness_sink=sink_no_trace, **_d2_kwargs())

    sink_with_trace = Depth2ReadinessCounts()
    _choose_best(
        _d2_req(), readiness_sink=sink_with_trace,
        report=[], trace=DecisionTrace(), **_d2_kwargs(),
    )

    assert sink_no_trace.turn1_accuracy_leaf_count == sink_with_trace.turn1_accuracy_leaf_count
    assert sink_no_trace.turn1_accuracy_cap_hits == sink_with_trace.turn1_accuracy_cap_hits
    assert sink_no_trace.turn2_accuracy_leaf_count == sink_with_trace.turn2_accuracy_leaf_count
    assert sink_no_trace.turn2_accuracy_cap_hits == sink_with_trace.turn2_accuracy_cap_hits
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py::test_readiness_sink_populated_depth2 -v`
Expected: FAIL — `_choose_best` does not accept `readiness_sink` yet.

- [ ] **Step 3: Wire the sink into `_choose_best`**

Modify `decision.py`:
- Add `readiness_sink=None` parameter to `_choose_best` signature (after `shape_sink`).
- After the accuracy/search resolution block (line ~410), if `readiness_sink is not None`,
  populate its config fields.
- After each Turn-1 `evaluate_line` scoring call (NOT trace calls), extract accuracy leaf counts
  from the `LineEvaluation` returned by `_evaluate_line_details` and call `sink.add_turn1_accuracy`.
- In the depth-2 block, after the frontier selection, set `depth2_candidates_selected` and
  `depth2_response_slots_eligible`.
- For Turn-2 accuracy counts, implement the chosen approach (wrapper or pass-through).

The implementer must read the current code to find the exact Turn-1 scoring call sites. The
primary ones are:
- `score_plan` inner function (around line 620-634)
- The `score_plan_with_outcome` variant inside the depth-2 guard (around line 639-649)

For each, the implementer needs to switch from calling `evaluate_line` (which returns
`(score, outcome)`) to calling `_evaluate_line_details` (which returns a `LineEvaluation` with
`.tie_order_details`), then extracting the accuracy counts from the `LineEvaluation`.

**Important:** The implementer should check whether `_evaluate_line_details` is already used at
these call sites or whether it needs to be introduced. The existing code at lines 620-634 calls
`evaluate_line(...)` which internally calls `_evaluate_line_details(...)`. To get leaf counts
without changing the internal structure of `evaluate_line`, the cleanest approach is to wrap
`_evaluate_line_details` with a temporary recorder for the scope of the decision, exactly like
the test recorder pattern in `test_accuracy_mode_wiring.py`.

- [ ] **Step 4: Wire the sink through `_choose_best_mega` into `score_evaluated_variants`**

Add `readiness_sink=None` to `_choose_best_mega` and forward it to `score_evaluated_variants`.
In `score_evaluated_variants`, apply the same counting approach.

- [ ] **Step 5: Run the tests**

Run: `pytest showdown_bot/tests/test_depth2_accuracy_wiring.py -k readiness_sink -v`
Expected: all PASS.

- [ ] **Step 6: Verify no regressions**

Run: `pytest showdown_bot/tests/test_search_depth2.py showdown_bot/tests/test_accuracy_mode_wiring.py showdown_bot/tests/test_depth2_accuracy_wiring.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/src/showdown_bot/battle/mega_scoring.py showdown_bot/tests/test_depth2_accuracy_wiring.py
git commit -m "feat: wire Depth2ReadinessCounts into scoring paths

_choose_best and score_evaluated_variants populate the optional
readiness sink with search config, Turn-1/Turn-2 accuracy leaf counts,
and frontier shape. No allocation when profiling is off. Spec §6.5."
```

---

## Task 7: Add decision-profile-v4 schema

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/decision_profile.py`
- Create: `showdown_bot/tests/test_decision_profile_v4.py`

v4 adds 14 new fields (the `Depth2ReadinessCounts.to_dict()` fields) to the v3 live field set.
The existing v1-v3 field sets and validators remain unchanged.

- [ ] **Step 1: Write the failing v4 schema tests**

Create `showdown_bot/tests/test_decision_profile_v4.py`:

```python
"""decision-profile-v4 schema tests (spec §7)."""
from __future__ import annotations

import copy
import pytest

from showdown_bot.eval.decision_profile import (
    SCHEMA_VERSION_V1,
    SCHEMA_VERSION_V2,
    SCHEMA_VERSION_LIVE,
    validate_profile_row_fields,
    validate_decision_profile_row,
    DecisionProfileError,
)


# ---- §7.1: v4 is a new schema version, not a mutation of v3 ----

def test_v4_schema_version_exists():
    from showdown_bot.eval.decision_profile import SCHEMA_VERSION_V4
    assert SCHEMA_VERSION_V4 == "decision-profile-v4"
    assert SCHEMA_VERSION_V4 not in {SCHEMA_VERSION_V1, SCHEMA_VERSION_V2, SCHEMA_VERSION_LIVE}


# ---- §7.2: v4 field set includes readiness fields ----

def test_v4_field_set_includes_readiness_fields():
    from showdown_bot.eval.decision_profile import _FIELD_SET_V4

    readiness_fields = {
        "search_depth", "search_topn_requested", "search_topm_requested",
        "depth2_candidates_selected", "depth2_response_slots_eligible",
        "accuracy_mode", "accuracy_branch_cap",
        "turn1_accuracy_leaf_count", "turn1_accuracy_cap_hits", "turn1_accuracy_cap_fallback",
        "turn2_accuracy_leaf_count", "turn2_accuracy_cap_hits", "turn2_accuracy_cap_fallback",
        "selection_stage", "fallback_reason",
    }
    assert readiness_fields <= _FIELD_SET_V4


def test_v4_is_superset_of_v3():
    from showdown_bot.eval.decision_profile import _FIELD_SET_V4, _FIELD_SET_LIVE
    assert _FIELD_SET_LIVE < _FIELD_SET_V4


# ---- §7.2: exact-closed field validation ----

def _minimal_v4_row():
    """A minimal valid v4 row for field-set testing."""
    from showdown_bot.eval.decision_profile import SCHEMA_VERSION_V4
    return {
        "schema_version": SCHEMA_VERSION_V4,
        "source": "live",
        "battle_id": "battle-1",
        "decision_index": 0,
        "arm_id": None,
        "rep": None,
        "config_id": "cfg",
        "format_id": "fmt",
        "git_sha": "abc123",
        "config_hash": "hash",
        "schedule_hash": "sched",
        "profile_manifest_hash": None,
        "calc_backend": "persistent",
        "backend_class": "persistent_warm",
        "cache_class": None,
        "damage_cache_size_at_rep_start": None,
        "speed_cache_size_at_rep_start": None,
        "dex_cache_size_at_rep_start": None,
        "spawn_count_before": 1,
        "transport_retried": False,
        "timer_scope": "agent_choose",
        "measured_ms": 100.0,
        "damage_batch_calls": 5,
        "planned_damage_batches": 3,
        "implicit_damage_batches": 2,
        "stats_batch_calls": 1,
        "types_batch_calls": 0,
        "mixed_batch_calls": 0,
        "transport_calls": 6,
        "transport_attempts": 6,
        "spawn_calls": 0,
        "requests_total": 20,
        "requests_unique": 15,
        "cache_hits": 5,
        "n_candidates": 6,
        "n_responses": 5,
        "n_mega_twins": 0,
        "n_branches": 0,
        "n_worlds": 1,
        "depth2_frontier": 0,
        "foe_mega_active": False,
        "outcome": "ok",
        "foe_mega_slots": [],
        "foe_mega_order_tie": False,
        # v4 readiness fields
        "search_depth": 1,
        "search_topn_requested": 2,
        "search_topm_requested": 2,
        "depth2_candidates_selected": 0,
        "depth2_response_slots_eligible": 0,
        "accuracy_mode": True,
        "accuracy_branch_cap": 6,
        "turn1_accuracy_leaf_count": 10,
        "turn1_accuracy_cap_hits": 0,
        "turn1_accuracy_cap_fallback": False,
        "turn2_accuracy_leaf_count": 0,
        "turn2_accuracy_cap_hits": 0,
        "turn2_accuracy_cap_fallback": False,
        "selection_stage": "heuristic",
        "fallback_reason": None,
    }


def test_v4_exact_field_set_accepts_valid():
    row = _minimal_v4_row()
    validate_profile_row_fields(row)  # should not raise


def test_v4_rejects_missing_field():
    row = _minimal_v4_row()
    del row["search_depth"]
    with pytest.raises(DecisionProfileError, match="missing=.*search_depth"):
        validate_profile_row_fields(row)


def test_v4_rejects_unknown_field():
    row = _minimal_v4_row()
    row["invented_field"] = 42
    with pytest.raises(DecisionProfileError, match="unknown=.*invented_field"):
        validate_profile_row_fields(row)


# ---- §7.3: Cross-field invariants (mutation-style negative tests) ----

def test_depth1_implies_zero_depth2_work():
    """search_depth == 1 -> all depth2 and turn2 counters must be zero."""
    row = _minimal_v4_row()
    row["search_depth"] = 1
    row["depth2_candidates_selected"] = 1  # violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_depth1_implies_zero_turn2():
    row = _minimal_v4_row()
    row["search_depth"] = 1
    row["turn2_accuracy_leaf_count"] = 5  # violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_depth2_frontier_bounded_by_eligible():
    row = _minimal_v4_row()
    row["search_depth"] = 2
    row["depth2_candidates_selected"] = 2
    row["depth2_response_slots_eligible"] = 3
    row["depth2_frontier"] = 4  # > eligible = violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_accuracy_off_implies_zero_leaf_counts():
    row = _minimal_v4_row()
    row["accuracy_mode"] = False
    row["turn1_accuracy_leaf_count"] = 5  # violation
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_cap_hit_fallback_consistency():
    row = _minimal_v4_row()
    row["turn1_accuracy_cap_hits"] = 2
    row["turn1_accuracy_cap_fallback"] = False  # violation: hits > 0 but fallback False
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_cap_fallback_without_hits():
    row = _minimal_v4_row()
    row["turn1_accuracy_cap_hits"] = 0
    row["turn1_accuracy_cap_fallback"] = True  # violation: no hits but fallback True
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_search_depth_enum():
    """search_depth must be exactly 1 or 2."""
    row = _minimal_v4_row()
    row["search_depth"] = 3
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_accuracy_mode_strict_bool():
    """accuracy_mode must be strict bool, not int."""
    row = _minimal_v4_row()
    row["accuracy_mode"] = 1  # int, not bool
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_counters_reject_bool():
    """Int counters must reject booleans (isinstance(True, int) is True in Python)."""
    row = _minimal_v4_row()
    row["turn1_accuracy_leaf_count"] = True  # bool, not int
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_counters_reject_negative():
    row = _minimal_v4_row()
    row["turn1_accuracy_leaf_count"] = -1
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


# ---- backward compatibility: v1/v2/v3 rows still validate ----

def test_v1_row_still_validates():
    """A valid v1 row must not be broken by v4 additions."""
    from showdown_bot.eval.decision_profile import PROFILE_ROW_FIELDS_V1
    row = {f: None for f in PROFILE_ROW_FIELDS_V1}
    row["schema_version"] = SCHEMA_VERSION_V1
    validate_profile_row_fields(row)  # should not raise


def test_v3_row_still_validates():
    """A valid v3 row must not be broken by v4 additions."""
    from showdown_bot.eval.decision_profile import PROFILE_ROW_FIELDS_LIVE
    row = {f: None for f in PROFILE_ROW_FIELDS_LIVE}
    row["schema_version"] = SCHEMA_VERSION_LIVE
    validate_profile_row_fields(row)  # should not raise
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest showdown_bot/tests/test_decision_profile_v4.py -v`
Expected: FAIL — `SCHEMA_VERSION_V4` does not exist.

- [ ] **Step 3: Implement v4 schema in `decision_profile.py`**

Add to `decision_profile.py` after the existing v3 definitions (around line 125):

```python
# v4 live-only (Stage-3 Readiness): v3 fields PLUS the Depth2ReadinessCounts fields and
# selection_stage/fallback_reason. Derived by union so it tracks v3 automatically.
_V4_ONLY_FIELDS = (
    "search_depth", "search_topn_requested", "search_topm_requested",
    "depth2_candidates_selected", "depth2_response_slots_eligible",
    "accuracy_mode", "accuracy_branch_cap",
    "turn1_accuracy_leaf_count", "turn1_accuracy_cap_hits", "turn1_accuracy_cap_fallback",
    "turn2_accuracy_leaf_count", "turn2_accuracy_cap_hits", "turn2_accuracy_cap_fallback",
    "selection_stage", "fallback_reason",
)
SCHEMA_VERSION_V4 = "decision-profile-v4"
PROFILE_ROW_FIELDS_V4: tuple[str, ...] = PROFILE_ROW_FIELDS_LIVE + _V4_ONLY_FIELDS
_FIELD_SET_V4 = _FIELD_SET_LIVE | frozenset(_V4_ONLY_FIELDS)
```

Update `_SCHEMA_VERSIONS` to include `SCHEMA_VERSION_V4`:

```python
_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION_V1, SCHEMA_VERSION_V2, SCHEMA_VERSION_LIVE, SCHEMA_VERSION_V4})
```

Update `validate_profile_row_fields` to handle v4:

Add an `elif sv == SCHEMA_VERSION_V4: expected = _FIELD_SET_V4` branch before the `else`.

Add v4 semantic validation rules to `validate_decision_profile_row`:

After the v3 foe-Mega rules (around line 937), add a v4 block:

```python
    # ---- v4 readiness telemetry (Stage-3) ---------------------------------
    if row.get("schema_version") == SCHEMA_VERSION_V4:
        sd = row["search_depth"]
        _require(
            isinstance(sd, int) and not isinstance(sd, bool) and sd in (1, 2),
            f"search_depth must be 1 or 2, got {sd!r}",
        )
        _require(
            isinstance(row["accuracy_mode"], bool),
            f"accuracy_mode must be a strict bool, got {row['accuracy_mode']!r}",
        )

        for field in ("search_topn_requested", "search_topm_requested",
                       "depth2_candidates_selected", "depth2_response_slots_eligible",
                       "accuracy_branch_cap",
                       "turn1_accuracy_leaf_count", "turn1_accuracy_cap_hits",
                       "turn2_accuracy_leaf_count", "turn2_accuracy_cap_hits"):
            v = row[field]
            _require(
                isinstance(v, int) and not isinstance(v, bool) and v >= 0,
                f"{field} must be a non-negative int, got {v!r}",
            )

        _require(
            isinstance(row["turn1_accuracy_cap_fallback"], bool),
            f"turn1_accuracy_cap_fallback must be bool, got {row['turn1_accuracy_cap_fallback']!r}",
        )
        _require(
            isinstance(row["turn2_accuracy_cap_fallback"], bool),
            f"turn2_accuracy_cap_fallback must be bool, got {row['turn2_accuracy_cap_fallback']!r}",
        )

        # Cross-field invariants (spec §7.3)
        if sd == 1:
            _require(row["depth2_candidates_selected"] == 0,
                     "search_depth==1 but depth2_candidates_selected != 0")
            _require(row["depth2_frontier"] == 0,
                     "search_depth==1 but depth2_frontier != 0")
            _require(row["turn2_accuracy_leaf_count"] == 0,
                     "search_depth==1 but turn2_accuracy_leaf_count != 0")
            _require(row["turn2_accuracy_cap_hits"] == 0,
                     "search_depth==1 but turn2_accuracy_cap_hits != 0")
            _require(row["turn2_accuracy_cap_fallback"] is False,
                     "search_depth==1 but turn2_accuracy_cap_fallback is True")

        _require(
            row["depth2_frontier"] <= row["depth2_response_slots_eligible"],
            "depth2_frontier > depth2_response_slots_eligible",
        )
        _require(
            row["depth2_candidates_selected"] <= row["search_topn_requested"],
            "depth2_candidates_selected > search_topn_requested",
        )
        _require(
            row["depth2_frontier"] <= row["depth2_candidates_selected"] * row["search_topm_requested"],
            "depth2_frontier > candidates * topm",
        )

        if not row["accuracy_mode"]:
            for field in ("turn1_accuracy_leaf_count", "turn1_accuracy_cap_hits",
                          "turn2_accuracy_leaf_count", "turn2_accuracy_cap_hits"):
                _require(row[field] == 0,
                         f"accuracy_mode is False but {field} != 0")

        _require(
            row["turn1_accuracy_cap_fallback"] == (row["turn1_accuracy_cap_hits"] > 0),
            "turn1_accuracy_cap_fallback inconsistent with turn1_accuracy_cap_hits",
        )
        _require(
            row["turn2_accuracy_cap_fallback"] == (row["turn2_accuracy_cap_hits"] > 0),
            "turn2_accuracy_cap_fallback inconsistent with turn2_accuracy_cap_hits",
        )

        if row["depth2_frontier"] == 0:
            _require(row["turn2_accuracy_leaf_count"] == 0,
                     "no depth2 but turn2_accuracy_leaf_count != 0")
            _require(row["turn2_accuracy_cap_fallback"] is False,
                     "no depth2 but turn2_accuracy_cap_fallback is True")

        # selection_stage / fallback_reason vocabulary
        ss = row["selection_stage"]
        _require(
            ss is None or ss in ({LIVE_OK_STAGE} | LIVE_FALLBACK_STAGES),
            f"selection_stage must be None or a known stage, got {ss!r}",
        )
```

**Note:** The implementer must verify the exact selection_stage vocabulary by reading the existing
code around `LIVE_OK_STAGE` and `LIVE_FALLBACK_STAGES` (lines 232-235 of `decision_profile.py`)
and write the validation accordingly.

- [ ] **Step 4: Run the v4 tests**

Run: `pytest showdown_bot/tests/test_decision_profile_v4.py -v`
Expected: all PASS.

- [ ] **Step 5: Run existing profile tests for backward compat**

Run: `pytest showdown_bot/tests/test_decision_profile_validator.py showdown_bot/tests/test_decision_profile_v3.py showdown_bot/tests/test_decision_profile_writer.py showdown_bot/tests/test_profile_fixtures.py showdown_bot/tests/test_i8d_live_row.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/decision_profile.py showdown_bot/tests/test_decision_profile_v4.py
git commit -m "feat: add decision-profile-v4 schema with readiness fields

15 new fields for search_depth, accuracy config, per-ply leaf/cap
counters, cap fallback booleans, and selection_stage/fallback_reason.
v1-v3 field sets and validators unchanged. Cross-field invariants
per spec §7.3."
```

---

## Task 8: Build and persist v4 profile rows

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/decision_profile.py`
- Modify: `showdown_bot/src/showdown_bot/client/gauntlet.py`
- Modify: `showdown_bot/tests/test_decision_profile_v4.py`

This task wires the `Depth2ReadinessCounts` into the profile row builder and the live gauntlet path.
`build_live_profile_row` gains a new optional `readiness` parameter; when provided, it stamps
`SCHEMA_VERSION_V4` and includes the readiness fields + the `SelectionStageSink` fields.

- [ ] **Step 1: Write the failing build test**

Append to `showdown_bot/tests/test_decision_profile_v4.py`:

```python
def test_build_live_profile_row_v4():
    """build_live_profile_row with readiness produces a valid v4 row."""
    from showdown_bot.eval.decision_profile import build_live_profile_row, SCHEMA_VERSION_V4
    from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts

    sink = Depth2ReadinessCounts()
    sink.search_depth = 1
    sink.search_topn_requested = 2
    sink.search_topm_requested = 2
    sink.accuracy_mode = True
    sink.accuracy_branch_cap = 6
    sink.add_turn1_accuracy(leaf_count=10, cap_hits=0)

    counters_before = {
        "damage_batch_calls": 0, "planned_damage_batches": 0, "implicit_damage_batches": 0,
        "stats_batch_calls": 0, "types_batch_calls": 0, "mixed_batch_calls": 0,
        "transport_attempts": 0, "requests_total": 0, "requests_unique": 0,
        "cache_hits": 0, "spawn_count": 0,
    }
    counters_after = {
        "damage_batch_calls": 5, "planned_damage_batches": 3, "implicit_damage_batches": 2,
        "stats_batch_calls": 1, "types_batch_calls": 0, "mixed_batch_calls": 0,
        "transport_attempts": 6, "requests_total": 20, "requests_unique": 15,
        "cache_hits": 5, "spawn_count": 0,
    }
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    shape = MegaShapeCounts(n_candidates=6, n_responses=5)

    row = build_live_profile_row(
        battle_id="b1", decision_index=0, schedule_hash="sh",
        config_id="c", format_id="f", git_sha="g", config_hash="h",
        calc_backend="persistent", outcome="ok", latency_ms=100.0,
        counters_before=counters_before, counters_after=counters_after,
        shape=shape,
        readiness=sink,
        selection_stage="heuristic",
        fallback_reason=None,
    )

    assert row["schema_version"] == SCHEMA_VERSION_V4
    assert row["search_depth"] == 1
    assert row["accuracy_mode"] is True
    assert row["turn1_accuracy_leaf_count"] == 10
    assert row["selection_stage"] == "heuristic"
    assert row["fallback_reason"] is None
    validate_profile_row_fields(row)
    validate_decision_profile_row(row, manifest=None)


def test_build_live_profile_row_no_readiness_stays_v3():
    """Without readiness, build_live_profile_row produces v3 as before."""
    from showdown_bot.eval.decision_profile import build_live_profile_row, SCHEMA_VERSION_LIVE

    counters_before = {
        "damage_batch_calls": 0, "planned_damage_batches": 0, "implicit_damage_batches": 0,
        "stats_batch_calls": 0, "types_batch_calls": 0, "mixed_batch_calls": 0,
        "transport_attempts": 0, "requests_total": 0, "requests_unique": 0,
        "cache_hits": 0, "spawn_count": 0,
    }
    counters_after = dict(counters_before)
    from showdown_bot.battle.mega_scoring import MegaShapeCounts
    shape = MegaShapeCounts(n_candidates=2, n_responses=3)

    row = build_live_profile_row(
        battle_id="b1", decision_index=0, schedule_hash="sh",
        config_id="c", format_id="f", git_sha="g", config_hash="h",
        calc_backend="persistent", outcome="ok", latency_ms=50.0,
        counters_before=counters_before, counters_after=counters_after,
        shape=shape,
    )
    assert row["schema_version"] == SCHEMA_VERSION_LIVE
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest showdown_bot/tests/test_decision_profile_v4.py::test_build_live_profile_row_v4 -v`
Expected: FAIL — `build_live_profile_row` does not accept `readiness`.

- [ ] **Step 3: Modify `build_live_profile_row` to accept readiness**

In `decision_profile.py`, modify `build_live_profile_row` signature to add:
```python
readiness=None, selection_stage=None, fallback_reason=None,
```

At the end of the row dict construction, if `readiness is not None`:
- Stamp `"schema_version": SCHEMA_VERSION_V4`
- Add all `readiness.to_dict()` fields
- Add `"selection_stage": selection_stage, "fallback_reason": fallback_reason`

If `readiness is None`, keep `SCHEMA_VERSION_LIVE` (v3 behavior unchanged).

- [ ] **Step 4: Modify `gauntlet.py` to allocate and pass readiness**

In `gauntlet.py`, in the `handle_request` method:
- Import `Depth2ReadinessCounts` from `showdown_bot.eval.depth2_readiness`
- When `profile_on` is True, allocate `readiness_sink = Depth2ReadinessCounts()`
- Pass `readiness_sink=readiness_sink` to `agent_choose` (which flows into `_choose_best`)
- When building the profile row, pass `readiness=readiness_sink`,
  `selection_stage=profile_stage_sink.selection_stage`,
  `fallback_reason=profile_stage_sink.fallback_reason`

The implementer must read the existing gauntlet code (around lines 800-993) to find the exact
insertion points.

- [ ] **Step 5: Run all v4 tests**

Run: `pytest showdown_bot/tests/test_decision_profile_v4.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full profile test suite**

Run: `pytest showdown_bot/tests/test_decision_profile_validator.py showdown_bot/tests/test_decision_profile_v3.py showdown_bot/tests/test_decision_profile_writer.py showdown_bot/tests/test_i8d_live_row.py showdown_bot/tests/test_i8d_live_profile_wiring.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/decision_profile.py showdown_bot/src/showdown_bot/client/gauntlet.py showdown_bot/tests/test_decision_profile_v4.py
git commit -m "feat: build and persist decision-profile-v4 rows

build_live_profile_row stamps v4 when readiness sink is provided.
gauntlet allocates the sink when profiling is on and threads it
through to the profile row. v3 path unchanged when readiness is None.
Spec §7."
```

---

## Task 9: Focused and full verification

**Files:** none (verification only)

- [ ] **Step 1: Run all new focused tests**

```bash
pytest showdown_bot/tests/test_depth2_accuracy_wiring.py showdown_bot/tests/test_depth2_readiness_telemetry.py showdown_bot/tests/test_decision_profile_v4.py -v
```

Expected: all PASS.

- [ ] **Step 2: Run all existing affected test suites**

```bash
pytest showdown_bot/tests/test_search_depth2.py showdown_bot/tests/test_accuracy_mode_wiring.py showdown_bot/tests/test_decision_profile_validator.py showdown_bot/tests/test_decision_profile_v3.py showdown_bot/tests/test_decision_profile_writer.py showdown_bot/tests/test_profile_fixtures.py showdown_bot/tests/test_i8d_live_row.py showdown_bot/tests/test_i8d_live_profile_wiring.py showdown_bot/tests/test_i8d_outcome_signal.py showdown_bot/tests/test_decision_trace.py -v
```

Expected: all PASS.

- [ ] **Step 3: Run the full `showdown_bot` test suite**

```bash
pytest showdown_bot -q
```

Expected: all PASS, no new unexplained skip/xfail.

- [ ] **Step 4: Run `git diff --check`**

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: If any test fails, fix and recommit before proceeding**

---

## Task 10: Cost preflight

**Files:** none modified (measurement run + report)

This task runs the 4-arm cost preflight on the fixed Windows measurement host with the persistent
calc backend. It uses the existing reproducible profile harness/manifest conventions.

**This task is MANUAL and operator-directed.** The implementer prepares the measurement script/config
and documents the invocation. The actual measurement is run by the operator.

- [ ] **Step 1: Document the preflight matrix and invocation**

Create a section in the closeout report (Task 11) documenting:
- The 4 arms: Depth1/AccOff, Depth1/AccOn(cap6), Depth2(3,3)/AccOff, Depth2(3,3)/AccOn(cap6)
- How to invoke each arm using existing env vars
- That cold/warm strata must be reported separately
- The required output columns (spec §11.2)

The operator runs the preflight and pastes the results. The implementer validates the results
against the v4 schema and the §11.3 interpretation rules.

- [ ] **Step 2: Validate the preflight results against v4 schema**

For every row produced by the preflight:
```bash
python -c "
import json, sys
from showdown_bot.eval.decision_profile import validate_decision_profile_row
for line in open(sys.argv[1]):
    row = json.loads(line)
    validate_decision_profile_row(row, manifest=None)
print('All rows valid')
" <path_to_preflight_output.jsonl>
```

Expected: "All rows valid".

---

## Task 11: Closeout report and status update

**Files:**
- Create: `docs/projects/learning/reports/2026-07-27-depth2-accuracy-stage3-readiness-closeout.md`
- Modify: `docs/ROADMAP.md` (status update)
- Modify: `docs/PROJECT_INDEX.md` (if applicable)

- [ ] **Step 1: Write the closeout report**

The report must state:
> When the existing coarse Depth-2 path is used, its Turn-1 and Turn-2 evaluations now use one
> resolved accuracy configuration, and the executed work is observable.

It must NOT say:
- Depth-2 is stronger
- Depth-2 is production-ready or default-on
- the method computes a full two-turn expected value
- the 1000-ms live gate passed
- the diverse panel passed
- Champions Strength changed from NO-GO
- a new holdout is authorized

Include: what was verified locally (focused + full suite), preflight summary, what remains unrun
(diverse panel, live gate, holdout).

- [ ] **Step 2: Update `docs/ROADMAP.md`**

Mark the Depth-2 accuracy consistency slice as complete. Do not change any Strength claim.

- [ ] **Step 3: Commit**

```bash
git add docs/projects/learning/reports/2026-07-27-depth2-accuracy-stage3-readiness-closeout.md docs/ROADMAP.md
git commit -m "docs: Stage-3 readiness closeout — accuracy-consistent Depth-2

Compatibility and observability only. No strength claim, no default
change. Spec §15."
```

---

## Stop conditions (spec §13)

If implementation requires ANY of the following, **stop and return to design review**:

- A second persisted sidecar (beyond the existing profile JSONL)
- A `DecisionTrace` schema change
- A chooser change (modifying `pick_best`, `aggregate_scores`, or tie-breaking)
- A frontier change (modifying how top-N/top-M are selected)
- A state-transition change (modifying `approx_turn2_state`)
- Touching `search.py` beyond what the spec explicitly allows (the `**eval_kwargs` seam already
  forwards; no new parameters or functions should be needed there)

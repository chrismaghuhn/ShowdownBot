# 2c NEUTRAL CVaR Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an off-by-default `SHOWDOWN_NEUTRAL_CVAR` toggle that replaces the NEUTRAL aggregation operator's variance downside with a weighted-CVaR worst-case-tail downside, byte-identical when unset.

**Architecture:** A pure `cvar_lower()` helper + three env readers in `battle/policy.py`, read **inside** `aggregate_scores`'s NEUTRAL branch (mirroring how `MUST_REACT` already reads `_must_react_lambda()` there — so **no `decision.py` change**, all call sites inherit it). Three env vars classified BEHAVIOR_AFFECTING. MUST_REACT and AHEAD operators are untouched. Winrate gate (Kaggle) is out-of-band, deferred to the controller.

**Tech Stack:** Python 3.12, pytest. Run tests with `PYTHONPATH=showdown_bot/src python -m pytest ...` from the repo root.

---

## File Structure

- `showdown_bot/src/showdown_bot/battle/policy.py` — add `cvar_lower()`, `_neutral_cvar_enabled()`, `_cvar_alpha()`, `_cvar_lambda()`; branch the two NEUTRAL returns in `aggregate_scores` on the toggle.
- `showdown_bot/src/showdown_bot/eval/config_env.py` — add the 3 env vars to `BEHAVIOR_AFFECTING`.
- `showdown_bot/tests/test_cvar_lower.py` — new; the CVaR math.
- `showdown_bot/tests/test_policy.py` — extend; operator behavior + off-parity.
- `showdown_bot/tests/test_config_env.py` — extend; classification + config_hash.

No `decision.py` change: `aggregate_scores` reads the CVaR env inside its NEUTRAL branch, exactly like `_must_react_lambda()` (policy.py:76), so all four call sites inherit it.

---

### Task 1: `cvar_lower` weighted lower-tail CVaR helper

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/policy.py` (add function after `risk_lambda()`, before `aggregate_scores`)
- Test: `showdown_bot/tests/test_cvar_lower.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `showdown_bot/tests/test_cvar_lower.py`:

```python
from statistics import mean

import pytest

from showdown_bot.battle.policy import cvar_lower


def test_empty_returns_zero():
    assert cvar_lower([], None, 0.25) == 0.0


def test_single_returns_that_value():
    assert cvar_lower([7.0], None, 0.25) == 7.0


def test_alpha_one_is_uniform_mean():
    scores = [1.0, 2.0, 3.0, 4.0]
    assert cvar_lower(scores, None, 1.0) == pytest.approx(mean(scores))


def test_small_alpha_approaches_min():
    scores = [5.0, 1.0, 9.0, 3.0]
    assert cvar_lower(scores, None, 1e-6) == pytest.approx(min(scores))


def test_uniform_worst_quarter_of_four():
    # alpha=0.25, 4 equal-weight scores -> exactly the worst one.
    assert cvar_lower([10.0, 2.0, 8.0, 6.0], None, 0.25) == pytest.approx(2.0)


def test_straddle_clipping_exact_alpha_mass():
    # 5 equal weights (0.2 each), alpha=0.25 -> worst (0.2 @ score 1) + 0.05 of next (score 2),
    # averaged over 0.25 mass: (0.2*1 + 0.05*2)/0.25 = 1.2
    assert cvar_lower([1.0, 2.0, 3.0, 4.0, 5.0], None, 0.25) == pytest.approx(1.2)


def test_weighted_tail_uses_weights():
    # scores 1,2,3 with weights 0.1,0.1,0.8; alpha=0.25 -> worst 0.1@1 + 0.1@2 + 0.05@3,
    # over 0.25: (0.1*1 + 0.1*2 + 0.05*3)/0.25 = (0.1+0.2+0.15)/0.25 = 1.8
    assert cvar_lower([1.0, 2.0, 3.0], [0.1, 0.1, 0.8], 0.25) == pytest.approx(1.8)


def test_bad_weights_fall_back_to_uniform():
    # wrong length -> uniform; equals the unweighted worst-quarter-of-four result.
    assert cvar_lower([10.0, 2.0, 8.0, 6.0], [1.0], 0.25) == pytest.approx(2.0)


def test_monotonic_nondecreasing_in_alpha():
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    vals = [cvar_lower(scores, None, a) for a in (0.1, 0.25, 0.5, 0.75, 1.0)]
    assert all(vals[i] <= vals[i + 1] + 1e-9 for i in range(len(vals) - 1))


def test_deterministic():
    scores = [3.0, 1.0, 4.0, 1.0, 5.0]
    assert cvar_lower(scores, None, 0.3) == cvar_lower(scores, None, 0.3)
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_cvar_lower.py -q`
Expected: FAIL — `ImportError: cannot import name 'cvar_lower'`.

- [ ] **Step 3: Implement `cvar_lower`**

In `showdown_bot/src/showdown_bot/battle/policy.py`, add after the `risk_lambda()` function (which ends near line 43) and before `aggregate_scores`:

```python
def cvar_lower(scores: list[float], weights: list[float] | None, alpha: float) -> float:
    """Lower-tail CVaR (expected shortfall): probability-weighted mean of the worst
    ``alpha``-mass of ``scores``. ``alpha`` clamped to (0, 1]; ``alpha >= 1`` -> full
    weighted mean; ``alpha`` -> 0 approaches ``min(scores)``. ``weights`` None or
    unusable (length mismatch / non-positive sum) -> uniform. Empty -> 0.0. Pure,
    deterministic, no RNG. Over the current <=5 opponent responses this is close to
    ``min``; the same helper takes the tail of many sampled worlds once +Sampling lands."""
    if not scores:
        return 0.0
    alpha = max(1e-9, min(1.0, alpha))
    n = len(scores)
    if weights is not None and len(weights) == n and sum(weights) > 0:
        total = sum(weights)
        pairs = [(s, w / total) for s, w in zip(scores, weights)]
    else:
        pairs = [(s, 1.0 / n) for s in scores]
    pairs.sort(key=lambda sw: sw[0])  # ascending: worst first
    acc_w = 0.0
    acc_sw = 0.0
    for s, w in pairs:
        take = min(w, alpha - acc_w)
        if take <= 0:
            break
        acc_sw += take * s
        acc_w += take
        if acc_w >= alpha:
            break
    return acc_sw / acc_w if acc_w > 0 else pairs[0][0]
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_cvar_lower.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/policy.py showdown_bot/tests/test_cvar_lower.py
git commit -m "feat(2c-cvar): weighted lower-tail cvar_lower helper"
```

---

### Task 2: Classify the three env vars BEHAVIOR_AFFECTING

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/config_env.py` (the `BEHAVIOR_AFFECTING` frozenset)
- Test: `showdown_bot/tests/test_config_env.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_config_env.py`:

```python
# --- NEUTRAL-mode CVaR knobs (2c-cvar) --------------------------------------------------

def test_neutral_cvar_knobs_behavior_affecting_and_classified():
    for name in ("SHOWDOWN_NEUTRAL_CVAR", "SHOWDOWN_CVAR_ALPHA", "SHOWDOWN_CVAR_LAMBDA"):
        assert name in BEHAVIOR_AFFECTING
        assert name not in SERVER_SIDE_BEHAVIOR_AFFECTING
        assert is_classified(name)


def test_behavior_env_includes_cvar_knobs():
    env = {"SHOWDOWN_NEUTRAL_CVAR": "1", "SHOWDOWN_CVAR_ALPHA": "0.25",
           "SHOWDOWN_CVAR_LAMBDA": "0.5"}
    assert behavior_env(env) == env


def test_config_hash_changes_when_neutral_cvar_toggled():
    h_off = make_config_hash(_manifest(behavior_env({})))
    h_on = make_config_hash(_manifest(behavior_env({"SHOWDOWN_NEUTRAL_CVAR": "1"})))
    assert h_off != h_on
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_config_env.py -q -k cvar`
Expected: FAIL — the three names are not in `BEHAVIOR_AFFECTING`.

- [ ] **Step 3: Add the vars to `BEHAVIOR_AFFECTING`**

In `showdown_bot/src/showdown_bot/eval/config_env.py`, inside the `BEHAVIOR_AFFECTING = frozenset({...})` block, right after the `"SHOWDOWN_RISK_LAMBDA",` entry, add:

```python
    # [2c-cvar] NEUTRAL-mode CVaR aggregation: SHOWDOWN_NEUTRAL_CVAR toggles the NEUTRAL
    # downside from variance to a worst-case CVaR tail; ALPHA/LAMBDA parameterize it. All
    # read in showdown_bot.battle.policy (aggregate_scores) -> Python source, changes which
    # move is played -> config_hash. Off by default = byte-identical.
    "SHOWDOWN_NEUTRAL_CVAR",
    "SHOWDOWN_CVAR_ALPHA",
    "SHOWDOWN_CVAR_LAMBDA",
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_config_env.py -q`
Expected: PASS (all, including the 3 new).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/config_env.py showdown_bot/tests/test_config_env.py
git commit -m "feat(2c-cvar): classify SHOWDOWN_NEUTRAL_CVAR/ALPHA/LAMBDA behavior-affecting"
```

---

### Task 3: NEUTRAL CVaR readers + operator toggle

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/policy.py` (3 readers + the two NEUTRAL branches in `aggregate_scores`)
- Test: `showdown_bot/tests/test_policy.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_policy.py` (imports `aggregate_scores`, `GameMode` are already at the top of that file; add `monkeypatch` usage inline):

```python
from statistics import mean, pvariance

from showdown_bot.battle.policy import aggregate_scores, cvar_lower
from showdown_bot.engine.belief.game_mode import GameMode


def test_neutral_off_is_unchanged_variance(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_NEUTRAL_CVAR", raising=False)
    scores = [1.0, 2.0, 3.0, 4.0]
    expected = mean(scores) - 0.5 * pvariance(scores)
    assert aggregate_scores(scores, GameMode.NEUTRAL, risk_lambda=0.5) == pytest.approx(expected)


def test_neutral_on_uses_cvar_unweighted(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.setenv("SHOWDOWN_CVAR_ALPHA", "0.25")
    monkeypatch.setenv("SHOWDOWN_CVAR_LAMBDA", "0.5")
    scores = [1.0, 2.0, 3.0, 4.0]
    m = mean(scores)
    expected = m - 0.5 * (m - cvar_lower(scores, None, 0.25))
    assert aggregate_scores(scores, GameMode.NEUTRAL) == pytest.approx(expected)


def test_neutral_on_uses_cvar_weighted(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.setenv("SHOWDOWN_CVAR_ALPHA", "0.25")
    monkeypatch.setenv("SHOWDOWN_CVAR_LAMBDA", "0.5")
    scores = [1.0, 2.0, 3.0]
    weights = [0.1, 0.1, 0.8]
    wmean = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    expected = wmean - 0.5 * (wmean - cvar_lower(scores, weights, 0.25))
    assert aggregate_scores(scores, GameMode.NEUTRAL, weights=weights) == pytest.approx(expected)


def test_neutral_on_lambda_zero_is_pure_mean(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.setenv("SHOWDOWN_CVAR_LAMBDA", "0")
    scores = [1.0, 5.0, 9.0]
    assert aggregate_scores(scores, GameMode.NEUTRAL) == pytest.approx(mean(scores))


def test_must_react_unaffected_by_cvar_env(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.delenv("SHOWDOWN_MUST_REACT_LAMBDA", raising=False)
    scores = [1.0, 2.0, 3.0, 4.0]
    expected = mean(scores) - 0.6 * (mean(scores) - min(scores))  # default mr_lambda 0.6
    assert aggregate_scores(scores, GameMode.MUST_REACT) == pytest.approx(expected)


def test_ahead_unaffected_by_cvar_env(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    scores = [1.0, 2.0, 3.0, 4.0]
    assert aggregate_scores(scores, GameMode.AHEAD) == pytest.approx(mean(scores))
```

(If `pytest` / `mean` / `pvariance` are already imported at the top of `test_policy.py`, do not duplicate the imports — keep the file's existing import block and add only what's missing.)

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_policy.py -q -k "neutral or must_react_unaffected or ahead_unaffected"`
Expected: FAIL — `_neutral_cvar_enabled` not defined / NEUTRAL still returns variance when the env is set.

- [ ] **Step 3: Add the three readers**

In `showdown_bot/src/showdown_bot/battle/policy.py`, after `risk_lambda()` (and before `cvar_lower` from Task 1) add:

```python
def _neutral_cvar_enabled() -> bool:
    """NEUTRAL-mode CVaR downside toggle (SHOWDOWN_NEUTRAL_CVAR). Off by default ->
    byte-identical variance behavior; '1'/'true'/'yes'/'on' -> CVaR worst-case tail."""
    return os.environ.get("SHOWDOWN_NEUTRAL_CVAR", "").strip().lower() in ("1", "true", "yes", "on")


def _cvar_alpha() -> float:
    """CVaR lower-tail mass (SHOWDOWN_CVAR_ALPHA), clamped to (0, 1]. Default 0.25."""
    try:
        return max(1e-9, min(1.0, float(os.environ.get("SHOWDOWN_CVAR_ALPHA", "0.25"))))
    except ValueError:
        return 0.25


def _cvar_lambda() -> float:
    """CVaR downside weight for NEUTRAL (SHOWDOWN_CVAR_LAMBDA), clamped [0, 1]. Default
    0.5 (= historic risk_lambda default, so on-with-defaults is a pure operator swap)."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("SHOWDOWN_CVAR_LAMBDA", "0.5"))))
    except ValueError:
        return 0.5
```

- [ ] **Step 4: Branch the two NEUTRAL returns**

In `aggregate_scores`, the **weighted** path currently reads (around lines 78-84):

```python
    if use_weights:
        wsum = sum(weights)
        wmean = sum(s * w for s, w in zip(scores, weights)) / wsum
        if mode == GameMode.AHEAD:
            return wmean
        wvar = sum(w * (s - wmean) ** 2 for s, w in zip(scores, weights)) / wsum
        return wmean - risk_lambda * wvar
```

Replace it with (insert the CVaR branch before the `wvar` line):

```python
    if use_weights:
        wsum = sum(weights)
        wmean = sum(s * w for s, w in zip(scores, weights)) / wsum
        if mode == GameMode.AHEAD:
            return wmean
        if _neutral_cvar_enabled():
            tail = cvar_lower(scores, weights, _cvar_alpha())
            return wmean - _cvar_lambda() * (wmean - tail)
        wvar = sum(w * (s - wmean) ** 2 for s, w in zip(scores, weights)) / wsum
        return wmean - risk_lambda * wvar
```

The **unweighted** path currently reads (around lines 86-90):

```python
    if mode == GameMode.AHEAD:
        return mean(scores)
    if len(scores) == 1:
        return scores[0]
    return mean(scores) - risk_lambda * pvariance(scores)
```

Replace it with:

```python
    if mode == GameMode.AHEAD:
        return mean(scores)
    if len(scores) == 1:
        return scores[0]
    if _neutral_cvar_enabled():
        m = mean(scores)
        tail = cvar_lower(scores, None, _cvar_alpha())
        return m - _cvar_lambda() * (m - tail)
    return mean(scores) - risk_lambda * pvariance(scores)
```

MUST_REACT (lines 69-76) and both AHEAD returns are untouched.

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_policy.py -q`
Expected: PASS (all, incl. the 6 new).

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/policy.py showdown_bot/tests/test_policy.py
git commit -m "feat(2c-cvar): NEUTRAL CVaR operator behind SHOWDOWN_NEUTRAL_CVAR (off=byte-identical)"
```

---

### Task 4: Off-parity guard + full-suite verification + closeout

**Files:**
- Test: `showdown_bot/tests/test_policy.py` (one more test)

- [ ] **Step 1: Write the off-parity test**

Append to `showdown_bot/tests/test_policy.py`:

```python
def test_neutral_default_env_is_exact_legacy(monkeypatch):
    # With no CVaR env set at all, NEUTRAL must equal the legacy variance formula EXACTLY
    # (byte-identical-off invariant) for both weighted and unweighted paths.
    for name in ("SHOWDOWN_NEUTRAL_CVAR", "SHOWDOWN_CVAR_ALPHA", "SHOWDOWN_CVAR_LAMBDA"):
        monkeypatch.delenv(name, raising=False)
    scores = [1.0, 3.0, 3.0, 7.0]
    assert aggregate_scores(scores, GameMode.NEUTRAL, risk_lambda=0.5) == (
        mean(scores) - 0.5 * pvariance(scores))
    weights = [0.4, 0.3, 0.2, 0.1]
    wsum = sum(weights)
    wmean = sum(s * w for s, w in zip(scores, weights)) / wsum
    wvar = sum(w * (s - wmean) ** 2 for s, w in zip(scores, weights)) / wsum
    assert aggregate_scores(scores, GameMode.NEUTRAL, risk_lambda=0.5, weights=weights) == (
        wmean - 0.5 * wvar)
```

- [ ] **Step 2: Run it (should PASS immediately — guards the invariant)**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests/test_policy.py::test_neutral_default_env_is_exact_legacy -q`
Expected: PASS (the off path is unchanged).

- [ ] **Step 3: Run the full suite**

Run: `PYTHONPATH=showdown_bot/src python -m pytest showdown_bot/tests -q`
Expected: PASS — prior green count (1536) + the new tests, 0 failures. If anything unrelated fails, it is a pre-existing/environment issue — note it, do not fix in this slice.

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/tests/test_policy.py
git commit -m "test(2c-cvar): byte-identical-off parity guard for NEUTRAL"
```

- [ ] **Step 5: Closeout note**

The winrate gate is **out of band** (Kaggle, controller-run, not part of this plan): a 3-arm env-A/B via `tools/kaggle/env_ab_kernel.py` on `2b4_devstrength_v001` —
baseline `{}` vs CVaR `{"SHOWDOWN_NEUTRAL_CVAR":"1"}` vs mean-control `{"SHOWDOWN_NEUTRAL_CVAR":"1","SHOWDOWN_CVAR_LAMBDA":"0"}` — then `eval-report --mode gate`. Held-out is user-gated. Do not run battles locally.

---

## Self-Review

**Spec coverage:** cvar_lower (Task 1) ✓; 3 env vars classified (Task 2) ✓; NEUTRAL operator toggle both paths (Task 3) ✓; byte-identical-off (Task 4) ✓; MUST_REACT/AHEAD untouched (Task 3 tests) ✓; 3-arm gate (Task 4 closeout, out-of-band) ✓. Deviation from spec: no `decision.py` change — CVaR is read inside `aggregate_scores` (mirrors `_must_react_lambda`), strictly simpler and within the spec's "mirror the lambda readers" intent; the byte-identical-off invariant is covered at the `aggregate_scores` level (Task 4).

**Placeholder scan:** none — all code is concrete.

**Type consistency:** `cvar_lower(scores, weights, alpha)` signature identical across Task 1 def, Task 3 call sites, and all tests. Readers `_neutral_cvar_enabled()/_cvar_alpha()/_cvar_lambda()` named consistently in def and use.

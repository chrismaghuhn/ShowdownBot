# Accuracy Default-On — Implementation Spec

**Status:** PROPOSED — pending user/Codex review (implements
[`reports/2026-07-14-accuracy-default-on-decision-note.md`](reports/2026-07-14-accuracy-default-on-decision-note.md);
**no implementation approval yet**)
**Date:** 2026-07-14
**Commit basis:** `4f7b0a9`

## 0. What this slice does

Flip production **env-parser defaults** only:

| Knob | Today | After slice |
|------|-------|-------------|
| `SHOWDOWN_ACCURACY_MODE` (unset) | off | **on** |
| `SHOWDOWN_ACCURACY_MODE` (`""` / `"0"` / `"false"`) | off | off (explicit opt-out, unchanged) |
| `SHOWDOWN_ACCURACY_BRANCH_CAP` (unset) | `4` | **`6`** |

No change to `evaluate_line(..., accuracy_mode=False)` API defaults, gate artifacts, or
measurement JSON under `data/eval/`.

## 1. Explicit non-goals

- **No strength or winrate claim.**
- **No Depth-2 Stage 3 work.**
- **No dev-generalization / strength panel** in this slice (runs only after merge).
- **No re-run** of Gate B, cap-derisk latency sweep, or `gate-b-report.json`.
- **No change** to eval/offline drivers that already set `SHOWDOWN_ACCURACY_MODE=0` explicitly
  (`showdown_bot/scripts/run_accuracy_baseline_freeze.py`,
  `showdown_bot/scripts/run_accuracy_baseline_diff.py`, gate scripts).

## 2. Gating evidence (read-only, already committed)

| Check | Source | Result |
|-------|--------|--------|
| Cap 6 Gate-B | `data/eval/accuracy-cap-derisk/cap6-report.json` @ `9f64c28` | PASS 6/944 = 0.64%, 0 exceptions |
| Cap 8 equivalence | `data/eval/accuracy-cap-derisk/cap8-report.json` | Same numbers; cap 8 rejected on latency margin |
| Cap 4 reference | `data/eval/accuracy-gate/gate-b-report.json` | Frozen FAIL 114/881; not recomputed |
| Latency proxy | `data/eval/accuracy-cap-derisk/latency-results.json` `cap6_trace_none` | p95×5 = 865.2 ms (13.5% margin) |
| Expected action delta | `data/eval/accuracy-cap-derisk/cross-cap-diffs.json` `off -> cap6` | 20/944 (known, not a surprise) |

## 3. Production code change

**Single file:** [`showdown_bot/src/showdown_bot/battle/decision.py`](showdown_bot/src/showdown_bot/battle/decision.py)

### 3.1 `_accuracy_mode()`

Replace the current “unset counts as off via `get(..., "")`” pattern with **explicit
default-on when the env key is absent**:

```python
def _accuracy_mode() -> bool:
    if "SHOWDOWN_ACCURACY_MODE" not in os.environ:
        return True
    raw = os.environ["SHOWDOWN_ACCURACY_MODE"].strip().lower()
    return raw not in ("0", "false", "")
```

**Parser matrix (must hold in tests):**

| Env state | Value | Result | Notes |
|-----------|-------|--------|-------|
| absent (unset) | — | **True** | new default-on |
| set | `""` | False | **conscious opt-out** (cleared env var) |
| set | `"0"`, `"false"`, `"False"` | False | explicit opt-out |
| set | `"1"`, `"true"` | True | explicit on |

Empty string is intentionally off — not equivalent to unset. Callers that clear the variable to
`""` get the historical always-hit path without removing the key from the environment block.

**Breaking invariant (intentional):** unset **≠** explicit `"0"` / `""`. The old
`test_unset_and_explicit_off_are_equivalent_post_refactor` must be replaced.

**Opt-out contract:** Any caller that needs the historical always-hit path must set
`SHOWDOWN_ACCURACY_MODE` to `0`, `false`, or `""` — baseline freeze/diff scripts already set
`0` explicitly.

Update the function docstring: default-on when unset; explicit off via `""` / `"0"` / `"false"`.

### 3.2 `_accuracy_branch_cap()`

Change the unset default from `"4"` to `"6"`; invalid int fallback from `4` to `6`:

```python
v = int(os.environ.get("SHOWDOWN_ACCURACY_BRANCH_CAP", "6"))
# ...
return 6  # on ValueError
```

Update docstring: “Default 6, clamped >=1. Only consulted when `_accuracy_mode()` is on.”

### 3.3 Out of scope for code

- `showdown_bot/src/showdown_bot/battle/evaluate.py` — keep `accuracy_mode: bool = False` on
  `evaluate_line` / `_evaluate_line_details` (call-site kwargs, not env defaults).
- `showdown_bot/src/showdown_bot/eval/config_env.py` — no classification changes; both vars stay
  `BEHAVIOR_AFFECTING`.
- Gate / cap-derisk scripts — unchanged (they set env explicitly per run).

## 4. Test plan

### 4.1 Must update

| File | Change |
|------|--------|
| [`showdown_bot/tests/test_config_env.py`](showdown_bot/tests/test_config_env.py) | `test_accuracy_mode_parser_matrix`: `(None, True)` instead of `(None, False)`; keep `("", False)`, `("0", False)`, `("false", False)`. Replace `test_unset_and_explicit_off_are_equivalent_post_refactor` with **`test_unset_defaults_on_explicit_off_stays_off`**: unset → True; `"0"` → False; assert they **differ**. Add **`test_accuracy_branch_cap_defaults_to_six_when_unset`**. |
| [`showdown_bot/tests/test_accuracy_mode_wiring.py`](showdown_bot/tests/test_accuracy_mode_wiring.py) | Rename/replace `test_accuracy_mode_off_by_default_*` → **`test_accuracy_mode_on_by_default_when_unset`**: unset → all recorded calls carry `accuracy_mode=True` and `accuracy_branch_cap=6`. Update `test_accuracy_mode_on_reaches_every_evaluate_line_call` to expect cap **6** when cap env unset. Add **`test_accuracy_mode_explicit_off_reaches_every_evaluate_line_call`**: `SHOWDOWN_ACCURACY_MODE=0` → all calls `accuracy_mode=False`. |

### 4.2 Must add (required coverage)

These three items are the **required** test coverage for the default flip. Do not require that
default-on visibly changes every generic fixture's chosen action or score.

| Test | Purpose |
|------|---------|
| **Parser/wiring (required)** | Covered by §4.1: unset env wires `accuracy_mode=True` and `accuracy_branch_cap=6` through every `evaluate_line` / `_evaluate_line_details` call site exercised by `_choose_best` (existing recorder pattern in `test_accuracy_mode_wiring.py`). |
| **Explicit-off parity (required)** | **`test_explicit_accuracy_off_is_stable`**: with `SHOWDOWN_ACCURACY_MODE=0`, `_choose_best` on `decision_fixture` produces a **stable** `(ja, val)` across repeated calls (same inputs → same outputs). Optionally pin against a small recorded golden tuple captured once at spec time — proves opt-out stays on the always-hit path and does not drift. |
| **Accuracy-sensitive fixture (optional)** | Add a dedicated regression fixture **only if** a small, reproducible accuracy-branching board is identified during implementation (e.g. a test-local state with sub-100% moves where off vs on is known to diverge). If no such fixture is added, **do not** assert `unset != explicit_off` on `decision_fixture` — default-on is validated by wiring tests, not by forcing a decision diff on every board. |

### 4.3 Must **not** change (unless red)

| File | Reason |
|------|--------|
| `showdown_bot/tests/test_evaluate.py` `test_evaluate_line_accuracy_mode_off_is_byte_identical_to_default` | Tests **API** default `accuracy_mode=False`, not env parser. |
| `showdown_bot/tests/eval/test_accuracy_baseline.py` | Freeze helper passes `accuracy_mode` explicitly to chooser stub. |
| Gate / cap-derisk / replay tests | Set `SHOWDOWN_ACCURACY_MODE=1` explicitly. |

### 4.4 Regression gate

From `showdown_bot/`:

```bash
PYTHONPATH="$(pwd)/src" python -m pytest \
  tests/test_config_env.py \
  tests/test_accuracy_mode_wiring.py \
  tests/test_evaluate.py \
  tests/eval/test_accuracy_gate_b.py \
  tests/eval/test_candidate_identity_replay.py \
  -q
```

Then full suite:

```bash
PYTHONPATH="$(pwd)/src" python -m pytest -q
```

Optional manual sanity (not blocking unless regressions):

```bash
PYTHONPATH="$(pwd)/src" SHOWDOWN_ACCURACY_MODE=0 python scripts/run_accuracy_baseline_diff.py
```

(Confirms explicit-off path still diffs cleanly against frozen baseline — script sets mode off itself.)

## 5. Documentation updates (after code + tests green)

**Only after** the regression gate passes **and** user/Codex review approves implementation:

1. [`docs/ROADMAP.md`](docs/ROADMAP.md) — P0 accuracy table row: `SHOWDOWN_ACCURACY_MODE`
   **default-on (cap 6)**; link spec + decision note; remove “default-off” language in that row.
2. [`reports/2026-07-14-accuracy-default-on-decision-note.md`](reports/2026-07-14-accuracy-default-on-decision-note.md) — add **Implementation** section: commit hash, date, “checklist item 5 complete”.
3. Do **not** edit frozen gate/cap measurement reports except a one-line cross-reference if needed.

Suggested commits (separate, like prior work):

1. `feat(accuracy): default-on mode and branch cap 6` — code + tests
2. `docs(accuracy): record default-on implementation` — ROADMAP + decision note status

## 6. Implementation tasks (ordered)

- [ ] **Task 0:** User/Codex review of this spec → explicit implementation approval.
- [ ] **Task 1:** Update `_accuracy_mode()` and `_accuracy_branch_cap()` in `decision.py` + docstrings.
- [ ] **Task 2:** Update parser/wiring tests (`test_config_env.py`, `test_accuracy_mode_wiring.py`).
- [ ] **Task 3:** Add explicit-off stability/parity test; optional accuracy-sensitive fixture only if identified.
- [ ] **Task 4:** Run focused pytest, then full suite; fix any unexpected reds (grep for `off.by.default`, `unset.*False`, `branch_cap.*4` in tests).
- [ ] **Task 5:** Update ROADMAP + decision note (docs-only commit).
- [ ] **Task 6:** User review; **then** schedule strength/dev-panel slice (out of scope here).

## 7. Risk notes

| Risk | Mitigation |
|------|------------|
| Callers assumed unset = off | Document opt-out; baseline scripts already set `MODE=0`. |
| `config_hash` changes for unset-env runs | Expected behavior change; tests that pin hash must pass explicit env dicts (existing pattern in `test_config_env.py`). |
| Gauntlet/live bot latency | Accepted per decision note (`cap6_trace_none` margin); no new sweep in this slice. |
| 20/944 action changes vs accuracy-off | Pre-measured; not a regression — do not treat as failure. |
| Generic fixture may not show off/on diff | Wiring tests prove default-on is active; do not require `!=` on every board. |

## 8. Success criteria

1. Unset env → accuracy on, branch cap 6, wired through all `evaluate_line` call sites in `_choose_best`.
2. `SHOWDOWN_ACCURACY_MODE` in `{0, false, ""}` → accuracy off; explicit-off path stable on regression fixture(s).
3. Full pytest green.
4. No edits under `data/eval/accuracy-gate/` or refreshed cap JSON artifacts.
5. Docs updated only after (3) and implementation approval.

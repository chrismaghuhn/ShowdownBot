# Phase 3 Slice 1a: Reranker data contract + teacher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frozen training-data contract (schema + JSONL) and the fixed-horizon counterfactual teacher (return + within-decision labels), as pure units testable with fakes.

**Architecture:** A new `learning/` package. `schema.py` defines the feature columns / metadata / label keys + a `Row` and JSONL (de)serialization. `teacher.py` computes the counterfactual return over injectable rollout primitives (`decide`, `resolve`, `leaf`) — no double-count, H=0 reduces to one-ply — and the within-decision normalization + dual (heuristic/teacher) labels. The real feature extraction + self-play export are Plan 1b.

**Tech Stack:** Python stdlib + dataclasses + pytest. Spec: `docs/projects/learning/specs/2026-06-29-ml-reranker-data-slice-design.md`. Run tests from `showdown_bot/`. No Node/calc dependency in this plan (all rollout primitives are injected).

---

## File Structure
- `src/showdown_bot/learning/__init__.py` — empty package marker.
- `src/showdown_bot/learning/schema.py` — feature columns (4 groups), metadata + label keys, `Row`, `validate_row`, `to_jsonl_line`/`from_jsonl_line`.
- `src/showdown_bot/learning/teacher.py` — `RolloutConfig`, `counterfactual_value`, `label_decision`.
- Tests: `tests/test_ml_schema.py`, `tests/test_teacher_rollout.py`.

---

## Completed work — DO NOT reimplement

These tasks are committed and green (full suite 254). They are described by their
**actual committed guarantees**, not a code snippet — read the commits, do not
rebuild from this section.

### Task 1: `schema.py` — frozen contract + JSONL — ✅ DONE (commits `aa96dbf`, `3ec740b`)
- [x] `FEATURE_COLUMNS` (4 groups) + `METADATA_KEYS` + `LABEL_KEYS`; `Row(features, metadata, label)` is **frozen**.
- [x] `validate_row` enforces **exact** key sets for features / metadata / label — rejects BOTH missing and unknown keys.
- [x] `to_jsonl_line` **validates before serializing**, uses `separators=(",", ":")` and **no `default=str`** (non-JSON types crash, never silently stringify); `from_jsonl_line` is the inverse.
- [x] `heuristic_rank` is **LABEL-only** (the heuristic *scores/gaps* are the features); `format_id` is the **only** intentional feature/metadata overlap.
- [x] `tests/test_ml_schema.py` (10): roundtrip, outcome-fields-are-metadata, unknown/missing feature·metadata·label keys, unique columns, section-overlap rule, validate-on-write.

### Task 2: `teacher.py` counterfactual return — ✅ DONE (commits `3d7341a`, `ad8700b`)
- [x] `RolloutConfig(H, gamma, top_k, use_leaf)` with `__post_init__` validation: `H >= 0`, `gamma in (0, 1]`, `top_k > 0`.
- [x] `counterfactual_value(start_state, candidate, responses, *, decide, resolve, leaf, cfg)` — incremental transition rewards + ONE bootstrap leaf at `gamma^(H+1)` (no double-count); `H=0` with `use_leaf=False` equals the one-ply aggregate; weighted mean over the response set; rejects empty responses / weights not summing to 1 / negative weights.
- [x] `tests/test_teacher_rollout.py` (7): H=0==one-ply, no-double-count formula, response-weights-applied, empty/sum/negative rejection, RolloutConfig validation.

---

## Task 3: `teacher.py` — within-decision normalization + dual labels  (OPEN)

The only remaining task in this plan. Appends `label_decision` (+ a `_ranks`
helper) to the existing `teacher.py`. All labels are computed **within one
decision**; the teacher's tie-break for "best" must match `_ranks` exactly so
`teacher_rank == 0` and `teacher_best` never disagree.

**Files:**
- Modify: `src/showdown_bot/learning/teacher.py`
- Test: `tests/test_teacher_rollout.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_teacher_rollout.py`)

```python
def test_label_decision_normalizes_and_flags_disagreement():
    from showdown_bot.learning.teacher import label_decision
    teacher_values = {"A": 1.0, "B": 3.0, "C": 2.0}   # teacher prefers B
    heuristic_values = {"A": 5.0, "B": 1.0, "C": 2.0}  # heuristic prefers A
    out = label_decision(teacher_values, heuristic_values, heuristic_choice_id="A")

    assert out["B"]["teacher_best"] is True
    assert out["A"]["teacher_best"] is False
    assert out["A"]["chosen_by_current_heuristic"] is True
    assert out["B"]["chosen_by_current_heuristic"] is False
    # within-decision normalization: value - mean(2.0)
    assert abs(out["B"]["counterfactual_value_normalized_within_decision"] - 1.0) < 1e-9
    assert abs(out["A"]["value_gap_to_best"] - (1.0 - 3.0)) < 1e-9
    # ranks (0 = best) differ: teacher ranks B first, heuristic ranks A first
    assert out["B"]["teacher_rank"] == 0
    assert out["A"]["heuristic_rank"] == 0
    assert out["A"]["teacher_rank"] != 0


def test_label_decision_tie_break_is_consistent():
    # tied teacher values: teacher_rank==0 and teacher_best MUST point at the same id
    from showdown_bot.learning.teacher import label_decision
    out = label_decision({"A": 1.0, "B": 1.0}, {"A": 0.0, "B": 0.0}, "A")
    assert out["A"]["teacher_rank"] == 0
    assert out["A"]["teacher_best"] is True
    assert out["B"]["teacher_best"] is False


def test_label_decision_requires_same_candidate_sets():
    from showdown_bot.learning.teacher import label_decision
    with pytest.raises(ValueError, match="same candidates"):
        label_decision({"A": 1.0}, {"A": 1.0, "B": 2.0}, "A")


def test_label_decision_requires_choice_in_candidates():
    from showdown_bot.learning.teacher import label_decision
    with pytest.raises(ValueError, match="must be one of"):
        label_decision({"A": 1.0, "B": 2.0}, {"A": 1.0, "B": 2.0}, "Z")


def test_label_decision_rejects_empty_values():
    from showdown_bot.learning.teacher import label_decision
    with pytest.raises(ValueError, match="empty"):
        label_decision({}, {}, "A")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_teacher_rollout.py -q`
Expected: FAIL with `ImportError: cannot import name 'label_decision'`

- [ ] **Step 3: Implement `label_decision`** (append to `src/showdown_bot/learning/teacher.py`)

```python
def _ranks(values: dict) -> dict:
    """0 = best (highest value). Ties broken by candidate id for determinism."""
    order = sorted(values, key=lambda c: (-values[c], str(c)))
    return {c: i for i, c in enumerate(order)}


def label_decision(teacher_values: dict, heuristic_values: dict, heuristic_choice_id) -> dict:
    """Per-candidate labels, all within-decision. ``teacher_values`` and
    ``heuristic_values`` map candidate_id -> value over the SAME candidate set."""
    if not teacher_values:
        raise ValueError("teacher_values must not be empty")
    if set(teacher_values) != set(heuristic_values):
        raise ValueError("teacher and heuristic values must cover the same candidates")
    if heuristic_choice_id not in teacher_values:
        raise ValueError("heuristic_choice_id must be one of the candidates")
    mean = sum(teacher_values.values()) / len(teacher_values)
    best = max(teacher_values.values())
    t_rank = _ranks(teacher_values)
    h_rank = _ranks(heuristic_values)
    best_id = min(t_rank, key=t_rank.get)   # rank 0 — SAME tie-break as _ranks (no inconsistency)
    return {
        cid: {
            "counterfactual_value_raw": v,
            "counterfactual_value_normalized_within_decision": v - mean,
            "value_gap_to_best": v - best,
            "counterfactual_rank": t_rank[cid],
            "teacher_rank": t_rank[cid],
            "heuristic_rank": h_rank[cid],
            "teacher_best": cid == best_id,
            "chosen_by_current_heuristic": cid == heuristic_choice_id,
        }
        for cid, v in teacher_values.items()
    }
```

- [ ] **Step 4: Run tests then the full suite**

Run: `cd showdown_bot && python -m pytest tests/test_teacher_rollout.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (suite was 254; expect 259 with the 5 new tests).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/learning/teacher.py showdown_bot/tests/test_teacher_rollout.py
git commit -m "feat(learning): within-decision normalization + dual (heuristic/teacher) labels"
```

---

## Self-Review notes
- **Spec coverage (this plan = contract + teacher):** done — frozen 4-group columns + metadata (incl. versioning) + label keys + JSONL + leakage guard (T1); counterfactual return with no-double-count + H=0==one-ply + weighted-mean-over-R + config/weight validation (T2); within-decision normalization + dual labels + consistent tie-break + guards (T3). **Deferred to Plan 1b:** real feature extraction from the decision (the 4 groups), the self-play export driver with decision sampling, the opponent **limited-view** rollout adapter, `git_sha`/`team_hash`/`config_hash` population, and end-to-end determinism/schema-version dataset tests.
- **Type consistency:** `Row(features, metadata, label)`, `validate_row`, `to_jsonl_line`/`from_jsonl_line`, `RolloutConfig(H, gamma, top_k, use_leaf)`, `counterfactual_value(start_state, candidate, responses, *, decide, resolve, leaf, cfg)`, `label_decision(teacher_values, heuristic_values, heuristic_choice_id)` — consistent across tasks.
- **No stale snippets:** Tasks 1–2 are described by committed guarantees only (no re-buildable code); Task 3 carries the single source of truth for `label_decision`.
- **No Node/calc dependency** — all rollout primitives injected; Plan 1b supplies the real adapters.

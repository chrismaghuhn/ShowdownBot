# Phase 3 Slice 1a: Reranker data contract + teacher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frozen training-data contract (schema + JSONL) and the fixed-horizon counterfactual teacher (return + within-decision labels), as pure units testable with fakes.

**Architecture:** A new `learning/` package. `schema.py` defines the feature columns / metadata / label keys + a `Row` and JSONL (de)serialization. `teacher.py` computes the counterfactual return over injectable rollout primitives (`decide`, `resolve`, `leaf`) — no double-count, H=0 reduces to one-ply — and the within-decision normalization + dual (heuristic/teacher) labels. The real feature extraction + self-play export are Plan 1b.

**Tech Stack:** Python stdlib + dataclasses + pytest. Spec: `docs/superpowers/specs/2026-06-29-ml-reranker-data-slice-design.md`. Run tests from `showdown_bot/`. No Node/calc dependency in this plan (all rollout primitives are injected).

---

## File Structure
- `src/showdown_bot/learning/__init__.py` — empty package marker.
- `src/showdown_bot/learning/schema.py` — feature columns (4 groups), metadata + label keys, `Row`, `validate_row`, `to_jsonl_line`/`from_jsonl_line`.
- `src/showdown_bot/learning/teacher.py` — `RolloutConfig`, `counterfactual_value`, `label_decision`.
- Tests: `tests/test_ml_schema.py`, `tests/test_teacher_rollout.py`.

---

## Task 1: `schema.py` — frozen contract + JSONL

**Files:**
- Create: `src/showdown_bot/learning/__init__.py`, `src/showdown_bot/learning/schema.py`
- Test: `tests/test_ml_schema.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ml_schema.py
import pytest

from showdown_bot.learning.schema import (
    FEATURE_COLUMNS, METADATA_KEYS, LABEL_KEYS, Row,
    validate_row, to_jsonl_line, from_jsonl_line,
)


def _row():
    features = {c: 0 for c in FEATURE_COLUMNS}
    metadata = {k: "x" for k in METADATA_KEYS}
    label = {k: 0 for k in LABEL_KEYS}
    return Row(features=features, metadata=metadata, label=label)


def test_outcome_fields_are_metadata_not_features():
    # the leakage guard: outcome/future fields must NOT be feature columns
    for forbidden in ("game_outcome", "winner", "final_turn", "teacher_trace"):
        assert forbidden not in FEATURE_COLUMNS
        assert forbidden in METADATA_KEYS


def test_jsonl_roundtrip_is_identity():
    row = _row()
    back = from_jsonl_line(to_jsonl_line(row))
    assert back.features == row.features
    assert back.metadata == row.metadata
    assert back.label == row.label


def test_validate_row_rejects_unknown_feature_key():
    row = _row()
    row.features["not_a_real_feature"] = 1
    with pytest.raises(ValueError, match="unknown feature"):
        validate_row(row)


def test_validate_row_requires_versioning_metadata():
    row = _row()
    del row.metadata["schema_version"]
    with pytest.raises(ValueError, match="missing metadata"):
        validate_row(row)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_ml_schema.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'showdown_bot.learning'`

- [ ] **Step 3: Create the package marker** — `src/showdown_bot/learning/__init__.py` with a single line:

```python
"""Phase 3 learning: training-data contract + counterfactual teacher."""
```

- [ ] **Step 4: Create `src/showdown_bot/learning/schema.py`**

```python
"""Frozen training-data contract for the reranker (Phase 3, slice 1).

features = ONLY decision-time info. metadata = outcome/versioning/debug (never a
feature). label = counterfactual teacher value/ranks. One JSONL row per
(decision x candidate); group by metadata.decision_id / metadata.game_id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

# --- feature columns, 4 frozen groups (decision-time info only) -------------
CONTEXT_FEATURES = [
    "game_mode", "turn_number", "endgame_flag", "our_alive_count", "opp_alive_count",
    "our_total_hp_frac", "opp_total_hp_frac", "field_weather", "field_terrain",
    "tailwind_ours", "tailwind_opp", "trick_room_active", "screens_ours",
    "screens_opp", "speed_control_state", "format_id", "mirror_flag",
]
ACTION_FEATURES = [
    "slot1_action_type", "slot2_action_type", "slot1_move_id", "slot2_move_id",
    "slot1_move_type", "slot2_move_type", "slot1_move_category", "slot2_move_category",
    "slot1_target_kind", "slot2_target_kind", "slot1_target_slot", "slot2_target_slot",
    "slot1_priority", "slot2_priority", "slot1_is_damaging", "slot2_is_damaging",
    "slot1_is_protect", "slot2_is_protect", "slot1_is_switch", "slot2_is_switch",
    "tera_used", "slot1_actor_species_id", "slot2_actor_species_id",
    "slot1_switch_target_species_id", "slot2_switch_target_species_id",
    "slot1_target_species_id_if_known", "slot2_target_species_id_if_known",
]
HEURISTIC_FEATURES = [
    "heuristic_aggregate_score", "heuristic_rank", "score_gap_to_top",
    "score_gap_to_second", "score_min_vs_opp", "score_mean_vs_opp",
    "score_var_vs_opp", "score_worst_response", "predicted_outgoing_damage",
    "predicted_incoming_damage", "out_in_ratio", "predicted_kos_for",
    "predicted_kos_against", "ko_secured_count", "ko_threatened_count",
    "survives_for_sure_count", "protect_stall_penalty", "partner_abandon_penalty",
    "fakeout_invalid_penalty", "action_economy_score",
]
TEMPO_FEATURES = [
    "we_outspeed_count", "they_outspeed_count", "speed_tie_count",
    "our_fastest_active_speed", "opp_fastest_active_speed", "must_react_reason_flags",
    "protect_prior_target1", "protect_prior_target2", "response_count",
    "opponent_response_entropy", "value_range_across_opp_responses",
]
FEATURE_COLUMNS = CONTEXT_FEATURES + ACTION_FEATURES + HEURISTIC_FEATURES + TEMPO_FEATURES

METADATA_KEYS = [
    "game_id", "decision_id", "candidate_index", "format_id", "game_outcome",
    "final_turn", "winner", "teacher_trace", "schema_version",
    "feature_extractor_version", "teacher_version", "git_sha", "team_hash",
    "config_hash", "teacher_config",
]
LABEL_KEYS = [
    "counterfactual_value_raw", "counterfactual_value_normalized_within_decision",
    "value_gap_to_best", "counterfactual_rank", "teacher_rank", "teacher_best",
    "chosen_by_current_heuristic", "heuristic_rank",
]

_FEATURE_SET = frozenset(FEATURE_COLUMNS)
_REQUIRED_META = frozenset({"schema_version", "decision_id", "game_id"})


@dataclass
class Row:
    features: dict
    metadata: dict
    label: dict = field(default_factory=dict)


def validate_row(row: Row) -> None:
    unknown = set(row.features) - _FEATURE_SET
    if unknown:
        raise ValueError(f"unknown feature key(s): {sorted(unknown)}")
    missing = _REQUIRED_META - set(row.metadata)
    if missing:
        raise ValueError(f"missing metadata: {sorted(missing)}")


def to_jsonl_line(row: Row) -> str:
    return json.dumps(
        {"features": row.features, "metadata": row.metadata, "label": row.label},
        sort_keys=True, default=str,
    )


def from_jsonl_line(line: str) -> Row:
    d = json.loads(line)
    return Row(features=d["features"], metadata=d["metadata"], label=d.get("label", {}))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/test_ml_schema.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (suite was 237; expect 241).

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/learning/__init__.py showdown_bot/src/showdown_bot/learning/schema.py showdown_bot/tests/test_ml_schema.py
git commit -m "feat(learning): reranker data contract (frozen columns, metadata, JSONL)"
```

---

## Task 2: `teacher.py` — counterfactual return (no double-count, H=0 sanity)

The teacher is a PURE function over injectable rollout primitives so it tests
without Node/calc:
- `decide(state, side) -> action` — the heuristic move for a side in a follow-up turn.
- `resolve(state, our_action, opp_action) -> (next_state, transition_reward)` — one
  turn; `transition_reward` is the INCREMENTAL `score_outcome` of that turn.
- `leaf(state) -> float` — the static one-ply board value at the horizon.

**Files:**
- Create: `src/showdown_bot/learning/teacher.py`
- Test: `tests/test_teacher_rollout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_teacher_rollout.py
from showdown_bot.learning.teacher import RolloutConfig, counterfactual_value


def _fakes(rewards_by_turn, leaf_value):
    """resolve/decide/leaf fakes. State is just an int turn counter; each turn's
    transition_reward is rewards_by_turn[turn]. decide returns a dummy action."""
    def decide(state, side):
        return ("dummy", side)

    def resolve(state, our_action, opp_action):
        turn = state
        return turn + 1, rewards_by_turn[turn]

    def leaf(state):
        return leaf_value

    return decide, resolve, leaf


def test_h0_no_leaf_equals_one_ply_aggregate():
    # two responses, weights 0.25/0.75; H=0, leaf off -> weighted mean of turn-0 reward
    decide, resolve, leaf = _fakes({0: 2.0}, leaf_value=99.0)
    cfg = RolloutConfig(H=0, gamma=0.75, use_leaf=False)
    v = counterfactual_value(
        start_state=0, candidate="c", responses=[("r1", 0.25), ("r2", 0.75)],
        decide=decide, resolve=resolve, leaf=leaf, cfg=cfg,
    )
    assert v == 2.0  # one-ply aggregate, no leaf, no follow-ups


def test_return_formula_no_double_count():
    # H=2 follow-ups; rewards r0=1, r1=2, r2=3; leaf=10; gamma=0.5
    # v = 1 + 0.5*2 + 0.25*3 + 0.5^3 * 10 = 1 + 1 + 0.75 + 1.25 = 4.0
    decide, resolve, leaf = _fakes({0: 1.0, 1: 2.0, 2: 3.0}, leaf_value=10.0)
    cfg = RolloutConfig(H=2, gamma=0.5, use_leaf=True)
    v = counterfactual_value(
        start_state=0, candidate="c", responses=[("r", 1.0)],
        decide=decide, resolve=resolve, leaf=leaf, cfg=cfg,
    )
    assert abs(v - 4.0) < 1e-9


def test_weighted_mean_over_responses():
    decide, resolve, leaf = _fakes({0: 4.0}, leaf_value=0.0)
    cfg = RolloutConfig(H=0, gamma=0.75, use_leaf=False)
    v = counterfactual_value(
        start_state=0, candidate="c", responses=[("r1", 0.5), ("r2", 0.5)],
        decide=decide, resolve=resolve, leaf=leaf, cfg=cfg,
    )
    assert v == 4.0  # both responses give 4.0 -> weighted mean 4.0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/test_teacher_rollout.py -q`
Expected: FAIL with `ImportError: cannot import name 'counterfactual_value'`

- [ ] **Step 3: Implement `src/showdown_bot/learning/teacher.py`**

```python
"""Fixed-horizon counterfactual teacher (Phase 3, slice 1).

Return = incremental transition rewards + ONE bootstrap leaf, never evaluating the
same state twice. H = follow-up turns after the candidate turn (1 + H transitions).
"""

from __future__ import annotations

from dataclasses import dataclass

US = "us"
THEM = "them"


@dataclass
class RolloutConfig:
    H: int = 4          # heuristic follow-up turns after the fixed candidate turn
    gamma: float = 0.75
    top_k: int = 6
    use_leaf: bool = True


def _rollout_one(start_state, candidate, first_opp, *, decide, resolve, leaf, cfg) -> float:
    # transition 0: the fixed candidate + this opponent response (gamma^0 = 1)
    state, reward = resolve(start_state, candidate, first_opp)
    v = reward
    for t in range(1, cfg.H + 1):  # H follow-up turns, heuristic both sides
        state, reward = resolve(state, decide(state, US), decide(state, THEM))
        v += (cfg.gamma ** t) * reward
    if cfg.use_leaf:
        v += (cfg.gamma ** (cfg.H + 1)) * leaf(state)  # bootstrap, strictly after last transition
    return v


def counterfactual_value(start_state, candidate, responses, *, decide, resolve, leaf, cfg) -> float:
    """Weighted mean over the (candidate-independent) opponent response set.
    ``responses`` is a list of (opponent_action, weight) with weights summing to 1."""
    return sum(
        w * _rollout_one(start_state, candidate, opp, decide=decide, resolve=resolve, leaf=leaf, cfg=cfg)
        for opp, w in responses
    )
```

- [ ] **Step 4: Run tests then the full suite**

Run: `cd showdown_bot && python -m pytest tests/test_teacher_rollout.py -q` then `cd showdown_bot && python -m pytest -q`
Expected: PASS (suite expect 244).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/learning/teacher.py showdown_bot/tests/test_teacher_rollout.py
git commit -m "feat(learning): counterfactual teacher return (no double-count, H=0 sanity)"
```

---

## Task 3: `teacher.py` — within-decision normalization + dual labels

**Files:**
- Modify: `src/showdown_bot/learning/teacher.py`
- Test: `tests/test_teacher_rollout.py`

- [ ] **Step 1: Write the failing tests** (append)

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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/test_teacher_rollout.py::test_label_decision_normalizes_and_flags_disagreement -q`
Expected: FAIL with `ImportError: cannot import name 'label_decision'`

- [ ] **Step 3: Implement `label_decision`** (append to `teacher.py`)

```python
def _ranks(values: dict) -> dict:
    """0 = best (highest value). Ties broken by candidate id for determinism."""
    order = sorted(values, key=lambda c: (-values[c], str(c)))
    return {c: i for i, c in enumerate(order)}


def label_decision(teacher_values: dict, heuristic_values: dict, heuristic_choice_id) -> dict:
    """Per-candidate labels, all within-decision. ``teacher_values`` and
    ``heuristic_values`` map candidate_id -> value over the SAME candidate set."""
    mean = sum(teacher_values.values()) / len(teacher_values)
    best = max(teacher_values.values())
    best_id = max(teacher_values, key=lambda c: (teacher_values[c], str(c)))
    t_rank = _ranks(teacher_values)
    h_rank = _ranks(heuristic_values)
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
Expected: PASS (suite expect 245).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/learning/teacher.py showdown_bot/tests/test_teacher_rollout.py
git commit -m "feat(learning): within-decision normalization + dual (heuristic/teacher) labels"
```

---

## Self-Review notes
- **Spec coverage (this plan = contract + teacher):** frozen 4-group columns + metadata (incl. versioning) + label keys + JSONL + feature-availability guard (T1); counterfactual return with no-double-count + H=0==one-ply + weighted-mean-over-R (T2); within-decision normalization + dual labels + disagreement (T3). **Deferred to Plan 1b:** real feature extraction from the decision (the 4 groups), the self-play export driver with decision sampling, the opponent **limited-view** rollout adapter, `git_sha`/`team_hash`/`config_hash` population, and end-to-end determinism/schema-version dataset tests.
- **Type consistency:** `Row(features, metadata, label)`, `validate_row`, `to_jsonl_line`/`from_jsonl_line`, `RolloutConfig(H, gamma, top_k, use_leaf)`, `counterfactual_value(start_state, candidate, responses, *, decide, resolve, leaf, cfg)`, `label_decision(teacher_values, heuristic_values, heuristic_choice_id)` — consistent across tasks.
- **No Node/calc dependency** — all rollout primitives injected; Plan 1b supplies the real adapters.

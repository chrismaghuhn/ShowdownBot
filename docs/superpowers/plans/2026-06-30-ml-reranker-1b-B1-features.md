# Phase 3 Slice 1b-B1: `learning/features.py` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Map a populated `DecisionTrace` + state/request/context to one schema-valid
`Row` per Top-K candidate — all 4 feature groups fully populated, no nulls, no leak,
no eval-recomputation.

**Architecture:** Pure `learning/features.py`: a `FeatureContext` DTO (provenance +
read-only tools), central sentinel constants, and `extract_features(trace, state,
request, context) -> list[Row]`. Group-3 (eval) reads ONLY from the trace
(`CandidateTrace` / `OutcomeBreakdown` / `CandidateModelFeatures`). Export driver +
client hook are Plans 1b-B2 / 1b-B3.

**Tech Stack:** Python stdlib + `statistics`. Spec:
`docs/superpowers/specs/2026-06-30-ml-reranker-1b-feature-extraction-export-design.md`.
Reads `learning/schema.py` (`FEATURE_COLUMNS`, `Row`, `validate_row`). Run tests from
`showdown_bot/`. No Node/calc (the trace already holds every eval value).

---

## File Structure
- Create: `src/showdown_bot/learning/features.py` — `FeatureContext`, sentinel
  constants, `extract_features`, four private group builders.
- Test: `tests/test_features.py`.

## Sentinels (central, frozen)
```python
SENTINEL_CAT_NONE = "__none__"        # not applicable (e.g. move field on a switch)
SENTINEL_CAT_UNKNOWN = "__unknown__"  # applicable but not revealed (e.g. opp species)
SENTINEL_CAT_UNTRACKED = "__untracked__"  # the state does not model it (screens)
SENTINEL_NUM = -1                     # optional numeric slot/target
SENTINEL_BOOL = False                 # optional bool
```

## FeatureContext
```python
@dataclass
class FeatureContext:
    run_id: str; game_id: str; decision_id: str
    decision_local_index: int; turn_number: int; our_side: str
    format_id: str; team_hash: str; config_hash: str
    git_sha: str; dirty_flag: bool
    teacher_config: dict; sampling_policy: str
    mirror_flag: bool
    dex: object | None = None         # to_id(species) + species lookups (G2)
    move_meta: object | None = None   # move_id -> MoveMeta (G2)
    speed_oracle: object | None = None  # effective speeds (G4)
    priors: object | None = None      # protect priors (G4)
```

## Exhaustive column → source mapping (the contract)

`our_side`/`opp_side` from context. Slot `1↔a`, `2↔b`. "candidate" = one
`CandidateTrace`. Decision-level values are computed once and copied to every row.

**Group 1 — decision context (identical for all candidates of a decision):**
| column | source |
|---|---|
| `game_mode` | `trace.game_mode` |
| `turn_number` | `context.turn_number` (== `state.turn`) |
| `endgame_flag` | `our_alive_count <= 1` |
| `our_alive_count` | count `request.side.pokemon` with `"fnt" not in condition` (authoritative) |
| `opp_alive_count` | `4 - opp_faints_observed` (revealed estimate: count non-fainted opp mons known in `state.side(opp)`); document the asymmetry |
| `our_total_hp_frac` | sum `hp_fraction` over our active living mons |
| `opp_total_hp_frac` | sum `hp_fraction` over opp active living mons |
| `field_weather` | `state.field.weather or SENTINEL_CAT_NONE` |
| `field_terrain` | `state.field.terrain or SENTINEL_CAT_NONE` |
| `tailwind_ours` | `state.field.tailwind[our_side]` |
| `tailwind_opp` | `state.field.tailwind[opp_side]` |
| `trick_room_active` | `state.field.trick_room` |
| `screens_ours` | `SENTINEL_CAT_UNTRACKED` (FieldState has no screens) |
| `screens_opp` | `SENTINEL_CAT_UNTRACKED` |
| `speed_control_state` | derive from tailwind/TR: `none / tailwind_ours / tailwind_opp / tailwind_both / trick_room / mixed` |
| `format_id` | `context.format_id` |
| `mirror_flag` | `context.mirror_flag` |

**Group 2 — candidate action (per candidate, per slot N∈{1,2} ↔ `trace`'s `joint_action.slot0/slot1` = `SlotAction`):**
| column | source |
|---|---|
| `slotN_action_type` | `SlotAction.kind` (`move`/`switch`/`pass`) |
| `slotN_move_id` | move: `request.active[N-1].moves[move_index-1].id`; else `SENTINEL_CAT_NONE` |
| `slotN_move_type` | move: `move_meta[move_id].move_type or SENTINEL_CAT_NONE`; else `SENTINEL_CAT_NONE` |
| `slotN_move_category` | move: `move_meta[move_id].category`; else `SENTINEL_CAT_NONE` |
| `slotN_priority` | move: `move_meta[move_id].priority`; else `0` |
| `slotN_is_damaging` | move: `move_meta[move_id].is_damaging`; else `False` |
| `slotN_is_protect` | move: `is_protect(move_meta[move_id])` (via `flags`/`effect_classes`/known protect-move set — pin against the codebase's protect check); else `False` |
| `slotN_target_kind` | from `SlotAction.target`: `1/2→foe`, `-1→ally`, `-2→self`, `None→SENTINEL_CAT_NONE` |
| `slotN_target_slot` | `SlotAction.target if not None else SENTINEL_NUM` |
| `slotN_is_switch` | `SlotAction.kind == "switch"` |
| `tera_used` | `joint_action.slot0.terastallize or joint_action.slot1.terastallize` |
| `slotN_actor_species_id` | `dex.to_id(state.side(our_side)[slot_letter].species)` (slot N→a/b); `SENTINEL_CAT_NONE` if empty |
| `slotN_switch_target_species_id` | switch: `dex.to_id(species_of(request, SlotAction.target_ident))`; else `SENTINEL_CAT_NONE` |
| `slotN_target_species_id_if_known` | move targeting a concrete slot whose species is known: `dex.to_id(species)`; else `SENTINEL_CAT_UNKNOWN` |

**Group 3 — eval/heuristic (per candidate, ONLY from the trace — never recompute):**
| column | source |
|---|---|
| `heuristic_aggregate_score` | `candidate.aggregate_score` |
| `score_gap_to_top` | `candidate.aggregate_score - trace.candidates[0].aggregate_score` |
| `score_gap_to_second` | `candidate.aggregate_score - trace.candidates[1].aggregate_score` (0.0 if <2 candidates) |
| `score_min_vs_opp` | `min(candidate.score_vector)` |
| `score_mean_vs_opp` | `mean(candidate.score_vector)` |
| `score_var_vs_opp` | `pvariance(candidate.score_vector)` (0.0 if len<2) |
| `score_worst_response` | `min(candidate.score_vector)` (v1: == score_min_vs_opp; documented) |
| `predicted_outgoing_damage` | `candidate.aggregate_breakdown.predicted_outgoing_damage` |
| `predicted_incoming_damage` | `candidate.aggregate_breakdown.predicted_incoming_damage` |
| `out_in_ratio` | `outgoing / (incoming + 1e-6)` (both from the breakdown) |
| `predicted_kos_for` | `candidate.aggregate_breakdown.my_kos` |
| `predicted_kos_against` | `candidate.aggregate_breakdown.my_faints` |
| `ko_secured_count` | `candidate.model_features.ko_secured_count` |
| `ko_threatened_count` | `candidate.model_features.ko_threatened_count` |
| `survives_for_sure_count` | `candidate.model_features.survives_for_sure_count` |
| `protect_stall_penalty` | `candidate.aggregate_breakdown.protect_stall_penalty` |
| `partner_abandon_penalty` | `candidate.aggregate_breakdown.partner_abandon_penalty` |
| `fakeout_invalid_penalty` | `0.0` (v1 sentinel) |
| `action_economy_score` | `0.0` (v1 sentinel) |

**Group 4 — tempo/risk:**
| column | source |
|---|---|
| `we_outspeed_count` | # opp active mons our fastest active mon outspeeds (`speed_oracle.effective_speed` on state); decision-level |
| `they_outspeed_count` | # our active mons opp fastest active mon outspeeds; decision-level |
| `speed_tie_count` | # our×opp active pairs with equal effective speed; decision-level |
| `our_fastest_active_speed` | max our active effective speed |
| `opp_fastest_active_speed` | max opp active effective speed |
| `must_react_reason_flags` | v1 coarse: `int(trace.game_mode == "MUST_REACT")` (granular reasons not exposed by `compute_game_mode`; documented) |
| `protect_prior_target1` | `context.priors` protect prior for opp slot a, else `0.0` |
| `protect_prior_target2` | `context.priors` protect prior for opp slot b, else `0.0` |
| `response_count` | `len(trace.opponent_responses)` |
| `opponent_response_entropy` | Shannon entropy of `trace.opponent_response_weights` (0.0 if empty/degenerate) |
| `value_range_across_opp_responses` | `max(candidate.score_vector) - min(candidate.score_vector)` |

---

## Tasks

### Task 1: scaffolding — FeatureContext, sentinels, gates with sentinel stubs

**Files:** Create `src/showdown_bot/learning/features.py`; Test `tests/test_features.py`.

- [ ] **Step 1: Write the failing gate tests** (the 7 hard gates; they pass once every column is present — even as a stub value)

```python
# tests/test_features.py
import math
import pytest
from showdown_bot.learning.schema import FEATURE_COLUMNS, METADATA_KEYS, LABEL_KEYS, validate_row
from showdown_bot.learning.features import FeatureContext, extract_features
# Build a populated DecisionTrace fixture by reusing tests/test_decision_trace.py's
# decision_fixture: run heuristic_choose_for_request(req, trace=tr, **kw); pass tr in.

def _ctx():
    return FeatureContext(run_id="r", game_id="g", decision_id="d",
        decision_local_index=0, turn_number=1, our_side="p1", format_id="fmt",
        team_hash="t", config_hash="c", git_sha="s", dirty_flag=False,
        teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all", mirror_flag=True,
        dex=..., move_meta=..., speed_oracle=..., priors=...)  # from the fixture

def test_gate_one_row_per_candidate(features_fixture):
    trace, state, req, ctx = features_fixture
    rows = extract_features(trace, state, req, ctx)
    assert len(rows) == len(trace.candidates)

def test_gate_every_feature_column_present_and_non_null(features_fixture):
    trace, state, req, ctx = features_fixture
    for row in extract_features(trace, state, req, ctx):
        assert set(row.features) == set(FEATURE_COLUMNS)   # exactly, no missing/extra
        assert all(v is not None for v in row.features.values())

def test_gate_no_metadata_or_outcome_field_in_features(features_fixture):
    trace, state, req, ctx = features_fixture
    forbidden = set(METADATA_KEYS) | set(LABEL_KEYS) | {"game_outcome", "winner"}
    for row in extract_features(trace, state, req, ctx):
        assert not (set(row.features) & (forbidden - {"format_id"}))  # format_id is the allowed overlap

def test_gate_rows_validate(features_fixture):
    trace, state, req, ctx = features_fixture
    for row in extract_features(trace, state, req, ctx):
        validate_row(row)   # features + metadata + label all exact

def test_gate_group1_identical_across_candidates(features_fixture):
    trace, state, req, ctx = features_fixture
    from showdown_bot.learning.features import CONTEXT_COLUMNS
    rows = extract_features(trace, state, req, ctx)
    for col in CONTEXT_COLUMNS:
        assert len({row.features[col] for row in rows}) == 1
```

- [ ] **Step 2: Run to verify they fail** — `cd showdown_bot && python -m pytest tests/test_features.py -q` → FAIL (`ImportError` / no `extract_features`).

- [ ] **Step 3: Implement the scaffold** — `FeatureContext`, the sentinel constants, `CONTEXT_COLUMNS = list(...)` (re-export the schema's `CONTEXT_FEATURES`), and `extract_features` that builds one `Row` per candidate where **every `FEATURE_COLUMNS` key is set to its sentinel** (`SENTINEL_CAT_NONE` for categoricals, `SENTINEL_NUM` for the `-1` numerics, `0.0`/`0` for scores, `False` for bools), plus `metadata` (from context: all `METADATA_KEYS`, with `candidate_index`) and a stub `label` (all `LABEL_KEYS` = 0, `teacher_version=stub-h0`). The point: the gates pass on stubs first; Tasks 2–4 replace stubs with real values without breaking the gates.

- [ ] **Step 4: Run** — gates green. Full suite. Commit `feat(learning): features.py scaffold + 7 gates (sentinel stubs)`.

### Task 2: Group 1 (decision context) — real values + the speed_control derivation

**Files:** Modify `features.py`; Test `tests/test_features.py`.

- [ ] **Step 1: tests** — `test_g1_weather_terrain_tailwind_trickroom` (set `state.field`, assert mapped values + `field_weather` sentinel when None), `test_g1_speed_control_state` (tailwind/TR combos → the 6 strings), `test_g1_screens_untracked` (== `"__untracked__"`), `test_g1_alive_and_hp` (counts + hp fracs), `test_g1_format_and_mirror_from_context`.
- [ ] **Step 2: fail.** **Step 3:** implement `_group1_context(state, request, trace, context)` per the G1 table; have `extract_features` merge it (identical for all candidates → keeps gate 5 green). **Step 4:** green + suite + commit.

### Task 3: Group 2 (candidate action) — JointAction → request/MoveMeta/dex

**Files:** Modify `features.py`; Test `tests/test_features.py`.

- [ ] **Step 1: tests** — `test_g2_move_slot_resolves_id_type_category_priority` (a move SlotAction → real move_id/type/category/priority/is_damaging from `move_meta`), `test_g2_switch_slot_sentinels_and_species` (switch → move fields `"__none__"`, `switch_target_species_id` resolved), `test_g2_pass_slot_all_sentinels`, `test_g2_target_kind_and_slot` (foe/ally/self/`__none__`, slot int or `-1`), `test_g2_tera_used`, `test_g2_target_species_unknown_sentinel` (opp species not revealed → `"__unknown__"`).
- [ ] **Step 2: fail.** **Step 3:** implement `_group2_action(candidate, request, state, context)` per the G2 table (a per-slot helper over `candidate.joint_action.slot0/slot1`; resolve `move_index`→`request.active[i].moves`, `target_ident`→bench species, `dex.to_id`; pin `is_protect`). **Step 4:** green + suite + commit.

### Task 4: Group 3 (eval, trace-only) + Group 4 (tempo/risk) + no-recompute gate

**Files:** Modify `features.py`; Test `tests/test_features.py`.

- [ ] **Step 1: tests** —
  `test_g3_reads_only_from_trace` (the **no-recompute gate**: monkeypatch/forbid any calc/DamageModel use — G3 values must equal the trace's `aggregate_score`/`score_vector`/`aggregate_breakdown`/`model_features` exactly), `test_g3_ko_counts_from_model_features`, `test_g3_sentinels_fakeout_action_economy_zero`,
  `test_g4_response_count_and_entropy` (from `trace.opponent_responses`/weights), `test_g4_value_range` (`max-min` of score_vector), `test_g4_speed_counts` (from `speed_oracle` on a known-speed fixture), `test_g4_must_react_flag` (coarse `int(game_mode=="MUST_REACT")`).
- [ ] **Step 2: fail.** **Step 3:** implement `_group3_eval(candidate, trace)` (ONLY trace reads + the two `0.0` sentinels) and `_group4_tempo(candidate, trace, state, context)` (trace + `speed_oracle` + `priors`). **Step 4:** green + full suite + commit.

---

## The 7 hard gates (acceptance criteria — all are tests above)
1. Every `schema.FEATURE_COLUMNS` key has exactly one source (gate: `set(row.features)==set(FEATURE_COLUMNS)`).
2. Every optional field has an explicit sentinel (G2/G1 sentinel tests).
3. `extract_features` returns one `Row` per `CandidateTrace` (gate 1 test).
4. All candidates of one decision share identical Group-1 features (gate 5 test).
5. Group-3 eval fields are read only from the trace, never recomputed (no-recompute test).
6. No metadata/outcome/future field appears in features (gate 3 test).
7. No feature value is `None` (gate 2 test).

## Self-Review notes
- **Spec coverage:** all 4 groups mapped per-column; sentinels central; gates are tests. **Deferred:** `DatasetExporter` + IDs + JSONL (1b-B2), client hook + E2E (1b-B3).
- **No Node/calc:** every G3 value comes from the trace; G2/G1/G4 are deterministic reads of request/state/dex/move_meta/speed_oracle/context.
- **v1 documented approximations:** `screens=__untracked__`, `fakeout/action_economy=0.0`, `must_react_reason_flags` coarse, `score_worst_response==score_min_vs_opp`, `opp_alive_count` revealed-estimate, switch candidates' decision-level threat (from the 1b-A amendment).

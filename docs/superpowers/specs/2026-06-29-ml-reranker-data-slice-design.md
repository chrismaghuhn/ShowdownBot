# Phase 3, Slice 1: Reranker training data + feature/label contract — Design

**Goal:** Generate offline training data for a future learned action *reranker*:
per decision, a frozen feature vector per candidate joint-action and a **silver
(teacher) label** from a fixed-horizon counterfactual rollout that is *deeper than
the one-ply eval*. No model, training, or integration here — just the data and the
frozen contract everything downstream depends on.

**Status:** approved-with-refinements (brainstorming, 2026-06-29). Slice 1 of
Phase 3 (Learned Action Reranker). The heuristic stays the candidate generator;
the reranker (later) re-scores its candidates, with the heuristic as the safety
floor.

> **Naming discipline:** the label is a **silver / teacher label**, NOT ground
> truth. It means "under our stronger counterfactual evaluator this candidate
> looks better" — never "objectively best". This keeps us honest about the ML.

## Scope / non-goals

**In:** the teacher rollout, the frozen 4-group feature schema, the per-candidate
label, and the JSONL dataset export. **Out (later slices):** the model, the
training pipeline (including the near-equal-pair margin rule — *specified here*
but applied at training time), evaluation, the reranker integration into
`pick_best`, and the optional hybrid terminal-MC quality check.

## The teacher: fixed-horizon counterfactual rollout

Parameters: **H = 4** turns (default; H=2 smoke, H=6 offline/experimental),
**top-K = 6** candidates, **γ = 0.75**, **leaf value = the current heuristic eval**
at the horizon. The heuristic plays **both sides** for turns 1..H (with the
now-correct own/opponent models).

**No counterfactual leak (precise rule):** the turn-0 opponent action(s) must be
chosen from the *public pre-decision state* and must **not** condition on the
fixed candidate. We use the existing Phase-2 machinery: `predict_responses`
produces a **candidate-independent** weighted opponent response set `R` (weights
`w`), computed **once per decision**. Every candidate is rolled out against the
*same* `R`.

For decision `D` (pre-decision state `S`, top-K candidates, response set `R`):

```
for candidate c in top_k:
    for response r in R:                       # same R for every candidate (no leak)
        s0   = resolve_turn(S, c + r)          # turn 0
        v_r  = score(s0) + sum_{t=1..H} γ^t · score(turn_t)   # turns 1..H: heuristic both sides
                        + γ^H · heuristic_eval(state_at_H)     # leaf
    counterfactual_value(c) = Σ_r w_r · v_r    # weighted mean over responses (matches Phase-2 eval)
```

Cost is real (K × |R| × H × a heuristic decision + calc per turn), so generation
**samples a subset of decisions per game** and is strictly offline. Reuses the
resolver + the heuristic decision; this is NOT the existing condition-only rollout.

## Dataset row — features / metadata / label (the key split)

One JSONL row per `(decision × candidate)`. Three disjoint sections:

- **`features`** — ONLY information available *at decision time* (see the 4 groups).
  Nothing derived from the future or the outcome (prevents label leakage).
- **`metadata`** — `game_id`, `decision_id`, `candidate_index`, `format_id`,
  `game_outcome`, `final_turn`, `winner`, `teacher_trace` (the rollout breakdown).
  Used for grouping + later evaluation, **never as a training feature**.
- **`label`** — `counterfactual_value_raw`,
  `counterfactual_value_normalized_within_decision`, `counterfactual_rank`,
  `teacher_best: bool`.

`decision_id` / `game_id` group rows so the reranker can train listwise/pairwise.

## Feature schema — 4 frozen groups

**Group 1 — decision-level context** (identical for every candidate of a
decision): `game_mode`, `turn_number`, `endgame_flag`, `our_alive_count`,
`opp_alive_count`, `our_total_hp_frac`, `opp_total_hp_frac`, `field_weather`,
`field_terrain`, `tailwind_ours`, `tailwind_opp`, `trick_room_active`,
`screens_ours`, `screens_opp`, `speed_control_state`, `format_id`, `mirror_flag`.
(`side_to_move` omitted — VGC turns are simultaneous.)

**Group 2 — candidate action** (per candidate): `slot1_action_type`,
`slot2_action_type` (move/protect/switch/tera), `slot1_move_id`, `slot2_move_id`,
`slot1_target_kind`, `slot2_target_kind`, `slot1_priority`, `slot2_priority`,
`slot1_is_damaging`, `slot2_is_damaging`, `slot1_is_protect`, `slot2_is_protect`,
`slot1_is_switch`, `slot2_is_switch`, `tera_used`. **`move_id`/`species_id` are
stored as categorical fields** even if the first (GBT/logistic) model ignores them
in favour of derived numerics — later models need the IDs.

**Group 3 — heuristic/eval** (the most important block): `heuristic_aggregate_score`,
`heuristic_rank`, `score_gap_to_top`, `score_gap_to_second`, `score_min_vs_opp`,
`score_mean_vs_opp`, `score_var_vs_opp`, `score_worst_response`,
`predicted_outgoing_damage`, `predicted_incoming_damage`, `out_in_ratio`,
`predicted_kos_for`, `predicted_kos_against`, `ko_secured_count`,
`ko_threatened_count`, `survives_for_sure_count`, and the play-quality terms so
they become learnable: `protect_stall_penalty`, `partner_abandon_penalty`,
`fakeout_invalid_penalty`, `action_economy_score`.

**Group 4 — tempo/risk** (central to caution-vs-aggression): `we_outspeed_count`,
`they_outspeed_count`, `speed_tie_count`, `our_fastest_active_speed`,
`opp_fastest_active_speed`, `must_react_reason_flags`, `protect_prior_target1`,
`protect_prior_target2`, `response_count`, `opponent_response_entropy`,
`value_range_across_opp_responses` (lets the model learn "good mean but risky").

## Label normalization + near-equal rule

Absolute heuristic values aren't comparable across board states, so the trainable
target is **within-decision**: `value_norm = value − mean(values_in_decision)`
(and `value_gap_to_best = value − max(values_in_decision)` is also stored).
`counterfactual_rank` and `teacher_best` are computed **only within the same
`decision_id`**.

**Near-equal pairs (write the rule now, apply at training):** two candidates less
than `margin` apart produce **no** pairwise training pair — avoids learning noise.
Default `margin = 0.5` score points (or percentile-based).

## File structure

A dedicated `src/showdown_bot/learning/` package (depends on `battle/`, never the
reverse):
- `learning/schema.py` — the frozen feature/metadata/label dataclasses + group
  definitions + JSONL (de)serialization.
- `learning/teacher.py` — the fixed-horizon counterfactual rollout teacher
  (top-K, response set `R`, return formula, normalization).
- `learning/export.py` — drive self-play, sample decisions, emit JSONL.
- Tests: `tests/test_ml_schema.py`, `tests/test_teacher_rollout.py`.

## Testing
- **Rollout determinism** — same seed/state → identical counterfactual values.
- **Top-K selection** — exactly the heuristic's top-K candidates are scored.
- **No counterfactual leak** — turn-0 opponent response set is identical across
  all candidates of a `decision_id` (not derived from the candidate).
- **H=0 ≈ pure eval** — the teacher at H=0 reduces to the one-ply aggregate (sanity).
- **JSONL schema roundtrip** — write → read → identical typed record.
- **Feature availability** — no `features` field is computable only from the
  future/outcome (assert `game_outcome`/`winner` live in `metadata`, not `features`).
- **Group consistency** — all candidates of a `decision_id` share identical
  Group-1 (decision-level context) features.
- **Normalization scope** — ranks / normalized values are computed only within a
  `decision_id` (a second decision in the same file doesn't shift them).

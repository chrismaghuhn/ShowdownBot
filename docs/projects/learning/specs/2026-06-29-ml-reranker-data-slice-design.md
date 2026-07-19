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

Parameters: **H = the number of heuristic follow-up turns after the fixed
candidate turn** (default 4; H=2 smoke, H=6 offline/experimental) — so there are
`1 + H` simulated transitions total (transition 0 = the candidate turn, then H
follow-ups). **top-K = 6** candidates, **γ = 0.75**, **leaf value = the current
heuristic eval** at the horizon. The heuristic plays **both sides** for the H
follow-up turns (with the now-correct own/opponent models).

**No counterfactual leak (precise rule):** the turn-0 opponent action(s) must be
chosen from the *public pre-decision state* and must **not** condition on the
fixed candidate. We use the existing Phase-2 machinery: `predict_responses`
produces a **candidate-independent** weighted opponent response set `R` (weights
`w`), computed **once per decision**. Every candidate is rolled out against the
*same* `R`.

For decision `D` (pre-decision state `S`, top-K candidates, response set `R`). The
return is **incremental transition rewards + one bootstrap leaf** — they must never
evaluate the same state twice:

```
for candidate c in top_k:
    for response r in R:                       # same R for every candidate (no leak)
        # transition 0 = fixed candidate c + opponent response r;
        # transitions 1..H = the heuristic playing BOTH sides.
        v_r = sum_{t=0..H} γ^t · transition_reward_t                        # incremental deltas
              + (γ^(H+1) · leaf_eval(state_after_transition_H) if use_leaf else 0)     # static board value, bootstrap only
    counterfactual_value(c) = Σ_r w_r · v_r    # weighted mean over responses (matches Phase-2 eval)
```

- **`transition_reward_t`** = the **incremental** outcome score of turn `t` — the
  existing `score_outcome` (KOs/damage/tempo *of that turn*), NOT an absolute board
  value.
- **`leaf_eval(state_after_transition_H)`** = the **static** heuristic value of the horizon
  state (one-ply aggregate). It is the ONLY full board evaluation and is discounted
  to `γ^(H+1)` — strictly *after* the last realized transition — so it cannot
  double-count `transition_reward_H`.
- **Invariant:** rollout transition scores are incremental; a static full-board
  evaluation appears **only** as the horizon leaf.

Cost is real (K × |R| × H × a heuristic decision + calc per turn), so generation
**samples a subset of decisions per game** and is strictly offline. Reuses the
resolver + the heuristic decision; this is NOT the existing condition-only rollout.

## Dataset row — features / metadata / label (the key split)

One JSONL row per `(decision × candidate)`. Three disjoint sections:

- **`features`** — ONLY information available *at decision time* (see the 4 groups).
  Nothing derived from the future or the outcome (prevents label leakage).
- **`metadata`** — `game_id`, `decision_id`, `candidate_index`, `format_id`,
  `game_outcome`, `final_turn`, `winner`, `teacher_trace` (the rollout breakdown),
  plus **dataset versioning** (mandatory — without it old JSONL is uninterpretable
  after any change to likely_sets / penalties / feature names / teacher logic):
  `schema_version`, `feature_extractor_version`, `teacher_version`, `git_sha`,
  `team_hash`, `config_hash`, and `teacher_config: {H, gamma, top_k,
  response_policy, model_flags, sample_policy, decision_sampling_rate,
  random_seed}` — the sampling fields record *which* decisions a dataset came from
  (every turn / every Nth / non-terminal only / high-disagreement only). Used for
  grouping + versioning + later evaluation, **never as a training feature**.
- **`label`** — `counterfactual_value_raw`,
  `counterfactual_value_normalized_within_decision`, `value_gap_to_best`,
  `counterfactual_rank`, `teacher_best: bool`, and — to surface the most valuable
  training/debug cases (heuristic chose A, teacher prefers B) —
  `chosen_by_current_heuristic: bool`, `heuristic_rank`, `teacher_rank`.

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
`slot1_move_type`, `slot2_move_type`, `slot1_move_category`, `slot2_move_category`
(generalize better than raw move-ids; reconstructable from `MoveMeta`),
`slot1_target_kind`, `slot2_target_kind`, `slot1_target_slot`, `slot2_target_slot`,
`slot1_priority`, `slot2_priority`, `slot1_is_damaging`, `slot2_is_damaging`,
`slot1_is_protect`, `slot2_is_protect`, `slot1_is_switch`, `slot2_is_switch`,
`tera_used`, and the **actor / switch-target / (known) target species** —
`slot1_actor_species_id`, `slot2_actor_species_id`,
`slot1_switch_target_species_id`, `slot2_switch_target_species_id`,
`slot1_target_species_id_if_known`, `slot2_target_species_id_if_known`. These
matter for reranking: Incineroar-Protect vs Flutter-Mane-Protect vs
Tornadus-Protect are the same action type but completely different contexts.
**All `*_id` fields are stored as categorical** even if the first (GBT/logistic)
model ignores them in favour of derived numerics — later models need the IDs.

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
(and `value_gap_to_best = value − max(values_in_decision)`). `counterfactual_rank`,
`teacher_best`, `heuristic_rank`, and `teacher_rank` are computed **only within the
same `decision_id`**. Storing both the heuristic's choice and the teacher's lets
training (and debugging) target the high-value disagreement cases — heuristic
chose A, teacher prefers B.

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
- **H=0 == one-ply aggregate** — with `use_leaf` off, the teacher at H=0 equals the
  one-ply aggregate **exactly, within float tolerance** (not merely "approximately").
- **Teacher formula / no double-count** — a hand-built short case checks that the
  return is `Σ γ^t·transition_reward_t + γ^(H+1)·leaf`, the leaf never re-scoring
  the last transition's state.
- **JSONL schema roundtrip** — write → read → identical typed record.
- **Schema versioning** — every record carries `schema_version`,
  `feature_extractor_version`, `teacher_version`, and `teacher_config`.
- **Feature availability** — no `features` field is computable only from the
  future/outcome (assert `game_outcome`/`winner` live in `metadata`, not `features`).
- **Group consistency** — all candidates of a `decision_id` share identical
  Group-1 (decision-level context) features.
- **Normalization scope** — ranks / normalized values are computed only within a
  `decision_id` (a second decision in the same file doesn't shift them).
- **Heuristic-vs-teacher disagreement** — when the teacher prefers a different
  candidate than the heuristic, `chosen_by_current_heuristic`, `teacher_best`,
  `heuristic_rank`, `teacher_rank` are all set consistently.

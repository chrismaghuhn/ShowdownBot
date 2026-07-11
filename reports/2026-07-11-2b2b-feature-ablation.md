# 2b-2b Feature Ablation — LOCO/SCO Report

Slice 2b-2b. Leave-one-class-out (LOCO) and single-class-only (SCO) retraining over the committed 2b-2.5a dataset, ATTACK-strict gate throughout -- same split (seed=42, by-game), same LightGBM params, same code paths as `reranker_train.main` (see docs/superpowers/specs/2026-07-11-2b2b-feature-ablation-design.md). This ranks which feature classes actually drive the gate metric (regret-vs-teacher), which LightGBM's own gain/split importance does not measure.

Dataset: `data/datasets/phase3-slice2b25a/dataset.jsonl.gz` (sha256 `3303351176733fd373eed251a29d7f2bde0f3aa50b4a8fd407eff448f39542d6`)
Live features: 66  |  dropped constant: 7

`tera_used` is one of the 7 `dropped_constant_columns` (never enters the LOCO/SCO partition below).
Its root cause is diagnosed separately: `reports/2026-07-11-2b2b-tera-used-diagnosis.md`.

## Self-check

FULL row reproduces the committed 2b-2.5a offline-eval numbers (`reports/2026-07-11-2b25a-offline-eval.md`): model_regret=0.6172, heuristic_regret=2.2286, model_wrong_near_equal=8, gate_pass=True, dropped_constant_columns=7. **PASS** (self-check ran before this report was written -- see `self_check()`; a mismatch aborts with no report written at all).

## Feature-class partition

Every live feature is assigned to exactly one class (exhaustive + disjoint, enforced by `partition_features`); `misc` is the explicit catch-all so nothing is silently unclassified.

| class | n | members |
|---|---|---|
| weather_terrain | 4 | field_weather, tailwind_ours, tailwind_opp, trick_room_active |
| move_desc | 10 | slot1_move_type, slot2_move_type, slot1_move_category, slot2_move_category, slot1_priority, slot2_priority, slot1_is_damaging, slot2_is_damaging, slot1_is_protect, slot2_is_protect |
| species_id | 6 | slot1_actor_species_id, slot2_actor_species_id, slot1_switch_target_species_id, slot2_switch_target_species_id, slot1_target_species_id_if_known, slot2_target_species_id_if_known |
| mirror | 1 | mirror_flag |
| damage | 8 | predicted_outgoing_damage, predicted_incoming_damage, out_in_ratio, predicted_kos_for, predicted_kos_against, ko_secured_count, ko_threatened_count, survives_for_sure_count |
| speed | 6 | speed_control_state, we_outspeed_count, they_outspeed_count, speed_tie_count, our_fastest_active_speed, opp_fastest_active_speed |
| board | 5 | endgame_flag, our_alive_count, opp_alive_count, our_total_hp_frac, opp_total_hp_frac |
| protect | 1 | protect_stall_penalty |
| misc | 25 | game_mode, turn_number, field_terrain, slot1_action_type, slot2_action_type, slot1_move_id, slot2_move_id, slot1_target_kind, slot2_target_kind, slot1_target_slot, slot2_target_slot, slot1_is_switch, slot2_is_switch, heuristic_aggregate_score, score_gap_to_top, score_gap_to_second, score_min_vs_opp, score_mean_vs_opp, score_var_vs_opp, score_worst_response, partner_abandon_penalty, must_react_reason_flags, response_count, opponent_response_entropy, value_range_across_opp_responses |

## LOCO — leave-one-class-out (sorted by Δ descending: most load-bearing first)

Baseline (FULL, all 66 features): model_regret=0.6172, heuristic_regret=2.2286, model_wrong_near_equal=8, gate_pass=True.

| class | features removed | model_regret | Δ vs FULL | gate still passes? |
|---|---|---|---|---|
| misc | 25 | 0.9670 | +0.3498 | True |
| board | 5 | 0.7818 | +0.1646 | True |
| damage | 8 | 0.7433 | +0.1261 | True |
| species_id | 6 | 0.6594 | +0.0422 | True |
| mirror | 1 | 0.6301 | +0.0129 | True |
| weather_terrain | 4 | 0.6140 | -0.0032 | True |
| protect | 1 | 0.5903 | -0.0269 | True |
| move_desc | 10 | 0.5593 | -0.0579 | True |
| speed | 6 | 0.4983 | -0.1189 | True |

## SCO — single-class-only (standalone signal; diagnostic, not a gate)

| class | n features | model_regret | gate_pass |
|---|---|---|---|
| weather_terrain | 4 | 2.2286 | False |
| move_desc | 10 | 1.4856 | True |
| species_id | 6 | 1.5512 | False |
| mirror | 1 | 2.2286 | False |
| damage | 8 | 1.6853 | False |
| speed | 6 | 2.2286 | False |
| board | 5 | 2.2286 | False |
| protect | 1 | 1.9812 | False |
| misc | 25 | 0.7471 | True |

## Verdicts

load-bearing: LOCO breaks the gate, or Δ >= 0.1 (absolute) or >= 15% (relative to FULL). prunable: |Δ| <= 0.03 (noise-level) AND SCO shows no material standalone signal. inconclusive: neither condition is met cleanly.

| class | n | Δ vs FULL | gate_pass (LOCO) | verdict |
|---|---|---|---|---|
| weather_terrain | 4 | -0.0032 | True | prunable |
| move_desc | 10 | -0.0579 | True | inconclusive |
| species_id | 6 | +0.0422 | True | inconclusive |
| mirror | 1 | +0.0129 | True | prunable |
| damage | 8 | +0.1261 | True | load-bearing |
| speed | 6 | -0.1189 | True | inconclusive |
| board | 5 | +0.1646 | True | load-bearing |
| protect | 1 | -0.0269 | True | prunable |
| misc | 25 | +0.3498 | True | load-bearing |

### Interpretation notes

- **Negative-delta classes** (`move_desc` (-0.0579), `speed` (-0.1189)): removing these classes made mean model_regret *lower* (better) than FULL on this test split. That is counterintuitive for a genuinely load-bearing class -- most likely redundancy/collinearity with other live features (the same signal is recoverable elsewhere) or plain refit noise on a small held-out split, not evidence the class is actively harmful. Classified `inconclusive` rather than `prunable`: under this rule a negative Δ is a *weaker*, not stronger, prunability signal than Δ≈0 -- a confident prune call needs more than one refit.

- **Single-column classes** (`mirror`, `protect`): only one feature each, so their LOCO Δ and SCO regret each reflect a single dropped/kept column's effect on one refit -- the lowest statistical power in this report. Their verdict is reported as-is but should not be treated as confidently settled.

- **`misc` dominance:** `misc` alone (SCO, 25 features) reaches model_regret=0.7471 vs FULL's 0.6172 -- most of the gate signal lives in this catch-all class, which includes the heuristic's own aggregate score/gap features (`heuristic_aggregate_score`, `score_gap_to_top`, ...). Unsurprising: the reranker leans heavily on the heuristic's own scoring as a feature, on top of which it improves.

## Caveats

- **Offline optimistic metric.** Regret-vs-teacher is measured against the rollout teacher's own value estimates on teacher-labeled offline data -- the same caveat as 2b-2.5a's offline eval applies here unchanged; this ranks feature classes relative to each other, it does not establish live playing strength.
- **Small test split.** The ATTACK-strict test set is a few hundred decisions from a held-back 30-game partition; small Δ values (roughly within `noise_abs_delta` of each other) are within the noise of a single LightGBM refit on this split, not a confident ranking. Single-column classes (`mirror`, `protect` on this dataset) have especially low statistical power -- report their Δ but do not over-read a small movement either way as proof of (ir)relevance.
- **LightGBM importance ≠ gate contribution.** Built-in gain/split importance ranks features for the model's own internal fit; it is not the same as marginal contribution to the ATTACK-strict gate metric on held-back data. This LOCO table **is** the gate contribution (the actual quantity we care about), not a proxy for it.

## Reproduction

```bash
python -m showdown_bot.learning.reranker_ablation data/datasets/phase3-slice2b25a/dataset.jsonl.gz \
  --out-report reports/2026-07-11-2b2b-feature-ablation.md \
  --out-json reports/2026-07-11-2b2b-feature-ablation.json
```

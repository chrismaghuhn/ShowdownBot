# Slice 2b-0 100-Game Dataset QA Report

Source file: `slice2b0_100g.jsonl`  
SHA256: `62f156b1ed7ab406a5838761a0985909737a738f2cd621d383e3ec9dbc73e849`  
Rows parsed: **4658**  
JSON parse errors: **0**

## Metadata QA

| Field | Distinct values |
|---|---:|
| games | 100 |
| decisions | 951 |
| format_id | `gen9vgc2025regi` |
| teacher_version | `rollout-h1-v1` |
| schema_version | `1` |
| feature_extractor_version | `1b-B1` |
| config_hash | `cc5d6b24fed11677` |
| git_sha | `27848461d4b03a8c22f981a164a66a8272c260a9` |
| NaN values | 0 |
| None/null values | 0 |
| Inf values | 0 |

Note: `winner`, `game_outcome`, and `final_turn` are still exported as `__pending__` / `-1` for every row. This is not blocking for candidate-rerank training, but it means final battle outcome metadata is not currently usable from this JSONL.

## Grouping / Decision Stats

| Metric | Value |
|---|---:|
| rows | 4658 |
| games | 100 |
| decisions | 951 |
| multi-candidate decisions | 851 (89.5%) |
| forced/single-candidate decisions | 100 (10.5%) |
| unique `teacher_best` decisions | 851 |
| explicit teacher-best ties | 100 |
| candidate-count distribution | {1: 100, 2: 101, 5: 144, 6: 606} |
| avg rows/game | 46.58 |
| avg decisions/game | 9.51 |
| avg candidates/decision | 4.90 |

## Heuristic Baseline

Definitions:
- `multi topset agreement`: heuristic top-set intersects teacher-best set.
- `unique multi strict agreement`: exactly one heuristic choice and exactly one teacher-best.

| Metric | Value |
|---|---:|
| heuristic == teacher_best, multi topset | 524/851 = 61.6% |
| heuristic == teacher_best, unique multi strict | 424/751 = 56.5% |
| learnable disagreement, unique multi strict | 327/751 = 43.5% |

### Agreement by chosen heuristic action class

Action class is derived from move IDs because `slot*_is_damaging` and `slot*_move_category` are constant/unpopulated in this export.

| Action class | Agreement |
|---|---:|
| ATTACK | 317/643 = 49.3% |
| protect | 107/108 = 99.1% |

## Contestability / Value Gaps

| Metric | Value |
|---|---:|
| contestable decisions, `abs(non_best_gap) <= 0.5` | 529/951 = 55.6% |
| contestable multi-candidate decisions | 529/851 = 62.2% |
| decisions with exact zero-gap non-best alternative | 348/951 = 36.6% |
| decisions with nonzero near-equal alternative, `0 < abs(gap) <= 0.5` | 279/951 = 29.3% |
| non-best rows | 3607 |
| non-best value_gap median | -1.3660 |
| non-best value_gap mean | -2.6640 |
| non-best value_gap min/max | -17.4745 / 0.0000 |
| non-best rows within 0.5 | 1595/3607 = 44.2% |
| normalized value stdev, non-best rows | 2.0907 |

## Deterministic 80/10/10 Game Split, Seed 42

| Split | Games | Decisions | Rows | Multi | Contestable | Heuristic unique-multi agreement | ATTACK agreement |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 80 | 762 | 3729 | 682 | 424 (55.6%) | 56.3% | 49.2% |
| val | 10 | 95 | 467 | 85 | 53 (55.8%) | 57.3% | 50.0% |
| test | 10 | 94 | 462 | 84 | 52 (55.3%) | 56.8% | 49.2% |

Leakage check: train/val/test game sets are disjoint and cover all 100 games.

## Feature QA Notes

The dataset is valid, but these feature columns are constant and therefore not useful for training in this export:

`action_economy_score, fakeout_invalid_penalty, field_weather, format_id, ko_secured_count, mirror_flag, protect_prior_target1, protect_prior_target2, screens_opp, screens_ours, slot1_actor_species_id, slot1_is_damaging, slot1_is_protect, slot1_move_category, slot1_move_type, slot1_priority, slot1_switch_target_species_id, slot1_target_species_id_if_known, slot2_actor_species_id, slot2_is_damaging, slot2_is_protect, slot2_move_category, slot2_move_type, slot2_priority, slot2_switch_target_species_id, slot2_target_species_id_if_known, tailwind_opp, tera_used, trick_room_active`

Important action metadata issue:
- `slot1_is_damaging` and `slot2_is_damaging` are **false for all 4658 rows**.
- `slot1_move_category`, `slot2_move_category`, `slot1_move_type`, and `slot2_move_type` are **`__none__` for all rows**.
- `slot*_is_protect` is also constant false, even though `protect` appears in move IDs.

For the first offline evaluator, derive action class from `slot*_move_id` as a fallback. Before serious model training, consider fixing/enriching the feature extractor so move category/type/protect/damaging flags are populated.

## Verdict

This is a good Slice 2b-0 dataset for building loader, split tooling, baseline evaluation, and a first offline reranker prototype.

Recommended next step:
1. Implement 2b-1 loader/eval.
2. Add margin-aware training masks because many alternatives have zero or near-zero rollout gap.
3. Train the first model only after the baseline evaluator reproduces these metrics.
4. Do not integrate live yet.

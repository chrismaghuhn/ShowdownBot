# Teacher-Disagreement Atlas

## Summary

- dataset: `../data/datasets/phase3-slice2b25a/dataset.jsonl.gz` (17458 rows, 3302 decisions, 299 games)
- decisions: 3302
- forced: 169
- multi_candidate: 3133
- strict_unique_choices: 2735
- topset_disagreement_rate: 0.520268 (1630/3133)
- strict_disagreement_rate: 0.542962 (1485/2735)
- high_value_threshold: 11.589575

## Breakdowns

### action_signature

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| move+move|protects=0 | 1257 | 543 | 714 | 0.568019 | 4.832005 |
| move+move|protects=1 | 417 | 162 | 255 | 0.611511 | 7.362524 |
| move+move|protects=2 | 566 | 394 | 172 | 0.303887 | 5.973521 |
| move+pass|protects=0 | 183 | 58 | 125 | 0.683060 | 0.000000 |
| move+pass|protects=1 | 30 | 0 | 30 | 1.000000 | 0.000000 |
| move+switch|protects=0 | 66 | 28 | 38 | 0.575758 | 2.226857 |
| move+switch|protects=1 | 13 | 6 | 7 | 0.538462 | 5.179960 |
| pass+move|protects=0 | 99 | 23 | 76 | 0.767677 | 0.000000 |
| pass+move|protects=1 | 24 | 0 | 24 | 1.000000 | 0.000000 |
| switch+move|protects=0 | 71 | 34 | 37 | 0.521127 | 3.546858 |
| switch+pass|protects=0 | 9 | 2 | 7 | 0.777778 | 0.071599 |

### candidate_count

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| 2 | 62 | 32 | 30 | 0.483871 | 0.016706 |
| 4 | 1 | 0 | 1 | 1.000000 | 0.000000 |
| 5 | 247 | 49 | 198 | 0.801619 | 0.000000 |
| 6 | 2425 | 1169 | 1256 | 0.517938 | 5.260394 |

### game_mode

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| AHEAD | 1095 | 599 | 496 | 0.452968 | 4.318276 |
| MUST_REACT | 539 | 114 | 425 | 0.788497 | 3.365610 |
| NEUTRAL | 1101 | 537 | 564 | 0.512262 | 5.381750 |

### heuristic_confidence_bucket

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| high | 731 | 355 | 376 | 0.514364 | 4.890701 |
| low | 765 | 271 | 494 | 0.645752 | 4.677154 |
| medium | 594 | 218 | 376 | 0.632997 | 5.570914 |
| tie_or_zero | 645 | 406 | 239 | 0.370543 | 1.520815 |

### response_entropy_bucket

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| high | 595 | 209 | 386 | 0.648739 | 6.198398 |
| low | 74 | 32 | 42 | 0.567568 | 0.000000 |
| medium | 2066 | 1009 | 1057 | 0.511617 | 3.987677 |

### speed_control_state

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| mixed | 7 | 2 | 5 | 0.714286 | 1.863210 |
| none | 1764 | 815 | 949 | 0.537982 | 3.586661 |
| tailwind_both | 137 | 11 | 126 | 0.919708 | 9.188358 |
| tailwind_opp | 57 | 34 | 23 | 0.403509 | 2.258228 |
| tailwind_ours | 606 | 279 | 327 | 0.539604 | 5.567652 |
| trick_room | 164 | 109 | 55 | 0.335366 | 2.985521 |

### threat_bucket

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| 0 | 2639 | 1216 | 1423 | 0.539219 | 4.488647 |
| 1 | 95 | 34 | 61 | 0.642105 | 3.609979 |
| 2 | 1 | 0 | 1 | 1.000000 | 0.001965 |

### turn_bucket

| value | decisions | agreements | disagreements | disagreement_rate | mean_disagreement_regret |
| --- | --- | --- | --- | --- | --- |
| 1-3 | 491 | 266 | 225 | 0.458248 | 5.422079 |
| 4-6 | 485 | 239 | 246 | 0.507216 | 5.879366 |
| 7+ | 1759 | 745 | 1014 | 0.576464 | 3.886848 |

## Top Opportunities

| decision_id | game_id | regret_gap | turn_bucket | game_mode | action_signature | high_value |
| --- | --- | --- | --- | --- | --- | --- |
| 96e47d88f2654a88 | 463f8e23c3f191c0 | 31.857323 | 7+ | NEUTRAL | move+move|protects=1 | True |
| f2eecc9c65d7a0b9 | 463f8e23c3f191c0 | 29.445962 | 7+ | NEUTRAL | move+move|protects=1 | True |
| a40de5d71c336924 | d5f17da160b81a16 | 27.914428 | 4-6 | AHEAD | move+move|protects=1 | True |
| 3f9d72c5ba2512c6 | de6a3ac2f0e4c2e1 | 26.077374 | 7+ | NEUTRAL | move+move|protects=0 | True |
| 635026dc0957a9f0 | e96ee83faf7c6a1e | 26.060666 | 7+ | NEUTRAL | move+move|protects=0 | True |
| a503948cb51d1264 | e151f18ac3b299cf | 26.047300 | 7+ | NEUTRAL | move+move|protects=0 | True |
| 507b42c58ee7f9d3 | dcbc0ae36bea9a5d | 25.975662 | 4-6 | AHEAD | move+move|protects=0 | True |
| 4e0e72f10762d335 | 463f8e23c3f191c0 | 25.266046 | 7+ | NEUTRAL | move+move|protects=0 | True |
| 9d5b2403a59c8953 | 369feaaaa7c5359a | 24.859119 | 4-6 | NEUTRAL | move+move|protects=0 | True |
| 4957e242cd0ccf70 | 6585e4d20cfc6a70 | 24.857506 | 4-6 | NEUTRAL | move+move|protects=0 | True |
| 1f3656b156651e5a | 36935ff2290e2261 | 24.003339 | 4-6 | AHEAD | move+move|protects=1 | True |
| 7784398b69e38777 | 0924cf62ad7cf8b9 | 24.003339 | 4-6 | AHEAD | move+move|protects=1 | True |
| 0cf7821862833833 | 1222430881637e3d | 23.993636 | 4-6 | AHEAD | move+move|protects=1 | True |
| 979eeec9e2f2292b | 5db6c6c67df5987a | 23.993636 | 4-6 | AHEAD | move+move|protects=1 | True |
| c0d47ab5369b04eb | c8c602d8b18e84af | 23.993636 | 4-6 | AHEAD | move+move|protects=1 | True |
| 839e9f6ccef6b406 | 23cadda97f6f62b1 | 23.986464 | 4-6 | AHEAD | move+move|protects=1 | True |
| d8c278f43d1e4b90 | fa6ede4cebeec8be | 23.986464 | 4-6 | AHEAD | move+move|protects=1 | True |
| ff5d6ace62c8e991 | a6d205973596131c | 23.986464 | 4-6 | AHEAD | move+move|protects=1 | True |
| 3af4c55ccfc8e78e | 14cc1409feaafb17 | 23.978027 | 4-6 | AHEAD | move+move|protects=1 | True |
| 7999aa3e85d6b3a5 | ccaf9a8f94fab902 | 23.099114 | 7+ | NEUTRAL | move+move|protects=2 | True |

## Limitations

The rollout teacher is an OFFLINE one-step counterfactual rollout, which makes it optimistic: a strict disagreement here is NOT a proven play error, and a strict agreement is NOT a strength claim. This atlas identifies WHERE regret concentrates, to aim the next reranker/belief work -- it is aimed measurement, not a gate.


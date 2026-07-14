# VERDICT: UNDERPOWERED — worst cell: max_damage x 69f471c2740f1927 (win_rate 0.0200, wilson upper 0.1050)

Mode: gate · schema_version 1 · paired: true

A = candidate (run A); B = baseline (run B). The A-vs-B comparison is the paired McNemar section below, never a side-by-side independent CI (review §10.3).

## Provenance

Run A (candidate):

| field | value |
|---|---|
| run_id | 5c0b0ca928019dfb |
| config_id | heuristic |
| config_hash | bc76bd1d538bb50f |
| format_id | gen9vgc2025regi |
| schedule_hash | 9ce8872b75065c63 |
| seed_base | accuracy-default-on-v001 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | a956b6b912ad0d07e0f9af50fc7128ab970e37ad |
| dirty | False |
| row_count | 150 |
| start_ts | 2026-07-14T14:34:27.049609+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | b13e2ba55aae4d9472d1475fdb56c01286f1e67545c42ac3b4fc90fb23bcf2d0 |
| seedlog | 3d86390b1a925694323f174d9a982c464362af845d0e58f8e3a669bf34eaf6bd |
| schedule | cf783b09ef47c1019197b1c41929c0c38894f80c7076d267922e22f8c07b1766 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | 8fc9962d1f76051fbcbcabf269ab32162b1a44a09d4911cea44e010ce3489889 |

| environment field | value |
|---|---|
| python | 3.14.5 |
| node | v24.16.0 |
| platform | Windows-11-10.0.26200-SP0 |
| dep:lightgbm | 4.6.0 |
| dep:pydantic | 2.13.4 |
| dep:websockets | 16.0 |

Run B (baseline):

| field | value |
|---|---|
| run_id | c9b2ba7d5dab99e2 |
| config_id | heuristic |
| config_hash | a11e829fa898b254 |
| format_id | gen9vgc2025regi |
| schedule_hash | 9ce8872b75065c63 |
| seed_base | accuracy-default-on-v001 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | a956b6b912ad0d07e0f9af50fc7128ab970e37ad |
| dirty | False |
| row_count | 150 |
| start_ts | 2026-07-14T14:18:12.946555+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 5be32ad6b62690c111cc6ccaa4cf058d46f26c9be294a2fa2dc5a61e3156e3e3 |
| seedlog | 3d86390b1a925694323f174d9a982c464362af845d0e58f8e3a669bf34eaf6bd |
| schedule | cf783b09ef47c1019197b1c41929c0c38894f80c7076d267922e22f8c07b1766 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | 8f16b96c04e29e6924c6d4de258b204bd7ccb2e8bcac0a314581a3ad18bc3d87 |

| environment field | value |
|---|---|
| python | 3.14.5 |
| node | v24.16.0 |
| platform | Windows-11-10.0.26200-SP0 |
| dep:lightgbm | 4.6.0 |
| dep:pydantic | 2.13.4 |
| dep:websockets | 16.0 |

## Safety Gates

Result: SAFETY-PASS (any FAIL in EITHER run fails the whole paired analysis)

Run A (candidate):

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 150 == 150 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=482 (budget 1000) |
| seed_log_alignment | PASS | 150 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | bc76bd1d538bb50f |
| one_schedule_hash | PASS | 9ce8872b75065c63 |
| one_seed_base | PASS | accuracy-default-on-v001 |
| one_run_id | PASS | 5c0b0ca928019dfb |
| one_git_sha | PASS | a956b6b912ad0d07e0f9af50fc7128ab970e37ad |
| manifest_match | PASS | ok |

Run B (baseline):

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 150 == 150 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=251 (budget 1000) |
| seed_log_alignment | PASS | 150 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | a11e829fa898b254 |
| one_schedule_hash | PASS | 9ce8872b75065c63 |
| one_seed_base | PASS | accuracy-default-on-v001 |
| one_run_id | PASS | c9b2ba7d5dab99e2 |
| one_git_sha | PASS | a956b6b912ad0d07e0f9af50fc7128ab970e37ad |
| manifest_match | PASS | ok |

## Per-Cell Results

Candidate (run A) per cell. The A-vs-B comparison is the paired section, never a side-by-side independent CI (review §10.3).

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| max_damage | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 50 | 1/49/0 | 0.0200 | 0.0035 | 0.1050 | yes |
| max_damage | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 50 | 14/36/0 | 0.2800 | 0.1747 | 0.4167 | yes |
| max_damage | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 50 | 5/45/0 | 0.1000 | 0.0435 | 0.2136 | yes |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| max_damage | 150 | 20 | 0.1333 | 0.0880 | 0.1970 |

Overall pooled: n=150 wins=20 win_rate=0.1333 wilson=[0.0880, 0.1970]

Unweighted cell mean win rate: 0.1333

Worst cell: max_damage x 69f471c2740f1927 — win_rate 0.0200, wilson upper 0.1050 (n=50)

Losing cells (Wilson upper < 0.5):
- max_damage x 69f471c2740f1927
- max_damage x b0048ae65f0e9ee5
- max_damage x e622869d6c68307e

## Paired McNemar (A vs B)

| n11 (both won) | n00 (both lost) | n10 (A won, B lost) | n01 (B won, A lost) | n_discordant | total |
|---|---|---|---|---|---|
| 20 | 124 | 0 | 6 | 6 | 150 |

delta_winrate = (n10 - n01) / N = -0.0400
delta (winrate_A - winrate_B) = 0.1333 - 0.1733 = -0.0400

exact two-sided binomial p = 0.0312 (n10 of n_discordant, H0 p=0.5)

strength-cell delta (heuristic+max_damage only): -0.0400 over 150 pairs (won 0, lost 6)

power floor: n_discordant=6 vs math floor 6 (p<0.05 unreachable below it) / claim minimum 10

> UNDERPOWERED: only 6 discordant pairs. No conclusion is possible in either direction. This is not evidence of equivalence and must not be cited to unblock 2b-4.

Discordant battles (6) — read every one at this scale (review §3):

| battle_id | cell | outcome | turns_a | turns_b | end_hp_diff_a | end_hp_diff_b |
|---|---|---|---|---|---|---|
| ea2ee12713ac84f6 | max_damage x b0048ae65f0e9ee5 | B won, A lost | 7 | 11 | -0.37 | 0.715385 |
| 696c9f69f4e3ee3c | max_damage x b0048ae65f0e9ee5 | B won, A lost | 9 | 12 | -0.96 | 0.692308 |
| b1a69794443b6bef | max_damage x b0048ae65f0e9ee5 | B won, A lost | 9 | 8 | -0.94 | 0.401523 |
| 357edfd31e433ed0 | max_damage x b0048ae65f0e9ee5 | B won, A lost | 9 | 10 | -0.87 | 0.569231 |
| 782ec4cbc2f61630 | max_damage x b0048ae65f0e9ee5 | B won, A lost | 9 | 12 | -0.98 | 0.607692 |
| e314fe4f8ae7fecd | max_damage x 69f471c2740f1927 | B won, A lost | 11 | 11 | 0.0 | 0.281535 |

## Warnings

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> Paired seeds share luck only up to the first differing choice: after the two configs diverge, the battles are no longer luck-matched, so per-turn comparisons past that point are not paired.

## Reproduction

Run A (candidate) — from the manifest's recorded invocation:

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=accuracy-default-on-v001 \
  python -m showdown_bot.cli gauntlet --schedule C:\Users\chris\Documents\SHowdown BOt\.claude\worktrees\accuracy-default-on-measure\config\eval\schedules\2b4_devstrength_v001.yaml --result-out C:\Users\chris\AppData\Local\sb_measure\accuracy-default-on-devstrength-ab\candidate\results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Run B (baseline) — from the manifest's recorded invocation:

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=accuracy-default-on-v001 \
  python -m showdown_bot.cli gauntlet --schedule C:\Users\chris\Documents\SHowdown BOt\.claude\worktrees\accuracy-default-on-measure\config\eval\schedules\2b4_devstrength_v001.yaml --result-out C:\Users\chris\AppData\Local\sb_measure\accuracy-default-on-devstrength-ab\baseline\results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this paired report (both runs):

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --run-b results.jsonl --seedlog-b seeds.jsonl --schedule 2b4_devstrength_v001.yaml --panel panel_v001.yaml --out <dir> --mode gate
```


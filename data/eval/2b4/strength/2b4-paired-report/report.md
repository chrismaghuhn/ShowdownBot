# VERDICT: NO-GO — delta <= 0 (candidate not ahead) · p too high (p=0.1048 >= 0.05) · cell flip winning->losing: max_damage x 69f471c2740f1927 · weak-policy-only improvement (flat/negative delta on heuristic+max_damage cells) · worst cell: max_damage x 69f471c2740f1927 (win_rate 0.0400, wilson upper 0.1346)

Mode: gate · schema_version 1 · paired: true

A = candidate (run A); B = baseline (run B). The A-vs-B comparison is the paired McNemar section below, never a side-by-side independent CI (review §10.3).

## Provenance

Run A (candidate):

| field | value |
|---|---|
| run_id | 14b3aaa041b1fcc9 |
| config_id | heuristic |
| config_hash | 23351717487f69e5 |
| format_id | gen9vgc2025regi |
| schedule_hash | 9ce8872b75065c63 |
| seed_base | 2b4-devstrength-v001 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | 13795ab9df4f4204d90d1d295ccd3ae2e7c05019 |
| dirty | False |
| row_count | 150 |
| start_ts | 2026-07-11T10:49:34.819224+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 935473728be070081e172289964e80a2263acaf6096ef1091a33da2ea816f707 |
| seedlog | 3ceaca2055db5ab61deb7246eafa7a3243a96a47aa0573df674f2f91f8e5f2ea |
| schedule | 36972d3ad611bc47168a595603ff1bceecd76c5544b0457eaa5d602aa20237e4 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | fab2f0f09c3e1dbcc83c7e50330649defa8716cd2c64ccf4a3e9232b9a3e3866 |

| environment field | value |
|---|---|
| python | 3.12.13 |
| node | v20.19.0 |
| platform | Linux-6.12.90+-x86_64-with-glibc2.35 |
| dep:lightgbm | 4.6.0 |
| dep:pydantic | 2.12.3 |
| dep:websockets | 15.0.1 |

Run B (baseline):

| field | value |
|---|---|
| run_id | f2bb1d3dfd2849b5 |
| config_id | heuristic_reranker |
| config_hash | cb5dd363dd630277 |
| format_id | gen9vgc2025regi |
| schedule_hash | 9ce8872b75065c63 |
| seed_base | 2b4-devstrength-v001 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | 13795ab9df4f4204d90d1d295ccd3ae2e7c05019 |
| dirty | False |
| row_count | 150 |
| start_ts | 2026-07-11T10:59:07.444694+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 4c08fae5a3079c2dedfe390557f3248db9a83f2035a8318be4bba8c20a70836b |
| seedlog | 3ceaca2055db5ab61deb7246eafa7a3243a96a47aa0573df674f2f91f8e5f2ea |
| schedule | 36972d3ad611bc47168a595603ff1bceecd76c5544b0457eaa5d602aa20237e4 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | 48f9705395923e285d437ac1e509a156836a52dc3b02ae19d07d6faaf0f1921e |

| environment field | value |
|---|---|
| python | 3.12.13 |
| node | v20.19.0 |
| platform | Linux-6.12.90+-x86_64-with-glibc2.35 |
| dep:lightgbm | 4.6.0 |
| dep:pydantic | 2.12.3 |
| dep:websockets | 15.0.1 |

## Safety Gates

Result: SAFETY-PASS (any FAIL in EITHER run fails the whole paired analysis)

Run A (candidate):

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 150 == 150 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=399 (budget 1000) |
| seed_log_alignment | PASS | 150 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | 23351717487f69e5 |
| one_schedule_hash | PASS | 9ce8872b75065c63 |
| one_seed_base | PASS | 2b4-devstrength-v001 |
| one_run_id | PASS | 14b3aaa041b1fcc9 |
| one_git_sha | PASS | 13795ab9df4f4204d90d1d295ccd3ae2e7c05019 |
| manifest_match | PASS | ok |

Run B (baseline):

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 150 == 150 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=440 (budget 1000) |
| seed_log_alignment | PASS | 150 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | cb5dd363dd630277 |
| one_schedule_hash | PASS | 9ce8872b75065c63 |
| one_seed_base | PASS | 2b4-devstrength-v001 |
| one_run_id | PASS | f2bb1d3dfd2849b5 |
| one_git_sha | PASS | 13795ab9df4f4204d90d1d295ccd3ae2e7c05019 |
| manifest_match | PASS | ok |

## Per-Cell Results

Candidate (run A) per cell. The A-vs-B comparison is the paired section, never a side-by-side independent CI (review §10.3).

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| max_damage | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 50 | 2/48/0 | 0.0400 | 0.0110 | 0.1346 | yes |
| max_damage | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 50 | 15/35/0 | 0.3000 | 0.1910 | 0.4375 | yes |
| max_damage | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 50 | 9/41/0 | 0.1800 | 0.0977 | 0.3080 | yes |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| max_damage | 150 | 26 | 0.1733 | 0.1211 | 0.2419 |

Overall pooled: n=150 wins=26 win_rate=0.1733 wilson=[0.1211, 0.2419]

Unweighted cell mean win rate: 0.1733

Worst cell: max_damage x 69f471c2740f1927 — win_rate 0.0400, wilson upper 0.1346 (n=50)

Losing cells (Wilson upper < 0.5):
- max_damage x 69f471c2740f1927
- max_damage x b0048ae65f0e9ee5
- max_damage x e622869d6c68307e

## Paired McNemar (A vs B)

| n11 (both won) | n00 (both lost) | n10 (A won, B lost) | n01 (B won, A lost) | n_discordant | total |
|---|---|---|---|---|---|
| 5 | 90 | 21 | 34 | 55 | 150 |

delta_winrate = (n10 - n01) / N = -0.0867
delta (winrate_A - winrate_B) = 0.1733 - 0.2600 = -0.0867

exact two-sided binomial p = 0.1048 (n10 of n_discordant, H0 p=0.5)

strength-cell delta (heuristic+max_damage only): -0.0867 over 150 pairs (won 21, lost 34)

power floor: n_discordant=55 vs math floor 6 (p<0.05 unreachable below it) / claim minimum 10

Cell flips (winning under baseline B, losing under candidate A):
- max_damage x 69f471c2740f1927

(discordant list omitted: n_discordant=55 > 12)

## Warnings

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> Paired seeds share luck only up to the first differing choice: after the two configs diverge, the battles are no longer luck-matched, so per-turn comparisons past that point are not paired.

## Reproduction

Run A (candidate) — from the manifest's recorded invocation:

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=2b4-devstrength-v001 \
  python -m showdown_bot.cli gauntlet --schedule /tmp/sb_repo/config/eval/schedules/2b4_devstrength_v001.yaml --result-out /tmp/sb_out/heuristic/results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Run B (baseline) — from the manifest's recorded invocation:

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=2b4-devstrength-v001 \
  python -m showdown_bot.cli gauntlet --schedule /tmp/sb_repo/config/eval/schedules/2b4_devstrength_v001.yaml --result-out /tmp/sb_out/override/results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this paired report (both runs):

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --run-b results.jsonl --seedlog-b seeds.jsonl --schedule 2b4_devstrength_v001.yaml --panel panel_v001.yaml --out <dir> --mode gate
```


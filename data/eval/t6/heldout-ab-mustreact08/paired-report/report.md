# VERDICT: UNDERPOWERED — worst cell: max_damage x 389416a631f66266 (win_rate 0.0000, wilson upper 0.4345)

Mode: gate · schema_version 1 · paired: true

A = candidate (run A); B = baseline (run B). The A-vs-B comparison is the paired McNemar section below, never a side-by-side independent CI (review §10.3).

## Provenance

Run A (candidate):

| field | value |
|---|---|
| run_id | b265543cde5d13a9 |
| config_id | heuristic |
| config_hash | 13abaf725512ef8e |
| format_id | gen9vgc2025regi |
| schedule_hash | 3076a71aa6841c8c |
| seed_base | t6heldout2026 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | d7283242c682d91f73e637ec3f4c87dac64748c3 |
| dirty | False |
| row_count | 34 |
| start_ts | 2026-07-12T09:55:39.642637+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | bc840139965088d48b04a8b2c1c7607c39c4e0e35b9aa98c06542b3e9136a6e5 |
| seedlog | 74f9689a70beec3c1b6d417650456a33117e363e454616fe8e5d3449a0f2fd25 |
| schedule | 2d40f244b523bf007e0d1e0946acb66b604224e70e782619c4dbd03ac76916d0 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | 261982147768beb75496679de3660685ffd3a732657e759a346e69e31bb9b25e |

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
| run_id | 8cb23da6e91b26bf |
| config_id | heuristic |
| config_hash | ced31adc69f89f5d |
| format_id | gen9vgc2025regi |
| schedule_hash | 3076a71aa6841c8c |
| seed_base | t6heldout2026 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | d7283242c682d91f73e637ec3f4c87dac64748c3 |
| dirty | False |
| row_count | 34 |
| start_ts | 2026-07-12T09:53:19.942974+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 4c5e6eef27966ceb10f8f01c48c99289cee38aa8ec65e2600fd02d42e02c7dd9 |
| seedlog | 74f9689a70beec3c1b6d417650456a33117e363e454616fe8e5d3449a0f2fd25 |
| schedule | 2d40f244b523bf007e0d1e0946acb66b604224e70e782619c4dbd03ac76916d0 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | 9f97ac2a3fa8e5431d8e2c933a7e36a4a23afce91561f4282ebbd4f5f8355c72 |

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
| rows_match_schedule | PASS | 34 == 34 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=399 (budget 1000) |
| seed_log_alignment | PASS | 34 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | 13abaf725512ef8e |
| one_schedule_hash | PASS | 3076a71aa6841c8c |
| one_seed_base | PASS | t6heldout2026 |
| one_run_id | PASS | b265543cde5d13a9 |
| one_git_sha | PASS | d7283242c682d91f73e637ec3f4c87dac64748c3 |
| manifest_match | PASS | ok |

Run B (baseline):

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 34 == 34 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=399 (budget 1000) |
| seed_log_alignment | PASS | 34 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | ced31adc69f89f5d |
| one_schedule_hash | PASS | 3076a71aa6841c8c |
| one_seed_base | PASS | t6heldout2026 |
| one_run_id | PASS | 8cb23da6e91b26bf |
| one_git_sha | PASS | d7283242c682d91f73e637ec3f4c87dac64748c3 |
| manifest_match | PASS | ok |

## Per-Cell Results

Candidate (run A) per cell. The A-vs-B comparison is the paired section, never a side-by-side independent CI (review §10.3).

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| greedy_protect | 389416a631f66266 | teams/panel_v001/tailwind_held.txt | 2 | 1/1/0 | 0.5000 | 0.0945 | 0.9055 | no |
| greedy_protect | f10c6e672c9362c9 | teams/panel_v001/balance_held.txt | 2 | 0/2/0 | 0.0000 | 0.0000 | 0.6576 | no |
| heuristic | 389416a631f66266 | teams/panel_v001/tailwind_held.txt | 5 | 1/4/0 | 0.2000 | 0.0362 | 0.6245 | no |
| heuristic | f10c6e672c9362c9 | teams/panel_v001/balance_held.txt | 5 | 1/4/0 | 0.2000 | 0.0362 | 0.6245 | no |
| max_damage | 389416a631f66266 | teams/panel_v001/tailwind_held.txt | 5 | 0/5/0 | 0.0000 | 0.0000 | 0.4345 | yes |
| max_damage | f10c6e672c9362c9 | teams/panel_v001/balance_held.txt | 5 | 0/5/0 | 0.0000 | 0.0000 | 0.4345 | yes |
| scripted_vgc | 389416a631f66266 | teams/panel_v001/tailwind_held.txt | 2 | 2/0/0 | 1.0000 | 0.3424 | 1.0000 | no |
| scripted_vgc | f10c6e672c9362c9 | teams/panel_v001/balance_held.txt | 2 | 2/0/0 | 1.0000 | 0.3424 | 1.0000 | no |
| simple_heuristic | 389416a631f66266 | teams/panel_v001/tailwind_held.txt | 3 | 0/3/0 | 0.0000 | 0.0000 | 0.5615 | no |
| simple_heuristic | f10c6e672c9362c9 | teams/panel_v001/balance_held.txt | 3 | 0/3/0 | 0.0000 | 0.0000 | 0.5615 | no |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| greedy_protect | 4 | 1 | 0.2500 | 0.0456 | 0.6994 |
| heuristic | 10 | 2 | 0.2000 | 0.0567 | 0.5098 |
| max_damage | 10 | 0 | 0.0000 | 0.0000 | 0.2775 |
| scripted_vgc | 4 | 4 | 1.0000 | 0.5101 | 1.0000 |
| simple_heuristic | 6 | 0 | 0.0000 | 0.0000 | 0.3903 |

Overall pooled: n=34 wins=7 win_rate=0.2059 wilson=[0.1035, 0.3680]

Unweighted cell mean win rate: 0.2900

Worst cell: max_damage x 389416a631f66266 — win_rate 0.0000, wilson upper 0.4345 (n=5)

Losing cells (Wilson upper < 0.5):
- max_damage x 389416a631f66266
- max_damage x f10c6e672c9362c9

## Paired McNemar (A vs B)

| n11 (both won) | n00 (both lost) | n10 (A won, B lost) | n01 (B won, A lost) | n_discordant | total |
|---|---|---|---|---|---|
| 7 | 27 | 0 | 0 | 0 | 34 |

delta_winrate = (n10 - n01) / N = 0.0000
delta (winrate_A - winrate_B) = 0.2059 - 0.2059 = 0.0000

exact two-sided binomial p = 1.0000 (n10 of n_discordant, H0 p=0.5)

strength-cell delta (heuristic+max_damage only): 0.0000 over 20 pairs (won 0, lost 0)

power floor: n_discordant=0 vs math floor 6 (p<0.05 unreachable below it) / claim minimum 10

> n_discordant == 0: the two configs are either behaviorally identical OR one is a mislabeled duplicate of the other. This is NOT evidence of stability and must never be cited as such.

## Warnings

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> Paired seeds share luck only up to the first differing choice: after the two configs diverge, the battles are no longer luck-matched, so per-turn comparisons past that point are not paired.

> scripted_vgc cells measure coverage, not strength: the scripted opponent is a fixed policy used to exercise pipeline paths, so a high win rate against it is not evidence of skill.

> HELD-OUT RUN — these numbers must never inform tuning decisions.

## Reproduction

Run A (candidate) — from the manifest's recorded invocation:

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=t6heldout2026 \
  python -m showdown_bot.cli gauntlet --schedule /tmp/sb_repo/config/eval/schedules/t6_heldout_v001.yaml --result-out /tmp/sb_out/candidate/results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Run B (baseline) — from the manifest's recorded invocation:

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=t6heldout2026 \
  python -m showdown_bot.cli gauntlet --schedule /tmp/sb_repo/config/eval/schedules/t6_heldout_v001.yaml --result-out /tmp/sb_out/baseline/results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this paired report (both runs):

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --run-b results.jsonl --seedlog-b seeds.jsonl --schedule t6_heldout_v001.yaml --panel panel_v001.yaml --out <dir> --mode gate
```


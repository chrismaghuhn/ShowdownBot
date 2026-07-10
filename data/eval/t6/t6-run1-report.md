# VERDICT: SINGLE-RUN SAFETY-PASS

Mode: gate · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | 31f0c2bee34f5695 |
| config_id | heuristic |
| config_hash | aeafb78a5beea9cd |
| format_id | gen9vgc2025regi |
| schedule_hash | 3076a71aa6841c8c |
| seed_base | t6heldout2026 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | 564a06f7d5afa5e74ed92cac333e3c2b5b479947 |
| dirty | False |
| row_count | 34 |
| start_ts | 2026-07-10T13:55:43.538575+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | bb973ec76d83cddb |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | ab6d6227a1be303fcb2da11ba341fd628aca85bbd7d0830ff4d8668661c57e8e |
| seedlog | 74f9689a70beec3c1b6d417650456a33117e363e454616fe8e5d3449a0f2fd25 |
| schedule | 248c1451c31f766e06a955dbe3741fc677782818f59eb6f14bad48e884570b24 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | f029065e047b083026d06c20c51de09b96ff7af6570f42461e137a5b8083a47c |

## Safety Gates

Result: SAFETY-PASS

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 34 == 34 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=334 (budget 1000) |
| seed_log_alignment | PASS | 34 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | aeafb78a5beea9cd |
| one_schedule_hash | PASS | 3076a71aa6841c8c |
| one_seed_base | PASS | t6heldout2026 |
| one_run_id | PASS | 31f0c2bee34f5695 |
| one_git_sha | PASS | 564a06f7d5afa5e74ed92cac333e3c2b5b479947 |
| manifest_match | PASS | ok |

## Per-Cell Results

Hero is the evaluated config in every cell; the opponent policy and team vary.

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

## Warnings

> This is a single-run safety readout, not a comparison. A single run cannot establish improvement over any baseline — it can only pass or fail the safety gates. Any strength claim requires a paired run against a pinned baseline (T6) with the positive-evidence rule.

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> scripted_vgc cells measure coverage, not strength: the scripted opponent is a fixed policy used to exercise pipeline paths, so a high win rate against it is not evidence of skill.

> HELD-OUT RUN — these numbers must never inform tuning decisions.

## Reproduction

Run (from the manifest's recorded invocation):

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=t6heldout2026 \
  python -m showdown_bot.cli gauntlet --schedule ../config/eval/schedules/t6_heldout_v001.yaml --result-out C:/tmp/t6/run1_results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash bb973ec76d83cddb

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a run1_results.jsonl --seedlog-a run1_seeds.jsonl --schedule t6_heldout_v001.yaml --panel panel_v001.yaml --out <dir> --mode gate
```


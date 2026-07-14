# VERDICT: SINGLE-RUN SAFETY-PASS

Mode: gate · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | 8a2ec9133cfe83ac |
| config_id | heuristic |
| config_hash | b8a0aa12b9f6c4de |
| format_id | gen9championsvgc2026regma |
| schedule_hash | b67a851881d76918 |
| seed_base | champions-panel-v0-smoke-i6 |
| panel_hash | aac1ea30446fde88 |
| recomputed_panel_hash | aac1ea30446fde88 |
| git_sha | 3bcd4b38f08585fc4f3870552bbee9b42c417dc2 |
| dirty | False |
| row_count | 2 |
| start_ts | 2026-07-14T21:13:19.444822+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 76ac7b3e3e402bc0e980ce118402c486ed395d19284a9408263a3d617b7e0b9a |
| seedlog | 24e6f23804c6c53b4704eb8a6e6fb92b514414dccdd7daf7ebc6fd6725361c56 |
| schedule | 76c92a2ff9685185ed0864acb18872a343849be4e8beac0b239b2c202d0e7a32 |
| panel | a391ef7cdc14214bed7fe6f4e19e59c052f20ff54ce6c426678a75fb38159fad |
| manifest | acdaf168e80515f2c0dce44bf7427eb04de52c824caa6c3fdfb59823bbb0f4a5 |

| environment field | value |
|---|---|
| python | 3.14.5 |
| node | v22.22.0 |
| platform | Windows-11-10.0.26200-SP0 |
| dep:lightgbm | 4.6.0 |
| dep:pydantic | 2.13.4 |
| dep:websockets | 16.0 |

## Safety Gates

Result: SAFETY-PASS

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 2 == 2 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=331 (budget 1000) |
| seed_log_alignment | PASS | 2 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | aac1ea30446fde88 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | b8a0aa12b9f6c4de |
| one_schedule_hash | PASS | b67a851881d76918 |
| one_seed_base | PASS | champions-panel-v0-smoke-i6 |
| one_run_id | PASS | 8a2ec9133cfe83ac |
| one_git_sha | PASS | 3bcd4b38f08585fc4f3870552bbee9b42c417dc2 |
| manifest_match | PASS | ok |

## Per-Cell Results

Hero is the evaluated config in every cell; the opponent policy and team vary.

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| heuristic | 0054b6894af7215a | teams/panel_champions_v0/goodstuff.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | e0c96fa0cabf1def | teams/panel_champions_v0/rain_offense.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| heuristic | 1 | 0 | 0.0000 | 0.0000 | 0.7935 |
| max_damage | 1 | 0 | 0.0000 | 0.0000 | 0.7935 |

Overall pooled: n=2 wins=0 win_rate=0.0000 wilson=[0.0000, 0.6576]

Unweighted cell mean win rate: 0.0000

Worst cell: heuristic x 0054b6894af7215a — win_rate 0.0000, wilson upper 0.7935 (n=1)

Losing cells (Wilson upper < 0.5): none

## Warnings

> This is a single-run safety readout, not a comparison. A single run cannot establish improvement over any baseline — it can only pass or fail the safety gates. Any strength claim requires a paired run against a pinned baseline (T6) with the positive-evidence rule.

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> HELD-OUT RUN — these numbers must never inform tuning decisions.

## Reproduction

Run (from the manifest's recorded invocation):

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-smoke-i6 \
  python -m showdown_bot.cli gauntlet --schedule ..\config\eval\schedules\champions_v0_smoke_i6_2battle.yaml --panel ..\config\eval\panels\panel_champions_v0.yaml --result-out ..\data\eval\champions-panel-v0\smoke-i6-damage-gen0\results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --schedule champions_v0_smoke_i6_2battle.yaml --panel panel_champions_v0.yaml --out <dir> --mode gate
```

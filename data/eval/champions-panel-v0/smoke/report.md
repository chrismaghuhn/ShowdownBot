# VERDICT: SINGLE-RUN SAFETY-PASS

Mode: dev · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | a8a5d29bfe325456 |
| config_id | heuristic |
| config_hash | d2a17c7935c3ff77 |
| format_id | gen9championsvgc2026regma |
| schedule_hash | 16ba86fd592d37e4 |
| seed_base | champions-panel-v0-smoke |
| panel_hash | aac1ea30446fde88 |
| recomputed_panel_hash | aac1ea30446fde88 |
| git_sha | 04b0eb78f895698eddcdfa76b01ccba28ff5f401 |
| dirty | False |
| row_count | 6 |
| start_ts | 2026-07-14T15:59:32.629343+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 1b24ec49e2101e02b00139bba73291a6020ff9a640e25b7189c60f7ea3efdc03 |
| seedlog | 65ebd350569e24d6f06714a843c310332668673ecfd6e18021e1dac38797dfce |
| schedule | 9317c2a16de10d91d4962f1ec73e44f5e268a43bc4bd09d99b73386a2c15f8fa |
| panel | a391ef7cdc14214bed7fe6f4e19e59c052f20ff54ce6c426678a75fb38159fad |
| manifest | 1ef3a14073f23b4525bc72df1460c202d1c7829a8359e46b678380fb19830f81 |

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
| rows_match_schedule | PASS | 6 == 6 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=0 (budget 1000) |
| seed_log_alignment | PASS | 6 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | aac1ea30446fde88 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | d2a17c7935c3ff77 |
| one_schedule_hash | PASS | 16ba86fd592d37e4 |
| one_seed_base | PASS | champions-panel-v0-smoke |
| one_run_id | PASS | a8a5d29bfe325456 |
| one_git_sha | PASS | 04b0eb78f895698eddcdfa76b01ccba28ff5f401 |
| manifest_match | PASS | ok |

## Per-Cell Results

Hero is the evaluated config in every cell; the opponent policy and team vary.

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| heuristic | 0054b6894af7215a | teams/panel_champions_v0/goodstuff.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| heuristic | 64ecc8fb2e6da7f1 | teams/panel_champions_v0/trick_room.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| heuristic | ea99dd840d0adce2 | teams/panel_champions_v0/tailwind_offense.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | 0054b6894af7215a | teams/panel_champions_v0/goodstuff.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | 64ecc8fb2e6da7f1 | teams/panel_champions_v0/trick_room.txt | 1 | 1/0/0 | 1.0000 | 0.2065 | 1.0000 | no |
| max_damage | ea99dd840d0adce2 | teams/panel_champions_v0/tailwind_offense.txt | 1 | 1/0/0 | 1.0000 | 0.2065 | 1.0000 | no |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| heuristic | 3 | 0 | 0.0000 | 0.0000 | 0.5615 |
| max_damage | 3 | 2 | 0.6667 | 0.2077 | 0.9385 |

Overall pooled: n=6 wins=2 win_rate=0.3333 wilson=[0.0968, 0.7000]

Unweighted cell mean win rate: 0.3333

Worst cell: heuristic x 0054b6894af7215a — win_rate 0.0000, wilson upper 0.7935 (n=1)

Losing cells (Wilson upper < 0.5): none

## Warnings

> This is a single-run safety readout, not a comparison. A single run cannot establish improvement over any baseline — it can only pass or fail the safety gates. Any strength claim requires a paired run against a pinned baseline (T6) with the positive-evidence rule.

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

## Reproduction

Run (from the manifest's recorded invocation):

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-smoke \
  python -m showdown_bot.cli gauntlet --schedule ..\config\eval\schedules\champions_v0_smoke_pilot.yaml --result-out ..\data\eval\champions-panel-v0\smoke\results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --schedule champions_v0_smoke_pilot.yaml --panel panel_champions_v0.yaml --out <dir> --mode gate
```

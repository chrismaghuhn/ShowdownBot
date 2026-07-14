# VERDICT: SINGLE-RUN SAFETY-FAIL

Mode: gate · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | 26f003dbcb2c6802 |
| config_id | heuristic |
| config_hash | b8a0aa12b9f6c4de |
| format_id | gen9championsvgc2026regma |
| schedule_hash | d6fba5070cd7cb49 |
| seed_base | champions-panel-v0-smoke-i5 |
| panel_hash | aac1ea30446fde88 |
| recomputed_panel_hash | aac1ea30446fde88 |
| git_sha | 4da007b49ceb204c76e7ab1b2511a77877281dc2 |
| dirty | False |
| row_count | 10 |
| start_ts | 2026-07-14T19:13:26.516373+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | c59aa71b4fc3fb9630b5ec2ff83a8dc4b38b58143bd90db12e1b7a6662077fad |
| seedlog | ae77a7f0bc7f8c2050df648a8450a94637183b72896c55ba5540a1940c45637b |
| schedule | 5ab011f4efb037fa58e8428fa32885192c9660a0d8c049fca5e744724e591325 |
| panel | a391ef7cdc14214bed7fe6f4e19e59c052f20ff54ce6c426678a75fb38159fad |
| manifest | e62a59e8e4a4190d3feb7a57286b5dd5947daa42527f0a44382a2c036e769cf0 |

| environment field | value |
|---|---|
| python | 3.14.5 |
| node | v22.22.0 |
| platform | Windows-11-10.0.26200-SP0 |
| dep:lightgbm | 4.6.0 |
| dep:pydantic | 2.13.4 |
| dep:websockets | 16.0 |

## Safety Gates

Result: SAFETY-FAIL

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 10 == 10 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | FAIL | worst=3235 (budget 1000) |
| seed_log_alignment | PASS | 10 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | aac1ea30446fde88 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | b8a0aa12b9f6c4de |
| one_schedule_hash | PASS | d6fba5070cd7cb49 |
| one_seed_base | PASS | champions-panel-v0-smoke-i5 |
| one_run_id | PASS | 26f003dbcb2c6802 |
| one_git_sha | PASS | 4da007b49ceb204c76e7ab1b2511a77877281dc2 |
| manifest_match | PASS | ok |

## Per-Cell Results

Hero is the evaluated config in every cell; the opponent policy and team vary.

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| heuristic | 0054b6894af7215a | teams/panel_champions_v0/goodstuff.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| heuristic | 64ecc8fb2e6da7f1 | teams/panel_champions_v0/trick_room.txt | 1 | 1/0/0 | 1.0000 | 0.2065 | 1.0000 | no |
| heuristic | 7b568b09f44b20fd | teams/panel_champions_v0/disruption.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| heuristic | e0c96fa0cabf1def | teams/panel_champions_v0/rain_offense.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| heuristic | ea99dd840d0adce2 | teams/panel_champions_v0/tailwind_offense.txt | 1 | 1/0/0 | 1.0000 | 0.2065 | 1.0000 | no |
| max_damage | 0054b6894af7215a | teams/panel_champions_v0/goodstuff.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | 64ecc8fb2e6da7f1 | teams/panel_champions_v0/trick_room.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | 7b568b09f44b20fd | teams/panel_champions_v0/disruption.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | e0c96fa0cabf1def | teams/panel_champions_v0/rain_offense.txt | 1 | 1/0/0 | 1.0000 | 0.2065 | 1.0000 | no |
| max_damage | ea99dd840d0adce2 | teams/panel_champions_v0/tailwind_offense.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| heuristic | 5 | 2 | 0.4000 | 0.1176 | 0.7693 |
| max_damage | 5 | 1 | 0.2000 | 0.0362 | 0.6245 |

Overall pooled: n=10 wins=3 win_rate=0.3000 wilson=[0.1078, 0.6032]

Unweighted cell mean win rate: 0.3000

Worst cell: heuristic x 0054b6894af7215a — win_rate 0.0000, wilson upper 0.7935 (n=1)

Losing cells (Wilson upper < 0.5): none

## Warnings

> This is a single-run safety readout, not a comparison. A single run cannot establish improvement over any baseline — it can only pass or fail the safety gates. Any strength claim requires a paired run against a pinned baseline (T6) with the positive-evidence rule.

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> HELD-OUT RUN — these numbers must never inform tuning decisions.

## Reproduction

Run (from the manifest's recorded invocation):

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-smoke-i5 \
  python -m showdown_bot.cli gauntlet --schedule ..\config\eval\schedules\champions_v0_smoke_i5.yaml --result-out ..\data\eval\champions-panel-v0\smoke-i5\results.jsonl --decision-trace-out ..\data\eval\champions-panel-v0\smoke-i5\decision_trace.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --schedule champions_v0_smoke_i5.yaml --panel panel_champions_v0.yaml --out <dir> --mode gate
```


# VERDICT: SINGLE-RUN SAFETY-PASS

Mode: gate · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | 92e9ad03a1a13327 |
| config_id | heuristic |
| config_hash | b8a0aa12b9f6c4de |
| format_id | gen9championsvgc2026regma |
| schedule_hash | d6fba5070cd7cb49 |
| seed_base | champions-panel-v0-smoke-i5 |
| panel_hash | aac1ea30446fde88 |
| recomputed_panel_hash | aac1ea30446fde88 |
| git_sha | 62117b51a737f315cf63425cccbbedfe8e8a9340 |
| dirty | False |
| row_count | 10 |
| start_ts | 2026-07-14T19:53:50.285400+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 56994404d27e95494c20a5c9d79459275d0ba7a9bcf721701a716e04e4b4f5e9 |
| seedlog | f7e599b346f8f24d574f87efac2f403c9d1d72852132478363a25e1216122600 |
| schedule | ea10f3ec8ed18b75a21ce3014fdbdc77ef33eb852e4a8959191b753fb582d2d4 |
| panel | a391ef7cdc14214bed7fe6f4e19e59c052f20ff54ce6c426678a75fb38159fad |
| manifest | 72691fa6488f3e2b093c827320d3f0cea0ce72eb7dd25faefc709a93b4a76599 |

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
| rows_match_schedule | PASS | 10 == 10 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=429 (budget 1000) |
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
| one_run_id | PASS | 92e9ad03a1a13327 |
| one_git_sha | PASS | 62117b51a737f315cf63425cccbbedfe8e8a9340 |
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
  python -m showdown_bot.cli gauntlet --schedule ..\config\eval\schedules\champions_v0_smoke_i5.yaml --result-out ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation\results.jsonl --decision-trace-out ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation\decision_trace.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --schedule champions_v0_smoke_i5.yaml --panel panel_champions_v0.yaml --out <dir> --mode gate
```

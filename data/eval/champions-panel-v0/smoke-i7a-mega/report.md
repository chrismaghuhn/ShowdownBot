# VERDICT: SINGLE-RUN SAFETY-PASS

Mode: gate · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | e1180db12f8ceba6 |
| config_id | heuristic |
| config_hash | e137fce925f25bd8 |
| format_id | gen9championsvgc2026regma |
| schedule_hash | b67a851881d76918 |
| seed_base | champions-panel-v0-smoke-i7a-mega |
| panel_hash | aac1ea30446fde88 |
| recomputed_panel_hash | aac1ea30446fde88 |
| git_sha | 5690de75a4f7bc627b8d4be4fddb2074c6b586fc |
| dirty | False |
| row_count | 2 |
| start_ts | 2026-07-15T23:02:19.131662+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | 86e31891547e87da |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | f4da66b80d700343998da818cc3c89aa239fb8b3c3ecbd214930f209c8bd7cb0 |
| seedlog | a21e790c82f25783a65903846121bbf23e42e4f495d0ea9603988e50e91ce9c8 |
| schedule | 88475a4897bcd2492c36c434baf7e992bf345b96f471d3dfeac5c9ee75dd8481 |
| panel | a391ef7cdc14214bed7fe6f4e19e59c052f20ff54ce6c426678a75fb38159fad |
| manifest | 1224ceac19eb7fa97e0b32bb844b9e95a9aa3eb97de2f1387c5a8a00a1cdf957 |

| environment field | value |
|---|---|
| python | 3.14.5 |
| node | v24.16.0 |
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
| latency_p95 | PASS | worst=588 (budget 1000) |
| seed_log_alignment | PASS | 2 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | aac1ea30446fde88 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | e137fce925f25bd8 |
| one_schedule_hash | PASS | b67a851881d76918 |
| one_seed_base | PASS | champions-panel-v0-smoke-i7a-mega |
| one_run_id | PASS | e1180db12f8ceba6 |
| one_git_sha | PASS | 5690de75a4f7bc627b8d4be4fddb2074c6b586fc |
| manifest_match | PASS | ok |

## Per-Cell Results

Hero is the evaluated config in every cell; the opponent policy and team vary.

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| heuristic | 0054b6894af7215a | teams/panel_champions_v0/goodstuff.txt | 1 | 0/1/0 | 0.0000 | 0.0000 | 0.7935 | no |
| max_damage | e0c96fa0cabf1def | teams/panel_champions_v0/rain_offense.txt | 1 | 1/0/0 | 1.0000 | 0.2065 | 1.0000 | no |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| heuristic | 1 | 0 | 0.0000 | 0.0000 | 0.7935 |
| max_damage | 1 | 1 | 1.0000 | 0.2065 | 1.0000 |

Overall pooled: n=2 wins=1 win_rate=0.5000 wilson=[0.0945, 0.9055]

Unweighted cell mean win rate: 0.5000

Worst cell: heuristic x 0054b6894af7215a — win_rate 0.0000, wilson upper 0.7935 (n=1)

Losing cells (Wilson upper < 0.5): none

## Warnings

> This is a single-run safety readout, not a comparison. A single run cannot establish improvement over any baseline — it can only pass or fail the safety gates. Any strength claim requires a paired run against a pinned baseline (T6) with the positive-evidence rule.

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> HELD-OUT RUN — these numbers must never inform tuning decisions.

## Reproduction

Run (from the manifest's recorded invocation):

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-smoke-i7a-mega \
  python -m showdown_bot.cli gauntlet --schedule ../config/eval/schedules/champions_v0_smoke_i7a_2battle.yaml --panel ../config/eval/panels/panel_champions_v0.yaml --result-out ../data/eval/champions-panel-v0/smoke-i7a-mega/results.jsonl --decision-trace-out ../data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash 86e31891547e87da

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --schedule champions_v0_smoke_i7a_2battle.yaml --panel panel_champions_v0.yaml --out <dir> --mode gate
```

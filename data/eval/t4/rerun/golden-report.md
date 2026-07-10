# VERDICT: SINGLE-RUN SAFETY-PASS

Mode: gate · schema_version 1 · paired: false

## Provenance

| field | value |
|---|---|
| run_id | 77993ce0cc2ba67e |
| config_id | heuristic |
| config_hash | aeafb78a5beea9cd |
| format_id | gen9vgc2025regi |
| schedule_hash | a7f000867fdfbde0 |
| seed_base | t4rerun2026 |
| panel_hash | 760c1e5935fe0474 |
| recomputed_panel_hash | 760c1e5935fe0474 |
| git_sha | e2d6f34d96126d0779ee5a00d67314d39ce3fbac |
| dirty | False |
| row_count | 51 |
| start_ts | 2026-07-10T01:03:16.763425+00:00 |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| server_patch_hash | bb973ec76d83cddb |
| pythonhashseed | 0 |

| input file | sha256 |
|---|---|
| results | 14107d6c2004298de007a970f41dc533f264af08766fcb396ddc9589f56377dd |
| seedlog | eee7e61ce1addb9efc4c47acbefb9958f2a2cfe08686825374a6f5344fd44f3d |
| schedule | ca3c55c1f4abb2a713c7de4f0a012a53c73fe04cce3fc46155b898ce4db8ad49 |
| panel | 13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c |
| manifest | 2e01850624e1c0cb98a662543bb265ff3044cee3d6de9b9a717a8517ac0ead23 |

## Safety Gates

Result: SAFETY-PASS

| gate | status | measured |
|---|---|---|
| rows_match_schedule | PASS | 51 == 51 |
| invalid_choices | PASS | 0 |
| crashes | PASS | 0 |
| end_reason_normal | PASS | all normal |
| latency_p95 | PASS | worst=216 (budget 1000) |
| seed_log_alignment | PASS | 51 contiguous, derived |
| no_duplicate_rows | PASS | none |
| panel_hash_match | PASS | 760c1e5935fe0474 |
| dirty | PASS | none |
| team_hashes_present | PASS | present |
| opp_hashes_subset_panel | PASS | subset |
| split_integrity | PASS | consistent |
| reproducible_policies | PASS | all reproducible |
| one_config_hash | PASS | aeafb78a5beea9cd |
| one_schedule_hash | PASS | a7f000867fdfbde0 |
| one_seed_base | PASS | t4rerun2026 |
| one_run_id | PASS | 77993ce0cc2ba67e |
| one_git_sha | PASS | e2d6f34d96126d0779ee5a00d67314d39ce3fbac |
| manifest_match | PASS | ok |

## Per-Cell Results

Hero is the evaluated config in every cell; the opponent policy and team vary.

| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | wilson_lo | wilson_hi | losing |
|---|---|---|---|---|---|---|---|---|
| greedy_protect | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 2 | 1/1/0 | 0.5000 | 0.0945 | 0.9055 | no |
| greedy_protect | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 2 | 0/2/0 | 0.0000 | 0.0000 | 0.6576 | no |
| greedy_protect | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 2 | 2/0/0 | 1.0000 | 0.3424 | 1.0000 | no |
| heuristic | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 5 | 0/5/0 | 0.0000 | 0.0000 | 0.4345 | yes |
| heuristic | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 5 | 0/5/0 | 0.0000 | 0.0000 | 0.4345 | yes |
| heuristic | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 5 | 5/0/0 | 1.0000 | 0.5655 | 1.0000 | no |
| max_damage | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 5 | 0/5/0 | 0.0000 | 0.0000 | 0.4345 | yes |
| max_damage | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 5 | 1/4/0 | 0.2000 | 0.0362 | 0.6245 | no |
| max_damage | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 5 | 1/4/0 | 0.2000 | 0.0362 | 0.6245 | no |
| scripted_vgc | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 2 | 2/0/0 | 1.0000 | 0.3424 | 1.0000 | no |
| scripted_vgc | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 2 | 2/0/0 | 1.0000 | 0.3424 | 1.0000 | no |
| scripted_vgc | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 2 | 2/0/0 | 1.0000 | 0.3424 | 1.0000 | no |
| simple_heuristic | 69f471c2740f1927 | teams/panel_v001/rain_dev.txt | 3 | 1/2/0 | 0.3333 | 0.0615 | 0.7923 | no |
| simple_heuristic | b0048ae65f0e9ee5 | teams/panel_v001/sun_dev.txt | 3 | 0/3/0 | 0.0000 | 0.0000 | 0.5615 | no |
| simple_heuristic | e622869d6c68307e | teams/panel_v001/trickroom_dev.txt | 3 | 0/3/0 | 0.0000 | 0.0000 | 0.5615 | no |

## Aggregates

Per-policy pooled:

| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |
|---|---|---|---|---|---|
| greedy_protect | 6 | 3 | 0.5000 | 0.1876 | 0.8124 |
| heuristic | 15 | 5 | 0.3333 | 0.1518 | 0.5829 |
| max_damage | 15 | 2 | 0.1333 | 0.0374 | 0.3788 |
| scripted_vgc | 6 | 6 | 1.0000 | 0.6097 | 1.0000 |
| simple_heuristic | 9 | 1 | 0.1111 | 0.0199 | 0.4350 |

Overall pooled: n=51 wins=17 win_rate=0.3333 wilson=[0.2197, 0.4703]

Unweighted cell mean win rate: 0.4156

Worst cell: heuristic x 69f471c2740f1927 — win_rate 0.0000, wilson upper 0.4345 (n=5)

Losing cells (Wilson upper < 0.5):
- heuristic x 69f471c2740f1927
- heuristic x b0048ae65f0e9ee5
- max_damage x 69f471c2740f1927

## Warnings

> This is a single-run safety readout, not a comparison. A single run cannot establish improvement over any baseline — it can only pass or fail the safety gates. Any strength claim requires a paired run against a pinned baseline (T6) with the positive-evidence rule.

> Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim.

> scripted_vgc cells measure coverage, not strength: the scripted opponent is a fixed policy used to exercise pipeline paths, so a high win rate against it is not evidence of skill.

## Reproduction

Run (from the manifest's recorded invocation):

```
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=t4rerun2026 \
  python -m showdown_bot.cli gauntlet --schedule ../config/eval/schedules/t4_smoke_v001.yaml --result-out C:/tmp/t4rerun/run1_results.jsonl
```

showdown_commit f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 · server_patch_hash bb973ec76d83cddb

Regenerate this report:

```
python -m showdown_bot.cli eval-report --run-a t4rerun-run1.jsonl --seedlog-a t4rerun-run1-seedlog.jsonl --schedule t4_smoke_v001.yaml --panel panel_v001.yaml --out <dir> --mode gate
```


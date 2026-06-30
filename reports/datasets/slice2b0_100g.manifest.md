# Dataset Manifest — slice2b0_100g (2026-06-30)

The 2b-0 training dataset: a real live-gauntlet rollout-label export. **The JSONL itself is NOT
committed** (14 MB, local-only) — this manifest is the committed provenance record.

## Provenance
- **Path (local, not committed):** `~/.cache/showdownbot/datasets/slice2b0_100g.jsonl`
- **Generated:** 2026-06-30, live local gauntlet (HeuristicBot vs max_damage, mirror `fixed_team`).
- **Server:** `node pokemon-showdown start --no-security 8000` (clone at `~/.cache/showdownbot/pokemon-showdown` @ f8ac140).
- **Command:**
  `cli gauntlet --games 100 --villain max_damage --format gen9vgc2025regi`
- **Env:** `SHOWDOWN_DATASET_TEACHER=rollout SHOWDOWN_CALC_BACKEND=persistent
  SHOWDOWN_ROLLOUT_HORIZON=1 SHOWDOWN_DATASET_SAMPLE_POLICY=all SHOWDOWN_TEAM_PATH=teams/fixed_team.txt`
- Bot code: `main` @ `2784846` (post format-rename + random-tera fixes).

## Shape
- **4658 rows · 100 games · 951 decisions** (~4.9 rows/decision).
- `teacher_version=rollout-h1-v1`, `trainable_label=true`, `format_id=gen9vgc2025regi`.
- **config_hash stable** (single value across all rows), **0 NaN/None**, 0 crashes/invalid choices.
- Gauntlet result: 46/100 wins (irrelevant to labels; just shows clean play).

## Baseline (the numbers a reranker must beat)
- **heuristic == teacher_best (multi-candidate decisions): 62% (524/851).**
- **contestable decisions (≥1 near-equal alt, |value_gap|≤0.5): 29% (279/951).**
- by `slot1_action_type` (multi-candidate, chosen): `move` 56% (423/750), `pass` 100% (trivial/forced).
- (Consistent with Probe 2's 15-game numbers — 60% / 30% — now on 851 multi-candidate decisions.)

## Split convention (for 2b-1)
**Split by `game_id`, never by row** (a decision's candidate rows must stay together; a game's
decisions must stay together to avoid leakage). Suggested deterministic split (seeded shuffle on
the 100 `game_id`s): train 80 / val 10 / test 10 games.

## Notes / follow-ups
- 100 games is enough to prove the model/trainer/eval pipeline; a 300–500-game run is the next
  step for serious statistics (the persistent calc makes it feasible).
- The `slot{1,2}_move_category` features allow a finer attack-vs-status split than the coarse
  `slot1_action_type` used above.

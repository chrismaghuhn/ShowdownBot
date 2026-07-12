# Outcome-Join — reference smoke on `phase3-slice2b25a`

**Date:** 2026-07-12 · **Reference smoke only** — proves the join runs end-to-end and
reconstructs the real `game_id<->battle_id` bridge correctly. No dataset rows were mutated
(`--mode label` only writes a sidecar), no battles were run, no held-out data was touched.

## Command

Run with `showdown_bot/` as the working directory. A plain `python -m` invocation does not get
pytest's `pythonpath = ["src"]` injection, and this worktree's editable install resolves to a
*different* checkout — so `PYTHONPATH=src` is required to run the package's own code rather than
whatever `showdown-bot` happens to be pip-installed as:

```bash
PYTHONPATH=src python -m showdown_bot.learning.outcome_join \
  --dataset "../data/datasets/phase3-slice2b25a/dataset.jsonl.gz" \
  --results \
    "../data/datasets/phase3-slice2b25a/evidence/fixed/results.jsonl" \
    "../data/datasets/phase3-slice2b25a/evidence/trickroom/results.jsonl" \
    "../data/datasets/phase3-slice2b25a/evidence/sun/results.jsonl" \
    "../data/datasets/phase3-slice2b25a/evidence/rain/results.jsonl" \
  --out-dir "C:/Users/chris/AppData/Local/Temp/outcome-join-smoke" \
  --mode label
```

(`data/` lives at the repo root, a sibling of `showdown_bot/`, not inside it — the plan's
`data/datasets/...` paths are relative to the repo root; `../data/...` reaches it from
`showdown_bot/` as cwd.)

## Result: Exit 0, status `COMPLETE`

| field | value |
|---|---|
| dataset | `data/datasets/phase3-slice2b25a/dataset.jsonl.gz` (17458 rows) |
| dataset_sha256 (uncompressed JSONL, canonical) | `ae6042fb03f6f59006186208ce2c780b2798dab36fa9f3061cbfc94f85d3e6cc` |
| groups found | 4 (one per hero: fixed / trickroom / sun / rain) |
| groups labelled | 4 / 4 |
| total_labelled (sidecar rows) | 299 — matches the dataset's own `manifest.json` `"games_with_rows": 299` exactly |
| turn_violations | 0 in every group |

## Per-group coverage + win/loss/tie distribution

Hero identity below is inferred from each group's dataset row-count matching `manifest.json`'s
`per_hero[].rows` exactly (4374 / 1922 / 3581 / 7581) — the join itself is hero-name-agnostic, it
only knows `team_hash`.

| hero | team_hash | labelled (of results battles) | (dirty, run_seed) | hero wins | villain wins | ties | turn_violations |
|---|---|---:|---|---:|---:|---:|---:|
| fixed | `c15cf06874ef2929` | 75 / 75 | (True, 0) | 30 | 45 | 0 | 0 |
| trickroom | `98c5840ba48f196e` | 74 / 75 | (True, 0) | 10 | 64 | 0 | 0 |
| sun | `d4633dbcfcad34c0` | 75 / 75 | (True, 0) | 59 | 16 | 0 | 0 |
| rain | `4028741d62aaaf12` | 75 / 75 | (True, 0) | 32 | 43 | 0 | 0 |

Cross-checked against `manifest.json`'s `per_hero[].hero_wins`/`villain_wins` (computed over all
75 *played* battles per hero, before any dataset-row filtering): fixed (30/45), sun (59/16), and
rain (32/43) match **exactly**. trickroom's manifest figures are 11/64 over 75 battles — one game
short of my 10/64 over 74 labelled battles, because manifest's own notes record that trickroom
"ran 75 games but only 74 produced training rows; one game was a legitimate blowout that sampled
zero decisions" — that battle has no dataset row to label at all, so it correctly does not appear
in `total_labelled`, and per this cross-check it was a hero win (11 → 10). All four groups
reconstructed with the identical constants `(dirty=True, run_seed=0)`, matching `manifest.json`'s
own independent note that "each kernel's results.jsonl.manifest.json reports dirty:true".

## Two plan-code bugs found and fixed (both revealed only by this real-data run — the plan's own
synthetic unit tests never exercise either edge case)

1. **`bridge.reconstruct_mapping` required exact set equality** between the replayed game_ids and
   the group's dataset game_ids. Real data breaks this: the trickroom results file has 75 battles
   but the dataset only has 74 games for it (the zero-sample-decisions battle above never
   produced a game_id). Fixed to a **subset** check (`group.game_ids <= replayed game_ids`), with
   the returned mapping trimmed to exactly the group's own game_ids so `integrity.check_group`'s
   exact-equality coverage check and `join.build_labels` needed no changes.
2. **`runner._results_index` matched a dataset group to a results file via `hero_team_hash ==
   team_hash` equality.** On the real data this matches for **zero** of the 4 groups: `dataset
   metadata.team_hash` (`learning.provenance.team_hash`, hashed from the packed team string) and
   `results.jsonl hero_team_hash` (`eval.result_jsonl`/schedule provenance) are different hashes
   over different inputs — verified zero overlap across all 4×4 group×file combinations. Fixed by
   applying the plan's own documented fallback ("hero_team_hash absent → the gate alone decides")
   **universally**: every group now tries every results file and keeps the one whose full gate
   (bijective bridge + 0 turn-violations) passes, failing closed on 0 or 2+ passing files. The
   turn-check disambiguates reliably in practice — each of the 4 real groups passed against
   exactly one results file, with 9–63 turn-violations against every other file.

Both fixes are committed separately (`fix(outcome-join): subset bridge coverage + gate-arbitrated
results-file matching`) with dedicated regression tests (a dataset-strict-subset-of-results-battles
case in `test_outcome_join_bridge.py`; a two-group/two-file `hero_team_hash`-mismatch case in
`test_outcome_join_runner.py` that would cross-wire labels under naive equality matching).

## Reading

- The self-consistency of the design holds: `learning.provenance.build_feature_context` computes
  `run_id`/`game_id` from the *same* `(git_sha, dirty_flag, team_hash, config_hash, run_seed)`
  values it also stores in `metadata`, so replaying `make_run_id`/`make_game_id` from a dataset
  group's own recorded fields reconstructs its own game_ids exactly — independent of whatever
  `eval.result_jsonl`'s separate `config_hash`/`hero_team_hash` provenance means (confirmed those
  are unrelated hash namespaces; irrelevant to bridge correctness once matching is gate-arbitrated).
- The two-layer gate (bijective coverage + turn-check) is the real safety net, not the
  `hero_team_hash` heuristic — this smoke is direct evidence the gate alone is sufficient to
  correctly pair 4 groups against 4 candidate files with zero ambiguity or mislabelling.

## Limitations

Reference smoke: verifies the join runs end-to-end on the real corpus and reproduces the known
win/loss ground truth exactly (modulo the documented, expected 1-game trickroom exclusion). It
does not freeze historical counts as a regression gate and does not exercise `--mode apply` against
this dataset (covered by `test_outcome_join_join.py`'s synthetic apply tests instead, to avoid
writing a 17k-row dataset copy into a report). No battles, no training, no held-out access.

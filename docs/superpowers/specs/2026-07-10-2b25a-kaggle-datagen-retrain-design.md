# 2b-2.5a — Panel-Diverse Dataset via Kaggle + Enriched Retrain — Design

> First slice of 2b-2.5 (user decisions 2026-07-10: class A before class B; hero AND opponent
> diverse; generation on Kaggle with API automation; main pushed to origin so Kaggle can clone).
> Goal: reactivate the ~18 class-A dead features (mirror-data artifacts) by regenerating the
> training dataset with panel-diverse matchups, then retrain and re-evaluate the reranker.
> Class B (~10 sentinel-capture features: screens, fakeout_invalid_penalty, action_economy_score,
> ko_secured_count, protect_prior_*) is explicitly a LATER slice (2b-2.5b) — no capture code here.

**Slice KPI (sharp):** `dropped_constant_columns` in the new training manifest falls from 28 to
≤ ~10 (only class-B sentinels remain constant). Secondary: regret-vs-teacher gates (2b-2a
pipeline) on the enriched model, compared against the 2b-2a numbers.

## Phase 1 — Kaggle validation gate (MUST pass before any datagen)

- **Artifact:** `tools/kaggle/repro_validation.py` (a Kaggle SCRIPT kernel, committed; script not
  notebook — easier API push). It: clones `github.com/chrismaghuhn/ShowdownBot` @ a PINNED commit
  sha (passed via kernel metadata/env; no floating main); installs the package + Node; clones
  pokemon-showdown @ the provenance.yaml `showdown_commit`, applies
  `tools/eval/patches/pokemon-showdown-seeded-battle.patch`, builds; runs the committed prefix
  schedule (`config/eval/schedules/t4_smoke_v001_prefix.yaml`, seed base `t4rerun2026`,
  PYTHONHASHSEED=0, persistent calc, fresh seeded server); then verifies:
  `verify_winner_sequence` vs the committed reference rows (`data/eval/t4/rerun/t4rerun-prefix.jsonl`)
  AND normalized room-log byte-comparison vs the committed gzipped reference logs. Prints a
  single machine-greppable verdict line `KAGGLE-REPRO: PASS|FAIL (...)` and copies results,
  seed log, room dumps, and the verdict into `/kaggle/working/` for API download.
- **Driver:** `tools/kaggle/kaggle_driver.py` (runs LOCALLY): thin wrapper over the `kaggle`
  Python API — push kernel, poll status, download output. Used by all phases; credentials come
  from the user's environment (verified working, account `chrismaghuhn`).
- **Gate:** `KAGGLE-REPRO: PASS` required. FAIL → stop the slice, report findings (a platform
  divergence would itself be a major finding — document, don't work around silently).

## Phase 2 — Data generation on Kaggle (4 parallel CPU kernels)

- **Schedules (committed, seeded, dev-only):** new module `eval/datagen_2b25a.py` +
  4 committed YAMLs `config/eval/schedules/datagen_2b25a_hero_{fixed,trickroom,sun,rain}.yaml`.
  Each: `generate_dev_schedule(panel_v001, hero_team_path=<that team>, policies=<all 5>,
  seeds_per_cell=5)` → 3 opp teams × 5 policies × 5 seeds = **75 rows**; 4 hero teams → **300
  games total**. Distinct seed bases per schedule: `dg25a-fixed`, `dg25a-trickroom`, `dg25a-sun`,
  `dg25a-rain` (pinned in the module). Drift test à la `test_t4_matrix.py`. Held-out teams are
  structurally impossible (`generate_dev_schedule` + the existing leakage drift test covers the
  committed YAMLs).
  - NOTE: hero teams are the PANEL teams played BY the bot — `hero_team_path` points at
    `teams/panel_v001/*_dev.txt` (hero .packed variants exist from T3b). fixed_team stays the
    fourth hero for continuity with 2b-0.
- **Datagen kernel:** `tools/kaggle/datagen_kernel.py` (committed): same bootstrap as Phase 1,
  then runs ONE schedule (selected via kernel env/metadata) with the T2 gauntlet CLI + export env:
  `SHOWDOWN_DATASET_EXPORT=<path> SHOWDOWN_DATASET_TEACHER=rollout SHOWDOWN_CALC_BACKEND=persistent
  PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=<base> SHOWDOWN_EVAL_SEED_LOG=<path>` and
  `--result-out` (result rows + manifest as free provenance). Outputs to `/kaggle/working/`:
  dataset JSONL, result JSONL + run manifest, seed log, client log, `DATAGEN: DONE rows=<n>` line.
- **Local merge + commit:** driver downloads all 4 outputs → local validation (every dataset row
  `validate_row`-clean; seed-log alignment re-verified per schedule via
  `verify_schedule_alignment`; zero `falling back`/`frame error` lines in client logs) → merge
  (concat, stable order by (hero schedule, game_id, decision_id, candidate_index)) → commit as
  `data/datasets/phase3-slice2b25a/{dataset.jsonl.gz, manifest.json, sha256}` (2b-0 pattern: gz
  committed, raw gitignored) + the 4 result-JSONL/manifests/seedlogs as provenance evidence.
- **Budget realism:** each kernel ≈ 75 games ≈ 75–120 min CPU (rollout labeling dominates) —
  well inside Kaggle's 9–12 h session limit; 4 kernels run concurrently. Kaggle CPU quota, not
  the 30 h GPU quota, is what this consumes.

## Phase 3 — Retrain + offline eval (local, existing 2b-2a pipeline)

- `reranker_features.build_feature_matrix` + `reranker_train` + `reranker_eval` on the merged
  dataset, INV-6 allowlist/denylist + INV-7 manifest exactly as 2b-2a. New artifacts
  `models/reranker/<date>-2b25a-attack-{lgbm.txt,manifest.json}` + offline-eval report.
- **Success evaluation (report):** (1) KPI: dropped_constant_columns count + the reactivated
  feature list; (2) ATTACK-strict regret vs teacher (gate, as 2b-2a); (3) side-by-side with the
  2b-2a numbers, with the honest caveat carried over from 2b-2a: regret-vs-teacher is an
  optimistic offline metric; play-strength claims stay with the 2b-3.5 harness (a paired eval of
  the retrained model vs heuristic on the T4 dev schedule is 2b-2b/2b-4 territory, NOT this slice).
- The old model stays; nothing goes live (shadow/override untouched).

## Requirements (testable / checkable)

- **R1** Phase-1 kernel prints `KAGGLE-REPRO: PASS` with 10/10 winner+seed match and log byte
  identity; the run is downloadable and archived under `data/eval/kaggle-validation/`.
- **R2** The 4 datagen schedules: committed, drift-tested, 75 rows each, dev-only, distinct
  pinned seed bases; leakage test still green.
- **R3** Merged dataset: schema-valid, all 4 seed logs align, ≥ ~10k rows expected (300 games;
  2b-0 ratio ≈ 46 rows/game → ~14k), committed gz + manifest with sha256 + per-kernel provenance.
- **R4** New training manifest: dropped_constant_columns ≤ 12 (target ~10) and every class-A
  feature (field_weather, trick_room_active, tailwind_opp, mirror_flag, slot*_move_*, tera_used,
  slot*_species_ids) present in feature_names (i.e. alive). List any class-A feature still dead
  with a diagnosis.
- **R5** Offline eval report with the three success metrics + caveat; INV-6 guard green; suite
  green (799 baseline); `battle/` untouched.
- **R6** Everything Kaggle-side is reproducible: kernel scripts committed, pinned repo sha +
  showdown commit, seeded runs — a re-push of the same kernel reproduces the same dataset rows.

## Out of scope

Class-B capture code (2b-2.5b); paired strength evaluation vs baseline (2b-2b/2b-4); live/shadow
changes; panel growth; GPU anything; VGC-Bench replay ingestion (later meta-memory work).

## Open risks (named, accepted)

- Kaggle image quirks (Node version, build toolchain) — Phase 1 exists precisely to surface them
  cheaply; fixes go into the kernel bootstrap, never into repo source.
- Internet-enabled kernels require a verified Kaggle account — user confirms verification state
  during Phase 1 (the driver surfaces the error clearly if not).
- Rollout-teacher skip-rate: the hard-fail threshold (skip_rate>0.05 after ≥20 sampled, from 1d)
  applies per kernel run; a diverse-matchup skip-spike would abort that kernel → diagnose, don't
  raise the threshold.

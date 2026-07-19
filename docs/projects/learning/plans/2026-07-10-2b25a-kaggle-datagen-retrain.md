# 2b-2.5a — Kaggle Datagen + Enriched Retrain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude.** Steps use `- [ ]`. Implements the approved spec
> `docs/projects/learning/specs/2026-07-10-2b25a-kaggle-datagen-retrain-design.md`.
> **HARD CONSTRAINT (user, 2026-07-10): the local CPU is saturated by a separate PTCG training —
> NO local battle runs or Showdown servers anywhere in this slice. All battle compute runs on
> Kaggle. Local work = code, tests (suite ~70s, keep runs minimal), API driver, LightGBM.**

**Goal:** Reactivate the ~18 class-A dead features via a panel-diverse, seeded, Kaggle-generated
training dataset (300 games, hero+opponent diverse), retrain the reranker, prove the KPI
(`dropped_constant_columns` 28 → ≤12).

**Architecture:** thin single-file Kaggle kernels that clone the repo at a PINNED sha and then
delegate to a repo-side payload module (`tools/kaggle/kernel_payload.py` — testable locally);
a local API driver (`tools/kaggle/kaggle_driver.py`) does push/poll/download. Datagen schedules
follow the `t4_matrix`/`t6_heldout` pattern. Retrain reuses the 2b-2a pipeline unchanged.

**Suite baseline:** 799 passed. Branch: create `feat/slice-2b25a-kaggle-datagen` off `main`.
Kaggle account `chrismaghuhn` (API auth verified from this machine).

---

### Task 1: Local Kaggle driver (`tools/kaggle/kaggle_driver.py`)

**Files:** Create `tools/kaggle/kaggle_driver.py` + `showdown_bot/tests/test_kaggle_driver.py`

- [ ] TDD on the PURE parts (no network in tests): `build_kernel_metadata(slug, script_path,
  env: dict) -> dict` (kernel-metadata.json shape: id `chrismaghuhn/<slug>`, language python,
  kernel_type script, enable_internet True, enable_gpu False, and env passed via a
  `# KAGGLE_ENV: {...json...}` header line the payload parses — Kaggle script kernels have no
  native env passing; document this convention); `parse_verdict(log_text) -> ("PASS"|"FAIL"|None,
  detail)` grepping `KAGGLE-REPRO:` / `DATAGEN:` lines.
- [ ] Network functions (thin, NOT unit-tested — exercised operationally in Task 3):
  `push(slug, script, env)` (stages a temp kernel dir: metadata json + script with env header,
  calls `kaggle` API kernels_push), `status(slug)`, `wait(slug, timeout_s, poll_s=60)`,
  `download_output(slug, dest)`. CLI entry: `python tools/kaggle/kaggle_driver.py push|wait|pull ...`.
- [ ] Suite green (single run). Commit: `feat(2b-2.5a): kaggle driver (push/poll/pull + metadata)`

### Task 2: Kernel payload + validation kernel

**Files:** Create `tools/kaggle/kernel_payload.py` (repo-side, testable), `tools/kaggle/repro_validation.py`
(single-file kernel), test `showdown_bot/tests/test_kernel_payload.py`

- [ ] `kernel_payload.py` (imported AFTER the kernel clones the repo): functions
  `bootstrap_node()` (idempotent: node>=18 present or install via apt/conda — document Kaggle
  image assumption), `setup_showdown(repo_root, cache_dir)` (clone pokemon-showdown @
  `load_showdown_commit()`, `git apply` the versioned patch, `node build`),
  `run_schedule_seeded(repo_root, schedule_relpath, seed_base, out_dir, *, dataset_export=None)`
  (starts the seeded server as subprocess, runs the T2 gauntlet CLI with the standard env
  incl. PYTHONHASHSEED=0 + persistent calc, stops server, returns paths),
  `validate_prefix_reproduction(repo_root, out_dir) -> bool` (verify_winner_sequence vs
  `data/eval/t4/rerun/t4rerun-prefix.jsonl` + normalized-log byte compare vs the committed gz
  reference — reuse eval/baseline + eval/room_dump), `print_verdict(tag, ok, detail)`.
  Unit tests cover: verdict formatting, env-header parsing, schedule/relpath resolution, and
  validate_prefix_reproduction against the committed fixture using LOCAL files (no battles run —
  it only READS committed artifacts + a synthetic out_dir copy).
- [ ] `repro_validation.py` (the kernel, single file, ~60 lines): parse `# KAGGLE_ENV` header
  (REPO_URL, REPO_SHA), `git clone` + `git checkout REPO_SHA`, `pip install -e showdown_bot`,
  then delegate: bootstrap_node → setup_showdown → run_schedule_seeded(prefix schedule,
  `t4rerun2026`) → validate_prefix_reproduction → `KAGGLE-REPRO: PASS|FAIL (...)`; copy
  results/seedlog/room_raw/verdict into `/kaggle/working/`.
- [ ] Suite green. Commit: `feat(2b-2.5a): kernel payload + repro-validation kernel`

### Task 3 (OPERATIONAL, Opus): Phase-1 execution — the Kaggle gate

- [ ] Push `repro_validation.py` via the driver (slug `sb-repro-validation`, REPO_SHA = current
  origin/main HEAD `d2f16a2…` or newer pushed sha — the kernel scripts themselves must be ON
  origin first: push the feature branch commits to a temp branch or merge-first? RESOLUTION:
  the kernel clones the sha it is given; Tasks 1–2 commits must be PUSHED before Task 3 can run.
  Push the feature branch to origin (`git push origin feat/slice-2b25a-kaggle-datagen`) and pin
  THAT sha — allowed (public repo, user approved pushing).
- [ ] Poll (`wait`, timeout 3600s), download, assert `KAGGLE-REPRO: PASS`. **Bounded iteration
  allowed on the KERNEL/PAYLOAD bootstrap only** (image quirks: node install, build toolchain) —
  each fix is a commit + re-push + re-run; NEVER touch repo source outside tools/kaggle/ for
  this. If >5 iterations or a genuine platform divergence (winner mismatch): BLOCKED with
  evidence (a divergence is a major finding, not a bug to paper over).
- [ ] Archive the passing run under `data/eval/kaggle-validation/` (verdict, results, seedlog,
  sha256) + short report section (goes into the Task 7 report). Commit.

### Task 4: Datagen schedules (`eval/datagen_2b25a.py` + 4 YAMLs)

**Files:** Create `showdown_bot/src/showdown_bot/eval/datagen_2b25a.py`,
`config/eval/schedules/datagen_2b25a_hero_{fixed,trickroom,sun,rain}.yaml`, test
`showdown_bot/tests/test_datagen_2b25a.py`

- [ ] Mirror `t6_heldout.py`: `HERO_TEAMS = {"fixed": "teams/fixed_team.txt", "trickroom":
  "teams/panel_v001/trickroom_dev.txt", "sun": …, "rain": …}`, `SEED_BASES = {"fixed":
  "dg25a-fixed", …}`, `generate_datagen_schedules(panel, *, teams_root=".") -> dict[str, Schedule]`
  = per hero: `generate_dev_schedule(panel, hero_team_path=…, policies=<all 5>, seeds_per_cell=5)`
  (75 rows each). TDD: shapes (75 rows, Counter {25,25,15,10,10}? NO — 5 policies × 5 seeds × 3
  teams: heuristic 15, max_damage 15, simple 15, greedy 15, scripted 15 — uniform int
  seeds_per_cell=5 → 15 each; that's the intended uniform mix for TRAINING diversity, unlike
  T4's weighted EVAL matrix — state this in the docstring), all panel_split=dev, hero hashes
  populated + distinct per schedule, drift tests vs committed YAMLs, leakage test still green.
- [ ] Generate + commit the 4 YAMLs; record the 4 schedule_hashes.
- [ ] Suite green. Commit: `feat(2b-2.5a): datagen schedules (4 hero teams x dev panel, seeded)`

### Task 5: Datagen kernel

**Files:** Create `tools/kaggle/datagen_kernel.py`; extend `kernel_payload.py` + its test

- [ ] Payload gains `run_datagen(repo_root, hero_key, out_dir)`: resolves schedule + seed base
  from `eval/datagen_2b25a`, runs `run_schedule_seeded(..., dataset_export=<out>/dataset.jsonl,
  extra_env={SHOWDOWN_DATASET_TEACHER: "rollout"})`, then LOCAL validations inside the kernel:
  seed-log alignment (verify_schedule_alignment), dataset rows validate_row-clean, zero
  `falling back`/`frame error` in client log; prints `DATAGEN: DONE hero=<k> rows=<n> games=75`
  or `DATAGEN: FAIL (...)`. Kernel file mirrors repro_validation.py (env: REPO_URL, REPO_SHA,
  HERO_KEY).
- [ ] Unit tests: payload pure parts (env resolution, verdict lines) — battles only on Kaggle.
- [ ] Suite green. Commit: `feat(2b-2.5a): datagen kernel (per-hero seeded export)`

### Task 6 (OPERATIONAL, Opus): Phase-2 execution + dataset commit

- [ ] Push branch (updated sha), then push 4 kernels (slugs `sb-datagen-{fixed,trickroom,sun,rain}`)
  CONCURRENTLY; poll all; download outputs. Any kernel FAIL → diagnose from its log; bootstrap
  fixes iterate like Task 3; a rollout-skip hard-fail (skip_rate>0.05) → BLOCKED (diagnose,
  never raise the threshold).
- [ ] Local merge + validation (light CPU): re-run seed-log alignment per schedule locally
  (file-based, no battles), validate_row over all rows, stable-order concat, dedupe check
  (game_ids unique across kernels), stats (rows, decisions, games).
- [ ] Commit `data/datasets/phase3-slice2b25a/`: `dataset.jsonl.gz`, `manifest.json`
  (per-kernel provenance: schedule_hashes, seed bases, run_ids, result sha256s, kaggle kernel
  slugs+versions, repo sha), `sha256.txt`, + the 4 result-JSONLs/manifests/seedlogs as evidence.
  Raw .jsonl gitignored (2b-0 pattern). Commit:
  `feat(2b-2.5a): panel-diverse training dataset (300 Kaggle games, seeded)`

### Task 7: Retrain + offline eval + report (local, light)

- [ ] Run the 2b-2a pipeline (`reranker_features`/`reranker_train`/`reranker_eval`) on the new
  dataset (LightGBM = seconds; fine on the busy CPU). INV-6 allowlist/denylist + INV-7 manifest.
- [ ] **KPI check:** new manifest `dropped_constant_columns` ≤ 12; every class-A feature alive
  (spec R4 list); any still-dead class-A feature gets a diagnosis in the report.
- [ ] Artifacts `models/reranker/<date>-2b25a-attack-{lgbm.txt,manifest.json}` + report
  `reports/<date>-2b25a-offline-eval.md`: KPI table (28 → n), reactivated-features list,
  ATTACK-strict regret vs teacher, side-by-side with 2b-2a, the optimistic-metric caveat, the
  Kaggle provenance summary (Phase 1 PASS + kernel versions), reproduction commands.
- [ ] Full suite green. Commit: `docs(2b-2.5a): enriched retrain + offline eval report`

### Task 8: Closeout
- [ ] `git diff main --stat` scope check; report to controller → merge decision.

---

## Out of scope
Class-B capture (2b-2.5b); paired strength eval (2b-2b/2b-4); live/shadow; GPU; VGC-Bench data.

## Self-review (writing-plans)
- Spec coverage: R1→Tasks 2-3, R2→Task 4, R3→Tasks 5-6, R4/R5→Task 7, R6→pinned shas + committed
  kernels throughout. Hard constraint (no local battles) enforced structurally: the only
  battle-running code path added is inside kernel_payload, executed on Kaggle; local tests read
  committed artifacts only. ✓
- Uniform 5 seeds/cell (training diversity) vs T4's weighted matrix (eval focus) — deliberate,
  documented in Task 4. Kernel env-header convention documented in Task 1. Feature-branch pushes
  to origin required for Kaggle clone (Tasks 3/6) — user-approved. ✓
- Placeholders: none; operational shas/hashes recorded at runtime by design. ✓

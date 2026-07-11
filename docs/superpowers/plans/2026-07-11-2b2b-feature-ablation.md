# 2b-2b Feature Ablation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A deterministic leave-one-class-out (LOCO) + single-class-only (SCO) feature-ablation
harness over the committed 2b-2.5a dataset, a ranked report of which feature classes drive the
ATTACK-strict gate, and a read-only `tera_used` root-cause diagnosis.

**Architecture:** New `learning/reranker_ablation.py` reuses the EXISTING pipeline pieces
(`reranker_features.build_feature_matrix` with an explicit `feature_names` subset,
`reranker_train`, `reranker_eval.regret_metrics`/`gates_pass`) — it never forks the model code,
only drives it with different feature subsets. Spec:
`docs/superpowers/specs/2026-07-11-2b2b-feature-ablation-design.md`.

**Tech stack:** existing repo (pytest, LightGBM, committed dataset
`data/datasets/phase3-slice2b25a/dataset.jsonl.gz`). **Hard constraint:** NO battles/servers;
run only touched test files per task; full suite once at closeout (1 strict-xfail known).

---

### Task 1: feature-class partition + LOCO/SCO harness (Sonnet)

**Files:** Create `showdown_bot/src/showdown_bot/learning/reranker_ablation.py`; test
`showdown_bot/tests/test_reranker_ablation.py`.

- [ ] Study first: `reranker_features.active_feature_names` / `build_feature_matrix`
  (signature: `feature_names=`, `encodings=`), `reranker_train.py` (how it trains + what it
  returns/writes — the train entry it exposes), `reranker_eval.regret_metrics(scored_decisions)`
  + `gates_pass`, and how the 2b-2a/2b-2.5a run wires features→train→eval (read
  reranker_train.main + the offline-eval report's invocation). The harness must call the SAME
  code paths so the full-model ablation row == the committed result.
- [ ] `FEATURE_CLASSES`: an ordered dict of {class_name: predicate/prefix-tuple}. Membership is
  computed at runtime by matching each name in the LIVE feature set (active_feature_names on the
  dataset) — classes are: weather_terrain, move_desc, species_id, mirror, damage, speed, board,
  protect, misc (catch-all). Use explicit column lists where the set is small/known
  (weather_terrain, move_desc, species_id, mirror from the spec) and prefix/substring matchers
  for damage/speed/board/protect; misc = live features matched by no class.
- [ ] `partition_features(live_features) -> dict[class -> list[str]]` asserting exhaustive
  (union == live set) and disjoint (no column in two classes) — raise on violation.
- [ ] Failing test: on the committed dataset's live feature set, the partition is exhaustive +
  disjoint; `misc` is returned (possibly empty) and its members are accessible for the report.
- [ ] `run_ablation(dataset_path, *, split_seed=42) -> AblationResult`: builds decisions once,
  computes live features + partition, then for the FULL set and each LOCO subset (live minus one
  class) and each SCO subset (only one class) trains via the real pipeline and computes
  ATTACK-strict `regret_metrics` on the same test split. Returns per-variant
  {model_regret, heuristic_regret, model_wrong_near_equal, gate_pass, delta_vs_full}.
- [ ] Test: LOCO with an EMPTY removed class == full-model metrics (identity); a class removal
  changes the feature count by exactly len(class). Use a small synthetic decisions fixture for
  the loop mechanics (mock/mini LightGBM path if the real train is slow/flaky in a unit — but
  at least ONE test must exercise the real train on a tiny real-data slice to prove wiring).
- [ ] Run touched tests. Commit `feat(2b-2b): leave-one-class-out feature ablation harness`.

### Task 2: run ablation + ranked report (Sonnet)

**Files:** CLI entry (extend `cli.py` OR a `__main__` in reranker_ablation.py — match how
reranker_train exposes its CLI); output `reports/2026-07-11-2b2b-feature-ablation.md` +
JSON sidecar `reports/2026-07-11-2b2b-feature-ablation.json`.

- [ ] `python -m ... ablation data/datasets/phase3-slice2b25a/dataset.jsonl.gz` runs the full
  ablation and writes both artifacts.
- [ ] **Self-check (fail loud):** the FULL-model row's dropped_constant_columns == 7 and its
  ATTACK metrics match the committed 2b-2.5a offline-eval report
  (reports/2026-07-11-2b25a-offline-eval.md final section) within float tolerance; if not, the
  harness/split diverged — abort with a clear error, do NOT publish a misleading report.
- [ ] Report content: the partition (every class + its members, incl. misc), a LOCO table
  (class | features removed | model_regret | Δ vs full | gate still passes?) sorted by Δ
  descending (most load-bearing first), an SCO table (standalone signal), a
  "load-bearing / prunable / inconclusive" verdict per class, and the caveats (offline
  optimistic metric; small test split; LightGBM importance ≠ gate contribution — this LOCO IS
  the gate contribution). JSON sidecar = the raw numbers.
- [ ] Test: the report + JSON are produced from a small fixture run and contain the required
  sections/keys (structure test, not golden byte-check).
- [ ] Commit `docs(2b-2b): feature-ablation run + ranked report`.

### Task 3: tera_used root-cause diagnosis (Sonnet, read-only analysis)

**Files:** analysis only → append a "tera_used diagnosis" section to the ablation report (or a
short standalone `reports/2026-07-11-2b2b-tera-used-diagnosis.md` — your call, keep it linked).
Optionally ONE tiny characterization test if it pins the cause cleanly. NO production change.

- [ ] Trace the tera path: how tera candidates are enumerated in the live decision
  (`battle/decision.py` tera overlay — grep `tera`), how the rollout teacher enumerates +
  truncates candidates (`learning/teacher.py` cfg.top_k, `learning/rollout.py`
  `for c in trace.candidates[: cfg.top_k]`), and where `tera_used` is set in
  `learning/features.py` (grep `tera_used`). Determine empirically from the committed dataset:
  is `tera_used` ever True in ANY row? how many candidates per decision carry a tera action
  before vs after the top_k=6 truncation?
- [ ] Confirm or refute the truncation hypothesis with the code trace + a dataset measurement
  (e.g. count decisions whose trace had a tera candidate that fell outside the top-6). State the
  real cause and whether it is: (a) truncation (fixable by raising top_k or ensuring tera
  candidates survive), (b) tera genuinely never chosen by the heuristic in these matchups
  (data-rare, not a bug), or (c) an extractor gap. Recommendation for a future slice; do NOT
  regenerate data here.
- [ ] Commit `docs(2b-2b): tera_used root-cause diagnosis`.

### Task 4: closeout

- [ ] Full suite once (`cd showdown_bot && python -m pytest -q`): all green + 1 xfailed
  (test_baseline strict-xfail — known). Anything else → BLOCKED.
- [ ] Ensure the two report artifacts + JSON sidecar are committed; short closeout note if not
  already in the report.
- [ ] `git diff main --stat` scope summary → controller → merge decision.

## Self-review (writing-plans)

- Spec coverage: LOCO/SCO→Tasks 1-2, class partition→Task 1, tera_used→Task 3. ✓
- No battles; committed dataset only. ✓
- Determinism self-check (full-model row reproduces committed numbers) guards against a
  silently-wrong harness. ✓
- Placeholders: damage/speed/board/protect membership is prefix-matched at runtime against
  schema.FEATURE_COLUMNS + printed in the report, so no hardcoded possibly-stale column list. ✓

# Teacher-Disagreement Atlas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Port the rollout-teacher-disagreement mining from the user's Decision-Error-Atlas
prototype onto current main + the 2b-2.5a dataset: classify decisions, bucket disagreements, rank
high-value opportunities, render a deterministic report. Aimed measurement, not a gate.

**Architecture:** New `showdown_bot/src/showdown_bot/eval/teacher_disagreement.py`, loading the
committed dataset via `learning.dataset.load_rows`. Spec:
`docs/projects/learning/specs/2026-07-11-teacher-disagreement-atlas-design.md`. Porting SOURCE (read but
adapt — it's on an old base + old loader): the clone
`C:\Users\chris\Documents\Showdown-Bot-Analysis-Clone\tools\analysis\` (`rollout_metrics.py` /
`atlas_metrics.py::analyze_rollout_decisions`) and its historical plan
`2026-07-10-decision-error-atlas.md` in that external analysis repository (Task 5 has the full function).

**Tech stack:** existing repo (pytest). **Constraint:** no battles; run only touched test files
per task; full suite once at closeout (1 strict-xfail known).

---

### Task 1: classification + bucketing core (Sonnet)

**Files:** Create `showdown_bot/src/showdown_bot/eval/teacher_disagreement.py`; test
`showdown_bot/tests/test_eval_teacher_disagreement.py`.

- [ ] Read the porting source (clone `tools/analysis/atlas_metrics.py::analyze_rollout_decisions`
  + helpers `_turn_bucket`, `_action_signature`, `_response_entropy_bucket`,
  `_heuristic_confidence_bucket`, `_nearest_rank`, `_breakdown` — reproduced in the plan doc
  `2026-07-10-decision-error-atlas.md` Task 5 Step 3). Port them with these ADAPTATIONS:
  - Input is a flat `list[dict]` of rows (from `load_rows`) OR a pre-grouped
    `dict[decision_id -> list[dict]]`. Provide `group_by_decision(rows) -> dict[str, list[dict]]`
    keyed on `metadata.decision_id`, deterministic (sorted).
  - `analyze_disagreement(decisions: dict[str, list[dict]]) -> dict` — the ported classifier:
    forced (len==1) / teacher-tie (>1 teacher_best) / genuine / disagreement
    (chosen != teacher_best). Fail-closed: exactly one `chosen_by_current_heuristic` row per
    decision else raise `TeacherDisagreementError`; ≥1 `teacher_best` else raise; finite
    non-negative `value_gap_to_best` else raise.
  - Bucket keys from the CHOSEN row's features: turn_bucket(turn_number), game_mode,
    action_signature(slot1_action_type, slot2_action_type, slot1_is_protect, slot2_is_protect),
    speed_control_state, threat_bucket(int(ko_threatened_count)), candidate_count,
    response_entropy_bucket(opponent_response_entropy), heuristic_confidence_bucket(score_gap_to_second).
  - Return {corpus:{decisions,forced,teacher_ties,genuine_choices,disagreements},
    disagreement_rate, high_value_threshold (90th nearest-rank pct of positive disagreement gaps),
    breakdowns:{key->rows}, top_opportunities (≤20, sorted by -value_gap then decision_id, each with
    decision_id/game_id/value_gap/turn_bucket/game_mode/action_signature/high_value flag)}.
- [ ] Tests (fabricate decision groups like the clone's `_candidate` helper — see plan Task 5
  Step 1): forced+tie+genuine+disagreement classification with exact corpus counts;
  disagreement_rate; high_value_threshold == the top gap in the synthetic set; top_opportunities[0]
  is the largest-gap disagreement; a bucket's value set; the exactly-one-chosen raise; the
  ≥1-teacher-best raise; determinism (two calls identical).
- [ ] Run touched tests. Commit `feat(disagreement): classify + bucket rollout-teacher disagreements`.

### Task 2: loader wiring + markdown/JSON + CLI (Sonnet)

**Files:** extend `eval/teacher_disagreement.py`; test file; CLI (a `main()` argparse like
`learning/reranker_train.py`, OR a cli.py subcommand — match the repo's lighter pattern:
reranker_train uses a module `main()`).

- [ ] `teacher_disagreement_atlas(dataset_path) -> dict`: `load_rows(dataset_path, validate=True)`
  → `group_by_decision` → `analyze_disagreement`; add a top-level `dataset` block
  {path, rows, decisions, games (distinct metadata.game_id)}. Deterministic (sorted keys).
- [ ] `format_md(atlas) -> str`: sections — summary (denominators), the per-bucket breakdown
  tables (every bucket, sorted), the top-opportunities table, and an **honest-limitations** section
  (offline one-step-counterfactual teacher = optimistic, NOT a proven play error, NOT a strength
  claim; identifies WHERE regret concentrates to aim the next reranker/belief work). Deterministic.
- [ ] `main(argv)`: `python -m showdown_bot.eval.teacher_disagreement <dataset> --out-md <..> --out-json <..>`;
  writes both (json pretty, sorted keys); prints a `DISAGREEMENT ATLAS: decisions=<n> disagreements=<n> (<rate>)` line.
- [ ] Tests: `teacher_disagreement_atlas` on a tiny committed fixture jsonl (2-3 decisions,
  validate=False path OR a schema-valid mini fixture — reuse an existing rollout fixture if one
  exists under tests/) returns internally-consistent counts; format_md contains all required
  sections + the limitations note; the CLI writes both files (structure test, monkeypatch or tmp).
- [ ] Run touched tests. Commit `feat(disagreement): dataset atlas + markdown/json + CLI`.

### Task 3 (controller): run on 2b-2.5a + closeout

- [ ] Run the atlas on `data/datasets/phase3-slice2b25a/dataset.jsonl.gz`; write
  `reports/2026-07-11-teacher-disagreement-atlas.{md,json}` and COMMIT them (this dataset is
  committed + reproducible, unlike the 2b-4 room logs — so the report is fully reproducible).
- [ ] Read the findings: which decision buckets have the highest disagreement rate + mean gap;
  the top opportunities. Add a 3-5 line "what this says for the next reranker/belief work" note to
  the report (aimed, honest — cross-link 2b-2b ablation + 2b-4 NO-GO). Cross-reference the source
  prototype (external clone) as provenance.
- [ ] Full suite once: green + 1 xfailed (known). `git diff main --stat` → merge decision.

## Self-review (writing-plans)

- Spec coverage: classify/bucket→Task 1, loader/render/CLI→Task 2, run+report→Task 3. ✓
- Ported with the OLD loader + OLD fixed counts REMOVED (works on any rollout dataset). ✓
- No overlap with diagnostics-v0 (different input + question). ✓
- Fail-closed invariants preserved from the source. ✓
- Honest-limitations framing (offline optimistic teacher, not a gate) in the report. ✓

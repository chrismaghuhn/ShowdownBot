# Teacher-Disagreement Atlas — where the heuristic diverges from the rollout teacher

**Status:** forward-port of the crown jewel of the user's external Decision-Error-Atlas prototype
(`Showdown-Bot-Analysis-Clone`, branch `codex/decision-error-atlas`, base 9af3dbb — STALE), onto
current main and the CURRENT 300-game 2b-2.5a dataset. The clone's log-signal detectors are NOT
ported (diagnostics-v0 already covers that ground); only the rollout-teacher-disagreement mining
is ported, because it is genuinely new and directly answers the post-2b-4 question.

## Motivation

2b-4 returned NO-GO (the LightGBM reranker is not certified stronger) and 2b-2b showed its feature
basis is thin. The open strategic question is **where** a better reranker (or later belief/search)
would gain the most. The rollout teacher already labels every candidate with `teacher_best` and
`value_gap_to_best`. Mining WHERE the current heuristic's chosen action disagrees with the teacher
— and how large the value gap is — ranks the decision types with the most exploitable regret. This
is aimed measurement, not a gate.

## Approach (ported from the clone's REFINED live `rollout_metrics.py` — TOPSET model)

**Important:** port the clone's LIVE `tools/analysis/rollout_metrics.py::analyze_rollout_decisions`
(the topset model), NOT the older plan-doc Task 5 snapshot. The snapshot's single-best model
compares one chosen row vs one teacher_best row and does `if value_gap_to_best < 0: raise` — but
OUR labels store `value_gap_to_best = v - best ≤ 0` (teacher.py), so the snapshot would raise on
nearly every real row. The topset model handles this correctly and treats ties on both sides.

Load the committed 2b-2.5a dataset (`data/datasets/phase3-slice2b25a/dataset.jsonl.gz`, 17458 rows
/ 299 games) via `learning.dataset.load_rows`, group by `metadata.decision_id`, and per decision:

- **heuristic topset** = the set of `candidate_index` where `label.chosen_by_current_heuristic`.
  **teacher topset** = the set where `label.teacher_best`.
- **forced** — `len(rows) == 1`. **multi_candidate** — the rest (the topset-rate denominator).
- **heuristic_ties** / **teacher_ties** — counted when the respective topset has >1 member.
- **topset disagreement** — the two topsets are DISJOINT (no shared candidate_index). Rate over
  multi_candidate.
- **strict-unique choice** — a multi_candidate decision with exactly ONE heuristic row AND exactly
  ONE teacher row (the clean subset used for the bucket breakdowns). **strict disagreement** = its
  topsets disjoint. `disagreement_rate` = strict_disagreements / strict_unique_choices.
- **regret_gap = max(0.0, -raw_value_gap)** (flip the ≤0 sign to a ≥0 regret magnitude). Bucketing
  keys from the chosen row's features: turn bucket, game_mode, action signature, speed_control_state,
  threat bucket, candidate_count, response_entropy bucket, heuristic-confidence bucket
  (score_gap_to_second — must be ≥0 on a strict-unique heuristic row else raise). Per bucket:
  decisions / agreements / disagreements / disagreement_rate / mean_disagreement_regret. Rank the
  **high-value opportunities**: regret_gap > 0 AND ≥ the 90th nearest-rank percentile of
  disagreement regret_gaps.

Corpus block (ported field names): decisions, forced, multi_candidate, heuristic_ties, teacher_ties,
strict_unique_choices, topset_agreements, topset_disagreements, strict_agreements,
strict_disagreements. Plus topset_disagreement_rate, strict_disagreement_rate, high_value_threshold,
breakdown_scope="strict_unique_choices". Fail-closed: `_validate_decisions`/`_validate_row` (typed
field checks), score_gap ≥0 on strict-unique, `_validate_output_numbers` (finite outputs).

## Output

`teacher_disagreement_atlas(dataset_path) -> dict` (deterministic, sorted keys) + a markdown
renderer. A CLI writes `reports/2026-07-11-teacher-disagreement-atlas.{md,json}`. The report states
its denominators explicitly and carries the honest-limitations framing: teacher-disagreement is an
OFFLINE regret signal (the teacher is a one-step counterfactual rollout, optimistic — see the 2b-2a
caveat), NOT a proven play error and NOT a strength claim. It identifies WHERE regret concentrates,
to aim the next reranker/belief work.

## Reconciliation with existing code

- `eval/diagnostics.py` (diagnostics-v0): log-based tactical detectors + candidate-vs-baseline
  bucket delta. DIFFERENT input (battle logs) + DIFFERENT question (habit changes). No overlap;
  this new module sits alongside it in `eval/`.
- Loader: use `learning.dataset.load_rows` (the repo's own schema-validated loader), NOT the
  clone's `atlas_inputs` (which hard-codes the old 100-game counts). No fixed corpus-count asserts
  — the atlas works on any rollout dataset; it reports the counts it finds.

## Non-goals

The clone's T4 log-signal detectors (covered by diagnostics-v0), the T4 matchup/tera atlas, the
combined orchestrator, the held-out guards (we load a committed training dataset, not eval runs).
No new data, no training, no gate.

## Testing strategy

Fixture-based + a real-dataset smoke. Unit tests on fabricated decision groups (forced / tie /
genuine / disagreement classification; the exactly-one-chosen and ≥1-teacher-best raises; the 90th
percentile threshold; bucket rate math; deterministic markdown). A real-dataset structure test
asserts the atlas runs on the committed 2b-2.5a dataset and returns internally-consistent counts
(forced + tie + genuine == total decisions; disagreements ≤ genuine).

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

## Approach (ported + re-aimed)

Load the committed 2b-2.5a dataset (`data/datasets/phase3-slice2b25a/dataset.jsonl.gz`, 17458 rows
/ 299 games) via `learning.dataset.load_rows`, group rows by `metadata.decision_id`, and classify
each decision deterministically:

- **forced** — a single candidate (nothing to choose). Excluded from the rate denominator.
- **teacher-tie** — multiple `teacher_best` rows (the teacher is indifferent). Excluded.
- **genuine choice** — >1 candidate, exactly one `teacher_best`. The denominator.
- **disagreement** — a genuine choice where the heuristic's chosen candidate
  (`label.chosen_by_current_heuristic`) is NOT the `teacher_best`.

For each genuine choice, record `value_gap_to_best` (the chosen candidate's regret vs the teacher's
best) and bucketing keys derived from the chosen candidate's features: turn bucket, game_mode,
action signature (slot1+slot2 action types + protect count), speed_control_state, threat bucket
(ko_threatened_count), candidate_count, opponent_response_entropy bucket, heuristic-confidence
bucket (score_gap_to_second). Per bucket, report decisions / disagreements / disagreement_rate /
mean disagreement gap. Rank the **high-value disagreement opportunities** (value_gap ≥ the 90th
nearest-rank percentile of positive disagreement gaps).

Fail-closed invariants (ported from the clone): exactly one chosen row per decision (else raise);
≥1 teacher_best per decision (else raise); finite non-negative gaps (else raise).

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

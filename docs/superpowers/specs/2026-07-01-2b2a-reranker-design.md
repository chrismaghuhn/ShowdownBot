# Slice 2b-2a — Feature-Limited Offline Reranker Baseline (design)

> **Status:** design, approved-with-refinements 2026-07-01. **2b-2a is a feature-limited
> LOWER-BOUND experiment.** It must NOT be used as the final judgment on reranker viability —
> ~29 of 74 feature columns are constant in the 2b-0 export (move semantics dead because the
> gauntlet ran with `move_meta=None`). 2b-2a proves the train→eval→manifest pipeline and a lower
> bound on model quality on the **45 live features**; the feature-extractor fix is a separate slice.
>
> **Sequence:** **2b-2a** (this) → **2b-2.5** (feature-extractor fix: revive the dead columns,
> regenerate the dataset) → **2b-2b** (same model/eval on enriched features; ablation 45-live vs
> enriched). **Offline only — no shadow, no live wiring, no override.**

## 1. Goal & success definition

Build the smallest honest offline reranker that answers ONE question: **can the full
dataset → feature-allowlist → groupwise LambdaRank → eval → manifest pipeline produce a model
that beats the heuristic on regret-vs-teacher, on real decisions, using only the live features?**

- **Win (GO):** test mean regret < heuristic mean regret AND ATTACK-only regret < heuristic ATTACK
  regret (gates below). ⇒ pipeline works; 2b-2.5 feature fix is then a quality boost, not a blocker.
- **No-win:** NOT an architecture failure. The next hypothesis becomes "features too poor" → prioritize
  2b-2.5. The report must say this explicitly.

## 2. Invariants this slice obeys

- **INV-6 No label leakage (hard, tested):** model input = a subset of `schema.FEATURE_COLUMNS` only.
  Everything in `schema.LABEL_KEYS` and the outcome-bearing `METADATA_KEYS` is forbidden as a feature.
  `value_gap_to_best` etc. are used **only** to derive the training **label/relevance** (the target `y`),
  never as an input feature `X` — that distinction is the whole point of a teacher.
- **INV-7 Model-artifact safety:** the artifact carries `dataset_sha256`, `feature_schema_hash`,
  `training_config_hash`, `eval_report_path` (+ the extra provenance in §7).
- **Groupwise only:** `group` = the candidate rows of one `decision_id`. Never an independent
  per-row binary classifier.
- **Near-equal-safe:** relevance bucketing (§5) gives equal-value alternatives equal top relevance;
  the GATE is continuous **regret-vs-teacher**, never exact-match.
- **No live behavior change:** nothing here is imported by `battle/`; no shadow, no override.

## 3. Module layout (new modules; do NOT touch `features.py`/`baseline_eval.py`)

`learning/features.py` (JSONL export extractor) and `baseline_eval.py` (2b-1 baseline) stay **stable**.

| New module | Responsibility |
|---|---|
| `learning/reranker_features.py` | `FEATURE_ALLOWLIST`, `LABEL_DENYLIST`, `METADATA_DENYLIST` constants · `build_feature_matrix(decisions, *, feature_names=None) -> FeatureMatrix` · `feature_schema_hash(feature_names)` · the INV-6 fail-fast guard |
| `learning/reranker_train.py` | `train_lambdarank(matrix, config) -> (booster, manifest)` + `main()` CLI; writes the model + `manifest.json` |
| `learning/reranker_eval.py` | `evaluate_reranker(booster, decisions) -> RerankerMetrics` (model vs heuristic regret + slice metrics) + `format_report` + CLI. **Independent of `baseline_eval.py`** (may import shared regret helpers, but does not bloat it). |

Artifacts: `models/reranker/2026-07-01-2b2a-attack-lgbm.txt` (LightGBM text dump) + `models/reranker/2026-07-01-2b2a-attack-manifest.json` + `reports/2026-07-01-2b2a-reranker-offline-eval.md`. (Model files are small text — committable; if large, gitignore + manifest only, like the dataset.)

## 4. Feature allowlist / denylist (INV-6)

Two **separate** filters, both reported:

1. **INV-6 denylist (leakage — never a feature):**
   - `LABEL_DENYLIST = schema.LABEL_KEYS` = `{teacher_best, teacher_rank, heuristic_rank,
     value_gap_to_best, counterfactual_value_raw, counterfactual_value_normalized_within_decision,
     counterfactual_rank, chosen_by_current_heuristic}`.
   - `METADATA_DENYLIST` = outcome/identity metadata = `{game_outcome, winner, final_turn, game_id,
     decision_id, candidate_index, teacher_version, teacher_trace, teacher_config, config_hash,
     git_sha, team_hash, schema_version, feature_extractor_version}`.
   - **Allowed heuristic features** (the model's main correction signal): the heuristic *scores/gaps*
     in `HEURISTIC_FEATURES` (`heuristic_aggregate_score`, `score_gap_*`, `score_*_vs_opp`,
     `predicted_*_damage`, `out_in_ratio`, …) ARE features. Only the heuristic *rank* is a label.
2. **Constant-column drop (data quality, 2b-2a-specific):** the 29 columns that are constant in the
   2b-0 export are dropped from the active feature set and listed as `dropped_constant_columns`
   in the manifest. They are revived in 2b-2.5. (LightGBM would ignore them anyway; dropping makes
   the active set honest and the schema hash meaningful.)

`FEATURE_ALLOWLIST` = `FEATURE_COLUMNS − LABEL_DENYLIST − METADATA_DENYLIST` (structurally none of
`FEATURE_COLUMNS` overlaps the denylists except the documented `format_id`, which is constant here
and thus dropped anyway). The **active feature set** = `FEATURE_ALLOWLIST − dropped_constant_columns`
(the ~45 live columns), computed from the data passed in, and frozen into `feature_schema_hash`.

**INV-6 fail-fast guard:** `build_feature_matrix` asserts `set(feature_names) & (LABEL_DENYLIST |
METADATA_DENYLIST) == ∅` and reads feature values **only** from `row["features"]` (never `row["label"]`
or `row["metadata"]`). Violation → `ValueError`. (Tested — §8.)

## 5. Data extraction → ranking matrix

`build_feature_matrix(decisions, *, feature_names=None) -> FeatureMatrix` where
`FeatureMatrix = (X: list[list[float]], group_sizes: list[int], relevance: list[int],
feature_names: list[str], categorical_feature_names: list[str],
decision_keys: list[tuple[str, str]])`:

- `decision_keys` are `(game_id, decision_id)` tuples — **never bare `decision_id`** (it can collide
  across games; 2b-1 keys on `(game_id, decision_id)` for exactly this reason).
- Iterate decisions **in order**; each decision contributes one group (its candidate rows, sorted by
  `candidate_index`); `group_sizes` records the per-decision candidate count for LightGBM's `group`.
- `X[i][j]` = `row["features"][feature_names[j]]`, coerced to float. **Categorical** low-cardinality
  ids — only the live ones: `slot1_move_id, slot2_move_id, slot1_action_type, slot2_action_type,
  slot1_target_kind, slot2_target_kind` — are integer-encoded via a **fixed, persisted** string→int
  map (`UNK` for unseen) **AND passed to LightGBM as `categorical_feature`** (by name/index) so the
  model treats them as categorical, NOT ordinal (otherwise `protect=1 < tackle=2 < moonblast=3` is
  semantic nonsense). The manifest stores **both** `categorical_encodings` (the maps) and
  `categorical_feature_names`. **If the training wrapper cannot pass them as categorical, these columns
  MUST be excluded from the active set or explicitly flagged experimental in the report — never fed as
  plain ordinals.** No one-hot in v1.
- **Relevance (training target `y`, near-equal-safe), from `value_gap_to_best` (≤ 0):**
  ```
  gap == 0            -> 4   (best + teacher ties + zero-gap alts all get top relevance)
  -0.5 <= gap < 0     -> 3   (near-equal)
  -2.0 <= gap < -0.5  -> 2
  -5.0 <= gap < -2.0  -> 1
  gap < -5.0          -> 0
  ```
  **Relevance is the training signal only. The GATE is regret-vs-teacher (§6). NDCG is an auxiliary
  training/early-stopping metric, NOT the success definition.** A model with higher NDCG but worse
  regret does NOT pass.

## 6. Training set, model, eval, gates

**Training decision filter (ATTACK-first — precise):** a decision enters training iff it is
`multi-candidate ∧ exactly-1 teacher_best ∧ exactly-1 chosen_by_current_heuristic` (the 2b-1
strict-unique set) **AND** `action_class(decision.chosen_row()) == "attack"`. **All candidate rows of
a qualifying decision stay in the group** — we filter *decisions* by the heuristic's chosen class, we
do **not** filter candidates inside a decision (filtering candidates would teach the ranker an
artificial choice world). zero-gap-nonbest candidates inside these strict decisions still occur and
are handled by the relevance bucketing.

- **Primary model 2b-2a:** ATTACK-filtered strict decisions, LightGBM `objective="lambdarank"`,
  `group` = candidates/decision, small/regularized (≈643 ATTACK decisions: shallow `num_leaves`,
  conservative `min_data_in_leaf`, modest `n_estimators`).
- **Optional comparison (not default):** an all-strict model (same filter minus the attack clause).
- **Early stopping:** may use LightGBM's native `ndcg` eval on the val split — that is fine and simple.
  **Custom regret-vs-teacher is mandatory in eval/gate but need NOT be the early-stopping metric.**
- **Split:** the 2b-1 `split_by_game(seed=42)` — train on train games, early-stop on val, report on
  test. No decision/game leak (already enforced by 2b-1).

**Eval (`reranker_eval.py`):** for each decision, score every candidate, `model_choice` = argmax
score, `model_regret` = `|value_gap_to_best|` of `model_choice`; `heuristic_regret` = `|value_gap|` of
the chosen row. **Gates (all must hold on the test set):**
```
model mean regret        <  heuristic mean regret
ATTACK-only mean regret   <  heuristic ATTACK mean regret
wrong-but-near-equal      <=  heuristic (no damage on equivalent swaps)
NO improvement that comes only from forced/protect/trivial decisions
report includes: strict-unique-multi ablation, contestable-only ablation,
                 INV-6 feature allowlist + denylist
```
Side metrics (reported, not gating): topset agreement, override-rate / override-correctness,
zero-gap-safe rate, NDCG (auxiliary).

**`format_report` MUST emit two fixed interpretation lines (not optional prose):**
- always: *"2b-2a uses feature-limited 45-live-feature input; this is a lower-bound experiment, not a
  final judgment on reranker viability."*
- on NO-WIN (any gate fails): *"NO-GO for this feature-limited model, NOT NO-GO for the reranker
  architecture. Next hypothesis: feature-extractor quality (→ slice 2b-2.5)."*

## 7. Artifacts & manifest (INV-7)

`manifest.json` MUST contain — base: `dataset_sha256`, `feature_schema_hash`,
`training_config_hash`, `model_type` (`lightgbm-lambdarank`), `split_seed` (42), `metrics_summary`,
`git_sha`, `eval_report_path`. **Plus (required for later live/shadow integration):**
- `feature_names` — the exact ordered active feature list fed to the model.
- `categorical_feature_names` — the columns LightGBM was told to treat as categorical.
- `categorical_encodings` — the persisted string→int maps for those categorical features.
- `dropped_constant_columns` — the 29 dead columns dropped in 2b-2a.
- `denied_columns_checked` — the INV-6 denylist the builder enforced.
- `training_decision_filter` — a human-readable string of the §6 filter (e.g.
  `"multi ∧ unique-teacher-best ∧ unique-chosen ∧ chosen action_class==attack"`).

`feature_names` is mandatory: without it, a later live/shadow run cannot know which columns, in which
order, went into the model.

**`dataset_sha256` is COMPUTED by the trainer** from the input dataset file (the same uncompressed
JSONL the loader reads, or the `.gz` decompressed), written to the manifest. When the canonical 2b-0
dataset is used, the trainer compares the computed hash to the expected `62f156b1…` and aborts/loudly
warns on mismatch. **Never blind-hardcode the hash** — otherwise a different JSONL could be trained
while the manifest still claims the canonical hash.

## 8. Tests & acceptance

- `test_reranker_features_rejects_label_leakage` (**INV-6, required, fail-fast**): pass
  `feature_names` containing a forbidden column (e.g. `teacher_best`, `teacher_rank`, `heuristic_rank`,
  `value_gap_to_best`, `counterfactual_value_raw`, `game_id`, `decision_id`) → expect `ValueError`.
- `build_feature_matrix`: group_sizes sum to row count; relevance bucketing maps the 5 gap bands
  correctly; categorical encoding is deterministic + reproduces from the persisted map; reads only
  `row["features"]`.
- `split` reuse: train/val/test groups disjoint by game (reuse 2b-1 guarantee).
- training smoke: trains on a tiny synthetic groupwise fixture, produces a booster, writes a manifest
  with all required fields.
- eval: model vs heuristic regret math on a hand-built fixture; ATTACK-only / contestable-only slices.
- **Acceptance:** full suite green; the leakage test fails-fast; a small end-to-end run
  (features → train → eval → manifest + report) completes; the report states the 2b-2a lower-bound
  caveat and the GO/NO-GO against the §6 gates. **No live behavior change** (nothing in `battle/`
  imports the reranker modules).

## 9. Dependencies

`lightgbm` + `numpy` are added as **offline/learning-only** deps (e.g. a `[learning]` optional extra
in `pyproject` / `requirements-dev.txt` + a `pip install -e ".[learning]"` doc note) — **not** a
live-runtime requirement. A normal bot run must not import lightgbm. The live-inference question
(load lightgbm live vs. export a light pure-Python/numpy predictor from the tree dump) is **deferred
to 2b-3** (shadow mode) and only noted here.

## 10. Explicitly deferred

- **2b-2.5** — feature-extractor fix: pass `move_meta` (and species/priority/tera/screens sources)
  into the export so the ~29 dead columns populate; regenerate a 100g (or 200g) dataset v2; re-QA.
- **2b-2b** — retrain the same model/eval on enriched features; ablation 45-live vs enriched.
- **2b-3** — shadow mode (compute heuristic + reranker live, use heuristic, log overrides) + the
  live-inference/format decision.
- **2b-4** — narrow gated attack-only override (safety-floor veto).

# 2b-2b — Feature Ablation + tera_used Diagnosis

**Status:** roadmap slice after 2b-2.5a + T4c (merged). Purpose: learn WHICH feature classes
drive the reranker's win over the heuristic, so future feature work (2b-2.5b class-B capture,
belief V2) is aimed, not guessed. Plus: resolve the `tera_used` open item.

## Problem

2b-2.5a reactivated 17 columns and passed the KPI (dropped_constant 28→7), but we do NOT know
which of the ~66 live features actually MATTER for the gate (ATTACK-strict model_regret <
heuristic_regret). LightGBM's built-in gain/split importance ranks features for the model's
internal fit, but that is not the same as marginal contribution to the *gate metric* on the
held-back test split. We want a causal, gate-aligned ranking.

## Approach (decided)

**Leave-one-class-out (LOCO) retraining** — primary. Group the live features into semantic
classes; for each class, retrain the model with that whole class removed from the feature set
(everything else identical: same dataset, same split seed, same LightGBM params, same
categorical handling) and re-measure the ATTACK-strict gate metrics. The delta vs the full
model = that class's marginal contribution. A class whose removal barely moves regret is a
candidate for pruning; a class whose removal breaks the gate is load-bearing.

**Single-class-only (SCO)** — secondary diagnostic, same loop, cheap: train with ONLY that
class. Shows standalone signal. Reported alongside LOCO but not a gate.

Determinism: the pipeline already fixes the split seed (seed=42 by-game) and LightGBM params.
Every ablation run reuses them; the full-model row must reproduce the committed 2b-2.5a numbers
exactly (a self-check — if it doesn't, the harness is wrong, fail loud).

### Feature classes (grouped by semantic prefix; the harness derives membership from the live
feature set at runtime so it never references a dead/absent column)

- **weather_terrain** — field_weather, trick_room_active, tailwind_ours, tailwind_opp
- **move_desc** — slot{1,2}_move_type/move_category/priority/is_damaging/is_protect
- **species_id** — slot{1,2}_actor_species_id/switch_target_species_id/target_species_id_if_known
- **mirror** — mirror_flag
- **damage** — the predicted-damage / threat features (prefix-matched; enumerated in the plan
  from schema.FEATURE_COLUMNS at build time, not hardcoded)
- **speed** — speed/priority-order features
- **board** — HP / fainted / board-state counters
- **protect** — protect-related live features
- **misc** — every live feature not captured above (explicitly listed in the report so nothing
  is silently unclassified)

The harness asserts the classes PARTITION the live feature set (no overlap, no omission) —
`misc` absorbs the remainder and the report prints its members so classification gaps are
visible, not hidden.

## tera_used sub-investigation

`tera_used` stays constant-False despite 3/4 hero teams defining a Tera Type. Leading
hypothesis (from the 2b-2.5a report): the rollout teacher's top-6 candidate truncation
(`teacher.py` cfg.top_k=6 / `rollout.py`) drops tera-overlay candidates before export, so the
exported candidate rows never include a tera action. Deliverable: a READ-ONLY diagnosis that
either confirms the truncation cause (with code trace) or finds the real cause, and a
recommendation (fixable in a future capture slice vs genuinely rare). If — and only if — a
fix is small, safe, and byte-neutral to existing recorded runs, note it; do NOT implement a
data-regenerating change in this slice (that would be a new datagen round, out of scope).

## Non-goals

No new battles/datagen (uses the committed 2b-2.5a dataset). No new production features. No
class-B capture (that's 2b-2.5b). No change to the shipped model or the gate definition — the
ablation is an offline analysis tool + report. tera_used is diagnosed, not fixed here.

## Testing strategy

Offline, deterministic. Unit tests: class partition is exhaustive+disjoint; LOCO with an empty
removal == full model (identity); the full-model self-check reproduces committed numbers;
a synthetic tiny dataset drives the loop without LightGBM flakiness where possible. The real
ablation run is a committed report artifact + the harness, not a golden byte-check (LightGBM
outputs can vary across platforms — pin the RANKING conclusions in prose, the raw numbers in a
JSON sidecar).

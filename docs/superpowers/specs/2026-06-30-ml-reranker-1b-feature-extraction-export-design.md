# Phase 3, Slice 1b: Real feature extraction + self-play JSONL export — Design

**Goal:** Instrument the real decision pipeline **read-only** so that, per decision,
the top-K candidate joint-actions are exported as **schema-valid JSONL rows** — all
four feature groups fully populated from the *same* values the bot decided on, plus
deterministic IDs and provenance. No model, no training, no reranker, and **no
internal turn-simulator** (that is slice 1c).

**Status:** approved-with-refinements (brainstorming, 2026-06-30). Slice 1b of
Phase 3. Consumes the frozen contract + pure teacher from slice 1a
(`learning/schema.py`, `learning/teacher.py`). Builds on
`docs/superpowers/specs/2026-06-29-ml-reranker-data-slice-design.md`.

## Scope / non-goals

**In:** the read-only decision `trace`, an additive `OutcomeBreakdown` from the
scorer, feature extraction of the 4 groups, deterministic IDs + provenance, the
`DatasetExporter` (sampling + sorted JSONL), and a thin optional `client/` hook.

**Out — explicitly slice 1c:** the internal turn-simulator (state-driven `decide`
for both sides, `apply_outcome → next BattleState`, the H-step rollout, limited-view
boundaries) and therefore the **real** counterfactual silver labels. Also out (later
slices): the model, training, reranker integration, hybrid terminal-MC.

**1b ships real *features* with a stub label.** That is deliberate: it proves the
feature contract matches real decisions, is leak-free, and serializes
deterministically — de-risking 1c — without building the invasive simulator.

## Dependency rule (hard)

```
battle/   has NO learning dependency.
learning/ may read battle DTOs.
client/   may optionally wire the learning exporter.
```

`battle/decision.py` knows only `DecisionTrace`. `client/` knows the optional
`DatasetExporter`. `learning/export.py` knows JSONL. Export logic never lives in
`battle/`.

## Architecture — modules

| File | Responsibility |
|---|---|
| `battle/decision_trace.py` | **Plain DTOs**, no logic / no JSONL / no learning import: `CandidateTrace` and `DecisionTrace`. |
| `battle/evaluate.py` | **Additive:** `OutcomeBreakdown` DTO + `score_outcome_with_breakdown(...) -> (float, OutcomeBreakdown)` wrapper. The existing `score_outcome` return type and all current call-sites are unchanged. |
| `battle/decision.py` | **Additive:** `trace: DecisionTrace \| None = None` (mirrors the existing `report=` pattern). `trace=None` ⇒ zero behaviour change. The `score_plan` loop retains the `OutcomeBreakdown`s it already produces. **`decision.py` never sees the exporter.** |
| `learning/features.py` | `extract_features(trace, state, request, context) -> list[Row]` — maps a decision to one `schema.Row` per candidate. Pure. |
| `learning/export.py` | `DatasetExporter` (+ `SamplingPolicy`, ID generation, `add` / `flush_sorted`, JSONL writer). |
| `client/runner.py`, `client/gauntlet.py` | Thin hook: build a `DecisionTrace`, pass `trace=` into the decision, then optionally call `exporter.observe_decision(...)`. `exporter=None` ⇒ runtime bit-identical. |

## DTOs

```python
# battle/decision_trace.py
@dataclass
class CandidateTrace:
    candidate_id: str          # stable label of the joint action
    joint_action: JointAction
    rank: int                  # 0 = heuristic's top (by aggregate score)
    aggregate_score: float
    score_vector: list[float]              # one score per opponent response (parallel to R)
    outcome_breakdowns: list[OutcomeBreakdown]  # parallel to opponent responses
    aggregate_breakdown: OutcomeBreakdown       # the representative/aggregate breakdown

@dataclass
class DecisionTrace:
    game_mode: str | None = None
    chosen_candidate_id: str | None = None
    opponent_responses: list = field(default_factory=list)        # R (candidate-independent)
    opponent_response_weights: list[float] = field(default_factory=list)
    candidates: list[CandidateTrace] = field(default_factory=list)

# DecisionTrace.candidates stores ONLY the exported top-K, already sorted by
# heuristic rank then candidate_id — the trace matches the export exactly (no
# separate slicing step). If full-candidate debugging is needed later, add an
# explicit opt-in flag; v1 stores top-K only.

# battle/evaluate.py
@dataclass
class OutcomeBreakdown:
    total_score: float = 0.0          # INVARIANT anchor: == the scalar score_outcome value
    predicted_outgoing_damage: float = 0.0
    predicted_incoming_damage: float = 0.0
    ko_secured_count: int = 0
    ko_threatened_count: int = 0
    survives_for_sure_count: int = 0
    protect_stall_penalty: float = 0.0
    partner_abandon_penalty: float = 0.0
    fakeout_invalid_penalty: float = 0.0
    action_economy_score: float = 0.0
```

`R` (the candidate-independent opponent response set) is `predict_responses`' output,
computed **once per decision** and identical for every candidate — the no-leak
property falls out for free.

## Feature extraction — sources + the no-drift guardrail

`extract_features` receives an explicit `FeatureContext` (no loose params drifting
in over time). It lives in `learning/` and bundles the provenance/IDs (which also
become metadata) plus the read-only reference tools the deterministic feature reads
need:

```python
# learning/features.py
@dataclass
class FeatureContext:
    # provenance / IDs (also written to metadata)
    run_id: str; game_id: str; decision_id: str
    decision_local_index: int; turn_number: int; our_side: str
    format_id: str; team_hash: str; config_hash: str
    git_sha: str; dirty_flag: bool
    teacher_config: dict; sampling_policy: str
    mirror_flag: bool
    # read-only reference tools for G1/G2/G4 (static lookups, never re-scoring)
    dex: object | None = None; move_meta: object | None = None
    speed_oracle: object | None = None; priors: object | None = None
```

Every `schema.FEATURE_COLUMNS` entry maps to **exactly one** source; the
"all-4-groups-populated" test enforces full coverage.

- **Group 1 (decision context)** and **Group 2 (candidate action)** and the
  **speed/tempo reads of Group 4** (`we_outspeed_count`, `they_outspeed_count`,
  `speed_tie_count`, `*_fastest_active_speed`, `must_react_reason_flags`,
  `protect_prior_*`, `response_count`, `opponent_response_entropy`): deterministic
  reads of `state` / `request` / `dex`+`MoveMeta` / `speed_oracle` / `mode` /
  priors. These are **not** re-scoring, so no drift concern.
- **Group 3 (heuristic/eval)** and `value_range_across_opp_responses` (Group 4):
  derived **only** from the trace — `CandidateTrace.score_vector` (aggregate score,
  score gaps, min/mean/var/worst, value range) and the `OutcomeBreakdown`s
  (predicted in/out, KOs, survives, the penalty breakdown).

> **No-drift guardrail (verbatim spec rule):** No recomputation in
> `learning/features.py`. Every eval-internal feature comes from the *same*
> `score_outcome` path that produced the candidate score (via the trace's
> `OutcomeBreakdown`). If a feature cannot be emitted from the scoring path, it is
> not computed separately in `learning/`.

**`aggregate_breakdown` reduction (per game-mode — the scalar eval features must
stay consistent with `aggregate_score`, whose aggregation differs by mode):**
- **worst-case modes (`MUST_REACT`):** `aggregate_breakdown` = the breakdown of the
  **selected worst response** (the one that sets the score). A test asserts the
  chosen response index matches `policy.aggregate_scores`.
- **mean / weighted-mean modes (`NEUTRAL` / `AHEAD`):** no single response is
  selected, so `aggregate_breakdown` = the **weighted reduction** of the
  per-response breakdowns (same weights as the score). A test asserts it equals the
  weighted reduction, not `response[0]`.
- **mean-minus-variance:** the scalar score uses `mean − λ·var`;
  `aggregate_breakdown` stores the **weighted-mean** components, and the variance /
  risk lives in the separate Group-4 features (`score_var_vs_opp`,
  `value_range_across_opp_responses`).

**No nulls — sentinels for optional features.** Some columns are semantically
optional (e.g. `slot{1,2}_switch_target_species_id`,
`slot{1,2}_target_species_id_if_known` are absent on a Protect or a non-switch).
"Fully populated" must not collide with these, so:

> No feature value is null. Optional **categorical** features use `"__none__"`
> (genuinely not applicable) or `"__unknown__"` (applicable but not yet revealed);
> optional **numeric** slot/target features use `-1`; optional **bool** features
> use `false`. The sentinels are part of the frozen contract and asserted by a test.

**No leakage:** features contain only decision-time info. `game_outcome` / `winner`
/ future fields live in metadata, never features (already enforced by
`schema.validate_row`; re-asserted by a 1b test).

## IDs, metadata, determinism

All dataset IDs are **deterministic** — no UUIDs, wall-clock, or process-local
randomness in exported rows.

```
run_id      = sha1(git_sha + dirty_flag + team_hash + config_hash + run_seed)
game_id     = sha1(run_id + game_index)
decision_id = sha1(game_id + decision_local_index + turn_number + our_side)
candidate_index = heuristic rank order (0 = top aggregate score; tie-break by candidate_id)
```

`decision_local_index` is a per-game monotonic counter (robust to >1 decision per
turn/side and to replays). Provenance: `format_id` (from request), `team_hash =
sha1(packed_team)`, `git_sha = git rev-parse HEAD` (+ dirty flag), `config_hash =
sha1(canonical dump of {weights, risk_lambda, rollout_horizon, protect knobs,
likely_sets file hash, our_spreads, OPP_SETS/OPP_SPEED})`.

**Byte-identical determinism requires stable sorting, not just deterministic IDs:**
- candidates sorted by heuristic rank, then `candidate_id`;
- rows sorted by `(game_id, decision_id, candidate_index)` at `flush_sorted()`;
- JSON `sort_keys=True` (already in `schema.to_jsonl_line`);
- no wall-clock timestamps, no unseeded randomness, no order-dependent dict iteration.

> With identical code, config, teams, seed, and sampling policy, export is
> **byte-identical**.

## Stub label (1b is not trainable)

1b binds the *pure* `label_decision` from slice 1a with **heuristic values on both
sides** — `label_decision(heuristic_values, heuristic_values, heuristic_choice_id)`.
This is H=0 and circular by construction; it exists only to satisfy
`schema.validate_row` (labels are required) and to exercise the pipeline. It is
marked **non-trainable** so no one mistakes 1b JSONL for a real teacher dataset:

```
metadata.teacher_config = {teacher_version: "stub-h0", trainable_label: false, ...}
```

The real (deeper, non-circular) silver labels arrive in slice 1c.

## Export flow

```
trace = DecisionTrace() if exporter is not None else None   # no exporter ⇒ no trace overhead, default
choice = choose_with_fallback(req, ..., trace=trace)
if exporter is not None:
    exporter.observe_decision(trace=trace, state=<stable snapshot>, request=req, context=ctx)
...
exporter.flush_sorted()   # at run end: stable sort + write JSONL
```

- **`exporter=None` ⇒ runtime is bit-identical** to today (the safety gate — same
  chosen action, no JSONL). `exporter on` ⇒ same choices **plus** JSONL.
- **`observe_decision` extracts Rows immediately** from a **stable state snapshot**
  (deep-copied or extracted before any further mutation). Only **finished Rows** are
  buffered — never `(trace, state)` for later extraction (state mutates between
  turns and async/WebSocket timing must not affect features or row order).
- `DatasetExporter` takes already-finished artifacts, so it unit-tests with a
  fake trace/state. It never starts battles itself.

**Sampling (v1):** `SamplingPolicy` is wired (seeded), but v1 default is
`sample_policy="all"` — the stub teacher is cheap, so there is no volume pressure;
the rate machinery (`decision_sampling_rate`, `random_seed`) exists for 1c's
expensive real teacher. (Every-Nth / disagreement-heavy are later.)

## Testing

**Pure / fake (no Node, the bulk):**
- `features.extract_features` from a recorded fixture `DecisionTrace`: all 4 groups
  fully populated; no feature key is an outcome/future field; every candidate of a
  `decision_id` shares identical Group-1 features (group consistency).
- `DatasetExporter` determinism: same fake rows + seed ⇒ **byte-identical** JSONL;
  every emitted row passes `schema.validate_row`; rows are stably sorted.
- **Breakdown no-drift (exact):** `score, bd = score_outcome_with_breakdown(...)` ⇒
  `assert bd.total_score == score` on hand-built outcomes (the precise anchor that
  makes "no drift" testable), plus KO/survive counts correct on a known outcome.
- **Mean-aggregation breakdown:** for a mean / weighted-mean mode,
  `aggregate_breakdown` equals the **weighted reduction** of the per-response
  breakdowns — not `response[0]`; for `MUST_REACT`, it equals the worst response's
  breakdown (index matches `aggregate_scores`).
- **Sentinel / no-null:** every feature value is non-null; optional fields carry the
  documented sentinels (`"__none__"` / `"__unknown__"` / `-1` / `false`) — e.g. a
  Protect candidate's `slot_switch_target_species_id` is `"__none__"`.
- **Trace-off equivalence:** `heuristic_choose_for_request(..., trace=None)` and
  `heuristic_choose_for_request(..., trace=DecisionTrace())` return the **identical
  chosen action** — populating the trace must not perturb the decision (the real
  behaviour-risk point, since `decision.py` sees only the trace).

**Required hermetic E2E** — `test_decision_trace_to_jsonl_row_e2e` (recorded/fake
decision fixture + fake oracle, no live Node, deterministic `run_seed`): drive the
real `heuristic_choose_for_request(..., trace=...)` through the exporter; then
- the chosen action is **identical with `exporter=None` vs enabled** (the primary
  safety assert at the export level; the trace-level gate is the Trace-off
  equivalence test above);
- the trace is fully populated; every row is schema-valid;
- JSONL is byte-identical on a re-run with the same seed.

**Optional manual smoke (not CI, not an exit gate):** a local Node gauntlet with the
exporter enabled; assert JSONL emits and validates.

## Exit criteria

- a real self-play/gauntlet decision is captured read-only;
- top-K candidates + score vectors are exported;
- all 4 feature groups are fully populated (no nulls; optional fields carry the
  documented sentinels) from the trace/eval path;
- every row validates via `learning/schema.py`;
- the deterministic (byte-identical) export test is green;
- the stub label is present and **clearly marked non-trainable** (`trainable_label:
  false`, `teacher_version: "stub-h0"`);
- no battle-outcome leakage into features;
- runtime is bit-identical both ways: `trace=None` vs trace-enabled **and**
  `exporter=None` vs enabled produce the identical chosen action;
- `observe_decision` extracts rows immediately from a stable state snapshot.

## File structure (for the plan)

- New: `battle/decision_trace.py`, `learning/features.py`, `learning/export.py`;
  tests `tests/test_decision_trace.py`, `tests/test_features.py`,
  `tests/test_export.py`, `tests/test_outcome_breakdown.py`, and the E2E
  `tests/test_export_e2e.py`.
- Modify (additive only): `battle/evaluate.py` (`OutcomeBreakdown` +
  `score_outcome_with_breakdown`), `battle/decision.py` (`trace=` param + retain
  breakdowns), `client/runner.py` + `client/gauntlet.py` (optional exporter hook).

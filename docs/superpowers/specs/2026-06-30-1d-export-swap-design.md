# Phase 3 Slice 1d: Export-Swap (stub-h0 → real rollout teacher) — Design

**Goal:** Make the 1b offline dataset export emit REAL, trainable counterfactual labels from
the 1c H-loop teacher (`rollout_labels`) instead of the `stub-h0` placeholder — selectable by
env, with the stub mode preserved byte-identically. The bot can then turn sampled self-play /
gauntlet decisions into a schema-valid, deterministic JSONL dataset with `trainable_label=true`.

**Status:** brainstorming, 2026-06-30, on `main` (1a+1b+1c merged, suite 386). Next slice after
this. Strictly local, never pushed.

## Where stub-h0 lives today (grounded)
- [features.py:581](showdown_bot/src/showdown_bot/learning/features.py) `_metadata` hardcodes
  `teacher_version="stub-h0"`; `_stub_label()` zeroes all 8 `LABEL_KEYS`; `extract_features`
  builds each Row with both. **`features.py` is not label-agnostic today — that is the smell.**
- [export_runtime.py:34](showdown_bot/src/showdown_bot/learning/export_runtime.py)
  `teacher_config = {"teacher_version":"stub-h0","trainable_label":False}`.
- `LABEL_KEYS` == the 8 keys `label_decision` returns → 1:1 mapping, and `validate_row` enforces
  the exact set (no drift possible).

## Architecture — a `LabelProvider` seam (three layers, cleanly separated)
```
features.py            label-AGNOSTIC: builds features + metadata; the per-candidate LABEL and
                       teacher_version come from injected inputs, never hardcoded.
LabelProvider          a Protocol with two impls: StubLabelProvider (= today, byte-identical) and
                       RolloutLabelProvider (1c rollout_labels -> real labels).
DatasetExportRuntime   owns the provider (stub|rollout via env) + ONE calc + book/our_spreads/
                       opp_sets/dex/move_meta/likely_sets/move_priors/RolloutConfig + the skip
                       counters; threads the provider's output through observe -> driver ->
                       extract_features. `battle/` untouched; the DatasetExporter stays dumb.
```

### The `LabelProvider` Protocol (pinned)
```python
class LabelProvider(Protocol):
    def teacher_config(self) -> dict: ...
        # run-level: {"teacher_version": ..., "trainable_label": bool, ["rollout_config": {...}]}
    def labels_for_decision(self, trace, state, request, *, context) -> dict[str, dict]: ...
        # returns {candidate_id: label_dict(exactly LABEL_KEYS)}.
        # MAY raise RolloutLabelError (recoverable -> the whole decision is skipped).
```
- **StubLabelProvider:** `teacher_config()` = `{"teacher_version":"stub-h0","trainable_label":False}`;
  `labels_for_decision` = `{c.candidate_id: zeroed_label for c in trace.candidates}` (ALL
  candidates). Byte-identical to today.
- **RolloutLabelProvider:** `teacher_config()` = `{"teacher_version": f"rollout-h{H}-v1",
  "trainable_label": True, "rollout_config": {...}}`; `labels_for_decision` builds the belief +
  calls `rollout_labels` → `{candidate_id: label}` for the top-K; raises `RolloutLabelError` on
  the recoverable cases.

### Driver + extract_features flow (pinned)
```python
# maybe_observe_decision (driver):
if not sampled: return 0
try:
    labels = provider.labels_for_decision(trace, state, request, context=ctx)
except RolloutLabelError as e:
    runtime.note_skip(reason=e); return 0           # skip WHOLE decision, no rows, counted
rows = extract_features(trace, state, request, ctx, labels=labels)
for row in rows: exporter.add(row)                  # add() validates -> hard-fail on wrong shape
return len(rows)
```
- `extract_features(trace, state, request, ctx, *, labels)` becomes label-agnostic: for each
  `cand in trace.candidates` **whose `candidate_id` is in `labels`**, emit one Row using
  `labels[cand.candidate_id]`; `_metadata` reads `teacher_version` from `ctx.teacher_config`
  (no longer hardcoded). **Candidate set emitted == the provider's labeled set.**

## Top-K alignment (hard rule)
The candidate set that gets rows == the candidate set the provider labeled:
- **Stub:** labels ALL `trace.candidates` → all emitted (byte-identical to today).
- **Rollout:** `rollout_labels` labels `trace.candidates[:cfg.top_k]` (a prefix) → exactly those
  emitted. `candidate_index` = the candidate's position in `trace.candidates`.
- The labeled set MUST be a prefix of `trace.candidates` (no gaps). If `extract_features` finds
  an emitted candidate whose `candidate_id` is missing from `labels` when it should be present
  (provider bug), that is a **hard-fail**, not a partial export. Never half-export some
  candidate rows of a decision and drop others silently.

## Deps assembly — explicitly mirrored from `battle/decision.py`
The rollout's `resolve` needs a `DamageModel(state, …, book, oracle, …)`. The deps derive from a
single `calc`, exactly as the live decision builds them
([decision.py:182-186](showdown_bot/src/showdown_bot/battle/decision.py)):
```
calc                       (one CalcClient, owned by the runtime, REUSED across decisions)
oracle        = DamageOracle(calc)
speed_oracle  = SpeedOracle(stats_backend=calc.backend)
book / our_spreads / opp_sets   (threaded from the gauntlet client: self.book/our_spreads/opp_sets)
```
`RolloutLabelProvider` constructs `deps` **using the same construction pattern as
`battle/decision.py`** (not merely "similar") so the rollout's turn-0 reward matches the
decision's evaluation (1c's H=0 gate guarantees turn-0 reward == decision eval when deps match).
A test/review note pins this construction against `decision.py`. `root_our_side = context.our_side`
(already passed to `observe`); `known_team = request.side.pokemon` (already passed to `observe`);
opponent belief via `build_opponent_belief(state, opp, likely_sets, move_priors, speed_oracle)` —
limited-view stays structurally guaranteed (the export only CALLS the 1c builder, it can't bypass
the no-`known_team` boundary).

## Error policy — skip-with-threshold, conservative taxonomy, never silent-stub
A NEW `RolloutLabelError` (recoverable). **Recoverable → skip the whole decision** (zero rows,
increment skip counter, log reason). Held NARROW:
- no opponent responses;
- all responses filtered/unsupported (e.g. all-switch R drained);
- `chosen_candidate_id` not in the rollout candidate set;
- missing belief for a currently-active revealed mon;
- a known rollout unsupported state.

**Everything else hard-fails immediately** (NOT skipped — `except Exception` must never be
treated as skip):
- `schema.validate_row` failure / wrong `LABEL_KEYS`;
- `trainable_label=true` paired with a stub teacher_version;
- provenance / config-hash construction failure;
- any unexpected exception, type/programming error.

`rollout_labels` (1c) is extended to raise `RolloutLabelError` for its known recoverable cases
(today it raises plain `ValueError`); the exact `ValueError → RolloutLabelError` mapping is a
small, pinned 1c-rollout touch (the taxonomy above). **No silent stub fallback:** in rollout
mode a sampled decision emits real trainable rollout labels OR emits no rows — never stub-h0.

Threshold (configurable, strict default): `max_rollout_skip_rate = 0.05`,
`min_sampled_decisions_before_threshold = 20`. After each decision / at flush: if
`sampled >= 20 and skipped/sampled > 0.05` → **hard-fail** the run. Counters are deterministic
and reported in the runtime summary/log.

## Determinism
`config_hash` is extended to include: the `rollout_config` (H/γ/top_k/use_leaf), a content hash
of `move_priors`, and a content hash of `likely_sets`. (Today it has `top_k:6` + heuristic
knobs.) `rollout_labels` is deterministic (1c gate); no wall-clock / uuid / random; SamplingPolicy
gates BEFORE label computation so expensive rollouts only run for sampled decisions.

## Metadata
`teacher_version = f"rollout-h{H}-v1"`, `trainable_label=true`, `rollout_config` inside
`teacher_config`. **`belief_quality` is omitted in 1d** — `METADATA_KEYS` is frozen, `teacher_config`
is run/config-level (not per-mon/per-decision), and belief-quality is per-mon. It stays
internal/debug-only; trainability is represented by `teacher_version != "stub-h0"` +
`trainable_label=true`. A later slice may export belief-quality if training needs it as a
weight/filter.

## Decomposition (the plan will cut it)
- **1d-1 — LabelProvider seam:** the `LabelProvider` Protocol + `StubLabelProvider`;
  `extract_features` becomes label-agnostic (`labels=` param; `teacher_version` from
  `ctx.teacher_config`). **Gate: stub mode byte-identical to today** (all 1b export tests green;
  `LABEL_KEYS` exactly validated).
- **1d-2 — RolloutLabelProvider:** deps assembly (mirror `decision.py`: calc→oracle/speed_oracle
  + book/our_spreads/opp_sets) + belief building for both sides + `rollout_labels` call +
  `RolloutLabelError` taxonomy (in `rollout.py`) + skip-with-threshold counters +
  `trainable_label=true` / `teacher_version="rollout-h{H}-v1"`.
- **1d-3 — Runtime / gauntlet wiring:** env mode `stub|rollout`; `RolloutConfig` from env/config;
  `likely_sets` + `move_priors` loading; `config_hash` extension; thread calc/book/our_spreads/
  opp_sets/dex/move_meta through `from_env`/`observe`; the hermetic E2E
  (trace → belief → rollout labels → Rows → byte-identical JSONL with `trainable_label=true`).

## Acceptance criteria (hard gates)
- StubProvider mode is **byte-identical** to the current stub-h0 export.
- RolloutProvider emits `trainable_label=true` and `teacher_version="rollout-h{H}-v1"`.
- A rollout failure (`RolloutLabelError`) emits **zero rows** and increments the skip counter.
- **No silent stub fallback** in rollout mode (skipped decision never emits trainable rows).
- Skip rate above threshold **hard-fails**; below threshold the export continues.
- Wrong label shape / wrong `LABEL_KEYS` / `trainable+stub` **hard-fail immediately**.
- Byte-identical JSONL still holds (deterministic; `config_hash` covers rollout_config + belief
  hashes).
- `exporter=None` remains runtime **bit-identical** (export off → unchanged behaviour).
- `battle/` still has **no** `learning/` dependency.
- Full hermetic E2E: `trace → build_belief_for_side → rollout_labels → Rows → JSONL`, asserting
  trainable labels + determinism + the limited-view belief tests still pass.

## Non-goals (hard)
No model, no training, no reranker, no push, no `battle/ → learning/` import, no new simulator
scope. The DatasetExporter stays dumb (finished Rows only). Stub mode stays valid. The teacher is
wired ONLY in the runtime/provider layer.

## Uncertain spots to ground in the plan
1. The exact `ValueError → RolloutLabelError` mapping in `rollout.py` (which raises are
   recoverable vs bugs) — small, pinned 1c touch; keep the recoverable set narrow.
2. `extract_features` emitting per labeled candidate (the prefix rule) — confirm `trace.candidates`
   ordering + that `rollout_labels`' `cfg.top_k` slice is a clean prefix; `candidate_index` stays
   the trace position.
3. `CalcClient` cost — one-build-reuse is required; measure rollout cost under SamplingPolicy in
   a real gauntlet (cost, not correctness).

# 1d Rollout-Export — Probe Report (2026-06-30)

A real probe of the merged 1d export path: real 2v2 VGC decision → DecisionTrace → `rollout_labels`
with a **real Node CalcClient** → schema-valid JSONL. Hermetic (no live Showdown server), driven by
the test-suite's realistic fixture (Incineroar+Rillaboom vs Flutter Mane+Tornadus), format
`gen9vgc2026regi`. No JSONL data committed — this report is the durable record.

## Commands / Env (actually used)
```
SHOWDOWN_DATASET_EXPORT=<scratchpad>/dataset_probe/probe_run1.jsonl
SHOWDOWN_DATASET_TEACHER=rollout
SHOWDOWN_ROLLOUT_HORIZON=1
SHOWDOWN_DATASET_SAMPLE_POLICY=all
SHOWDOWN_DATASET_RUN_SEED=0
real CalcClient (node calc.mjs) — confirmed working (Incineroar→[Fire,Dark], Flutter Mane→[Ghost,Fairy])
```

## Results
- **Decisions:** 1 sampled · **0 skipped** · 6 rows (6 candidates, all labeled).
- **Output:** 6 lines, 17,899 bytes.
- **Metadata:** `teacher_version="rollout-h1-v1"` · `teacher_config.trainable_label=true` ·
  `rollout_config={H:1,gamma:0.75,top_k:6,use_leaf:true}` · deterministic `decision_id`/`game_id`.
- **config_hash:** `82eaa488e170f4a9` — stable across both runs.
- **Determinism:** run1 sha == run2 sha (`f13a2d54…`) — **byte-identical**.
- **Label keys:** exactly `LABEL_KEYS`. No None / NaN. Not all-zero. Example spread:
  ```
  counterfactual_value_raw:   [7.06, 5.37, 4.95, 4.71, 4.52, 4.22]
  normalized_within_decision: [1.92, 0.23, -0.19, -0.42, -0.62, -0.92]
  value_gap_to_best:          [0.0, -1.69, -2.11, -2.35, -2.54, -2.84]
  teacher_rank: [0..5]   teacher_best: [True, F×5]   chosen=(Protect,Protect)
  ```
- **No stub-h0 in rollout mode; no silent stub fallback.**

## Runtime cost (the one real finding)
- `decide_s = 4.2s` (the real turn-0 decision).
- **`observe_s = 145.9s` for ONE decision** (6 candidates, H=1) — ~146s/sampled-decision.
- Cause: **one-shot `node calc.mjs` subprocess per resolve/decide/leaf** (~100ms startup × ~120
  calc-batches/decision at H=1/top_k=6). Dominated by Node-process startup, not the calc itself.
- ⇒ a training-sized dataset (≈1000 decisions ≈ 40h) is impractical until the calc backend is
  persistent. `CalcClient` already anticipates this ("Phase 2: persistent Node process").

## Bug found + fixed (why the review/probe cadence matters)
**Production crash on switch candidates:** `build_known_side` (1c-D) keyed its roster by the full
`slot.ident` (`"p1: Flutter Mane"`), but `battle/actions.py` switch `target_ident` is the
ident-suffix (`"Flutter Mane"`), so `simulator._apply_switches`' `roster[target_ident]` lookup
crashed for any rollout where a switch candidate was in the top-K. Masked by all prior tests (fake
deps / no real switch through the apply path). **Fix:** `build_known_side` keys all four maps by
`slot.ident.split(": ",1)[-1]`. Merged to main (no-ff), +3 regression tests (incl. a path-level
`apply_outcome_to_state` switch test that reproduced the crash), suite 402→405.

## Go/No-Go for Slice 2
- **Functional: GO** — the path produces real, schema-valid, deterministic, trainable labels.
- **Cost prerequisite:** land a **persistent CalcClient backend (Slice 2a)** before generating a
  training-sized dataset; then Slice 2b (model + training). Small smoke datasets (heavy sampling,
  H=1) are usable now.

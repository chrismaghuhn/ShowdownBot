# Slice 2b-3a — Reranker Shadow Mode — Smoke Report (2026-07-01)

Hermetic end-to-end smoke of the shadow path: a real heuristic decision (populated `DecisionTrace`) →
`RerankerShadowRuntime.observe_shadow` with the **committed 2b-2a model** → one ShadowTrace row. Run via
the test `decision_fixture` (no live server), `SHOWDOWN_RERANKER_SHADOW=1` pointed at
`models/reranker/2026-07-01-2b2a-attack-{lgbm.txt,manifest.json}`. No JSONL committed — this is the record.

## Real ShadowTrace row (representative)
```
actual_choose_string : /choose move 3, move 3|2      (the SENT command — unchanged by shadow)
candidate_count      : 6
heuristic_choice_index: 0     reranker_choice_index: 3     diverged: True
model_top_margin     : 0.0    (reranker's top pick tied with idx 4,5 — argmax took the first)
fallback_reason      : None   (scored cleanly)
feature_context_mode : 2b2a_move_meta_none
runtime_feature_schema_hash == training_feature_schema_hash  (efce5d60adb4e9a4)
shadow_latency_ms    : 1.6    (budget 50 ms; post-send anyway)
```

## What the smoke proves
- **The shadow works live, log-only:** a real decision produces a full ShadowTrace row; the sent
  `choose` is unaffected (structural — the hook runs after `conn.send`).
- **Feature-parity design validated in the exact tricky case:** this fixture has the **29 columns that
  were dead in 2b-2a training now POPULATED** (`move_meta` present). They appear in `extra_live_features`
  and raise `feature_parity_warnings`, but are **not fed to the model** — the model reads only its 45
  `manifest.feature_names`. `runtime_feature_schema_hash == training_feature_schema_hash`; no schema
  mismatch, no garbage-scoring. This is precisely the drift the review worried about, handled correctly.
- **Divergence signal is real:** heuristic idx 0 vs reranker idx 3 — the kind of live divergence the
  slice is meant to collect for a later (2b-4) override decision.
- **Latency:** ~1.6 ms scoring; the gauntlet hook additionally hard-bounds it via
  `asyncio.wait_for(to_thread, timeout=50ms)` off the event loop.

## Status
Slice 2b-3a complete (Tasks 0–5). Suite 466 green. `battle/` has no reranker import (INV-1). Shadow is
default-off, gauntlet-only, log-only. **This is NOT a playing-strength result** — divergence/parity/
latency telemetry only; a real override (2b-4) stays blocked until a diverse-opponent eval harness exists.

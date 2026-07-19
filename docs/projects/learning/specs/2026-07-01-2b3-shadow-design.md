# Slice 2b-3 — Reranker Shadow Mode (design)

> **Status:** design, 2026-07-01. **2b-3a = gauntlet-only shadow.** The reranker's choice is computed
> live and **logged only** — it is NEVER used to play. First time the reranker touches the live path.
> Log-only, zero risk (runs AFTER the server command is sent). `runner.py`/ladder shadow = **2b-3b**,
> deferred until gauntlet shadow is stable.

## 1. Goal

Measure — on the real live path, without changing a single action — how often and where the 2b-2a
reranker's top pick **diverges** from the heuristic's chosen action, and whether the divergences look
sensible. This is the honest next step after the (caveated, offline) 2b-2a GO: it produces the
divergence + feature-parity telemetry needed to later decide (2b-4) whether a narrow override is worth
trying. **No override, no behavior change.**

**2b-3 Shadow is NOT a playing-strength proof.** It measures live parity, latency, divergence, and
logging quality — nothing about winrate. Any real override (2b-4) is **blocked** until a separate
diverse-opponent evaluation harness exists; a pretty divergence report must never be misread as
"GO override".

## 2. Hard scope (all of these hold)

```
gauntlet-only · env-gated · default OFF · post-send observe_shadow
shared DecisionTrace with DatasetExportRuntime · eager model/manifest load
manifest feature_names ONLY · move_meta=None parity mode · per-decision JSONL append
fail-safe no-score · NO override · NO behavior change
```

## 3. Hard rules (spec invariants)

1. **Post-send.** Shadow runs only AFTER `conn.send(room|choose)` (gauntlet.py:177). The action is
   already on the wire before any shadow code executes → **zero current-action latency, structurally no
   override.** NB: post-send is *not* zero event-loop cost — `observe_shadow` runs synchronously in the
   client loop, so it must be bounded/non-blocking (rule 6) or it delays *future* message handling.
6. **Bounded / non-blocking.** `observe_shadow` is best-effort and time-bounded. If scoring exceeds
   `SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS` (default 50) it writes `fallback_reason="shadow_timeout"` and
   skips scoring; it must not block the client loop beyond that budget. Prediction is expected < 5 ms,
   but the timeout is an **acceptance criterion (§10)**, not just a trace field.
2. **Never touch the choose string.** Shadow may not write, replace, or mutate `choose`. It reads it.
3. **candidate_index parity.** ShadowTrace uses the `candidate_index` from the **same feature-row order**
   as the JSONL export (the trace's candidate order). No free-form candidate id as the primary key.
4. **Fail-safe.** If the model / manifest / features don't exactly fit → log `fallback_reason`,
   **no-score, no crash, no action change.**
5. **LightGBM import is confined to the ShadowRuntime**, and only when shadow is enabled. A normal bot
   run with `SHOWDOWN_RERANKER_SHADOW=0` must NOT import lightgbm and must NOT die if lightgbm is absent.

## 4. Invariants (northstar)

- **INV-1 (live allowlist):** `battle/` is **untouched**. The only live-code change is one gate line in
  `client/gauntlet.py` (extend the `trace_obj` condition to `_shadow`). All shadow logic lives in a new
  `learning/` runtime, mirroring `DatasetExportRuntime`.
- **INV-3 (anytime):** shadow is post-send telemetry; it cannot delay or alter the action.
- **INV-7 (artifact safety):** the runtime checks the model's `feature_schema_hash` against the runtime
  feature schema; mismatch → no-score + `fallback_reason` (never garbage-scored play — and there is no
  play impact anyway since it's log-only).

## 5. Architecture / seam-map

```
gauntlet.py handle_request:
  trace_obj = DecisionTrace() if ((_export is not None OR _shadow is not None)
                                   and agent == "heuristic" and state is not None) else None   [Z.162 — CHANGED]
  choose = agent_choose(... trace=trace_obj)
  conn.send(room|choose)                                   [Z.177 — action sent]
  ── post-send, best-effort (try/except each) ──
  if _export is not None:  _export.observe(trace=trace_obj, …)                 [Z.179 — unchanged]
  if _shadow is not None:  _shadow.observe_shadow(trace=trace_obj, state, request,
                                                  choose=choose, turn_number=…, our_side=…)   [NEW]
```

- **One shared `trace_obj`** serves both export and shadow (rule: never build two traces → no divergence).
  Both may be on, either may be on, or neither (→ `trace_obj=None`, bit-identical to today).
- `battle/decision.py`, `heuristic_choose_for_request`, `_choose_best` — **all unchanged.**

## 6. `learning/reranker_shadow.py` — `RerankerShadowRuntime`

New module, mirrors `DatasetExportRuntime`. **Imports lightgbm lazily inside `from_env` only.**

- **`from_env(*, format_id, dex=None, move_meta=None) -> RerankerShadowRuntime | None`:**
  - Returns `None` unless `SHOWDOWN_RERANKER_SHADOW` is truthy (→ no shadow, no lightgbm import).
  - When enabled: **eager-load** the model + manifest from `SHOWDOWN_RERANKER_MODEL_PATH` /
    `SHOWDOWN_RERANKER_MANIFEST_PATH`. Import lightgbm here. On ANY failure (missing model/manifest,
    lightgbm import error, malformed manifest) → **log one warning, return `None`** (shadow disabled,
    battle runs heuristically). No lazy first-battle load.
  - Reads from the manifest: `feature_names`, `categorical_feature_names`, `categorical_encodings`,
    `feature_schema_hash`, `dataset_sha256`, `git_sha`. Opens the `SHOWDOWN_RERANKER_SHADOW_LOG` JSONL
    for append.
  - **INV-7 schema check (eager, at load — the ONLY schema gate):**
    ```
    runtime_feature_schema_hash = feature_schema_hash(manifest.feature_names,
                                                      manifest.categorical_feature_names)
    require runtime_feature_schema_hash == manifest.feature_schema_hash      # manifest self-consistency
    require booster.feature_name()      == manifest.feature_names            # model <-> manifest
    ```
    The runtime schema hash is derived **only from the manifest** — NEVER from live rows / live active
    columns / live values. **Do NOT call `active_feature_names(live_rows)`** anywhere in the shadow path
    (that would let extra/dead-now-live live columns falsely trip a mismatch and kill legitimate runs).
    Extra live features and dead-now-live columns are **diagnostics only** (§7), never a schema mismatch.
    On failure of either check → `from_env` returns `None` (`fallback_reason="feature_schema_hash_mismatch"`
    logged once).
  - **`move_meta` is pinned to `None`** for this model (2b-2a training parity) regardless of what the
    caller passes; the FeatureContext is built with `move_meta=None` and tagged
    `feature_context_mode="2b2a_move_meta_none"`.
- **`observe_shadow(*, trace, state, request, choose, turn_number, our_side) -> None`:**
  1. Build a `FeatureContext` via `build_feature_context(...)` with `move_meta=None` (same IDs as export:
     game_id/decision_id via the decision indices).
  2. **Reuse the export feature path:** `extract_features(trace, state, request, ctx, labels=<placeholder
     covering every trace candidate>)` → one schema Row per candidate, in candidate_index order. Only
     `row.features` is used; the placeholder label is discarded. (Guarantees byte-identical feature rows
     to the JSONL export by construction.)
  3. **Build model vectors from `manifest.feature_names` ONLY**, applying `manifest.categorical_encodings`
     (unseen → UNK). Extra live feature columns are ignored; the 29 dropped/dead columns never enter.
     Reuse `reranker_features.build_feature_matrix(feature_names=…, encodings=…)` (or a thin scorer with
     identical semantics).
  4. `booster.predict(X)` → per-candidate scores. `reranker_choice_index = argmax`.
     `heuristic_choice_index` = the candidate whose action matches the sent `choose` string / the trace's
     chosen action. **Fail-safe — never guess:** if the `choose` string cannot be matched to **exactly
     one** trace candidate (joint-action / Tera / switch / pass-forced / ordering subtleties), write
     `fallback_reason="heuristic_choice_not_in_trace"` (zero matches) or `"ambiguous_heuristic_choice_match"`
     (>1 match) and set `diverged=null` (no-divergence claim). Model scores may still be logged, but
     divergence is not asserted.
  5. Compute parity fields (schema-hash compare, missing/extra features, feature_vector_hash).
  6. **Append one ShadowTrace JSONL row** (§7). Line-buffered; no fsync; wrapped in try/except.
  - Any failure at 1–5 → write a ShadowTrace row with `fallback_reason` set and
    `shadow_enabled_but_not_scored=true` (no scores). **Never raises to the caller** (the gauntlet hook
    also wraps it in try/except, belt-and-suspenders).
- **Indices:** `start_game()` / per-decision index management mirrors `DatasetExportRuntime` so
  `decision_id`/`game_id` line up with any concurrent export.

## 7. ShadowTrace schema (per decision, JSONL append)

```
game_id, decision_id, turn_number, our_side
actual_choose_string          # exactly the sent command (choose)
heuristic_choice_index        # candidate_index the heuristic played
reranker_choice_index         # candidate_index of the model argmax (LOGGED ONLY)
diverged                      # reranker_choice_index != heuristic_choice_index
candidate_count
candidate_indices             # [0,1,2,...] in feature-row order
model_scores                  # [{"candidate_index": 0, "score": ...}, ...]  (index, not free id)
model_top_margin              # score#1 - score#2
# --- INV-7 identity / parity ---
model_dataset_sha256, model_git_sha
training_feature_schema_hash  # = manifest.feature_schema_hash
runtime_feature_schema_hash   # = feature_schema_hash(manifest.feature_names, manifest.categorical_feature_names)
                              #   — manifest-DERIVED, never from live columns/values (see §6 INV-7 check)
manifest_feature_names_hash
feature_vector_hash
missing_model_features        # manifest feature_names absent from the live row (diagnostic)
extra_live_features           # live feature columns not in the model (diagnostic)
dropped_constant_columns_present_values   # 2b-2a-dropped columns that carry a value live (diagnostic).
                              # EXACT "now_nondefault" only if the manifest provides dropped_constant_values
                              # (the 2b-2a manifest does NOT) — otherwise this is nonempty/present-only, NOT a
                              # true "changed vs training constant" claim. Never a schema mismatch (§6).
feature_context_mode          # "2b2a_move_meta_none"
feature_parity_warnings       # e.g. ["train-dead column X now live"]
# --- fail-safe ---
fallback_reason               # null when scored, else the reason (see §8)
shadow_enabled_but_not_scored # true when fallback_reason is set
shadow_latency_ms             # scoring time (post-send; informational for 2b-4)
```

## 8. Fail-safe — each → `fallback_reason`, no-score, no crash, no action change

```
model_file_missing · manifest_missing · lightgbm_import_failed
feature_schema_hash_mismatch                                          (→ from_env returns None, one warning)
feature_name_missing_in_row · extract_features_error · predict_error · shadow_timeout
heuristic_choice_not_in_trace · ambiguous_heuristic_choice_match      (→ scores may log, diverged=null)
categorical_value_unseen  → mapped to UNK (NORMAL, not a fallback)
```
`SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS` (default 50) bounds the scoring; exceeding it → `shadow_timeout`
fallback. (Post-send, so it never affects play — but it prepares the pre-send budget needed for 2b-4.)

## 9. Config (env)

```
SHOWDOWN_RERANKER_SHADOW=1                                           # enable (default off)
SHOWDOWN_RERANKER_MODEL_PATH=models/reranker/2026-07-01-2b2a-attack-lgbm.txt
SHOWDOWN_RERANKER_MANIFEST_PATH=models/reranker/2026-07-01-2b2a-attack-manifest.json
SHOWDOWN_RERANKER_SHADOW_LOG=logs/reranker_shadow/<run>.jsonl
SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS=50                               # optional
```

## 10. Tests & acceptance

- **No-override / bit-identical (the core safety test):** for the same decision, the command sent by the
  gauntlet client is **identical** with shadow ON vs OFF. (Structurally guaranteed — shadow is post-send —
  but pinned by a test.)
- **lightgbm-not-imported-when-off:** with `SHOWDOWN_RERANKER_SHADOW` unset, importing the client /
  running a decision does NOT import lightgbm (assert `"lightgbm" not in sys.modules`) and does not fail
  if lightgbm is absent.
- **Shared trace:** with both export and shadow on, exactly one `DecisionTrace` is built and both consume
  it; with only shadow on, the trace is still built; with neither, `trace_obj is None` (bit-identical).
- **Feature parity:** the model vector built by the shadow for a candidate equals the vector built from
  the JSONL export row for the same candidate (same `feature_names` + `encodings`).
- **Label-independence (protects INV-6 at the extraction boundary):** changing the placeholder labels
  passed to `extract_features` does NOT change any `row["features"]` value; and only `row["features"]`
  (never `row["metadata"]`/`row["label"]`) enters the model `X`.
- **Bounded scoring (rule 6 acceptance):** with a stubbed slow scorer, `observe_shadow` respects
  `SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS` — it writes `fallback_reason="shadow_timeout"` and returns without
  blocking beyond the budget; the decision + sent command are unaffected.
- **Heuristic-match fallback:** a `choose` string that matches zero / >1 trace candidates yields
  `fallback_reason="heuristic_choice_not_in_trace"` / `"ambiguous_heuristic_choice_match"` and `diverged=null`
  (the heuristic index is never guessed).
- **Fail-safe paths:** missing model / manifest / schema-hash-mismatch / predict error each →
  `RerankerShadowRuntime.from_env` returns `None` OR `observe_shadow` writes a `fallback_reason` row;
  the decision and the sent command are unaffected in every case.
- **ShadowTrace shape:** a scored decision writes a row with all §7 fields; `diverged` correct;
  `model_scores` keyed by `candidate_index`.
- **Acceptance:** full suite green; a small gauntlet run with shadow on produces a ShadowTrace JSONL with
  divergence + parity telemetry; `battle/` has no reranker import; a normal (shadow-off) run is
  bit-identical and lightgbm-free.

## 11. Explicitly deferred

- **2b-3b** — `runner.py` / ladder shadow (after gauntlet shadow is stable).
- **2b-4** — narrow gated attack-only override (pre-send, uses the `shadow_latency_ms` budget data).
- **2b-2.5** — feature-extractor fix (populate the 29 dead columns) → retrain (the model then trained on
  enriched features; the `move_meta=None` parity pin is revisited).

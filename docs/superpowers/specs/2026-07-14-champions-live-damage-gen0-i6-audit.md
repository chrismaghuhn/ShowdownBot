# I6 — Live Damage → Calc Gen 0 (Audit / Design for Codex Review)

**Status:** DRAFT rev 3 — audit only, no implementation
**Date:** 2026-07-14
**Base commit:** `ad97c1b` (main, clean working tree)
**Builds on:** I4 (`CalcProfile`, `FormatConfig.calc_generation`, gen-0 speed oracle, pinned gen-0 damage fixture §7.1)
**Supersedes:** audit rev 1–2

---

## 0. Goal (binding scope)

Champions live decisions must use **calc generation 0** for **all** in-scope damage consumers:

1. Live heuristic (`choose_with_fallback` / `_choose_best`)
2. `max_damage` baseline (fallback chain + gauntlet agent)
3. Export / rollout runtime (`RolloutLabelProvider` inner decisions + `make_resolve`)

**Not heuristic-only.** Champions must not use gen 0 in one consumer and gen 9 in another on the same format.

Threading must be **format-driven** via existing `FormatConfig` → `CalcProfile` — no `if format_id == "gen9champions…"` in the decision core.

**Dependency key name (binding):** `calc_profile` in rollout `deps` — not `profile`. **`calc_profile` is not a `_choose_best` kwarg.**

---

## 1. I4 baseline (verified present @ `ad97c1b`)

| Artifact | State |
|----------|-------|
| `FormatConfig.calc_generation` | Loaded; Champions yaml = `0`, Reg-I yaml = `9`, missing → default `9` |
| `CalcProfile` + `calc_profile_from_config()` | Present; `None` config → `DEFAULT_CALC_PROFILE` (gen 9) |
| Speed oracle factory | `build_speed_oracle(backend, calc_profile_from_config(format_config))` at gauntlet, decision, baselines, export |
| Gen-0 bridge | `calc.mjs` reads per-request `gen`; defaults `req.gen ?? 9` |
| Pinned gen-0 damage fixture | `showdown_bot/tests/fixtures/calc_gen0_damage_upstream.json` (Body Slam, gen 0, 39–46) — **I4 bridge test only** |
| Live damage gen threading | **Not done** — all `DamageModel` / in-scope helpers still omit `gen` |

Champions format yaml (`gen9championsvgc2026regma.yaml`): `calc_generation: 0`, `stat_investment.kind: stat_points`, `max_per_stat: 32`.

---

## 2. Ist-Callgraph

### 2.1 Primary table (binding consumers)

| Consumer | Creates `DamageModel` / `DamageRequest` where | `FormatConfig` today? | `CalcProfile` today? | Damage `gen` today | I6 measure |
|----------|-----------------------------------------------|----------------------|----------------------|-------------------|------------|
| **Heuristic — single-world** | `decision._choose_best` → `DamageModel(...)` → `_request()` / helpers | Yes (`format_config` param) | Derived inside `_choose_best` for speed only | **9** | Derive `calc_profile` **once** inside `_choose_best`; pass same instance to `DamageModel`, speed oracle, game_mode, `d2_model_kwargs` |
| **Heuristic — K-world** | Same file, loop: `model_k = DamageModel(..., oracle=shared_oracle)` | Yes | Speed only | **9** | Same **single** `calc_profile` instance on every `model_k` |
| **Heuristic — depth-2** | `search.depth2_value` → `DamageModel(..., **model_kwargs)` only | Indirect (via `d2_model_kwargs`) | No | **9** | Add `calc_profile` to `d2_model_kwargs`; **no direct `DamageRequest` in `search.py`** (verified) |
| **Tera overlay** | `_maybe_tera` re-scores via existing `model.damage_fn` | Yes (`format_config.tera` gate) | No | **9** (inherits model) | Fixed when parent `DamageModel` gets `calc_profile` |
| **Report / trace side paths** | Chosen-line `evaluate_line(..., model.damage_fn)`; trace `guaranteed_ohko` / `ko_threat_counts` via `CalcClient` + raw `DamageRequest` | Yes | Speed only | **9** | Model path via `calc_profile`; game_mode batches get same `calc_profile` — **no DamageOracle refactor** |
| **`max_damage`** | `baselines.max_damage_choice` → `DamageModel(...)` | Yes | Speed only | **9** | Derive `calc_profile` from `format_config` **independently** of whether `speed_oracle` was injected |
| **Gauntlet** | `agent_choose` → `choose_with_fallback` / `max_damage_choice` | Yes | Speed only | **9** | Unchanged deps bundle; decision/baseline factories use `calc_profile` |
| **Runner** | `handle_battle_message` → `choose_with_fallback(..., format_config=cfg)` | Yes | Speed only (inside decision) | **9** | No runner change |
| **Export / rollout — resolve** | `export_runtime._build_rollout_provider` → `learning/rollout.make_resolve` → `DamageModel(...)` | Loaded in export_runtime for speed only | Not in deps today | **9** | `deps["calc_profile"]` for resolve; see §5.7 back-compat |
| **Export / rollout — inner decide** | `make_decide` → `decide_adapter.decide` → `_choose_best(..., **_core_deps(deps))` | **Stripped** by `_CORE_DEP_KEYS` | N/A (not a `_choose_best` kwarg) | **9** | Add **`format_config` only** to `_CORE_DEP_KEYS`; `_choose_best` derives `calc_profile` internally |
| **KO / survival — `DamageModel` helpers** | `evaluate.DamageModel.secures_ko`, `has_ko_chance`, `survives_for_sure` | Via model's `calc_profile` | No | **9** | All four builders: `gen=calc_profile.generation` |
| **KO / survival — game_mode** | `decision._choose_best`: `classify_game_mode`, trace `ko_threat_counts`, `_ko_secured_for` | Yes (decision) | No | **9** | Optional `calc_profile` on public functions; `_ko_request` forwards internally |

### 2.2 P1 — Export inner-decide gap (verified @ `ad97c1b`)

`learning/decide_adapter.py::_CORE_DEP_KEYS` currently:

```python
{"book", "calc", "oracle", "speed_oracle", "dex", "priors", "weights",
 "risk_lambda", "tera_margin", "rollout_horizon", "our_spreads", "opp_sets"}
```

**Missing:** `format_config`.

`decide()` and `decide_score()` call `_choose_best(..., **_core_deps(deps))`. Any key not in `_CORE_DEP_KEYS` is **silently dropped**.

**Splatt constraint (verified):** `_choose_best` accepts `format_config` but **does not** accept `calc_profile`. Therefore **`calc_profile` must not** be added to `_CORE_DEP_KEYS`. If it were, inner rollout would raise:

```text
TypeError: _choose_best() got an unexpected keyword argument 'calc_profile'
```

Therefore:

- Export can build a Champions `speed_oracle` with gen-0 stats in `_build_rollout_provider`.
- Inner rollout leaf decisions still invoke `_choose_best` **without** `format_config` → internal `calc_profile_from_config(None)` → gen-9 `DamageModel`.

**Binding I6 fix (export path):**

1. **`export_runtime._build_rollout_provider`:** load `format_cfg = load_format_config(format_id)` once; derive `calc_profile = calc_profile_from_config(format_cfg)` once.
2. **`deps["format_config"] = format_cfg`**
3. **`deps["calc_profile"] = calc_profile`** — for `make_resolve` only; **not** splatted into `_choose_best`.
4. **`decide_adapter._CORE_DEP_KEYS`:** add **`format_config` only** (not `calc_profile`).
5. **`learning/rollout.make_resolve`:** use `calc_profile` from deps with back-compat fallback (§5.7).

Inner `make_decide` path: `format_config` reaches `_choose_best` → `_choose_best` derives its single `calc_profile` once → gen-0 damage on leaf heuristic decisions.

Without step 4, step 2 alone does **not** fix inner rollout heuristics. Step 3 without step 5 leaves `make_resolve` on gen 9.

### 2.3 Secondary sites (explicit scope boundary)

| Site | Role | I6 |
|------|------|-----|
| `engine/validate.py` | Offline log validation | **OUT** |
| `scripts/*`, accuracy gates | Offline Reg-I tooling | **OUT** |
| `SpeciesDex.types_batch` | Typing lookup (hardcoded gen 9) | **OUT** |
| Trace KO → `DamageOracle` dedupe | Performance refactor | **OUT** (separate future work) |
| Tests | Unit / integration coverage | Updated **after** implementation |

### 2.4 Repo-wide construction inventory

**`DamageModel(` (production):**

- `battle/decision.py` — single-world + K-world
- `battle/baselines.py` — `max_damage_choice`
- `battle/search.py` — depth-2 turn-2 model (**no direct `DamageRequest`** — grep verified)
- `learning/rollout.py` — export rollout resolve

**`DamageRequest(` without explicit `gen` (production — all default to 9):**

- `battle/evaluate.py` — `_request`, `secures_ko`, `has_ko_chance`, `survives_for_sure`
- `engine/belief/game_mode.py` — `_ko_request`, outgoing loop in `compute_game_mode`
- `engine/validate.py` — validation (OUT)

---

## 3. Root cause (evidence)

### 3.1 Where gen 9 is set implicitly

1. **`DamageRequest.gen: int = 9`** in `engine/calc/models.py`.
2. **`DamageModel._request()`** and three named helpers — no `gen`.
3. **`game_mode._ko_request` and outgoing builders** — no `gen`.
4. **Export inner decide** — `format_config` stripped by `_core_deps()` even when parent deps carry it.

### 3.2 Why speed is already correct but damage is not

I4 wired `calc_profile_from_config(format_config)` only into **`build_speed_oracle`**. `DamageModel` never receives `calc_profile`. Export outer speed is correct; export inner `_choose_best` and `make_resolve` are not.

### 3.3 Naive-fix traps

| Partial fix | Still gen 9 at — or breaks |
|-------------|---------------------------|
| Only `_request()`, not helpers | `secures_ko`, `has_ko_chance`, `survives_for_sure` |
| Only `DamageModel`, not game_mode | `classify_game_mode`, trace KO counts |
| Only single-world path | K-world `model_k`, depth-2 `search.DamageModel` |
| Export deps without `_CORE_DEP_KEYS` | Inner rollout `_choose_best` (P1) |
| Add **`calc_profile` to `_CORE_DEP_KEYS`** | **`TypeError` on inner `_choose_best` splat** |
| Only `make_resolve`, not `format_config` in `_CORE_DEP_KEYS` | Rollout H-loop leaf decisions |
| Only heuristic, not max_damage | `baselines.max_damage_choice` |
| Global `CalcClient` gen | **No effect** — per-request `gen` in payload |

### 3.4 Cache behavior (unchanged)

`DamageOracle._key()` includes `gen` in payload. No oracle change required.

---

## 4. Format mechanics (verified claims only)

### 4.1 Gen + stat scale pairing

Champions yaml `evs` hold **Stat Point counts** (0–32). `CalcMon.evs` passes them unchanged. **`gen=0`** required for `calcStatChampions`; **`gen=9`** misinterprets SP as EVs.

### 4.2 I4 vs I6 fixture boundary

| Fixture | Owner | Purpose |
|---------|-------|---------|
| Meganium-Mega / Body Slam vs Abomasnow (39–46) | **I4** | Bridge / vendor pin — uses `-Mega` species for upstream parity |
| Non-Mega Champions panel species | **I6** | Live-model integration — base-form species from panel spreads (e.g. Garchomp, Incineroar) |

I6 must **not** use the Mega Body Slam case as a live-`DamageModel` test — I6 does not implement Mega form synthesis (OUT).

### 4.3 `DamageOracle` stays format-neutral

Per-request `gen` in payload; oracle is memoizing transport only.

---

## 5. Architecture (decided — Alternative A)

### 5.1 `DamageModel`

```python
# evaluate.py
DamageModel(..., calc_profile: CalcProfile | None = None)
self._calc_profile = calc_profile or DEFAULT_CALC_PROFILE  # gen 9 default

# All four request builders:
DamageRequest(..., gen=self._calc_profile.generation)
```

### 5.2 `_choose_best` — single profile instance

Derive **once** at top of `_choose_best`:

```python
calc_profile = calc_profile_from_config(format_config)
```

Pass the **same object** to:

- `build_speed_oracle(calc.backend, calc_profile)` (when building speed oracle)
- every `DamageModel(..., calc_profile=calc_profile)` (single-world + K-world)
- `classify_game_mode(..., calc_profile=calc_profile)` and trace KO helpers
- `d2_model_kwargs["calc_profile"] = calc_profile`

No second derivation mid-function. **`_choose_best` does not accept `calc_profile` as a parameter** — callers pass `format_config`; profile is always internal.

### 5.3 `max_damage_choice`

Derive `calc_profile = calc_profile_from_config(format_config)` **always** from `format_config`, whether or not caller injected `speed_oracle`. Injected speed oracle must not be the only source of format correctness for damage.

### 5.4 `game_mode` — no holder type

- Public functions (`ko_threat_counts`, `guaranteed_ohko`, `compute_game_mode`, `classify_game_mode`): optional `calc_profile: CalcProfile | None = None`, default `DEFAULT_CALC_PROFILE`.
- Private `_ko_request(..., calc_profile)`: receives profile from callers; sets `gen=calc_profile.generation`.
- **No `GameModeCalc` holder.**

### 5.5 Trace KO features

Keep direct `CalcClient.damage_batch` calls. Pass the same `calc_profile` from `_choose_best` for gen 0. **Do not** refactor onto shared `DamageOracle` in I6.

### 5.6 Depth-2

`calc_profile` in `d2_model_kwargs` is **sufficient**. Audit holds: `search.py` constructs `DamageModel` only via `model_kwargs` — no additional direct `DamageRequest` builders. Gate: test asserts depth-2 path emits gen 0 when profile passed.

### 5.7 Export (full chain)

```
export_runtime._build_rollout_provider
  → format_cfg = load_format_config(format_id)
  → calc_profile = calc_profile_from_config(format_cfg)
  → deps["format_config"] = format_cfg
  → deps["calc_profile"] = calc_profile          # resolve path only
  → decide_adapter._CORE_DEP_KEYS += format_config   # NOT calc_profile
  → rollout.make_resolve:
        calc_profile = deps.get("calc_profile")
                      or calc_profile_from_config(deps.get("format_config"))
  → inner decide → _core_deps(deps) → _choose_best(format_config=format_cfg)
  → _choose_best derives calc_profile once internally → gen-0 DamageModel
```

**`make_resolve` back-compat (binding):** existing direct/test callers that pass a deps dict without `calc_profile` or `format_config` continue to get `DEFAULT_CALC_PROFILE` (gen 9) via the fallback chain:

```python
calc_profile = deps.get("calc_profile") or calc_profile_from_config(deps.get("format_config"))
```

No breaking change for callers that omit both keys.

### 5.8 Rejected alternatives

- **B:** free `damage_gen: int` at every site — high drift risk.
- **C:** global `CalcClient` generation — does not propagate to damage payloads.
- **Adding `calc_profile` to `_CORE_DEP_KEYS`:** breaks inner rollout with `TypeError`.

---

## 6. IN / OUT scope

### IN

- Champions gen-0 damage: heuristic, max_damage, export (resolve **and** inner decide)
- `decide_adapter._CORE_DEP_KEYS` adds **`format_config` only** + export deps wiring (P1)
- `deps["calc_profile"]` for `make_resolve` with back-compat fallback
- Reg-I / `format_config=None` parity (gen 9)
- All four `DamageModel` request builders + game_mode live paths
- Hermetic consumer tests (gen-0 proof) + 2-battle Champions smoke (safety only)
- Latency observation only (no causal claim)

### OUT

- Mega overlay / form synthesis
- Trace KO → DamageOracle dedupe refactor
- Adding `calc_profile` as a `_choose_best` parameter or `_CORE_DEP_KEYS` member
- Strength / winrate claims
- Gen-0 proof from live smoke (smoke checks crashes/invalid/dirty only)
- New trace telemetry for gen auditing in smoke
- `validate.py`, accuracy gates, latency budget changes

---

## 7. Test and smoke gates (post-implementation)

### 7.1 Hermetic consumer tests (gen-0 proof)

| Gate | Pass criterion |
|------|----------------|
| **G1 — Profile factory** | `calc_profile_from_config(champions_cfg).generation == 0`; `None` / Reg-I → `9` |
| **G2 — DamageModel** | Fake backend: all four builders emit **`gen=0`** with Champions `calc_profile` |
| **G3 — game_mode** | `classify_game_mode` / `guaranteed_ohko` with Champions `calc_profile` emit **`gen=0`** |
| **G4 — Cache separation** | Identical payloads differing only in `gen` → distinct oracle keys |
| **G5 — I6 live-model case (non-Mega)** | Champions panel base-form species + spreads; fake backend records **`gen=0` on every `DamageModel` request**; optional real-bridge sanity on non-Mega matchup — **not** Meganium-Mega Body Slam |
| **G5b — I4 bridge (unchanged)** | Meganium-Mega Body Slam fixture through bridge — **I4 regression**, not I6 live-model claim |
| **G6 — Heuristic** | Hermetic: `_choose_best` / `choose_with_fallback` path records **`gen=0`** for Champions |
| **G7 — max_damage** | Hermetic: `max_damage_choice` records **`gen=0`** even when `speed_oracle` pre-injected |
| **G8 — Rollout resolve** | Hermetic: `make_resolve` with Champions deps → **`gen=0`** on `DamageModel` requests; caller omitting both `calc_profile` and `format_config` → **gen 9** (back-compat) |
| **G9 — Rollout inner decide** | Hermetic: `make_decide` → `decide_adapter` → `_choose_best` receives **`format_config` only** (not `calc_profile` kwarg); `_choose_best` internal derivation → inner decisions **`gen=0`**; splat does **not** pass `calc_profile` |
| **G10 — Depth-2** | With `SHOWDOWN_SEARCH_DEPTH=2`, fake backend shows **`gen=0`** via `d2_model_kwargs["calc_profile"]`; assert `search.py` has no direct `DamageRequest` construction |
| **G11 — Reg-I regression** | Existing Reg-I / `None`-config tests byte-/behavior-identical for gen-9 payloads |
| **G12 — Full suite** | `pytest` from repo root, pre-merge |

### 7.2 Live Champions smoke (safety only — no gen proof)

| Gate | Pass criterion |
|------|----------------|
| **S1 — Minimal smoke** | 2 battles, Champions format, heuristic agent |
| **S2 — Safety** | `crashes=0`, `invalid=0`, `dirty=false` |
| **S3 — Explicit non-claims** | **No** strength/winrate claim; **no** gen-0 telemetry requirement; **no** new trace fields for gen auditing |

### 7.3 Latency (observational)

Report p95/p99 before vs after; footnote only — not a merge gate.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| P1 export inner decide missed | `format_config` in `_CORE_DEP_KEYS` + G9 |
| `calc_profile` splatted into `_choose_best` | Explicit OUT; `_CORE_DEP_KEYS` excludes it; G9 asserts no splat |
| Reg-I drift | `DEFAULT_CALC_PROFILE` gen 9; G11; `make_resolve` back-compat |
| Mega fixture conflated with I6 live test | G5 vs G5b split |
| Depth-2 missed profile | G10 + verified no direct requests in search |
| Trace oracle refactor scope creep | Explicit OUT; profile-only gen threading |

---

## 9. Proposed commit boundaries (implementation phase)

1. **`feat(calc): CalcProfile in DamageModel`** — `calc_profile` param + four request sites; G2/G4.
2. **`feat(decision): wire calc_profile in _choose_best`** — single internal derivation from `format_config`; speed, models, game_mode, `d2_model_kwargs`; G3/G6/G10/G11.
3. **`feat(baselines): max_damage calc_profile`** — independent derivation; G7.
4. **`feat(export): format_config in _CORE_DEP_KEYS + rollout deps`** — export_runtime deps, `make_resolve` back-compat, **`format_config` only** in `_CORE_DEP_KEYS`; G8/G9.
5. **`test(champions): hermetic gates + safety smoke`** — G5/G5b, S1–S3, G12; optional latency note.

---

## 10. Resolved Codex decisions

| Topic | Decision |
|-------|----------|
| game_mode API | Optional `calc_profile` per public function; `_ko_request` forwards; **no holder** |
| Trace KO oracle dedupe | **OUT of I6** — keep `CalcClient` batches with `calc_profile` |
| Depth-2 scope | `calc_profile` in `d2_model_kwargs` sufficient + G10 |
| Export `_CORE_DEP_KEYS` | **`format_config` only** — not `calc_profile` (`_choose_best` has no such param) |
| Export `deps["calc_profile"]` | For **`make_resolve` only**; inner decide uses `format_config` → internal derivation |
| `make_resolve` back-compat | `deps.get("calc_profile") or calc_profile_from_config(deps.get("format_config"))` |
| Smoke | Hermetic tests prove gen 0; live smoke = 2 battles safety only |
| Mega Body Slam fixture | **I4 bridge only**; I6 uses non-Mega panel case |

---

## 11. Audit checklist (self-review)

- [x] No placeholders
- [x] No `if champions` / `format_id` branch in decision core
- [x] No silent gen-9 on Champions path when `format_config` is present
- [x] P1 export: `format_config` in `_CORE_DEP_KEYS`; **`calc_profile` excluded** (splatt constraint)
- [x] Dependency key **`calc_profile`** in rollout deps (not `profile`)
- [x] G5 split: I4 Mega bridge vs I6 non-Mega live-model + fake gen proof
- [x] G9 / §5.7: inner decide via `format_config`; no `calc_profile` kwarg to `_choose_best`
- [x] `make_resolve` back-compat documented
- [x] Smoke separated: hermetic gen proof vs 2-battle safety smoke
- [x] No Mega overlay, strength, or gen proof from live smoke

---

## 12. Summary for Codex (rev 3)

**Root cause confirmed:** `DamageRequest.gen` defaults to 9; I4 threaded `CalcProfile` to speed only.

**P1 fix (rev 3 correction):** Export inner rollout drops `format_config` via `_core_deps()`. **`calc_profile` cannot be added to `_CORE_DEP_KEYS`** because `_core_deps()` splats into `_choose_best`, which accepts `format_config` but not `calc_profile`. Binding wiring:

- `deps["format_config"]` + `deps["calc_profile"]`
- `_CORE_DEP_KEYS` += **`format_config` only**
- Inner decide: `_choose_best(format_config=…)` → derives `calc_profile` once internally
- `make_resolve`: `deps.get("calc_profile") or calc_profile_from_config(deps.get("format_config"))` for back-compat

**Architecture unchanged otherwise:** `CalcProfile` in `DamageModel`; game_mode without holder; no trace-oracle refactor; depth-2 via `d2_model_kwargs`; Mega fixture I4-only; 2-battle smoke safety-only.

**No code, tests, commit, or push in this deliverable.**

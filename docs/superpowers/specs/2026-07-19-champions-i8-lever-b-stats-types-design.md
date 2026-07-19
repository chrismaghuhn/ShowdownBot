# Champions I8 — Lever B (stats/types transport) Design

**Status:** `APPROVED` — **B2 selected as the design path** (Codex review PASS, 2026-07-19). This design authorizes **no** production/test code, run, benchmark, backend switch, evidence change, or Strength work; implementation follows only from the separate B2 plan (`docs/superpowers/plans/2026-07-19-champions-i8-lever-b-stats-types.md`). Persistent (Option D) remains a separate stratum; Strength remains **NO-GO**.

**Basis:** built on the APPROVED diagnosis `docs/superpowers/specs/2026-07-19-champions-i8-post-lever-a-latency-diagnosis.md` (post-Lever-A: 1786 oneshot spawns; `stats_batch_calls`=401 + `types_batch_calls`=511 = 912 = 51.1 %, untouched by Lever A). All code claims verified against `main @ 34b088e` via `rg`/source read.

*(Rev. 3 — Rev. 2 findings (`_spe_cache` warming does not work for `opponent_range`; per-kind error domains, not blanket-`CalcError`; corrected call-site/timing inventory; "our base-speed" is not a spawn; the counter contract is bound) **plus two further review corrections**: the counter contract is **backend-specific** — `spawn_calls == dmg+stats+types+mixed` holds only for oneshot, and generally `transport_attempts >= transport_calls` with `transport_retried == (attempts > calls)`; the schema surface spans `_DELTA_FIELDS`, the microprofile writer and **both** dataset validators with v1 frozen-evidence back-compat; and the speed cache key must include the **generation**.)*

## 1. Headline feasibility finding (and a correction to the diagnosis)

**Lever B is feasible only in a narrower and larger form than first drafted, and it is NOT "the same fold as Lever A."** The diagnosis's shorthand ("same fold pattern Lever A proved safe") is **corrected here** (and should be added to the diagnosis by erratum): Lever A folded damage into an **existing collecting oracle** (`DamageOracle`). Stats/types have **no** such oracle — `SpeedOracle` (`showdown_bot/src/showdown_bot/engine/speed.py:88`) and `SpeciesDex` (`showdown_bot/src/showdown_bot/battle/opponent.py:35`) are synchronous per-mon caches.

Two findings narrow the design further:

- **Cache-warming works for types, NOT for speed.** `SpeciesDex.types` reads `self._cache` (`opponent.py:47`), so pre-warming it makes later `dex.types()` spawn-free. But `SpeedOracle.opponent_range` calls `backend.stats_batch()` **directly and never reads `_spe_cache`** (`speed.py:133-149`), and its per-spread specs vary level/IVs (`spe:0` / default / `spe:31`) which the `_spe_cache` key `(gen,species,nature,evs)` (`speed.py:111`) does not distinguish. So a "warm the speed cache" pre-pass **cannot** make `opponent_range` spawn-free without first refactoring `SpeedOracle` to be cache-first with an exact key.
- **Error domains differ per kind** (§2.5) and must be preserved.

So Lever B is a **decision-level collection design** that, for any cross-kind (stats+types) win, requires a **SpeedOracle cache-first refactor** — a genuine change to a synchronous API, not a drop-in fold.

## 2. Transport audit — the protocol is ALREADY heterogeneous (no Node/RPC change) [UNCHANGED, still valid]

- Both backends transport stats/types via `_run(payload)` sending a JSON array of self-describing dicts: oneshot `SubprocessCalcBackend._run` (`engine/calc/client.py:102`), `stats_batch` `{"id":"s{i}","kind":"stats"}` (`client.py:133`), `types_batch` `{"id":"t{i}","kind":"types"}` (`client.py:144`); persistent `_run` (`client.py:268`), `stats_batch` (`client.py:320`), `types_batch` (`client.py:331`).
- Node `calc.mjs` dispatches per item by `req.kind` (`tools/calc/calc.mjs:124` `dispatch`; `:150`/`:161` `requests.map(dispatch)`; per-item `{id,error}` `:133`). A **mixed stats+types payload works today**; `s{i}`/`t{i}` ids split cleanly; **no Node change**. A thin Python `mixed_batch(specs, species) → (stats, types)` on both backends is the only transport addition.

### 2.5 Mixed error handling MUST preserve per-kind legacy semantics [CORRECTED — was wrong]

The prior draft's "raise `CalcError` on any item error" is **rejected**: it couples domains that are separate today and could abort a decision earlier.

- **stats today:** `stats_batch` does `[item["stats"] for item in data]` (`client.py:142`) → **`KeyError`/raises** on an error item.
- **types today:** `types_batch` does `[item.get("types", []) for item in data]` (`client.py:154`) → **degrades to `[]`** on an error item; and some callers additionally swallow (e.g. the setup-time `load_opp_sets_for_format` `is_valid` `bool(...)` `hypotheses.py:207`).

A `mixed_batch` must reproduce **each kind's** legacy handling **per item**: stats-item error raises (as today), types-item error yields `[]` (as today). The behaviour-neutrality tests (§8) must assert both domains separately, on partial-failure fixtures, for every caller that consumes the result.

## 3. Call-site inventory & timing (verified) [CORRECTED]

Constructed once per decision, sharing `calc.backend`: `SpeciesDex(calc.backend)` (`decision.py:347`); `SpeedOracle` passed in.

| call-site | file:line | kind | in decision timer? | timing | candidate-dependent? | reads a warmable cache? |
|---|---|---|---|---|---|---|
| `dex.types()` → set `mon.types` | `decision.py:358` | types | yes | setup | no (board species) | **yes** (`SpeciesDex._cache`) |
| `dex.types()` (opp modeling) | `opponent.py:92`, `:129` | types | yes | opp modeling | no | **yes** |
| `_opponent_speed()` → `opponent_range()`/`likely_speed()` | `opponent.py:237`,`:298` → `:256`/`:253` (`speed.py:133`/`:124`) | stats | yes | opp modeling | no | **no** (`opponent_range` bypasses `_spe_cache`) |
| `speed_for_species()` (own Mega form) | `mega_scoring.py:590`, `mega_projection.py:127`, `:186` | stats | yes | **variant scoring / projection** | **yes** | no |
| `our_speed()` | `decision.py:218`,`:1224` (`speed.py:105`) | — | yes | scoring | — | **no backend spawn** (`effective_speed_from_state`) |
| `load_opp_sets_for_format` `is_valid` types | `hypotheses.py:207` (via `gauntlet.py:993`) | types | **NO — gauntlet SETUP, own backend** | pre-run | — | out of scope |

**Corrected sequence (in-timer only):**

```
Decision start (board mons + book known)
  → setup: dex.types() on board mons                        [types, board-invariant, cache-warmable]
  → opponent modeling: dex.types() + _opponent_speed()      [types cache-warmable; SPEED not cache-warmable today]
  → variant scoring / projection: speed_for_species()       [stats, CANDIDATE-DEPENDENT — late, 3 sites]
```

`hypotheses.py:207` is **removed** (setup, separate backend, never measured). `our_speed` is **not** a spawn. The only in-timer stats spawns are `opponent_range`/`likely_speed` (early, but **not cache-warmable as-is**) and `speed_for_species` (late/candidate-dependent, 3 sites).

## 4. Evidence sizing (post-Lever-A profile only; COUNT ceiling, not achievable) [UNCHANGED]

`data/eval/champions-panel-v0/i8d-live-post-lever-a/profile.jsonl`:

| scope | rows | stats dist | types dist | both>0 | CEILING (all→1/row) | within-kind |
|---|---|---|---|---|---|---|
| all 679 | 679 | `{0:483,1:76,2:35,3:85}` | `{0:414,1:129,2:50,3:62,4:24}` | 195 | 646 | 451 (+195 cross-kind) |
| 60 gate | 60 | `{0:15,2:35,3:10}` | `{0:12,1:3,2:34,3:11}` | 45 | 156 | 111 (+45) |
| top-10 gate | 10 | `{3:10}` | `{3:10}` | 10 | 50 of 60 | 40 (+10) |

**Constant-cost counterfactual — MODEL ONLY, not a bound, not a verdict.** At `c = 154.906 ms/spawn`, modeled gate p95 = **517.7 ms** (full) / **672.6 ms** (within-kind). Per-spawn cost actually varies 124–332 ms and the tail is variance-sensitive; **only a separately-authorized gate run could verdict.** The **achievable** reduction is below the ceiling and its split (early vs. late; and whether speed is reachable at all without the §5 refactor) is **not determinable from the sidecar**.

## 5. Design options [CORRECTED — the cache-warming split changes B]

**Option A — `mixed_batch` transport primitive.** Additive method on both backends (one `_run`, split by id prefix, per-kind error semantics §2.5). *Transport-trivial, necessary but NOT sufficient* — no current caller holds both, and speed is not cache-warmable (§1).

**Option B1 — types-only pre-pass.** Warm `SpeciesDex._cache` for the board species in **one** `types_batch` at decision start (gated on "will score"). Downstream `dex.types()` then hit the warm cache (0 spawns). *Works today* (types cache is read); *small*: coalesces only the types within-kind portion (gate types dist `{0:12,1:3,2:34,3:11}` → ~1/row), **no cross-kind, no speed**. Behaviour-neutral (cache warming).

**Option B2 — types pre-pass + SpeedOracle cache-first refactor + mixed pre-pass.** Refactor `SpeedOracle` so `opponent_range`/`likely_speed` resolve through an **exact** cache (key incl. species, level, nature, evs, ivs) that a pre-pass can warm; then issue **one mixed** `mixed_batch` for board types + opponent speed specs. This is the only path to the **cross-kind** win. *Bigger/riskier*: changes a synchronous API (`opponent_range` returns a `SpeedRange` immediately), must prove the exact-cache key is complete and byte-neutral, and still leaves the late candidate-dependent `speed_for_species` spawns.

**Option C — general mixed damage+stats+types.** Not recommended: damage already has its own oracle/flush (Lever A); folding it here broadens scope and entangles subsystems for little marginal count.

**Option D — persistent-backend stratum.** Out of Lever B scope: different `config_hash`/stratum, its own design/review/separately-authorized gate; not a silent oneshot replacement.

**Option E — no Lever B slice.** Defensible: B1 is likely too small to move a variance-dominated tail; B2 is a real `SpeedOracle` refactor whose gate-closing effect is unproven. A legitimate outcome.

## 6. Recommendation [CORRECTED]

**Lever B remains the strongest localized oneshot spawn candidate, but the cross-kind win is gated behind a `SpeedOracle` cache-first refactor (B2), not a cache-warming fold.** Honest ranking:

- **B1 (types-only)** is small and safe but probably too small to matter against a variance/per-spawn-cost-dominated tail (diagnosis §5).
- **B2 (speed refactor + mixed pre-pass)** delivers the real cross-kind coalescence but is a non-trivial change to `SpeedOracle`'s synchronous API, and **whether it closes the 1000 ms gate is unknown** (the §4 model is illustrative only).
- **Option E** and the separate **Option D (persistent stratum)** deserve genuine weight given (a) the refactor cost of B2 and (b) the diagnosis's finding that the tail is per-spawn-cost/variance-bound, so even a large spawn cut may not reach the budget under oneshot.

**Decision (2026-07-19): B2 is the chosen path**, taken into its own PROPOSED implementation plan (`docs/superpowers/plans/2026-07-19-champions-i8-lever-b-stats-types.md`); Options D (persistent stratum) and E (no Lever B) are not taken. B2 carries the corrected error (§2.5), inventory (§3), and counter (§7.5) contracts. **No implementation follows from this document** — only from the reviewed plan. Whether B2 closes the 1000 ms gate remains unknown until a separately-authorized gate run (the §4 model is illustrative only).

## 7. Scope & behaviour contract (IF Option B2 is later approved)

- **In scope:** `engine/calc/client.py` (`mixed_batch` on both backends + `CalcClient`); a `SpeedOracle` cache-first refactor of `opponent_range`/`likely_speed` through an exact speed cache keyed on `(gen, canonical CalcMon stats payload)` — at minimum `(gen, species, level, nature, normalized evs, normalized ivs)` — preserving today's `_base_speed` (level 50 / spe-IV 31, `speed.py:119`) vs `opponent_range` (`mon.level`, three IV spreads, `speed.py:143-147`) distinctions; a gated decision-start pre-pass (`battle/decision.py`) that warms `SpeciesDex._cache` and the new speed cache via one `mixed_batch`; cache-seed methods on `SpeciesDex`/`SpeedOracle`.
- **Excluded:** persistent default/backend switch; any budget/gate/exposure change; Strength; damage folding (Option C); the setup-time `load_opp_sets_for_format` path; the late `speed_for_species` spawns (stay lazy); Lever-A rework.
- **Error/timeout:** per-kind legacy domains preserved (§2.5); timeout/retry identical to each backend's `_run` (`client.py:84/119` oneshot; `:268-279` persistent).
- **Behaviour-neutral means:** identical chosen actions, `GameMode`s, full score-vectors, tie-break order, and visible outputs (Reg-I + Champions); only internal transport counters change by design.

### 7.5 Counter contract (BOUND — was an open decision) [CORRECTED]

A `mixed_batch` is **one** transport. It must **not** increment both `stats_batch_calls` and `types_batch_calls` (that would count one spawn as two). The contract is **backend-specific** and the derived transport fields must stay correct:

- Introduce a **`mixed_batch_calls`** counter on both backends, incremented once per mixed call (not the per-kind counters).
- **oneshot** (`spawn_count` counts transports, `client.py:72/107`): `spawn_calls == damage_batch_calls + stats_batch_calls + types_batch_calls + mixed_batch_calls`. **persistent** (`spawn_count` counts process (re)starts only, `client.py:229`): that identity does **not** hold — there the mixed call is one `_run` → one `transport_attempts`, and `spawn_count` is unchanged unless the process restarts.
- **Transport fields are derived in the writer** (`eval/decision_profile.py`): `transport_calls = damage + stats + types + mixed` (`:282`, extended), and `transport_retried = (transport_attempts > transport_calls)` (`:285`). The general invariant is **`transport_attempts >= transport_calls`** (retry bumps `transport_attempts` only, `client.py:285`), with equality **only** on the no-retry path — never asserted as equality on retry/error paths.
- **Schema surface (broader than "writer + 2 validators"):** add `mixed_batch_calls` to the microprofile `_DELTA_FIELDS` (`eval/profile_harness.py:88`) and its spawn derivation (`profile_harness.py:320`); to the live-writer's delta set and its `transport_calls` derivation (`eval/decision_profile.py:282`, add `+ mixed`) and `transport_retried` (`:285`); extend the field-schema check that today reads `transport_calls != damage + stats + types` (`decision_profile.py:808`, add `+ mixed`) and add the field to the closed row schema; and update **both** dataset validators — `validate_decision_profile_dataset` (microprofile tier) and `validate_live_profile_dataset` (live tier). Bump `schema_version` `decision-profile-v1 → -v2`.
- **v1 frozen-evidence back-compat is mandatory:** the existing frozen `i8d-live/`, `i8d-live-post-lever-a/`, and microprofile `-v1` datasets must continue to validate **unchanged** (`mixed_batch_calls` optional/defaulted-0 for `-v1` rows).
- `config_hash` is **unchanged** (telemetry-only, not behaviour-affecting); `schema_version` changes and must be single-valued within a run.

## 8. TDD acceptance matrix (binding test plan; NOT implemented here)

1. known stats+types calls emit separate oneshot spawns pre-change (RED).
2. post-change: exactly the approved spawn reduction on a both-kinds fixture.
3. no eager requests on short-circuit / single-action / unscored paths.
4. stats and types **results byte-identical** to the pre-change lazy path.
5. **per-kind partial failure preserved:** stats-item error raises (as today), types-item error → `[]` (as today), for every consuming caller.
6. timeout/retry semantics unchanged on both backends.
7. warm-cache paths emit no additional requests (types cache; and the new speed cache if B2).
8. full decision goldens (`showdown_bot/tests/test_decision_equivalence_golden.py`) byte-identical.
9. Reg-I and Champions output-neutral.
10. **counter invariants** hold on success and error paths: **oneshot** `spawn_calls == dmg+stats+types+mixed`; generally `transport_attempts >= transport_calls` with `transport_retried == (attempts > calls)` (equality **only** on the no-retry path — not asserted on retry/error paths); **persistent** `spawn_count` = process starts, unchanged by a mixed call.
11. `PersistentCalcBackend` behaviour unchanged unless explicitly in scope.
12. `config_hash` unchanged; `schema_version` bump validated (writer + both validators + `-v1` back-compat).

## 9. Open decisions

- B1 vs B2 vs Option D/E (the primary fork).
- The exact `SpeedOracle` cache key — `(gen, canonical CalcMon stats payload)` or at least `(gen, species, level, nature, normalized evs, normalized ivs)` — proven complete + byte-neutral, preserving the `_base_speed` vs `opponent_range` differences (B2).
- Which mons/spreads the pre-pass resolves (active only? revealed bench?) — equal to what a scored decision certainly needs, no more.
- The precise gate condition guaranteeing no cost on short-circuit paths.
- Whether the residual (late `speed_for_species` + damage) still leaves the gate infeasible under oneshot — an input to B-vs-D.

## 10. Explicit non-claims

- **No approval or implementation of Lever B** — design candidate only.
- **No causal or predictive latency claim.** The §4 counterfactual is a labelled constant-cost model, not a bound or verdict.
- **No backend switch** (persistent stays a separate stratum, Option D).
- **No budget/gate/exposure change.**
- **No Strength claim** — Champions Strength remains **NO-GO**.
- **No new run, server, battle, or benchmark authorized.**
- **The diagnosis's "same fold as Lever A" is corrected** (§1) and should be added to the APPROVED diagnosis by **erratum**, so this PROPOSED spec does not silently contradict it. The Lever-A design/plan themselves remain the historical, implemented contract and are not changed.

---

`LEVER-B DESIGN — APPROVED (B2 CHOSEN; CODEX REVIEW PASS) — NO CODE/RUN/PUSH; IMPLEMENTATION VIA THE SEPARATE PLAN ONLY`

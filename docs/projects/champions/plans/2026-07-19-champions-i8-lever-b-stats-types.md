# Champions I8 — Lever B (B2) Implementation Plan

**Status:** `APPROVED` — implementation authorized (Codex plan review PASS, 2026-07-19); execute T1→T6 on this branch, **offline-only**. It does **not** authorize a live gate run, benchmark, server, battle, backend switch, budget change, push/PR, or Strength work. Whether B2 closes the 1000 ms gate is **unknown** and decided only by a **separately-authorized** unchanged I8-D rerun after this slice merges.

**Design basis (APPROVED):** `docs/projects/champions/specs/2026-07-19-champions-i8-lever-b-stats-types-design.md` (Option **B2**). **Diagnosis (APPROVED + erratum):** `docs/projects/champions/specs/2026-07-19-champions-i8-post-lever-a-latency-diagnosis.md`. All file:line anchors verified against `main @ 34b088e`.

*(Rev. 4 — closes two P1s and one mechanical gap: the pre-pass is **best-effort** — a mixed transport-level failure injects nothing and falls back to the unchanged lazy path; the T5 counterproof uses a **phase snapshot** isolating the early consumers (late Mega stats stay lazy); and every command is spelled out with the T5-RED baseline hard-pinned before GREEN.)*

**Base command:** `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider` (append the test path; omit for the full suite).

## Goal

Coalesce the **early, world-invariant** coalescible part of the 51.1 % stats/types oneshot-spawn block into **one** shared mixed transport per scoring decision. **Excluded / left lazy:** late candidate-dependent Mega-form speeds (`speed_for_species`, `mega_scoring.py:590`, `mega_projection.py:127/:186`); `opp_sets`/world-dependent `likely_speed` where not world-invariant; all speed in K-world. Behaviour-neutral: identical chosen actions, `GameMode`s, full score-vectors, tie-break order, visible outputs; only internal transport counters change.

## Binding execution order

Today: dex build (`decision.py:347`) → **type-enrichment `mon.types = dex.types()` (`:354-360`, first types transport, wrapped in `try/except: pass` so a types error is swallowed)** → `apply_own_team_knowledge` (`:367`) → `my_actions = enumerate_my_actions` (`:396`, raises only on **zero** actions) → Lever A (`:400+`) → scoring.

**New order (T5):** `apply_own_team_knowledge` → `enumerate_my_actions` → **gate (reaches scoring path)** → **mixed pre-pass** → **type-enrichment (moved here; warm-cache hit)** → Lever A → scoring. **Single-action:** no short-circuit (`:397` scores `len==1`) → the pre-pass runs on the scoring path regardless of action count; non-scoring decisions never run it.

## Shared spec-collector (branch-accurate, backend-guarded)

One collector used by **both** the pre-pass and lazy `_opponent_speed` (`opponent.py:237`):
- **Reproduces the branch** exactly: extract `use_likely = SHOWDOWN_OPP_SPEED!=0 and lookup_opp_set(opp_sets, mon) is not None` (`opponent.py:246-250`) + the built spec into `opp_speed_specs(mon, field, side, book, opp_sets) -> list[CalcMon]`; both call it. **No range prefetch for a `likely_speed` mon.**
- **Single-world (`n_worlds==1`, the gate case):** collect each opp mon's exact specs (world-invariant, `opp_sets` fixed).
- **K-world (`n_worlds>1`):** `merged_sets` vary (`mega_scoring.py:489`) → speed pre-pass **disabled** (`speed_specs=[]` when `world_samples()>1`); **types still pre-warmed**.
- **Backend/CalcProfile identity guard:** run + inject **only if** `speed_oracle.backend is calc.backend and dex.backend is calc.backend and speed_oracle.profile.generation == calc_profile.generation` (default path shares them: `decision.py:342/347`); else pre-pass **skipped**, lazy path unchanged.

## Pre-pass failure semantics (transport-level — behaviour-neutral)

A `mixed_batch` is one transport, so a **timeout/process/`CalcError`** fails the whole call — unlike today's split, where the early types error is swallowed (`decision.py:358-360`) and a later stats error propagates. **Binding rule:** the pre-pass wraps `mixed_batch` in `try/except CalcError`; on failure it **injects nothing** (caches stay cold), aborts the pre-pass, and lets the decision continue on the **unchanged lazy path** — where `dex.types()` again swallows its own error (`:358-360`) and the stats path again propagates via its caller (as today). The failed mixed attempt still counts (`mixed_batch_calls`+1, `transport_attempts`+1, oneshot `spawn_count`+1, incremented before `_run` like `calc_batch` `client.py:64`); the subsequent lazy calls add their own transports. Net decision-level error behaviour is **identical** to today.

## Tasks (RED→GREEN checkboxes; each boundary green; full suite at T2 and T6)

### T1 — mixed transport primitive + `mixed_batch_calls`
Files: `engine/calc/client.py` (`SubprocessCalcBackend:36`, `PersistentCalcBackend:166`, `CalcClient:360`; counter by `stats_batch_calls:58/:200`; increment before `_run`). One payload `[s{i}…,t{j}…]`, one `_run`, split by `s`/`t` prefix; per-item error domains (stats raises `client.py:142`, types → `[]` `:154`).
- [ ] **RED:** create `tests/test_lever_b_mixed_transport.py`: `test_mixed_batch_one_spawn_and_prefix_split`, `test_mixed_batch_empty_no_transport`, `test_mixed_batch_stats_only_one_spawn`, `test_mixed_batch_types_only_one_spawn`, `test_mixed_batch_per_item_error_is_per_kind`, `test_mixed_batch_transport_error_raises_calcerror` (timeout/process → `CalcError`, `mixed_batch_calls` still +1). Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_mixed_transport.py` → **expect** `AttributeError: … has no attribute 'mixed_batch'`.
- [ ] **GREEN:** implement `mixed_batch` + counter on both backends + `CalcClient`. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_mixed_transport.py` → **expect** pass.
- [ ] **Commit:** `feat(calc): mixed stats+types one-shot transport + mixed_batch_calls`.

### T2 — schema migration (v1→v2; separate live/microprofile fixtures; full back-compat)
Files: `eval/decision_profile.py` (`transport_calls:282` `+mixed`; `transport_retried:285`; field check `:808` `+mixed`; closed schema; `SCHEMA_VERSION -v1→-v2`), `eval/profile_harness.py` (`_DELTA_FIELDS:88`, spawn deriv `:320`), `eval/profile_fixtures.py:220` `ProfileSession.counters()` + every fake-session/fixture backend, both dataset validators.
- [ ] **RED:** create `tests/eval/test_profile_schema_v2_mixed.py`: `test_v2_live_row_validates`, `test_v2_microprofile_row_validates` (row + `manifest`; separate artifacts — one row cannot pass both tiers), `test_v1_live_frozen_still_validate` (`i8d-live/`, `i8d-live-post-lever-a/` → `{679,60,45}`), `test_v1_microprofile_frozen_still_validates` (`i8-microprofile/profile.jsonl`+`profile_manifest.json`), `test_oneshot_spawn_and_transport_relation`. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/eval/test_profile_schema_v2_mixed.py` → **expect** closed-field validator rejects `mixed_batch_calls`.
- [ ] **GREEN:** implement across the surface (oneshot `spawn_calls==dmg+stats+types+mixed`; `transport_attempts>=transport_calls`, equality only no-retry; persistent `spawn_count`=process starts). Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/eval/test_profile_schema_v2_mixed.py` then the full suite `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider` → **expect** pass; the three frozen v1 datasets re-validate unchanged.
- [ ] **Commit:** `feat(profile): mixed_batch_calls telemetry (decision-profile-v2, v1 back-compat)`.

### T3 — `SpeedOracle` exact cache + cache-first (batched cold-miss) + `seed_results` + `opp_speed_specs`
Files: `engine/speed.py` (exact key `(gen, canonical CalcMon payload)` ≥ `(gen, species, level, nature, norm evs, norm ivs)`, preserving `_base_speed` level 50/spe-IV 31 `:119` vs `opponent_range` `mon.level`/3 IV spreads `:143-147`; cache-first `opponent_range` **checks all keys, collects misses, one `stats_batch`**; `seed_results([(CalcMon, stats)])` pure; `opp_speed_specs` extracted from `_opponent_speed`).
- [ ] **RED:** create `tests/test_lever_b_speed_cache.py`: `test_opponent_range_byte_identical`, `test_opponent_range_cold_miss_one_batch` (3 misses→**1** `stats_batch`), `test_opponent_range_partial_hit_one_batch` (misses→**1**), `test_opponent_range_warm_zero_transport`, `test_seed_results_no_io`. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_speed_cache.py` → **expect** cold-miss issues >1 batch and/or `AttributeError: seed_results`.
- [ ] **GREEN:** implement. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_speed_cache.py` → **expect** pass.
- [ ] **Commit:** `refactor(speed): exact gen-keyed cache-first (batched miss) + seed_results + opp_speed_specs (no behavior change)`.

### T4 — `SpeciesDex.seed_results`
Files: `battle/opponent.py` (`SpeciesDex.seed_results([(species, types)])`, pure `_cache` inject; `types()` `:47` unchanged).
- [ ] **RED:** create `tests/test_lever_b_dex_seed.py`: `test_seeded_dex_zero_spawn`, `test_dex_seed_results_no_io`. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_dex_seed.py` → **expect** `AttributeError: … 'seed_results'`.
- [ ] **GREEN:** implement. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_dex_seed.py` → **expect** pass.
- [ ] **Commit:** `refactor(opponent): SpeciesDex.seed_results cache-seed (no behavior change)`.

### T5 — reordered, gated, best-effort pre-pass (phase-snapshot counterproof)
Files: `battle/decision.py` (move `:354-360` after pre-pass; insert pre-pass after `:396`; backend guard; best-effort try/except), the `opp_speed_specs` collector.
- [ ] **RED:** create `tests/test_lever_b_prepass.py` (real Node calc; reuse `test_lever_a_fold.py::_gating_state`/`_run_mega`):
  - `test_prepass_phase_snapshot_early_consumers_zero` — **RED first records and HARD-PINS** the fixture's current `stats_batch_calls`/`types_batch_calls` on `_gating_state` (the exact integers, asserted as constants before GREEN; **named in the commit report**). GREEN uses a **phase snapshot** at the pre-pass boundary: assert **one** `mixed_batch`; between the pre-pass and scoring, warmed `dex.types()` + `_opponent_speed()` add **0** stats/types calls; the **late** `speed_for_species` (Mega) stats are counted **separately** and may still occur; total path = 1 `mixed_batch` + only the expected late/lazy calls.
  - `test_prepass_mixed_error_falls_back_to_lazy` — a mixed **transport** error injects **nothing** (no partial cache), the decision continues on the lazy path: lazy `dex.types()` degrades as before (swallowed), lazy stats propagates as before; counters show the failed mixed attempt (`mixed_batch_calls`+1) **plus** the lazy calls.
  - `test_prepass_not_run_on_nonscoring_decision` (team-preview/forced → 0 `mixed_batch`).
  - `test_prepass_runs_on_single_action_scoring_decision`.
  - `test_no_mon_types_read_before_prepass` (reorder guard).
  - `test_prepass_disabled_on_mismatched_backend` (injected different backend → 0 `mixed_batch`, no cross-injection, identical output).
  - `test_prepass_speed_disabled_in_k_world` (`SHOWDOWN_WORLD_SAMPLES=2` → types warmed, speed lazy, output identical).
  - `test_prepass_no_range_prefetch_for_likely_speed_mon` (mon with `opp_set` → `likely_speed` → no range prefetch).
  Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_prepass.py` → **expect** `mixed_batch_calls == 0` and ≥2 separate stats/types spawns (RED).
- [ ] **GREEN:** implement the reordered, guarded, best-effort pre-pass + collector wiring. Run `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_lever_b_prepass.py` → **expect** pass.
- [ ] **Commit:** `perf(champions-latency): Lever B — coalesce early world-invariant board stats/types into one shared pre-pass` — the commit report states the pinned RED baseline (fixture `stats_batch_calls`/`types_batch_calls`) and the post-GREEN early-consumer count (0) + late Mega count.

### T6 — behaviour-neutrality + counter-invariant gates
- [ ] `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_decision_equivalence_golden.py` — goldens byte-identical (Reg-I 68 + Champions 8); Reg-I + Champions output-neutral.
- [ ] Counter invariants (design §8.10) incl. `mixed_batch_calls`, `transport_attempts>=transport_calls`, `transport_retried` on success + error paths.
- [ ] Per-kind partial-failure + mixed-transport-failure fail-closed exactly as legacy, per consuming caller.
- [ ] `PersistentCalcBackend` unchanged beyond additive `mixed_batch`.
- [ ] Three frozen v1 datasets (`i8d-live/`, `i8d-live-post-lever-a/`, `i8-microprofile/`) re-validate unchanged; `git diff --check`; no evidence bytes touched.
- [ ] Full suite `cd showdown_bot && PYTHONPATH=src python -m pytest -q -p no:cacheprovider` green; reconcile pass/skip/xfail + skip set vs pre-slice baseline.

## Acceptance matrix

Design spec §8 (1–12) **plus**: one backend call for the pre-warmed set with a phase snapshot isolating early consumers (T5); best-effort fallback on mixed transport failure (T5); empty/one-sided mixed pinning (T1); cold/partial/warm `opponent_range` batching (T3); `ProfileSession.counters()`+fixtures (T2); reorder/backend/K-world/likely-speed guards (T5); separate v2-live/v2-microprofile + all three frozen v1 datasets in back-compat (T2/T6).

## Sequencing & non-claims

Order T1→T2→T3→T4→T5→T6; each boundary green; full suite at T2 and T6. No live run/server/battle/benchmark/gate; after merge the **unchanged** I8-D gate may be rerun **only** under separate authorization (design §4 model is illustrative, not a prediction). **No** gate-closure/causal/predictive latency claim; **no** Strength claim (**NO-GO**); **no** backend switch, budget change, evidence/ROADMAP/PROJECT_INDEX change, push/PR/merge authorized. Persistent stays a separate stratum; late Mega + per-world/K-world speeds stay lazy by design.

---

`LEVER-B (B2) PLAN — APPROVED (CODEX REVIEW PASS) — IMPLEMENT T1→T6 OFFLINE; NO PUSH/BENCHMARK/SERVER/BATTLE/GATE`

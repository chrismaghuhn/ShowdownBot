# Champions I8 Latency-Reduction — Implementation Plan (Lever A)

**Status:** `APPROVED` (plan review, 2026-07-18) — planning only. No production code, no test code, no
benchmark, no server, no battle, no live gate, no evidence change was produced here. Approval covers
this plan for **Lever A only**; implementation, tests, and the eventual unchanged live-gate rerun are
separate, later, separately-authorized steps. Base: `main` @ `b655047`. Worktree
`plan/champions-i8-latency-reduction`. Executes the **APPROVED** design
`docs/superpowers/specs/2026-07-18-champions-i8-latency-reduction-design.md` — **Lever A only**.

Lever A: fold the **initial** game-mode classification's **incoming** (`ko_threat`) damage into the
single existing scoring flush, removing exactly one Node-process spawn per decision (~142 ms) while
preserving the base `MUST_REACT` short-circuit. Lever B and the `opponent_range` cache are excluded.

All `file:line` anchors below are verified at `b655047`. The eventual unchanged live-gate rerun is a
separate, later, separately-authorized step; this plan does not run it.

---

## 1. Guardrails carried from the design (unchanged)

- The later rerun uses the identical gate: `oneshot`, budget **1000 ms**, D-1 (≥60 from ≥20), D-2
  (200/2000), identical active population (`is_active_valid_live_row`) and p95 function, identical
  schedule/panel/teams/seed. `config_hash` stays `594295543f13a55d`; only `git_sha` advances.
- Behavior-neutral: identical decisions, scores, tie-break, candidate coverage, `GameMode`, belief
  state, and determinism. Internal transport ordering and calc counters (`spawn_calls`,
  `transport_*`, `damage_batch_calls`) change by design and are **not** part of the contract.
- No backend switch; no candidate/search/strength change; Strength stays NO-GO.

---

## 2. Why a two-phase split is required (the load-bearing structural fact)

The classification and the scoring flush live in different places, and `mode` is consumed only after
the flush — so the incoming batch can be folded, but only by splitting classification into
**enqueue** (before the flush) and **resolve** (after it).

Call chain (verified): `heuristic_choose_for_request` (decision.py:1273) → `_choose_best_ja`
(:1222→:1250) → `_choose_best` (:281). Inside `_choose_best`:

- `mode = classify_game_mode(state, our_side, calc=calc, book, calc_profile)` at **decision.py:397**,
  **unconditionally**, before any scoring oracle exists.
- If `format_config.mega` (decision.py:401): `_choose_best_mega` is dispatched at **:408** with
  `oracle=oracle` (**:411**) and `mode=mode` (**:417**). The mega scoring flush is **mega_scoring.py:661**; `mode`
  is consumed only later at `aggregate_scores` (**mega_scoring.py:775, :845**).
- Else (non-mega): the scoring oracle is `shared_oracle = oracle or DamageOracle()` (**:444**, K-world)
  and the flush is **:460** (K-world) or inside `model.prefetch(groups)` (**:503**, single-world;
  prefetch enqueues-then-flushes, evaluate.py:285-287). `mode` is consumed at `pick_best` (**:488**).

`classify_game_mode` (game_mode.py:209) is the **extended** classifier: it takes the calc-based
`compute_game_mode` base result (which issues the incoming/outgoing damage) plus non-calc mon-count
and speed-control signals. **Only `compute_game_mode`'s incoming batch is calc;**
the extended signals are pure state reads. `compute_game_mode` (game_mode.py:140): incoming
`ko_threat_counts` (:170 → game_mode.py:103 `calc.damage_batch`); if `threatened > 0` → `MUST_REACT`
(**game_mode.py:173**, the base short-circuit); else the outgoing batch (:177-198, game_mode.py:195).

Consequence: to put the incoming into the scoring flush, it must be **enqueued** before that flush
and its result **read** after — and `mode` must be **resolved after** the flush. Since `mode` is only
consumed post-flush on every path (:488 / :775 / :845), moving classification past the flush is
order-legal. No behavior depends on `mode` being known before the flush.

---

## 3. Exact call-chain changes

### 3.1 `engine/belief/game_mode.py` — split the calc-based classifier into enqueue / resolve

Add an oracle-backed two-phase form of the base classifier; keep the existing functions as thin
wrappers so nothing else (and no existing test) breaks.

1. `enqueue_game_mode_incoming(state, *, our_side, oracle: DamageOracle, book, calc_profile) ->
   IncomingHandle` — builds the incoming `ko_threat` `DamageRequest`s exactly as `ko_threat_counts`
   does today (game_mode.py:95-101), but calls `oracle.request(req)` (oracle.py:63) for each instead
   of `calc.damage_batch`, returning the keys + the per-owner grouping needed to score them later.
   **Does not flush.** Empty-board early-returns (game_mode.py:90-93) are preserved as an empty handle.
2. `resolve_base_game_mode(handle, *, oracle, state, our_side, book, calc_profile) -> GameMode` —
   reads incoming via `oracle.get(key)` (oracle.py:113; already resolved by the shared flush, so this
   is a cache hit, no implicit flush). Computes `threatened` with the **same** `is_guaranteed_ohko` /
   `can_ohko` logic (game_mode.py:108-117). If `threatened > 0` → `MUST_REACT` (**base short-circuit
   preserved — no outgoing built or sent**). Else it enqueues the outgoing requests (game_mode.py:
   177-198) into `oracle`, calls `oracle.flush()` (the **second** flush), reads them, and returns
   `AHEAD`/`NEUTRAL` — byte-identical to `compute_game_mode`'s tail.
3. Refactor `compute_game_mode` (game_mode.py:140) to delegate to the two new functions with a private
   single-shot **`DamageOracle(client=calc)`** so its result is provably identical (it becomes
   `enqueue → flush → resolve`). It **must** bind the injected `calc` — never a default `DamageOracle()`,
   which would silently drop a pinned backend client, a test spy, or an error stub. This keeps every
   existing caller and test of `compute_game_mode` green unchanged.
4. Add the extended two-phase form for `classify_game_mode` (game_mode.py:209):
   `enqueue_classification(state, oracle, book, calc_profile) -> IncomingHandle` (delegates to (1))
   and `resolve_classification(handle, oracle, state, our_side, book, calc_profile) -> GameMode`
   (calls (2) for the base, then applies the
   **unchanged** non-calc mon-count / speed-control adjustments from the current `classify_game_mode`
   body). `classify_game_mode` itself is refactored to `enqueue → flush → resolve` for back-compat.

Guarantee: the outgoing short-circuit is governed strictly by the **base** `threatened > 0`
(game_mode.py:173), never by an extended `MUST_REACT`.

### 3.2 `battle/decision.py::_choose_best` — enqueue before the flush, resolve after (both paths)

1. The shared, calc-bound oracle **already exists**: `_choose_best` sets `oracle = oracle or
   DamageOracle(calc)` at **decision.py:334** (positional `calc` == `client=calc`). This same `oracle`
   already backs non-mega scoring (the `shared_oracle = oracle or DamageOracle()` at :444 never fires,
   since `oracle` is non-None after :334 — its bare fallback is dead defensive code) and the mega path
   (:411 forwards `oracle`). So classification simply **enqueues into this existing `oracle`** — no new
   oracle is created. Any residual bare `DamageOracle()` fallback introduced by the edit must be
   `DamageOracle(client=calc)` so an injected calc is never dropped.
2. Replace the eager `classify_game_mode` call at **:397** with
   `cls_handle = enqueue_classification(state, our_side=our_side, oracle=oracle, book=book,
   calc_profile=calc_profile)`. No flush here.
3. **Non-mega paths:** after the existing scoring flush (**:460** K-world; **:503** single-world),
   insert `mode = resolve_classification(cls_handle, oracle=oracle, state=state, our_side=our_side,
   book=book, calc_profile=calc_profile)`. `mode` is then used unchanged at `pick_best` (:488) and in
   the report line (:642). The incoming folded into the scoring flush; the conditional outgoing takes a
   second (planned) flush **on the same `oracle`** only when not base-`MUST_REACT`.
4. **Mega path:** stop passing a precomputed `mode` (:417). Instead pass a bound `resolve_mode`
   (a zero-arg closure capturing `oracle`, `cls_handle`, and the classification inputs) down to
   `_choose_best_mega`.

### 3.3 `battle/decision.py::_choose_best_mega` + `mega_scoring.py::score_evaluated_variants` — resolve after the flush

1. `_choose_best_mega` (decision.py:677) receives `resolve_mode: Callable[[], GameMode]` instead of
   `mode: GameMode` (:417 becomes the closure). It forwards it to `score_evaluated_variants`.
2. **The flush at mega_scoring.py:661 is INSIDE the world loop** `for world_idx, (world_sets, world_w)
   in enumerate(worlds)` (**mega_scoring.py:487**), so `resolve_mode()` must **not** be called
   unconditionally after :661 — that would resolve (and issue the conditional second flush) once per
   world when `world_samples > 1`. Instead: resolve **only after the first world's flush** and reuse:
   - Before the loop, `mode = None`.
   - After `oracle.flush()` (:661), inside the loop: `if world_idx == 0: mode = resolve_mode()`
     (mirrors the existing `if world_idx == 0:` guards at :698 / :741).
   - Every world uses that single `mode` at the sort (:775) and the final aggregate (:845) — identical
     across worlds, exactly as today (`mode` was a single value passed in).
   - **After the loop, fail-closed:** assert `mode is not None` (there is always ≥1 world), so a
     refactor that skipped world 0 cannot silently score with an unset mode.
3. `resolve_mode` is invoked **exactly once** per decision. Minimal-churn: change the parameter type
   from `GameMode` to `Callable[[], GameMode]`; the only touched lines are the pre-loop init, the
   `world_idx == 0` resolve after :661, and the post-loop assert — the two `aggregate_scores` sites
   (:775, :845) read `mode` unchanged.

### 3.4 Explicitly NOT touched

- Trace-diagnostic call-sites `ko_threat_counts` (decision.py:933 mega, :1134 legacy) and
  `guaranteed_ohko` (decision.py:959, :1156) — post-scoring, out of scope; keep using `calc` directly.
- `compute_game_mode`'s public result, `battle/search.py`, the scoring math in `mega_scoring.py`
  (only the `mode`-resolution point moves), `eval/config_env.py`, seed derivation, `client.py`,
  `calc.mjs`, `SpeedOracle`, `SpeciesDex`.

---

## 4. RED→GREEN sequencing

Each test lands **with** the code it guards — no test is committed in a failing state; the T1 RED is
demonstrated locally and logged (§7). The suite is green at every commit boundary.

| # | RED (before) | GREEN (after) |
|---|---|---|
| T1 | a fixture foe-Mega decision issues the incoming `ko_threat` (and any outgoing) as its own direct `calc.damage_batch`; measured `spawn_calls` includes them and `spawn > damage_batch_calls+stats+types` | both incoming and (conditional) outgoing now go through `oracle`, so on the same fixture: **`spawn_calls` drops by exactly 1** (the incoming's separate spawn folds into the scoring flush); the telemetry **gap → 0** in both cases — base-`MUST_REACT` `1→0`, non-`MUST_REACT` `2→0` (the outgoing is now a *planned* oracle batch, not an untracked spawn); non-`MUST_REACT` `damage_batch_calls` rises `1→2`; and `transport_retried` is no longer spuriously `True` (the old accounting gap is closed). Counter assertions, offline, no timing |
| T2 | — | **Decision equivalence** on a fixed corpus of foe-Mega boards + seeds: chosen action, full score vectors, tie-break order, and `GameMode` are identical before/after (golden captured from `b655047`) |
| T3 | — | `GameMode` identical on base-`MUST_REACT` (`threatened>0`), `AHEAD`, `NEUTRAL`, and on extended-`MUST_REACT` (down-mons / speed-control) boards; on a base-`MUST_REACT` board **no outgoing request is built or sent** (assert via an oracle/calc spy) |
| T4 | — | a calc failure in the shared flush raises `CalcError` and yields a non-ok row (fail-closed), exactly as the direct path did; the second (outgoing) flush's failure behaves identically |
| T5 | — | Reg-I / `format_config=None` / non-foe-Mega decisions: chosen action, scores, and visible outputs identical before/after (NOT internal transport bytes — classification is format-independent, so transport/counters change there too by design) |
| T6 | — | `config_hash` still `594295543f13a55d`; `eval/config_env.py` unchanged; no behavior-affecting env var added |
| T7 | — | `compute_game_mode` and `classify_game_mode` public results unchanged on a fixture battery (the wrapper refactor is provably identical) |
| T8 | — | **World-once resolve:** with `world_samples=2` on a foe-Mega board, `resolve_mode` is invoked **exactly once** (spy), all worlds are scored with the same `mode`, and the two worlds' evaluations match the pre-change golden; the post-loop `mode is not None` assert holds |
| T9 | — | **Injected-calc integrity:** a fake/​spy calc passed as `calc` receives every classification request; **no default `CalcClient` is ever constructed or called** (guards both the `game_mode` wrapper and `_choose_best`) |

The decision-equivalence corpus (T2/T5) is the primary neutrality proof and is captured from
`b655047` **before** any code change, then asserted byte-identical after.

---

## 5. Equivalence proofs (why each step is behavior-neutral)

- **Same requests, same results.** The incoming `DamageRequest`s are built by the same code
  (game_mode.py:95-101); routing them through `DamageOracle.request`/`get` returns the same
  `DamageResult`s (the oracle dedups by full semantic payload, oracle.py:57-61 — collisions are only
  genuinely-identical calcs). A game-mode request that collides with a scoring request is computed
  once and both read the same value.
- **Same GameMode.** `resolve_base_game_mode` uses the identical `is_guaranteed_ohko`/`can_ohko`
  comparisons and the identical `threatened>0` / outgoing tail; the extended adjustments are copied
  verbatim. `compute_game_mode`/`classify_game_mode` are refactored to call the split and are pinned
  by T7.
- **Same scores/action.** `mode` feeds only `aggregate_scores` (policy.py) at :488 / :775 / :845;
  its value is unchanged, so every aggregate and the final ranking are identical (T2).
- **Order-legality.** `mode` is consumed only after each path's flush, so moving classification past
  the flush cannot change any value read before it.
- **Short-circuit / error domain preserved.** Outgoing is gated by the base `threatened>0`
  (game_mode.py:173); on those boards no outgoing request is ever built or sent — the set of calcs
  that can raise is unchanged (T3, T4).

---

## 6. Error, timeout, retry, cache semantics

- Oneshot performs no retry; `SubprocessCalcBackend` raises `CalcError` on non-zero exit / timeout /
  malformed JSON (client.py:82-100, 117-131). Unchanged. `transport_attempts` continues to equal
  `spawn_calls`.
- `DamageOracle.flush` counts the attempt before the round trip and splits planned/implicit
  (oracle.py:103-107); a raising batch still increments and propagates. Folding the incoming means an
  incoming-calc failure now surfaces from the shared flush instead of a separate call — same
  `CalcError`, same fail-closed non-ok row (excluded from the active population). The conditional
  outgoing keeps its own (second) flush and identical failure behavior.
- Caches untouched: `DamageOracle._cache/_pending`, `SpeedOracle._spe_cache`, `SpeciesDex._cache`.
  `planned_damage_batches`/`implicit_damage_batches` accounting stays valid (the oracle owns it); the
  incoming fold registers as a planned enqueue, the outgoing (if any) as its own flush.
- `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` stays unset (part of `config_hash`); the 20 s calc subprocess
  timeout (client.py:46) is unchanged.

---

## 7. Commit boundaries (each independently green — no committed failing test)

**Every commit leaves the full suite green, with no new skip/xfail.** The T1 spawn-counter RED is
demonstrated **locally and logged** in the implementing session (captured console output) — it is
**not** committed as a failing test; T1 lands **with** its GREEN implementation in commit 3.

The non-mega and mega folds **cannot** be split across two green commits: both are driven by the
single shared `classify_game_mode` at decision.py:397, so converting it to `enqueue`/deferred-resolve
changes the `mode` source for **both** paths at once. A "non-mega only" commit would leave
`_choose_best_mega` receiving an unresolved handle → red before the mega commit. They therefore land
in **one** production commit.

1. **`refactor(game-mode): split calc classifier into enqueue/resolve (no behavior change)`** —
   game_mode.py split (§3.1) + T7. `compute_game_mode`/`classify_game_mode` results byte-identical;
   internal oracle is `DamageOracle(client=calc)`. No decision.py change yet. Full suite green.
2. **`test(champions-latency): capture decision-equivalence golden corpus`** — the T2/T5 corpus golden
   captured from this base + the equivalence harness. Green (it asserts `current == golden`; no
   production change yet). No failing test is introduced.
3. **`perf(champions-latency): fold game-mode incoming into the shared scoring flush`** — the single
   production commit: decision.py `_choose_best` enqueue-into-`oracle` + resolve for the non-mega paths
   **and** the mega dispatch's deferred `resolve_mode`, plus `_choose_best_mega` /
   `score_evaluated_variants` world-once resolve (§3.2–3.3). Lands with T1, T3, T4, T5, T6, T8, T9;
   T2 stays green. This is the commit that moves the gate p95. Full suite green.
4. **`docs(champions): reconcile I8 latency-reduction status`** — ROADMAP/PROJECT_INDEX note Lever A is
   implemented and the unchanged rerun is the next separately-authorized step. Docs only.

Commit-prefix note: **do not use `champions-i8a`** — I8-A already denotes the earlier offline
instrumentation. Use `champions-latency` (or a neutral scope) for the code commits.

Ordering rationale: the pure refactor (1) and the golden (2) de-risk the single production commit (3);
the RED is proven locally before (3) rather than committed.

---

## 8. Verification gates (offline only; no run)

- Full suite green at every commit with **no new skips/xfails** vs the `b655047` baseline (2783
  passed / 1 skipped / 1 xfailed); calc/oracle, I7b mega-scoring (`tests/i7b/test_i7b_scoring.py`),
  `tests/test_baselines.py`, decision/search, and I8 profile/validator suites specifically green.
- **Decision equivalence** (T2/T5) byte-identical on the captured corpus.
- **Spawn reduction** demonstrated as a counter fact (T1): exactly −1 spawn/decision, offline, **no
  latency benchmark and no timing claim**.
- `config_hash` resolves to `594295543f13a55d` (T6); `eval/config_env.py` unchanged.
- `battle/search.py` and the `mega_scoring.py` scoring math byte-identical (only the `mode`-resolution
  point moves); `git diff` limited to game_mode.py, decision.py, mega_scoring.py, and the new tests.
- `git diff --check` clean; LF hygiene preserved; the frozen evidence untouched.

Explicitly **not** a gate: any p95 or latency number. The live verdict comes only from the later
unchanged rerun.

---

## 9. Scope guards / risks

- **Surface is larger than "reuse the seam" implies.** The fold is a two-phase classification split
  across `_choose_best`, `_choose_best_mega`, and `score_evaluated_variants`. It remains behavior-
  neutral, but the decision core is touched — hence the elevated equivalence rigor (goldens captured
  pre-change, T2/T5/T7) and the refactor-first commit ordering.
- **`mode` typing on the mega path.** Prefer the minimal-churn closure (`resolve_mode: Callable[[],
  GameMode]`) over a broad signature change, to keep the diff at the flush site + two aggregate sites.
- **Do not fold the trace call-sites.** They are post-scoring and out of scope; folding them is a
  separate concern (would need a later implicit flush or a large pre-computation).
- **No cherry-picking, no budget shift, no backend switch, no candidate/search/strength change.**

---

## 10. Non-goals and non-claims

- **No latency PASS**, no benchmark, no gate run in this plan or the code slice it describes.
- **No Strength claim** — Champions Strength remains NO-GO.
- Lever B and the `opponent_range` cache are out of scope (design §14).
- The unchanged live-gate rerun is run only after the code slice is merged and separately authorized.

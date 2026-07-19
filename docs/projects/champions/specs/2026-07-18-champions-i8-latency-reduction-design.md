# Champions I8 Latency-Reduction — Design (APPROVED)

**Status:** `APPROVED` (design review, 2026-07-18) — diagnosis + design only. No production code, no
test, no server, no battle, no benchmark, no microprofile, no live-gate run, and no evidence mutation
was performed to produce this document. Approval covers **Lever A alone** (§6); Lever B and the
`opponent_range` cache are explicitly excluded (§14). Implementation, tests, and the eventual
unchanged live-gate rerun are separate, later, separately-authorized steps. Base commit `b09d6a6`
(merge of PR #27, the frozen I8-D FAIL evidence). Worktree `design/champions-i8-latency-reduction`.

Filename note: kept in the existing `champions-i8-latency` family and dated today (2026-07-18); no
new phase name is invented.

---

## 1. Scope and unchanged guardrails

This slice proposes a **behavior-neutral latency reduction** so that the **same** I8-D gate, repeated
**unchanged**, can be re-run later under a separate authorization. It does not touch play strength.

The later repeat run MUST use the identical gate (verbatim from the frozen FAIL):

- `SHOWDOWN_CALC_BACKEND=oneshot` — no backend switch may be used as an "optimization".
- Budget exactly **1000 ms** — never shifted, never reinterpreted as a per-arm microprofile threshold.
- **D-1** unchanged: ≥ 60 active-valid decisions from ≥ 20 distinct battles.
- **D-2** unchanged: MAX_BATTLES 200 / MAX_SCORED_DECISIONS 2000.
- Identical active population via `is_active_valid_live_row` (`source=="live"` ∧
  `timer_scope=="agent_choose"` ∧ `outcome=="ok"` ∧ `foe_mega_active is True`).
- Identical nearest-rank p95 function (`gauntlet._latency_p95`).
- Identical schedule / panel / team / seed bindings (`schedule_hash a1192d9dde4c65df`,
  `panel_hash aac1ea30446fde88`, `seed_base champions-panel-v0-i8d-latency`, seed 0).
- No post-hoc selection of favourable battles or decisions; no budget shift; no change to strength,
  candidate set, search semantics, tie-breaking, or decision ordering to make the gate pass.
- Champions Strength remains **NO-GO**.

The optimization must be **behavior-neutral**: every proposed change states why it does not change
score, action selection, tie-breaking, candidate coverage, belief-state semantics, or deterministic
reproducibility. If neutrality cannot be proven, the option is classified as unsuitable for this slice.

The frozen evidence at `data/eval/champions-panel-v0/i8d-live/` and its pinned SHA-256s are **not**
touched by this slice.

---

## 2. Reproduced evidence baseline (Phase 1 — from the frozen bytes, independently)

Reproduced read-only from `data/eval/champions-panel-v0/i8d-live/{profile,verdict,seeds}` on
`b09d6a6`, reusing the production `validate_live_profile_dataset`, `is_active_valid_live_row`, and
`gauntlet._latency_p95`. No number is taken on trust.

- Validator over the frozen `profile.jsonl`: `{rows: 679, active_valid_rows: 60,
  distinct_active_battle_ids: 45}`; closed 41-key schema, uniform across all rows.
- 679 rows, **679 unique** `(battle_id, decision_index)` (0 duplicates).
- Active-valid population: **60** rows from **45** distinct battles.
- Nearest-rank p95: n = 60, index = `min(59, round(0.95·59)) = 56` (0-based). `ordered[56] =
  1110.2130000072066` = `verdict.json.p95_ms` (bit-identical). The gate-determining row is
  **battle `0078733cc3f28e38`, `decision_index=2`, `measured_ms=1110.2130000072066`**. Exactly **3**
  rows lie strictly above the gate value (indices 57–59).
- Distribution of the 60: min **373.408**, median **959.247**, p90 **1092.490**, p95 **1110.213**,
  max **1187.719**; **20 of 60** exceed 1000 ms. The p95 sits in a **dense cluster**: gap to the
  previous order statistic is **0.418 ms**, gap to the next is **2.329 ms**. The verdict is not one
  outlier spike; it is the shoulder of a band of ~1090–1110 ms decisions.
- Provenance uniform across all 679 rows: `git_sha 9fc0f36…`, `config_hash 594295543f13a55d`,
  `calc_backend oneshot`, `backend_class oneshot`, `schedule_hash a1192d9dde4c65df`,
  `format_id gen9championsvgc2026regma`, `source live`, `schema_version decision-profile-v1`.
- No mixing with the two aborted attempts: the frozen seedlog has 75 rows; both aborted run
  directories had **no seedlog file at all** (0 battles created), so there is nothing to mix.

Verdict reproduced: **FAIL** (p95 1110.213 ms > 1000 ms budget), `stop_reason=exposure_floor_met`.

---

## 3. Quantitative cost analysis (Phase 2 — existing telemetry only)

All figures are from the frozen telemetry fields; no new measurement was run.

### 3.1 The dominant driver is Node-process spawn count

Correlation of `measured_ms` with the numeric telemetry (Pearson):

| driver | r over the 60 gate rows | r over all 679 live rows |
|---|---:|---:|
| `spawn_calls` | +0.978 | **+0.975** |
| `transport_attempts` | +0.978 | +0.975 |
| `transport_calls` (= dmg+stats+types) | +0.958 | +0.946 |
| `types_batch_calls` | +0.958 | +0.926 |
| `stats_batch_calls` | +0.940 | +0.932 |
| `n_candidates` / `n_responses` | +0.287 | +0.80 |
| `n_mega_twins` | −0.205 | +0.284 |
| `n_branches`, `n_worlds`, `depth2_frontier` | constant (1,1,0) | constant |

`measured_ms` tracks **`spawn_calls`** (each spawn is one `node calc.mjs` process start). Median
cost per spawn over all 679 rows is **141.7 ms/spawn**, which agrees independently with the frozen
microprofile's persistent-cold arm (≈144 ms for its single spawn). The foe-Mega structural counts
(`n_mega_twins` 4–90, `n_branches`=1) do **not** drive latency — twins are already batch-collapsed
by the shared oracle flush (I7b-B), so a decision with 90 twins still issues only ~1 damage batch.

### 3.2 Per-decision spawn decomposition

`spawn_calls` is NOT `damage_batch_calls + stats_batch_calls + types_batch_calls`. Over the 60 gate
rows the difference (`spawn − (dmg+stats+types)`) is **1 for 19 rows and 2 for 41 rows**. This gap is
real and load-bearing. Its origin (verified in code, §4): the telemetry's `damage_batch_calls` reads
`oracle.batch_calls` (the shared DamageOracle's flush count) while `spawn_count` is the backend's, so
**direct `calc.damage_batch` calls that bypass the oracle are counted in the spawns but not in
`damage_batch_calls`.** Those are the game-mode / KO-threat classification calls.

The per-active-decision spawn budget is therefore:

| source | spawns/decision | verified call-site (§4) |
|---|---:|---|
| **initial** game-mode classification damage (bypasses the oracle) | **1–2** ("the gap") | `compute_game_mode` incoming game_mode.py:103; conditional outgoing game_mode.py:195 — via `classify_game_mode` decision.py:397 |
| scoring damage — one shared oracle flush | 1 | mega_scoring.py:661, decision.py:460 |
| stats (speed) batches | 2–3 | speed.py:120 (and :133 uncached) |
| types batches | 2–3 | opponent.py:49 |
| **total** | **6–8 (median 7)** | — |

The gap is the **initial classification** (incoming, always present; outgoing only when not
`MUST_REACT` — hence 1 vs 2). The trace-diagnostic `ko_threat_counts` (decision.py:933/1134) and
`guaranteed_ohko` (decision.py:959/1156, game_mode.py:134) run **after** the scoring flush to populate
`CandidateTrace` and are **not** part of this measured gap; Lever A leaves them untouched (§6).

Spawn-count distribution of the 60 gate rows: `{2:7, 3:5, 4:3, 6:7, 7:27, 8:11}`. The gate-
determining row (`0078733cc3f28e38:2`) is `dmg=1, stats=2, types=2, spawn=7` (gap 2), `measured_ms
1110.213`.

### 3.3 Live-vs-microprofile: the live FAIL is base-cost, not a foe-Mega explosion

The microprofile localized foe-Mega worst cases at high spawn counts: A03/A04 (spawn 19, p95
≈ 2400 ms), A05 (spawn 45, p95 ≈ 5750 ms), A12 depth-2 (spawn 94, p95 ≈ 12300 ms). **None of those
materialized live.** The live active decisions cluster at spawn 6–8, matching the microprofile's
*base* arms A01/A02/A06/A08 (spawn 8, p95 1008–1114 ms). The live p95 (1110 ms) ≈ A01 (1114 ms). So
the live FAIL is **consistent with the microprofile mechanism** (oneshot ≈ one spawn per calc batch,
~140 ms each) and is dominated by the **base per-decision spawn count**, not by the dual-Mega /
tie / depth-2 branch blow-ups the synthetic arms exercised. This is a mechanism confirmation, not a
new mechanism.

### 3.4 Counterfactual spawn removal (MODEL-BASED PROJECTION — not a measurement)

Projected p95 if `measured_ms' = measured_ms − (removed spawns)·MS`, with `MS = 141.7 ms/spawn`
(the observed median, corroborated by the microprofile's ~144 ms single spawn). These are arithmetic
projections from the frozen counters, **not** re-measurements; the only real verdict is the unchanged
repeat gate. Per-spawn cost is not perfectly constant (observed 135–159 ms/spawn in the tail), so
treat the margins as approximate.

| lever | mean spawns removed / decision | projected p95 | rows > 1000 ms |
|---|---:|---:|---:|
| baseline | 0 | 1110.213 | 20/60 |
| **A (this slice)** — fold the game-mode **incoming** batch into the shared scoring flush | **1.00** | **968.513** | **2/60** |
| A, rejected ordering — incoming resolved separately, outgoing+scoring flushed | 0.68 | 1109.795 | 10/60 |
| B (future slice) — stats+types coalesced into one heterogeneous round trip | 2.60 | 670.450 | 0/60 |
| A+B (future) | 3.60 | 528.750 | 0/60 |

**Lever A saves at least one spawn per decision (see the Erratum below) — not the full gap.**
`compute_game_mode` must know the **incoming** (`ko_threat`) result before it can decide whether to
compute **outgoing** (game_mode.py:170→195), so incoming and outgoing cannot share one flush without
either breaking the short-circuit or computing outgoing unconditionally (which enlarges the error
domain — see §7). The behavior-neutral fold is: enqueue **incoming** with the scoring requests and
resolve them in the **existing** scoring flush; the (conditional) **outgoing** keeps its short-circuit
and, when reached, is resolved on the **same shared oracle** (a second `flush()` that dedups against
the scoring cache). Incoming is always present, so this removes **at least 1** spawn from **every**
active decision → in the constant-141.7-ms model every order statistic shifts down by one spawn-cost:
projected p95 `1110.213 − 141.7 = 968.513`, **2/60** still over budget. The rejected ordering (resolve incoming on its own,
fold only outgoing) removes a spawn only on the `gap=2` rows and leaves a ~1109.795 ms row unmoved →
still FAIL. Lever B (a separate future slice, §6) would add robust headroom but is out of this slice.

> **Erratum (2026-07-18, from implementation).** The measured effect on the reference Champions
> foe-Mega board is **−2 spawns, not −1**, and `damage_batch_calls` stays **1** (not 1→2). When
> reached, the conditional **outgoing** requests (OFFENSE-vs-DEFENSE calcs the scoring pass usually
> already computed) dedup against the scoring cache and are typically **cache-served**, so the
> outgoing's second `flush()` is transport-empty and folds too. The correct contract is therefore
> **"≥ 1 spawn removed per active decision"** — the incoming always folds; the outgoing additionally
> folds whenever its calcs are already cached (board-dependent) — and `damage_batch_calls` does **not**
> necessarily rise to 2. The `968.513 ms` figure is a **conservative point projection in the constant-
> 141.7-ms model** — but 141.7 ms is the observed **median** per-spawn cost, and per-spawn cost varies
> **135–159 ms** (§3.4), so it is **not** an upper bound: removing ≥ one *variable-cost* spawn per
> decision shifts each order statistic by a variable amount, and the real p95 may land **above or
> below** 968.513. **Only the unchanged rerun decides the latency verdict.** Verified by counterproof:
> pre-fold `spawn_count = 3`, post-fold `= 1` (a −2 on the reference board).
> This does **not** change the fold's behavior-neutrality (the decision-equivalence golden is
> unchanged); only the *cost* claim is corrected. Only the rerun decides the latency verdict.

---

## 4. Verified code paths and call-sites (machine-checked at `b09d6a6`)

Every anchor below was grepped/read against the current commit.

**Spawn origin — `SubprocessCalcBackend` (oneshot):**
- Docstring "One-shot `node calc.mjs` per batch" — `engine/calc/client.py:36-38`.
- Damage batch spawn: `damage_batch_calls += 1` at `client.py:64`; `spawn_count += 1` /
  `transport_attempts += 1` at `client.py:72-73`; `subprocess.run([node, script])` at `client.py:74`.
- Second spawn site `_run` (serves stats+types), `client.py:103-116`; `spawn_count += 1` at `:107`.
- `stats_batch` `client.py:133`; `types_batch` `client.py:144`; each single-kind payload, one `_run`
  spawn per call.
- Backend selection `make_calc_backend` `client.py:343-357`: `SHOWDOWN_CALC_BACKEND` unset/""/"oneshot"
  → `SubprocessCalcBackend` (`client.py:350-351`).

**Counter snapshot / spawn accounting:**
- `snapshot_calc_counters(oracle, backend)` reads `damage_batch_calls` from `oracle.batch_calls` but
  `stats/types/transport_attempts/spawn_count` from `backend` — `eval/decision_profile.py:245-260`.
- `spawn_calls = Δspawn_count`; `transport_calls = Δdmg + Δstats + Δtypes`; `transport_retried =
  transport_attempts > transport_calls` — `decision_profile.py:280-285`. The gap makes
  `transport_retried` True on all 60 gate rows even though oneshot performs no retry; it is the
  un-oracled game-mode damage, not a transport retry.

**The measured gap: the INITIAL classification damage bypasses the shared oracle (Lever A target):**
- `ko_threat_counts` incoming → `calc.damage_batch(flat)` at `engine/belief/game_mode.py:103`.
- `compute_game_mode` outgoing → `calc.damage_batch(outgoing)` at `game_mode.py:195` (only reached
  when not `MUST_REACT`, which is why the gap is 1 on must-react boards and 2 otherwise).
- Both are driven by the single `classify_game_mode` at `battle/decision.py:397` (before the scoring
  oracle exists). `mode` is consumed later by `aggregate_scores` (`decision.py:548, 618, 1165`), so
  the classification may be resolved after the scoring flush.

**NOT the gap — post-scoring trace diagnostics (out of scope, unchanged by Lever A):**
- The decision-level `ko_threat_counts` at `decision.py:933` (mega) / `:1134` (legacy) and the
  per-candidate `guaranteed_ohko` (`game_mode.py:134`) at `decision.py:959` / `:1156` all run in the
  **post-scoring trace population** — but not all after the candidate sort: `ko_threat_counts` runs
  **before** the sort (`decision.py:967` mega / `scored.sort` `:1168` legacy), and `guaranteed_ohko`
  runs **after** it during candidate building (called at `decision.py:979` / `:1177`). All four fill
  `CandidateTrace` model features and are not part of the frozen rows' measured game-mode gap; they
  are left untouched (folding them would require a later implicit flush or a large pre-computation).

**The single scoring damage flush (already consolidated):**
- `shared_oracle = oracle or DamageOracle()` at `decision.py:444`; `shared_oracle.flush()` at
  `decision.py:460`; Phase-B `oracle.flush()` on the mega path at `battle/mega_scoring.py:661`.
- `DamageOracle.request/flush/get/damage` seam — `battle/oracle.py:63-130`: `request` enqueues and
  dedups by full payload (`_key`, `oracle.py:57-61`); `flush` fires one `client.damage_batch` for the
  whole pending set (`oracle.py:79-111`); `get` auto-flushes a still-pending key (`oracle.py:113-125`).

**Stats/types spawns (Phase A, upstream of the flush):**
- `SpeedOracle._base_speed` → `stats_batch([spec])` at `engine/speed.py:120`, cached in `_spe_cache`.
- `SpeedOracle.opponent_range` at `engine/speed.py:133` → `stats_batch(specs)` **uncached** (re-spawns
  on every reach that lacks a curated opponent set).
- `SpeciesDex.types` → `types_batch([species])` at `battle/opponent.py:49`, cached in `_cache`.
- Per-battle caches built once and threaded into every decision (gauntlet `_decision_deps`).

**Heterogeneous dispatch already exists in the JS (the Lever-B enabler):**
- `calc.mjs:129` `if (req.kind === "stats") return runStats(gens.get(genNum), req)`; `calc.mjs:130`
  `if (req.kind === "types") return runTypes(gens.get(genNum), req)`; default is damage. `calc.mjs:150`
  `requests.map((req) =>
  dispatch(gens, req))` over the whole stdin array. A single process can therefore answer a mixed
  damage+stats+types payload; homogeneity is imposed only by the three separate Python methods.

**Timed window:**
- `agent_choose` timer `start = time.perf_counter()` at `client/gauntlet.py:661`, with
  `snapshot_calc_counters` taken immediately before and after (import at `gauntlet.py:18`). Every
  spawn described above is inside the gated window.

---

## 5. Discarded approaches (with reasons)

- **Switch to the persistent backend.** Forbidden by the guardrails — a backend switch is exactly the
  kind of "optimization" that changes the pinned `oneshot` gate rather than the code under it. Also
  changes `config_hash` and is not comparable. Rejected outright.
- **Reduce candidates / branches / search depth / click-rate.** Changes candidate coverage, score,
  action selection, or belief-state semantics — a strength/behavior change to make the gate pass.
  Forbidden. Rejected.
- **Cherry-pick battles/decisions, or shift the budget.** Forbidden by the guardrails. Rejected.
- **Cache `opponent_range` (speed.py:133) only.** A genuine caching gap, but in the frozen live data
  `stats_batch_calls` is only 2–3 per gate decision (opponents mostly had curated sets, routing to the
  cached `likely_speed`/`_base_speed` path), so this alone removes almost no gate spawns. **Excluded**
  from this slice per the review (§14, decision 3) — too little demonstrated benefit for the scope.
- **Make `compute_game_mode` skip the outgoing batch more aggressively.** The short-circuit already
  skips `outgoing` on `MUST_REACT` boards (that is why the gap is 1 there). Skipping more would change
  the classification result — a behavior change. Rejected.
- **A generic "coalesce all three kinds into one round trip".** The damage flush depends on the
  Phase-A speed/type results (speed → move order, types → chosen move → which damage is enqueued), a
  hard data dependency (`mega_scoring.py` Phase A at 494–658 precedes Phase B `oracle.flush()` at
  661). Damage cannot share a round trip with the stats/types that feed it. Only same-phase,
  mutually independent work may be coalesced. This is why Levers A and B are scoped as they are.

---

## 6. Recommended optimization and its exact scope boundary

**Recommended slice: Lever A — fold the *initial* game-mode classification's incoming (`ko_threat`)
damage into the single existing scoring flush, so it stops paying its own spawn.** This removes
**at least one** spawn per decision (the incoming always folds; the conditional outgoing additionally
folds when its calcs are cache-served — board-/cache-dependent, see the §3.4 Erratum), while preserving
the outgoing's short-circuit (§3.4).

Rationale: it targets the clearest defect (classification damage that should have used the batching
seam), **reuses the existing `DamageOracle`** rather than building new infrastructure, and has the
**strongest behavior-neutrality proof** (identical `DamageRequest` objects, resolved by the same
dedup-and-flush, yield identical `DamageResult`s → identical `GameMode` → identical scores and action).

**Viable order (preserves the short-circuit, removes ≥ one spawn — see the §3.4 Erratum):**
1. Build the game-mode **incoming** requests and enqueue them into the shared scoring oracle.
2. Enqueue all scoring requests.
3. **First flush** — incoming + scoring together (this is the fold; incoming no longer spawns alone).
4. Read the incoming results and evaluate the incoming threat.
5. If the **base** classification short-circuits — `compute_game_mode` sees `threatened > 0` and
   returns `MUST_REACT` (game_mode.py:173, driven by the incoming `ko_threat_counts` at
   game_mode.py:170) — then **no outgoing** request is built or sent. This is precisely the
   calc-based base `MUST_REACT` inside `compute_game_mode`, not any later/extended `MUST_REACT`.
6. Otherwise: enqueue outgoing and resolve it with a **second flush**.
7. Determine `GameMode`, then score from the already-cached scoring results.

The "incoming and outgoing must share one flush" idea is impossible: `compute_game_mode` needs the
incoming result (game_mode.py:170) before it can decide whether outgoing is computed at all
(game_mode.py:195). Folding only outgoing (incoming resolved separately) removes a spawn just on the
`gap=2` rows and leaves a ~1109.795 ms row → still FAIL (§3.4). Computing outgoing unconditionally to
force one flush is rejected as non-neutral (it enlarges the error domain — §7).

**Exact scope boundary (in-scope) — the INITIAL classification only:**
- The single `classify_game_mode` call at `battle/decision.py:397` and the `compute_game_mode` /
  `ko_threat_counts` it drives (`engine/belief/game_mode.py:140, 68`). Their `incoming` requests are
  enqueued into the shared scoring oracle and resolved by the existing flush (`decision.py:460`, mega
  `mega_scoring.py:661`); `mode` is classified from the flushed results (order-legal because `mode` is
  only consumed at `aggregate_scores`, `decision.py:548/618/1165`).
- No change to what is scored, how it is scored, tie-breaking, candidate enumeration, belief updates,
  or seed usage.

**Explicitly OUT of scope (unchanged by this slice):**
- The **post-scoring trace-diagnostic** call-sites — `ko_threat_counts` at `decision.py:933` / `:1134`
  and `guaranteed_ohko` at `decision.py:959` / `:1156` — which populate `CandidateTrace` model
  features *after* the scoring flush. All four are post-scoring, but not all after the candidate sort:
  `ko_threat_counts` runs **before** the sort (`decision.py:967` / `:1168`) and `guaranteed_ohko`
  **after** it during candidate building (`decision.py:979` / `:1177`). Routing them through the shared
  flush would need a later implicit flush or a large pre-computation of all trace requests; that is a
  separate concern and is left untouched. They are not part of the measured game-mode gap of the
  frozen I8-D rows.
- stats/types coalescing (Lever B), any speed/dex cache redesign, any `calc.mjs` change, any backend
  change.

**Lever B is NOT part of this slice and is NOT pre-authorized.** If, after this slice is merged, the
unchanged repeat gate does not clear the budget with margin, Lever B becomes a **separate, later
design slice** (its own PROPOSED design, its own review). For reference only: Lever B = a stats/types
prefetch-and-flush seam (analogous to `DamageOracle`) issuing one heterogeneous `node calc.mjs` round
trip per decision for all speed (`stats`) and typing (`types`) lookups, leveraging the existing
per-item `kind` dispatch (`calc.mjs:129-130,150`), over `SpeedOracle` (`engine/speed.py`) and
`SpeciesDex` (`battle/opponent.py`); projected p95 ≈ 670 ms but a harder neutrality proof. It is
neither designed nor implemented here.

The recommendation is Lever A as the minimal-invasive slice; its thin projected margin is the open
decision for review (§14).

---

## 7. Behavior-neutrality contract (Lever A)

The change is behavior-neutral iff, on an identical board and seed, every one of the following is
byte-identical before and after:

1. **Score vectors** for every candidate (per response, per world, per branch).
2. **Chosen action** and its **tie-breaking** order.
3. **Candidate coverage** — the same candidate set is enumerated and scored.
4. **`GameMode` classification** (`MUST_REACT` / `AHEAD` / `NEUTRAL`) for every decision.
5. **Belief-state semantics** — opponent-set and spread beliefs are unchanged.
6. **Determinism** — same seed ⇒ same decisions and same order log; no new RNG draw, no reordering
   that could change a tie.

Why it holds: the game-mode `DamageRequest`s are constructed from the same state/book/profile
(`game_mode.py:_ko_request`, `_our_attacker`); routing them through `DamageOracle.request`/`flush`/
`get` returns the same `DamageResult`s (the oracle dedups by the full semantic payload — `oracle.py:
57-61` — so identical calcs collide only when genuinely identical; a game-mode request that collides
with a scoring request is computed once and both read the same result, which is still the same value).
`GameMode` reads those results through the same comparisons (`is_guaranteed_ohko`, `can_ohko`), so the
mode is identical; `aggregate_scores` then combines identical scores under the identical mode.

The contract governs **decisions, scores, and visible outputs — not internal transport**. Lever A
changes transport ordering and the calc counters (`spawn_calls`, `transport_*`, `damage_batch_calls`)
by design; that is not a behavior change. Only items 1–6 above must hold.

Error-domain preservation is built into the order (§6): the short-circuit is **kept**, so on a
`MUST_REACT` board **no outgoing request is ever built or sent** — exactly as today. The set of calc
requests that can raise is therefore unchanged: incoming is always computed (before and after), and
outgoing is computed only when not `MUST_REACT` (before and after). Lever A only moves *where* incoming
is resolved (into the existing flush), never *whether* a request is issued. This is why the rejected
"compute outgoing unconditionally" variant is out: it would issue an outgoing request on `MUST_REACT`
boards that the code never sends today, enlarging the error domain — not neutral.

Neutrality is proven **offline** by a decision-equivalence corpus (§10, §11), not by any live run.

---

## 8. Error, timeout, retry, and cache semantics

- **Oneshot has no retry.** `SubprocessCalcBackend.calc_batch`/`_run` do one `subprocess.run` each and
  raise `CalcError` on non-zero exit, timeout, or malformed JSON (`client.py:82-100, 117-131`). Lever A
  does not add retry and does not change this. `transport_attempts` continues to equal `spawn_calls`.
- **Flush error path unchanged.** `DamageOracle.flush` counts the attempt *before* the round trip
  (`oracle.py:103-108`) so a batch that raises still increments `batch_calls` and its planned/implicit
  split; the exception propagates to the caller exactly as a direct `calc.damage_batch` would. Folding
  game-mode requests into the flush means a calc failure surfaces as one `CalcError` from the shared
  flush instead of from a separate game-mode call — same failure, same non-ok row semantics, same
  fail-closed behavior at the gate (`outcome != "ok"` ⇒ excluded from the active population).
- **Timeout.** The per-battle `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` stays **unset** (standard default);
  it is behavior-affecting and part of `config_hash 594295543f13a55d`, so it is not touched. The calc
  subprocess timeout (`client.py:46`, 20 s) is unchanged.
- **Caches.** `DamageOracle._cache`/`_pending` dedup is unchanged; `SpeedOracle._spe_cache` and
  `SpeciesDex._cache` are untouched by Lever A. Fewer spawns come purely from batching, never from
  dropping a computation or changing a cache key. `planned_damage_batches` / `implicit_damage_batches`
  accounting stays valid (the oracle owns it).
- **Determinism/isolation.** No new process lifetime, no shared state across decisions, no RNG change.

---

## 9. RED→GREEN test matrix (to be implemented in the code slice, not here)

| # | RED (fails before) | GREEN (passes after) | guards |
|---|---|---|---|
| T1 | the initial classification's damage is separate `calc.damage_batch` calls on a private oracle (pre-fold `spawn_count = 3` on the reference board) | all classification damage routes through the SHARED oracle: `spawn_count == oracle.batch_calls` and `spawn_calls` drops by **≥ 1** (incoming always folds; the conditional outgoing additionally folds when its calcs are cache-served — observed **−2**, `damage_batch_calls` unchanged; see §3.4 Erratum) | asserts the reduction as a **counter** fact, offline, no latency timing |
| T2 | — | **Decision equivalence:** on a fixed corpus of foe-Mega boards + seeds, the chosen action, full score vectors, tie-break order, and `GameMode` are **identical** before/after | the behavior-neutrality contract (§7) |
| T3 | — | `GameMode` classification identical on `MUST_REACT`, `AHEAD`, and `NEUTRAL` boards, and on a `MUST_REACT` board **no outgoing request is built or sent** (short-circuit preserved) | §6 order, §7 error domain |
| T4 | — | a calc failure during the shared flush raises `CalcError` and produces a non-ok row (fail-closed), exactly as the direct path did | §8 error semantics |
| T5 | — | Reg-I / `format_config=None` and non-foe-Mega decisions: the chosen action, scores, and visible outputs are **identical** before/after. **Not** internal transport bytes — `classify_game_mode` is format-independent, so Lever A intentionally changes transport ordering and calc counters on these paths too; only the decisions/outputs must match | decision-level equivalence, not transport identity |
| T6 | — | `config_hash` still resolves to `594295543f13a55d`; no behavior-affecting env var added (`eval/config_env.py` unchanged) | gate comparability |

Existing regression suites that MUST stay green unchanged: the full test suite (baseline **2783
passed / 1 skipped / 1 xfailed** at the FAIL-evidence merge), specifically the calc/oracle tests, the
I7b mega-scoring tests (`tests/i7b/test_i7b_scoring.py`), `tests/test_baselines.py`, the decision/
search tests, and the I8 profile/validator tests. `battle/search.py` and the scoring math must be
byte-identical.

---

## 10. Offline acceptance criteria (no live run)

The slice is accepted for merge on offline evidence only:

1. Full test suite green with no new skips/xfails versus the `b09d6a6` baseline.
2. New tests T1–T6 present and green (RED demonstrated for T1).
3. **Decision equivalence proven** on the fixed offline corpus (T2/T3/T5) — same seed ⇒ identical
   decisions, byte-for-byte.
4. **Spawn reduction demonstrated as a counter fact** (T1), offline, with **no latency benchmark and
   no timing claim** — the design does not assert milliseconds saved; only that the number of spawns
   per decision drops.
5. `config_hash` unchanged (`594295543f13a55d`); `git diff` touches only the in-scope files (§6);
   `git diff --check` clean; LF hygiene preserved.
6. No server, battle, microprofile, or gate run performed for acceptance.

Explicitly **not** an acceptance criterion: any p95 or latency number. Latency is decided only by the
later repeat gate.

---

## 11. Conditions for the later, separate live-run authorization

After the code slice is merged, a repeat I8-D gate may be authorized **separately** under exactly the
frozen conditions:

- Host = the fixed Windows host; server pinned at `f8ac140` + the seeded-battle patch; fresh seeded
  server; clean tree; run from the repo root with `--teams-root showdown_bot`.
- `SHOWDOWN_CALC_BACKEND=oneshot`; `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` unset; `config_hash`
  `594295543f13a55d`; seed 0; unchanged schedule/panel/teams (`schedule_hash a1192d9dde4c65df`,
  `panel_hash aac1ea30446fde88`).
- Same gate binary/CLI (`i8d-live-gate`), same D-1/D-2, same active population and p95 function.
- New `git_sha` (the optimization commit) is expected and correct — the guardrail fixes config, not
  code. Only `git_sha` changes; `config_hash` must not.
- Fail-closed, one run, no auto-retry; the only admissible verdicts remain `PASS`, `FAIL`, or
  `INCONCLUSIVE — exposure floor not met`; a technical abort is not a verdict.
- New frozen evidence in its own directory; the FAIL evidence is never overwritten or re-hashed.

## 12. Explicit rule on the repeat run

The gate run is **repeated unchanged only after this slice is merged and under its own separate
authorization**. This design does not authorize a run. No run may be started as part of implementing
the slice.

---

## 13. Non-claims

- **No latency PASS.** Nothing here shows the budget is met; the p95 numbers in §3.4 are model-based
  projections, not measurements.
- **No Strength claim.** Champions Strength remains NO-GO.
- **No new-benchmark claim.** No benchmark, microprofile, or gate was run; every figure is derived
  from the frozen FAIL evidence or read from the code at `b09d6a6`.
- The budget is not moved and the gate is not changed.

## 14. Resolved decisions (review, 2026-07-18)

1. **Implement Lever A alone.** The thin model margin (projected p95 **968.513 ms**, ~31 ms, 2/60 over)
   is accepted because the change is minimal and behavior-neutral; only the **unchanged live-gate
   rerun** decides PASS/FAIL. No latency claim is made from the projection.
2. **Lever B stays a separate, later design slice** — pursued only if the unchanged rerun of Lever A
   does not actually clear the budget. It is neither designed nor pre-authorized here.
3. **`opponent_range` cache is NOT included.** Too little demonstrated benefit on this dataset
   (stats already only 2–3/decision) to justify the extra scope; excluded from this slice.
4. **Short-circuit scope pinned** to the calc-based base `MUST_REACT` (`threatened > 0`,
   game_mode.py:173), not any later/extended `MUST_REACT` (§6, Step 5).

No open decisions remain.

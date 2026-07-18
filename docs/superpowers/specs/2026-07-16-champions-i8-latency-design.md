# Champions I8 — Active Foe-Mega Latency Profile & Budget Gate (measurement design)

**Status:** APPROVED — implementation planning allowed; no run authorized. D-1 (§5.4) is
closed. Approval covers **planning the implementation**: it authorizes no profile run, no live
run, no optimization, no Strength run and no measurement claim.

**Revision:** Rev. 11 + **Errata 1–2**. Each revision's errors are recorded in §9 rather than
silently rewritten. Erratum 1 corrects a self-contradiction Rev. 11 shipped: §2.7's manifest table
placed `warmup` at **run** level while §2.8, §2.4's validator list and §5.4's
`expected_cache_class` all read **`arm.warmup`**. It changes no decision, no gate and no D-1
term — it makes the manifest say what the rest of the design already required (§9, Erratum 1).
Erratum 2 (C3, found in implementation) precisifies §2.5's "contains the spawn? **no**" for the
narrow scope: it means *context construction is excluded*, **not** that `score()` cannot spawn —
arm 7 (no own Mega) is the real counterexample. No gate, no D-1 term, no arm changes (§9,
Erratum 2).
Rev. 11 fixes three contradictions Rev. 10's own cache/backend rules introduced: they were
written for microprofile rows but applied to **every** row, so a live row — which has no arm, no
`rep` and no declared lifecycle — could not satisfy them (§2.4); `expected_cache_class` branched
on `rep > 1`/`rep == 1` while `rep` is **0-based** (§2.4:440), leaving the genuinely cold first
rep matching **no branch** and calling the warm second rep cold (§2.8); and the backend rule
rejected a **legitimate respawn**, repeating entry 23's mistake in the same revision that claimed
not to (§2.8).
Rev. 10 closes the last gap between what the profile contract *declares* and what its validator
*enforces*: `cache_class` was asserted by the writer and bound to nothing (§5.5), so a row could
claim a cold cache while the manifest declared `per_arm` and pass every invariant — corrupting
the one contrast this slice exists to protect. It is now **falsifiable** rather than merely
declared. `source`/`timer_scope` compatibility is likewise enforced instead of tabulated.
Rev. 9 fixes an input the manifest producer **cannot obtain** — `_mega_req()` passes its payload
dict straight into `BattleRequest.model_validate({...})` and returns only the model, so Rev. 8's
"raw request payload dict" is unreachable (§2.7) — plus two citation defects: an **invented
symbol** (`apply_packed_team_items` does not exist) and an anchor pointing at a docstring instead
of the code it describes.

Rev. 8 fixes three defects **in the field Rev. 7 introduced**, and removes the reflex behind all
three. Rev. 7 added `items` to the fixture hash — and then **sorted** it. It sorted
`legal_actions` too. Both destroy meaning:

- `default_spreads.yaml:12` says it outright — *"items: candidate held items (first is the
  default assumption)"* — and production reads `preset.items[0]` (`hypotheses.py:109`,
  `spreads.py:89-91`). Sorting `[Life Orb, Choice Specs, Focus Sash]` makes the assumed item
  **Choice Specs**.
- Enumeration order is binding for first-wins ties, and `mega_scoring.py:184-198` records that
  as a past **Codex merge-blocker**.

So Rev. 7 reproduced, one level down, the exact defect it was fixing: two different fixtures
mapping to one hash. The reflex was *"canonicalise by sorting"*. Rev. 8 replaces it with a rule
that follows from the source types:

> **Sort only what has no order.** A `set` must be sorted — it has no order to preserve. A
> `list` must never be sorted — its order is either meaningful or, at minimum, not ours to
> discard. For a fixture hash the asymmetry is decisive: over-discrimination is harmless (two
> equivalent fixtures get two hashes), under-discrimination is not (two different fixtures get
> one).

And **§2.7 no longer hand-lists fields at all** (Rev. 5 missed eight inputs, Rev. 6 missed
`items`, Rev. 7 mis-typed the DTO). Serialisation is **recursive over `dataclasses.fields()`**,
and the fail-closed rule now fires on an unhandled **type** — a closed, verified set — not on a
field name someone forgot to list.

The third defect: `our_spreads`/`opp_sets`/`book` hold **`SpeciesSpreads`** (`offense` +
`defense`), not a bare `SpreadPreset`; both branches are behaviour-relevant.

**Base commit:** `f824239146270f69b21734fc1c90cd4a8ee9a41f` (`main`, == `origin/main`), which
contains PR #17 (`8942232`) and the post-I7b-C status reconciliation.

**Scope:** define *how* Champions decision latency will be measured and gated, and *what a
result would be allowed to claim*. This document authorizes no run and no code.

This spec is self-contained. Every file, symbol, line number, env var and number below was
verified against the base commit. Where something does not exist, it says so.

---

## 0. Why this slice exists, and what the existing numbers actually say

`docs/ROADMAP.md` binds the order **latency → coverage/holdout → Strength**, with the
dedicated Champions latency profile as the load-bearing blocker. Two latency numbers are in
circulation. **Both are re-derived below from the committed artifacts, and neither means what
a casual reading suggests.**

### 0.1 The I7b-C smoke's "worst p95 672 ms" is not a foe-Mega measurement

Re-derived from `data/eval/champions-panel-v0/smoke-i7b-mega/` (`decision_trace.jsonl` joined
to `opp_mega_trace.jsonl` on `(battle_id, decision_index)`). **All 17 non-preview decisions of
the frozen run, complete and exact:**

| hero candidates | `decision_latency_ms` | battle#idx | foe-Mega active? |
|---|---|---|---|
| 104 | **671.5** | `bc08ec1e#1` | no |
| 104 | 421.1 | `242a0c3e#1` | no |
| 45 | 185.2 | `bc08ec1e#3` | no |
| 45 | 140.9 | `bc08ec1e#2` | no |
| 45 | 102.5 | `242a0c3e#2` | no |
| 41 | 96.9 | `bc08ec1e#6` | no |
| 41 | **83.0** | `242a0c3e#4` | **ACTIVE** |
| 41 | 76.9 | `bc08ec1e#5` | no |
| 25 | 60.3 | `242a0c3e#6` | no |
| 5 | 19.2 | `bc08ec1e#8` | no |
| 5 | 14.6 | `bc08ec1e#9` | no |
| 5 | 13.3 | `bc08ec1e#10` | no |
| 5 | 6.2 | `242a0c3e#7` | no |
| 2 | 5.7 | `bc08ec1e#4` | no |
| 2 | 3.7 | `242a0c3e#3` | no |
| 1 | 3.1 | `242a0c3e#5` | no |
| 2 | 2.3 | `bc08ec1e#7` | no |

**Pearson r(candidates, latency) = 0.9210 over n = 17** (computed with
`statistics.correlation` on the frozen rows).

Three facts follow, and they set this slice's whole direction:

1. **The 672 ms worst p95 came from an INACTIVE decision** — a turn-1 board with 104 hero
   candidates and `required_classes == ["none"]`. It contains no opponent-Mega work at all.
2. **Latency tracks hero-candidate count** (r = 0.921), not foe-Mega activity.
3. **The one active decision (83.0 ms) sat mid-pack**, between its inactive 41-candidate peers
   at 76.9 ms and 96.9 ms. Its foe-Mega cost is not separable from noise at n = 1.

So the existing p95 does not measure the thing this slice is about. That is not a flaw in the
smoke — it was a safety/telemetry gate and says so — but it means **a latency verdict must
never be read off the aggregate p95.**

*Caveat on r itself:* candidate count is confounded with turn number (turn 1 has the most legal
actions). r = 0.921 says candidate count predicts latency in this run; it does not isolate
candidate count as the *cause*. Only the microprofile (§3.A), which varies V at a fixed board,
can do that.

### 0.2 The single live active decision exercised the *cheap* half of the foe-Mega path

From the frozen sidecar row (`battle 242a0c3ec6d0e79c`, `decision_index=4`):

- `branch_indices` distinct = `[0]`, `branch_weights` distinct = `[1.0]` → **exactly one
  projection branch at weight 1.0**, i.e. the *unequal pre-Mega speed* case
  (`engine/mega_projection.py:201-203`; a tie yields two branches at 0.5).
- Responses/candidate = **5**, `max_candidates` = **5** → the decision sat **at the cap**.
  `required_classes == retained_classes == ["1", "none"]`.
- Comparable inactive 41-candidate decisions carried **4** responses/candidate; another
  inactive decision (`bc08ec1e#2`, 45 candidates) carried **5**.

So the foe-Mega class **competes for cap slots** rather than adding freely: with
`DEFAULT_MAX_CANDIDATES = 5` (`battle/opponent.py:259`) and a coverage-preserving
reserve/truncate (`battle/opponent.py:377-382`, `:437-442`), the marginal response cost is
bounded by the cap and can be zero. **The expensive regime — the exact-speed tie with two
branches — was never exercised live.**

### 0.3 The "≈2.4×" is a batch-count effect, measured under the DEFAULT backend

The plan (`docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md:205-212`) records
the controlled I7b-B measurement verbatim, including its own methodology line "different
harness, synthetic fixture, **cold Node subprocess**":

| path | backend batches | ≈ wall clock | ms per batch |
|---|---|---|---|
| inactive (`eligibility=None`) | 6 | ~1116 ms | ~186 |
| active, rate `0.0` | 6 | ~1158 ms | ~193 |
| active, rate `0.35` | 16 | ~2676 ms | ~167 |
| active, rate `1.0` | 16 | ~2641 ms | ~165 |

**Per-batch cost is roughly constant; wall clock scales with batch count.**
`2676/1116 = 2.40` ≈ `16/6 = 2.67`. Under `oneshot` a "batch" is one
`subprocess.run([node, calc.mjs])` — a fresh Node process per batch, "~50-100ms each" by the
code's own estimate (`engine/calc/client.py:37-38`, spawn at `:58-65`).

**Which backend is which, stated precisely** (`make_calc_backend()`,
`engine/calc/client.py:306-320`):

| | backend | who uses it |
|---|---|---|
| `SHOWDOWN_CALC_BACKEND` unset / `""` / `"oneshot"` | `SubprocessCalcBackend` | **the default — i.e. the default production configuration**, and what the ≈2.4× measurement ran under |
| `"persistent"` | `PersistentCalcBackend` | an explicit opt-in. **The I7b-C smoke set it** (`reports/champions-panel-v0-i7b-mega-smoke.md`) |

So the ≈2.4× was measured under the **default** backend, and the smoke was the **deviation** —
not the other way round. Two consequences:

- **The ≈2.4× is dominated by process spawns, not by scoring complexity.** It is a *batch
  count* finding wearing a *wall clock* costume.
- **The 2.4× and the smoke's 83 ms describe different backends and cannot be compared.**
  Neither is "the" foe-Mega cost. Both remain valid *for their own configuration*.

### 0.4 Why 16 batches for one decision — the real cost mechanism

`score_evaluated_variants` performs **exactly one explicit `oracle.flush()` per world**
(`battle/mega_scoring.py:625-626`; the only `.flush()` in the file), and the default world
count is 1 (`SHOWDOWN_WORLD_SAMPLES` default `"1"`,
`engine/belief/world_sampler.py:19-25`). One planned flush cannot produce 6 or 16 batches.

The remainder are **implicit flushes**. `DamageOracle.get` auto-flushes the entire pending map
when its key is not yet resolved (`battle/oracle.py:55-58`), and `DamageModel.damage_fn` reads
via `self.oracle.get(self.oracle.request(req))` (`battle/evaluate.py:295`). Every **prefetch
miss** in Phase C therefore triggers a full inline round trip — under `oneshot`, a full Node
spawn, mid-decision.

**That is the cost model this slice must measure:** not "foe-Mega is 2.4× slower", but *how
many round trips a decision makes, which are planned, which are prefetch misses, and which of
them the foe-Mega path adds.*

`DamageOracle.batch_calls` counts **damage** batches (`battle/oracle.py:26`, incremented at
`:50` inside `flush`, which early-returns on empty at `:42-43` — so it counts non-empty damage
batches only). **It is written and never read anywhere in `src/`.**

**It is not a round-trip counter.** **Three** call sites on the measured decision path reach the
shared backend *without* going through the oracle — each a full transport call, and under
`oneshot` a fresh Node process:

| call site | method | on the decision path? |
|---|---|---|
| `engine/speed.py:120` (`SpeedOracle`, single) | `backend.stats_batch` | **yes** |
| `engine/speed.py:149` (`SpeedOracle`, batched) | `backend.stats_batch` | **yes** |
| `battle/opponent.py:49` (`SpeciesDex.types`) | `backend.types_batch` | **yes** |
| `engine/belief/hypotheses.py:207` | `backend.types_batch` | **no — excluded, see below** |

Speed and typing lookups are exactly what a first Mega context needs, so they can be the calls
that *start* the process. A profile counting only `batch_calls` would make that cost invisible.
§2.4's contract therefore counts transport at the **backend**, not at the oracle.

**`hypotheses.py:207` is deliberately excluded** (Rev. 4 correction — Rev. 3 wrongly listed it
as a fourth per-decision site). `load_opp_sets_for_format` is called once at run setup
(`client/gauntlet.py:913`), constructs its **own** `SubprocessCalcBackend()`
(`hypotheses.py:204`) rather than the decision's shared backend, and runs entirely outside the
decision timer. It is a real oracle bypass and a real Node cost — but it is **run-setup cost,
not per-decision transport**, and a profile row must not attribute it to a decision.

---

## 1. Verified call and cost graph

Path: `handle_request → agent_choose → _choose_best → _choose_best_mega →
score_evaluated_variants → (enqueue → flush → evaluate) → optional depth-2`.

### 1.1 Where the timer starts and stops

| | file:line | code |
|---|---|---|
| start | `client/gauntlet.py:625` | `start = time.perf_counter()` |
| stop | `client/gauntlet.py:652` | `decision_latency_ms = (time.perf_counter() - start) * 1000` |

The window contains **only** `agent_choose(...)` (`gauntlet.py:626-636`) and its crash handler
(`:637-648`). There is no `await` inside it.

### 1.2 What is inside vs outside `decision_latency_ms`

**Inside, and load-bearing: the first Node spawn of the battle.** `_decision_deps()`
(`gauntlet.py:598` → def at `:433`, construction body `:457-480`) **constructs objects only and makes no backend call**:

- `CalcClient()` (`:461`) → `self.backend = backend or make_calc_backend()` (`client.py:328`)
  — constructs the backend object.
- `PersistentCalcBackend.__init__` sets `self._proc = None` (`client.py:167`); the spawn is
  lazy via `_ensure()` (`client.py:176-180`) on the first `_run_once` (`client.py:252`).
- `SpeedOracle.__init__` stores the backend and an empty `_spe_cache` (`engine/speed.py:96-104`).
- `SpeciesDex.__init__` stores the backend and an empty `_cache`; `types()` is lazy
  (`battle/opponent.py:39-50`).

So **no process starts in `_decision_deps()`**. The first Node process starts on the first
`calc_batch` / `types_batch` / `stats_batch`, which happens **inside `agent_choose`** — i.e.
**inside the timer**. Under `oneshot` every batch spawns anyway; under `persistent` the boot
lands in whichever decision issues the first request. The battle's first decision therefore
**includes** a cold start in both backends.

**Outside, before the start:**

| work | file:line | why it matters |
|---|---|---|
| request parse | `gauntlet.py:540` | small |
| **state build** | `gauntlet.py:551` → `_state_for` `:525-534` | `BattleState.from_log_text("\n".join(room_raw))` — a **full re-replay of the accumulated room log on every decision**, growing with turn count. Entirely unmeasured. |
| `DecisionTrace()` | `gauntlet.py:558-560`, `:587-588` | |
| `prepare_capture` | `gauntlet.py:593` | `copy.deepcopy(state)` + 2 canonical-JSON sha256 (`decision_capture.py:119`, `:130-131`) |
| `_decision_deps()` **object construction** | `gauntlet.py:598` | constructor cost only — see above; the spawn is **not** here |
| reranker override | `gauntlet.py:603` | lazy lightgbm import + Booster load |

**Outside, after the stop:** the WebSocket send (`gauntlet.py:655`, documented at `:649-651`),
all three sidecar writes (`:666-681`, `:689-706`, `:712-732`), export observe (`:737-746`), and
the reranker shadow — which **awaits up to `sh.timeout_ms`** (`gauntlet.py:766`), uncounted.

**Design consequence:** `decision_latency_ms` measures `agent_choose` alone — the decision core
**plus** any calc process start it triggers. It is the right quantity for a *decision-core*
budget and the wrong quantity for a *request-handling* budget. This spec keeps the existing
meaning and does not redefine it.

### 1.3 Flushes and batches per decision

| quantity | value | source |
|---|---|---|
| explicit flushes | **1 per world** | `mega_scoring.py:625-626` |
| worlds K | **1** by default | `SHOWDOWN_WORLD_SAMPLES`, `world_sampler.py:19-25`; gate at `mega_scoring.py:408` |
| pre-loop enqueues | folded into world 0's flush | `mega_scoring.py:236-237` |
| implicit flushes | **1 per prefetch miss**, unbounded | `oracle.py:55-58` ← `evaluate.py:295` |
| depth-2 round trips | up to `top_n × top_m` (default 2×2 = 4) | `search.py:99-111`, never flushes itself; `mega_scoring.py:753`, `:758`, `:775` |
| batch → Node | `oneshot`: **one `subprocess.run` spawn per batch** | `client.py:53-84`, `:58-65` |
| | `persistent`: one NDJSON line to a long-lived process | `client.py:277-283`, `:251-273` |

### 1.4 Batching and deduplication

- **Batching:** one batch = one `list[DamageRequest]` → `CalcClient.damage_batch`
  (`client.py:338-357`) → `backend.calc_batch`. The oracle emits exactly one batch per flush
  (`oracle.py:49`).
- **Dedup: YES, in the oracle only.** `request()` skips keys already in `_cache` or `_pending`
  (`oracle.py:34-39`). `_pending` dedupes within a batch; `_cache` across batches. Key = full
  `to_payload()` minus `id`, canonical JSON (`oracle.py:28-32`).
- **Dedup in `CalcClient`: DOES NOT EXIST** — `damage_batch` re-ids and forwards everything
  (`client.py:338-345`).

Because all contexts share one injected oracle (`mega_scoring.py:470-474`, `:590-594`), the
`C × (1 + F×B)` model fan-out collapses at the `_pending` map.

### 1.5 Caches and their lifetimes

| cache | where | key | lifetime |
|---|---|---|---|
| `DamageOracle._cache` | `oracle.py:24` | canonical payload minus `id` | **the oracle object's**; never cleared, never evicted, unbounded (`_pending.clear()` at `:53` is the only clear) |
| production scope | `gauntlet.py:459-462` | — | **one CalcClient+DamageOracle per battle**, torn down at `:812-814` |
| decision scope | `decision.py:331-332`, `:442`; `baselines.py:55-56`; `evaluate.py:220` | — | per decision when no oracle is injected |
| `SpeedOracle._spe_cache` | `engine/speed.py:103` | — | the SpeedOracle object's |
| `SpeciesDex._cache` | `battle/opponent.py:45` | species name | the dex object's |
| `CalcClient` / backends | — | — | **DOES NOT EXIST** |

**Cold vs warm reuse:** the damage cache spans worlds and decisions **within a battle** and is
never shared across battles. Under `persistent`, the Node process itself also warms
(`spawn_count`, `client.py:171`, `:199`). Under `oneshot` there is nothing to warm.

### 1.6 Size drivers (all verified)

| symbol | meaning | default / bound | source |
|---|---|---|---|
| **K** | worlds | 1 | `world_sampler.py:19-25` |
| **C** | contexts = 1 + projectable own-Mega slots | ≤ 3 (doubles) | `mega_scoring.py:215-217`, `:393` |
| **V** | hero candidates (records) | measured 1–104 live | `mega_scoring.py:422-428` |
| **R** | opponent responses per candidate | **≤ 5** | `DEFAULT_MAX_CANDIDATES = 5`, `opponent.py:259`, `:270`, applied `:365` / `:442` |
| **F** | eligible foe-Mega slots with weight > 0 | ≤ 2 | `mega_scoring.py:516-519` |
| **B** | projection branches per (slot, foe slot) | **1** (unequal speed) or **2** (exact tie) | `mega_projection.py:201-203` |
| **top_n** | depth-2 record frontier | 2 | `decision.py:66-76` |
| **top_m** | depth-2 response frontier | 2 | `decision.py:79-88` |

Composite: evaluation fan-out ≈ `K × Σ_slot [ V_slot × (R + Σ_branches R_branch) ]` calls to
`_evaluate_line_details`.

**Round trips vs fan-out — precisely.** *Planned* round trips are **not** multiplied by V/R/C:
they are `K` (one flush per world), plus up to `top_n × top_m` under depth-2. **Implicit round
trips can scale with the V/R/C/B fan-out**, because each `_evaluate_line_details` leaf reaches
`damage_fn` → `oracle.get(...)`, and any key the enqueue phase did not prefetch triggers an
inline flush (`oracle.py:55-58`). Prefetch coverage is intended to make Phase C cache-hit-only
(`DamageModel.enqueue` → `_candidate_targets`, `evaluate.py:260-282`), **but nothing measures
or enforces it** — see F-3. Whether misses scale with fan-out in practice is one of the
questions this profile exists to answer; it must not be assumed in either direction.

**Hidden multipliers inside `_evaluate_line_details`** (they multiply Python work; whether they
also multiply round trips depends on prefetch coverage): a genuine speed tie evaluates both
orderings (`evaluate.py:535-537`), and `accuracy_mode` runs `resolve_turn_branches(...,
branch_cap=accuracy_branch_cap)` and scores every leaf (`evaluate.py:516-520`).

### 1.7 What is measured and persisted today

| metric | status |
|---|---|
| `decision_latency_ms` per decision | **EXISTS** — decision-trace-v3 only, written at `decision_capture.py:659`, required at `:548`. Hero client only. Classified volatile and excluded from repeat-identity diffing (`decision_diff.py:395`). **Never gated.** |
| `decision_latency_p95_ms` per battle | **EXISTS** — `_latency_p95` (`gauntlet.py:171-176`), emitted `:199-209`, persisted into the result row at `:1061`; required by `result_jsonl.py:20`. Nearest-rank, no interpolation; `round(...*1000)` → **integer ms** (`gauntlet.py:204`); hero-only. |
| the gate | **EXISTS** — `report.py:411-413`: `worst = max(per-battle p95)`, compared to `bundle.latency_budget_ms`, `soft=True` (WARN in `dev`, FAIL in `gate`). |
| `DamageOracle.batch_calls` | **EXISTS, never read** (`oracle.py:26`, `:50`) |
| `PersistentCalcBackend.spawn_count` | **EXISTS, never read in `src/`** (`client.py:171`, `:199`) |
| requests per batch | **DOES NOT EXIST** |
| planned vs implicit flush split | **DOES NOT EXIST** |
| cache hits / misses | **DOES NOT EXIST** — `oracle.request` branches on presence (`:37`) but counts nothing |
| any timing in `oracle.py` / `client.py` | **DOES NOT EXIST** — neither imports a timing module |
| candidate count per decision | derivable as `len(row["candidates"])` (`decision_capture.py:621-629`); **not stored as a field** |
| response / branch / world counts per decision | present as parallel-array lengths in the opp-mega sidecar **for every regular heuristic decision** (see §2.3), not as explicit fields |

### 1.8 The pinned budget, verbatim

`config/eval/gates.yaml` is six lines; line 6 is its only key:

```yaml
decision_latency_p95_budget_ms: 1000
```

Loaded by `load_latency_budget_ms` (`eval/gates.py:23-35`, positive non-bool int or
`GatesConfigError`). **No p50, p99 or max budget exists.** The file's own comment (line 4)
claims a "~200 ms" baseline against the 1000 ms pin.

**Contract conflict, recorded not resolved:** `cli.py:559-560` hard-codes a **second,
independent** threshold — `if p95 >= 1.5: failures.append(...)` — on the `--games N --strict`
path. It does **not** read `gates.yaml`. So 1000 ms and 1500 ms are two constants that can
drift apart. This spec **does not change either** (F-1).

---

## 2. Instrumentation

### 2.1 Metrics that are unavailable today and are load-bearing

| needed | today |
|---|---|
| round trips per decision | **nothing counts them.** `batch_calls` is damage-only, cumulative, and never read; `stats_batch`/`types_batch` bypass the oracle entirely (§0.4) |
| planned vs **implicit** damage batches | absent — the single most valuable missing number (§0.4). Cannot be derived by subtraction (§2.4) |
| requests per batch | absent |
| cache hits/misses | absent |
| Node spawns per decision | `spawn_count` exists on `PersistentCalcBackend` only, never read; `SubprocessCalcBackend` has **no counter at all** although it spawns per batch (F-8) |
| sub-ms resolution at battle level | destroyed by `round(...*1000)` (`gauntlet.py:204`); per-decision `decision_latency_ms` keeps float ms |

### 2.2 Would instrumentation change behavior or `config_hash`?

- **`config_hash`**: only `BEHAVIOR_AFFECTING` env vars enter it (`eval/config_env.py`). An
  off-by-default profiling sidecar changes no behavioural knob, so `config_hash` is unaffected
  **provided** its switch is classified `NON_BEHAVIORAL` — the `SHOWDOWN_OPP_MEGA_TRACE_OUT`
  precedent (`config_env.py`), which is what keeps telemetry-on and telemetry-off runs
  comparable.
- **Behaviour**: reading `perf_counter` and incrementing ints cannot change a `/choose`.
  `oracle.batch_calls` is **already** incremented today, so counting round trips needs no new
  production write — only a read.
- **The real risk is measurement distortion, not correctness.** Under `oneshot`, per-batch cost
  is ~165–190 ms and a counter is noise. Under `persistent` the margin is far smaller and a
  naive per-request timer could measurably inflate what it measures. **Binding: the profile
  sidecar records counters and one decision-level duration; it must not add per-request
  timing.**

### 2.3 Extend the existing sidecar, or a separate one?

**A separate, off-by-default profile sidecar. The opp-mega sidecar must not be extended.**

**Correction (Rev. 2):** Rev. 1 justified this partly by claiming the opp-mega sidecar only has
rows for foe-Mega decisions. **That is false.** Its writer fires for every successful regular
heuristic decision with battle state — the gate is `opp_mega_evidence is not None and
opp_mega_agent_ok` (`client/gauntlet.py`), and the frozen file proves it: **17 rows for 17
non-preview decisions — 16 entirely `foe_mega_slot=None`, 1 active, 0 empty.** Inactive
decisions *are* described. That reason is withdrawn.

Two reasons stand, each sufficient on its own:

1. **The schema is exact-closed.** `validate_opp_mega_trace_row` raises on any unknown field
   (`opp_mega_trace.py:115-121`); trace-v3 does the same (`decision_capture.py:570-573`).
   Adding a timing field is a schema change, and the I7b-C contract forbids one.
2. **Its rows are frozen provenance whose sha256 is pinned in a merged verdict report.** Timing
   is non-deterministic; mixing it into a byte-pinned artifact makes that artifact
   irreproducible by construction — the exact property I7b-C established.

A third, positive reason: the profile sidecar must also describe **microprofile** runs, which
have no `battle_id` at all (§2.4).

### 2.4 Profile sidecar — the contract

**This is an interface contract, not an implementation.** No code is written by this spec. It
is specified to this depth so an implementation plan does not have to invent the architecture.

**Module:** `showdown_bot/src/showdown_bot/eval/decision_profile.py` — a new module, mirroring
`eval/opp_mega_trace.py`'s split (context DTO / row builder / validator / writer).

**Env switch:** `SHOWDOWN_DECISION_PROFILE_OUT` — output path; **off when unset**. Must be
added to `NON_BEHAVIORAL` in `eval/config_env.py` (IO path; the `SHOWDOWN_OPP_MEGA_TRACE_OUT`
precedent). It must never be confused with a behaviour knob.

**Join identity.** Two run kinds, one schema, disjoint identity:

| field | live run | microprofile |
|---|---|---|
| `source` | `"live"` | `"microprofile"` |
| `battle_id` | the real battle id | `null` |
| `decision_index` | the client's shared request sequence — the **same** value trace-v3 and the opp-mega sidecar carry | `null` |
| `arm_id` | `null` | the §4 arm id, e.g. `"A9_dual_mega_tie"` |
| `rep` | `null` | 0-based repetition index within the arm |

**Live rows join to trace-v3 and the opp-mega sidecar on `(battle_id, decision_index)`** —
the identity I7b-C already established and proved (every sidecar key resolves to exactly one
trace row, gaps only at team preview). **Microprofile rows never join to a battle**; they are
keyed by `(arm_id, rep)`. A consumer must reject a row whose `source` and identity disagree.

**Counters — where they must live.** Transport is counted at the **backend**, not at the
oracle. `DamageOracle.batch_calls` counts **damage batches only**; `stats_batch` and
`types_batch` reach the shared backend directly from **three** on-path call sites that never
touch the oracle (`engine/speed.py:120`, `engine/speed.py:149`, `battle/opponent.py:49`). Under
`oneshot` each of those is its own Node process. Counting only `batch_calls` would hide exactly
the calls a first Mega context makes. (`engine/belief/hypotheses.py:207` is a fourth bypass but
is **run-setup cost on its own backend instance**, not per-decision transport — §0.4.)

Neither backend counts transport today: `spawn_count` (`client.py:171`, `:199`) exists on
`PersistentCalcBackend` only, and `SubprocessCalcBackend` has **no counter at all** although it
spawns per batch (F-8). The plan must therefore add, on **both** backends, one counter per
transport method, a **physical attempt** counter, and a spawn counter — **P-9**:

| counter | increments in | note |
|---|---|---|
| `damage_batch_calls` | `calc_batch`, **only on a non-empty request list** | **logical** operation |
| `stats_batch_calls` | `stats_batch`, **only on a non-empty spec list** | **logical** operation |
| `types_batch_calls` | `types_batch`, **only on a non-empty species list** | **logical** operation |
| `transport_attempts` | `PersistentCalcBackend`: every `_run_once`; `SubprocessCalcBackend`: every `subprocess.run` | **physical** attempts |
| `spawn_calls` | `SubprocessCalcBackend`: every `subprocess.run`; `PersistentCalcBackend`: every `_spawn` | process starts; the existing `spawn_count` is the persistent half already |

All three public methods already early-return on an empty list without touching transport
(`client.py:54-55`, `:114-115`, `:124-125` for `SubprocessCalcBackend`; `:278-279`, `:287-288`,
`:297-298` for `PersistentCalcBackend`), so "non-empty only" matches what the code already does
— it is stated here so the counter can never be placed above that guard.

**Logical calls ≠ physical attempts.** `PersistentCalcBackend._run`
(`client.py:238-249`) runs `_run_once`, and on `_TransportError` does `_spawn()` and
**`_run_once` again** (`:242-245`). One logical `calc_batch` can therefore be **two** physical
attempts, both paying latency. Rev. 3's `transport_calls` would have reported `1` for that —
and a retried row, where this happens by definition, would have been the worst-attributed of
all. `transport_attempts` is the physical count; the `*_batch_calls` are logical; neither
substitutes for the other.

**Planned vs implicit — measured at origin, never by subtraction (Rev. 3 correction).**
Rev. 2 defined `implicit_flushes = batch_calls_delta − planned_flushes`. **That is invalid.**
`flush()` early-returns on an empty pending map (`oracle.py:42-43`) **before** incrementing
`batch_calls` (`:50`), so an explicit flush over an empty map yields
`batch_calls_delta = 0, planned_flushes = 1 → implicit = −1`. This is not a corner case: the
oracle cache is per battle and never evicted (§1.5), so a later decision — or an extra world —
can be fully cache-resident and flush nothing. Rev. 2's validator would have enforced a broken
invariant.

The split must be attributed at the **actual non-empty batch**, by its origin:

```
damage_batch_calls == planned_damage_batches + implicit_damage_batches
```

- `planned_damage_batches` — non-empty batches originating from the explicit
  `mega_scoring.py:626` flush.
- `implicit_damage_batches` — non-empty batches originating from `oracle.get`'s auto-flush
  (`oracle.py:56-57`), i.e. **prefetch misses**.

Both are counted where the batch actually happens; neither is derived by subtracting call
counts. Distinguishing the two origins is the one genuinely new piece of oracle
instrumentation this design needs — **P-7**.

**Field set (exact, closed).** Counters are **per-decision deltas**, taken as
after-minus-before around the measured call — never cumulative:

| field | type | meaning |
|---|---|---|
| `schema_version` | str | `"decision-profile-v1"` |
| `source` | str | `"live"` \| `"microprofile"` |
| `battle_id` | str \| null | see join identity |
| `decision_index` | int \| null | see join identity |
| `arm_id` | str \| null | see join identity |
| `rep` | int \| null | see join identity |
| `config_id`, `format_id`, `git_sha` | str | provenance, same values as the sibling sidecars |
| `config_hash` | str | the run's effective config hash |
| `schedule_hash` | str \| null | the schedule's hash for `source="live"`; **`null` for `source="microprofile"`**, which has no schedule (Rev. 4 correction) |
| `profile_manifest_hash` | str \| null | **required for `source="microprofile"`, `null` for `live`** — canonical hash of the profile manifest (§2.7) that pins arm config, fixture bytes, reps and warmup |
| `calc_backend` | str | `"oneshot"` \| `"persistent"` — resolved value, not the raw env |
| `backend_class` | str | `"oneshot"` \| `"clean_cold"` \| `"clean_warm"` \| `"contaminated"` — a **predicate** over the three raw facts below, with `contaminated` as the residual, so it is exhaustive by construction (§5.5) |
| `cache_class` | str \| null | `"cold"` (the semantic caches were built fresh for this row) \| `"warm"` (reused). **`null` for `source="live"`** — the contract is defined against an arm's declared `lifecycle`, which a live row does not have (§2.8). **Orthogonal to `backend_class`** — the Node process and the `DamageOracle`/`SpeedOracle`/`SpeciesDex` caches are different things. Recomputed by the validator from the manifest lifecycle, and falsifiable by the three sizes below |
| `damage_cache_size_at_rep_start` | int \| null | `len(DamageOracle._cache)` sampled **at rep start** — before context construction, before the timer (§2.8). **`null` for `source="live"`** |
| `speed_cache_size_at_rep_start` | int \| null | `len(SpeedOracle._spe_cache)`, same point. **`null` for `source="live"`** |
| `dex_cache_size_at_rep_start` | int \| null | `len(SpeciesDex._cache)`, same point. **`null` for `source="live"`** |
| `spawn_count_before` | int | the backend's cumulative spawn count **before** this decision. Required: `backend_class` is a predicate over it and cannot be recovered after the fact (§5.5) |
| `transport_retried` | bool | `transport_attempts > transport_calls` — **a statement about failed attempts, never about spawns** (§5.5) |
| `timer_scope` | str | `"agent_choose"` \| `"contexts_and_score"` \| `"score_evaluated_variants"` — **which boundary `measured_ms` used** (§2.5). Rows with different scopes are never pooled |
| `measured_ms` | float \| null | the duration of `timer_scope`. **`null` when `outcome != "ok"`** (§2.6) |
| `damage_batch_calls` | int | non-empty damage batches this decision |
| `planned_damage_batches` | int | of which: from the explicit flush |
| `implicit_damage_batches` | int | of which: from `oracle.get` auto-flush = **prefetch misses** |
| `stats_batch_calls` | int | `SpeedOracle` → `backend.stats_batch` |
| `types_batch_calls` | int | `SpeciesDex.types` → `backend.types_batch` (`battle/opponent.py:49`). **Not** `hypotheses.py:207`, which runs at run setup on its own backend instance (§0.4) |
| `transport_calls` | int | `damage_batch_calls + stats_batch_calls + types_batch_calls` = **logical** backend operations this decision. **Not** a physical round-trip count |
| `transport_attempts` | int | actual `_run_once` / `subprocess.run` executions = **physical** round trips. `>= transport_calls`; exceeds it exactly when a persistent retry fired |
| `spawn_calls` | int | Node processes started this decision. Under `oneshot` this equals `transport_attempts` by construction; under `persistent` it is 0 (unstarted/warm), 1 (cold) or ≥1 (restart) |
| `requests_total` | int | raw `DamageRequest`s handed to `request()` |
| `requests_unique` | int | distinct keys that reached `_pending` (dedup survivors) |
| `cache_hits` | int | `request()` calls whose key was already in `_cache` |
| `n_candidates` | int | V |
| `n_responses` | int | Σ responses scored |
| `n_mega_twins` | int | responses with a non-null `foe_mega_slot` |
| `n_branches` | int | Σ projection branches composed |
| `n_worlds` | int | K |
| `depth2_frontier` | int | records × indices actually refined; `0` at depth 1 |
| `foe_mega_active` | bool | any non-null `foe_mega_slot` this decision |
| `outcome` | str | `"ok"` \| `"crash"` \| `"fallback"` \| `"degraded_state"` |

`requests_total`, `requests_unique`, `cache_hits`, the three `*_batch_calls`, `spawn_calls` and
the planned/implicit split **do not exist today** (§2.1, P-7, P-9). Only `batch_calls` and
`spawn_count` exist, and both are unread. The three `*_cache_size_at_rep_start` fields
(Rev. 10) do not exist as counters either, but need no new interface: each is `len()` over an
attribute that already exists and is already reachable from the harness
(`oracle.py:24`, `speed.py:103`, `opponent.py:45`).

**Emission point.** Live: after a successful dispatch, alongside the existing sidecars
(`gauntlet.py:712-732`'s position) — **never inside the timer**. Microprofile: after each
repetition. See §2.6 for exactly which decisions emit a row.

**Three enforcement tiers — binding (Rev. 10).** Rev. 9's defect was not a missing rule but a
missing *owner*: invariants were written in prose and bound to nothing, so "declared" quietly
meant "unenforced" (§9, entries 43-46). Every invariant in this spec belongs to exactly one tier,
and an invariant with no tier is **not enforced and may not be relied on**:

| tier | owner | runs | on violation | owns |
|---|---|---|---|---|
| **per-row** | `validate_decision_profile_row` | at **every** write, inside the writer | **raises** — the row is never emitted | everything in the validator list below |
| **dataset-level** | `validate_decision_profile_dataset(path, manifest)` | once, **after the profile run finishes and before any row is read as evidence**; the profile harness calls it and a report generator refuses to consume an unvalidated sidecar | **fails the run** — an arm is void, not annotated | `fixture_input_hash` ⇒ constant `n_candidates` (§2.7); `backend_class` distribution vs the declared `calc_backend` lifecycle (§2.8); contaminated/excluded-row counts (§5.5) |
| **cross-artifact** | — | never | — | `decision_latency_ms` agreement with trace-v3 (§2.5) — **offered, not enforced**, and named here so that stays explicit |

**The dataset tier is a function, not an aspiration (Rev. 11).** Rev. 10 named the tier and gave
it invariants but no owner, no trigger and no consequence — a tier with no enforcement, which is
the very defect the tiers were introduced to fix (§9, entry 52). It is
`validate_decision_profile_dataset(path, manifest)`: it runs once when the run completes, it
**fails the run** rather than annotating it, and any consumer that reads rows as evidence without
it is wrong by construction. This design does **not** propose its implementation — §6 holds the
boundary — it fixes what the contract must say.

Nothing else may be added to the cross-artifact tier: it is enforced by nobody by design, so a
new entry there would silently mean "unenforced" again.

**Validator (per-row).** `validate_decision_profile_row` — exact-closed field set (unknown ⇒
raise), plus:

- `damage_batch_calls == planned_damage_batches + implicit_damage_batches`
- `transport_calls == damage_batch_calls + stats_batch_calls + types_batch_calls`
- `transport_attempts >= transport_calls` (a retry adds attempts, never calls)
- all counters `>= 0` (a negative counter is a contract violation, not a datum)
- `requests_unique <= requests_total`
- `n_mega_twins > 0` ⇒ `foe_mega_active`
- `outcome == "ok"` ⇔ `measured_ms is not None` (§2.6)
- `transport_retried == (transport_attempts > transport_calls)` — **the only definition**; it
  never references `spawn_calls` (§5.5)
- `calc_backend == "oneshot"` ⇒ `backend_class == "oneshot"` and `spawn_calls == transport_attempts`
- `backend_class` equals the §5.5 predicate evaluated on this row's own
  (`spawn_count_before`, `spawn_calls`, `transport_retried`) — the validator **recomputes** it
  rather than trusting the writer, so a mislabelled row fails rather than skewing a contrast
- **`source == "live"` ⇒ `cache_class`, `damage_cache_size_at_rep_start`,
  `speed_cache_size_at_rep_start` and `dex_cache_size_at_rep_start` are all `null`.** The cache
  contract is a **microprofile** concept: it is defined against an arm's declared `lifecycle`,
  and a live row has no arm, no `rep` and no manifest (see the identity rule below). Rev. 10 wrote
  the three rules below unqualified, so they applied to live rows too and **no live row could
  satisfy them** — there is no `arm` to resolve `expected_cache_class` against, and the sizes are
  null, so any live `cache_class` value failed (§9, entry 49)
- the three rules below are **all** gated on `source == "microprofile"`:
- `cache_class == expected_cache_class(arm, rep)` — recomputed from the **manifest's resolved
  lifecycle**, `arm.warmup` and this row's **0-based** `rep` (§2.8); the validator never trusts
  the writer's label
- `cache_class == "cold"` ⇒ `damage_cache_size_at_rep_start == 0` **and**
  `speed_cache_size_at_rep_start == 0` **and** `dex_cache_size_at_rep_start == 0` — the sound
  direction only: a fresh cache is provably empty (`oracle.py:24`, `speed.py:103`,
  `opponent.py:45`), so a non-empty one disproves the declared lifecycle (§2.8)
- `cache_class == "warm"` ⇒ `rep >= 1 or arm.warmup >= 1` (**`rep` is 0-based** — §2.4)
- `source == "live"` ⇔ `timer_scope == "agent_choose"`; `source == "microprofile"` ⇔
  `timer_scope in {"contexts_and_score", "score_evaluated_variants"}` — §2.5's table is a
  **contract**, not documentation: a live row at a microprofile scope (or the reverse) is a
  category error, and pooling it would compare an end-to-end ms with a sub-call ms
- `source == "microprofile"` ⇒ `config_hash` equals the `effective_config_hash` of this row's
  `arm_id` in the manifest identified by `profile_manifest_hash` (§2.7)
- identity/`source` consistency: `live` ⇒ `battle_id`/`decision_index` set, `schedule_hash` set,
  `arm_id`/`rep`/`profile_manifest_hash` null; `microprofile` ⇒ `arm_id`/`rep`/
  `profile_manifest_hash` set, `battle_id`/`decision_index`/`schedule_hash` null

**Bytes.** LF-only: `open(..., "a", encoding="utf-8", newline="")` plus
`json.dumps(sort_keys=True, separators=(",", ":"))` — the `eval/opp_mega_trace.py` contract, and
the `data/eval/champions-panel-v0/** -text` rule already covers the output path. Tests assert on
**raw bytes**; a text-mode read hides CRLF on the platform that produces it.

**Error semantics.** Best-effort: a failing write is logged at debug and **never** propagates
out of `handle_request` or stalls a battle — the `agg_trace`/`opp_mega_trace` precedent. A
failed write increments no counter, so a rows-written counter reflects only successful writes.

### 2.7 Profile manifest — the microprofile's provenance anchor

**Rev. 4 correction.** Rev. 3 required `schedule_hash` on every row and offered `arm_id` as the
microprofile's identity. Neither works: a microprofile runs no schedule, and `arm_id` is a
label — it binds no fixture bytes, no repetition count, no warmup rule, no arm parameters and
no environment. Two microprofile runs could carry identical `arm_id`s and be incomparable.
Without an anchor, the causal comparisons this design rests on (§3.C) are not reproducible.

A microprofile run therefore emits **one manifest**, and every row of that run carries its
canonical hash in `profile_manifest_hash`. `schedule_hash` is `null` for those rows.

**One `config_hash` cannot describe an arm matrix (Rev. 5 correction).** Rev. 4 put a single
`config_hash` and a single `behavior_env` at the manifest's top level. That is impossible by
construction: the arms vary `SHOWDOWN_OPP_MEGA_CLICK_RATE` and `SHOWDOWN_SEARCH_DEPTH`, and both
are **BEHAVIOR_AFFECTING** (`eval/config_env.py:85` and `:40`; `SHOWDOWN_WORLD_SAMPLES` at `:35`
likewise). Arms that differ in those knobs have **different effective config hashes** — that is
the entire point of `config_hash`. A single top-level value would either be wrong for every arm
but one, or silently pretend the arms share a configuration they do not.

*(`SHOWDOWN_SEARCH_TOPM` and `SHOWDOWN_SEARCH_TOPN` are `EXCLUDED_BY_REASON`
(`eval/config_env.py:146-149`) — they cannot affect output at depth 1, so they do **not** move
`config_hash`. Arm 12 varies TOPM without changing the hash; that is expected, and the arm entry
records TOPM explicitly so the difference is not invisible. `SHOWDOWN_CALC_BACKEND` is
NON_BEHAVIORAL (F-7) and likewise does not move it — which is exactly what makes cold/warm arms
comparable.)*

**Manifest content (exact).** Top level carries only what is genuinely invariant across the run;
everything an arm can change lives in the arm entry:

| field | scope | meaning |
|---|---|---|
| `schema_version` | run | `"profile-manifest-v1"` |
| `git_sha`, `dirty` | run | the code the arms ran against |
| `calc_pin_hash` | run | the pinned calc bundle (`engine/calc/pin.py`) |
| `format_id`, `format_config_hash` | run | the format all arms share |
| `speciesdata_hash`, `itemdata_hash`, `movedata_hash` | run | generated-data provenance (re-serialised hashes, platform-stable — §0.3 of the I7b-C precedent) |
| `arms[]` | — | one entry per arm, below. **A LIST, and `arm_id` is a field of the entry** — not a mapping keyed by `arm_id`. The distinction is load-bearing: a mapping cannot *represent* a duplicate `arm_id`, so the duplicate would vanish at construction and the frozen manifest could never be re-checked for it. Frozen evidence must not have to trust the writer that produced it |

**There is deliberately no run-level `warmup` (Erratum 1).** It is a **per-arm** field, declared in
the arm entry below. Rev. 5's manifest did pin a single run-level warmup count (§9 entry 24), and
Rev. 6 moved the lifecycle per-arm and wrote "**Warmup** is declared per arm" in §2.8 — but this
table was never updated, so the design carried both readings at once. §2.8, §2.4's validator list
(`arm.warmup`) and §5.4's `expected_cache_class` (`arm.warmup == 0`) are the four places that
agree; this row was the one that did not.

Per-arm is also the only coherent reading: §2.8 states that a **cold-cache** arm which "warms up"
is *a contradiction, because its caches are discarded anyway*. A run-level warmup would force every
cold-cache arm to declare one it cannot use. **A manifest that carries a top-level `warmup` is
rejected** — two truths about the same quantity is exactly the drift this erratum removes.

**Arm entry (exact):**

| field | meaning |
|---|---|
| `arm_id` | the §4 arm id, e.g. `"A9_dual_mega_tie"` |
| `effective_config_hash` | `make_config_hash(effective_config_manifest(agent, format_id, env=<this arm's behavior_env>))` — **this arm's** hash, computed the same way a live run computes its own |
| `behavior_env` | this arm's **full effective** `behavior_env()` mapping, verbatim — not a diff |
| `arm_params` | the env knobs that define the arm, including those outside `behavior_env`: `SHOWDOWN_SEARCH_TOPM`, `SHOWDOWN_SEARCH_TOPN`, `SHOWDOWN_CALC_BACKEND` |
| `scoring_params` | the **call-bound** semantic arguments — group B below. An arm is precisely a choice of these plus `arm_params` |
| `fixture_input_hash` | group A below |
| `reps` | timed repetitions |
| `warmup` | **per arm** (Erratum 1): how many **untimed** repetitions precede this arm's timed ones. Arms may differ. **Required**, and it must cohere with `lifecycle`: an arm whose caches are `per_rep` must declare `warmup == 0`, because a cold-cache arm that warms up is a contradiction (§2.8) |
| `lifecycle` | which objects are rebuilt per repetition — see §2.8. **Required**; there is no default |
| `timer_scope` | the microprofile scope this arm is measured at (§2.5): `"score_evaluated_variants"` (narrow, every branch-cost arm) or `"contexts_and_score"` (wide, the persistent-backend spawn arms 13b/14). **Required** (C3). Pinned here so it is not a second, unpinned truth the harness carries: the row validator checks every row's `timer_scope` against this field, and `run_arm` reads it from the arm rather than accepting it as an argument |

**`fixture_input_hash` — exact DTO over every direct scoring input (Rev. 6 correction).**
Rev. 4 hashed "the constructed board". Rev. 5 replaced that with "all ten inputs, canonically
serialised" — which was **neither complete nor well-defined**, the same charge Rev. 5 laid
against Rev. 4:

- **Incomplete.** `score_evaluated_variants` (`battle/mega_scoring.py:334-361`) takes ~19 direct
  arguments. Rev. 5 listed ten and silently dropped `priors`, `risk_lambda`, `rollout_horizon`,
  `accuracy_mode`, `accuracy_branch_cap`, `endgame`, `fast_board` and `foe_mega_eligibility` —
  every one of which changes the score, and several of which change the cost.
- **Not well-defined.** "canonical_json" over a `BattleState` is not a specification.
  `PokemonState.moves` and `.move_names` are `set[str]` (`engine/state.py:66-67`), which
  `json.dumps` **cannot serialise at all** (`TypeError`), and any `str()` fallback is
  iteration-order dependent. A hash whose serialiser is unspecified is not a hash.

The inputs split cleanly by **where they are bound**, and the split is not cosmetic — the
fixture is shared across arms while the call-time knobs are what *define* an arm:

**A. Fixture-bound** → `fixture_input_hash`. These come from `_build_mega_decision_kw`
(`tests/conftest.py:178-218`) and are identical across every arm sharing that fixture:

| input | serialisation |
|---|---|
| `state` | the DTO below |
| `request` | `encode(BattleRequest)` — the **model**, via the pinned `model_dump` below. **Not** the raw payload dict: it is unreachable, and the model is the more correct input anyway (see below) |
| `legal_actions` | `[joint_action_key_v2(ja) for ja in enumerate_my_actions(req)]`, **in enumeration order — never sorted** (see below). This is what V scales with |
| `book` | `SpreadBook` → `{"default": <SpeciesSpreads>, "species": {<key-sorted>: <SpeciesSpreads>}}` |
| `our_spreads` | `{species: <SpeciesSpreads DTO>}`, keys sorted |
| `opp_sets` | same shape, or `null` |
| `calc_profile` | `CalcProfile` → `{"generation": int, "max_spe_investment": int}` |
| `species_meta` | **referenced by `speciesdata_hash`**, not re-hashed (it is generated data with an embedded, platform-stable hash) |
| `our_side`, `opp_side` | `"p1"` / `"p2"` |

**B. Call-bound** → `scoring_params` in the **arm entry**, because an arm is precisely a choice
of these:

`weights` (all `EvalWeights` fields), `mode`, `risk_lambda`, `rollout_horizon`,
`accuracy_mode`, `accuracy_branch_cap`, `endgame`, `fast_board`, `priors`,
`foe_mega_eligibility` (as the resolved `{slot: form_species_id}` map, or `null`).

**The spread DTO — nested, and order-preserving (Rev. 8 correction).** Rev. 6 dropped
`SpreadPreset.items`; Rev. 7 added it, **sorted it**, and typed the leaf wrongly. All three are
fixed here. The real shapes (`engine/belief/hypotheses.py:20-33`):

```python
@dataclass(frozen=True)
class SpreadPreset:
    nature: str
    evs: dict[str, int]
    items: list[str] = field(default_factory=list)   # ← Rev. 6 dropped; Rev. 7 sorted

@dataclass(frozen=True)
class SpeciesSpreads:
    offense: SpreadPreset          # ← Rev. 7 collapsed these two
    defense: SpreadPreset
    def preset(self, mode): return self.offense if mode == OFFENSE else self.defense
```

**`our_spreads`, `opp_sets` and `SpreadBook` hold `SpeciesSpreads`, not `SpreadPreset`.**
Verified in the fixture itself (`tests/conftest.py:198-205`):
`spreads = SpeciesSpreads(offense=SpreadPreset("Jolly", …), defense=SpreadPreset("Impish", …))`,
then `book = SpreadBook(default=spreads)` and `our_spreads = {"aerodactyl": spreads, …}`.

**Both branches are load-bearing, on different paths:**

| branch | who reads it | consequence |
|---|---|---|
| `offense` | `speed_for_species` → `_base_speed(species, preset.offense.nature, preset.offense.evs)` (`engine/speed.py:176`) | the projected **Mega speed** — hence tie-vs-unequal, hence 2 branches @ 0.5 vs 1 @ 1.0 |
| `defense` | `apply_own_team_knowledge` (`team/spreads.py:55`) → `items = spreads.defense.items` (`:89`) → `mon.item, mon.item_known = items[0], True` (`:91`) | **our own item truth**, incl. whether we hold Choice Scarf |
| `defense` (opp) | `_opponent_speed` binds `preset = preset_spreads.defense` (`battle/opponent.py:252`) and passes `preset.items` to `_item_for_speed` (`:254`), which returns `curated_items[0]` when the item is unknown (`:234`) | the **opponent's assumed Scarf speed** |

A DTO that collapses the two branches maps a fixture with fast-offense/bulky-defense onto one
with the branches swapped. They score differently and cost differently.

**`items` is an ordered preference, not a set (Rev. 8 correction).** Rev. 7 wrote *"`items` is
sorted because it is a set-like membership list, not an ordered preference."* **The config says
the opposite, in words**, at `showdown_bot/config/formats/meta/default_spreads.yaml:12`:

> `# items: candidate held items (first is the default assumption).`

And production takes exactly that first element, on two independent paths:

- `hypotheses.py:109` — `item = preset.items[0] if preset.items else None` (the opponent's
  assumed item when unknown)
- `spreads.py:91` — `mon.item, mon.item_known = items[0], True` (our own item when unknown)

The real config data makes the damage concrete — `default_spreads.yaml:18` is
`items: [Life Orb, Choice Specs, Focus Sash]`. Sorted, that becomes
`[Choice Specs, Focus Sash, Life Orb]` and the assumed item silently changes from **Life Orb to
Choice Specs** — a different item, different damage, and for any Scarf-bearing list a different
speed and therefore a different branch count. Two presets with identical membership but
different defaults would have shared a `fixture_input_hash` while producing different scores and
different costs. Rev. 7 asserted the semantics of this field without reading the config that
defines it; the config was one line long and explicit.

```
SpreadPreset   → {"evs": {<key-sorted>}, "items": [<enumeration order preserved>], "nature": str}
SpeciesSpreads → {"defense": <SpreadPreset>, "offense": <SpreadPreset>}
```

**`legal_actions` is an ordered priority, not a set (Rev. 8 correction).** Rev. 7 sorted it.
Enumeration order **is** the tie-break, and `battle/mega_scoring.py:184-198` says so, naming the
review that caught it before:

> "Callers computing ranking/tie-break/trace/max_damage order MUST iterate this list, never
> reconstruct an order … breaks first-wins tie-break semantics (Codex I7a-B merge-blocker: a tie
> between `A+Mega` and `B` must resolve to `A+Mega` because it is enumerated immediately after
> `A`, before `B`, in the true expand order)."

Two enumerations with the same membership and different order resolve ties to **different
chosen actions**. Sorting them into one hash is the same defect as sorting `items`.

**The rule that generalises both — and the one this spec now applies everywhere:**

| source type | serialisation | why |
|---|---|---|
| `set` / `frozenset` | **sorted** list | it has no order; sorting is the only deterministic option |
| `list` / `tuple` | **order preserved** | order is either meaningful (`items`, `legal_actions`, `types`) or at minimum not ours to discard |
| `dict` | **key-sorted**, values recursed | every dict here is a keyed lookup (`sides`, `evs`, `boosts`, `tailwind`, `species`); key order carries nothing |
| dataclass | fields **name-sorted**, values recursed | stable under field reordering |

`moves` and `move_names` are sorted **because they are genuinely `set[str]`**
(`engine/state.py:66-67`) — not because sorting is canonical. `PokemonState.types: list[str]`
is a list and keeps its order.

**Operationalising the fail-closed rule (Rev. 8, P2).** Rev. 7 said "a field this spec does not
name must raise" but named expected field sets for nothing — an unenforceable rule. Of the two
ways out, **"all fields, recursively" is adopted**, because the alternative asks this spec to
hand-list the fields of `BattleState`, `PokemonState`, `FieldState`, `SpeciesSpreads`,
`SpreadBook` and `CalcProfile` — and hand-listing is precisely what produced §9 entries 27-31
and 33-35. The serialiser therefore takes **every** field from `dataclasses.fields()` and
recurses, with no field list anywhere:

```
encode(x):
  pydantic BaseModel → encode(x.model_dump(mode="python", by_alias=True,
                                           exclude_unset=False, exclude_defaults=False,
                                           exclude_none=False))     # see `request` above
  dataclass          → {f.name: encode(getattr(x, f.name)) for f in fields(x)}, name-sorted
  dict               → {k: encode(v)}, key-sorted
  set | frozenset    → sorted(encode(e) for e in x)
  list | tuple       → [encode(e) for e in x]          # order preserved
  str | int | bool   → verbatim      (bool before int: bool is a subclass of int)
  None               → null                            # never elided
  float              → repr(x)                         # full precision, never rounded
  anything else      → raise TypeError                 # fail-closed
```

The `BaseModel` branch is **not optional** (Rev. 9): `BattleRequest` is a pydantic model
(pydantic 2.13.4), not a dataclass, so Rev. 8's encoder — which had no such branch — would have
hit `anything else → raise TypeError` on the very input it claimed to serialise. It would have
failed closed rather than produced a wrong hash, but the spec asserted a path that could not run.
`model_dump` recurses into the nested models (`ActiveSlot`, `MoveSlot`, `SideInfo`,
`PokemonSlot`) itself, so one branch covers the whole tree.

The fail-closed branch now fires on an unhandled **type**, not a forgotten field name — and the
type closure is **closed and verified on both halves of the input**:

- **The dataclass half.** Enumerating `dataclasses.fields()` over `BattleState`, `PokemonState`,
  `FieldState`, `SpreadPreset`, `SpeciesSpreads`, `SpreadBook` and `CalcProfile` yields only
  `str`, `int`, `bool`, `str | None`, `int | None`, `set[str]`, `list[str]`, `dict[str, …]` and
  nested dataclasses. Nothing else appears.
- **The pydantic half (Rev. 9).** `model_dump` over the real `_mega_req()` yields a tree of only
  dicts, lists, `str`, `int`, `bool` and `None` — no exotic leaf reaches `encode`.

A field added to any of them is picked up automatically; a field of a *new* type raises rather
than being silently skipped.

Over-discrimination is the deliberate trade: including a field that turns out not to matter
splits one hash into two, which costs a comparison. Excluding one that does matter merges two
fixtures into one hash, which corrupts every claim built on it. The hash is a **fixture
identity**, not a semantic equivalence class, so it errs toward splitting.

**`request`: the model, not the payload (Rev. 9 correction).** Rev. 8 specified "the raw
request payload dict, as parsed". **No such object is reachable.** `_mega_req()`
(`tests/conftest.py:112-157`) builds a dict *literal* inline and passes it directly into
`BattleRequest.model_validate({...})` at `:126`; the dict is never bound to a name and never
returned, and `_build_mega_decision_kw` receives only the model. A manifest producer cannot
reproduce the input Rev. 8 demanded.

Of the two ways out — pin an exact `model_dump`, or change the fixture builder to also return the
payload and record that as a missing interface — **the `model_dump` is adopted, and not as a
fallback: it is the more correct input.**

- `score_evaluated_variants` receives the **model**. The payload is upstream trivia that no
  scoring code ever sees.
- `BattleRequest.model_config` does not set `extra`, so pydantic's default `ignore` applies —
  **verified empirically**: a payload carrying `bogusExtraKey` validates to a model whose dump
  does not contain it. Keys the model drops therefore *cannot* affect behaviour or cost.
- So two payloads validating to the same model are behaviourally identical and **should** share a
  fixture hash. Hashing the payload would split them — over-discriminating on provably irrelevant
  keys. Hashing the model is exact.

No missing interface is needed, and none is claimed.

**The dump is pinned, because its options change the bytes:**

```
request → encode(req.model_dump(
              mode="python",        # nested models → plain dicts; leaves stay python scalars
              by_alias=True,        # "forceSwitch", not "force_switch"
              exclude_unset=False,  # a field left unset still takes its default and still acts
              exclude_defaults=False,
              exclude_none=False,   # null is a state, never elided
          ))
```

`by_alias` is pinned because it **demonstrably** changes the keys (`forceSwitch` /
`teamPreview` / `maxTeamSize` vs `force_switch` / `team_preview` / `max_team_size`); the three
`exclude_*` flags are pinned to `False` for the same reason `None` is never elided — an omitted
field is not an absent input, it is a defaulted one. Verified on the real fixture:
`model_dump(mode="python", by_alias=True)` over `_mega_req()` yields a tree of **only** dicts,
lists, `str`, `int`, `bool` and `None` — no exotic leaf — and two independent builds dump
byte-identically.

`species_meta` is referenced by its existing `speciesdata_hash` rather than re-encoded (generated
data with an embedded, platform-stable hash).

**Serialiser:** `json.dumps(encode(dto), separators=(",", ":"), ensure_ascii=False)` — `encode`
has already fixed all ordering, so `sort_keys` is **not** used: it would re-sort nothing and
must not be relied on to.

**Hash:** `sha1(<that string>)[:16]`, the `make_config_hash` convention
(`eval/result_jsonl.py:69`).

`contexts` and `evaluated_variants` are **derived** from A by `build_own_mega_contexts` and are
deliberately **not** hashed — hashing a derived object pins an implementation detail rather than
an input. Their sizes (C, V) land on every row (`n_candidates`) as the cross-check: identical
`fixture_input_hash` with differing `n_candidates` is a contract violation, not a datum.

**Rev. 10 — this one has an owner, because a per-row validator cannot see it.** It compares two
rows, so `validate_decision_profile_row` structurally cannot enforce it; Rev. 9 declared it and
assigned it to nobody. It belongs to the **dataset-level** check (§2.4's tiers): over all
`source="microprofile"` rows sharing a `profile_manifest_hash`, group by `fixture_input_hash` and
require `n_candidates` to be constant within each group. A violation means the hash bound fewer
inputs than the scoring path actually consumed — the exact failure entries 20, 25, 30, 33-35 and
39 were each an instance of — so it fails the run rather than annotating it.

**Hash:** `sha1(json.dumps(encode(manifest), separators=(",", ":"), ensure_ascii=False))[:16]`,
the `make_config_hash` convention (`eval/result_jsonl.py:69`) — **the same `encode` as §2.7's
fixture hash**. Rev. 8 note: this said `canonical_json(manifest)`, which is exactly the
unspecified serialiser F-15 charges against. The manifest is plain scalars and strings, so the
weakness was latent rather than live, but a spec that names an undefined serialiser one page
after calling that a defect is not one this design should ship.

**Binding:**

- A microprofile row without a resolvable `profile_manifest_hash` is not evidence.
- **Every row's `config_hash` must equal the `effective_config_hash` of its own `arm_id`'s
  manifest entry** — enforced by the validator (§2.4). A row whose config hash does not match
  the arm it claims to belong to is describing a different configuration than it says.
- Two arms are **causally comparable** only when their entries differ in exactly the
  intended factor and share `fixture_input_hash` — that shared hash is what makes the contrast
  causal rather than coincidental (§3.C). A contrast across differing `fixture_input_hash`
  values is a different-board comparison and carries the same defect as the live arms (§3.1).

`scripts/run_cap_latency_sweep.py:119-124` is the closest existing precedent for the warmup rule
(3 untimed decisions before timed ones, `SHOWDOWN_CALC_BACKEND=persistent` forced) but it writes
no manifest — **P-10**.

### 2.8 Cache lifecycle — the microprofile's most dangerous free variable

**Rev. 6 correction.** Rev. 5's manifest pinned the warmup count and whether the backend is
re-created, but said nothing about the **caches**. That gap is not a detail — it can make the
measurement meaningless without any error surfacing:

- `DamageOracle._cache` is **never cleared and never evicted** (`oracle.py:24`; the only
  `.clear()` is `_pending.clear()` at `:53`) and lives for the oracle object's lifetime (§1.5).
- If an arm reuses one `DamageOracle` across repetitions, **the warmup repetitions populate the
  cache for every timed repetition that follows**. Reps 2..N would then issue near-zero damage
  batches — `damage_batch_calls ≈ 0` — and the profile would report that the foe-Mega path costs
  almost nothing. It would be measuring its own cache.
- `SpeedOracle._spe_cache` (`engine/speed.py:103`) and `SpeciesDex._cache`
  (`battle/opponent.py:45`) have exactly the same property.
- `contexts` / `evaluated_variants` embed per-context `DamageModel`s bound to a specific oracle
  (`mega_scoring.py:470-474`), so rebuilding them without rebuilding the oracle does **not**
  reset the cache.

**Binding: every arm entry carries an explicit `lifecycle`, and there is no default.** Each of
these objects is declared `"per_rep"` (constructed fresh for every repetition, warmup included)
or `"per_arm"` (constructed once, reused):

| object | what `per_arm` means |
|---|---|
| `calc_backend` | the backend **object** is reused — so `spawn_count_before >= 1` once some rep has used calc. **Not** `spawn_calls == 0`: `_ensure` legitimately revives a process that died between reps (`client.py:176-180`), which is why a respawn is handled by §5.5's `contaminated` residual rather than forbidden (Rev. 11) |
| `damage_oracle` | **the damage cache carries across reps** — every rep after the first measures a warm cache |
| `speed_oracle` | speed lookups resolve from `_spe_cache` after the first rep |
| `species_dex` | typing lookups resolve from `_cache` after the first rep |
| `contexts_and_variants` | `build_own_mega_contexts` runs once; its cost leaves the timed window |

**Constraint (Rev. 10): `damage_oracle`, `speed_oracle` and `species_dex` must share one
lifecycle.** A manifest declaring them differently is **invalid and rejected at load**. This
forbids nothing legitimate — both coherent configurations below already declare the three
identically — and it is what keeps `expected_cache_class` total without inventing a `mixed`
class the way Rev. 4-6 kept inventing backend states (§9, entry 27). `calc_backend` and
`contexts_and_variants` are **not** bound by this: they are independent properties, and the
warm-cache configuration deliberately pairs a `per_arm` backend with `per_rep` contexts.

**The two coherent configurations**, both legitimate, measuring different things — an arm must
say which it is:

| configuration | lifecycle | measures | must not claim |
|---|---|---|---|
| **cold-cache** | everything `per_rep` | the full cost of a decision that resolves nothing from cache — the closest analogue to a battle's *first* Mega decision | steady-state cost |
| **warm-cache** | `calc_backend`/`damage_oracle`/`speed_oracle`/`species_dex` `per_arm`, `contexts_and_variants` `per_rep` | the marginal cost of a decision whose calc results are already known — the analogue of a *later* decision in the same battle | first-decision cost |

**A cold cache does not imply a cold backend (Rev. 7 correction).** Rev. 6 asserted that "a
cold-cache arm reaches `persistent_cold` on every rep by construction". **That is false at the
microprofile's own timer**, and the reason is a call chain Rev. 6 never traced:

```
build_own_mega_contexts        (mega_scoring.py:210)
  → filter_projectable_variants (mega_variants.py:73)
    → project_mega              (mega_variants.py:119 → mega_projection.py:69)
      → speed_oracle.speed_for_species          (mega_projection.py:127)
        → SpeedOracle._base_speed               (speed.py:176 / :185)
          → backend.stats_batch                 (speed.py:120, on a _spe_cache miss)
            → _run → _run_once → _ensure → SPAWN
```

Context construction happens **before** `score_evaluated_variants` is entered, and a cold-cache
arm rebuilds the `SpeedOracle` every rep, so its `_spe_cache` **always** misses and it **always**
spawns. Once P-5 is fixed — i.e. fixtures share one backend across speed and damage, the way
production does (`gauntlet.py:469-472`) — that spawn is the *shared* backend's. So at
`timer_scope="score_evaluated_variants"` the process is **already alive when the timer starts**:
the row is `backend_class="clean_warm"`, on **every** rep, precisely for the arm Rev. 6 called
cold. Fixing P-5 does not bring the spawn into the timer; **it moves it out**.

The two facts are therefore **orthogonal properties, recorded independently**:

| property | what it describes | how it is established |
|---|---|---|
| `cache_class` | were the **semantic caches** (`DamageOracle._cache`, `SpeedOracle._spe_cache`, `SpeciesDex._cache`) built fresh for this row, or reused from an earlier rep? | **derived from the arm's declared `lifecycle`, and falsified by three observed cache sizes** (§2.8) — never asserted free-hand |
| `backend_class` | was the **Node process** alive when the timer started, and did it stay clean? | **observed**, per §5.5's predicate |

`cache_class="cold"` means *these objects were constructed for this repetition* — it does **not**
mean "zero entries at timer start". Pre-timer context construction legitimately populates
`_spe_cache` before `score_evaluated_variants` is entered. Claiming otherwise would be the same
error one level down.

**`cache_class` must be falsifiable, not declared (Rev. 10 correction).** Rev. 9 said
`cache_class` was "**declared** by the arm's `lifecycle` and cross-checked against observed batch
counts", and the validator bound it to **nothing**. Two defects:

1. **Batch counts cannot cross-check freshness — in either direction.** A *reused* oracle whose
   board needs all-new keys issues a full set of batches and looks cold; a *fresh* oracle on a
   board that needs no damage issues none and looks warm. `DamageOracle._cache` is keyed by
   semantic payload, so batch count measures key novelty, not object identity. The claim was
   hand-waving and is withdrawn.
2. **Nothing bound the row to the manifest.** A row could report `cache_class="cold"` while its
   arm declared `damage_oracle/speed_oracle/species_dex = "per_arm"` and pass every invariant —
   silently feeding a warm-cache measurement into the cold/warm contrast.

The fix is the one that made `backend_class` sound: **record raw observed facts and derive the
label, then let the facts contradict it.** A freshly constructed cache is *provably* empty —
`DamageOracle._cache = {}` (`battle/oracle.py:24`), `SpeedOracle._spe_cache = {}`
(`engine/speed.py:103`), `SpeciesDex._cache = {}` (`battle/opponent.py:45`) — so emptiness is a
sound necessary condition for freshness.

**Scope — binding: `cache_class` is a microprofile property, `null` for live rows (Rev. 11).**
It is defined against an arm's declared `lifecycle`, and a live row has no arm, no `rep` and no
manifest — so there is nothing to derive it from and nothing to falsify it against. Rev. 10 wrote
its rules unqualified and thereby made them unsatisfiable for every live row (§9, entry 49). Live
decisions *do* share oracles across a battle (`_decision_deps`, `gauntlet.py:433-480`), so a
live cold/warm question exists — but it is a different question, against a different (per-battle,
undeclared) lifecycle, and this slice does not answer it. Saying so is the honest scope; leaving
the rules unqualified was not.

**Sampling point — binding: at rep start, before context construction and before the timer.**
Not at timer start: `build_own_mega_contexts` legitimately populates `_spe_cache` pre-timer
(§2.8), so a timer-start sample would call every cold-cache arm warm. At rep start a fresh object
has zero entries and a reused one carries whatever earlier reps left.

**Manifest constraint:** the three semantic caches **must share one lifecycle**. §2.8's two
coherent configurations already do (cold-cache: all `per_rep`; warm-cache: all `per_arm`), so
this forbids only incoherent arms — and it keeps `expected_cache_class` total without inventing a
`mixed` class:

```
cache_lifecycle := the shared lifecycle of damage_oracle/speed_oracle/species_dex
                   (a manifest declaring them differently is INVALID — rejected at load)

# rep is 0-BASED (§2.4) — rep == 0 is the first TIMED repetition.
expected_cache_class(arm, rep) :=
    "cold"   if cache_lifecycle == "per_rep"
    "cold"   if cache_lifecycle == "per_arm" and arm.warmup == 0 and rep == 0
    "warm"   otherwise                      # ← residual: total by construction
```

**`rep` is 0-based, and Rev. 10 read it as 1-based (Rev. 11 correction).** The field is defined
"0-based repetition index within the arm" (§2.4), so `rep == 0` is the first timed repetition.
Rev. 10 branched on `rep > 1` and `rep == 1`, which broke it twice over:

| arm | rep | truth | Rev. 10 said |
|---|---|---|---|
| `per_arm`, `warmup == 0` | **0** (first, genuinely cold) | cold | **no branch matched at all** |
| `per_arm`, `warmup == 0` | **1** (second, genuinely warm) | warm | **"cold"** — it fell into the `rep == 1` branch |

And Rev. 10 asserted "Total over its domain … splits exhaustively" in the same breath. It was not
total, by its own off-by-one. So the third branch is now a **residual (`otherwise`)** rather than
a third condition — total by construction, the §5.5 lesson applied one level down instead of
merely cited. A `per_arm` arm's first timed rep with no warmup is genuinely cold; that is now
written as `rep == 0`, once.

**What is asserted, and what deliberately is not:**

- `cache_class == "cold"` ⇒ **all three sizes are 0.** Sound: `__init__` sets each cache to `{}`,
  so a non-empty cache at rep start *proves* the object was not constructed for this rep — the
  harness contradicts its own manifest, and the row fails.
- `cache_class == "warm"` ⇒ `rep >= 1 or warmup >= 1`. A warm claim needs something to have
  run before it. (**`rep >= 1`, not `> 1`**: `rep` is 0-based, so the second repetition is
  `rep == 1` — Rev. 10's `> 1` silently exempted it.)
- **The converse is NOT asserted.** `"warm" ⇒ sizes > 0` is **unsound**: a reused `SpeciesDex` on
  a board whose species were never looked up is legitimately empty, and would fail a rule that
  demanded otherwise. Rev. 5 shipped exactly that mistake for `backend_state` — a validator that
  rejects a real, successful row (§9, entry 23). Only the provable direction is enforced.

**Consequence — stated rather than hidden: `clean_cold` is unreachable at
`timer_scope="score_evaluated_variants"`.** An arm that wants to measure spawn cost must use a
timer scope that contains the spawn: `"contexts_and_score"` (microprofile) or `"agent_choose"`
(live). This is what arm 13b actually requires, and §4's arm 13b entry is corrected accordingly.

**The backend cross-check is arm-level, and must not be a per-row rule (Rev. 11 correction).**
Rev. 10 turned it into one:

```
calc_backend_lifecycle == "per_arm" and (rep > 1 or arm.warmup >= 1)  ⇒  spawn_calls == 0
```

**That rule rejects a real, successful row.** Its own justification gave it away — *"a process
constructed once **and still alive** cannot spawn again"*. `per_arm` declares that the **backend
object** is reused, not that the OS process survives. `_ensure` (`client.py:176-180`) checks
`poll()` and revives a process that died *between* reps **before the first attempt**, with no
failure and no retry: `spawn_calls == 1`, `transport_retried == false`, result correct. Rev. 10's
rule fails that row.

This is **entry 23 verbatim** — Rev. 5's validator demanded `retried=true` for a respawn and
would have rejected a real row — and Rev. 10 repeated it one bullet *after* citing entry 23 as
the mistake it was avoiding (entry 44). Citing a lesson is not learning it.

**The rule is also redundant**, which is the tell that it was the wrong mechanism. §5.5 already
handles a respawn correctly and without rejecting anything: `clean_warm` requires
`spawn_calls == 0`, so a mid-run respawn falls to the `contaminated` residual and is **excluded
from the contrast and reported by count**. The machinery built to be exhaustive already covered
the case the new rule tried to police.

**Nor can a sound per-row replacement be written.** The obvious candidate —
`per_arm and rep >= 1 ⇒ spawn_count_before >= 1` — is *also* unsound: if rep 0 used no calc at
all, the process was never started and rep 1 legitimately reports `spawn_count_before == 0`.

So the check belongs where §2.8 originally put it, and where Rev. 10's own tier table says it
belongs: **"the arm's rows are void" is an arm-level verdict, not a row-level one.** It is a
**dataset-level** check (§2.4): for each arm, compare the observed `backend_class` distribution
against the declared `calc_backend` lifecycle — a `per_arm` arm whose rows are predominantly
`clean_cold`, or a `per_rep` arm reporting `clean_warm`, means the declaration and the run
disagree, and that **arm's** rows are void. Rev. 10 read an arm-level verdict as a row-level
rejection and got an unsound rule for it.

**Warmup** is declared per arm and is only meaningful for a **warm-cache** arm; a cold-cache arm
that "warms up" is a contradiction, because its caches are discarded anyway. Warmup repetitions
are untimed and emit **no** profile rows.

### 2.5 Timer scope — binding

`measured_ms` is **not** implicitly "the same quantity as trace-v3". The row carries
`timer_scope`, and only these three values are permitted:

| `timer_scope` | boundary | who uses it | contains the spawn? | may be compared to the 1000 ms budget? |
|---|---|---|---|---|
| `"agent_choose"` | exactly `gauntlet.py:625`→`652` — the identical boundary `decision_latency_ms` uses | **live rows only** | yes | **yes** |
| `"contexts_and_score"` | `build_own_mega_contexts` **and** the `score_evaluated_variants` call that consumes it | **microprofile rows only** | **yes** — this is the only microprofile scope in which `clean_cold` is reachable (§2.8) | **no** |
| `"score_evaluated_variants"` | the single call to `score_evaluated_variants`, excluding context construction and fixture setup | **microprofile rows only** | **no** — context construction has already spawned the shared backend (§2.8) | **no** |

**Why the third scope exists (Rev. 7).** Arm 13b measures the cost of a Node **spawn**. Rev. 6
placed every microprofile row at `score_evaluated_variants` scope, where the spawn has already
happened during context construction — so arm 13b was an arm the design **could not measure**,
and Rev. 6 did not notice because it asserted the opposite (§2.8). `"contexts_and_score"` gives
the spawn arm a boundary that contains its subject. It is **not** a new measurement of the
branch-cost arms: those stay at the narrower scope, where context construction is not
confounding them.

The narrower scope remains the default for every branch-cost arm precisely because it excludes
context construction; the wider one is for the backend arms, which need it included. Neither may
be compared to the budget, and **the two may never be pooled with each other** — the wider scope
is a strict superset of the narrower one by construction, so a mixed distribution would be
meaningless.

A live row with `timer_scope == "agent_choose"` and the same `(battle_id, decision_index)` must
carry the **same** value as trace-v3's `decision_latency_ms`, up to float formatting — that is a
cross-check the profile makes available, not a new measurement.

The microprofile deliberately does **not** measure `agent_choose`: its fixtures enter at
`score_evaluated_variants` / `_choose_best_mega`, and there is no state build, no send and no
`_Client` around them. Naming the scope explicitly is what stops a microprofile ms from being
read as an end-to-end ms. **A consumer must never pool rows with different `timer_scope`** —
including the two microprofile scopes with each other.

### 2.6 Crash semantics — binding, one variant chosen

Rev. 2 was self-contradictory: it required emission "only when the agent completed" *and* an
`outcome="crash"` row, while `decision_latency_ms` was a mandatory float and the active-p95 gate
filtered only on `foe_mega_active` — so a crash row could have entered the gate value.

**Variant 2 is adopted:**

1. A crashed / fallback / degraded decision **does** emit a row — its counters are real and its
   absence would silently bias any per-decision distribution.
2. `measured_ms` is **`null`** whenever `outcome != "ok"`. A crashed decision's wall clock is
   the crash handler (`gauntlet.py:637-648`), not decision work; recording it as a latency would
   be a false datum. The validator enforces `outcome == "ok"` ⇔ `measured_ms is not None`.
3. **Every latency gate and every latency statistic requires `outcome == "ok"` explicitly**, not
   merely `foe_mega_active`. §5.3 states this as part of the gate predicate.

Counters from a non-ok row remain usable (they describe transport that really happened) and are
reported separately; they are never pooled into a latency figure.

**Validity boundary — binding.** A microprofile row (`source="microprofile"`) may support
counter and ratio claims (§3). It **may not** be pooled with live rows, and its
`measured_ms` **may not** be compared to the 1000 ms budget: its fixture layer has a
backend topology production does not have (§3.A). Any consumer that pools the two `source`
values is wrong by construction.

---

## 3. Comparison of the three measurement approaches

### A. Deterministic decision replay / microprofile

Drive real `score_evaluated_variants` / `_choose_best_mega` over constructed states.

- **Can support:** cost *attribution* — round trips, planned/implicit flush split, requests,
  dedup, branch counts, and the **causal** marginal cost of one foe-Mega class or one extra
  branch, because V/R/B/K and the board are held fixed while exactly one factor varies.
- **Cannot support:** any absolute end-to-end claim. It excludes the state build
  (`gauntlet.py:551` — the growing room-log replay), the send, and the sidecar writes.
- **Verified blocker:** every existing mega fixture hard-codes
  `SpeedOracle(stats_backend=SubprocessCalcBackend(), ...)` (`tests/conftest.py:197`,
  `tests/i7b/conftest.py:19`, `tests/i7b/test_i7b_b_caller_gate.py:140`). Production instead
  passes the **shared** backend — `build_speed_oracle(self._decision_calc.backend, ...)`
  (`gauntlet.py:469-472` → `calc_profile.py:33-36`). So under
  `SHOWDOWN_CALC_BACKEND=persistent` a fixture-based microprofile runs **damage persistent
  while speed stays one-shot** — a topology that **does not exist in production**. Absolute ms
  from that hybrid is an artifact. *(`SpeedOracle.__init__` only defaults to
  `SubprocessCalcBackend` when `stats_backend is None`, `engine/speed.py:96-101`; production
  never hits that default. The defect is in the fixtures — plan input P-5.)*

### B. Paired live gauntlet profile

Identical schedule/seed arms, pre-pinned differing configs.

- **Can support:** real end-to-end `decision_latency_ms` under the production backend topology,
  with real state builds and real board evolution — the only thing that may be compared to the
  budget.
- **Cannot support:** attribution, and — decisively — **any causal foe-Mega ratio**. See §3.1.
- **Additional noise:** turn-1 candidate explosion dominates the tail (672/421 ms, r = 0.921);
  bot names carry per-run random suffixes; the battle's first decision absorbs the cold start
  (§1.2).

### 3.1 Live arms are NOT causally paired — binding

Same seed base + same schedule reproduce the same *battle setup*, not the same *decision
sequence*. The moment two arms make different choices, the boards diverge; every later
decision is a different board with a different candidate count. Given r = 0.921 between
candidate count and latency (§0.1), a live active-vs-inactive difference is **dominated by
board divergence, not by foe-Mega work**.

Worse, an *within-run* active-vs-inactive comparison is not paired at all: the active decisions
are a different set of turns than the inactive ones.

**Therefore:**

- **A live active/inactive latency ratio must never be reported as the marginal foe-Mega
  effect.** It is not one.
- The **causal** ratio comes **only** from the microprofile (A), which varies exactly one factor
  on a fixed board.
- If a live paired ratio is ever wanted, it requires pairing on **identical state snapshots** —
  the same `observable_state_hash` / `request_hash` evaluated under two configs — which is a
  microprofile-shaped design driven by recorded states, not a gauntlet arm. **No such
  interface exists today** (plan input P-8).

### C. Hybrid — RECOMMENDED, and the audit forces it rather than suggesting it

Microprofile (A) for the **cost model**, small live confirmatory run (B) for **absolute
end-to-end sanity**.

- **Only A can produce the number that matters.** §0.4 shows the cost is round trips, driven by
  prefetch misses — invisible in any live aggregate.
- **Only B can produce an absolute claim**, because A's fixture layer has a backend topology
  production does not have.
- **Neither may borrow the other's authority.**

**Allocation of claims — binding:**

| claim | licensed by | never by |
|---|---|---|
| round trips / planned vs implicit flushes / requests / dedup per arm | A | B |
| **causal** marginal cost of +1 foe-Mega class at the cap | A | B |
| **causal** marginal cost of tie (2 branches) vs unequal (1 branch) | A | B |
| cold vs warm delta, as a controlled contrast | A | B |
| absolute end-to-end p95 vs the 1000 ms budget | B | A |
| "the active foe-Mega path is/is not within budget" | **B, and only if the exposure floor is met** | A |
| any live active-vs-inactive ratio as a foe-Mega effect | **nobody** (§3.1) | — |

---

## 4. Profile arms

Reachability was audited against the base commit. **No helper is invented.** Arms not
constructible today are recorded as plan inputs, not papered over.

| # | Arm | Reachable today? | Evidence / what is missing |
|---|---|---|---|
| 1 | Champions, no foe-Mega hypothesis | **YES** | `mega_decision_fixture` (`tests/conftest.py:222-226`, p2.a Incineroar → eligibility `{}`); decision level `tests/i7b/test_i7b_b_caller_gate.py:249-270` |
| 2 | Gate active, click rate **0.0** (inertness control) | **YES** | `SHOWDOWN_OPP_MEGA_CLICK_RATE=0` + tie fixture, `tests/i7b/test_i7b_scoring.py:99-126`. Twins are emitted at weight 0 (`opponent.py:409-422`) but the `weight > 0` filter (`mega_scoring.py:516-519`) composes **zero branches**, so this arm's cost ≈ the no-mega path *by construction* — which is what makes it the inertness control. |
| 3 | Default rate **0.35** | **YES** | `opponent.py:205-217`; pinned `tests/i7b/test_i7b_responses.py:15-17` |
| 4 | Foe-Mega on opponent **slot 0** | **YES** | `mega_decision_tie_fixture` (`tests/conftest.py:229-245`); pinned `test_i7b_scoring.py:288` |
| 5 | Foe-Mega on opponent **slot 1** | **NO — MISSING INTERFACE** | No fixture places a Mega-capable mon in `p2.b`. `_mega_state()` (`tests/conftest.py:160-175`) takes only `foe_a` and never populates `p2.b`. Production supports it (`opponent.py:377`, `mega_scoring.py:529`); only `predict_responses`-level coverage exists via a hand-built eligibility dict (`test_i7b_responses.py:160-189`), bypassing `foe_mega_eligibility()`. **P-1.** |
| 6 | Own-Mega without foe-Mega | **YES** | `mega_decision_fixture`; `canMegaEvo` at `tests/conftest.py:128` |
| 7 | Foe-Mega without own-Mega | **Branch: YES. Board: NO** | The `own_mega_slot=None` context inside the tie fixture takes exactly this path (`mega_scoring.py:521-530` → single activation → 1 branch @ 1.0). A *board* where our side has no Mega option does not exist — every mega request fixture hard-codes `canMegaEvo: True` (`tests/conftest.py:128,145`). **P-2.** |
| 8 | Dual-Mega, **unequal** pre-Mega speed (1 branch @ 1.0) | **Projection layer: YES. Decision layer: NO** | `test_i7b_projection.py:133-148` (Aerodactyl 200 vs Meganium 100). At `score_evaluated_variants` level the only board with both a real foe hypothesis and a projectable own Mega is the **tie** fixture (200/200). **P-3 — and this is the configuration the one live active decision actually used (§0.2), so its absence at decision level is a real gap.** |
| 9 | Dual-Mega, **exact tie** (2 branches @ 0.5) | **YES** | `mega_decision_tie_fixture`; precondition asserted `test_i7b_scoring.py:45-53` (own == foe == 200, real backend) |
| 10 | Trick Room reversed activation order | **Projection layer: YES. Decision layer: NO** | `mega_activation_order_key` exists (`engine/speed.py:48-54`), tested `test_i7b_projection.py:17-26`, `:231-257` with a hand-built state. No TR fixture; a post-hoc `kw["state"]` swap is explicitly forbidden (`tests/conftest.py:179-182`) because contexts are pre-bound. **P-4.** |
| 11 | Depth-1 | **YES** | default (`decision.py:57-63`); pinned `test_i7b_scoring.py:590-610` |
| 12 | Depth-2 with the foe-Mega frontier **actually reached** | **YES, but only with `SHOWDOWN_SEARCH_TOPM ≥ 4`** | `test_i7b_scoring.py:396-462`. **Measured fact documented at `:419-429`: at the default TOPM=2 and rate 0.35 the top-M frontier is all-no-mega, so the foe-Mega depth-2 path is never reached.** Measured weights `[0.2453, 0.2453, 0.2453, 0.1321, 0.1321]` against ctx slots `[None, None, None, 0, 0]`. **Gate-design constraint — §5.4.** |
| 13a | **oneshot** — fresh process per batch | **YES** | default (`client.py:306-320`, `:53-84`) |
| 13b | **persistent cold** — first request incl. spawn | **YES, but only at a scope that contains the spawn** | `SHOWDOWN_CALC_BACKEND=persistent`; `_proc=None` at construction (`client.py:167`), spawn on first `_run_once` via `_ensure` (`client.py:176-180`, `:252`). Inside the timer at `agent_choose` (§1.2) and at `contexts_and_score`, but **outside** it at `score_evaluated_variants`: context construction already spawned the shared backend via `speed_for_species` (§2.8). **Rev. 7 correction** — Rev. 6 claimed "inside the timer" unconditionally. |
| 14 | **persistent warm** — steady state | **YES in production; SPLIT in fixtures** | Production shares one backend across damage **and** speed (`gauntlet.py:469-472`); fixtures do not (§3.A) — **P-5.** "Warmed-up" has no production symbol; `scripts/run_cap_latency_sweep.py:119-124` does it inline with 3 untimed decisions. |

### 4.1 Missing interfaces — the plan's actual input

**No helper is proposed here.** Recorded so the implementation plan can decide:

- **P-1** — no board with a Mega-capable opponent in slot **b**. Blocks arm 5.
- **P-2** — no board where our side lacks a Mega option. Blocks arm 7 as a board.
- **P-3** — no *decision-level* board with dual-Mega at **unequal** speed. Blocks arm 8 — the
  configuration the one live active decision used.
- **P-4** — no Trick-Room board at decision level. Blocks arm 10.
- **P-5** — fixtures' `SpeedOracle` does not share the calc backend
  (`tests/conftest.py:197` hard-codes its own `SubprocessCalcBackend()`), while production
  shares one (`gauntlet.py:469-472`), so arms 13/14 cannot be cleanly separated in a
  fixture-based microprofile. **Rev. 7 adds the consequence the plan must weigh:** sharing the
  backend — i.e. matching production — makes context construction spawn it via
  `speed_for_species` **before** `score_evaluated_variants` is entered, so `clean_cold` becomes
  unreachable at that scope (§2.8). P-5's fix therefore does **not** by itself make arm 13b
  measurable; it needs `timer_scope="contexts_and_score"` (§2.5). The plan must decide P-5 and
  the 13b scope **together** — fixing one without the other yields either a non-production
  topology or an unmeasurable arm.
- **P-6** — `DamageOracle.batch_calls` is cumulative and unread; per-decision deltas need a
  read strategy.
- **P-7** — nothing distinguishes the explicit `mega_scoring.py:626` flush from an
  `oracle.get`-triggered one. The planned/implicit split (§2.4) is the one genuinely new
  counter this design needs.
- **P-8** — no interface pairs two configs on an identical recorded state snapshot (§3.1).
- **P-9** — neither backend counts transport per method, nor **physical attempts**.
  `stats_batch`/`types_batch` reach the backend from three on-path sites that bypass the oracle
  (`engine/speed.py:120`, `engine/speed.py:149`, `battle/opponent.py:49`), so no round-trip
  count exists today. `SubprocessCalcBackend` has no counter at all (F-8), and
  `PersistentCalcBackend._run` can make two `_run_once` attempts per logical call (F-10).
- **P-10** — no profile manifest producer exists. `scripts/run_cap_latency_sweep.py:119-124`
  warms up inline but writes no manifest, so a microprofile has no provenance anchor today
  (§2.7).

Arms 5, 7-board, 8-decision and 10 are **NOT MEASURABLE** under this spec as written. A profile
run that omits them must not claim coverage of them.

### 4.2 C3 implementation status — P-1…P-5 closed

**The paragraphs above are the historical audit and are preserved verbatim.** They record what
was unconstructible *at C2 time* and why; they are not rewritten, because the reasoning is the
evidence that the closure below is real rather than assumed. This subsection records that C3
closed them.

| blocker | closed by | proof |
|---|---|---|
| **P-1** (foe Mega in p2.b) | an I8 board that places a real Aerodactylite holder in `p2.b`, resolved by the **real** `foe_mega_eligibility()` | `tests/i8`… `test_each_c3_arm_is_constructible_and_its_rows_validate[5]` |
| **P-2** (no own Mega) | a board coherent on **both** signals — `p1.a` holds no stone **and** the request's `canMegaEvo` is False — so `contexts=[None]` and the foe-Mega branch composes against it | arm 7 proof |
| **P-3** (dual-Mega, unequal speed, decision level) | a decision-level board with own Aerodactyl 200 vs foe Meganium 145; only the inequality is pinned, `200/145` is the real book-driven value | arm 8 proof |
| **P-4** (Trick Room, decision level) | the dual-unequal board with `field.trick_room` set on the **final** state before contexts are built — never a post-hoc `kw["state"]` swap | arm 10 proof |
| **P-5** (fixtures split the backend) | a **production-topology session** that shares one calc backend across damage/speed/dex (`gauntlet.py`'s topology), measured at `timer_scope="contexts_and_score"` so the scope contains the spawn context construction does | arms 13b (`clean_cold`) and 14 (`clean_warm`) proofs |

Also closed in support: **P-6/P-7** (per-decision deltas and the planned/implicit split — I8-A);
**P-9** (per-method transport + physical attempts — I8-A); **P-10** (the profile manifest
producer — I8-C/C1); and the request-outcome counters and the at-origin `MegaShapeCounts`
work-set telemetry the row shape needs (I8-A addendum + the C3 telemetry addendum). `timer_scope`
is now a pinned manifest field checked against every row, `behavior_env` is mandatory from the
manifest arm, and `fixture_input_hash` binds the complete §2.7 group-A input via
`group_a_fixture_dto`. **No run, evidence, D0, D-2 or optimization is authorized by this status;
it records that the arms are constructible, nothing about their measured latency.**

---

## 5. Gates — fixed before any run

### 5.1 Unchanged by fiat

- `decision_latency_p95_budget_ms: 1000` stays exactly as pinned (`config/eval/gates.yaml:6`).
- `SHOWDOWN_OPP_MEGA_CLICK_RATE` is **not** lowered to manufacture a PASS. Default `0.35`.
- `DEFAULT_MAX_CANDIDATES` (5), `SHOWDOWN_SEARCH_TOPN`, `SHOWDOWN_SEARCH_TOPM`,
  `SHOWDOWN_SEARCH_DEPTH`, `SHOWDOWN_WORLD_SAMPLES` and all accuracy settings are **not**
  changed after seeing a result. Arm 12 requires `TOPM ≥ 4` — that is an **arm configuration
  pinned here, before any run**, and its results are reported as a TOPM≥4 arm, never merged
  into a default-TOPM claim.
- Arm configurations are pinned **in this document** before the first run.

### 5.2 The aggregate p95 alone is not a verdict — with evidence

§0.1 is the proof, not an argument: the frozen run's worst p95 (672 ms) came from an
**inactive** turn-1 decision, while the only **active** decision cost 83 ms, and
r(candidates, latency) = 0.921. **A gate on `max(per-battle p95)` measures hero-candidate
count.** It is retained as the existing safety gate and is **not** the I8 verdict.

### 5.3 Separate gate value for genuinely active foe-Mega decisions

The I8 verdict is evaluated over profile rows matching **all four** conditions — this is the
full gate predicate, not an abbreviation:

```
source == "live"  AND  timer_scope == "agent_choose"  AND  outcome == "ok"  AND  foe_mega_active
```

`foe_mega_active` alone is **not** the predicate. `outcome == "ok"` is required because a
crashed decision's row carries `measured_ms = null` and its wall clock is the crash handler, not
decision work (§2.6). `source`/`timer_scope` are required because a microprofile row measures a
narrower boundary and must never be compared to the budget (§2.5).

- **Absolute (gated):** p95 of `measured_ms` over rows matching the predicate above, vs the
  unchanged 1000 ms budget. Rows with `outcome != "ok"` are **excluded from the statistic and
  reported separately by count**, never silently dropped.
- **Causal marginal cost (reported, microprofile only):** the controlled A/B on a fixed board —
  e.g. arm 9 vs arm 1 — reported as Δ round trips, Δ requests and Δ ms with its rep count.
- **Live active-vs-inactive ratio: NOT REPORTED AS A FOE-MEGA EFFECT.** §3.1 — it is a board
  divergence measurement wearing a foe-Mega label.

**No new numeric threshold is proposed.** The only pinned number is the existing 1000 ms. The
causal Δ is **reported, not gated**: no pre-existing baseline or pre-declared statistical rule
licenses a threshold on it, and inventing one after seeing the data is precisely the judgment
call this spec forbids. A Δ gate would require its own approved revision **before** the run.

### 5.4 Exposure floor — D-1, closed

A latency verdict over active decisions requires enough of them to mean anything. **The floor
is a precondition, not a result**: a run that misses it yields
`INCONCLUSIVE — exposure floor not met`, never PASS and never FAIL.

**Derived necessary floor: n ≥ 12 active decisions per gated arm.** This is derived from the
production statistic itself, not chosen. `_latency_p95` (`gauntlet.py:171-176`) is nearest-rank:
`idx = min(len-1, round(0.95 * (len-1)))`. Evaluating it directly over strictly increasing
inputs: **for n ≤ 11 it returns the maximum**; at **n = 12** it first returns a non-maximal
order statistic. Below 12, calling the gate value a "p95" is a misnomer — it is `max()`, so a
single outlier decides the verdict.

*(Recorded: the review proposed `n ≥ 20` on the grounds that "below that the nearest-rank p95
is simply the maximum". The value may well be reasonable; **the stated reason is not exact** —
the degeneracy ends at n = 12, verified by evaluating `_latency_p95` itself. This spec adopts
only what it can derive.)*

**n ≥ 12 is necessary, not sufficient.** A stable tail estimate needs more, and how much more
is a statistical-power question this document cannot answer by derivation. Two facts frame it:

- the frozen live run produced **1 active decision in 17** (§0.1) — n = 1;
- at default `SHOWDOWN_SEARCH_TOPM=2` the depth-2 foe-Mega frontier is **never reached** (arm
  12), so a depth-2 claim needs its own exposure statement.

**D-1 — CLOSED. Binding, pre-declared before any run.** The sufficient floor is a decision, not
a derivation; it was taken by the approver and is recorded here verbatim as the pre-declared rule
this spec required:

| | |
|---|---|
| **Minimum decisions** | **≥ 60** valid active foe-Mega decisions |
| **Minimum spread** | from **≥ 20 distinct battles** (distinct `battle_id`) |
| **Valid row** | `source == "live" AND timer_scope == "agent_choose" AND outcome == "ok" AND foe_mega_active` — **this is §5.3's gate predicate, referenced rather than restated**, so the two cannot drift |
| **PASS** | floor met **and** p95 of `measured_ms` over those rows **≤ 1000 ms** |
| **FAIL** | floor met **and** p95 **> 1000 ms** |
| **INCONCLUSIVE** | either minimum not reached — `INCONCLUSIVE — exposure floor not met`. Never PASS, never FAIL |
| **Claim boundary** | **no general statistical claim and no strength claim.** The verdict is about this budget on this exposure, and nothing else (§6, §8) |

Both minima are **preconditions evaluated before the p95**, not filters applied after seeing it.
Neither may be lowered to rescue a run: a run that misses the floor is `INCONCLUSIVE` and its
p95 is not reported as a verdict.

**The floor satisfies the derived necessary condition.** 60 ≥ 12, so the nearest-rank degeneracy
above is not in play: at n ≥ 60 the gate value is a genuine non-maximal order statistic rather
than `max()` wearing a p95 label. The ≥ 20-battle spread is the second minimum and is not
derivable from `_latency_p95` at all — it bounds *concentration*, since 60 decisions drawn from
two battles would measure two boards, not the format.

The microprofile is unaffected — its arm sizes are chosen, not sampled, so exposure is a design
parameter there rather than an outcome. D-1 governs the **live** verdict only.

### 5.4a I8-D schedule & stop semantics — CLOSED 2026-07-18 (approver-set)

D-1/D-2 fixed the floor and the caps but not the concrete battle schedule; the harness
implementation STOPPED and reported the gap, and these are now bound (see the plan §5.4 for the
full statement). Summary, because the gate predicate depends on them:

- **Dev-only 6-matchup matrix, fixed cyclic order** — `goodstuff`, `tailwind_offense`, `trick_room`
  each × `heuristic` then `max_damage`; held-out `rain_offense`/`disruption` **excluded** from I8-D.
- **`MAX_BATTLES = 200` ⇒ distribution `34, 34, 33, 33, 33, 33`** (cyclic round-robin; never
  re-ordered by exposure or latency).
- **Seed base `champions-panel-v0-i8d-latency`, `seed_index = 0..199`**, `seed_index=i` bound to
  schedule row `i`, all materialised before the first battle. The `seed_index` values are frozen in
  `schedule_hash`; the seed **namespace** is **not** in that hash (code-review finding 2), so the
  runner binds it separately — it asserts `SHOWDOWN_BATTLE_SEED_BASE == champions-panel-v0-i8d-latency`
  and verifies the server's Channel-A seed log (`derive_battle_seed`) before any verdict is written.
- **Whole-battle stop semantics** — stop conditions are evaluated only after a fully-completed,
  validated battle; a running battle is never aborted. `scored_decisions` may therefore exceed
  `MAX_SCORED_DECISIONS` by **at most one completed battle's** scored decisions; this bounded
  overshoot is reported and is **not** an error and is **not** corrected by truncation or mid-battle
  abort. Once D-1 is met the run ends after that battle — no extra battles to move the p95.

### 5.4b Live `outcome` derivation — harness finding (minimal erratum)

The row `outcome` (§2.4/§2.6) is derived from **existing** signals: `crash` = the `agent_choose`
exception handler; `degraded_state` = `state is None and not req.team_preview`; `fallback` vs `ok`
= `choose_with_fallback`'s `selection_stage` (`"heuristic"` ⇒ `ok`; a fallback stage ⇒ `fallback`).
Reading `selection_stage` requires the live profile to build/reuse a `DecisionTrace`; this is
consistent with the live-latency baseline (I7b-C smoke, measured with the trace seam on), and §2.2
forbids only a **second timer**, not passive telemetry. Correct `fallback` classification is
load-bearing: a timed-out heuristic fallback mislabelled `ok` would carry a non-decision-core
`measured_ms` into the p95 — precisely what §2.6's `outcome == "ok"` predicate excludes.

### 5.4c First live attempts — ABORTED before battle creation; team-path wiring fix (2026-07-18)

**Both** authorized I8-D live attempts **aborted with no verdict, no evidence, and no latency
statement** — and crucially **before any battle was ever created** (`seeds.jsonl` empty, `out/` never
published). Root cause: an **I8-D team-path wiring bug**. `run_local_gauntlet` loads the battle team
files relative to the process CWD, but the `i8d-live-gate` command runs from the repo root (so the
repo-root-relative panel path resolves) while the team files live under `showdown_bot/teams/`.
`--teams-root` was only used to HASH the teams (`verify_i8d_panel_and_teams`), not to LOAD them at
battle time, so the gauntlet got missing files, `_resolve_side_teams` silently degraded them to
EMPTY packed teams, the server rejected the empty-team challenge, no battle was created, and the gate
only timed out. **Neither timeout (180 s attempt 1, 900 s attempt 2) was ever the cause** — no battle
ever started to be slow.

**The 900 s decision is RETRACTED.** It rested on a wrong "slow battle" diagnosis, was **never
empirically exercised**, and its `config_hash 06b2b96e76486563` is void. Both aborted runs' logs are
**scratch diagnostics only, never pooled**.

**Fix:** `run_i8d_live_gate` takes `teams_root` and, immediately before `run_local_gauntlet`,
resolves the hero/opponent paths to ABSOLUTE against that root and proves each loads a NON-EMPTY
packed team — failing closed before any server/battle otherwise. The schedule's stored relative
paths and `schedule_hash` are untouched, and `run_local_gauntlet` (and `run_schedule`) is not
changed. The next real attempt reverts to the **original stratum**: `oneshot`, **standard 180 s / no
`SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S`**, `config_hash` expected back to `594295543f13a55d`, restart at
**seed 0**, separately authorized.

### 5.5 Backend class — two clean predicates and a residual

Never pooled. **Classification is derived from the backend's observed state, never from
"is this the battle's first decision"** (Rev. 4 correction). Rev. 3 tied `persistent_cold` to
the first decision; that is wrong, because team preview returns from `agent_choose` before any
calc use (`gauntlet.py:117-118`, `_state_for` at `:526-527`), so the battle's first decision can
complete with the process never started — and the first *regular* turn, which does start it, is
no longer the first decision and would have been mislabelled `persistent_restarted`.

The rule is a predicate over three observed facts, all carried on the row:

**Rev. 7: this is a predicate, not an enum — and that is the point.** Revisions 4, 5 and 6 each
hand-enumerated backend states, and each enumeration missed a reachable cell:

| revision | missed cell |
|---|---|
| Rev. 4 | cold start whose first attempt fails → two spawns, a retry, still called clean `persistent_cold` |
| Rev. 5 | process dies **between** decisions → `_ensure` respawns with **no** retry; the validator demanded `retried=true` and would have rejected a real, successful row |
| Rev. 6 | process dies **within** a decision, between two logical calls → `spawn_count_before=0`, `spawn_calls=2`, `attempts == calls`, `retried=false`. `persistent_cold_retried` demanded a retry; `persistent_respawned` demanded `spawn_count_before ≥ 1`. **No state matched.** |

Three misses in three revisions is not bad luck; hand-enumerating a product of three independent
variables is the defect. So the classification is now a **predicate over the raw facts, with a
residual**, and cannot miss a cell:

**Raw facts, all observed and all on the row:**

- `spawn_count_before` — the backend's cumulative spawn count before this decision
- `spawn_calls` — spawns during it
- `transport_retried` := `transport_attempts > transport_calls` — **a statement about failed
  attempts, never about spawns.** `_ensure` (`client.py:176-180`) revives a dead process before
  the first attempt with no failure at all, so a spawn does not imply a retry (F-13).

**Derived classification (`backend_class`), exhaustive by construction:**

```
oneshot        := calc_backend == "oneshot"
clean_cold     := persistent ∧ spawn_count_before == 0 ∧ spawn_calls == 1 ∧ ¬transport_retried
clean_warm     := persistent ∧ spawn_count_before >= 1 ∧ spawn_calls == 0 ∧ ¬transport_retried
contaminated   := persistent ∧ ¬clean_cold ∧ ¬clean_warm          # the residual
```

`contaminated` is defined as the negation of the two clean cases, so **every** combination of
(`spawn_count_before`, `spawn_calls`, `transport_retried`) lands somewhere — including the three
cells the enums missed, plus `spawn_calls == 0 ∧ spawn_count_before == 0` (a decision that used
no calc at all) and any cell nobody has thought of yet.

**Binding: only `clean_cold` and `clean_warm` enter a cold/warm contrast.** `contaminated` rows
are excluded and reported by count, broken down by the raw facts so the reason is visible rather
than hidden behind a label — the two clean predicates are the contract; the taxonomy of dirt is
diagnostics.

The two underlying transport realities are:

- **oneshot**: a fresh Node process per batch (`client.py:53-84`); nothing to warm.
- **persistent**: `_proc=None` at construction (`client.py:167`); the spawn is lazy via
  `_ensure` on the first `_run_once` (`:176-180`, `:252`) — **inside the `agent_choose` timer**
  (§1.2), in whichever decision first uses calc. Whether it is inside a *microprofile* timer
  depends on that arm's `timer_scope`, and at `score_evaluated_variants` it is **not** (§2.8).

**Team preview.** A preview decision uses no calc: `spawn_calls == 0` with
`spawn_count_before == 0` and every counter zero. Under the predicate above that is neither
`clean_cold` nor `clean_warm`, so it falls to `contaminated` — correctly, since it carries no
calc cost to contrast, but it would inflate the contaminated count with rows that are not
actually dirty. **Binding: team-preview decisions are not profiled** — the profile writer
mirrors the opp-mega sidecar's gate and emits only for decisions with battle state
(`state is not None`, `gauntlet.py:526-527`), so a preview never produces a profile row. A
zero-calc row therefore remains reachable only for a **stateful** decision that used no calc at
all, and the `contaminated` breakdown by raw facts is what makes that case visible instead of
silently pooled.

### 5.6 What a result may and may not authorize

- **FAIL → a separate optimization slice.** The budget is not loosened. Given §0.4, the first
  hypothesis such a slice must test is **round-trip count** — specifically implicit flushes
  from prefetch misses — not "make scoring faster".
- **PASS authorizes no Strength run.** It only unblocks the *design* of the coverage +
  independent-holdout slice (§6).
- **Neither PASS nor FAIL licenses a claim about arms 5, 7-board, 8-decision or 10**, which are
  not measurable today (§4.1).

---

## 6. Boundary to coverage and Strength

This spec is measurement-only. It **does not**: select a Strength panel; use `rain_offense` as
a holdout; interpret winrates; select seeds by exposure; authorize a Strength run; or claim
slot-0 / dual-Mega coverage that was not measured.

After a latency PASS, a **separate approved spec** is required for: broader opponent-Mega
exposure; slot 0 **and** slot 1; dual-Mega and activation ordering; an independent holdout; and
a pre-declared statistical decision rule. `docs/ROADMAP.md` already binds this order.

`rain_offense` is not an independent Strength holdout (reused across parser/I5/I6/I7a safety
work) — recorded verbatim from the roadmap, unchanged by this spec.

---

## 7. Open findings and decisions

| id | item |
|---|---|
| **D-1** | **CLOSED** — approver-set, pre-declared before any run (§5.4): ≥ 60 valid active foe-Mega decisions from ≥ 20 distinct battles; valid row = §5.3's gate predicate; p95 ≤ 1000 ms ⇒ PASS, > 1000 ms ⇒ FAIL, floor not met ⇒ INCONCLUSIVE; no general statistical or strength claim. |
| **F-1** | **Two independent latency thresholds exist.** `gates.yaml:6` pins 1000 ms; `cli.py:559-560` hard-codes `p95 >= 1.5` s on the `--games N --strict` path without reading `gates.yaml`. They can drift. Recorded, not changed. |
| **F-2** | `DamageOracle.batch_calls` (`oracle.py:26`, `:50`) and `PersistentCalcBackend.spawn_count` (`client.py:171`, `:199`) are written and **never read**. **Neither is a round-trip count**: `batch_calls` is damage-only, and `stats_batch`/`types_batch` bypass the oracle from **three** on-path call sites (§0.4). |
| **F-3** | `DamageOracle.get` auto-flushes (`oracle.py:55-58`), so a **prefetch miss is a silent mid-evaluation round trip** — a full process spawn under the default backend. Nothing counts, surfaces or enforces prefetch coverage. |
| **F-4** | The **state build is outside the timer** (`gauntlet.py:551`) and re-replays the whole accumulated room log every decision, growing with turn count. Any "request handling is within budget" claim is unsupported by the current metric. |
| **F-5** | `_latency_p95` rounds to **integer ms** (`gauntlet.py:204`), degenerates to `max()` for n ≤ 11 (§5.4), and includes **team-preview decisions** as near-zero samples (`gauntlet.py:653`; `_state_for` returns `None` for preview at `:526-527`), diluting the p95 downward. |
| **F-6** | Fixtures' `SpeedOracle` does not share the calc backend (P-5), so `persistent` cannot be cleanly profiled through them. |
| **F-7** | `SHOWDOWN_CALC_BACKEND` is `NON_BEHAVIORAL` with an explicit caveat (`config_env.py:106-109`): both backends call the same Node script, so results are numerically identical **today**. A profile that varies it does not perturb `config_hash` — which is what makes cold/warm arms comparable at all. |
| **F-8** | `SubprocessCalcBackend` has **no counter of any kind**, although it spawns a Node process per batch. Under `oneshot`, spawns == `transport_attempts` by construction (§2.4) — derivable once transport is counted, but not observed today. |

| **F-9** | `DamageOracle.flush()` early-returns on an empty pending map (`oracle.py:42-43`) **before** incrementing `batch_calls` (`:50`). An explicit flush over a fully cache-resident map therefore costs a call but no batch. Since the oracle cache is per battle and never evicted (§1.5), later decisions and extra worlds can legitimately flush nothing — which is why the planned/implicit split must be attributed at the batch, not derived by subtracting call counts (§2.4). |

| **F-10** | `PersistentCalcBackend._run` (`client.py:238-249`) retries once through a fresh process on `_TransportError` (`:242-245`). One logical `calc_batch` can therefore be **two** physical `_run_once` attempts, both paying latency, with nothing distinguishing them. Logical calls and physical attempts must be counted separately (§2.4). |
| **F-11** | Team preview returns from `agent_choose` before any calc use (`gauntlet.py:117-118`; `_state_for` returns `None` for preview at `:526-527`), so a persistent backend can still be unstarted after the battle's first decision. Any classification keyed on "first decision" is wrong; §5.5 keys on observed `spawn_count_before`/`spawn_calls` instead. |

| **F-12** | `_run_once` calls `_ensure()` on its first line (`client.py:252`), so a **cold** start spawns inside the first attempt. If that attempt fails, `_run` spawns again and retries (`:242-245`) — a cold decision can therefore end with `spawn_calls = 2` and `transport_attempts = 2` for **one** logical call. Cold-with-retry is a distinct, contaminated state (§5.5). |
| **F-13** | `_ensure` (`client.py:176-180`) revives a process that died **between** decisions before the first attempt — a spawn with **no** retry (`spawn_calls=1, attempts=calls, retried=false`). A spawn therefore does not imply a retry, and `transport_retried` must be defined from `attempts > calls` alone (§5.5). |
| **F-14** | `DamageOracle._cache` is never cleared or evicted (`oracle.py:24`, `:53`), and `SpeedOracle._spe_cache` (`engine/speed.py:103`) / `SpeciesDex._cache` (`battle/opponent.py:45`) behave the same. A microprofile that reuses these objects across repetitions has its warmup populate the cache for every timed rep, so reps 2..N would measure ~zero calc — silently. Cache lifecycle must be declared per arm (§2.8). |
| **F-15** | `PokemonState.moves` and `.move_names` are `set[str]` (`engine/state.py:66-67`). `json.dumps` raises `TypeError` on a set, and any `str()` fallback is iteration-order dependent — so "canonical JSON over the board" is not a specification without an explicit set→sorted-list encoder (§2.7). |

**Explicitly out of this slice** (may be mentioned, never implemented here): the I7a
CRLF/config-hash impact audit; Studio exporter/Godot; EPOké/belief audit; search/K-world
optimization; a calc-backend change; a new engine; Strength evaluation; new behaviour env
knobs; any budget change; any production optimization.

---

## 8. Non-claims

- No profile has been run. Every number in §0 is **re-derived from already-committed
  artifacts** or quoted from a recorded prior measurement with its methodology attached.
- The ≈2.4× is **not** a general foe-Mega figure (§0.3): it was measured under `oneshot` — the
  default — with a cold Node spawn per batch, while the smoke explicitly opted into
  `persistent`. The two describe different configurations.
- The 672 ms is **not** a foe-Mega figure (§0.1): that decision had no Mega hypothesis.
- The 83 ms active decision is **not** evidence that the foe-Mega path is cheap: n = 1, 1
  branch, at the response cap, and the expensive tie case was never exercised live.
- r = 0.921 (§0.1) is **association, not causation**: candidate count is confounded with turn
  number in this run.
- **Champions Strength remains NO-GO.** This spec does not change it.

---

## 9. Rev. 1 → Rev. 2: corrections

Recorded rather than silently rewritten.

| # | Rev. 1 claim | Status | Correction |
|---|---|---|---|
| 1 | "The Node calc spawn is excluded from the first decision's recorded latency" (§1.2) | **FALSE** | `_decision_deps()` constructs only: `PersistentCalcBackend.__init__` sets `_proc=None` (`client.py:167`), `SpeedOracle.__init__` and `SpeciesDex.__init__` store the backend and an empty cache without calling it (`engine/speed.py:96-104`, `battle/opponent.py:39-50`). The spawn is lazy via `_ensure` on the first batch — **inside `agent_choose`, inside the timer**. It also contradicted §5.5. Corrected in §1.2, §4 (arm 13b) and §5.5. |
| 2 | "[the opp-mega sidecar] only has rows for decisions that produced foe-Mega evidence" (§2.3) | **FALSE** | Its writer fires for every successful regular heuristic decision with state; the frozen file has **17 rows for 17 non-preview decisions — 16 entirely `foe_mega_slot=None`, 1 active, 0 empty**. The reason is withdrawn; §2.3's other two reasons stand on their own. |
| 3 | "measured under a backend production does not use" (§0.3 heading) | **INVERTED** | `oneshot` is the **default**, i.e. the default production configuration, and the ≈2.4× ran under it. The **smoke** was the deviation (`persistent`). Corrected in §0.3 with an explicit backend table. |
| 4 | §0.1 table binned the 6.2 ms decision under "1–2 candidates" | **WRONG** | It is `242a0c3e#7` with **5** candidates. §0.1 now lists all 17 rows individually with battle#idx, and adds Pearson r = 0.9210 over n = 17. |
| 5 | "Round trips are **not** multiplied by V/R/C" (§1.6) | **TOO CATEGORICAL** | True for *planned* flushes only. Implicit flushes from prefetch misses **can** scale with the fan-out, since every evaluation leaf reaches `oracle.get`. Rewritten; whether they do in practice is a question the profile must answer, not assume. |
| 6 | §5.3 proposed a live "active vs paired inactive arm" ratio | **NOT CAUSAL** | Same seeds do not reproduce the same board once decisions diverge, and within-run active/inactive are different turns. Causal ratios are now **microprofile-only** (§3.1); a live snapshot-paired design is recorded as P-8. |
| 7 | §2.3 declared a separate sidecar without a contract | **INCOMPLETE** | §2.4 now specifies module, env switch and classification, join identity for both run kinds, the exact closed field set with per-decision deltas, the planned/implicit flush split, emission point, validator, LF byte policy, error semantics, and the microprofile/live validity boundary. |
| 8 | D-1 left entirely open | **PARTIALLY CLOSED** | `n ≥ 12` is now **derived** from `_latency_p95`'s own algorithm (p95 == max for n ≤ 11). The sufficient floor stays open; the review's `n ≥ 20` rationale was checked and is **not exact** — the degeneracy ends at 12, not 20. |

### Rev. 2 → Rev. 3

| # | Rev. 2 claim | Status | Correction |
|---|---|---|---|
| 9 | "`batch_calls_delta` = round trips this decision"; "under `oneshot`, spawns == `batch_calls_delta`" (§2.4) | **FALSE** | `batch_calls` counts **damage batches only**. `stats_batch`/`types_batch` reach the backend from four sites that bypass the oracle — `battle/opponent.py:49`, `engine/belief/hypotheses.py:207`, `engine/speed.py:120`, `engine/speed.py:149` — each a Node process under `oneshot`, and exactly what a first Mega context needs. Transport is now counted at the **backend**, split damage/stats/types/spawns, with `transport_calls` as the round-trip total (§2.4, P-9). |
| 10 | "`implicit_flushes = batch_calls_delta − planned_flushes`", enforced by the validator (§2.4) | **INVALID** | `flush()` early-returns on an empty pending map (`oracle.py:42-43`) **before** `batch_calls += 1` (`:50`), so an empty explicit flush gives `0 − 1 = −1`. Realistic, not hypothetical: the oracle cache is per battle and never evicted, so a later decision or an extra world can flush nothing. Rev. 2's validator would have enforced a broken invariant. The split is now attributed at the actual non-empty batch — `damage_batch_calls == planned_damage_batches + implicit_damage_batches` (§2.4, F-9, P-7). |
| 11 | Crash semantics: emit "only when the agent completed" **and** an `outcome="crash"` row, with `decision_latency_ms` a mandatory float, while the gate filtered only on `foe_mega_active` (§2.4) | **SELF-CONTRADICTORY, gate-polluting** | Variant 2 adopted (§2.6): non-ok rows **are** written (their counters are real), `measured_ms` is **`null`** whenever `outcome != "ok"`, and every latency gate/statistic now requires `outcome == "ok"` explicitly in its predicate (§5.3). |
| 12 | `persistent_cold` covered every non-warm persistent case (§5.5) | **AMBIGUOUS** | A `_TransportError` re-spawn (`client.py:242-243`) is neither cold nor warm. Added `persistent_restarted` as a fourth state, excluded from cold/warm comparisons and reported by count (§5.5). |
| 13 | Microprofile `decision_latency_ms` was "the same quantity trace-v3 records" (§2.4) | **UNDEFINED** | The microprofile enters at `score_evaluated_variants`, not `agent_choose`; the boundary was never stated. Renamed to `measured_ms` with a mandatory `timer_scope` field (`"agent_choose"` \| `"score_evaluated_variants"`); only `agent_choose` rows may meet the budget, and rows with different `timer_scope` may never be pooled (§2.5). |

### Rev. 3 → Rev. 4

| # | Rev. 3 claim | Status | Correction |
|---|---|---|---|
| 14 | `transport_calls` = "**round trips this decision**"; `spawn_calls == transport_calls` under `oneshot` (§2.4) | **CONFLATES LOGICAL WITH PHYSICAL** | `PersistentCalcBackend._run` (`client.py:238-249`) retries once through a fresh process on `_TransportError` (`:242-245`), so one logical `calc_batch` can be **two** physical `_run_once` attempts. Rev. 3 would have reported `transport_calls=1, spawn_calls=1` while two attempts paid latency — worst of all in `persistent_restarted`, the state where this happens by definition. Split into logical `*_batch_calls` / physical `transport_attempts` / `spawn_calls`, with `transport_attempts >= transport_calls` enforced (§2.4, F-10, P-9). |
| 15 | Four `backend_state` values, with `persistent_cold` = "the battle's first request" (§5.5) | **NOT EXHAUSTIVE, AND MIS-KEYED** | Team preview returns from `agent_choose` before any calc use (`gauntlet.py:117-118`, `:526-527`), so the first decision can complete with the process **never started** — no Rev. 3 state describes that. Worse, the first *regular* turn then starts the process but is not the first decision, so Rev. 3's rule would have called it `persistent_restarted`. Classification is now derived from observed `spawn_count_before`/`spawn_calls`, giving five mutually exclusive, exhaustive states incl. `persistent_unstarted`; and **team-preview decisions are not profiled at all** (§5.5, F-11). |
| 16 | Microprofile rows required `schedule_hash`; `arm_id` was their identity (§2.4) | **NO PROVENANCE ANCHOR** | A microprofile runs no schedule, and `arm_id` is a label binding no fixture bytes, reps, warmup, arm parameters or env — two runs could share an `arm_id` and be incomparable, making the causal comparisons irreproducible. `schedule_hash` is now `null` for microprofile rows and a mandatory `profile_manifest_hash` anchors them to a manifest pinning arm config, fixture hashes, reps and the warmup rule (§2.7, P-10). |
| 17 | "Four call sites reach the backend without going through the oracle" (§0.4) — Rev. 3's own addition to the review's list | **OVERCLAIM** | `engine/belief/hypotheses.py:207` is a real oracle bypass, but `load_opp_sets_for_format` runs once at **run setup** (`client/gauntlet.py:913`) on its **own** `SubprocessCalcBackend()` (`hypotheses.py:204`), outside the decision timer. It is run-setup cost, not per-decision transport. **Three** on-path sites, not four (§0.4). |
| 18 | §5.3 "all three conditions" listing four; §5.5 titled "three states" listing four; a stale `decision_latency_ms` in the validity boundary | **DOC ERRORS** | Corrected to "all four", "five states", and `measured_ms`. |

### Rev. 4 → Rev. 5

| # | Rev. 4 claim | Status | Correction |
|---|---|---|---|
| 19 | `persistent_cold` = `spawn_count_before == 0 and spawn_calls >= 1`; `persistent_restarted` is "the one state where `transport_attempts > transport_calls`" (§5.5) | **FALSE, and it contaminated the contrast** | `_run_once` calls `_ensure()` on its first line (`client.py:252`), so a cold start spawns inside the first attempt; a failure there makes `_run` spawn **again** and retry (`:242-245`). The real row is `spawn_count_before=0, spawn_calls=2, transport_attempts=2, transport_calls=1` — which Rev. 4 called a clean `persistent_cold` and fed into the cold/warm contrast. Added `persistent_cold_restarted` (six states, exhaustive over `spawn_count_before`×`spawn_calls`), an explicit `transport_retried` field, `persistent_cold` now requires **exactly one** spawn and no retry, and **any** retried row is excluded from cold/warm (§5.5, F-12). |
| 20 | `fixture_hashes` = "the constructed board's canonical serialisation" (§2.7) | **BINDS ~1/10 OF THE INPUTS** | `_build_mega_decision_kw` (`tests/conftest.py:178-218`) feeds ten primary scoring inputs — state, request, legal actions, `SpreadBook`, `our_spreads`, `opp_sets`, `EvalWeights`, `GameMode`, `calc_profile`, `species_meta`. Two runs could share a board hash and differ in spreads, legal actions, weights or mode, producing different scores *and* costs. Replaced by `fixture_input_hash` over all ten, with derived `contexts`/`evaluated_variants` deliberately excluded and cross-checked via `n_candidates` (§2.7). |
| 21 | One top-level manifest `config_hash` + one `behavior_env` for the whole run (§2.7) | **IMPOSSIBLE FOR AN ARM MATRIX** | The arms vary `SHOWDOWN_OPP_MEGA_CLICK_RATE` (`config_env.py:85`) and `SHOWDOWN_SEARCH_DEPTH` (`:40`), both **BEHAVIOR_AFFECTING** — so arms have different effective config hashes by definition. Top level now carries only run-invariant provenance; each arm entry carries its own `effective_config_hash`, full effective `behavior_env`, `arm_params` (incl. the non-behavioural TOPM/TOPN/backend) and `fixture_input_hash`. The validator requires each row's `config_hash` to equal its arm's entry (§2.4, §2.7). |
| 22 | Rev. 4's own corrections applied in §0.4/§5.5 only | **INCONSISTENT** | Six places still carried the superseded text: the `backend_state` field listed four values without `persistent_unstarted`; §2.4's counter paragraph still claimed four per-decision bypasses naming `hypotheses.py:207`; `types_batch_calls` still said "SpeciesDex / hypotheses"; F-2 still said four call sites; F-8 still said `spawns == transport_calls`; and the non-empty-list guard was implicit for `stats_batch`/`types_batch`. All swept, and the guards pinned to the code that already implements them (`client.py:54-55`, `:114-115`, `:124-125`, `:278-279`, `:287-288`, `:297-298`). |

### Rev. 5 → Rev. 6

| # | Rev. 5 claim | Status | Correction |
|---|---|---|---|
| 23 | "a retry is always preceded by a spawn … therefore `transport_retried` ⇔ `spawn_calls ≥ 1` when `spawn_count_before ≥ 1`"; `persistent_restarted` required `transport_retried is True` (§5.5) | **FALSE — the validator would reject a real row** | The implication does not invert: **a spawn does not imply a retry.** `_ensure` (`client.py:176-180`) checks `poll()` and revives a process that died *between* decisions **before the first attempt** — `spawn_count_before≥1, spawn_calls=1, attempts=1, calls=1, retried=false`. Rev. 5 called that `persistent_restarted` and then demanded `retried=True` for it, so a real successful decision would have failed validation. `transport_retried` is now defined **solely** as `attempts > calls`; restart and retry are independent. Seven states, exhaustive over (`spawn_count_before`, `spawn_calls`, `transport_retried`), with the new `persistent_respawned` for exactly this case (§5.5, F-13). |
| 24 | The manifest pinned warmup and backend restarts, but not cache lifecycle (§2.7) | **THE MEASUREMENT'S BIGGEST FREE VARIABLE** | `DamageOracle._cache` is never cleared or evicted (`oracle.py:24`, `:53`); ditto `SpeedOracle._spe_cache` and `SpeciesDex._cache`. An arm reusing one oracle across reps would have its **warmup populate the cache for every timed rep**, so reps 2..N would report `damage_batch_calls ≈ 0` and the profile would conclude the foe-Mega path is nearly free — while measuring its own cache, with nothing failing. §2.8 now requires an explicit per-arm `lifecycle` for backend/damage-oracle/speed-oracle/dex/contexts, defines the two coherent configurations (cold-cache, warm-cache), and makes `backend_state` the cross-check on the declaration (F-14). |
| 25 | `fixture_input_hash` = `sha1(canonical_json(<all ten, canonically serialised>))` (§2.7) | **NEITHER COMPLETE NOR DEFINED — the same charge Rev. 5 laid against Rev. 4** | *Incomplete*: `score_evaluated_variants` (`mega_scoring.py:334-361`) takes ~19 direct arguments; the ten omitted `priors`, `risk_lambda`, `rollout_horizon`, `accuracy_mode`, `accuracy_branch_cap`, `endgame`, `fast_board` and `foe_mega_eligibility`. *Undefined*: `PokemonState.moves`/`.move_names` are `set[str]` (`engine/state.py:66-67`) and `json.dumps` cannot serialise a set at all. Split into fixture-bound (group A → `fixture_input_hash`) and call-bound (group B → the arm entry's `scoring_params`, since an arm *is* a choice of those), with an explicit DTO, set→sorted-list normalisation, full-precision floats, preserved nulls and a fail-closed encoder (§2.7, F-15). |
| 26 | §5.5 titled "five states" listing six; "The three states below" followed by two categories | **DOC ERRORS** | Corrected to "seven states" and "The two underlying transport realities are". |

### Rev. 6 → Rev. 7

| # | Rev. 6 claim | verdict | why |
|---|---|---|---|
| 27 | Seven `backend_state` values, "mutually exclusive and exhaustive over (`spawn_count_before`, `spawn_calls`, `transport_retried`)" (§5.5) | **STILL NOT EXHAUSTIVE — third miss in three revisions** | A process that dies **within** a decision, between two logical calls, and is revived by `_ensure` with no failure gives `spawn_count_before=0`, `spawn_calls=2`, `transport_retried=false`. `persistent_cold` required `spawn_calls==1`; `persistent_cold_retried` required a retry; `persistent_respawned` required `spawn_count_before>=1`. **No state matched a real, successful row.** Fixed structurally, not by adding an eighth state: `backend_class` is now a **predicate** with `contaminated` as the residual (§5.5), so no cell can be missed. |
| 28 | "A **cold-cache** arm reaches `persistent_cold` on every rep by construction" (§2.8) | **FALSE — and it inverted the effect of fixing P-5** | `build_own_mega_contexts` (`mega_scoring.py:210`) → `filter_projectable_variants` (`mega_variants.py:73`) → `project_mega` (`:119`) → `speed_for_species` (`mega_projection.py:127`) → `_base_speed` (`speed.py:176`/`:185`) → `backend.stats_batch` (`speed.py:120`). Context construction runs **before** `score_evaluated_variants`, and a cold-cache arm's fresh `_spe_cache` always misses — so with P-5 fixed (shared backend, as production) the spawn happens **outside** the timer and every rep is `clean_warm`. Rev. 6 had it exactly backwards. Fixed by separating `backend_class` (observed, about the process) from `cache_class` (declared, about the semantic caches) and adding `timer_scope="contexts_and_score"` for the arms whose subject is the spawn (§2.5/§2.8). |
| 29 | Arm 13b: the spawn is "**inside the timer** (§1.2)" (§4) | **TRUE FOR LIVE, FALSE FOR THE MICROPROFILE** | §1.2's claim is about `agent_choose`, where it holds (`_decision_deps()` only constructs, `gauntlet.py:433-480`). Rev. 6 carried it to a microprofile whose only scope was `score_evaluated_variants`, where the spawn is already gone — so 13b was an arm the design **could not measure** and did not know it. Arm 13b now names the scopes that contain its subject. |
| 30 | `SpreadPreset` serialised as "nature + sorted EV pairs per preset" (§2.7) | **DROPS AN INPUT THAT DRIVES THE DOMINANT COST** | `SpreadPreset.items` exists (`engine/belief/hypotheses.py:21-24`) and carries **Choice Scarf**, which `likely_speed` reads for speed (`engine/speed.py:130`). Speed decides tie-vs-unequal, which decides 2 branches @ 0.5 vs 1 @ 1.0 (§0.2) — the largest cost driver in the slice. Two books differing only in `items` would have shared a `fixture_input_hash` while producing different branch counts and latencies: **actively misleading, not merely incomplete.** Fixed by adding sorted `items` to the DTO. |
| 31 | Hand-listing the fields of each hashed input (§2.7) | **THE HABIT, NOT JUST THE INSTANCE** | Rev. 5 hand-listed inputs and missed eight; Rev. 6 hand-listed preset fields and missed `items`; entries 27-30 are all enumeration misses. The serialiser now enumerates `dataclasses.fields()` and **raises** on a field this spec does not name, so the next added field breaks the hash loudly instead of silently weakening it (§2.7). |
| 32 | `persistent_unstarted` for team preview; `backend_state` in the `spawn_count_before` field note; "only these two values are permitted" for `timer_scope`; `persistent_restarted` in §2.4's attempts note | **STALE AFTER 27-29** | Swept: team preview now falls to `contaminated` by the predicate and stays excluded by the existing `state is not None` gate (`gauntlet.py:526-527`); the field note points at `backend_class`; `timer_scope` lists three values; §2.4 says "a retried row". |

### Rev. 7 → Rev. 8

| # | Rev. 7 claim | verdict | why |
|---|---|---|---|
| 33 | "`items` is sorted because it is a set-like membership list, **not an ordered preference**" (§2.7) | **FALSE — the config says the opposite, in one explicit line** | `showdown_bot/config/formats/meta/default_spreads.yaml:12`: *"items: candidate held items (**first is the default assumption**)"*. Production takes that first element on two independent paths: `hypotheses.py:109` (`item = preset.items[0]` — the opponent's assumed item) and `team/spreads.py:91` (`mon.item, mon.item_known = items[0], True` — our own). Real data makes it concrete: `default_spreads.yaml:18` is `[Life Orb, Choice Specs, Focus Sash]`; sorted, the assumed item becomes **Choice Specs**, a different item with different damage — and for a Scarf-bearing list, a different speed and branch count. **Rev. 7 fixed Rev. 6's omission of `items` and reintroduced the identical defect one level down: two different fixtures, one hash.** I asserted this field's semantics without reading the config that defines it. |
| 34 | `our_spreads`/`opp_sets`/`book` serialised as `{species: <SpreadPreset>}` (§2.7) | **WRONG TYPE — and it collapses two behaviour-relevant branches** | They hold **`SpeciesSpreads`** (`offense` + `defense`, `hypotheses.py:27-33`), verified in the fixture: `SpeciesSpreads(offense=SpreadPreset("Jolly", …), defense=SpreadPreset("Impish", …))` → `SpreadBook(default=spreads)` → `our_spreads = {"aerodactyl": spreads, …}` (`tests/conftest.py:198-205`). Both branches are read on different paths: `offense` by `speed_for_species` → `_base_speed(…, preset.offense.nature, preset.offense.evs)` (`engine/speed.py:176`) for Mega speed; `defense` by `team/spreads.py:89-91` for **our own item truth** and by `battle/opponent.py:227-229` for the **opponent's assumed Scarf speed**. A collapsed DTO maps branch-swapped fixtures onto one hash. The evidence was in a line I had already read this session — `preset.offense.nature` — and I did not notice the leaf was not a `SpreadPreset`. |
| 35 | `legal_actions` serialised **sorted** (§2.7) | **DESTROYS A BINDING ORDER THAT A PRIOR REVIEW ALREADY BLOCKED ON** | Enumeration order **is** the first-wins tie-break, and `battle/mega_scoring.py:184-198` states it and names the review: *"Callers … MUST iterate this list, never reconstruct an order … breaks first-wins tie-break semantics (Codex I7a-B merge-blocker: a tie between `A+Mega` and `B` must resolve to `A+Mega` because it is enumerated immediately after `A`, before `B`)"*. Two enumerations with equal membership and different order choose **different actions**; sorting maps them to one hash. |
| 36 | "a field this spec does not name must raise" (§2.7) | **UNENFORCEABLE AS WRITTEN (P2)** | Rev. 7 demanded a raise on unknown dataclass fields but named expected field sets for none of `BattleState`, `PokemonState`, `FieldState`, `SpeciesSpreads`, `SpreadBook`, `CalcProfile`. Of the two ways out, **"all fields, recursively" is adopted** — the alternative asks for exactly the hand-listing that produced entries 27-31 and 33-35. `encode()` now recurses over `dataclasses.fields()` with no field list anywhere, and fails closed on an unhandled **type**. The type closure was enumerated and verified: only `str`, `int`, `bool`, `str \| None`, `int \| None`, `set[str]`, `list[str]`, `dict[str, …]` and nested dataclasses occur. |
| 37 | "canonicalise by sorting" applied per field, by hand (§2.7) | **THE REFLEX BEHIND 33, 35 — AND IT HAD A THIRD TARGET** | Entries 33 and 35 are one habit, not two mistakes: sorting was applied without asking whether order carries meaning. `PokemonState.types: list[str]` was next in line. Replaced by a rule derived from the source types: **sort only what has no order** — `set` sorted (no order exists), `list`/`tuple` order preserved, `dict` key-sorted (keyed lookups), dataclass fields name-sorted. `moves`/`move_names` stay sorted **because they are genuinely `set[str]`** (`engine/state.py:66-67`), not because sorting is canonical. The asymmetry justifies it: for a fixture **identity**, over-discrimination costs a comparison; under-discrimination corrupts every claim built on it. |
| 38 | `sha1(canonical_json(manifest))` for the profile manifest (§2.7) | **UNDEFINED SERIALISER — the exact charge F-15 makes** | Latent rather than live (the manifest is plain scalars and strings), but a spec that calls "canonical_json" unspecifiable in F-15 and then uses it one page later is inconsistent. Pointed at the same `encode()`. |

### Rev. 8 → Rev. 9

| # | Rev. 8 claim | verdict | why |
|---|---|---|---|
| 39 | `request` = "the raw request payload dict, as parsed" (§2.7) | **THE INPUT IS UNREACHABLE — the manifest producer cannot obtain it** | `_mega_req()` (`tests/conftest.py:112-157`) builds a dict *literal* inline and passes it straight into `BattleRequest.model_validate({...})` at `:126`. The dict is never bound and never returned; `_build_mega_decision_kw` gets only the model. Rev. 8 specified an input that does not exist as an object. Of the two fixes, the pinned `model_dump` is adopted **on the merits, not as a fallback**: `score_evaluated_variants` receives the model, and `BattleRequest.model_config` leaves `extra` unset → pydantic's `ignore` — **verified empirically** (a payload with `bogusExtraKey` validates to a model whose dump lacks it). Keys the model drops cannot affect behaviour, so two payloads validating to one model are behaviourally identical and *should* share a hash; hashing the payload would over-discriminate on provably irrelevant keys. The dump's options are pinned because `by_alias` demonstrably changes the keys (`forceSwitch` vs `force_switch`). **No missing interface is needed.** |
| 40 | "`request` … passes through the same encoder" (§2.7) | **THE ENCODER HAD NO BRANCH FOR IT** | `BattleRequest` is a pydantic `BaseModel` (2.13.4), not a dataclass, so Rev. 8's `encode()` would have hit `anything else → raise TypeError` on the one input it named as passing through. Fail-closed rather than wrong — but a specified path that cannot run is still a defect, and Rev. 8 asserted the closure was verified while omitting this half of it. Added the `BaseModel` branch; verified that `model_dump` over the real fixture yields only plain types, and that two independent builds dump byte-identically. |
| 41 | `apply_packed_team_items` (§2.7) | **INVENTED SYMBOL — it does not exist** | `grep` finds no such name anywhere in the tree. The real path is `apply_own_team_knowledge` (`team/spreads.py:55`), whose packed-team fallback reads `spreads.defense.items` (`:89`) and assigns `items[0]` (`:91`). I fabricated a plausible-sounding name for a function I had already read, in the same entry where I criticised asserting a field's semantics without reading its source. |
| 42 | The opponent Scarf anchor `battle/opponent.py:227-229` (§2.7) | **POINTS AT A DOCSTRING, NOT THE CODE** | `:227-229` is `def _item_for_speed` plus its docstring. The selection is at `:234` (`return curated_items[0] if curated_items else None`); the `defense` branch is bound at `:252` (`preset = preset_spreads.defense`) and its items are passed at `:254` (`_item_for_speed(mon, preset.items)`). The claim was right; the citation did not support it. |

### Rev. 9 → Rev. 10

| # | Rev. 9 claim | verdict | why |
|---|---|---|---|
| 43 | `cache_class` is "**declared** by the arm's `lifecycle` and cross-checked against observed batch counts" (§2.8) | **DECLARED AND BOUND TO NOTHING — the contrast the slice exists to protect was unguarded** | The validator (§2.4) had no `cache_class` rule at all, so a row could report `cache_class="cold"` while its arm declared `damage_oracle/speed_oracle/species_dex = "per_arm"` and still pass every invariant. And the named cross-check does not work **in either direction**: `DamageOracle._cache` is keyed by semantic payload, so a *reused* oracle facing all-new keys issues full batches and looks cold, while a *fresh* oracle on a board needing no damage issues none and looks warm. Batch count measures key novelty, not object identity. Fixed by the move that made `backend_class` sound: raw observed facts (`len()` of each cache at **rep start** — before context construction, which legitimately warms `_spe_cache` pre-timer) plus a validator that recomputes the label from the manifest and lets the facts contradict it. |
| 44 | Only the label was at issue | **THE SOUND DIRECTION IS ONE-WAY, AND SAYING SO IS PART OF THE FIX** | `cold ⇒ all three sizes == 0` is **provable**: every one of the three caches is set to `{}` in `__init__` (`oracle.py:24`, `speed.py:103`, `opponent.py:45`), so a non-empty cache at rep start disproves the declared lifecycle — this catches a **harness** bug that reuses an object the manifest said was fresh, which plain manifest-equality cannot. The converse `warm ⇒ sizes > 0` is **unsound** and is deliberately not asserted: a reused `SpeciesDex` on a board whose species were never looked up is legitimately empty. Rev. 5 shipped precisely that over-strict mistake for `backend_state` and would have rejected a real, successful row (entry 23); this revision does not repeat it. |
| 45 | §2.5's `source`/`timer_scope` table (§2.5) | **A CONTRACT WRITTEN AS DOCUMENTATION** | The table restricts `agent_choose` to live rows and the two narrower scopes to microprofile rows, but the validator enforced neither. A live row at `score_evaluated_variants`, or a microprofile row at `agent_choose`, would have validated — and pooling it compares an end-to-end ms with a sub-call ms. Now enforced as a biconditional in both directions. |
| 46 | Per-object `lifecycle` with no coherence constraint (§2.8) | **`expected_cache_class` WOULD NOT HAVE BEEN TOTAL** | Rev. 9 let each object declare its own lifecycle, so a mixed arm (`damage_oracle` `per_arm`, `speed_oracle` `per_rep`) has no defined `cache_class`. Rather than add a `mixed` class — the reflex that produced entries 27-30 — the three semantic caches are now **required to share one lifecycle**, invalid at load otherwise. This forbids nothing legitimate: both coherent configurations already declare them identically. `calc_backend` and `contexts_and_variants` stay independent, as the warm-cache configuration requires. |
| 47 | `per_arm` backend "reports `spawn_calls > 0` on rep 5 … the arm's rows are void" (§2.8) | **THE SAME DEFECT AS 43, ONE PROPERTY OVER — and unflagged** | Found by sweeping for the *class* rather than fixing only the two instances reported. §2.8's backend-lifecycle cross-check was declared in prose and bound to nothing, exactly like `cache_class`. Now a per-row rule: `calc_backend_lifecycle == "per_arm" and (rep > 1 or warmup >= 1)` ⇒ `spawn_calls == 0`, asserted in the sound direction only (a live, once-constructed process cannot re-spawn; the converse is false, since a rep may use no calc at all). |
| 48 | "identical `fixture_input_hash` with differing `n_candidates` is a contract violation" (§2.7) | **DECLARED WITH NO POSSIBLE OWNER** | It compares two rows, so `validate_decision_profile_row` **structurally cannot** enforce it — Rev. 9 wrote it as a contract and assigned it to nobody. The root cause behind 43, 45, 47 and this one is one thing: the spec never said *which* validator owns which invariant, so "declared" quietly meant "unenforced". Fixed generally rather than per-instance — §2.4 now names **three enforcement tiers** (per-row / dataset-level / cross-artifact), every invariant belongs to exactly one, and an invariant with no tier is stated to be **unenforced and not to be relied on**. This invariant is dataset-level; the trace-v3 latency agreement is now explicitly *available, not enforced*, instead of implying a guarantee it never had. |

### Rev. 10 → Rev. 11

| # | Rev. 10 claim | verdict | why |
|---|---|---|---|
| 49 | The three `cache_class` rules, written unqualified in the per-row validator (§2.4) | **NO LIVE ROW COULD SATISFY THEM** | The cache contract is defined against an **arm's** declared `lifecycle`, but a live row has `arm_id`/`rep`/`profile_manifest_hash` = `null` by the validator's own identity rule, and Rev. 10 declared the three cache sizes `null` for live. So `cache_class == expected_cache_class(arm, rep)` had no `arm` to resolve, and `cache_class == "cold" ⇒ sizes == 0` compared `null` against `0`. Every live row failed a contract written for microprofile rows. Fixed by scoping: `cache_class` and the three sizes are **`null` for live**, and all three rules are gated on `source == "microprofile"`. Live decisions do share oracles per battle (`gauntlet.py:433-480`), so a live cold/warm question exists — but against a different, undeclared lifecycle, and this slice does not answer it. |
| 50 | `expected_cache_class` branching on `rep > 1` / `rep == 1`, asserted **"total over its domain … splits exhaustively"** (§2.8) | **NOT TOTAL, AND WRONG WHERE IT DID MATCH — `rep` is 0-based** | §2.4 defines `rep` as the "0-based repetition index within the arm". For a `per_arm`, `warmup == 0` arm: **rep 0** — the first timed rep, genuinely cold — matched **no branch at all**; **rep 1** — the second, genuinely warm — fell into the `rep == 1` branch and was labelled **"cold"**. Two defects from one off-by-one, in the same paragraph that claimed exhaustiveness. The third branch is now a **residual (`otherwise`)** — total by construction — and `cache_class == "warm" ⇒ rep >= 1`, not `> 1`. Rev. 10 cited §5.5's residual lesson in entry 46 and then wrote a three-condition enumeration anyway. |
| 51 | `calc_backend_lifecycle == "per_arm" and (rep > 1 or warmup >= 1) ⇒ spawn_calls == 0` as a **per-row** rule (§2.8, entry 47) | **UNSOUND — REJECTS A REAL, SUCCESSFUL ROW. This supersedes entry 47's fix.** | Its own justification named the flaw: *"a process constructed once **and still alive** cannot spawn again"*. `per_arm` declares the **object** is reused, not that the OS process survives — `_ensure` (`client.py:176-180`) revives one that died between reps **before the first attempt**, no failure, no retry: `spawn_calls == 1`, correct result, rule fails it. **This is entry 23 verbatim**, and Rev. 10 committed it one bullet *after* citing entry 23 as the mistake it was avoiding (entry 44). Citing a lesson is not learning it. It was also **redundant**: §5.5's `contaminated` residual already excludes a respawn from the contrast without rejecting the row — the tell that it was the wrong mechanism. And no sound per-row replacement exists: `per_arm and rep >= 1 ⇒ spawn_count_before >= 1` also fails, because a rep that used no calc never starts the process. Moved to **dataset-level**, where §2.8's original words ("the **arm's** rows are void") always said it belonged: compare each arm's observed `backend_class` distribution against its declared lifecycle. Rev. 10 read an arm-level verdict as a row-level rejection. |
| 52 | "**dataset-level** — run once over a finished sidecar" (§2.4) | **A TIER WITH NO ENFORCEMENT — the defect the tiers existed to fix** | Rev. 10 named the tier and listed invariants for it, but gave it no owner, no trigger and no consequence. That is precisely "declared, bound to nothing" (entries 43-48) reproduced at the level of the fix for it. Now concrete: `validate_decision_profile_dataset(path, manifest)`, run once when the profile run finishes and before any row is read as evidence, **failing the run** rather than annotating it. The cross-artifact tier is explicitly enforced by **nobody** and closed to new entries, so it cannot quietly become the same hiding place. |
| 53 | Field types: the three `*_cache_size_at_rep_start` declared `int` while the prose said `null` for live (§2.4); the lifecycle table's `calc_backend` row and its "reps 2..N"/"after rep 1" prose (§2.8) | **STALE AFTER 49-51** | Swept: the three sizes are `int \| null`; the `calc_backend` row no longer claims `spawn_calls == 0` after the first rep (a respawn is legitimate — 51) and states the reuse invariant as `spawn_count_before >= 1` instead; and the 1-based colloquialisms that produced 50 are gone in favour of "the first rep". |

### Erratum 1 — Rev. 11 contradicted itself about `warmup`

Not a revision: no claim is withdrawn and no gate moves. Rev. 11 stated one quantity two ways, and
the implementation could not satisfy both.

| # | Rev. 11 as shipped | verdict | why |
|---|---|---|---|
| E1 | §2.7's manifest table: `\| warmup \| run \| stated once …` | **CONTRADICTS FOUR OTHER PLACES IN THE SAME DOCUMENT** | §2.8 ("**Warmup** is declared per arm"), §2.4's validator rule (`arm.warmup`), §2.4's `cache_class == "warm" ⇒ rep >= 1 or arm.warmup >= 1`, and §5.4's `expected_cache_class` (`arm.warmup == 0`) all read it per-arm. §9 entry 24 shows the origin: Rev. 5 pinned a run-level warmup, Rev. 6 moved the lifecycle per-arm and declared warmup per-arm in §2.8 — and this table row was never updated. Per-arm is also the only coherent reading, since §2.8 calls a warming-up cold-cache arm a contradiction and a run-level value would force one on every such arm. Corrected: `warmup` moves to the arm entry, a top-level `warmup` is **rejected** so the two readings cannot coexist, and the arm entry states the coherence rule (`per_rep` caches ⇒ `warmup == 0`). |
| E2 | `arms[]` left implicit enough that an implementation read it as a mapping keyed by `arm_id` | **A MAPPING DEFEATS A FAIL-CLOSED CHECK THE SLICE REQUIRES** | The design says "one entry per arm" and gives each entry an `arm_id` **field**, which is redundant in a mapping — the tell that a list was meant. It matters beyond style: a mapping **cannot represent** a duplicate `arm_id`, so the duplicate disappears at construction and the frozen manifest can never be re-checked for it. That contradicts the principle the dataset tier already rests on — frozen evidence must not blindly trust the writer. Stated explicitly as a LIST, validated in full before any lookup index is built. |

### Erratum 2 — §2.5's "narrow scope contains the spawn? no" was too strong

Not a revision: no claim is withdrawn, no gate moves, no arm changes. Found while building the C3
harness against the real scoring path.

| # | as shipped | verdict | why |
|---|---|---|---|
| E3 | §2.5's `score_evaluated_variants` row: "contains the spawn? **no** — context construction has already spawned the shared backend (§2.8)" | **TRUE FOR THE ARMS §2.8 REASONED ABOUT, BUT NOT UNIVERSAL** | The "no" was derived on a board where context construction *does* spawn the shared backend (an own-Mega projection calls `speed_for_species` → `stats_batch` → spawn, §2.8's call chain), so the process is already alive when the narrow window opens. That is not guaranteed. **Arm 7** (foe-Mega with **no** own Mega) has no own projection, so context construction spawns **nothing** (measured: `spawn_count` 0→0 across `build_own_mega_contexts`); its first spawn is the damage batch *inside* `score_evaluated_variants`. So `clean_cold` **is** reachable at the narrow scope for that arm. The precise statement: the narrow scope **excludes context construction** from the window; it does **not** assert `score()` performs no spawn. This changes nothing operationally — the branch-cost arms stay at the narrow scope, arm 13b (the spawn-cost arm) is measured at `contexts_and_score` regardless, and `backend_class` is still recomputed per row from its own facts — but the one-word "no" would mislead a reader into thinking a narrow-scope row can never be `clean_cold`. |

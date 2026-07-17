# Champions I8 — Active Foe-Mega Latency Profile: Implementation Plan

**Status:** `I8-A COMPLETE · I8-B COMPLETE · NO LIVE WIRING · NO LIVE RUN`

I8-A landed as `b87d5a6` — counters on both calc backends, the planned/implicit batch split, and
the cache-size characterization. I8-B follows it: the sidecar, both validator tiers, and the one
canonical encoder. **Nothing imports the profile module yet** — there is no live wiring, and none
is authorized here. **No run of any kind is authorized by this plan** — not a smoke, not a server,
not a battle. I8-C's microprofile and I8-D's live run each need their own.

**I8-B, as built.** Four review findings landed against it first:

| finding | what it was |
|---|---|
| the field set was 39, must be **41** | the design declares `config_id`, `format_id` and `git_sha` on **one** table row; a parse taking the first backticked name per row dropped two mandatory fields — **and the drift guard used the same parser**, so it certified the wrong set |
| the manifest was **self-referential** | it stored `profile_manifest_hash` inside itself. A document carrying a digest of itself cannot be hashed: the field is an input to the digest that depends on it. The hash is now **computed** from content |
| semantically invalid rows **passed** | `schema_version`, the `outcome` enum, `calc_backend`, bool/float types and non-empty provenance were unvalidated. Structural completeness is not validity |
| the sink path was **unclassified** | `config_env.is_excluded` fails closed toward **inclusion**, so `SHOWDOWN_DECISION_PROFILE_OUT` would have entered `behavior_env` and `config_hash` — enabling a measurement sidecar would have changed the identity of the run being measured |

The last has a second half worth stating: the drift scanner that exists to catch it matches only a
**string literal at an `os.environ.get` call site**, and `env.get(PROFILE_OUT_ENV, …)` dodged it on
both counts — a constant instead of a literal, an injected mapping instead of `os.environ`. The var
was registered **and** the scanner widened, so the next constant-named var cannot hide the same way.

**Mutation testing then caught two vacuous tests of this slice's own.** Weakening the `outcome`
enum to `is not None` left all 83 tests green: the test's rows were rejected by the
`outcome ⇔ measured_ms` rule, never by the enum it named. The `cache_class` enum was worse — **dead
code**, since `expected_cache_class` returns only `"cold"`/`"warm"` and the equality rule already
constrains the domain; no test could distinguish its presence from its absence, so it was removed
rather than left implying a guard that never fires. Both are now pinned with `match=`, which is
what made them visible. The same technique showed the design's `warm ⇒ rep>=1 or warmup>=1` rule is
a **backstop** against `expected_cache_class` itself being wrong rather than an independently
reachable rule, and it is now tested as one.

**Approved design:** `docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md` (Rev. 11,
`APPROVED — implementation planning allowed; no run authorized`, committed `12b19c2`). The design
is the contract; this plan sequences its construction and **adds no design decisions**. Where this
plan needs a value the design does not pin, it raises it as an explicit decision (D-2) rather than
choosing one silently.

**Goal:** build the instrumentation, sidecar, validators and microprofile that the design
specifies, then run a live measurement dimensioned to D-1's exposure floor — producing `PASS`,
`FAIL` or `INCONCLUSIVE` against the existing 1000 ms budget, and nothing else.

**Method — binding: strict TDD for every task that adds code.** Each such task is
**RED → GREEN**: the failing test is written and *seen to fail for the stated reason* before any
implementation exists. The RED blocks below are the actual tests, not sketches. A task whose test
passes on first run is a **stop condition**, not a success.

**Correction, found by that stop condition firing on A3.** The rule as first written said "every
task", which is wrong for a task that adds **no code**. A3 exposes nothing: the three caches
already exist and `len()` already works, so there is no implementation and therefore no RED. Its
tests are **characterization tests** — they pin facts the design *depends on* rather than drive
new behaviour.

That is not a licence to wave a green test through. When the stop condition fires, the obligation
is to **prove the test binds**, and the proof is mutation, not argument:

| mutation | caught by |
|---|---|
| a freshly constructed `DamageOracle._cache` is pre-populated | `test_a_freshly_constructed_cache_is_empty[damage]` |
| `SpeedOracle._spe_cache` renamed | 4 tests, incl. the name-contract test |

Both mutations were applied to the real source, seen to fail, and reverted (`speed.py` byte-identical
to HEAD afterwards). A characterization test that survives mutation binds; one that does not is the
defect the stop condition is looking for.

**No run is authorized by this plan.** Every gate below is satisfiable **offline** — by unit tests
and by the already-committed frozen artifacts. Any step needing a live battle is called out
explicitly and needs its own authorization (§4.1, §5).

---

## 0. The exposure reality — measured, not assumed

Everything in §4 follows from this. It is measured from the frozen smoke
(`data/eval/champions-panel-v0/smoke-i7b-mega/`), which is the **only live foe-Mega evidence that
exists**:

| fact | value |
|---|---|
| battles | 2 |
| decisions in `decision_trace.jsonl` | 19 |
| scored decisions (`opp_mega_trace.jsonl`) | 17 — team preview excluded, matching the `state is not None` gate |
| **active** foe-Mega decisions | **1** (battle `…0c3ec6d0e79c`, decision 4, slot 1) |
| active rate | **1/17 = 5.88 % of scored decisions** |
| scored decisions per battle | 8.5 |
| **active decisions per battle** | **0.5** |

**A row is active iff `foe_mega_slots` contains a non-`None` entry** — the list is per-response and
is non-empty on every row, so "list non-empty" is *not* the predicate. (This plan's first draft got
that wrong and read 17/17; the correct filter reproduces the design's §0.1 figure of 1/17.)

**The point estimate is one active decision.** Its Wilson 95 % interval is **[1.0 %, 27.0 %]** — a
~26× span. What that implies for reaching D-1's 60 active decisions:

| rate | scored decisions needed | ≈ battles needed |
|---|---|---|
| CI low, 1.0 % | ~5 700 | ~675 |
| **point estimate, 5.9 %** | **~1 020** | **~120** |
| CI high, 27.0 % | ~220 | ~26 |

**Why exposure cannot be bought more cheaply — checked, not assumed:**

- **Not a panel-composition problem.** All five panel teams already carry a Mega stone
  (`Lucarionite`, `Delphoxite`, `Meganiumite`, `Froslassite`, `Tyranitarite`). Stratifying the panel
  toward "opponents that can Mega" gains **nothing**; it is already 100 %.
- **Not an `opp_sets` coverage gap.** `foe_mega_eligibility` (`battle/opponent.py:151-196`) resolves
  a slot via a revealed item **or** a curated `opp_sets` preset, and `opp_sets` comes from
  `likely_sets` (`engine/belief/hypotheses.py:190-211`). The Champions `likely_sets.yaml` lists a
  stone for **every** panel Mega species. There is no missing entry to add.
- **It is structural.** A slot is eligible only while the Mega-capable mon is *active* (`a`/`b`, not
  fainted) **and** the foe has not yet spent its Mega (`opponent.py:174-179`). Once the opponent
  Megas, eligibility returns `{}` for the rest of the battle. That window is narrow, and nothing in
  a *measurement* slice may widen it.

**The one lever that would raise exposure is forbidden here.** Curating more Mega items into
`opp_sets`, or changing the click rate, changes **eligibility → twins → scoring → behaviour**. It is
BEHAVIOR_AFFECTING and would change the very thing being measured. I8 is measurement-only (design
§6). Exposure is therefore bought only with battles.

**Consequence, stated up front:** `INCONCLUSIVE` is a realistic outcome of a correctly executed
run, not a failure of it. The plan is built so that outcome costs a bounded amount and produces
usable exposure data either way.

---

## 1. Mandatory execution order

Instrumentation, sidecar, validators and microprofile land and are **tested** before the live
harness exists. This is not tidiness: the live run is the expensive, hard-to-repeat artifact, and
every one of its rows is produced by machinery that must already be proven.

```
I8-A  instrumentation          (counters + cache sizes; no consumer yet)
   ↓
I8-B  sidecar + validators     (per-row + dataset; both tiers, both tested)
   ↓
I8-C  microprofile harness     (manifest, fixture hash, arms) — exercises A and B end-to-end
   ↓                             on fixtures, with no server and no battle
I8-D  live harness + run       (schedule, stop rule, verdict) — LAST, and its run is
                                 separately authorized
```

**Cross-slice stop gates:**

- **A → B**: no counter may be read by anything until every counter has a test that pins it against
  a *known* transport count.
- **B → C**: the dataset validator must **fail a deliberately corrupted sidecar** before the
  microprofile is allowed to write one.
- **C → D**: the microprofile must produce a green run whose rows pass both validator tiers, and
  D-2 (§4.1) must be approved. **No live harness work starts before that.**
- **D → run**: the run itself needs its own explicit authorization. This plan does not carry it.

---

## 2. I8-A — Instrumentation

The design's P-6…P-10 record what does not exist. Nothing here changes a decision, a score or a
byte of existing output; every task is additive and off by default.

### Task A1 — per-method transport counters **and `spawn_calls`** on both backends

`SubprocessCalcBackend` and `PersistentCalcBackend` gain `damage_batch_calls`,
`stats_batch_calls`, `types_batch_calls` (logical), `transport_attempts` (physical) **and
`spawn_calls`**.

**`spawn_calls` is not optional and does not exist today — least of all on the oneshot backend.**
The design's validator requires `calc_backend == "oneshot" ⇒ spawn_calls == transport_attempts`,
and `backend_class` is a predicate over `(spawn_count_before, spawn_calls, transport_retried)`.
But:

- `spawn_count` exists **only** on `PersistentCalcBackend` (`client.py:194`, incremented in
  `_spawn` at `:199`);
- `SubprocessCalcBackend` (`client.py:36`) has **no spawn counter at all**, while spawning a fresh
  Node process on **every** batch — at **two distinct sites**: `calc_batch` directly
  (`client.py:74`) and `_run` (`client.py:109`), which serves both `stats_batch` (`:133`) and
  `types_batch` (`:144`).

So the oneshot backend must gain a spawn counter incremented at **both** spawn sites; counting
only one would silently under-report exactly the spawn-dominated cost this slice exists to measure.

**The backend counters are CUMULATIVE, and the row's are per-decision deltas (found while
implementing A1; binding on I8-B).** The design's row field `spawn_calls` is a *per-decision*
delta, but a backend has no concept of a "decision" and must not acquire one. More decisively:
the row's `spawn_count_before` is **defined** as "the backend's cumulative spawn count before this
decision" — which is computable **only** from a cumulative counter. So:

| level | counter | semantics | owner |
|---|---|---|---|
| backend | `spawn_count`, `transport_attempts`, `damage_batch_calls`, `stats_batch_calls`, `types_batch_calls` | **cumulative since construction** — the semantics `PersistentCalcBackend.spawn_count` already had (`client.py:194`) | **A1** |
| row | `spawn_count_before`, `spawn_calls`, and the per-decision counters | **deltas**, from a before/after snapshot around the decision | **I8-B**, not A1 |

Naming a *backend* attribute `spawn_calls` would have quietly conflated the two and left
`spawn_count_before` uncomputable. A1 therefore adds `spawn_count` to the oneshot backend — the
same name and semantics the persistent one already uses — and B derives every delta.

- Counters increment **only on a non-empty request list**, above the existing empty-guards
  (`client.py:62-63`, `:135-136`, `:146-147`; `:312-313`, `:322-323`, `:333-334`).
- `transport_attempts` increments in `_run_once`, so `_run`'s retry path (`client.py:272-273`)
  records **two** attempts for one logical call.

**RED — write these first; each must fail before any counter exists:**

**LANDED** — `showdown_bot/tests/test_calc_counters.py`, 17 tests. RED first (17 failures, every
one an `AttributeError` for a missing counter — the stated reason), then GREEN:

```python
def test_oneshot_spawn_count_counts_every_process_including_the_run_helper():
    # Two spawn sites: calc_batch's own subprocess.run (client.py:58) and the shared
    # _run helper (client.py:88) serving BOTH stats_batch and types_batch.
    backend = SubprocessCalcBackend()
    backend.calc_batch([_req()])              # site 1
    backend.stats_batch([_spec()], gen=9)     # site 2 via _run
    backend.types_batch(["Incineroar"])       # site 2 again
    assert backend.spawn_count == 3
    assert backend.spawn_count == backend.transport_attempts   # the oneshot invariant

def test_oneshot_empty_list_spawns_nothing_and_counts_nothing():
    # The counters must sit BELOW the existing empty-guards, not above them.
    backend = SubprocessCalcBackend()
    backend.calc_batch([]); backend.stats_batch([], gen=9); backend.types_batch([])
    assert (backend.spawn_count, backend.transport_attempts) == (0, 0)

def test_persistent_one_logical_call_can_be_two_physical_attempts(monkeypatch):
    # _run retries once on _TransportError (client.py:242-243). transport_attempts is
    # incremented in _run_once, so a retried call reports 2 attempts for 1 logical call.
    ...
    assert backend.damage_batch_calls == 1        # logical
    assert backend.transport_attempts == 2        # physical
```

### Task A2 — planned vs implicit damage batches
`DamageOracle` distinguishes the explicit `mega_scoring.py:625-626` flush from an
`oracle.get`-triggered one (`oracle.py:92-102`). **Measured at origin, never by subtraction** — the
design's §2.4 records why `delta − planned` is invalid (an empty flush early-returns before
incrementing, `oracle.py:59-60`, so the arithmetic can yield −1).

**LANDED** — `showdown_bot/tests/test_oracle_batch_origin.py`, 8 tests. RED first (8 failures,
all `AttributeError` on the missing counters), then GREEN.

The split is made at the only place the distinction still exists: `flush()` stays the public
entry point and is **planned by definition**; it delegates to `_flush(planned=...)`, and `get()`'s
auto-flush passes `planned=False`. The public signature is unchanged, so **no call site moves** —
which is what keeps this task additive.

```python
def test_planned_and_implicit_are_counted_at_origin_not_by_subtraction():
    oracle = DamageOracle(_FakeClient())
    oracle.request(_req("Moonblast")); oracle.flush()      # planned
    key2 = oracle.request(_req("Dazzling Gleam")); oracle.get(key2)   # implicit
    assert (oracle.planned_damage_batches, oracle.implicit_damage_batches) == (1, 1)
    assert oracle.batch_calls == oracle.planned_damage_batches + oracle.implicit_damage_batches

def test_an_empty_flush_moves_no_counter():
    # The early return sits ABOVE every counter (oracle.py:59-60), which is exactly why
    # `implicit = batch_calls_delta - planned` is invalid: it would score this -1.
    oracle = DamageOracle(_FakeClient())
    oracle.flush(); oracle.flush()
    assert (oracle.batch_calls, oracle.planned_damage_batches, oracle.implicit_damage_batches) == (0, 0, 0)

def test_the_split_always_accounts_for_every_batch():
    ...
    assert len(client.batches) == oracle.batch_calls   # counters match REAL round trips
```

`damage()` (request + get) counts **implicit**, and that is correct rather than a quirk: it
prefetched nothing and resolved on demand, which is what the implicit counter means.

**A2 near-miss — the call graph is part of the contract (recorded because no test run would
have caught it).** The first cut split the flush by routing `get` to a private
`_flush(planned=False)`. That silently **blinded two existing guards**:

| guard | what it forbids | what the private route did to it |
|---|---|---|
| `tests/i7b/test_i7b_scoring.py:340-355` — "exactly one flush" | prefetch misses in the three-phase scoring contract | spies by patching `flush` on the instance; a miss routed to `_flush` is invisible, so the count stays 1 and the test **passes while violated** |
| `tests/test_baselines.py:290-319` — single expand/filter/context pass and single flush | the same, for `max_damage` | identical |

Both kept passing, because these fixtures happen to have no misses — so the suite was green,
the guards were dead, and **a full-suite run could never have revealed it.** Only reading the
diff against the call graph did.

The fix keeps `get` calling the **public** `flush`, unchanged from before I8-A, and adds a flag
that tells `flush` how to attribute the batch without ever rerouting the call. A new guard pins
it — `test_get_still_calls_the_PUBLIC_flush_so_prefetch_spies_stay_alive` — and it was verified by
mutation: reintroducing the bypass (`DamageOracle.flush(self)`) makes it fail, and reverting makes
it pass.

**Binding on every later slice: an instrumentation change may add bookkeeping to a call, never
move the call.** The observability of a defect is itself a contract.

**A2 second defect — the counters counted successes, not attempts (review finding; the suite
could not have caught it either).** The increments sat *after* `client.damage_batch(reqs)`, so a
batch that **raised** counted nothing — even though the round trip was made and paid latency.
That contradicted A1 one layer down, where `damage_batch_calls` and `transport_attempts`
deliberately increment **before** their call so a failure still counts:

| layer | on a failed damage batch | |
|---|---|---|
| backend (`client.py:64`) | `damage_batch_calls == 1` | counts the attempt |
| oracle (before the fix) | `planned + implicit == 0` | counted only successes |

So the row's invariant `damage_batch_calls == planned + implicit` **broke on every transport
error** — precisely the row a reader reaches for, since design §2.6 keeps a non-ok row's counters
*because* they describe transport that really happened. No A2 test sent an error through the
oracle path, so the full suite would have stayed green.

**Fix (as directed):** `batch_calls` is now defined as a logical **attempt**, and it and the
origin increment together immediately **before** `client.damage_batch()`, so the equality holds on
the error path by construction. Safe to redefine: no production code reads `oracle.batch_calls`
(grep-confirmed — the design's "both are unread" holds), and the tests that read it only exercise
success paths, where attempt == success.

**Four counter-proofs, all verified by mutation** (reverting to count-successes fails exactly
these four, restoring passes):

- `test_a_planned_batch_that_raises_is_still_counted`
- `test_an_implicit_batch_that_raises_is_still_counted`
- `test_a_failed_implicit_batch_does_not_leak_the_origin_flag` — a leaked flag would misattribute
  every later planned batch as implicit, turning the prefetch-miss counter into noise for the rest
  of the decision
- `test_oracle_and_backend_agree_on_the_error_path` — the invariant spans **two layers**, so the
  proof must too: backend and oracle must agree on a failed batch

**A1 re-checked against the same defect: sound.** Every `*_batch_calls` already increments before
its call (`client.py:64`, `:137`, `:148`, `:314`, `:324`, `:335`), and `transport_attempts` is the
first line of `_run_once` (`:285`). The one asymmetry is deliberate and correct: `_spawn` counts
**after** `Popen` (`:229`) because a raising `Popen` means no process exists, while the oneshot
counts **before** `subprocess.run` because a timeout means it *did* spawn.

### Task A3 — cache sizes readable at rep start

Expose `len()` over the three caches: `DamageOracle._cache` (`oracle.py:24`),
`SpeedOracle._spe_cache` (`speed.py:103`), `SpeciesDex._cache` (`opponent.py:45`).

**Scope correction (this plan's own error).** An earlier draft said "the backend's existing
`spawn_count` … all four attributes already exist and are already reachable". **That is false.**
Only the three *caches* already exist. `spawn_count` exists on `PersistentCalcBackend` alone; the
oneshot backend has no spawn counter, which is why spawn counting is **new work in A1**, not a read
here. A3 covers the caches only.

**RED:**

```python
@pytest.mark.parametrize("make, probe", [
    (lambda: DamageOracle(), lambda o: len(o._cache)),
    (lambda: SpeedOracle(stats_backend=SubprocessCalcBackend()), lambda o: len(o._spe_cache)),
    (lambda: SpeciesDex(SubprocessCalcBackend()), lambda o: len(o._cache)),
])
def test_a_freshly_constructed_cache_is_empty(make, probe):
    # The empirical basis for the design's ONLY sound cache direction
    # (cold => all three sizes == 0). Pinned by test, never by inspection.
    assert probe(make()) == 0
```

**LANDED as characterization, not TDD** — `showdown_bot/tests/test_cache_sizes.py`, 7 tests,
green on first run. **No implementation, because there is nothing to implement**: the caches exist
and `len()` works. The stop condition fired and was answered with mutation testing (see *Method*
above) rather than an argument.

The tests pin three things the design leans on:

- a freshly constructed cache is empty — the entire basis of the only **sound** direction
  (`cold ⇒ all three sizes == 0`);
- the three attribute **names** the design's validator cites (`_cache`, `_spe_cache`, `_cache`) —
  a rename would silently cost the profile its falsifier, so the names are contract;
- a reused cache carries entries into the next rep — the falsifier's premise, i.e. the scenario
  where a row could otherwise claim `cold`, match its manifest, and measure a warm cache.

The **converse is deliberately untested and unasserted**: `warm ⇒ sizes > 0` is unsound (a reused
`SpeciesDex` on a board whose species were never looked up is legitimately empty). Design §9
entries 23/51 record two revisions that shipped exactly that over-strict shape and would have
rejected real, successful rows.

### A completion gate — **offline; no run**

- Every counter pinned by a test against a *known* transport count. **Nothing reads them yet.**
- **No-behaviour-change evidence, without a battle:** the full existing test suite passes
  unchanged, and the counters are additive fields on backend objects that no decision path reads.

**An earlier draft made "a byte-identical re-run of the frozen smoke" the gate. That gate was both
unauthorized and impossible, and is withdrawn:**

- **Unauthorized.** Re-running the 2-battle smoke is a **new live run**. The earlier smoke
  authorization was consumed by the run that produced the frozen evidence; it does not carry
  forward to a re-run (§4.1).
- **Impossible.** `decision_latency_ms` is wall-clock, and the repo already knows it:
  `VOLATILE_TRACE_FIELDS = frozenset({"decision_latency_ms"})`
  (`eval/decision_diff.py:395`), with `compare_repeat_identity` (`:402`) comparing traces
  **modulo** that field precisely because byte-identity is unreachable. A gate demanding
  byte-identity would never have passed.

---

## 3. I8-B — Sidecar and validators

**Binding for the whole slice (approver-set, before any B code):**

| | |
|---|---|
| **Per-decision values** | **only** from before/after snapshots of A's cumulative counters. B never re-counts, and never asks a backend what happened "this decision" — a backend has no such concept (§2, A1) |
| **Error paths** | keep their **real deltas**. A failed batch made its round trip and paid its latency; A already counts the attempt, and B must carry that delta through rather than zero it |
| **Order** | **deliberately invalid rows first, validator second.** The violating row is the test; a validator written before the row it must reject is a validator written against an imagined row |
| **Live rows** | `cache_class` and all three cache sizes stay **`null`** — the cache contract is defined against an arm's declared lifecycle, which a live row does not have |
| **Dataset validator** | must **actually run before every evidence evaluation**, not merely exist. A tier nobody invokes is the defect the tiers were introduced to fix (§9, entry 52) |
| **Sidecar** | **off by default** and **LF-stable**, asserted on raw bytes |
| **Not authorized** | no smoke, no server, no push |

**Checkpoint after B2, before B3/B4 begin.** — passed at 2360 passed / 2 skipped / 1 xfailed.

### Task B1 — `eval/decision_profile.py`, off by default
The row contract is design §2.4, verbatim: exact-closed field set, LF-only bytes
(`open(..., "a", encoding="utf-8", newline="")` + `json.dumps(sort_keys=True, separators=(",", ":"))`),
mirroring the `eval/opp_mega_trace.py` byte contract that the I7b-C slice already proved.

**RED — assert on raw bytes, never a text-mode read.** The I7b-C slice shipped a "determinism"
test that passed on the very platform producing CRLF, because it read in text mode:

```python
def test_profile_rows_are_lf_only_as_raw_bytes(tmp_path):
    w = DecisionProfileWriter(tmp_path / "p.jsonl")
    w.write(_valid_row()); w.write(_valid_row())
    raw = (tmp_path / "p.jsonl").read_bytes()      # BYTES. A text-mode read hides CRLF.
    assert b"\r\n" not in raw
    assert raw.endswith(b"}\n")

def test_writer_is_off_by_default_and_creates_no_file(tmp_path):
    assert _writer_from_env(env={}) is None
```

### Task B2 — per-row validator
`validate_decision_profile_row`, implementing design §2.4's list exactly, including:

- `backend_class` **recomputed** from the row's own `(spawn_count_before, spawn_calls, transport_retried)`;
- the cache rules **gated on `source == "microprofile"`**, and `source == "live"` ⇒ `cache_class`
  and all three sizes are `null`;
- `source`/`timer_scope` compatibility as a biconditional.

**RED — every rule gets a violating row that must raise, plus the rows earlier design revisions
would have wrongly *rejected*:**

```python
def test_respawn_row_is_legitimate_and_must_not_be_rejected():
    # Design section 9, entries 23 and 51: a process that died between decisions is revived
    # by _ensure BEFORE the first attempt (client.py:176-180) -- no failure, no retry.
    # TWO revisions shipped validators that rejected this real, successful row.
    row = _row(calc_backend="persistent", spawn_count_before=1, spawn_calls=1,
               transport_attempts=1, transport_calls=1, transport_retried=False)
    validate_decision_profile_row(row, manifest=_manifest())      # must NOT raise
    assert row["backend_class"] == "contaminated"                 # excluded, not rejected

def test_live_row_has_null_cache_fields_and_passes():
    # The cache contract is a MICROPROFILE concept: a live row has no arm, no rep and no
    # manifest (design 2.8). Rev. 10 made every live row unsatisfiable.
    row = _row(source="live", timer_scope="agent_choose", cache_class=None,
               damage_cache_size_at_rep_start=None,
               speed_cache_size_at_rep_start=None,
               dex_cache_size_at_rep_start=None)
    validate_decision_profile_row(row, manifest=None)             # must NOT raise

def test_live_row_at_a_microprofile_timer_scope_is_rejected():
    row = _row(source="live", timer_scope="score_evaluated_variants")
    with pytest.raises(ProfileRowError):
        validate_decision_profile_row(row, manifest=None)

@pytest.mark.parametrize("rep,warmup,declared,expected", [
    (0, 0, "per_arm", "cold"),   # 0-BASED: rep 0 is the FIRST timed rep, genuinely cold
    (1, 0, "per_arm", "warm"),   # rep 1 is the SECOND rep -- Rev. 10 called this "cold"
    (0, 1, "per_arm", "warm"),   # warmup already populated the caches
    (0, 0, "per_rep", "cold"),
])
def test_expected_cache_class_is_recomputed_and_rep_is_zero_based(rep, warmup, declared, expected):
    assert expected_cache_class(_arm(lifecycle=declared, warmup=warmup), rep) == expected

def test_cold_claim_with_a_populated_cache_is_rejected():
    # The sound direction: a fresh cache is provably empty (oracle.py:24, speed.py:103,
    # opponent.py:45), so a non-empty one disproves the declared lifecycle.
    row = _row(source="microprofile", cache_class="cold", damage_cache_size_at_rep_start=7)
    with pytest.raises(ProfileRowError):
        validate_decision_profile_row(row, manifest=_manifest(cache="per_rep"))

def test_warm_claim_with_an_empty_dex_cache_is_ACCEPTED():
    # The converse is UNSOUND and deliberately not asserted: a reused SpeciesDex on a board
    # whose species were never looked up is legitimately empty (design 2.8).
    row = _row(source="microprofile", cache_class="warm", rep=1,
               damage_cache_size_at_rep_start=4, speed_cache_size_at_rep_start=2,
               dex_cache_size_at_rep_start=0)
    validate_decision_profile_row(row, manifest=_manifest(cache="per_arm"))   # must NOT raise
```

### Task B3 — dataset validator

`validate_decision_profile_dataset(path, manifest)` — design §2.4's second tier. It **fails the
run**, and no consumer may read rows as evidence without it.

**The lifecycle rule must be executable, and "distribution vs declared lifecycle" is not.** An
earlier draft of this plan said the validator compares "each arm's `backend_class` distribution
against its declared `calc_backend` lifecycle" — that is a description, not a predicate. There is
no threshold, no direction, nothing a function could return `False` from. It is replaced by an
**exact accounting identity**, which is stronger than any distribution test and needs no threshold:

`spawn_count` is cumulative on the backend **object** and never resets while that object lives
(`client.py:194`, `:199`). So for rows of one arm, ordered by `rep`:

```
per_arm  (the object is reused across reps):
    spawn_count_before[0] == 0
    spawn_count_before[n+1] == spawn_count_before[n] + spawn_calls[n]     # exact identity

per_rep  (a fresh object every rep):
    spawn_count_before[n] == 0   for every n
```

Why this is the right rule and the earlier one was not:

- It **catches a harness that reuses when it declared `per_rep`** — a reused object carries
  `spawn_count_before > 0` into rep 1, which `per_rep` forbids.
- It **catches a harness that rebuilds when it declared `per_arm`** — a fresh object resets the
  count to 0, breaking the identity.
- It **never rejects a legitimate respawn.** `_ensure` reviving a dead process (`client.py:206-210`)
  just adds 1 to `spawn_calls[n]`, and the identity still holds exactly. This is the trap that
  entries 23/51 of the design's §9 fell into twice; the identity form is immune to it by
  construction.

The same identity form covers the caches, and is sound for the same reason — the three caches are
never cleared or evicted (design F-14, `oracle.py:24`):

```
per_arm  caches:  size_at_rep_start[n+1] >= size_at_rep_start[n]    # monotone; never cleared
per_rep  caches:  size_at_rep_start[n] == 0   for every n
```

Also owned: `fixture_input_hash ⇒ constant n_candidates`; contaminated/excluded counts reported by
raw fact.

**LANDED** — `validate_decision_profile_dataset(path, manifest)`, 17 tests, corrupted files
written first. Two details the design's prose left implicit and the implementation had to settle:

- **The grouping key is the ARM's `fixture_input_hash`, not `arm_id`.** `fixture_input_hash` is an
  *arm-entry* field while `n_candidates` is a *row* field, so the join runs row → `arm_id` →
  `manifest.arms[…]`. It matters: two arms differing only in call-bound `scoring_params` share a
  fixture, and V is fixture-determined, so they **must** agree on `n_candidates`.
- **The dataset tier re-validates every row.** A file on disk is not a trusted writer — it may have
  been hand-edited, truncated or concatenated since its rows were checked on write. Without this,
  "no consumer may read rows as evidence without it" would be satisfiable by a tampered file.

The respawn case has its own test asserting it **passes**: it only adds to `spawn_calls`, so the
identity stays exact and the row is counted as `contaminated` rather than rejected. A
"predominantly clean_warm" rule would have voided that arm.

### Task B4 — LANDED: one encoder, two hashes

`encode` is public in `eval/decision_profile.py` and is the **only** canonicalisation in the
slice: `profile_manifest_hash` and `fixture_input_hash` are both `_sha1_16(encode(x))`. It came
forward from B4 into B2 because a computed manifest hash cannot rest on a provisional serialiser,
and B4 **extended that same function** rather than introducing a second one — two
canonicalisations would be free to disagree about the one question both exist to answer.

21 tests, each pinning a rule the design shipped and withdrew (§9 entries 33-37): `items` order
changes the hash (`items[0]` is the default assumption); `legal_actions` order changes it (the
first-wins tie-break); `offense`/`defense` are not collapsed; a `set` hashes identically in any
iteration order **because a set has no order to preserve**; an unhandled type fails closed; a
dataclass field added later is picked up automatically. The pydantic branch is verified against
the real `BattleRequest`: `by_alias` is honoured (`forceSwitch`, not `force_switch`) and two
independent builds encode identically.

**RED — the B → C gate. Each corrupted sidecar must fail; the legitimate one must pass:**

```python
def test_dataset_validator_rejects_same_fixture_hash_with_different_n_candidates():
    rows = [_row(fixture_input_hash="abc", n_candidates=12, rep=0),
            _row(fixture_input_hash="abc", n_candidates=13, rep=1)]   # same inputs, different V
    with pytest.raises(ProfileDatasetError):
        validate_decision_profile_dataset(_write(rows), _manifest())

def test_per_rep_arm_with_a_reused_backend_is_rejected():
    # declared per_rep, but rep 1 inherited a spawn count -> the object was reused
    rows = [_row(rep=0, spawn_count_before=0, spawn_calls=1),
            _row(rep=1, spawn_count_before=1, spawn_calls=1)]
    with pytest.raises(ProfileDatasetError):
        validate_decision_profile_dataset(_write(rows), _manifest(calc_backend="per_rep"))

def test_per_arm_arm_that_silently_rebuilt_the_backend_is_rejected():
    # identity breaks: rep 1 should start at 0+1 == 1, not 0
    rows = [_row(rep=0, spawn_count_before=0, spawn_calls=1),
            _row(rep=1, spawn_count_before=0, spawn_calls=1)]
    with pytest.raises(ProfileDatasetError):
        validate_decision_profile_dataset(_write(rows), _manifest(calc_backend="per_arm"))

def test_per_arm_respawn_is_LEGITIMATE_and_must_pass():
    # the process died between reps; _ensure revived it with no retry (client.py:176-180).
    # spawn_calls == 1 on rep 1, identity still exact. Design entries 23/51: do not reject this.
    rows = [_row(rep=0, spawn_count_before=0, spawn_calls=1),
            _row(rep=1, spawn_count_before=1, spawn_calls=1),
            _row(rep=2, spawn_count_before=2, spawn_calls=0)]
    validate_decision_profile_dataset(_write(rows), _manifest(calc_backend="per_arm"))   # no raise
```

### Task B4 — the recursive encoder and `fixture_input_hash`
Design §2.7: `encode()` recursing over `dataclasses.fields()`, the pydantic `BaseModel` branch with
pinned `model_dump` options, **sets sorted, lists order-preserving**, fail-closed on an unhandled
type.

**RED — the ordering rules are the whole point, and each test pins a defect the design actually
shipped and had to withdraw:**

```python
def test_items_order_changes_the_hash():
    # items[0] IS the default assumption (default_spreads.yaml:12; read at hypotheses.py:109
    # and spreads.py:91). Sorting [Life Orb, Choice Specs, Focus Sash] silently changes the
    # assumed item to Choice Specs. Same membership, different default -> different hash.
    a = SpreadPreset("Jolly", {"spe": 252}, ["Choice Scarf", "Life Orb"])
    b = SpreadPreset("Jolly", {"spe": 252}, ["Life Orb", "Choice Scarf"])
    assert fixture_input_hash(_kw(book=_book(a))) != fixture_input_hash(_kw(book=_book(b)))

def test_legal_actions_order_changes_the_hash():
    # Enumeration order IS the first-wins tie-break (mega_scoring.py:184-198, a prior
    # Codex I7a-B merge-blocker): same membership, different order -> different chosen action.
    assert fixture_input_hash(_kw(legal_actions=[j1, j2])) != fixture_input_hash(_kw(legal_actions=[j2, j1]))

def test_offense_and_defense_branches_are_not_collapsed():
    # SpeciesSpreads carries BOTH (hypotheses.py:27-33); offense drives Mega speed
    # (speed.py:176), defense drives our own item truth (spreads.py:89-91).
    assert fixture_input_hash(_kw(our_spreads={"x": SpeciesSpreads(O, D)})) != fixture_input_hash(_kw(our_spreads={"x": SpeciesSpreads(D, O)}))

def test_a_set_field_hashes_identically_regardless_of_iteration_order():
    # moves/move_names are genuinely set[str] (state.py:66-67) -- a set has NO order to
    # preserve, so sorting is the only deterministic option. This is exactly why
    # "canonicalise by sorting" looked right and was wrong for lists.
    assert fixture_input_hash(_kw(state=_state(moves={"a", "b"}))) == fixture_input_hash(_kw(state=_state(moves={"b", "a"})))

def test_an_unhandled_type_fails_closed():
    with pytest.raises(TypeError):
        encode(object())

def test_request_is_encoded_from_the_model_with_pinned_dump_options():
    # The raw payload is unreachable: _mega_req() passes a dict literal straight into
    # model_validate (conftest.py:126) and returns only the model. by_alias is pinned
    # because it demonstrably changes keys (forceSwitch vs force_switch).
    enc = encode(_mega_req())
    assert "forceSwitch" in enc and "force_switch" not in enc
```

### B completion gate — **offline; no run**

Both tiers tested. A corrupted sidecar fails; a legitimate respawn passes. Sidecar off by default.

**No-behaviour-change evidence without a battle:** the sidecar is off by default and its writer has
no call site in any decision path yet, so the existing suite passing is the evidence. The
"byte-identical smoke re-run" an earlier draft asked for is withdrawn for both reasons given under
the A gate — unauthorized, and impossible against a wall-clock `decision_latency_ms`.

---

## 4. I8-C — Microprofile

### Task C1 — manifest and arm matrix
Design §2.7's manifest; arms per §4. Every arm declares `lifecycle` explicitly (no default), and
the three semantic caches **share** one lifecycle (invalid at load otherwise).

### Task C2 — the harness
Timer scopes per §2.5. Cache sizes sampled **at rep start**, before context construction and before
the timer — the design's §2.8 records why a timer-start sample would call every cold-cache arm warm.

### Task C3 — arms that need a missing fixture
P-1…P-5 block arms 5, 7, 8, 10, 13/14. **Each blocked arm is either given a fixture or dropped with
its blocker named in the report.** None is silently skipped — the design's §5 forbids a bounded
coverage claim that reads as complete.

### C completion gate
A green microprofile run; all rows pass both tiers; no server, no battle, no latency claim.

---

## 5. I8-D — Live harness and the run

### 5.1 The stop rule — exposure only

```
stop when   (active_valid >= 60 AND distinct_battles_with_active >= 20)   # D-1 met
       or   (battles_played >= MAX_BATTLES)                               # cap
       or   (scored_decisions >= MAX_SCORED_DECISIONS)                    # cap
```

- **`measured_ms` is never an input to the stop rule.** Not as a threshold, not as a trend, not as a
  "looks fine, stop early". The runner does not compute a p95 until the run has stopped.
- **A valid row is design §5.3's gate predicate**, referenced not restated:
  `source == "live" AND timer_scope == "agent_choose" AND outcome == "ok" AND foe_mega_active`.
- **No seed-shopping.** Seeds are `seed_index` values assigned by the schedule **before** the run and
  frozen in the schedule hash. No seed is re-rolled, skipped, or chosen after seeing any row. A run
  that is restarted for an infrastructure fault restarts **from its first seed** and its partial
  output is discarded, not merged.
- **No strength claim.** The verdict is about the 1000 ms budget on active foe-Mega decisions.
  Nothing about winrate, play quality, or the value of the Mega overlay.

### 5.2 The verdict

| condition | verdict |
|---|---|
| floor met **and** p95 ≤ 1000 ms | `PASS` |
| floor met **and** p95 > 1000 ms | `FAIL` |
| either minimum unmet at cap | `INCONCLUSIVE — exposure floor not met` |

The floor is a **precondition evaluated before the p95**. If the run stops at the cap with 47 active
decisions, the verdict is `INCONCLUSIVE` and **the p95 of those 47 is not reported as a verdict** —
it may be reported as exposure data, explicitly labelled as not a gate value.

### 5.3 Reporting on INCONCLUSIVE

The run still yields the thing the project most lacks: a **real exposure rate** on n ≫ 17, which
turns D-1's next sizing from a 26×-wide CI into an estimate. The report states the observed active
rate with its interval, the cap that bound it, and what n would have been required. That is a
measurement outcome, not a consolation.

---

## 4.1 D-2 — the cap. **Open; needs approval before I8-D starts.**

The design forbids inventing thresholds, and the cap **cannot be derived** — it is a cost decision,
exactly as D-1 was. The arithmetic from §0, at 8.5 scored decisions/battle:

| cap | scored decisions | expected active @ 5.9 % | reaches 60? |
|---|---|---|---|
| 120 battles | ~1 020 | ~60 | ~coin-flip at the point estimate; `INCONCLUSIVE` below it |
| **200 battles** | **~1 700** | **~100** | ~1.7× headroom at the point estimate; still `INCONCLUSIVE` if the true rate is ≤ 3.5 % |
| 675 battles | ~5 700 | ~340 | covers the CI floor; cost likely prohibitive |

**Recommendation: `MAX_BATTLES = 200`, `MAX_SCORED_DECISIONS = 2000`, whichever binds first.** It
carries meaningful headroom over the point estimate without pricing in the CI floor, and it makes
the failure mode explicit rather than surprising: *if the true rate is at or below ~3.5 %, this run
returns `INCONCLUSIVE` by construction, and that is accepted in advance.*

**Unmeasured and needed before the cap is fixed:** wall-clock per battle. The frozen smoke's 2
battles are the only sample and their runtime was never recorded.

**Task D0 — a 2-battle timing run. SEPARATELY AUTHORIZED; not covered by anything so far.**

An earlier draft of this plan called D0 "a timing measurement of *already-authorized* work, no new
battles". **That was wrong, and the error mattered:**

- **Re-running the smoke is a new live run.** It starts a Showdown server, plays two fresh battles
  and produces new artifacts. The I7b-C smoke authorization was consumed by the run that produced
  the frozen evidence — an authorization to run once is not a standing licence to run again.
- **"No new battles" was simply false.** Two battles would be played.
- The frozen artifacts cannot supply the number either: runtime was never recorded in them, so
  there is nothing offline to read.

**Therefore:**

| | |
|---|---|
| **Status** | **BLOCKED — needs its own explicit authorization**, requested separately, before D-2 |
| **Scope** | replay the existing 2-battle smoke schedule (`champions_v0_smoke_i7b_2battle.yaml`), unchanged, to record wall-clock per battle and per decision |
| **Produces** | a runtime figure only. **No latency verdict, no exposure claim, no strength claim** — n = 2 battles decides nothing about D-1 |
| **Artifacts** | written to a scratch path and **not** frozen as evidence; the existing frozen smoke is not overwritten, re-hashed, or touched |
| **Blocks** | D-2, which should not be decided against a guessed cost |

**Sequence:** authorize D0 → run D0 → decide D-2 with a real per-battle cost → then, and only then,
I8-D. If D0 is not authorized, D-2 must be decided on an explicitly acknowledged unknown, and this
plan says so rather than pretending the number exists.

---

## 6. What this plan does not do

- It starts **no code**: every task above is a specification of work, not the work.
- It starts **no run**: I8-D's run needs separate authorization, and D-2 must be approved first.
- It changes **no behaviour**: no click rate, no TOPM/TOPN, no `opp_sets` curation, no budget. The
  §0 finding that `opp_sets` curation *would* raise exposure is recorded precisely so it is **not**
  done here.
- It makes **no strength claim** and licenses none.

---

## 7. Open decisions

| id | decision | status |
|---|---|---|
| **D-1** | Exposure floor | **CLOSED** — approver-set (design §5.4): ≥ 60 active from ≥ 20 battles; PASS/FAIL/INCONCLUSIVE; no statistical or strength claim |
| **D-2** | `MAX_BATTLES` / `MAX_SCORED_DECISIONS` | **OPEN** — recommendation 200 / 2000 (§4.1); blocks I8-D; wants D0's per-battle runtime first |
| **D0** | Authorize a 2-battle timing run to cost D-2 | **BLOCKED — needs its own authorization** (§4.1). It is a **new live run**; no earlier smoke authorization covers it |

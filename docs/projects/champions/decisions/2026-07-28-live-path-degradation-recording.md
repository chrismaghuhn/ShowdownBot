# Live-path degradation recording: always-on, own-seat only, off the turn path

**Status:** DECIDED — written before the implementation it authorises.
**Amended:** 2026-07-29, §8.0 — `completion.json` gains `schema_errors_total` and
`recorder_errors_total`. Three zero counters define a **clean completion snapshot** at the moment
of serialisation, *not* a successful run. A successful run requires exit `0` **plus** a
`completion.json` that is present, parses, validates, and carries three zeros; a non-zero exit
means the run failed, and with a clean snapshot the file alone cannot say whether recording failed
after the snapshot or an independent runner exception ended the run. The write is exclusive but
**not atomic**, so *absent*, *unparseable* and *schema-invalid* are equivalent failure states.
Still before the implementation: no code exists yet, so nothing frozen is recalculated by this
amendment.
**Date:** 2026-07-28
**Scope:** `showdown_bot/src/showdown_bot/client/runner.py` — `run_ladder_search`,
`run_challenge`, `run_smoke_battle`. See §3 for what `run_smoke_battle` may and may not record.
**Issue:** #125.

---

## 1. The question this record settles

Should structured degradation recording on the live path be **always active**, or opt-in
behind an environment flag?

**Ruling: always active.** Written automatically under `logs/`, with an optional path
override. No flag gates whether recording happens; a flag may only redirect where it goes.

## 2. Why opt-in was rejected

Opt-in preserves the exact gap this slice exists to close: a normally started live bot would
still run without analysable degradation evidence, and nobody discovers that until they go
looking for evidence that was never produced.

This is not hypothetical in this repository. The Gate B independent strength holdout captured
no hero logs across **360 battles** because `SHOWDOWN_ROOM_RAW_DUMP` was env-gated and unset
for both arms. That evidence is not recoverable, and the gap was found only after the run.

## 3. Correcting the premise this slice inherited

The ROADMAP and #125 described the gap as "`client/runner.py`: 0 of 9 signals". **That number
is not supported by any artifact and is withdrawn.** It was reconstructible only by adding
categories that are not comparable:

- `_seat_counters` (`gauntlet.py:230`) returns six values, but only **four** are per-seat.
- `invalid_total` / `crashes_total` are the explicitly **summed historical** fields. Gate B
  finding 5 identified that summing as the defect; counting the sum as an additional
  independent signal reproduces the error the per-seat split exists to correct.
- Crashes are not transported per seat at all.
- `SelectionStageSink`, the decision-profile row and `on_battle_result` are **transport and
  persistence mechanisms**, not degradation signals of the same kind.
- The audit `2026-07-27-degradation-asymmetry-gauntlet-vs-live.md` §3 contains no enumeration
  of nine; its `6`, `13` and `2` are counts of code references in the gauntlet.

**And the decisive one:** the ladder runner controls exactly **one seat — its own**. `hero_*` /
`villain_*` pairs cannot be carried across literally. A schema that copied them would ship
fields that are structurally always zero, and a later reader would take "zero" for "clean"
instead of "not observable from this path".

## 4. The contract, by layer

| Layer | Content | Note |
|---|---|---|
| **Raw facts** | `state_build_failed` (§5); agent crash (§6); selection stage / fallback reason; own invalid choice (§7); room-scoped server error (§7) | Own seat only |
| **Context** | `book_absent`, `team_preview` | **Not** degradation facts. They are why a decision took the no-state path, recorded so a reader can tell "not applicable" from "clean" (§5). Carrying them does not widen the raw-fact set (§11) |
| **Derivation** | `is_degraded_decision()` / `classify_live_outcome()`, **gated by `derivation_applicable`** (§5.1) | Existing functions, unchanged. They are not called at all when the gate is false |
| **Aggregation** | Own per-battle counters | **Never mixed with another seat.** No `hero_`/`villain_` field names on this path |
| **Transport** | `SelectionStageSink` | Already an explicit optional sink parameter |
| **Persistence** | `live-degradation-v1` — see §8 | **Not** the decision-profile schema |

## 5. `state_build_failed` is narrower than `state is None`

In `handle_battle_message`, `state` ends up `None` in **three** distinct situations, and only
one of them is degradation:

| Situation | `state is None` | Degradation? |
|---|---|---|
| `book is None` (format unsupported, e.g. a random format) | yes | **no** — the state path was never entered |
| `req.team_preview` | yes | **no** — deliberately skipped |
| The build was attempted and raised | yes | **yes** |

The raw fact is therefore `state_build_failed`: *the build was attempted and failed*. It is
recorded only on the third branch and must not be derived from `state is None`.

The gauntlet already scopes this — it guards with `not req.team_preview and self.agent in
_DEGRADABLE_AGENTS` before passing `state_degraded=(state is None)` (`gauntlet.py:885-889`).
The live path needs the same scoping **plus** the `book is None` exclusion, which the gauntlet
does not need because it always has a book.

**Consequence for `run_smoke_battle`:** it searches `gen9randomdoublesbattle`, for which
`_get_book` returns `None`. Every smoke decision therefore has `state is None` while nothing is
degraded. A naive rule would report smoke as 100 % degraded. Smoke runs record the
`book_absent` condition and take the no-state path; they do **not** emit `state_build_failed`,
and a smoke record must never be read as a degradation measurement of the heuristic path.

### 5.1 The derivation must be gated, not merely annotated

Context fields do not prevent misclassification, because the misclassification happens inside
the derivation functions themselves. Verified:

- `is_degraded_decision()` **fails closed to `True`** on an absent or unknown
  `selection_stage` — deliberately, because it runs in the battle loop where raising would kill
  the battle.
- `classify_live_outcome()` **raises `DecisionProfileError`** on the same input.

On the live path both inputs occur normally and innocently. `run_smoke_battle` goes through
`choose_for_request()`, which has no `SelectionStageSink` at all, so the stage is absent for
every smoke decision. Team preview carries no intended stage either. Feeding those into the
derivations would mark every smoke decision degraded and would make the classifier raise.

**Rule:**

```
derivation_applicable = (not book_absent) and (not team_preview)
```

- When `derivation_applicable` is **false**, neither derivation function is called. The row
  records `derivation_applicable: false` and `outcome: "not_applicable"`.
- Such decisions **increment no degradation counter of any kind.** `not_applicable` is not a
  degraded outcome and must never be aggregated as one.
- When it is **true**, the existing functions are called unchanged, and `outcome` takes one of
  their existing values.


## 6. Agent crash — record, then re-raise

"Agent crash" means an exception escaping the chooser call for **this** decision. It is
recorded with its exception type and then **re-raised unchanged**.

An earlier revision said the runner "still returns a legal action" afterwards. That would have
been a behaviour change, and it contradicts this slice's own non-goal. Verified: today the
chooser call in `handle_battle_message` has no guard at all — the single `except` in that
function wraps the state build, nothing else — so a chooser exception propagates out of the
battle loop. Introducing a default-choose fallback here would change what the bot does, not
just what it records.

The recording boundary therefore observes and re-raises. A process crash is covered by §10,
not here.

## 7. `|error|` and the invalid-choice PM

These are two different things and must not be conflated:

- **`|error|` in a battle room** — recorded as a **room-scoped server error with its payload**,
  attributed to that room. It is *not* automatically classified as an invalid choice: the
  server sends `|error|` for several conditions, and pre-classifying at record time would bake
  an interpretation into the raw layer. Classification, if any, belongs to the derivation layer
  or to later analysis.
- **A `pm` containing `Invalid choice`** — carries **no room**. The loop fans out
  `_send_default_choose` to *every* active battle precisely because it cannot tell which battle
  the PM refers to. It is therefore **unattributable in general** and is recorded as a
  run-scoped event, never assigned to a room. It may be attributed to a room only in the
  degenerate case where exactly one battle is active at that moment, and the record must mark
  that attribution as inferred.

An earlier revision of this record said attribution "must be per room, not per event". That was
wrong: per-room attribution is not available for the PM path.

## 8. Artifact: `live-degradation-v1`, not the decision-profile schema

The decision-profile schema is **closed** and produced by the gauntlet's own machinery, which
supplies fields the ladder runner has no way to produce. Writing partial or improvised rows into
it would corrupt a schema that frozen evidence and its validators depend on. This slice defines
its own artifact under a run directory in `logs/`, versioned independently.

`decisions.jsonl` alone is not enough: the invalid-choice PM is run-scoped, and `|error|` can
arrive outside any decision. Those need their own sink, or they would have to be forced onto a
decision they do not belong to.

`schema_version` is the literal string **`"live-degradation-v1"`** in every row of every file.

| File | Grain | Required fields |
|---|---|---|
| `decisions.jsonl` | one decision | `schema_version`, `run_id`, `room_id`, `decision_seq`, `rqid`, `book_absent`, `team_preview`, `state_build_failed`, `selection_stage`, `fallback_reason`, `agent_crash_type`, `derivation_applicable`, **`is_degraded`**, `outcome` |
| `events.jsonl` | one async event | `schema_version`, `run_id`, `event_type` (`server_error` \| `invalid_choice_pm`), `attribution` (`room` \| `inferred` \| `unattributed`), `room_id`, `payload`, `active_battle_count` |
| `battles.jsonl` | one battle | `schema_version`, `run_id`, `room_id`, `decisions_total`, `decisions_not_applicable`, **`degraded_decisions`**, `state_build_failures`, `agent_crashes`, `fallback_decisions`, `own_invalid_choices`, `server_errors`, `end_reason` (`win` \| `tie` \| `unterminated`), `write_errors` |
| `completion.json` | one run, best-effort | `schema_version`, `run_id`, `battles_finished`, `unterminated_rooms`, **`write_errors_total`**, **`schema_errors_total`**, **`recorder_errors_total`**, `preflight_ok` |

### 8.0 Amendment 2026-07-29 — the three error counters, and why two were added

The original six-field `completion.json` carried only `write_errors_total`. That left a hole the
implementation plan discovered and could not close on its own: a run whose recording failed for a
**non-write** reason would write a `completion.json` that reads permanently clean —
`write_errors_total: 0`, `preflight_ok: true` — while the process exited non-zero. Two such
reasons exist and both are real:

- a **validator rejection**, when a row this module built does not satisfy the schema it declares;
- a **recorder failure** at a call site, when something escapes a `record_*`/`flush_*` call and the
  guard that exists to keep it out of the battle loop swallows it (§10.2, and the rule that a
  recorder failure must never prevent an already-chosen action being sent).

**An exit code and a log line are not a substitute for the persisted evidence artifact.** This
slice exists precisely because evidence that is not written down is evidence that is lost; leaving
two of three failure modes out of the only per-run artifact would reproduce that error inside the
fix for it. The three counters are therefore persisted:

| Field | Counts |
|---|---|
| `write_errors_total` | failed appends and writes across the run, including a failed or refused completion write — subject to the persistence limit below |
| `schema_errors_total` | rows rejected by `validate_decision_row` / `validate_event_row` / `validate_battle_row` / `validate_completion_row` |
| `recorder_errors_total` | anything that escaped a `record_*`/`flush_*` call and was caught by the call-site guard |

**Persistence limit — `completion.json` cannot contain a failure that happens at or after its own
write, and it is not written atomically.** The counters are snapshotted when the payload is built,
so a completion write that *itself* fails is never reflected in a `completion.json`. Three cases,
and only one of them leaves nothing behind:

| Case | What is on disk | What carries the failure |
|---|---|---|
| The **first** completion write fails **before** the file is created | no file at all | the absence (§10.3) plus the exit status |
| The **first** completion write fails **after** `open(..., "x")` succeeded | a file that may be **empty, truncated mid-JSON, complete but unsynced, or otherwise invalid** | the exit status, plus the fact that the file does not parse or does not validate |
| A **later** completion write is refused (§8.1: exclusive create, never truncate) | the earlier successful write's file, byte-for-byte unchanged and possibly reading clean | **the exit status** — the only contractually guaranteed machine-checkable signal outside that unchanged file. The existing file cannot report a failure that occurred after it was written, and it must not be rewritten to say so. `logger.error` also fires (§10.3 item 1), but a log line is neither guaranteed to be retained nor a defined machine contract |

**Why the middle row exists.** The writer opens the final path directly with mode `"x"` and then
serialises, flushes and `fsync`s into it. `"x"` buys **exclusivity, not atomicity**: once the open
has succeeded the file exists, and anything failing afterwards — a full disk, an interrupted
process, a failing `fsync` — leaves a partial or unusable `completion.json` behind. "No file at
all" was therefore never guaranteed, and claiming it would have made a consumer trust the absence
check more than it deserves.

> **Alternative considered and deliberately not taken here: an atomic temp-file commit** (write
> `completion.json.tmp`, `fsync`, then `os.replace`). That would collapse the middle row — a reader
> would see either no file or a complete one. It is rejected *for this amendment*, not on merit: the
> final step of that pattern **overwrites**, which is exactly what §8.1's never-truncate,
> never-overwrite rule forbids, so adopting it means reopening §8.1 rather than extending §8.0. If
> it is wanted, it is its own decision. Until then the honest best-effort taxonomy below is the
> contract, because a stated limit beats an unstated assumption.

The last two rows are why the exit status is a required part of the guarantee and not a
convenience. A consumer must never treat a `completion.json` as proof on its own, and must never
treat one as valid without parsing and validating it — see the taxonomy immediately below,
and §10.3.

**What three zeros mean — and what they do not.** The conjunction

```
write_errors_total == 0 and schema_errors_total == 0 and recorder_errors_total == 0
```

is derived by the consumer; it is not a stored field. And it defines exactly one thing: a **clean
completion snapshot**, meaning the counters as they stood *at the moment the payload was
serialised*. It is **not** a definition of a successful run.

An earlier revision of this amendment did define a "successfully recorded run" that way, and it
contradicted §10.3: the refused-second-write case of the persistence limit above satisfies "three
zeros" and "the run failed" simultaneously. That phrasing is withdrawn. A verdict needs the exit
status as well, and the combinations are these:

**Three file states, not two.** Because the write is not atomic, "the file is there" is not a
usable condition. A consumer must read it, parse it and run `validate_completion_row()` on it.
**Absent, unparseable and schema-invalid are equivalent failure states** — they differ in
diagnostics, never in verdict.

| Exit status | `completion.json` | Verdict |
|---|---|---|
| `0` | present, parses, validates, three zeros | **Successful run, recording included.** The only combination that establishes it |
| ≠ 0 | present, parses, validates, three zeros | **Run failed.** The file alone cannot distinguish *recording failed after its snapshot* (persistence limit above) from *an independent runner exception, cancellation or `KeyboardInterrupt` ended the run*. Both are failures; separating them needs the log or the surrounding context, not this file |
| ≠ 0 | present, valid, some counter non-zero | **Run failed, and recording is a known contributor** |
| ≠ 0 | absent, **or unparseable, or schema-invalid** | **Run failed.** Consistent with an unwritable sink (§10.1, §10.3), a write that died after `open` succeeded (persistence limit, middle row), or a hard kill (§10.4) |
| `0` | anything other than a present, valid, three-zero file | **A defect, not a state.** It contradicts the normal-return rule below and must be treated as an implementation bug rather than interpreted |

**What the exit status means, stated narrowly.** The process exit status is *not* a function of
these three counters alone: a propagated runner exception, a cancellation and a `KeyboardInterrupt`
all end the process non-zero for their own reasons, and this record does not change that — nor may
the recorder mask any of them (§10.3). The rule added here is only the **additional** recorder-based
status **on the normal-return path**:

> On the normal-return path, **after all finalisation attempts — including the completion write —
> and immediately before the recorder-derived status is evaluated**, the process exits non-zero if
> and only if any in-memory error counter is non-zero.

**The two moments are deliberately different, and that difference is the whole taxonomy.** An
earlier revision of this amendment pinned the rule to the moment `completion.json` is serialised,
which made it contradict the persistence limit it sits next to. Walk the refused-second-write case
mechanically, because the details decide it:

1. the payload is **constructed** in memory with three zeros;
2. `open(path, "x")` raises `FileExistsError` — so the payload is **never serialised and never
   reaches the disk at all**. What remains on disk is the snapshot the *earlier successful* write
   left there;
3. `write_errors_total` is incremented **in memory**;
4. the status check runs afterwards and yields non-zero.

An earlier wording of step 1 said the payload "is serialised … and that is what reaches the file".
That is false for this case: nothing from this attempt reaches the file, and the on-disk snapshot
belongs to a *different, earlier* write. The correction matters because it is what makes row 2 of
the taxonomy an honest reading rather than a coincidence — the file is old, not stale-by-a-moment.

The failed-**first**-write case walks differently again: step 2 may fail *before* the create, or
*after* it, and only the first of those leaves nothing behind (persistence limit, middle row).

A rule tied to step 1 would demand exit `0` for a run that had just lost its completion write. The
status is therefore evaluated **last**, over the in-memory counters, while what is on disk is
whatever the last *successful* write put there — or a partial file, or nothing. That gap between
"what the file says" and "what the status says" is exactly why rows 2 and 4 of the taxonomy exist.

A non-zero exit therefore means "the run failed, possibly at recording"; it never means "recording
failed" on its own, and a clean snapshot never upgrades it to success.

**There is deliberately no `recording_ok` boolean field.** A stored boolean is a second
representation of the same fact, and a second representation can disagree with the first. A
consumer computes the conjunction above from the three counters; that cannot drift, because there
is nothing to drift from.

**`completion.json` is validated like the three JSONL grains, not exempt from them.** The closed
contract of §8 covers it: `validate_completion_row(row, *, expected_run_id=None)` checks field set
**and order**, types (`bool` is not an integer counter), non-negativity, and the invariants below.
Mutation tests prove each rule can fail, exactly as for the other three grains.

| Field | Rule |
|---|---|
| `schema_version` | the literal `"live-degradation-v1"` |
| `run_id` | non-empty string; **and**, when `expected_run_id` is supplied, equal to it |
| `battles_finished` | non-negative int; `bool` rejected |
| `unterminated_rooms` | list of non-empty strings, no duplicates |
| `write_errors_total`, `schema_errors_total`, `recorder_errors_total` | non-negative ints; `bool` rejected |
| `preflight_ok` | must be `true`. The file can only be written after preflight succeeded (§10.1), so `false` here is a defect, not a state |

**What the row validator can and cannot prove about `run_id`.** §8 makes `run_id` the join key
across all four files, but a validator handed one completion object cannot see the other three —
and passing the recorder's own `self.run_id` as `expected_run_id` proves only that the recorder is
self-consistent, since both values come from the same source. The cross-file identity is therefore
a **directory-level invariant with its own check**, not something the row validator establishes:

> **Artifact invariant.** In a completed run directory, **every JSONL line that is present**
> carries the same `run_id` as `completion.json`, and that `run_id` equals the directory name
> (§8.1). A **missing** JSONL file means zero persisted rows of that grain — unless the error
> counters mark that state as a write failure, in which case the absence is a failure, not an
> emptiness.

**Why "present", not "all four".** An earlier wording of this invariant demanded all four files
and would have been false on a normal run. Nothing creates empty files: preflight removes its probe
and leaves an empty directory (§10.1), and the append helper returns without touching the disk when
it is handed zero rows. A clean run with no `|error|` and no invalid-choice PM therefore has **no
`events.jsonl` at all** — the commonest case there is — and a run whose writes failed can be
missing more. An invariant that a correct run violates is not a check; it is a false alarm waiting
to happen.

This is proven by an integration test that writes a real run and reads back whatever files exist —
separately from the pure row validators, which perform no IO and must keep performing none (they
run at record time). It covers **two** shapes, not one:

1. a run that produces **every** grain (decisions, at least one event, a battle row, completion);
2. a run with **no events at all**, asserting that `events.jsonl` is absent, that the error
   counters are zero, and that its absence is therefore read as emptiness rather than as loss.

Keeping the invariant and the row validators apart also keeps each able to fail on its own: a row
validator that silently could not check something would be worse than one that does not claim to.

**The absence rule of §10.3 is extended, not weakened:** a missing, unparseable or schema-invalid `completion.json` and a
`completion.json` reporting non-zero counters are equivalent failure states, and success is never
inferred from the absence of a failure record.

**`is_degraded` — the canonical result, and it must be persisted.** `is_degraded_decision()`
is the one function that answers this slice's actual question. Gating its *invocation* (§5.1)
without recording its *result* would discard exactly the signal the slice exists to capture.

| Field | Value |
|---|---|
| `is_degraded` | the return value of `is_degraded_decision()` when `derivation_applicable == true`; **`null`** when it is `false` — never `false`, because "not asked" is not "not degraded" |

**Counter derivation** — each `battles.jsonl` counter is the count of rows **from the source
named for it**, matching a stated predicate. Not all counters come from `decisions.jsonl`; an
earlier revision claimed they did, which was wrong for three of them.

| Counter | Source | Predicate |
|---|---|---|
| `decisions_total` | `decisions.jsonl` | all rows for this room |
| `decisions_not_applicable` | `decisions.jsonl` | `derivation_applicable == false` |
| `degraded_decisions` | `decisions.jsonl` | `is_degraded == true` |
| `state_build_failures` | `decisions.jsonl` | `state_build_failed == true` |
| `agent_crashes` | `decisions.jsonl` | `agent_crash_type != null` |
| `fallback_decisions` | `decisions.jsonl` | `derivation_applicable == true` and `outcome == "fallback"` |
| `own_invalid_choices` | `events.jsonl` | `event_type == "invalid_choice_pm"` **and** `attribution == "inferred"` **and** `room_id` == this room |
| `server_errors` | `events.jsonl` | `event_type == "server_error"` and `room_id` == this room |
| `write_errors` | in-memory failure counter for this room's flushes | not derived from any row — the rows are precisely what could not be written |

`attribution == "unattributed"` events stay **only** in the event stream and increment no battle
counter (§8, attribution rule). `is_degraded == null` rows are counted by
`decisions_not_applicable` and by nothing else.

`decisions_not_applicable` is reported **separately and is never folded into any degradation
counter** (§5.1). Events with `attribution == "unattributed"` contribute to **no** room counter
(§8, attribution rule).

**Null rules.** `selection_stage` and `fallback_reason` are `null` exactly when the value does
not exist — no sentinel strings, no empty strings:

| Field | `null` when |
|---|---|
| `selection_stage` | `derivation_applicable == false`, or the sink recorded no stage |
| `fallback_reason` | the decision did not fall back |
| `agent_crash_type` | no exception escaped the chooser |
| `room_id` | and only when `attribution == "unattributed"` |
| `is_degraded` | `derivation_applicable == false` — the question was not asked |
| `outcome` | never — it is `"not_applicable"` when the gate is false |

**Join keys:** `run_id` across all four; `(run_id, room_id)` joins `decisions` and `events` to
`battles`; `(run_id, room_id, decision_seq)` identifies a decision. `rqid` is recorded as
server-side provenance, **not** as a join key — it is not guaranteed unique across rooms.

**Attribution rule, load-bearing:** an event with `attribution = "unattributed"` **must not
increment any battle counter**. It has no room, and charging it to one — or to all — would
manufacture degradation that was never observed on that battle. `inferred` is permitted only
when `active_battle_count == 1` and is recorded as `inferred`, never as `room`.

### 8.1 Run directory, override, and collision

- Default: `logs/live-degradation/<run_id>/`, where `run_id` is a UTC start timestamp plus a
  short random suffix.
- Override: the environment variable **`SHOWDOWN_LIVE_DEGRADATION_DIR`** replaces the parent
  directory only; the `<run_id>` subdirectory is still created beneath it.
- **The run directory is created exclusively** (`os.makedirs(..., exist_ok=False)`). If it
  already exists, the run **fails preflight** (§10.1) rather than reusing or overwriting it.
- **No file is ever opened in a mode that truncates.** A new run never overwrites existing
  evidence; that is the whole point of the exclusive create.

**Environment-classification obligation.** `SHOWDOWN_LIVE_DEGRADATION_DIR` matches the
`SHOWDOWN_*` prefix, and `eval/config_env.py::is_excluded` **fails closed toward inclusion** —
an unclassified name lands in `behavior_env` and therefore in `config_hash`. Left unclassified,
merely choosing where to write telemetry would change the identity of the run being measured.
It is an IO path with no `/choose` effect, so it must be added to `NON_BEHAVIORAL`, exactly like
`SHOWDOWN_DECISION_PROFILE_OUT`. The drift test that asserts every `SHOWDOWN_*` read in source
is classified will otherwise fail — by design.

## 9. Battle boundaries and exit paths

Taken from `runner.py::_run_battle_loop`, not assumed:

- **Start:** `|init|battle` → the room enters `active_battles`.
- **End:** `|win|` or `|tie|` → the room leaves `active_battles` and `_room_raw.pop(room)`
  discards the raw log. **The battle record must be flushed before that pop** — that pop is
  where today's evidence is thrown away.
- **Run end:** `battles_finished >= max_battles` → connection closed, count returned.

**A battle can end without either event, and not only by the stream running out.** Rooms may
still be in `active_battles` when the loop exits via:

- the `async for` ending (disconnect, server close),
- an exception — `_run_battle_loop` itself raises `RuntimeError` on the `not ladderable` and
  `invalid team` popups, and any other exception propagates,
- `asyncio.CancelledError` — cancellation is not an exception the loop handles today.

All three must flush the still-active rooms as `unterminated`. That requires a `finally`, not a
post-loop statement: a post-loop flush is skipped on exactly the exception and cancellation
paths where the evidence matters most. A design that flushes only on `|win|`/`|tie|` silently
loses precisely the battles most likely to have degraded.

## 10. Initialisation, write failures, and what cannot be guaranteed

### 10.1 Preflight — fail closed BEFORE the first live battle

"Always on" is only true if the sink is known to work before anything is at stake. Before
`_connect_and_login` and before any `/search` or challenge is sent, the runner creates the run
directory and proves the writer works (open, write a probe, fsync, close).

**If preflight fails, the run aborts before the first live battle.** That is the one place a
recording failure is allowed to stop the run, precisely because nothing has been played yet:
aborting costs nothing, whereas discovering an unwritable sink after 50 ladder games costs all
50 games' evidence. Once battles are in flight the policy inverts — see 10.2.

### 10.2 During play — no write on the decision path, no propagation into a battle

The absolute claim "a write failure never blocks a turn or a battle" was too strong, because a
synchronous flush at a battle boundary sits inside the shared `async for` loop and can delay
message processing for *other* active battles.

The precise contract:

- **No filesystem write occurs on the decision/turn path.** Decisions are buffered in memory.
- **Flushes happen at battle boundaries only**, and their errors **never propagate into a
  battle** — they are caught, counted, and logged.
- A boundary flush is **synchronous, with no latency bound.** "Bounded" was claimed in an
  earlier revision and withdrawn: without a background thread or a timeout, a filesystem call
  can hang indefinitely, so no upper bound can be honoured. This slice does **not** introduce a
  background writer — concurrency would add its own failure modes and ordering questions to a
  slice whose entire purpose is evidence integrity — and therefore accepts the unbounded case
  explicitly rather than asserting a limit it cannot enforce.
- **Accepted consequence, stated rather than hidden:** a slow or stalled disk at a boundary can
  delay message processing for other active battles for the duration of that flush. That is a
  real cost of the synchronous choice. If it ever bites, a background writer is the remedy, and
  it is a separate decision.

### 10.3 The failure record cannot be guaranteed by the writer that failed

An earlier revision said a flush failure "is itself recorded", which is circular — if the sink
is unwritable, the record of that fact is unwritable too. The guarantee is split:

1. **In-memory counters + `logger.error`** — always available, independent of the sink. All three
   counters of §8.0 (`write_errors_total`, `schema_errors_total`, `recorder_errors_total`), not
   the write counter alone.
2. **`completion.json`** — best-effort, and it **persists all three counters** (§8.0). It may
   itself fail to write, and its absence is meaningful, not neutral. It must never read clean
   while a counter was already non-zero when its payload was built — that was the hole §8.0
   closes. It **can** read clean about failures that happen at or after its own write; that
   residual case is bounded and tabulated in §8.0's persistence limit, not waved away.
3. **Process exit status** — the machine-checkable signal, and for §8.0's refused-second-write
   case the only contractually guaranteed machine-checkable one outside the unchanged file.
   Item 1's `logger.error` still fires there; it is simply not a machine contract — nothing in
   this record guarantees the log is retained, parseable or even enabled. On the normal-return
   path, **after all finalisation attempts including the completion write, and immediately before
   the recorder-derived status is evaluated**, the run exits non-zero if and only if any in-memory
   counter is non-zero — §8.0 states this rule authoritatively and explains why it is evaluated
   last rather than at serialisation time. This is an **additional** condition, not a definition
   of the
   exit status: a propagated runner exception, a cancellation and a `KeyboardInterrupt` produce
   their own non-zero exits, and the recorder must not mask, replace or suppress any of them —
   whatever ended the run keeps its own status. Exit status depends on no file being writable,
   which is why it is the last line of defence; it is also not persisted evidence and does not
   survive the process, which is why it is not the first.

A consumer must treat *"no `completion.json`"*, *"a `completion.json` that does not parse or does not validate"* and *"a `completion.json` reporting failures"* as
equivalent failure states, and must never infer success from the absence of a failure record.

**And a third state, from §8.0's persistence limit:** a `completion.json` with three zero counters
alongside a **non-zero exit status** is a failure too, not a contradiction to resolve in the file's
favour. Three zeros are a **clean completion snapshot** at serialisation time, never a verdict on
the run — §8.0's taxonomy is authoritative and this paragraph restates it, it does not extend it.
The correct reading is "the run failed, and this file predates or does not cover that failure";
whether recording failed after the snapshot or an independent runner exception ended the run is
something the file cannot decide. A consumer that checks only the file, or only the exit status,
will be wrong on one of these cases; the verdict needs both.

### 10.4 Remaining evidence limit

Because a battle is buffered in memory until its boundary, a hard process termination —
`SIGKILL`, power loss, an OOM kill — loses that battle's unflushed decisions entirely. No
`finally` runs. This is the accepted residual gap of the buffered design; per-decision appending
was rejected because it puts a filesystem write on the turn path (10.2). A future slice may
revisit that trade; this record does not.

## 11. Non-goals

- No new degradation signals beyond the raw facts in §4. The **context** fields
  (`book_absent`, `team_preview`) are not degradation facts and do not widen that set;
  they exist so a reader can distinguish "not applicable" from "clean" (§5).
- No threshold changes.
- No automatic abort on degradation. `_abort_on_degradation` checks four counters and stays
  narrower than what is recorded. **Recording and aborting are allowed to differ in breadth** —
  that is this slice's explicit non-goal, not a gap to be closed later by accident.
- No strength claim, and no change to how any decision is chosen. This is a recording slice.

## 12. What this authorises

A narrow wiring slice against §4, honouring §5–§10. It does not authorise harmonising the two
choosers (option C in the asymmetry audit), which remains a separate, unmade decision.

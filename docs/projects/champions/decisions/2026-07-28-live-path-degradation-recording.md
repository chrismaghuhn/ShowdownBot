# Live-path degradation recording: always-on, own-seat only, off the turn path

**Status:** DECIDED — written before the implementation it authorises.
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
| `decisions.jsonl` | one decision | `schema_version`, `run_id`, `room_id`, `decision_seq`, `rqid`, `book_absent`, `team_preview`, `state_build_failed`, `selection_stage`, `fallback_reason`, `agent_crash_type`, `derivation_applicable`, `outcome` |
| `events.jsonl` | one async event | `schema_version`, `run_id`, `event_type` (`server_error` \| `invalid_choice_pm`), `attribution` (`room` \| `inferred` \| `unattributed`), `room_id`, `payload`, `active_battle_count` |
| `battles.jsonl` | one battle | `schema_version`, `run_id`, `room_id`, `decisions_total`, `decisions_not_applicable`, `state_build_failures`, `agent_crashes`, `fallback_decisions`, `own_invalid_choices`, `server_errors`, `end_reason` (`win` \| `tie` \| `unterminated`), `write_errors` |
| `completion.json` | one run, best-effort | `schema_version`, `run_id`, `battles_finished`, `unterminated_rooms`, `write_errors_total`, `preflight_ok` |

**Counter derivation** — each `battles.jsonl` counter is the count of that room's
`decisions.jsonl` rows matching a stated predicate, so no counter can drift from the rows:

| Counter | Predicate over the room's decision rows |
|---|---|
| `decisions_total` | all rows |
| `decisions_not_applicable` | `derivation_applicable == false` |
| `state_build_failures` | `state_build_failed == true` |
| `agent_crashes` | `agent_crash_type != null` |
| `fallback_decisions` | `derivation_applicable == true` and `outcome == "fallback"` |
| `own_invalid_choices` | own invalid-choice events attributed to this room |
| `server_errors` | `events.jsonl` rows with `event_type == "server_error"` and `room_id` == this room |

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

1. **In-memory counter + `logger.error`** — always available, independent of the sink.
2. **`completion.json`** — best-effort. It may itself fail to write, and its absence is
   meaningful, not neutral.
3. **Process exit status** — the machine-checkable signal. If any flush failed, the run exits
   non-zero. This depends on no file being writable and is what an automated caller keys on.

A consumer must treat *"no `completion.json`"* and *"`completion.json` reporting failures"* as
equivalent failure states, and must never infer success from the absence of a failure record.

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

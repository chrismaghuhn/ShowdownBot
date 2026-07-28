# Live-path degradation recording: always-on, own-seat only, non-blocking

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
| **Derivation** | `is_degraded_decision()` / `classify_live_outcome()` | Existing functions, unchanged — this slice adds no new definition |
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

## 6. Agent crash

"Agent crash" means an exception escaping the chooser call for **this** decision, caught at the
recording boundary, after which the runner still returns a legal action. It is recorded with
the exception type; it is not a process crash and not a connection error. A process crash is
covered by §9, not here.

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
it would corrupt a schema that frozen evidence and its validators depend on.

This slice therefore defines its own artifact, under a run directory in `logs/`:

| File | Content |
|---|---|
| `decisions.jsonl` | one row per decision — the raw facts of §4 for the runner's own seat |
| `battles.jsonl` | one row per battle — own per-battle counters, plus how the battle ended (`win` / `tie` / `unterminated`) |
| `completion.json` | run-level summary, **best-effort** — see §10 |

Schema name `live-degradation-v1`, versioned independently of `decision-profile-v*`. Nothing in
this slice writes to the decision-profile schema.

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

## 10. Write failures, and what cannot be guaranteed

**A write failure must never block a turn or a battle.** The runner plays real ladder games
against a live server; a blocking write costs the game. Recording is buffered in memory during
the battle and flushed at the boundaries in §9, inside a handler that cannot propagate into the
battle loop.

**But the failure record cannot be guaranteed by the writer that just failed.** An earlier
revision said a flush failure "is itself recorded", which is circular — if the sink is
unwritable, the record of that fact is unwritable too. The guarantee is therefore split:

1. **In-memory counter + `logger.error`** — always available, independent of the sink.
2. **`completion.json`** — best-effort. It may itself fail to write, and its absence is
   meaningful, not neutral.
3. **Process exit status** — the machine-checkable signal. If any flush failed, the run exits
   non-zero. This does not depend on any file being writable and is what an automated caller
   must key on.

A consumer must treat *"no `completion.json`"* and *"`completion.json` reporting failures"* as
equivalent failure states, and must not infer success from the absence of a failure record.

**Remaining evidence limit, stated rather than papered over:** because a battle is buffered in
memory until its boundary, a hard process termination — `SIGKILL`, power loss, an OOM kill —
loses that battle's unflushed decisions entirely. No `finally` runs. This is the accepted
residual gap of the buffered design; the alternative, appending per decision, was not chosen
because it puts a filesystem write on the turn path. A future slice may revisit that trade;
this record does not.

## 11. Non-goals

- No new degradation signals beyond the raw facts in §4.
- No threshold changes.
- No automatic abort on degradation. `_abort_on_degradation` checks four counters and stays
  narrower than what is recorded. **Recording and aborting are allowed to differ in breadth** —
  that is this slice's explicit non-goal, not a gap to be closed later by accident.
- No strength claim, and no change to how any decision is chosen. This is a recording slice.

## 12. What this authorises

A narrow wiring slice against §4, honouring §5–§10. It does not authorise harmonising the two
choosers (option C in the asymmetry audit), which remains a separate, unmade decision.

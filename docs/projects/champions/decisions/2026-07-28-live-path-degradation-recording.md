# Live-path degradation recording: always-on, own-seat only, non-blocking

**Status:** DECIDED — written before the implementation it authorises.
**Date:** 2026-07-28
**Scope:** `showdown_bot/src/showdown_bot/client/runner.py` (ladder + challenge + smoke).
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
An env-gated degradation record would fail the same way, for the same reason, on the path
where the bot actually plays real ladder games.

The cost of the opposite error is small and bounded: an always-on writer appends a small
structured record per battle to a directory the runner already creates.

## 3. Correcting the premise this slice inherited

The ROADMAP and #125 described the gap as "`client/runner.py`: 0 of 9 signals". **That number
is not supported by any artifact and is withdrawn.**

The nine was reconstructible only by adding categories that are not comparable:

- `_seat_counters` (`gauntlet.py:230`) returns six dictionary values, but only **four** are
  per-seat: `hero`/`villain` × `degraded`/`invalid`.
- `invalid_total` and `crashes_total` are explicitly the **summed historical** fields. Gate B
  finding 5 identified that summing as the defect — a summed counter lets a blind baseline
  hide behind a clean candidate. Counting the sum as an additional independent signal
  reproduces the very error the per-seat split exists to correct.
- Crashes are not transported per seat at all.
- `SelectionStageSink`, the decision-profile row and `on_battle_result` are **transport and
  persistence mechanisms**, not degradation signals of the same kind.
- The audit `2026-07-27-degradation-asymmetry-gauntlet-vs-live.md` §3 contains no enumeration
  of nine. Its `6`, `13` and `2` are counts of code references in the gauntlet.

**And the decisive one:** the ladder runner controls exactly **one seat — its own**. The
gauntlet drives both clients; the live runner does not. `hero_*` / `villain_*` pairs therefore
cannot be carried across literally. A schema that copied them would ship fields that are
structurally always zero, and a later reader would take "zero" for "clean" instead of "not
observable from this path".

## 4. The contract, by layer

Replaces the fixed-count promise. Each layer is defined by what it is, not by how many
members it has, so a signal can be added later without renegotiating a number.

| Layer | Content | Note |
|---|---|---|
| **Raw facts** | `state_degraded` (the state build returned `None`); agent crash; selection stage / fallback reason; own invalid choice | Observed at the decision, own seat only |
| **Derivation** | `is_degraded_decision()` / `classify_live_outcome()` | Existing functions, unchanged — this slice adds no new definition |
| **Aggregation** | Own per-battle counters | **Never mixed with another seat.** No `hero_`/`villain_` field names on this path |
| **Transport** | `SelectionStageSink` | Already an explicit optional sink parameter |
| **Persistence** | Structured decision-profile rows + a battle-completion record | Under `logs/` |

## 5. Battle boundaries

Taken from the real loop in `runner.py::_run_battle_loop`, not assumed:

- **Start:** `|init|battle` → the room enters `active_battles`.
- **End:** `|win|` or `|tie|` → `battles_finished += 1`, the room leaves `active_battles`, and
  `_room_raw.pop(room)` discards the raw log. **The battle record must be flushed before that
  pop**, which is the point where today's evidence is thrown away.
- **Run end:** `battles_finished >= max_battles` → connection closed, count returned.

**A battle can end without either event.** If the message stream ends — disconnect, server
close, cancelled search — `_run_battle_loop` falls out of its `async for` and returns with
rooms still in `active_battles`. Those battles have no terminal event, so any design that only
flushes on `|win|`/`|tie|` silently loses precisely the battles most likely to have degraded.
Unterminated rooms must be flushed on loop exit and marked as unterminated rather than
completed.

Two further degradation paths already exist in the loop and are currently uncounted:
`|error|` in a battle room, and a `pm` containing `Invalid choice` — both call
`_send_default_choose`. The second fans out to **every** active battle, so attribution must be
per room, not per event.

## 6. Write failures

**A write failure must never block a turn or a battle.** The runner plays real ladder games
against a live server; a blocking write costs the game. Recording is buffered in memory during
the battle and flushed at the boundaries in §5, inside a handler that cannot propagate into the
battle loop.

**But a swallowed write failure is the same defect as no recording at all.** So:

- A flush failure is itself recorded (in memory, and to the logger) and counted.
- At run completion the runner **fails visibly and machine-checkably** if any flush failed —
  a non-zero result and an explicit failure field in the run-completion record, not a warning
  someone has to notice in a log.

The asymmetry is deliberate: silent during play, loud at the end.

## 7. Non-goals

- No new degradation signals beyond the raw facts in §4.
- No threshold changes.
- No automatic abort on degradation. `_abort_on_degradation` checks four counters and stays
  narrower than what is recorded. **Recording and aborting are allowed to differ in breadth** —
  that is this slice's explicit non-goal, not a gap to be closed later by accident.
- No strength claim, and no change to how any decision is chosen. This is a recording slice;
  the choosing behaviour on the live path is untouched.

## 8. What this authorises

A narrow wiring slice against the layered contract in §4, honouring the boundaries in §5 and
the failure policy in §6. It does not authorise harmonising the two choosers (option C in the
asymmetry audit), which remains a separate, unmade decision.

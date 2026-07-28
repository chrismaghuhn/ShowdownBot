# Live-Path Degradation Recording — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `client/runner.py` records `live-degradation-v1` evidence for its own seat on every
ladder, challenge and smoke run, always on, without touching the turn path or the chosen action.

**Base:** `main @ 43f08af` · **Issue:** #125
**Authoritative decision:** `docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md`
(referenced below as §N, **including the merged §8.0 amendment** — the plan implements the
record and adds no rulings of its own).

**Architecture:** one new self-contained module owns the schema, its validators, the writer and the
aggregation. `runner.py` gains call sites only; `cli.py` gains one wrapper. The decision core is
untouched: the existing `SelectionStageSink` already carries `selection_stage`/`fallback_reason`,
and `is_degraded_decision()` / `classify_live_outcome()` are used unchanged, behind the §5.1 gate.

**Tech stack:** Python 3.14, stdlib only (`json`, `os`, `pathlib`, `datetime`, `secrets`), pytest,
`pytest-asyncio` (already used by `tests/test_runner_format_config.py`).

---

## Revision note — what the previous revision got wrong

The revision at `0d45bfb` carried a banner listing six open defects. Two further facts have since
been established by reading the file and the sources, and both are corrected here:

1. **`0d45bfb`'s own commit message overclaimed.** It said the `flush_battle` ordering bug was
   fixed and that `flush_run_events()` had been added. Neither change was in its diff:
   `grep -n "self._decisions.pop"` still found the pop *before* `build_battle_row`, and
   `flush_run_events` appeared only in the banner prose. Both are genuinely implemented in this
   revision (Task 8). The placeholder count at `0d45bfb` was **16**, not the 15 previously stated.
2. **The `|error|` payload as planned was always empty.** `parse_message` sets `payload` only for
   `prefix == "request"` (`protocol/messages.py:26`); for `|error|` the text lives in `args`. The
   previous plan recorded `parsed.payload`, which would have written `""` into every
   `server_error` row — silently losing exactly the evidence §7 requires. Corrected to
   `"|".join(parsed.args)` (Task 9), which reconstructs a payload that itself contains `|`.

Two further defects were found while writing this revision and are fixed here:

3. **Repo-root `logs/` is not gitignored.** `.gitignore:12` covers `showdown_bot/logs/` only, and
   `git check-ignore logs/live-degradation/x/decisions.jsonl` exits 1. An always-on recorder run
   from the repo root would therefore leave untracked evidence in `git status` and contradict
   Task 12 Step 3. Task 3 adds the ignore entry and verifies it.
4. **`run_smoke_battle` never assigns `_active_format`** (`runner.py:264-280`, unlike
   `run_ladder_search:233` and `run_challenge:252`). `book_absent` is still `True` for smoke, so
   §5's consequence holds — but for the additional reason that the format is never set, not only
   because a random format has no book. This is recorded as an observation; changing it is a
   behaviour change and out of scope (C10 / §11).

---

> **STATUS: AWAITING PLAN REVIEW — implementation only after an explicit GO.**
>
> The §8 amendment is **merged** (`main @ 3fad797`, PR #146). This revision is rewritten against
> the final contract, and the "Two additions beyond the decision record" section is gone: after the
> amendment there is no addition beyond the record. What changed here:
>
> 1. `COMPLETION_FIELDS` gains `schema_errors_total` and `recorder_errors_total` (Task 1).
> 2. The recorder's counters are named `schema_errors_total` / `recorder_errors_total`, one-to-one
>    with the persisted fields (Tasks 4–8).
> 3. `validate_completion_row(row, *, expected_run_id=None)` plus mutation tests (Task 2).
> 4. `write_completion()` persists all three counters (Task 8).
> 5. Four separate exit-status tests, not one combined (Task 8).
> 6. The artifact invariant and its two run shapes, plus the parse/validate success condition
>    (Task 8, Task 12).
>
> The plan is complete and self-consistent as far as I can verify it. It has not been executed.
---

## Load-bearing constraints (from the decision record)

These are gates, not preferences. Every task below is written to keep them.

| # | Constraint | Enforced by |
|---|---|---|
| C1 | No filesystem access on the turn path | Tasks 5/6 buffer in memory; Task 8 flushes only at boundaries. Validation is pure in-memory field checking and performs no IO |
| C2 | No latency bound claimed at the boundary flush | Task 8 docstring; no timeout, no assertion of one |
| C3 | No background writer | Single-threaded module; no `threading`, no `asyncio.to_thread` |
| C4 | No automatic degradation abort | Nothing in the module raises on a degraded count |
| C5 | No new chooser fallback | Task 9 re-raises the caught exception unchanged |
| C6 | Decision-profile schema untouched | New module; imports only the two derivation functions and the reason vocabulary from `eval/decision_profile`, never its writers |
| C7 | No `hero_`/`villain_` fields | Task 1 schema test asserts absence |
| C8 | `unattributed` events increment no battle counter | Task 7 predicate + Task 7 test |
| C9 | Existing evidence never overwritten | Task 4 `exist_ok=False`; append-only `_append_jsonl`; exclusive `_write_json_exclusive` |
| C10 | No strength or production-readiness claim | Docs only assert recording |
| C11 | A recorder or validator failure never prevents the chosen action being sent | Task 9: the send happens **before** the record call, **and** the record call is guarded |

---

## File structure

| File | Responsibility |
|---|---|
| **Create** `showdown_bot/src/showdown_bot/client/live_degradation.py` | Schema constants, validators, row builders, `LiveDegradationRecorder` (preflight, buffers, flush, counters, exit status) |
| **Modify** `showdown_bot/src/showdown_bot/client/runner.py` | Call sites only: preflight, decision record, event record, boundary flush, `finally`, `recorder_exit_status()` |
| **Modify** `showdown_bot/src/showdown_bot/cli.py` | One `_run_live` wrapper around the three live commands |
| **Modify** `showdown_bot/src/showdown_bot/eval/config_env.py` | Add `SHOWDOWN_LIVE_DEGRADATION_DIR` to `NON_BEHAVIORAL` |
| **Modify** `.gitignore` | Ignore `logs/live-degradation/` |
| **Create** `showdown_bot/tests/test_live_degradation.py` | Schema, validators + mutation tests, recorder, counters, preflight, write failures |
| **Create** `showdown_bot/tests/test_live_degradation_runner.py` | Runner wiring, boundaries, `finally`, CLI exit status, smoke |

---

## Task 1: Schema constants and the closed field set

**Files:** Create `showdown_bot/src/showdown_bot/client/live_degradation.py`;
create `showdown_bot/tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing test**

Create `showdown_bot/tests/test_live_degradation.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.client.live_degradation import (
    ATTRIBUTIONS,
    BATTLE_FIELDS,
    COMPLETION_FIELDS,
    DECISION_FIELDS,
    END_REASONS,
    EVENT_FIELDS,
    EVENT_TYPES,
    OUTCOMES,
    SCHEMA_VERSION,
)


def test_schema_version_literal():
    assert SCHEMA_VERSION == "live-degradation-v1"


def test_decision_fields_are_exactly_the_contract():
    assert DECISION_FIELDS == (
        "schema_version", "run_id", "room_id", "decision_seq", "rqid",
        "book_absent", "team_preview", "state_build_failed",
        "selection_stage", "fallback_reason", "agent_crash_type",
        "derivation_applicable", "is_degraded", "outcome",
    )


def test_battle_fields_are_exactly_the_contract():
    assert BATTLE_FIELDS == (
        "schema_version", "run_id", "room_id", "decisions_total",
        "decisions_not_applicable", "degraded_decisions", "state_build_failures",
        "agent_crashes", "fallback_decisions", "own_invalid_choices",
        "server_errors", "end_reason", "write_errors",
    )


def test_event_fields_are_exactly_the_contract():
    assert EVENT_FIELDS == (
        "schema_version", "run_id", "event_type", "attribution",
        "room_id", "payload", "active_battle_count",
    )


def test_completion_fields_are_exactly_the_contract():
    assert COMPLETION_FIELDS == (
        "schema_version", "run_id", "battles_finished", "unterminated_rooms",
        "write_errors_total", "schema_errors_total", "recorder_errors_total",
        "preflight_ok",
    )


def test_vocabularies_are_closed():
    assert EVENT_TYPES == ("server_error", "invalid_choice_pm")
    assert ATTRIBUTIONS == ("room", "inferred", "unattributed")
    assert END_REASONS == ("win", "tie", "unterminated")
    assert OUTCOMES == ("ok", "crash", "fallback", "degraded_state", "not_applicable")


def test_outcomes_extend_the_existing_vocabulary_by_exactly_one_value():
    """OUTCOMES must be the four existing decision-profile outcomes plus the single
    gate value from 5.1 -- not a second, drifting vocabulary (C6)."""
    from showdown_bot.eval import decision_profile

    assert set(OUTCOMES) - set(decision_profile._OUTCOMES) == {"not_applicable"}
    assert set(decision_profile._OUTCOMES) - set(OUTCOMES) == set()


def test_no_hero_or_villain_field_anywhere():
    """C7: the live runner holds one seat; hero_/villain_ names would be
    structurally always zero and read as 'clean' rather than 'not observable'."""
    every = DECISION_FIELDS + EVENT_FIELDS + BATTLE_FIELDS + COMPLETION_FIELDS
    assert not [f for f in every if f.startswith(("hero_", "villain_"))]
```

- [ ] **Step 2: Run it, expect a collection error**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

Expected: `ModuleNotFoundError: No module named 'showdown_bot.client.live_degradation'`

- [ ] **Step 3: Implement the constants**

Create `showdown_bot/src/showdown_bot/client/live_degradation.py`:

```python
"""live-degradation-v1: own-seat degradation evidence for the live runner.

Implements docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md.
Deliberately independent of eval/decision_profile's CLOSED schema (section 8, C6): this module
imports that module's two derivation functions and its fallback-reason vocabulary, and nothing
else. It never writes a decision-profile row.
"""
from __future__ import annotations

SCHEMA_VERSION = "live-degradation-v1"

DECISION_FIELDS = (
    "schema_version", "run_id", "room_id", "decision_seq", "rqid",
    "book_absent", "team_preview", "state_build_failed",
    "selection_stage", "fallback_reason", "agent_crash_type",
    "derivation_applicable", "is_degraded", "outcome",
)
EVENT_FIELDS = (
    "schema_version", "run_id", "event_type", "attribution",
    "room_id", "payload", "active_battle_count",
)
BATTLE_FIELDS = (
    "schema_version", "run_id", "room_id", "decisions_total",
    "decisions_not_applicable", "degraded_decisions", "state_build_failures",
    "agent_crashes", "fallback_decisions", "own_invalid_choices",
    "server_errors", "end_reason", "write_errors",
)
COMPLETION_FIELDS = (
    "schema_version", "run_id", "battles_finished", "unterminated_rooms",
    "write_errors_total", "schema_errors_total", "recorder_errors_total",
    "preflight_ok",
)

EVENT_TYPES = ("server_error", "invalid_choice_pm")
ATTRIBUTIONS = ("room", "inferred", "unattributed")
END_REASONS = ("win", "tie", "unterminated")

# The four EXISTING classify_live_outcome values plus the single gate value from 5.1.
# Not a second vocabulary -- test_outcomes_extend_the_existing_vocabulary_by_exactly_one_value
# pins it against decision_profile._OUTCOMES so the two can never drift apart.
OUTCOMES = ("ok", "crash", "fallback", "degraded_state", "not_applicable")
```

- [ ] **Step 4: Run, expect 8 passed**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: live-degradation-v1 schema constants and closed vocabularies"
```

---

## Task 2: Validators and mutation tests

Field-name tuples do not close a schema. These three validators are the closure: field set **and
order**, types, enum membership, null rules and cross-field consistency. They are pure — no IO —
so they may run at record time without breaking C1.

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
from showdown_bot.client.live_degradation import (  # noqa: E402
    SchemaError,
    validate_battle_row,
    validate_completion_row,
    validate_decision_row,
    validate_event_row,
)

VALID_DECISION = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "room_id": "battle-gen9vgc2025regg-1", "decision_seq": 0, "rqid": 7,
    "book_absent": False, "team_preview": False, "state_build_failed": False,
    "selection_stage": "heuristic", "fallback_reason": None, "agent_crash_type": None,
    "derivation_applicable": True, "is_degraded": False, "outcome": "ok",
}

VALID_EVENT = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "event_type": "server_error", "attribution": "room",
    "room_id": "battle-gen9vgc2025regg-1",
    "payload": "[Invalid choice] Can't move: Zamazenta needs a target",
    "active_battle_count": 2,
}

VALID_BATTLE = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "room_id": "battle-gen9vgc2025regg-1", "decisions_total": 10,
    "decisions_not_applicable": 1, "degraded_decisions": 2, "state_build_failures": 1,
    "agent_crashes": 0, "fallback_decisions": 1, "own_invalid_choices": 0,
    "server_errors": 1, "end_reason": "win", "write_errors": 0,
}


def _mutate(base: dict, **changes) -> dict:
    """Replace values IN PLACE of the original keys, preserving insertion order."""
    out = dict(base)
    out.update(changes)
    return out


def test_the_three_valid_rows_pass():
    validate_decision_row(dict(VALID_DECISION))
    validate_event_row(dict(VALID_EVENT))
    validate_battle_row(dict(VALID_BATTLE))


# --- decision-row mutations -------------------------------------------------

def _decision_without(key: str) -> dict:
    out = dict(VALID_DECISION)
    del out[key]
    return out


def _decision_reordered() -> dict:
    keys = list(VALID_DECISION)
    keys[0], keys[1] = keys[1], keys[0]
    return {k: VALID_DECISION[k] for k in keys}


DECISION_MUTATIONS = [
    ("missing_field", _decision_without("rqid")),
    ("extra_field", _mutate(VALID_DECISION, hero_wins=1)),
    ("wrong_order", _decision_reordered()),
    ("wrong_schema_version", _mutate(VALID_DECISION, schema_version="live-degradation-v2")),
    ("empty_run_id", _mutate(VALID_DECISION, run_id="")),
    ("empty_room_id", _mutate(VALID_DECISION, room_id="")),
    ("seq_is_bool", _mutate(VALID_DECISION, decision_seq=True)),
    ("seq_negative", _mutate(VALID_DECISION, decision_seq=-1)),
    ("rqid_is_str", _mutate(VALID_DECISION, rqid="7")),
    ("book_absent_is_int", _mutate(VALID_DECISION, book_absent=1)),
    ("stage_empty_string", _mutate(VALID_DECISION, selection_stage="")),
    ("unknown_outcome", _mutate(VALID_DECISION, outcome="weird")),
    ("is_degraded_is_str", _mutate(VALID_DECISION, is_degraded="yes")),
    # cross-field
    ("gate_disagrees_with_book_absent",
     _mutate(VALID_DECISION, book_absent=True)),
    ("gate_disagrees_with_team_preview",
     _mutate(VALID_DECISION, team_preview=True)),
    ("not_applicable_outcome_while_gate_true",
     _mutate(VALID_DECISION, outcome="not_applicable")),
    ("gate_false_but_is_degraded_is_false",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             selection_stage=None, outcome="not_applicable", is_degraded=False)),
    ("gate_false_but_stage_set",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             outcome="not_applicable", is_degraded=None)),
    ("gate_true_but_is_degraded_null",
     _mutate(VALID_DECISION, is_degraded=None)),
    ("crash_type_without_crash_outcome",
     _mutate(VALID_DECISION, agent_crash_type="ValueError")),
    ("crash_outcome_without_crash_type",
     _mutate(VALID_DECISION, outcome="crash", is_degraded=True)),
    ("state_build_failed_not_degraded",
     _mutate(VALID_DECISION, state_build_failed=True)),
    ("state_build_failed_while_gate_false",
     _mutate(VALID_DECISION, book_absent=True, derivation_applicable=False,
             state_build_failed=True, selection_stage=None, is_degraded=None,
             outcome="not_applicable")),
    ("fallback_reason_without_stage",
     _mutate(VALID_DECISION, selection_stage=None, fallback_reason="heuristic_timeout",
             is_degraded=True, outcome="fallback")),
    ("unknown_fallback_reason",
     _mutate(VALID_DECISION, selection_stage="max_damage_fallback",
             fallback_reason="made_up", is_degraded=True, outcome="fallback")),
]


@pytest.mark.parametrize("label,row", DECISION_MUTATIONS, ids=[m[0] for m in DECISION_MUTATIONS])
def test_decision_mutation_is_rejected(label, row):
    with pytest.raises(SchemaError):
        validate_decision_row(dict(row))


# --- event-row mutations ----------------------------------------------------

def _event_without(key: str) -> dict:
    out = dict(VALID_EVENT)
    del out[key]
    return out


EVENT_MUTATIONS = [
    ("missing_field", _event_without("payload")),
    ("extra_field", _mutate(VALID_EVENT, villain_errors=1)),
    ("unknown_event_type", _mutate(VALID_EVENT, event_type="disconnect")),
    ("unknown_attribution", _mutate(VALID_EVENT, attribution="guess")),
    ("payload_is_none", _mutate(VALID_EVENT, payload=None)),
    ("count_is_negative", _mutate(VALID_EVENT, active_battle_count=-1)),
    ("count_is_bool", _mutate(VALID_EVENT, active_battle_count=True)),
    ("room_attribution_without_room",
     _mutate(VALID_EVENT, room_id=None)),
    ("unattributed_with_a_room",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="unattributed")),
    ("inferred_without_a_room",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="inferred",
             room_id=None, active_battle_count=1)),
    ("inferred_with_two_active_battles",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="inferred",
             active_battle_count=2)),
    ("server_error_marked_inferred",
     _mutate(VALID_EVENT, attribution="inferred", active_battle_count=1)),
    ("pm_marked_room",
     _mutate(VALID_EVENT, event_type="invalid_choice_pm", attribution="room")),
]


@pytest.mark.parametrize("label,row", EVENT_MUTATIONS, ids=[m[0] for m in EVENT_MUTATIONS])
def test_event_mutation_is_rejected(label, row):
    with pytest.raises(SchemaError):
        validate_event_row(dict(row))


# --- battle-row mutations ---------------------------------------------------

def _battle_without(key: str) -> dict:
    out = dict(VALID_BATTLE)
    del out[key]
    return out


BATTLE_MUTATIONS = [
    ("missing_field", _battle_without("write_errors")),
    ("extra_field", _mutate(VALID_BATTLE, hero_invalid_total=0)),
    ("unknown_end_reason", _mutate(VALID_BATTLE, end_reason="aborted")),
    ("negative_counter", _mutate(VALID_BATTLE, server_errors=-1)),
    ("counter_is_bool", _mutate(VALID_BATTLE, agent_crashes=True)),
    ("counter_is_float", _mutate(VALID_BATTLE, decisions_total=10.0)),
    ("not_applicable_exceeds_total",
     _mutate(VALID_BATTLE, decisions_not_applicable=11)),
    ("degraded_plus_not_applicable_exceeds_total",
     _mutate(VALID_BATTLE, decisions_not_applicable=9, degraded_decisions=2)),
    ("state_build_failures_exceed_degraded",
     _mutate(VALID_BATTLE, state_build_failures=3)),
    ("fallback_exceeds_degraded",
     _mutate(VALID_BATTLE, fallback_decisions=3)),
]


@pytest.mark.parametrize("label,row", BATTLE_MUTATIONS, ids=[m[0] for m in BATTLE_MUTATIONS])
def test_battle_mutation_is_rejected(label, row):
    with pytest.raises(SchemaError):
        validate_battle_row(dict(row))


# --- completion mutations (section 8.0) ----------------------------------------

VALID_COMPLETION = {
    "schema_version": "live-degradation-v1", "run_id": "20260729T101112Z-a1b2c3",
    "battles_finished": 3, "unterminated_rooms": ["battle-gen9vgc2025regg-9"],
    "write_errors_total": 0, "schema_errors_total": 0, "recorder_errors_total": 0,
    "preflight_ok": True,
}


def _completion_without(key: str) -> dict:
    out = dict(VALID_COMPLETION)
    del out[key]
    return out


COMPLETION_MUTATIONS = [
    ("missing_field", _completion_without("recorder_errors_total")),
    ("extra_field", _mutate(VALID_COMPLETION, recording_ok=True)),
    ("wrong_schema_version", _mutate(VALID_COMPLETION, schema_version="v2")),
    ("empty_run_id", _mutate(VALID_COMPLETION, run_id="")),
    ("battles_finished_is_bool", _mutate(VALID_COMPLETION, battles_finished=True)),
    ("battles_finished_negative", _mutate(VALID_COMPLETION, battles_finished=-1)),
    ("counter_is_bool", _mutate(VALID_COMPLETION, schema_errors_total=True)),
    ("counter_negative", _mutate(VALID_COMPLETION, recorder_errors_total=-1)),
    ("counter_is_str", _mutate(VALID_COMPLETION, write_errors_total="0")),
    ("unterminated_is_not_a_list", _mutate(VALID_COMPLETION, unterminated_rooms="r")),
    ("unterminated_holds_a_non_string", _mutate(VALID_COMPLETION, unterminated_rooms=[1])),
    ("unterminated_holds_an_empty_string", _mutate(VALID_COMPLETION, unterminated_rooms=[""])),
    ("unterminated_has_duplicates", _mutate(VALID_COMPLETION, unterminated_rooms=["a", "a"])),
    ("preflight_ok_false", _mutate(VALID_COMPLETION, preflight_ok=False)),
    ("preflight_ok_is_int", _mutate(VALID_COMPLETION, preflight_ok=1)),
]


@pytest.mark.parametrize("label,row", COMPLETION_MUTATIONS,
                         ids=[m[0] for m in COMPLETION_MUTATIONS])
def test_completion_mutation_is_rejected(label, row):
    with pytest.raises(SchemaError):
        validate_completion_row(dict(row))


def test_completion_run_id_is_checked_only_when_an_expectation_is_supplied():
    """The validator sees ONE object. It cannot reach the other three files, and passing the
    recorder's own run_id proves only self-consistency -- section 8.0 says so explicitly. The
    cross-file property is the artifact invariant, tested separately in Task 12."""
    validate_completion_row(dict(VALID_COMPLETION))                       # no expectation
    validate_completion_row(dict(VALID_COMPLETION),
                            expected_run_id="20260729T101112Z-a1b2c3")    # matching
    with pytest.raises(SchemaError, match="expected_run_id"):
        validate_completion_row(dict(VALID_COMPLETION), expected_run_id="someone-elses-run")
```

- [ ] **Step 2: Run, expect an ImportError**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

Expected: `ImportError: cannot import name 'SchemaError' from 'showdown_bot.client.live_degradation'`

- [ ] **Step 3: Implement the validators**

Append to `live_degradation.py`, after the constants:

```python
from showdown_bot.eval.decision_profile import KNOWN_FALLBACK_REASONS


class SchemaError(ValueError):
    """A row this module built does not satisfy live-degradation-v1.

    This is a DEFECT signal, not an expected runtime condition: every row is built by this
    module from its own inputs. It is raised by the validators only; the recorder catches it,
    counts it and refuses to buffer the row, so it can never reach a battle (C11).
    """


def _require_shape(row: dict, fields: tuple[str, ...], what: str) -> None:
    """Field set AND ORDER. Order matters because the JSONL is read positionally by eye and
    diffed line-by-line; a reordered row is a different artifact even if it parses the same."""
    actual = tuple(row)
    if actual != fields:
        missing = [f for f in fields if f not in row]
        extra = [f for f in actual if f not in fields]
        raise SchemaError(
            f"{what}: field set/order mismatch; missing={missing} extra={extra} "
            f"actual={list(actual)}"
        )
    if row["schema_version"] != SCHEMA_VERSION:
        raise SchemaError(f"{what}: schema_version={row['schema_version']!r}")
    if not isinstance(row["run_id"], str) or not row["run_id"]:
        raise SchemaError(f"{what}: run_id must be a non-empty str, got {row['run_id']!r}")


def _is_int(value: object) -> bool:
    """bool is a subclass of int; True must never pass as a counter or a sequence number."""
    return isinstance(value, int) and not isinstance(value, bool)


def _require_bool(row: dict, key: str, what: str) -> None:
    if not isinstance(row[key], bool):
        raise SchemaError(f"{what}: {key} must be bool, got {row[key]!r}")


def _require_str_or_none(row: dict, key: str, what: str) -> None:
    value = row[key]
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise SchemaError(
            f"{what}: {key} must be a non-empty str or None (no sentinel or empty "
            f"strings, section 8 null rules), got {value!r}"
        )


def _require_count(row: dict, key: str, what: str) -> None:
    if not _is_int(row[key]) or row[key] < 0:
        raise SchemaError(f"{what}: {key} must be a non-negative int, got {row[key]!r}")


def validate_decision_row(row: dict) -> None:
    what = "decision row"
    _require_shape(row, DECISION_FIELDS, what)

    if not isinstance(row["room_id"], str) or not row["room_id"]:
        raise SchemaError(f"{what}: room_id must be a non-empty str, got {row['room_id']!r}")
    _require_count(row, "decision_seq", what)
    if row["rqid"] is not None and not _is_int(row["rqid"]):
        raise SchemaError(f"{what}: rqid must be int or None, got {row['rqid']!r}")
    for key in ("book_absent", "team_preview", "state_build_failed", "derivation_applicable"):
        _require_bool(row, key, what)
    for key in ("selection_stage", "fallback_reason", "agent_crash_type"):
        _require_str_or_none(row, key, what)
    if row["is_degraded"] is not None and not isinstance(row["is_degraded"], bool):
        raise SchemaError(f"{what}: is_degraded must be bool or None, got {row['is_degraded']!r}")
    if row["outcome"] not in OUTCOMES:
        raise SchemaError(f"{what}: outcome={row['outcome']!r} not in {OUTCOMES}")

    applicable = row["derivation_applicable"]
    expected = (not row["book_absent"]) and (not row["team_preview"])
    if applicable != expected:
        raise SchemaError(
            f"{what}: derivation_applicable={applicable} contradicts the section 5.1 rule "
            f"(not book_absent and not team_preview) = {expected}"
        )

    if not applicable:
        if row["is_degraded"] is not None:
            raise SchemaError(
                f"{what}: gate false requires is_degraded=None ('not asked' is not "
                f"'not degraded'), got {row['is_degraded']!r}"
            )
        if row["outcome"] != "not_applicable":
            raise SchemaError(f"{what}: gate false requires outcome='not_applicable'")
        if row["selection_stage"] is not None:
            raise SchemaError(
                f"{what}: gate false requires selection_stage=None (section 8 null rules)"
            )
        if row["state_build_failed"]:
            raise SchemaError(
                f"{what}: state_build_failed=True is impossible with the gate false -- the "
                f"build is only ATTEMPTED when a book exists and it is not team preview"
            )
    else:
        if not isinstance(row["is_degraded"], bool):
            raise SchemaError(f"{what}: gate true requires a bool is_degraded")
        if row["outcome"] == "not_applicable":
            raise SchemaError(f"{what}: outcome='not_applicable' requires the gate to be false")
        crashed = row["agent_crash_type"] is not None
        if crashed and row["outcome"] != "crash":
            raise SchemaError(f"{what}: agent_crash_type set but outcome={row['outcome']!r}")
        if row["outcome"] == "crash" and not crashed:
            raise SchemaError(f"{what}: outcome='crash' requires agent_crash_type")
        if (crashed or row["state_build_failed"]) and row["is_degraded"] is not True:
            raise SchemaError(
                f"{what}: crashed/state_build_failed dominate and force is_degraded=True"
            )

    if row["fallback_reason"] is not None:
        if row["selection_stage"] is None:
            raise SchemaError(
                f"{what}: fallback_reason without a selection_stage -- _mark_selection always "
                f"writes both together"
            )
        if row["fallback_reason"] not in KNOWN_FALLBACK_REASONS:
            raise SchemaError(
                f"{what}: fallback_reason={row['fallback_reason']!r} not in "
                f"{sorted(KNOWN_FALLBACK_REASONS)}"
            )


def validate_event_row(row: dict) -> None:
    what = "event row"
    _require_shape(row, EVENT_FIELDS, what)

    if row["event_type"] not in EVENT_TYPES:
        raise SchemaError(f"{what}: event_type={row['event_type']!r} not in {EVENT_TYPES}")
    if row["attribution"] not in ATTRIBUTIONS:
        raise SchemaError(f"{what}: attribution={row['attribution']!r} not in {ATTRIBUTIONS}")
    if not isinstance(row["payload"], str):
        raise SchemaError(f"{what}: payload must be a str, got {row['payload']!r}")
    _require_count(row, "active_battle_count", what)
    _require_str_or_none(row, "room_id", what)

    attribution = row["attribution"]
    if attribution == "unattributed":
        if row["room_id"] is not None:
            raise SchemaError(
                f"{what}: attribution='unattributed' requires room_id=None -- charging an "
                f"unattributable event to a room would manufacture degradation (C8)"
            )
    elif row["room_id"] is None:
        raise SchemaError(f"{what}: attribution={attribution!r} requires a room_id")

    if row["event_type"] == "server_error" and attribution != "room":
        raise SchemaError(
            f"{what}: |error| is room-scoped by construction; attribution={attribution!r}"
        )
    if row["event_type"] == "invalid_choice_pm":
        if attribution == "room":
            raise SchemaError(
                f"{what}: the invalid-choice PM carries no room; 'room' attribution is never "
                f"available for it (section 7)"
            )
        if attribution == "inferred" and row["active_battle_count"] != 1:
            raise SchemaError(
                f"{what}: 'inferred' is permitted only when exactly one battle is active, "
                f"got active_battle_count={row['active_battle_count']}"
            )


def validate_completion_row(row: dict, *, expected_run_id: str | None = None) -> None:
    """Validate the single completion object (section 8.0).

    `expected_run_id` is optional and proves only that the caller and the row agree. It does
    NOT establish the cross-file identity -- a validator handed one object cannot see the other
    three files, and the recorder's own run_id shares a source with this row. That property is
    the ARTIFACT INVARIANT and has its own integration test (Task 12).
    """
    what = "completion row"
    _require_shape(row, COMPLETION_FIELDS, what)

    _require_count(row, "battles_finished", what)
    for key in ("write_errors_total", "schema_errors_total", "recorder_errors_total"):
        _require_count(row, key, what)

    rooms = row["unterminated_rooms"]
    if not isinstance(rooms, list):
        raise SchemaError(f"{what}: unterminated_rooms must be a list, got {rooms!r}")
    for room in rooms:
        if not isinstance(room, str) or not room:
            raise SchemaError(f"{what}: unterminated_rooms holds {room!r}")
    if len(set(rooms)) != len(rooms):
        raise SchemaError(f"{what}: unterminated_rooms has duplicates: {rooms!r}")

    if row["preflight_ok"] is not True:
        raise SchemaError(
            f"{what}: preflight_ok must be True -- this file can only be written after preflight "
            f"succeeded (section 10.1), so {row['preflight_ok']!r} is a defect, not a state"
        )

    if expected_run_id is not None and row["run_id"] != expected_run_id:
        raise SchemaError(
            f"{what}: run_id={row['run_id']!r} does not match expected_run_id="
            f"{expected_run_id!r}"
        )


def validate_battle_row(row: dict) -> None:
    what = "battle row"
    _require_shape(row, BATTLE_FIELDS, what)

    if not isinstance(row["room_id"], str) or not row["room_id"]:
        raise SchemaError(f"{what}: room_id must be a non-empty str, got {row['room_id']!r}")
    for key in (
        "decisions_total", "decisions_not_applicable", "degraded_decisions",
        "state_build_failures", "agent_crashes", "fallback_decisions",
        "own_invalid_choices", "server_errors", "write_errors",
    ):
        _require_count(row, key, what)
    if row["end_reason"] not in END_REASONS:
        raise SchemaError(f"{what}: end_reason={row['end_reason']!r} not in {END_REASONS}")

    total = row["decisions_total"]
    not_applicable = row["decisions_not_applicable"]
    degraded = row["degraded_decisions"]
    if not_applicable > total:
        raise SchemaError(f"{what}: decisions_not_applicable {not_applicable} > total {total}")
    if not_applicable + degraded > total:
        raise SchemaError(
            f"{what}: not_applicable {not_applicable} + degraded {degraded} > total {total} -- "
            f"a not_applicable row has is_degraded=None and is counted by neither the other"
        )
    # state_build_failed and a fallback stage each FORCE is_degraded=True, so both are
    # subsets of degraded_decisions. agent_crashes deliberately is NOT: a crash on the
    # book-absent path (smoke) has the gate false and therefore is_degraded=None.
    if row["state_build_failures"] > degraded:
        raise SchemaError(
            f"{what}: state_build_failures {row['state_build_failures']} > degraded {degraded}"
        )
    if row["fallback_decisions"] > degraded:
        raise SchemaError(
            f"{what}: fallback_decisions {row['fallback_decisions']} > degraded {degraded}"
        )
```

- [ ] **Step 4: Run, expect 8 + 1 + 25 + 13 + 10 + 15 + 1 = 73 passed**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: live-degradation-v1 validators with mutation tests"
```

---

## Task 3: `SHOWDOWN_LIVE_DEGRADATION_DIR` classification and the gitignore entry

**Files:** Modify `showdown_bot/src/showdown_bot/eval/config_env.py`; modify `.gitignore`;
add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
def test_live_degradation_dir_is_non_behavioural():
    """It is an IO path with no /choose effect. is_excluded fails closed toward
    INCLUSION, so leaving it unclassified would put the telemetry path into
    config_hash -- choosing where to write would change the identity of the run
    being measured."""
    from showdown_bot.eval.config_env import (
        NON_BEHAVIORAL, behavior_env, is_classified, is_excluded,
    )

    name = "SHOWDOWN_LIVE_DEGRADATION_DIR"
    assert name in NON_BEHAVIORAL
    assert is_classified(name)
    assert is_excluded(name)
    assert behavior_env({name: "X:/anywhere"}) == {}


def test_run_directory_is_gitignored():
    """The recorder is ALWAYS ON and writes under the repo root by default. .gitignore:12
    covers showdown_bot/logs/ only, so without this entry every run would leave untracked
    evidence in git status and break the Task 12 hygiene check."""
    import subprocess

    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["git", "check-ignore", "--", "logs/live-degradation/20260729T000000Z-abc123/decisions.jsonl"],
        cwd=root, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        "logs/live-degradation/ is not ignored; git check-ignore said: "
        f"rc={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}"
    )
```

- [ ] **Step 2: Run, expect two failures**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q -k "non_behavioural or gitignored"
```

Expected: an `AssertionError` on `'SHOWDOWN_LIVE_DEGRADATION_DIR' in NON_BEHAVIORAL` and the
gitignore assertion message.

- [ ] **Step 3a: Implement the classification**

In `showdown_bot/src/showdown_bot/eval/config_env.py`, directly after the
`"SHOWDOWN_DECISION_PROFILE_OUT",` entry (line 126):

```python
    # Live-path degradation sink DIRECTORY (live-degradation-v1). Same species as
    # SHOWDOWN_DECISION_PROFILE_OUT above: an IO path with no /choose effect. It must be
    # classified, not merely commented -- is_excluded fails closed toward INCLUSION, so an
    # unclassified name lands in behavior_env and thus in config_hash, and merely choosing
    # where to write telemetry would change the identity of the run being measured.
    "SHOWDOWN_LIVE_DEGRADATION_DIR",
```

- [ ] **Step 3b: Implement the gitignore entry**

Append to `.gitignore`:

```
# live-degradation-v1 run directories (always-on live-path evidence, written under the
# CWD of the runner). .gitignore's showdown_bot/logs/ entry does not cover the repo root,
# where the ladder/challenge/smoke commands are run from.
logs/live-degradation/
```

- [ ] **Step 4: Run the new tests and the drift test**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py showdown_bot/tests/test_config_env.py -q
```

Expected: all pass. `test_every_showdown_env_read_is_classified`
(`tests/test_config_env.py:272`) must stay green — it asserts every `SHOWDOWN_*` read in source
is classified, and Task 4 adds the read.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/config_env.py .gitignore showdown_bot/tests/test_live_degradation.py
git commit -m "feat: classify SHOWDOWN_LIVE_DEGRADATION_DIR and ignore its run directories"
```

---

## Task 4: Run directory, environment override and writer preflight (§8.1, §10.1, C9)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
from showdown_bot.client.live_degradation import (  # noqa: E402
    DEFAULT_PARENT,
    DIR_ENV,
    LiveDegradationRecorder,
    PreflightError,
    resolve_parent,
)


def test_preflight_creates_an_exclusive_run_dir(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert rec.run_dir.parent == tmp_path
    assert rec.run_dir.is_dir()
    assert rec.run_dir.name == rec.run_id


def test_preflight_refuses_an_existing_run_dir(tmp_path, monkeypatch):
    """C9: a new run must never reuse or overwrite existing evidence."""
    monkeypatch.setattr(
        "showdown_bot.client.live_degradation._new_run_id", lambda: "fixed-run-id")
    LiveDegradationRecorder.preflight(parent=tmp_path)
    with pytest.raises(PreflightError, match="already exists"):
        LiveDegradationRecorder.preflight(parent=tmp_path)


def test_preflight_fails_when_the_parent_is_not_a_directory(tmp_path):
    target = tmp_path / "not-a-dir"
    target.write_text("blocking file", encoding="utf-8")
    with pytest.raises(PreflightError):
        LiveDegradationRecorder.preflight(parent=target)


def test_preflight_probe_is_removed_and_the_dir_is_left_empty(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert list(rec.run_dir.iterdir()) == []


def test_preflight_fails_when_the_probe_cannot_be_written(tmp_path, monkeypatch):
    real_open = open

    def _refuse(path, mode="r", *args, **kwargs):
        if str(path).endswith(".probe"):
            raise OSError("read-only filesystem")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("showdown_bot.client.live_degradation.open", _refuse, raising=False)
    with pytest.raises(PreflightError, match="probe"):
        LiveDegradationRecorder.preflight(parent=tmp_path)


# --- the environment override gets its own tests ----------------------------

def test_default_parent_when_the_override_is_unset(monkeypatch):
    monkeypatch.delenv(DIR_ENV, raising=False)
    assert resolve_parent() == DEFAULT_PARENT
    assert DEFAULT_PARENT == Path("logs") / "live-degradation"


def test_env_override_replaces_the_parent_only(tmp_path, monkeypatch):
    """8.1: the override replaces the PARENT; the <run_id> subdirectory is still
    created beneath it."""
    monkeypatch.setenv(DIR_ENV, str(tmp_path / "custom-sink"))
    rec = LiveDegradationRecorder.preflight()
    assert rec.run_dir.parent == tmp_path / "custom-sink"
    assert rec.run_dir.name == rec.run_id
    assert rec.run_dir.is_dir()


def test_env_override_empty_string_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv(DIR_ENV, "")
    assert resolve_parent() == DEFAULT_PARENT


def test_explicit_parent_wins_over_the_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(DIR_ENV, str(tmp_path / "env-sink"))
    rec = LiveDegradationRecorder.preflight(parent=tmp_path / "explicit-sink")
    assert rec.run_dir.parent == tmp_path / "explicit-sink"
    assert not (tmp_path / "env-sink").exists()


def test_the_override_is_the_only_environment_read_in_the_module():
    """The drift test in test_config_env.py scans source for SHOWDOWN_* reads. Keeping this
    module to exactly one environment read keeps that scan unambiguous, and keeps the
    always-on guarantee honest: no second variable can quietly gate recording."""
    module_path = Path(
        LiveDegradationRecorder.__module__.replace(".", "/") + ".py")
    root = Path(__file__).resolve().parents[1] / "src"
    text = (root / module_path).read_text(encoding="utf-8")
    assert text.count("os.environ") == 1
    assert "os.environ.get(DIR_ENV)" in text
    assert 'DIR_ENV = "SHOWDOWN_LIVE_DEGRADATION_DIR"' in text
```

- [ ] **Step 2: Run, expect an ImportError**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

Expected: `ImportError: cannot import name 'DEFAULT_PARENT' from 'showdown_bot.client.live_degradation'`

- [ ] **Step 3: Implement**

Add to the imports at the top of `live_degradation.py` (module level — an import inside
`record_decision` would put a filesystem read on the turn path, C1):

```python
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from showdown_bot.eval.decision_profile import classify_live_outcome, is_degraded_decision

logger = logging.getLogger(__name__)

DEFAULT_PARENT = Path("logs") / "live-degradation"
DIR_ENV = "SHOWDOWN_LIVE_DEGRADATION_DIR"
```

Then append:

```python
class PreflightError(RuntimeError):
    """The sink could not be established. Raised BEFORE connect/search (section 10.1)."""


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def resolve_parent(explicit: Path | None = None) -> Path:
    """An explicit parent wins; then the override; then the default. An EMPTY override is
    treated as unset -- an empty string would otherwise resolve to the current directory."""
    if explicit is not None:
        return Path(explicit)
    override = os.environ.get(DIR_ENV)
    return Path(override) if override else DEFAULT_PARENT


class LiveDegradationRecorder:
    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.write_errors_total = 0
        self.schema_errors_total = 0
        self.recorder_errors_total = 0
        self.battles_finished = 0
        self.unterminated_rooms: list[str] = []
        self._decisions: dict[str, list[dict]] = {}
        self._events: list[dict] = []
        self._room_write_errors: dict[str, int] = {}
        self._seq: dict[str, int] = {}

    @classmethod
    def preflight(cls, *, parent: Path | None = None) -> "LiveDegradationRecorder":
        """Create the run directory exclusively and prove the writer works.

        Called BEFORE _connect_and_login and before any /search or challenge (section 10.1).
        This is the ONE place a recording failure may stop the run: nothing has been played,
        so aborting costs nothing, whereas an unwritable sink discovered after 50 ladder games
        costs all 50 games' evidence.
        """
        base = resolve_parent(parent)
        run_id = _new_run_id()
        run_dir = base / run_id
        try:
            os.makedirs(run_dir, exist_ok=False)
        except FileExistsError as exc:
            raise PreflightError(f"run directory already exists: {run_dir}") from exc
        except OSError as exc:
            raise PreflightError(f"cannot create run directory {run_dir}: {exc}") from exc
        probe = run_dir / ".probe"
        try:
            with open(probe, "x", encoding="utf-8") as fh:
                fh.write("probe")
                fh.flush()
                os.fsync(fh.fileno())
            os.remove(probe)
        except OSError as exc:
            raise PreflightError(f"writer probe failed in {run_dir}: {exc}") from exc
        return cls(run_dir, run_id)
```

- [ ] **Step 4: Run, expect 10 more passing (85 total in this file: 73 from Task 2, 2 from Task 3)**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: exclusive run directory, env override and writer preflight"
```

---

## Task 5: Decision rows — the §5.1 gate and `is_degraded`

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
def _record_clean(rec, room="battle-x-1", rqid=1):
    return rec.record_decision(
        room_id=room, rqid=rqid, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="heuristic",
        fallback_reason=None, agent_crash_type=None)


def test_gate_false_for_book_absent_records_not_applicable(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=3, book_absent=True, team_preview=False,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None)
    assert row["derivation_applicable"] is False
    assert row["is_degraded"] is None       # NOT False -- "not asked" != "not degraded"
    assert row["outcome"] == "not_applicable"


def test_gate_false_for_team_preview(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=1, book_absent=False, team_preview=True,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None)
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


def test_gate_true_clean_decision(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = _record_clean(rec, rqid=5)
    assert row["derivation_applicable"] is True
    assert row["is_degraded"] is False
    assert row["outcome"] == "ok"


def test_state_build_failure_is_degraded_with_the_stage_it_really_gets(tmp_path):
    """When the state build fails, choose_with_fallback skips both the heuristic and the
    max_damage layer (both require `state is not None`) and lands on
    deterministic_default_pair. state_degraded DOMINATES that stage in both derivations."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=6, book_absent=False, team_preview=False,
        state_build_failed=True, selection_stage="deterministic_default_pair",
        fallback_reason=None, agent_crash_type=None)
    assert row["is_degraded"] is True
    assert row["outcome"] == "degraded_state"


def test_fallback_stage_is_degraded_and_classified_fallback(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=7, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="max_damage_fallback",
        fallback_reason="heuristic_timeout", agent_crash_type=None)
    assert row["is_degraded"] is True and row["outcome"] == "fallback"


def test_crash_dominates_the_stage(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=8, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="heuristic", fallback_reason=None,
        agent_crash_type="ValueError")
    assert row["is_degraded"] is True and row["outcome"] == "crash"


def test_crash_on_the_book_absent_path_stays_not_applicable(tmp_path):
    """A smoke crash has the gate FALSE: neither derivation is called, so is_degraded stays
    null. This is why agent_crashes is not bounded by degraded_decisions (Task 2)."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=9, book_absent=True, team_preview=False,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type="KeyError")
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


def test_decision_seq_is_monotonic_per_room(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    seqs = [
        _record_clean(rec, room=r, rqid=i)["decision_seq"]
        for r, i in (("a", 1), ("a", 2), ("b", 1), ("a", 3))
    ]
    assert seqs == [0, 1, 0, 2]


def test_row_has_exactly_the_declared_fields(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = _record_clean(rec)
    assert tuple(row) == DECISION_FIELDS


def test_every_recorded_decision_validates(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rows = [
        _record_clean(rec, rqid=1),
        rec.record_decision(room_id="battle-x-1", rqid=2, book_absent=True,
                            team_preview=False, state_build_failed=False,
                            selection_stage=None, fallback_reason=None,
                            agent_crash_type=None),
        rec.record_decision(room_id="battle-x-1", rqid=3, book_absent=False,
                            team_preview=False, state_build_failed=True,
                            selection_stage="deterministic_default_pair",
                            fallback_reason=None, agent_crash_type=None),
    ]
    for row in rows:
        validate_decision_row(dict(row))
    assert rec.schema_errors_total == 0


def test_an_invalid_row_is_counted_and_not_buffered(tmp_path, monkeypatch):
    """The validator is a DEFECT signal. If it ever fires, the row is refused rather than
    written into a file consumers are told is schema-valid, the failure is counted, and the
    exit status goes non-zero. It never propagates (C11)."""
    def _reject(row):
        raise SchemaError("forced")

    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(
        "showdown_bot.client.live_degradation.validate_decision_row", _reject)
    _record_clean(rec)
    assert rec.schema_errors_total == 1
    assert rec._decisions.get("battle-x-1", []) == []
    assert rec.exit_status() != 0


def test_the_stage_vocabulary_of_choose_with_fallback_is_fully_classifiable():
    """classify_live_outcome RAISES on an unknown stage. That raise is unreachable here only
    because every stage choose_with_fallback can mark is either an intended-completion stage,
    a known fallback stage, or team_preview -- which the 5.1 gate excludes. This test turns
    that assumption into a checked invariant: if a future stage is added to
    battle/decision.py without extending the vocabulary, THIS fails rather than a live run."""
    import re

    from showdown_bot.eval.decision_profile import LIVE_FALLBACK_STAGES, LIVE_OK_STAGE

    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "showdown_bot" / "battle" / "decision.py"
    ).read_text(encoding="utf-8")
    marked = set(re.findall(r'_mark_selection\(\s*trace,\s*"([a-z_]+)"', source))
    assert marked, "no _mark_selection call sites found -- the regex needs updating"
    classifiable = {LIVE_OK_STAGE, *LIVE_FALLBACK_STAGES, "team_preview"}
    assert marked <= classifiable, f"unclassifiable stages: {sorted(marked - classifiable)}"
```

- [ ] **Step 2: Run, expect `AttributeError: 'LiveDegradationRecorder' object has no attribute 'record_decision'`**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 3: Implement** — add to `LiveDegradationRecorder`:

```python
    def record_decision(
        self, *, room_id: str, rqid: int | None, book_absent: bool, team_preview: bool,
        state_build_failed: bool, selection_stage: str | None, fallback_reason: str | None,
        agent_crash_type: str | None,
    ) -> dict:
        """Build, validate and buffer one decision row.

        NO filesystem access here (C1). Validation is pure field checking -- it touches no
        file, so it does not violate C1 and it catches a malformed row where the offending
        inputs are still in scope, instead of at a flush minutes later.
        """
        applicable = (not book_absent) and (not team_preview)
        if applicable:
            crashed = agent_crash_type is not None
            is_degraded = is_degraded_decision(
                crashed=crashed, state_degraded=state_build_failed,
                selection_stage=selection_stage)
            outcome = classify_live_outcome(
                crashed=crashed, state_degraded=state_build_failed,
                selection_stage=selection_stage)
        else:
            # 5.1: neither function is called. Ungated, is_degraded_decision fails closed
            # to True and classify_live_outcome RAISES -- both wrong on this path, where an
            # absent stage is normal and innocent.
            is_degraded = None
            outcome = "not_applicable"
            selection_stage = None
            fallback_reason = None

        seq = self._seq.get(room_id, 0)
        row = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id, "room_id": room_id,
            "decision_seq": seq, "rqid": rqid, "book_absent": book_absent,
            "team_preview": team_preview, "state_build_failed": state_build_failed,
            "selection_stage": selection_stage, "fallback_reason": fallback_reason,
            "agent_crash_type": agent_crash_type, "derivation_applicable": applicable,
            "is_degraded": is_degraded, "outcome": outcome,
        }
        try:
            validate_decision_row(row)
        except SchemaError as exc:
            self.schema_errors_total += 1
            logger.error("live-degradation rejected a decision row: %s | row=%r", exc, row)
            return row
        self._seq[room_id] = seq + 1
        self._decisions.setdefault(room_id, []).append(row)
        return row
```

- [ ] **Step 4: Run, expect 12 more passing (97 total in this file)**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: gated decision rows with persisted is_degraded"
```

---

## Task 6: Event rows and attribution (§7, C8)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
def test_server_error_is_room_attributed(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="server_error",
                          payload="[Invalid choice] Can't move: needs a target",
                          room_id="battle-x-1", active_battle_count=2)
    assert ev["attribution"] == "room" and ev["room_id"] == "battle-x-1"


def test_server_error_payload_is_stored_whole(tmp_path):
    """Section 7 requires the payload; no truncation rule has been approved."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    payload = "x" * 4096
    ev = rec.record_event(event_type="server_error", payload=payload,
                          room_id="battle-x-1", active_battle_count=1)
    assert ev["payload"] == payload


def test_invalid_choice_pm_with_two_active_battles_is_unattributed(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id=None, active_battle_count=2)
    assert ev["attribution"] == "unattributed" and ev["room_id"] is None


def test_invalid_choice_pm_room_hint_is_dropped_when_more_than_one_is_active(tmp_path):
    """Even if a caller passes a room, two active battles make the PM unattributable."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id="battle-x-1", active_battle_count=2)
    assert ev["attribution"] == "unattributed" and ev["room_id"] is None


def test_invalid_choice_pm_with_one_active_battle_is_inferred(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id="battle-x-1", active_battle_count=1)
    assert ev["attribution"] == "inferred" and ev["room_id"] == "battle-x-1"


def test_event_row_has_exactly_the_declared_fields_and_validates(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="server_error", payload="p",
                          room_id="battle-x-1", active_battle_count=1)
    assert tuple(ev) == EVENT_FIELDS
    validate_event_row(dict(ev))


def test_an_unknown_event_type_is_counted_and_not_buffered(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.record_event(event_type="disconnect", payload="p",
                     room_id="battle-x-1", active_battle_count=1)
    assert rec.schema_errors_total == 1
    assert rec._events == []
    assert rec.exit_status() != 0
```

- [ ] **Step 2: Run, expect `AttributeError: 'LiveDegradationRecorder' object has no attribute 'record_event'`**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 3: Implement** — add to `LiveDegradationRecorder`:

```python
    def record_event(
        self, *, event_type: str, payload: str, room_id: str | None,
        active_battle_count: int,
    ) -> dict:
        """Build, validate and buffer one asynchronous event. NO filesystem access (C1).

        The invalid-choice PM carries no room -- the loop fans _send_default_choose out to
        EVERY active battle precisely because it cannot tell which one it means. It is
        therefore unattributable in general; `inferred` is permitted only in the degenerate
        single-battle case and is recorded as such, never as `room` (section 7).
        """
        if event_type == "server_error":
            attribution = "room"
        elif room_id is not None and active_battle_count == 1:
            attribution = "inferred"
        else:
            attribution = "unattributed"
            room_id = None
        ev = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "event_type": event_type, "attribution": attribution, "room_id": room_id,
            "payload": payload, "active_battle_count": active_battle_count,
        }
        try:
            validate_event_row(ev)
        except SchemaError as exc:
            self.schema_errors_total += 1
            logger.error("live-degradation rejected an event row: %s | row=%r", exc, ev)
            return ev
        self._events.append(ev)
        return ev
```

- [ ] **Step 4: Run, expect 7 more passing (104 total in this file)** · **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: event rows with section 7 attribution rules"
```

---

## Task 7: Battle aggregation from the named sources (§8)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
def test_counters_come_from_their_named_sources(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_decision(room_id="R", rqid=2, book_absent=True, team_preview=False,
                        state_build_failed=False, selection_stage=None,
                        fallback_reason=None, agent_crash_type=None)
    rec.record_decision(room_id="R", rqid=3, book_absent=False, team_preview=False,
                        state_build_failed=True,
                        selection_stage="deterministic_default_pair",
                        fallback_reason=None, agent_crash_type=None)
    rec.record_event(event_type="server_error", payload="p",
                     room_id="R", active_battle_count=1)
    rec.record_event(event_type="invalid_choice_pm", payload="p",
                     room_id="R", active_battle_count=1)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["decisions_total"] == 3
    assert row["decisions_not_applicable"] == 1
    assert row["degraded_decisions"] == 1
    assert row["state_build_failures"] == 1
    assert row["agent_crashes"] == 0
    assert row["fallback_decisions"] == 0
    assert row["server_errors"] == 1
    assert row["own_invalid_choices"] == 1     # from events.jsonl, inferred only
    assert row["write_errors"] == 0
    assert tuple(row) == BATTLE_FIELDS
    validate_battle_row(dict(row))


def test_fallback_decisions_counts_only_gate_true_fallback_outcomes(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.record_decision(room_id="R", rqid=1, book_absent=False, team_preview=False,
                        state_build_failed=False, selection_stage="max_damage_fallback",
                        fallback_reason="heuristic_timeout", agent_crash_type=None)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["fallback_decisions"] == 1 and row["degraded_decisions"] == 1


def test_unattributed_event_increments_no_battle_counter(tmp_path):
    """C8: charging an unattributable event to a room -- or to all -- would
    manufacture degradation never observed on that battle."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_event(event_type="invalid_choice_pm", payload="p",
                     room_id=None, active_battle_count=3)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["own_invalid_choices"] == 0
    assert row["degraded_decisions"] == 0


def test_another_rooms_events_do_not_leak_into_this_battle(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_event(event_type="server_error", payload="p",
                     room_id="OTHER", active_battle_count=2)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["server_errors"] == 0


def test_not_applicable_rows_are_never_counted_as_degraded(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    for i in range(4):
        rec.record_decision(room_id="R", rqid=i, book_absent=True, team_preview=False,
                            state_build_failed=False, selection_stage=None,
                            fallback_reason=None, agent_crash_type=None)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["decisions_not_applicable"] == 4 and row["degraded_decisions"] == 0
```

- [ ] **Step 2: Run, expect `AttributeError: 'LiveDegradationRecorder' object has no attribute 'build_battle_row'`**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 3: Implement** — add to `LiveDegradationRecorder`:

```python
    def build_battle_row(self, *, room_id: str, end_reason: str) -> dict:
        """Aggregate one battle from the sources named per counter (section 8).

        Not every counter comes from decisions.jsonl: own_invalid_choices and server_errors
        come from the event stream, and write_errors from the in-memory failure counter --
        necessarily, since the rows are precisely what could not be written.
        """
        rows = self._decisions.get(room_id, [])
        evs = [e for e in self._events if e["room_id"] == room_id]
        return {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id, "room_id": room_id,
            "decisions_total": len(rows),
            "decisions_not_applicable": sum(
                1 for r in rows if r["derivation_applicable"] is False),
            "degraded_decisions": sum(1 for r in rows if r["is_degraded"] is True),
            "state_build_failures": sum(1 for r in rows if r["state_build_failed"]),
            "agent_crashes": sum(1 for r in rows if r["agent_crash_type"] is not None),
            "fallback_decisions": sum(
                1 for r in rows
                if r["derivation_applicable"] is True and r["outcome"] == "fallback"),
            "own_invalid_choices": sum(
                1 for e in evs
                if e["event_type"] == "invalid_choice_pm"
                and e["attribution"] == "inferred"),
            "server_errors": sum(1 for e in evs if e["event_type"] == "server_error"),
            "end_reason": end_reason,
            "write_errors": self._room_write_errors.get(room_id, 0),
        }
```

- [ ] **Step 4: Run, expect 5 more passing (109 total in this file)** · **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: battle aggregation from the section 8 named sources"
```

---

## Task 8: Flush, write-failure accounting, completion, exit status (§10.2–§10.4)

The ordering here is load-bearing and was wrong in two earlier revisions: **the decision rows are
written first, the battle row is built afterwards so it can see this flush's own write errors, and
the buffers are discarded only at the end.** Popping first made `build_battle_row` read an empty
buffer and emit an all-zero row — a silent, plausible-looking "clean battle".

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation.py`:

```python
def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_flush_writes_decisions_events_and_battle(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_event(event_type="server_error", payload="p",
                     room_id="R", active_battle_count=1)
    rec.flush_battle(room_id="R", end_reason="win")
    assert len(_read_jsonl(rec.run_dir / "decisions.jsonl")) == 1
    assert len(_read_jsonl(rec.run_dir / "events.jsonl")) == 1
    battles = _read_jsonl(rec.run_dir / "battles.jsonl")
    assert len(battles) == 1 and battles[0]["end_reason"] == "win"


def test_the_battle_row_is_built_after_the_rows_are_written(tmp_path):
    """REGRESSION: an earlier revision popped the decision buffer BEFORE calling
    build_battle_row, so every battle row was all-zero -- a clean-looking battle that had
    in fact recorded three decisions."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    _record_clean(rec, room="R", rqid=2)
    rec.record_decision(room_id="R", rqid=3, book_absent=True, team_preview=False,
                        state_build_failed=False, selection_stage=None,
                        fallback_reason=None, agent_crash_type=None)
    rec.flush_battle(room_id="R", end_reason="win")
    battle = _read_jsonl(rec.run_dir / "battles.jsonl")[0]
    assert battle["decisions_total"] == 3
    assert battle["decisions_not_applicable"] == 1


def test_flush_appends_and_never_truncates(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="A", rqid=1)
    rec.flush_battle(room_id="A", end_reason="win")
    _record_clean(rec, room="B", rqid=1)
    rec.flush_battle(room_id="B", end_reason="tie")
    assert len(_read_jsonl(rec.run_dir / "battles.jsonl")) == 2
    assert len(_read_jsonl(rec.run_dir / "decisions.jsonl")) == 2


def test_flush_discards_the_buffers_so_a_second_flush_writes_nothing_new(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.flush_battle(room_id="R", end_reason="win")
    rec.flush_battle(room_id="R", end_reason="win")
    assert len(_read_jsonl(rec.run_dir / "decisions.jsonl")) == 1
    assert len(_read_jsonl(rec.run_dir / "battles.jsonl")) == 2   # two battle rows, one decision


def test_flush_counts_a_finished_battle_but_not_an_unterminated_one(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="A", rqid=1)
    rec.flush_battle(room_id="A", end_reason="win")
    _record_clean(rec, room="B", rqid=1)
    rec.flush_unterminated(["B"])
    assert rec.battles_finished == 1
    assert rec.unterminated_rooms == ["B"]


def test_run_scoped_events_are_persisted_at_run_end(tmp_path):
    """REGRESSION: a battle flush writes only events whose room_id matches, so every
    unattributed invalid-choice PM -- the most likely event in a multi-battle ladder
    session -- lived and died in memory."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                     room_id=None, active_battle_count=3)
    rec.flush_battle(room_id="R", end_reason="win")
    assert _read_jsonl(rec.run_dir / "events.jsonl") == []
    rec.flush_run_events()
    events = _read_jsonl(rec.run_dir / "events.jsonl")
    assert len(events) == 1
    assert events[0]["attribution"] == "unattributed" and events[0]["room_id"] is None


def test_flush_failure_is_counted_and_never_raises(tmp_path, monkeypatch):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)

    def _boom(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr("showdown_bot.client.live_degradation._append_jsonl", _boom)
    rec.flush_battle(room_id="R", end_reason="win")   # must NOT raise (10.2)
    assert rec.write_errors_total > 0
    assert rec.exit_status() != 0


def test_the_battle_row_sees_this_flushs_own_write_errors(tmp_path, monkeypatch):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    calls = {"n": 0}
    real_append = None

    def _fail_first(path, rows):
        calls["n"] += 1
        if calls["n"] == 1:                      # decisions.jsonl fails
            raise OSError("disk gone")
        return real_append(path, rows)

    import showdown_bot.client.live_degradation as mod
    real_append = mod._append_jsonl
    monkeypatch.setattr(mod, "_append_jsonl", _fail_first)
    rec.flush_battle(room_id="R", end_reason="win")
    battle = _read_jsonl(rec.run_dir / "battles.jsonl")[0]
    assert battle["write_errors"] == 1
    assert battle["decisions_total"] == 1        # the row existed; only the WRITE failed


def test_clean_run_persists_three_zeros_and_exits_zero(tmp_path):
    """Case 1 of four (§8.0): the ONLY combination that establishes a successful run."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _record_clean(rec, room="R", rqid=1)
    rec.flush_battle(room_id="R", end_reason="win")
    rec.flush_run_events()
    rec.write_completion()
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    validate_completion_row(dict(completion), expected_run_id=rec.run_id)
    assert tuple(completion) == COMPLETION_FIELDS
    assert completion["write_errors_total"] == 0
    assert completion["schema_errors_total"] == 0
    assert completion["recorder_errors_total"] == 0
    assert completion["battles_finished"] == 1
    assert completion["preflight_ok"] is True
    assert rec.exit_status() == 0


def test_a_prior_schema_error_is_persisted_as_one_and_exits_non_zero(tmp_path, monkeypatch):
    """Case 2 of four. The counter must reach the FILE, not only the exit status -- a
    completion.json reading permanently clean beside a non-zero exit was the hole §8.0 closes."""
    def _reject(row):
        raise SchemaError("forced")

    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(
        "showdown_bot.client.live_degradation.validate_decision_row", _reject)
    _record_clean(rec, room="R", rqid=1)
    monkeypatch.undo()                          # the completion write must not be rejected too
    rec.write_completion()
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    assert completion["schema_errors_total"] == 1
    assert completion["write_errors_total"] == 0
    assert completion["recorder_errors_total"] == 0
    assert rec.exit_status() != 0


def test_a_prior_recorder_error_is_persisted_as_one_and_exits_non_zero(tmp_path):
    """Case 3 of four."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.note_recorder_error(RuntimeError("something escaped a record_ call"))
    rec.write_completion()
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    assert completion["recorder_errors_total"] == 1
    assert completion["schema_errors_total"] == 0
    assert completion["write_errors_total"] == 0
    assert rec.exit_status() != 0


def test_a_missing_completion_exits_non_zero(tmp_path, monkeypatch):
    """Case 4 of four: an unwritable completion. The failure of THIS write cannot appear in the
    file it failed to produce, so the exit status carries it (§8.0 persistence limit)."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)

    def _boom(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(
        "showdown_bot.client.live_degradation._write_json_exclusive", _boom)
    rec.write_completion()                      # must not raise
    assert not (rec.run_dir / "completion.json").exists()
    assert rec.exit_status() != 0               # the machine-checkable signal (10.3)


def test_a_present_but_unusable_completion_is_a_failure_state_not_a_success(tmp_path):
    """§8.0: open(..., "x") buys exclusivity, NOT atomicity. A write that dies after the create
    leaves a file behind. Absent, unparseable and schema-invalid are ONE failure state, which is
    why a consumer must parse and validate rather than stat."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    path = rec.run_dir / "completion.json"

    path.write_text('{"schema_version": "live-degrad', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        json.loads(path.read_text(encoding="utf-8"))

    path.write_text('{"schema_version": "live-degradation-v1"}', encoding="utf-8")
    with pytest.raises(SchemaError):
        validate_completion_row(json.loads(path.read_text(encoding="utf-8")))


def test_completion_never_overwrites_an_existing_file(tmp_path):
    """C9: mode 'x'. A second write is a refusal, counted, not a truncation."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    rec.write_completion()
    first = (rec.run_dir / "completion.json").read_text(encoding="utf-8")
    rec.battles_finished = 99
    rec.write_completion()
    assert (rec.run_dir / "completion.json").read_text(encoding="utf-8") == first
    assert rec.exit_status() != 0


def test_recorder_errors_reach_the_exit_status(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert rec.exit_status() == 0
    rec.note_recorder_error(RuntimeError("something escaped a record_ call"))
    assert rec.recorder_errors_total == 1
    assert rec.exit_status() != 0
```

- [ ] **Step 2: Run, expect `AttributeError: 'LiveDegradationRecorder' object has no attribute 'flush_battle'`**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 3a: Implement the two writers** — module-level functions in `live_degradation.py`:

```python
def _append_jsonl(path: Path, rows: list[dict]) -> None:
    """Append-only. Never opens in a truncating mode (C9)."""
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _write_json_exclusive(path: Path, payload: dict) -> None:
    """Exclusive create (C9). Mode "w" would truncate; inside a run directory that is by
    construction ours, an EXISTING completion.json means something already wrote here --
    that is a refusal, not a file to overwrite."""
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
```

- [ ] **Step 3b: Implement the flush machinery** — add to `LiveDegradationRecorder`:

```python
    def _append_or_count(self, path: Path, rows: list[dict], room_id: str | None) -> None:
        """One guarded append. Errors are counted and logged, never propagated (10.2)."""
        if not rows:
            return
        try:
            _append_jsonl(path, rows)
        except OSError as exc:
            self.write_errors_total += 1
            if room_id is not None:
                self._room_write_errors[room_id] = self._room_write_errors.get(room_id, 0) + 1
            logger.error("live-degradation write failed for %s -> %s: %s",
                         room_id or "<run>", path.name, exc)

    def flush_battle(self, *, room_id: str, end_reason: str) -> None:
        """Flush one battle at its boundary. Synchronous, with NO latency bound (C2).

        Called BEFORE _room_raw.pop(room) discards the raw log -- that pop is where today's
        evidence is thrown away (section 9). Deliberately not backgrounded (C3); the accepted
        consequence is that a stalled disk here can delay message processing for other active
        battles, and no upper bound is claimed.

        ORDER IS LOAD-BEARING. The rows are written first; the battle row is built AFTER, so
        it sees this flush's own write errors; the buffers are discarded LAST. Popping first
        made build_battle_row read an empty buffer and emit an all-zero row.

        One inherent limit: write_errors on the battle row cannot include the failure of
        writing the battle row itself. That failure is still counted in write_errors_total
        and in the exit status.
        """
        rows = list(self._decisions.get(room_id, []))
        evs = [e for e in self._events if e["room_id"] == room_id]

        self._append_or_count(self.run_dir / "decisions.jsonl", rows, room_id)
        self._append_or_count(self.run_dir / "events.jsonl", evs, room_id)

        battle_row = self.build_battle_row(room_id=room_id, end_reason=end_reason)
        try:
            validate_battle_row(battle_row)
        except SchemaError as exc:
            self.schema_errors_total += 1
            logger.error("live-degradation rejected a battle row: %s | row=%r", exc, battle_row)
        else:
            self._append_or_count(self.run_dir / "battles.jsonl", [battle_row], room_id)

        self._decisions.pop(room_id, None)
        self._events = [e for e in self._events if e["room_id"] != room_id]
        self._seq.pop(room_id, None)
        if end_reason != "unterminated":
            self.battles_finished += 1

    def flush_unterminated(self, rooms) -> None:
        """Rooms still active when the loop exits (stream end, exception, cancellation)."""
        for room_id in list(rooms):
            self.unterminated_rooms.append(room_id)
            self.flush_battle(room_id=room_id, end_reason="unterminated")

    def flush_run_events(self) -> None:
        """Persist events that belong to no battle (section 7 / C8).

        A battle flush writes only events whose room_id matches. An `unattributed`
        invalid-choice PM has room_id None by construction and would otherwise never be
        written -- and in a multi-battle ladder session it is the MOST likely event there is.
        """
        leftover = list(self._events)
        self._append_or_count(self.run_dir / "events.jsonl", leftover, None)
        self._events = []

    def note_recorder_error(self, exc: BaseException) -> None:
        """Something escaped a record_/flush_ call at a call site. Counted so it reaches the
        exit status; never re-raised (C11)."""
        self.recorder_errors_total += 1
        logger.error("live-degradation recorder error: %s: %s", type(exc).__name__, exc)

    def write_completion(self) -> None:
        """Best-effort (10.3). Its ABSENCE is meaningful, not neutral.

        The payload is a SNAPSHOT: the counters as they stand right now. A failure of this very
        write increments write_errors_total afterwards and therefore cannot appear in the file
        it just failed to produce -- section 8.0's persistence limit. The exit status carries it.

        The write is exclusive but NOT atomic. open(..., "x") can succeed and the serialisation
        then fail, leaving an empty, truncated or unsynced completion.json behind. A reader must
        parse and validate it, never merely stat it (section 8.0).
        """
        payload = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "battles_finished": self.battles_finished,
            "unterminated_rooms": list(self.unterminated_rooms),
            "write_errors_total": self.write_errors_total,
            "schema_errors_total": self.schema_errors_total,
            "recorder_errors_total": self.recorder_errors_total,
            "preflight_ok": True,
        }
        try:
            validate_completion_row(payload, expected_run_id=self.run_id)
        except SchemaError as exc:
            self.schema_errors_total += 1
            logger.error("live-degradation rejected the completion row: %s | row=%r",
                         exc, payload)
            return
        try:
            _write_json_exclusive(self.run_dir / "completion.json", payload)
        except OSError as exc:
            self.write_errors_total += 1
            logger.error("live-degradation completion write failed: %s", exc)

    def exit_status(self) -> int:
        """The machine-checkable signal (10.3): it depends on no file being readable.

        All three counters feed it, and all three are also PERSISTED in completion.json since
        the section 8.0 amendment -- that is what closes the hole where a run could exit 1
        while its only per-run artifact read permanently clean.

        This is the recorder-derived status only. Section 8.0 scopes it to the normal-return
        path, evaluated after every finalisation attempt including the completion write; a
        propagated exception, a cancellation or a KeyboardInterrupt keeps its own status and
        must never be masked by this value.
        """
        return 1 if (self.write_errors_total or self.schema_errors_total
                     or self.recorder_errors_total) else 0
```

- [ ] **Step 4: Run, expect 15 more passing (124 total in this file)**

```bash
python -m pytest showdown_bot/tests/test_live_degradation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py
git commit -m "feat: boundary flush, write-failure accounting, completion and exit status"
```

---

## Task 9: Runner wiring — send first, then record; crash re-raised; events

Two independent guarantees keep C11:

1. **`await conn.send()` happens BEFORE `record_decision()`.** A recorder failure then
   cannot prevent the send, by construction rather than by a guard that might be wrong.
2. **The record call is additionally wrapped**, so a recorder failure cannot kill the battle
   loop either.

**Files:** Modify `showdown_bot/src/showdown_bot/client/runner.py`;
create `showdown_bot/tests/test_live_degradation_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `showdown_bot/tests/test_live_degradation_runner.py`:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from showdown_bot.client import runner
from showdown_bot.client.live_degradation import LiveDegradationRecorder

FIXTURES = Path(__file__).parent / "fixtures"
ROOM = "battle-gen9vgc2025regg-1"


def _request_payload(name: str = "request_doubles_moves.json") -> str:
    """The fixture JSON as one line -- parse_message splits on '|', and the fixtures
    contain none, so a single-line payload round-trips."""
    return json.dumps(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


class _StubConnection:
    """Records what the runner sent and replays a fixed frame list."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True

    async def messages(self):
        for frame in self._frames:
            yield frame


class _RaisingConnection(_StubConnection):
    async def messages(self):
        for frame in self._frames:
            yield frame
        raise RuntimeError("stream exploded")


class _CancellingConnection(_StubConnection):
    async def messages(self):
        for frame in self._frames:
            yield frame
        raise asyncio.CancelledError()


class _FakeState:
    """Stand-in for BattleState so a test controls whether the build succeeds."""


def _install_recorder(monkeypatch, tmp_path) -> LiveDegradationRecorder:
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(runner, "_recorder", rec)
    return rec


def _events_of(rec) -> list[dict]:
    """Every event the run has produced, wherever it currently lives.

    Task 9 has no run-end flush yet, so events sit in the buffer; from Task 10 on they are
    on disk. Reading both keeps these assertions true across that step instead of forcing
    a rewrite of the very tests that prove Task 9.
    """
    path = rec.run_dir / "events.jsonl"
    on_disk = []
    if path.exists():
        on_disk = [json.loads(line) for line in
                   path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return list(rec._events) + on_disk


def _use_heuristic_path(monkeypatch, *, stage="heuristic", reason=None,
                        state_raises=False, chooser_raises=None):
    """Make handle_battle_message take the book-present branch deterministically.

    _get_book is stubbed to a sentinel (only its not-None-ness matters to the runner),
    BattleState/merge_request are stubbed so the test decides whether the build fails, and
    choose_with_fallback is stubbed to mark a chosen stage on the sink.
    """
    monkeypatch.setenv("SHOWDOWN_TURN_TRACE", "0")
    monkeypatch.setattr(runner, "_active_format", "gen9vgc2025regg")
    monkeypatch.setattr(runner, "_our_spreads", None)
    monkeypatch.setattr(runner, "_opp_sets", {})
    monkeypatch.setattr(runner, "_get_book", lambda fmt: object())
    monkeypatch.setattr(runner, "_get_priors", lambda fmt: None)
    monkeypatch.setattr(runner, "_get_format_config", lambda fmt: None)

    def _from_log_text(text):
        if state_raises:
            raise ValueError("corrupt log")
        return _FakeState()

    monkeypatch.setattr(
        runner, "BattleState",
        type("_BS", (), {"from_log_text": staticmethod(_from_log_text)}))
    monkeypatch.setattr(runner, "merge_request", lambda req, state: None)

    def _choose(req, **kwargs):
        if chooser_raises is not None:
            raise chooser_raises
        sink = kwargs.get("stage_sink")
        if sink is not None:
            sink.selection_stage = stage
            sink.fallback_reason = reason
        return f"/choose default|{req.rqid}"

    monkeypatch.setattr(runner, "choose_with_fallback", _choose)


@pytest.mark.asyncio
async def test_a_clean_decision_is_recorded(tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["derivation_applicable"] is True
    assert row["is_degraded"] is False and row["outcome"] == "ok"
    assert row["selection_stage"] == "heuristic"


@pytest.mark.asyncio
async def test_state_build_failure_is_recorded_and_is_not_state_is_none(tmp_path, monkeypatch):
    """Section 5: the raw fact is 'the build was ATTEMPTED and failed', never 'state is None'."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch, stage="deterministic_default_pair", state_raises=True)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["state_build_failed"] is True
    assert row["is_degraded"] is True and row["outcome"] == "degraded_state"


@pytest.mark.asyncio
async def test_team_preview_is_recorded_as_not_applicable(tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([])
    await runner.handle_battle_message(
        conn, ROOM, _request_payload("request_team_preview.json"))
    row = rec._decisions[ROOM][0]
    assert row["team_preview"] is True
    assert row["state_build_failed"] is False
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


@pytest.mark.asyncio
async def test_book_absent_is_recorded_as_not_applicable(tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    monkeypatch.setenv("SHOWDOWN_TURN_TRACE", "0")
    monkeypatch.setattr(runner, "_get_book", lambda fmt: None)
    monkeypatch.setattr(runner, "choose_for_request",
                        lambda req: f"/choose default|{req.rqid}")
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["book_absent"] is True
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


@pytest.mark.asyncio
async def test_chooser_exception_is_recorded_then_re_raised(tmp_path, monkeypatch):
    """C5: the chooser call is unguarded today, so the exception propagates. Adding a
    default-choose fallback here would change what the bot DOES, not what it records."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch, chooser_raises=ValueError("boom"))
    conn = _StubConnection([])
    with pytest.raises(ValueError, match="boom"):
        await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["agent_crash_type"] == "ValueError"
    assert row["outcome"] == "crash" and row["is_degraded"] is True
    assert conn.sent == []          # nothing was chosen, so nothing was sent


@pytest.mark.asyncio
async def test_cancellation_in_the_chooser_is_not_recorded_as_an_agent_crash(
        tmp_path, monkeypatch):
    """`except Exception`, NOT BaseException: CancelledError, KeyboardInterrupt and
    SystemExit are not agent crashes."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch, chooser_raises=asyncio.CancelledError())
    conn = _StubConnection([])
    with pytest.raises(asyncio.CancelledError):
        await runner.handle_battle_message(conn, ROOM, _request_payload())
    assert rec._decisions.get(ROOM, []) == []


@pytest.mark.asyncio
async def test_the_chosen_action_is_byte_identical_with_and_without_the_recorder(
        tmp_path, monkeypatch):
    """C5/C10: recording must not alter the action string."""
    _use_heuristic_path(monkeypatch)
    monkeypatch.setattr(runner, "_recorder", None)
    without = _StubConnection([])
    await runner.handle_battle_message(without, ROOM, _request_payload())

    _install_recorder(monkeypatch, tmp_path)
    with_rec = _StubConnection([])
    await runner.handle_battle_message(with_rec, ROOM, _request_payload())

    assert with_rec.sent == without.sent
    assert len(with_rec.sent) == 1


@pytest.mark.asyncio
async def test_a_recorder_failure_after_a_successful_choice_does_not_stop_the_send(
        tmp_path, monkeypatch):
    """C11, both guarantees at once: the send has already happened when record_decision is
    called, and the call is guarded, so a recorder defect neither loses the action nor
    kills the battle."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)

    def _explode(**kwargs):
        raise RuntimeError("recorder defect")

    monkeypatch.setattr(rec, "record_decision", _explode)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())    # must NOT raise
    assert len(conn.sent) == 1
    assert rec.recorder_errors_total == 1
    assert rec.exit_status() != 0


@pytest.mark.asyncio
async def test_no_recorder_means_no_behaviour_change(tmp_path, monkeypatch):
    _use_heuristic_path(monkeypatch)
    monkeypatch.setattr(runner, "_recorder", None)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    assert len(conn.sent) == 1


@pytest.mark.asyncio
async def test_server_error_records_the_real_payload_not_an_empty_string(
        tmp_path, monkeypatch):
    """REGRESSION: parse_message sets `payload` only for prefix == 'request'
    (protocol/messages.py:26). Recording parsed.payload for |error| wrote '' every time."""
    rec = _install_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "battle-logs")
    runner._battle_logs.clear()
    runner._room_raw.clear()
    runner._last_rqid[ROOM] = 4
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|error|[Invalid choice] Can't move: Zamazenta needs a target",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    errors = [e for e in _events_of(rec) if e["event_type"] == "server_error"]
    assert len(errors) == 1
    assert errors[0]["payload"] == "[Invalid choice] Can't move: Zamazenta needs a target"
    assert errors[0]["attribution"] == "room" and errors[0]["room_id"] == ROOM


@pytest.mark.asyncio
async def test_invalid_choice_pm_with_two_active_battles_is_unattributed(
        tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "battle-logs")
    runner._battle_logs.clear()
    runner._room_raw.clear()
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        ">battle-gen9vgc2025regg-2\n|init|battle",
        "|pm| Staff|~|Invalid choice",
    ])
    await runner._run_battle_loop(conn, max_battles=5, cancel_on_done=None)
    pms = [e for e in _events_of(rec) if e["event_type"] == "invalid_choice_pm"]
    assert len(pms) == 1
    assert pms[0]["attribution"] == "unattributed" and pms[0]["room_id"] is None
    assert pms[0]["active_battle_count"] == 2
```

- [ ] **Step 2: Run, expect failures on the missing `runner._recorder`**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q
```

Expected: `AttributeError: <module 'showdown_bot.client.runner'> has no attribute '_recorder'`

- [ ] **Step 3a: Add the module-level state to `runner.py`**

After the existing imports (`runner.py:20`) and next to the other module globals:

```python
from showdown_bot.battle.decision import SelectionStageSink
from showdown_bot.client.live_degradation import LiveDegradationRecorder
```

and, after `_format_config_cache` (`runner.py:34`):

```python
# The always-on live-degradation sink (live-degradation-v1). Set by preflight in each of the
# three run_* entry points; None only in unit tests that do not exercise recording.
_recorder: LiveDegradationRecorder | None = None


def recorder_exit_status() -> int:
    """0, or non-zero when the last run had a write, schema or recorder failure (10.3).
    Read by cli.py on the NORMAL-return path only, so it can never mask an exception."""
    return _recorder.exit_status() if _recorder is not None else 0


def _guarded(call, *args, **kwargs) -> None:
    """Run a recorder call so that no recorder defect can reach a battle (C11).

    `except Exception`, not BaseException: a CancelledError or KeyboardInterrupt raised
    through here is control flow, not a recorder failure, and must keep propagating.
    """
    if _recorder is None:
        return
    try:
        call(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a recorder defect must never kill a battle
        _recorder.note_recorder_error(exc)
```

- [ ] **Step 3b: Rewrite `handle_battle_message` (`runner.py:98-131`)**

```python
async def handle_battle_message(conn: ShowdownConnection, room: str, payload: str) -> None:
    req = BattleRequest.model_validate(json.loads(payload))
    if req.wait:
        # Opponent's turn; we've already locked in. Nothing to choose, nothing to record.
        return
    _last_rqid[room] = req.rqid

    book = _get_book(_active_format)
    book_absent = book is None
    team_preview = bool(req.team_preview)
    state_build_failed = False
    state: BattleState | None = None
    if book is not None and not req.team_preview:
        try:
            state = BattleState.from_log_text("\n".join(_room_raw.get(room, [])))
            merge_request(req, state)
        except Exception as exc:  # noqa: BLE001 - never block a turn on state build
            logger.warning("state build failed in %s: %s", room, exc)
            state = None
            # Section 5: the raw fact is "ATTEMPTED and failed". `state is None` also happens
            # for a missing book and for team preview, neither of which is degradation.
            state_build_failed = True

    stage_sink = SelectionStageSink() if _recorder is not None else None
    report: list[str] = []
    try:
        if book is not None:
            priors = _get_priors(_active_format)
            cfg = _get_format_config(_active_format)
            choose = choose_with_fallback(
                req, state=state, book=book, our_side=req.side.id, priors=priors,
                report=report, our_spreads=_our_spreads, opp_sets=_opp_sets,
                format_config=cfg, stage_sink=stage_sink,
            )
        else:
            choose = choose_for_request(req)
    except Exception as exc:  # noqa: BLE001 - NOT BaseException: CancelledError,
        # KeyboardInterrupt and SystemExit are control flow, not agent crashes.
        _guarded(
            _record_decision_for, room=room, req=req, book_absent=book_absent,
            team_preview=team_preview, state_build_failed=state_build_failed,
            stage_sink=stage_sink, agent_crash_type=type(exc).__name__,
        )
        raise                     # C5: unchanged exception, no new fallback

    # C11: the action goes out BEFORE anything is recorded, so no recorder defect can
    # prevent an already-chosen action being sent. The guard below is the second layer.
    await conn.send(f"{room}|{choose}")
    _guarded(
        _record_decision_for, room=room, req=req, book_absent=book_absent,
        team_preview=team_preview, state_build_failed=state_build_failed,
        stage_sink=stage_sink, agent_crash_type=None,
    )
    kind = "team preview" if req.team_preview else "battle"
    logger.info("sent %s (%s)", choose, kind)
    if book is not None and not req.team_preview:
        _emit_turn_trace(room, report)


def _record_decision_for(*, room, req, book_absent, team_preview, state_build_failed,
                         stage_sink, agent_crash_type) -> None:
    _recorder.record_decision(
        room_id=room, rqid=req.rqid, book_absent=book_absent, team_preview=team_preview,
        state_build_failed=state_build_failed,
        selection_stage=getattr(stage_sink, "selection_stage", None),
        fallback_reason=getattr(stage_sink, "fallback_reason", None),
        agent_crash_type=agent_crash_type,
    )
```

- [ ] **Step 3c: Add event recording in `_run_battle_loop`**

Replace the PM branch (`runner.py:187-190`):

```python
            if parsed.prefix == "pm" and parsed.args and "Invalid choice" in parsed.args[-1]:
                # Section 7: this PM carries NO room. The fan-out below exists precisely
                # because the loop cannot tell which battle it refers to, so `inferred` is
                # permitted only in the degenerate single-battle case.
                if _recorder is not None:
                    only = next(iter(active_battles)) if len(active_battles) == 1 else None
                    _guarded(
                        _recorder.record_event, event_type="invalid_choice_pm",
                        payload=parsed.args[-1], room_id=only,
                        active_battle_count=len(active_battles),
                    )
                for battle_room in list(active_battles):
                    await _send_default_choose(conn, battle_room)
                continue
```

and the `|error|` branch (`runner.py:193-194`):

```python
                if parsed.prefix == "error":
                    # parse_message fills `payload` only for prefix == "request"
                    # (protocol/messages.py:26); the error text lives in args, and joining
                    # with "|" restores a payload that itself contains "|".
                    if _recorder is not None:
                        _guarded(
                            _recorder.record_event, event_type="server_error",
                            payload="|".join(parsed.args), room_id=parsed.room,
                            active_battle_count=len(active_battles),
                        )
                    await _send_default_choose(conn, parsed.room)
```

Both fragments are shown at **today's** indentation, which is what Task 9 must produce: the loop
has no `try` yet, and Task 9's own tests drive `_run_battle_loop`. Task 10 wraps the loop and
re-indents both fragments one level deeper; its Step 3a prints the whole resulting function, so
the two are consistent by construction rather than by memory.

- [ ] **Step 4: Run, expect 11 passed**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/runner.py showdown_bot/tests/test_live_degradation_runner.py
git commit -m "feat: record live decisions and events; send before record (C11)"
```

---

## Task 10: Battle boundaries, `finally`, preflight call site (§9, §10.1)

**Files:** Modify `runner.py`; add to `tests/test_live_degradation_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation_runner.py`:

```python
def _battle_rows(rec) -> list[dict]:
    path = rec.run_dir / "battles.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def _clean_runner_state(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "battle-logs")
    runner._battle_logs.clear()
    runner._room_raw.clear()
    runner._last_rqid.clear()
    yield
    runner._battle_logs.clear()
    runner._room_raw.clear()
    runner._last_rqid.clear()


@pytest.mark.asyncio
async def test_flush_happens_before_room_raw_is_popped(
        tmp_path, monkeypatch, _clean_runner_state):
    """Section 9: that pop is where today's evidence is thrown away."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|win|opponent",
    ])
    finished = await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert finished == 1
    rows = _battle_rows(rec)
    assert len(rows) == 1
    assert rows[0]["end_reason"] == "win"
    assert rows[0]["decisions_total"] == 1        # the decision survived the pop
    assert ROOM not in runner._room_raw


@pytest.mark.asyncio
async def test_stream_end_flushes_active_rooms_as_unterminated(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    rows = _battle_rows(rec)
    assert [r["end_reason"] for r in rows] == ["unterminated"]
    assert rows[0]["decisions_total"] == 1
    assert rec.unterminated_rooms == [ROOM]


@pytest.mark.asyncio
async def test_exception_exit_flushes_active_rooms_as_unterminated(
        tmp_path, monkeypatch, _clean_runner_state):
    """A post-loop statement would be SKIPPED here -- exactly where the evidence matters."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _RaisingConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
    ])
    with pytest.raises(RuntimeError, match="stream exploded"):
        await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert [r["end_reason"] for r in _battle_rows(rec)] == ["unterminated"]


@pytest.mark.asyncio
async def test_the_not_ladderable_popup_still_flushes(
        tmp_path, monkeypatch, _clean_runner_state):
    """_run_battle_loop raises RuntimeError itself on this popup (runner.py:176-180)."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        "|popup|The ladder is not ladderable right now.",
    ])
    with pytest.raises(RuntimeError, match="ladderable"):
        await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert [r["end_reason"] for r in _battle_rows(rec)] == ["unterminated"]
    assert conn.closed is True


@pytest.mark.asyncio
async def test_cancellation_flushes_active_rooms_as_unterminated(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _CancellingConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
    ])
    with pytest.raises(asyncio.CancelledError):
        await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert [r["end_reason"] for r in _battle_rows(rec)] == ["unterminated"]


@pytest.mark.asyncio
async def test_completion_is_written_at_run_end(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|win|opponent",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    assert completion["battles_finished"] == 1
    assert completion["unterminated_rooms"] == []
    assert completion["preflight_ok"] is True


@pytest.mark.asyncio
async def test_run_scoped_events_are_written_at_run_end(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        ">battle-gen9vgc2025regg-2\n|init|battle",
        "|pm| Staff|~|Invalid choice",
    ])
    await runner._run_battle_loop(conn, max_battles=5, cancel_on_done=None)
    events = [json.loads(line) for line in
              (rec.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["attribution"] == "unattributed" for e in events)


@pytest.mark.asyncio
async def test_preflight_failure_aborts_before_connect(tmp_path, monkeypatch):
    """Section 10.1: the ONE place a recording failure may stop the run -- nothing has been
    played yet, so aborting costs nothing."""
    from showdown_bot.client.live_degradation import PreflightError
    from showdown_bot.config import Settings

    connected = {"called": False}

    async def _should_not_connect(settings):
        connected["called"] = True
        raise AssertionError("connect must not be reached after a preflight failure")

    def _fail(**kwargs):
        raise PreflightError("writer probe failed")

    monkeypatch.setattr(runner.LiveDegradationRecorder, "preflight", staticmethod(_fail))
    monkeypatch.setattr(runner, "_connect_and_login", _should_not_connect)
    settings = Settings(
        username="tester", password="", server_url="ws://localhost:8000/showdown/websocket",
        team_path=Path("teams/fixed_team.txt"), format_id="gen9vgc2025regg")
    with pytest.raises(PreflightError):
        await runner.run_ladder_search(settings, max_battles=1)
    assert connected["called"] is False


@pytest.mark.asyncio
async def test_preflight_runs_for_challenge_and_smoke_too(tmp_path, monkeypatch):
    from showdown_bot.client.live_degradation import PreflightError
    from showdown_bot.config import Settings

    def _fail(**kwargs):
        raise PreflightError("writer probe failed")

    async def _should_not_connect(settings):
        raise AssertionError("connect must not be reached after a preflight failure")

    monkeypatch.setattr(runner.LiveDegradationRecorder, "preflight", staticmethod(_fail))
    monkeypatch.setattr(runner, "_connect_and_login", _should_not_connect)
    settings = Settings(
        username="tester", password="", server_url="ws://localhost:8000/showdown/websocket",
        team_path=Path("teams/fixed_team.txt"), format_id="gen9vgc2025regg")
    with pytest.raises(PreflightError):
        await runner.run_challenge(settings, "someone", max_battles=1)
    with pytest.raises(PreflightError):
        await runner.run_smoke_battle(settings)
```

- [ ] **Step 2: Run, expect nine failures**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q
```

- [ ] **Step 3a: Replace `_run_battle_loop` in full**

`_run_battle_loop` (`runner.py:157-220`) is replaced by the function below. It is the existing
body with three changes and nothing else: the `try`/`finally`, the flush moved above
`_room_raw.pop`, and the two event call sites from Task 9. The `finally` also covers the early
`return battles_finished` at the `max_battles` boundary, because a `return` inside `try` runs it.

```python
async def _run_battle_loop(
    conn: ShowdownConnection,
    max_battles: int,
    *,
    cancel_on_done: str | None = "|/cancelsearch",
) -> int:
    battles_finished = 0
    active_battles: set[str] = set()

    try:
        async for raw in conn.messages():
            parsed_list = list(parse_incoming(raw))
            for room in {p.room for p in parsed_list if p.room.startswith("battle-")}:
                _room_raw.setdefault(room, []).append(raw)
                _log_battle_line(room, raw)
            for parsed in parsed_list:
                if parsed.prefix == "popup" and parsed.args:
                    popup = parsed.args[0]
                    logger.warning("popup: %s", popup[:200])
                    lower = popup.lower()
                    if "not ladderable" in lower:
                        if cancel_on_done:
                            await conn.send(cancel_on_done)
                        await conn.close()
                        raise RuntimeError(popup)
                    if "invalid team" in lower or "team was rejected" in lower:
                        if cancel_on_done:
                            await conn.send(cancel_on_done)
                        await conn.close()
                        raise RuntimeError(popup)

                if parsed.prefix == "pm" and parsed.args and "Invalid choice" in parsed.args[-1]:
                    # Section 7: this PM carries NO room. The fan-out below exists precisely
                    # because the loop cannot tell which battle it refers to, so `inferred`
                    # is permitted only in the degenerate single-battle case.
                    if _recorder is not None:
                        only = next(iter(active_battles)) if len(active_battles) == 1 else None
                        _guarded(
                            _recorder.record_event, event_type="invalid_choice_pm",
                            payload=parsed.args[-1], room_id=only,
                            active_battle_count=len(active_battles),
                        )
                    for battle_room in list(active_battles):
                        await _send_default_choose(conn, battle_room)
                    continue

                if parsed.room.startswith("battle-"):
                    if parsed.prefix == "error":
                        # parse_message fills `payload` only for prefix == "request"
                        # (protocol/messages.py:26); the error text lives in args, and
                        # joining with "|" restores a payload that itself contains "|".
                        if _recorder is not None:
                            _guarded(
                                _recorder.record_event, event_type="server_error",
                                payload="|".join(parsed.args), room_id=parsed.room,
                                active_battle_count=len(active_battles),
                            )
                        await _send_default_choose(conn, parsed.room)
                    if parsed.prefix == "request":
                        await handle_battle_message(conn, parsed.room, parsed.payload)
                    if parsed.prefix in ("win", "tie"):
                        if parsed.room in active_battles:
                            # BEFORE the pop below -- that pop is where the raw log, and
                            # with it today's only evidence, is discarded (section 9).
                            if _recorder is not None:
                                _guarded(_recorder.flush_battle,
                                         room_id=parsed.room, end_reason=parsed.prefix)
                            battles_finished += 1
                            active_battles.discard(parsed.room)
                            _room_raw.pop(parsed.room, None)
                            logger.info(
                                "battle ended in %s (%d/%d)",
                                parsed.room,
                                battles_finished,
                                max_battles,
                            )
                            if battles_finished >= max_battles:
                                if cancel_on_done:
                                    await conn.send(cancel_on_done)
                                await conn.close()
                                return battles_finished
                    if parsed.prefix == "init" and parsed.args and parsed.args[0] == "battle":
                        active_battles.add(parsed.room)
                        await conn.send(f"|/join {parsed.room}")
                        logger.info("battle started: %s", parsed.room)

            logger.debug("recv %s", raw[:160])

        return battles_finished
    finally:
        # A `finally`, NOT a post-loop statement: the async-for ending, an exception (the two
        # popup RuntimeErrors are raised by this function itself) and a CancelledError are
        # exactly the exits where the evidence matters most, and a post-loop statement is
        # skipped on two of those three (section 9).
        if _recorder is not None:
            _guarded(_recorder.flush_unterminated, active_battles)
            _guarded(_recorder.flush_run_events)
            _guarded(_recorder.write_completion)
```

- [ ] **Step 3b: Preflight in all three entry points**

At the top of each of `run_ladder_search`, `run_challenge` and `run_smoke_battle`, **before**
`_connect_and_login` and before any `/search`, `/challenge` or `/utm`:

```python
    global _recorder
    _recorder = None                                   # never inherit a previous run's sink
    _recorder = LiveDegradationRecorder.preflight()    # PreflightError aborts the run
```

For `run_ladder_search` and `run_challenge` this joins the existing
`global _active_format, _our_spreads, _opp_sets` statement; add `_recorder` to it rather than
writing a second `global`. `run_smoke_battle` has no `global` today and needs
`global _recorder` added.

- [ ] **Step 4: Run, expect 9 more passed (20 in this file)**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/client/runner.py showdown_bot/tests/test_live_degradation_runner.py
git commit -m "feat: boundary flush before the raw-log pop, finally-flush, preflight call sites"
```

---

## Task 11: The process exit status (§10.3)

`exit_status()` on its own changes nothing: the three runners return battle counts and `main()`
discards them. This task is the wiring, and its whole design point is that **no exception handler
is involved**, so nothing can be masked.

**Files:** Modify `showdown_bot/src/showdown_bot/cli.py`; add to
`tests/test_live_degradation_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `showdown_bot/tests/test_live_degradation_runner.py`:

```python
def test_clean_run_does_not_raise_system_exit(monkeypatch):
    from showdown_bot import cli

    async def _ok():
        return 1

    monkeypatch.setattr(cli, "recorder_exit_status", lambda: 0)
    cli._run_live(_ok())        # must not raise


def test_a_write_error_produces_a_non_zero_process_status(monkeypatch):
    from showdown_bot import cli

    async def _ok():
        return 1

    monkeypatch.setattr(cli, "recorder_exit_status", lambda: 1)
    with pytest.raises(SystemExit) as excinfo:
        cli._run_live(_ok())
    assert excinfo.value.code == 1


def test_an_original_exception_is_never_masked(monkeypatch):
    """The status check is a plain statement AFTER asyncio.run(), so it runs only on the
    normal-return path. There is no except clause that could swallow this."""
    from showdown_bot import cli

    async def _boom():
        raise RuntimeError("the real failure")

    monkeypatch.setattr(cli, "recorder_exit_status", lambda: 1)
    with pytest.raises(RuntimeError, match="the real failure"):
        cli._run_live(_boom())


def test_a_cancellation_is_never_masked(monkeypatch):
    from showdown_bot import cli

    async def _cancelled():
        raise asyncio.CancelledError()

    monkeypatch.setattr(cli, "recorder_exit_status", lambda: 1)
    with pytest.raises(asyncio.CancelledError):
        cli._run_live(_cancelled())


def test_a_keyboard_interrupt_is_never_masked(monkeypatch):
    from showdown_bot import cli

    async def _interrupted():
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "recorder_exit_status", lambda: 1)
    with pytest.raises(KeyboardInterrupt):
        cli._run_live(_interrupted())


def test_main_routes_all_three_live_commands_through_run_live(monkeypatch):
    """Otherwise a write failure on `challenge` or `smoke` would still exit 0."""
    import inspect

    from showdown_bot import cli

    flat = "".join(inspect.getsource(cli.main).split())
    for command in ("run_ladder_search", "run_challenge", "run_smoke_battle"):
        assert f"_run_live({command}(" in flat, f"{command} is not routed through _run_live"
```

- [ ] **Step 2: Run, expect `AttributeError: module 'showdown_bot.cli' has no attribute '_run_live'`**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q -k "run_live or masked or process_status"
```

- [ ] **Step 3: Implement in `cli.py`**

Extend the existing import (`cli.py:10`):

```python
from showdown_bot.client.runner import (
    recorder_exit_status,
    run_challenge,
    run_ladder_search,
    run_smoke_battle,
)
```

Add above `main()`:

```python
def _run_live(coro) -> None:
    """Run a live runner and turn a recording failure into a non-zero process status.

    There is deliberately NO try/except here. The status check is a plain statement after
    asyncio.run(), so it executes only when the coroutine RETURNED normally; an exception, a
    KeyboardInterrupt and a CancelledError all propagate untouched and keep producing their
    own non-zero status. Nothing here can mask an original failure, because nothing here
    catches anything.

    SystemExit is how this file already reports a machine-checkable verdict -- see the two
    `raise SystemExit` call sites in the Gate B commands below.
    """
    asyncio.run(coro)
    status = recorder_exit_status()
    if status:
        raise SystemExit(status)
```

and replace the three live command bodies at the end of `main()` (`cli.py:1581-1589`):

```python
    settings = Settings.from_env()
    if args.command == "ladder":
        _run_live(run_ladder_search(settings, max_battles=args.max_battles))
    elif args.command == "challenge":
        if not args.opponent:
            parser.error("challenge requires --opponent USERNAME")
        _run_live(run_challenge(settings, args.opponent, max_battles=args.max_battles))
    elif args.command == "smoke":
        _run_live(run_smoke_battle(settings))
```

- [ ] **Step 4: Run, expect 6 more passed (26 in this file)**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q
```

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/cli.py showdown_bot/tests/test_live_degradation_runner.py
git commit -m "feat: route the three live commands through a non-masking exit-status wrapper"
```

---

## Task 12: Smoke behaviour, the real smoke run, and closeout

- [ ] **Step 1: Write the smoke-shape test**

Append to `showdown_bot/tests/test_live_degradation_runner.py`:

```python
@pytest.mark.asyncio
async def test_smoke_records_every_decision_as_not_applicable(
        tmp_path, monkeypatch, _clean_runner_state):
    """run_smoke_battle searches gen9randomdoublesbattle, for which _get_book returns None
    (and, separately, run_smoke_battle never assigns _active_format at all). So `state is
    None` on every decision while NOTHING is degraded. A naive `state is None` rule would
    report smoke as 100% degraded."""
    rec = _install_recorder(monkeypatch, tmp_path)
    monkeypatch.setenv("SHOWDOWN_TURN_TRACE", "0")
    monkeypatch.setattr(runner, "_active_format", None)
    monkeypatch.setattr(runner, "choose_for_request",
                        lambda req: f"/choose default|{req.rqid}")
    runner.reset_format_caches()
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|win|opponent",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)

    rows = [json.loads(line) for line in
            (rec.run_dir / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows
    assert all(r["book_absent"] is True for r in rows)
    assert all(r["derivation_applicable"] is False for r in rows)
    assert all(r["is_degraded"] is None for r in rows)
    assert all(r["outcome"] == "not_applicable" for r in rows)
    assert all(r["state_build_failed"] is False for r in rows)

    battle = _battle_rows(rec)[0]
    assert battle["degraded_decisions"] == 0
    assert battle["state_build_failures"] == 0
    assert battle["decisions_not_applicable"] == len(rows)
```

- [ ] **Step 2: Run it**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q -k smoke
```

Expected: **PASS with no new production code.** If it fails, the §5.1 gate is wrong, not the
test — fix the gate, not the assertion.

- [ ] **Step 3: The artifact invariant, both run shapes (§8.0)**

`validate_completion_row()` cannot establish the cross-file `run_id` identity — it sees one
object, and `expected_run_id` proves only that the recorder agrees with itself. §8.0 makes the
cross-file property a **directory-level invariant with its own check**, and it must not demand
files a correct run never creates: nothing writes an empty file, so a run with no `|error|` and
no invalid-choice PM has **no `events.jsonl` at all**.

Append to `showdown_bot/tests/test_live_degradation_runner.py`:

```python
def _run_id_of_every_line(run_dir: Path) -> set[str]:
    """Collect run_id from every JSONL line PRESENT. A missing file is zero rows, not a
    violation -- see the second test below for why that distinction is load-bearing."""
    seen: set[str] = set()
    for name in ("decisions.jsonl", "events.jsonl", "battles.jsonl"):
        path = run_dir / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(json.loads(line)["run_id"])
    return seen


@pytest.mark.asyncio
async def test_artifact_invariant_on_a_run_that_produces_every_grain(
        tmp_path, monkeypatch, _clean_runner_state):
    """Shape 1: decisions, at least one event, a battle row and a completion."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|error|[Invalid choice] Can't move: Zamazenta needs a target",
        f">{ROOM}\n|win|opponent",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)

    for name in ("decisions.jsonl", "events.jsonl", "battles.jsonl", "completion.json"):
        assert (rec.run_dir / name).exists(), f"{name} missing on the all-grains shape"
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    validate_completion_row(dict(completion), expected_run_id=rec.run_id)
    assert _run_id_of_every_line(rec.run_dir) == {completion["run_id"]}
    assert completion["run_id"] == rec.run_dir.name          # §8.1: dir name IS the run_id


@pytest.mark.asyncio
async def test_artifact_invariant_on_a_run_with_no_events(
        tmp_path, monkeypatch, _clean_runner_state):
    """Shape 2, and the commonest one: no |error| and no invalid-choice PM. events.jsonl is
    ABSENT, and with all three counters at zero that absence means zero rows, not loss. An
    invariant demanding all four files would fail here -- on a correct run."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|win|opponent",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)

    assert not (rec.run_dir / "events.jsonl").exists()
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    validate_completion_row(dict(completion), expected_run_id=rec.run_id)
    assert completion["write_errors_total"] == 0
    assert completion["schema_errors_total"] == 0
    assert completion["recorder_errors_total"] == 0
    assert rec.exit_status() == 0                            # absence here is emptiness
    assert _run_id_of_every_line(rec.run_dir) == {completion["run_id"]}
```

The test file needs `validate_completion_row` in its imports:

```python
from showdown_bot.client.live_degradation import (
    LiveDegradationRecorder,
    validate_completion_row,
)
```

- [ ] **Step 4: Run, expect 29 passed in this file**

```bash
python -m pytest showdown_bot/tests/test_live_degradation_runner.py -q
```

- [ ] **Step 5: The real smoke run — requires the user's explicit go-ahead**

This step plays one real battle against a real opponent on the public server. It is an
outward-facing action; **do not run it without the user saying so in this session.** No local
alternative is in scope: `_connect_and_login` uses `authenticate` (not `authenticate_local`), and
pairing a smoke search on a private server needs a second client this slice does not build.

Preconditions, all of them:

| Precondition | Value |
|---|---|
| Working directory | the repo root (`logs/live-degradation/` resolves relative to the CWD) |
| Tree state | clean apart from the seven known local artifacts (Step 5) |
| `SHOWDOWN_USERNAME` | a throwaway, **unregistered** name; `fetch_assertion` takes the guest path when the password is empty (`client/auth.py:106-110`) |
| `SHOWDOWN_PASSWORD` | **unset or empty.** A registered password must never be typed into a command that is pasted into a report |
| `SHOWDOWN_SERVER` | unset — the default `wss://sim3.psim.us/showdown/websocket` |
| `SHOWDOWN_LIVE_DEGRADATION_DIR` | unset — this run must prove the default path |

One PowerShell process, one tool call:

```powershell
$env:SHOWDOWN_USERNAME = "<throwaway-unregistered-name>"; $env:SHOWDOWN_PASSWORD = ""; Remove-Item Env:SHOWDOWN_LIVE_DEGRADATION_DIR -ErrorAction SilentlyContinue; python -m showdown_bot.cli smoke; Write-Output "exit=$LASTEXITCODE"
```

Then locate the run directory and read all four artifacts:

```powershell
$run = Get-ChildItem logs/live-degradation | Sort-Object LastWriteTime | Select-Object -Last 1; Write-Output $run.FullName; Get-Content "$($run.FullName)/completion.json"; Get-Content "$($run.FullName)/decisions.jsonl" -TotalCount 1; Get-Content "$($run.FullName)/battles.jsonl"
```

Output rules for the closeout report:

1. Paste the **first** `decisions.jsonl` row, the `battles.jsonl` row and the whole
   `completion.json` **verbatim**. A hand-written sample does not satisfy this step; if the run
   did not happen, the report says so and the step stays open.
2. Record `exit=` verbatim. `exit=0` is the expected result; any other value means
   `write_errors_total`, `schema_errors` or `recorder_errors` was non-zero and the closeout
   reports the cause.
3. **Credential scrub before pasting.** The chosen username can appear inside a `payload` field
   and in `run_id`-adjacent log lines. Search the three pasted blocks for the username string;
   if it occurs, replace it with `<smoke-user>` and state in the report that the substitution was
   made and where. Never paste `SHOWDOWN_PASSWORD`, an assertion string, or a session cookie.
4. **Artifact rule.** The run directory itself is evidence but is **not committed** — it is
   covered by the `.gitignore` entry from Task 3, and the repository hygiene rule keeps raw logs
   out of commits. Only the three excerpts, inside the closeout report, enter git.
5. Record the run directory name (it contains the UTC timestamp and the random suffix) so the
   excerpts can be traced back to the run that produced them.

Write the report at `docs/projects/champions/reports/2026-07-29-live-path-degradation-closeout.md`.

- [ ] **Step 6: Closeout gates**

```bash
git diff --check
```

Expected: silent (no whitespace errors).

```bash
python -m pytest showdown_bot -q
```

Expected: **at or above** the `main @ 43f08af` baseline of `3860 passed, 2 skipped, 1 xfailed`,
plus the new tests, with no new failures. Run from the repo root, and note that
`python -m pytest showdown_bot -q` (not a bare `pytest -q`) is the form that actually picks up
new modules in this repo.

- [ ] **Step 7: Confirm the seven local artifacts are untouched**

```bash
git status --porcelain
```

Expected: the intended files as modified/added, and these still listed as untracked and
unmodified — `.claude/`,
`docs/projects/evaluation/specs/2026-07-22-luck-adjusted-outcome-research-note.md`,
`reports/2026-07-16-pokemon-showdown-bot-referenzrecherche.md`,
`reports/2026-07-16-pokemon-showdown-quellenannotationen.md`, `showdown_bot/uv.lock`,
`showdownbot_studio/docs/plans/2026-07-26-phase3-m2-part1-login-and-matchmaking.md`,
`tools/_pkmn_differential_audit/`. **No `logs/` entry may appear** — if one does, the Task 3
gitignore entry is wrong.

- [ ] **Step 8: Commit the closeout**

```bash
git add docs/projects/champions/reports/2026-07-29-live-path-degradation-closeout.md
git commit -m "docs: live-path degradation recording closeout"
```

---

## Coverage matrix — decision record §4–§10

| § | Requirement | Task |
|---|---|---|
| §4 | Raw facts, own seat only | 5, 6 |
| §4 | Context layer (`book_absent`, `team_preview`) | 1, 5 |
| §4 | Derivation gated | 5 |
| §4 | Aggregation, no cross-seat mixing | 7 (C7 test in 1) |
| §4 | Transport via `SelectionStageSink` | 9 |
| §4 | Persistence = `live-degradation-v1`, not the decision-profile schema | 1, 2, 8 |
| §5 | `state_build_failed` ≠ `state is None` (three situations) | 9 (all three asserted), 2 (validator forbids the impossible combination) |
| §5 | `run_smoke_battle` consequence | 12 |
| §5.1 | Gate; `not_applicable` counts nothing | 5, 7, 12 |
| §5.1 | Neither derivation is CALLED when the gate is false | 5 (`test_crash_on_the_book_absent_path_stays_not_applicable`) |
| §6 | Crash recorded, re-raised unchanged, no new fallback | 9 |
| §7 | `\|error\|` room-scoped, payload preserved, not pre-classified | 6, 9 |
| §7 | PM unattributable; `inferred` only at `active_battle_count == 1` | 6, 9 |
| §8 | Closed schema: field set, order, types, enums, null rules | 1, 2 |
| §8.0 | `completion.json` carries all three error counters | 1, 8 |
| §8.0 | Three zeros = a clean **snapshot**, never a verdict | 8 (four separate exit tests) |
| §8.0 | Success = exit `0` **and** a present, parsing, validating, three-zero file | 8, 11, 12 |
| §8.0 | Absent / unparseable / schema-invalid are one failure state | 8 |
| §8.0 | Persistence limit: the completion write's own failure is not in it | 8 |
| §8.0 | No `recording_ok` field | 1 (`COMPLETION_FIELDS`), 2 (`extra_field` mutation) |
| §8.0 | `validate_completion_row(row, *, expected_run_id=None)` + mutation tests | 2 |
| §8.0 | Artifact invariant is a directory check, not a row check | 2 (what the row cannot prove), 12 (both shapes) |
| §8 | `is_degraded` persisted; `null`, never `false`, when gated | 2, 5 |
| §8 | Counters from their named sources | 7 |
| §8 | Join keys `run_id` / `(run_id, room_id)` / `(…, decision_seq)`; `rqid` not a join key | 1, 5 (`decision_seq` monotonic per room) |
| §8 | `unattributed` increments no battle counter | 2, 7 |
| §8.1 | Exclusive dir, no truncating open, no overwrite | 4, 8 |
| §8.1 | `SHOWDOWN_LIVE_DEGRADATION_DIR` override, parent only | 4 |
| §8.1 | `NON_BEHAVIORAL` classification obligation | 3 |
| §9 | Flush before `_room_raw.pop` | 10 |
| §9 | `finally` for stream end, exception, cancellation | 10 (four tests: stream end, generic exception, the `not ladderable` popup, cancellation) |
| §10.1 | Preflight fails closed before connect/search, in all three entry points | 4, 10 |
| §10.2 | No turn-path write; flush errors never propagate; no bound claimed | 8 (C1/C2 in docstrings and tests) |
| §10.3 | In-memory counter + `logger.error` | 8 |
| §10.3 | Best-effort `completion.json`; its absence is a failure state | 8 |
| §10.3 | Non-zero process exit status, without masking | 11 |
| §10.3 | Status evaluated **last**, after every finalisation attempt | 8 (`exit_status` docstring), 11 |
| §10.4 | Buffered-design residual limit documented, not fixed here | — (this document + the non-claims below) |

## Coverage matrix — #125 acceptance criteria

| Criterion | Task |
|---|---|
| Raw facts recorded, always on, no enabling flag | 4, 10 |
| Flush before the room log is discarded; loop-exit flush on all three exits | 10 |
| Write failure blocks nothing, is counted, surfaces at completion | 8 |
| Non-zero process exit; a missing `completion.json` counts as failure | 8, 11 |
| All three counters **persisted**, not merely surfaced via the exit status | 1, 2, 8 |
| Clean run → three zeros + exit 0; prior schema error → 1 + exit 1; prior recorder error → 1 + exit 1; unwritable completion → exit 1 | 8 (four separate tests) |
| A present-but-unusable `completion.json` is a failure, not a success | 8 |
| Artifact invariant, all-grains shape **and** no-events shape | 12 |
| No `hero_`/`villain_` names | 1 |
| `state_build_failed` not raised for preview, missing book, or smoke | 2, 9, 12 |
| Derivation gated so smoke is not reported 100 % degraded | 5, 12 |
| `is_degraded` persisted, `null` when gated; `degraded_decisions` counts it | 2, 5, 7 |
| Counters from named sources; `unattributed` increments nothing | 2, 7 |
| `SHOWDOWN_LIVE_DEGRADATION_DIR` in `NON_BEHAVIORAL`, with its own tests | 3, 4 |
| Closed schema enforced by validators, proven by mutation tests | 2 |
| Integration tests: end-to-end, unterminated ×4, failed write, preflight ×2, refused dir, smoke | 4, 8, 10, 12 |
| Recording never changes the chosen action or prevents it being sent | 9 |
| `python -m pytest showdown_bot -q` passes at or above baseline | 12 |

---

## Non-claims

This slice records. It makes **no strength claim**, no production-readiness claim and no latency
claim, and it changes no chosen action — Task 9 asserts the sent string is byte-identical with and
without the recorder. `_abort_on_degradation` stays narrower than what is recorded; that asymmetry
is the decision record's explicit non-goal (C4), not a gap to close later by accident.

Two limits are stated rather than hidden:

- A hard process termination (`SIGKILL`, power loss, OOM kill) loses the current battle's
  unflushed decisions. No `finally` runs. This is §10.4's accepted residual gap of the buffered
  design; per-decision appending was rejected because it puts a filesystem write on the turn path.
- `completion.json` is written **exclusively but not atomically** (§8.0): `open(..., "x")` buys
  exclusivity only, so a write that dies after the create leaves an empty, truncated or unsynced
  file. The plan does not fix that — an atomic temp-file commit would need §8.1 reopened — so
  *absent*, *unparseable* and *schema-invalid* are treated as one failure state, and success
  requires exit `0` **plus** a present, parsing, validating, three-zero file.

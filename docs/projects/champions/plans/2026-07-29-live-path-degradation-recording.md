# Live-Path Degradation Recording — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `client/runner.py` records `live-degradation-v1` evidence for its own seat on every
ladder, challenge and smoke run, always on, without touching the turn path or the chosen action.

**Base:** `main @ 43f08af` · **Issue:** #125
**Authoritative decision:** `docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md`
(referenced below as §N — the plan implements it and adds no new rulings).

**Architecture:** one new self-contained module owns the schema, the writer and the aggregation.
`runner.py` gains call sites only. The decision core is untouched: the existing
`SelectionStageSink` already carries `selection_stage`/`fallback_reason`, and
`is_degraded_decision()` / `classify_live_outcome()` are used unchanged, behind the §5.1 gate.

**Tech stack:** Python 3.14, stdlib only (`json`, `os`, `pathlib`, `datetime`, `secrets`), pytest.

> **STATUS: NOT YET EXECUTABLE — do not start implementation from this revision.**
>
> Review of PR #145 found six defects. Fixed in this revision: the `flush_battle` ordering bug
> (decisions were popped before aggregation, so every battle row would have been all-zero), the
> lost `unattributed` events (now `flush_run_events`), the truncating `completion.json` write
> (now exclusive, C9), the first-turn filesystem import, `except BaseException` swallowing
> `CancelledError`/`KeyboardInterrupt`/`SystemExit` as agent crashes, the unapproved
> `payload[:500]` truncation, and the wrong closeout baseline.
>
> **Still outstanding, and this revision does not claim otherwise:**
> 1. **Validators are missing.** Field-name tuples do not close a schema. `record_event` still
>    accepts unknown `event_type` values and contradictory attribution combinations; decision and
>    battle rows are unvalidated. Needs `validate_decision_row` / `validate_event_row` /
>    `validate_battle_row` plus mutation tests for field set, types, enums, null rules and
>    cross-field consistency.
> 2. **The exit status is not wired to a process status.** `exit_status()` alone changes nothing:
>    the three runners return battle counts and `cli.py` ignores those returns. The plan must say
>    exactly how a clean-finishing run with a write error reaches a non-zero process status
>    **without masking an original exception or a cancellation**.
> 3. **Placeholders remain.** Task 8's test helpers, all five Task 9 tests, the Task 10 smoke
>    driver and two production blocks still contain `...`. An earlier revision of this plan and
>    its PR body both claimed "no placeholders". That claim was false and is withdrawn.
> 4. **A recorder or validator failure after a successful choice must not stop the chosen action
>    being sent.** No fail-closed rule for that has been approved.
> 5. **The environment override needs its own test.**
> 6. **The real-smoke step needs a complete command** plus explicit output and credential rules.

---

## Load-bearing constraints (from the decision record)

These are gates, not preferences. Every task below is written to keep them.

| # | Constraint | Enforced by |
|---|---|---|
| C1 | No filesystem access on the turn path | Task 5 buffers in memory; Task 8 flushes only at boundaries |
| C2 | No latency bound claimed at the boundary flush | Task 8 docstring; no timeout, no assertion of one |
| C3 | No background writer | Single-threaded module; no `threading`/`asyncio.to_thread` |
| C4 | No automatic degradation abort | Nothing in the module raises on a degraded count |
| C5 | No new chooser fallback | Task 6 re-raises the caught exception unchanged |
| C6 | Decision-profile schema untouched | New module; no import of `eval/decision_profile`'s writers |
| C7 | No `hero_`/`villain_` fields | Task 1 schema test asserts absence |
| C8 | `unattributed` events increment no battle counter | Task 7 predicate + Task 9 test |
| C9 | Existing evidence never overwritten | Task 3 `exist_ok=False`, no truncating open |
| C10 | No strength or production-readiness claim | Docs only assert recording |

---

## File structure

| File | Responsibility |
|---|---|
| **Create** `showdown_bot/src/showdown_bot/client/live_degradation.py` | Schema constants, row builders, `LiveDegradationRecorder` (preflight, buffers, flush, counters, exit status) |
| **Modify** `showdown_bot/src/showdown_bot/client/runner.py` | Call sites only: preflight, decision record, event record, boundary flush, `finally` |
| **Modify** `showdown_bot/src/showdown_bot/eval/config_env.py` | Add `SHOWDOWN_LIVE_DEGRADATION_DIR` to `NON_BEHAVIORAL` |
| **Create** `showdown_bot/tests/test_live_degradation.py` | Schema, recorder, counters, preflight, write failures |
| **Create** `showdown_bot/tests/test_live_degradation_runner.py` | Runner wiring, boundaries, `finally`, smoke |

---

## Task 1: Schema constants and the closed field set

**Files:** Create `client/live_degradation.py`; create `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing test**

```python
from showdown_bot.client.live_degradation import (
    SCHEMA_VERSION, DECISION_FIELDS, EVENT_FIELDS, BATTLE_FIELDS, COMPLETION_FIELDS,
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
        "write_errors_total", "preflight_ok",
    )


def test_no_hero_or_villain_field_anywhere():
    """C7: the live runner holds one seat; hero_/villain_ names would be
    structurally always zero and read as 'clean' rather than 'not observable'."""
    every = DECISION_FIELDS + EVENT_FIELDS + BATTLE_FIELDS + COMPLETION_FIELDS
    assert not [f for f in every if f.startswith(("hero_", "villain_"))]
```

- [ ] **Step 2: Run it, expect ImportError**

Run: `python -m pytest showdown_bot/tests/test_live_degradation.py -q`
Expected: `ModuleNotFoundError: No module named 'showdown_bot.client.live_degradation'`

- [ ] **Step 3: Implement the constants**

```python
"""live-degradation-v1: own-seat degradation evidence for the live runner.

Implements docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md.
Deliberately independent of eval/decision_profile's closed schema (§8, C6).
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
    "write_errors_total", "preflight_ok",
)

EVENT_TYPES = ("server_error", "invalid_choice_pm")
ATTRIBUTIONS = ("room", "inferred", "unattributed")
END_REASONS = ("win", "tie", "unterminated")
```

- [ ] **Step 4: Run, expect 5 passed**

- [ ] **Step 5: Commit** — `git add showdown_bot/src/showdown_bot/client/live_degradation.py showdown_bot/tests/test_live_degradation.py && git commit -m "feat: live-degradation-v1 schema constants"`

---

## Task 2: `SHOWDOWN_LIVE_DEGRADATION_DIR` is NON_BEHAVIORAL

**Files:** Modify `eval/config_env.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing test**

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
```

- [ ] **Step 2: Run, expect `AssertionError: assert 'SHOWDOWN_LIVE_DEGRADATION_DIR' in frozenset(...)`**

- [ ] **Step 3: Implement** — in `config_env.py`, directly after the `"SHOWDOWN_DECISION_PROFILE_OUT",` entry (line 126):

```python
    # Live-path degradation sink DIRECTORY (live-degradation-v1). Same species as
    # SHOWDOWN_DECISION_PROFILE_OUT above: an IO path with no /choose effect. It must be
    # classified, not merely commented -- is_excluded fails closed toward INCLUSION, so an
    # unclassified name lands in behavior_env and thus in config_hash, and merely choosing
    # where to write telemetry would change the identity of the run being measured.
    "SHOWDOWN_LIVE_DEGRADATION_DIR",
```

- [ ] **Step 4: Run both the new test and the drift test**

Run: `python -m pytest showdown_bot/tests/test_live_degradation.py showdown_bot/tests/test_config_env.py -q`
Expected: all pass. The `is_classified` drift test in `test_config_env.py` must stay green — it
asserts every `SHOWDOWN_*` read in source is classified, and Task 5 adds the read.

- [ ] **Step 5: Commit**

---

## Task 3: Run directory and writer preflight (§10.1, C9)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
import pytest
from pathlib import Path
from showdown_bot.client.live_degradation import LiveDegradationRecorder, PreflightError


def test_preflight_creates_exclusive_run_dir(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert rec.run_dir.parent == tmp_path
    assert rec.run_dir.is_dir()
    assert rec.run_id in rec.run_dir.name


def test_preflight_refuses_an_existing_run_dir(tmp_path, monkeypatch):
    """C9: a new run must never reuse or overwrite existing evidence."""
    monkeypatch.setattr(
        "showdown_bot.client.live_degradation._new_run_id", lambda: "fixed-run-id")
    LiveDegradationRecorder.preflight(parent=tmp_path)
    with pytest.raises(PreflightError, match="already exists"):
        LiveDegradationRecorder.preflight(parent=tmp_path)


def test_preflight_fails_when_parent_is_unwritable(tmp_path):
    target = tmp_path / "not-a-dir"
    target.write_text("blocking file", encoding="utf-8")
    with pytest.raises(PreflightError):
        LiveDegradationRecorder.preflight(parent=target)


def test_preflight_probe_is_removed_and_dir_left_empty(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    assert list(rec.run_dir.iterdir()) == []
```

- [ ] **Step 2: Run, expect `ImportError: cannot import name 'LiveDegradationRecorder'`**

- [ ] **Step 3: Implement**

```python
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

# Module level, NOT inside record_decision: a first-turn import would put a filesystem
# read on the turn path (C1).
from showdown_bot.eval.decision_profile import classify_live_outcome, is_degraded_decision

logger = logging.getLogger(__name__)

DEFAULT_PARENT = Path("logs") / "live-degradation"
DIR_ENV = "SHOWDOWN_LIVE_DEGRADATION_DIR"


class PreflightError(RuntimeError):
    """The sink could not be established. Raised BEFORE connect/search (§10.1)."""


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def resolve_parent(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    override = os.environ.get(DIR_ENV)
    return Path(override) if override else DEFAULT_PARENT


class LiveDegradationRecorder:
    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.write_errors_total = 0
        self.battles_finished = 0
        self.unterminated_rooms: list[str] = []
        self._decisions: dict[str, list[dict]] = {}
        self._events: list[dict] = []
        self._room_write_errors: dict[str, int] = {}
        self._seq: dict[str, int] = {}

    @classmethod
    def preflight(cls, *, parent: Path | None = None) -> "LiveDegradationRecorder":
        """Create the run directory exclusively and prove the writer works.

        Called BEFORE _connect_and_login and before any /search or challenge (§10.1).
        This is the ONE place a recording failure may stop the run: nothing has been
        played, so aborting costs nothing, whereas an unwritable sink discovered after
        50 ladder games costs all 50 games' evidence.
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

- [ ] **Step 4: Run, expect 4 passed**

- [ ] **Step 5: Commit**

---

## Task 4: Decision rows — the §5.1 gate and `is_degraded`

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_gate_false_for_book_absent_records_not_applicable(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=3, book_absent=True, team_preview=False,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None,
    )
    assert row["derivation_applicable"] is False
    assert row["is_degraded"] is None       # NOT False -- "not asked" != "not degraded"
    assert row["outcome"] == "not_applicable"


def test_gate_false_for_team_preview(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=1, book_absent=False, team_preview=True,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None,
    )
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


def test_gate_true_clean_decision(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=5, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="heuristic", fallback_reason=None,
        agent_crash_type=None,
    )
    assert row["derivation_applicable"] is True
    assert row["is_degraded"] is False
    assert row["outcome"] == "ok"


def test_gate_true_state_build_failure_is_degraded(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=6, book_absent=False, team_preview=False,
        state_build_failed=True, selection_stage="heuristic", fallback_reason=None,
        agent_crash_type=None,
    )
    assert row["is_degraded"] is True
    assert row["outcome"] == "degraded_state"


def test_decision_seq_is_monotonic_per_room(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    seqs = [
        rec.record_decision(
            room_id=r, rqid=i, book_absent=False, team_preview=False,
            state_build_failed=False, selection_stage="heuristic",
            fallback_reason=None, agent_crash_type=None)["decision_seq"]
        for r, i in (("a", 1), ("a", 2), ("b", 1), ("a", 3))
    ]
    assert seqs == [0, 1, 0, 2]


def test_row_has_exactly_the_declared_fields(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    row = rec.record_decision(
        room_id="battle-x-1", rqid=1, book_absent=True, team_preview=False,
        state_build_failed=False, selection_stage=None, fallback_reason=None,
        agent_crash_type=None)
    assert tuple(row) == DECISION_FIELDS
```

- [ ] **Step 2: Run, expect `AttributeError: 'LiveDegradationRecorder' object has no attribute 'record_decision'`**

- [ ] **Step 3: Implement**

```python
    def record_decision(
        self, *, room_id: str, rqid: int | None, book_absent: bool, team_preview: bool,
        state_build_failed: bool, selection_stage: str | None, fallback_reason: str | None,
        agent_crash_type: str | None,
    ) -> dict:
        """Buffer one decision row. NO filesystem access here (C1)."""
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
            # §5.1: neither function is called. Ungated, is_degraded_decision fails
            # closed to True and classify_live_outcome raises -- both wrong here.
            is_degraded = None
            outcome = "not_applicable"

        seq = self._seq.get(room_id, 0)
        self._seq[room_id] = seq + 1
        row = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id, "room_id": room_id,
            "decision_seq": seq, "rqid": rqid, "book_absent": book_absent,
            "team_preview": team_preview, "state_build_failed": state_build_failed,
            "selection_stage": selection_stage, "fallback_reason": fallback_reason,
            "agent_crash_type": agent_crash_type, "derivation_applicable": applicable,
            "is_degraded": is_degraded, "outcome": outcome,
        }
        self._decisions.setdefault(room_id, []).append(row)
        return row
```

- [ ] **Step 4: Run, expect 6 passed**

- [ ] **Step 5: Commit**

---

## Task 5: Event rows and attribution (§7, C8)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_server_error_is_room_attributed(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="server_error", payload="[Invalid choice] x",
                          room_id="battle-x-1", active_battle_count=2)
    assert ev["attribution"] == "room" and ev["room_id"] == "battle-x-1"


def test_invalid_choice_pm_with_two_active_battles_is_unattributed(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id=None, active_battle_count=2)
    assert ev["attribution"] == "unattributed" and ev["room_id"] is None


def test_invalid_choice_pm_with_one_active_battle_is_inferred(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="invalid_choice_pm", payload="Invalid choice",
                          room_id="battle-x-1", active_battle_count=1)
    assert ev["attribution"] == "inferred" and ev["room_id"] == "battle-x-1"


def test_event_row_has_exactly_the_declared_fields(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    ev = rec.record_event(event_type="server_error", payload="p",
                          room_id="r", active_battle_count=1)
    assert tuple(ev) == EVENT_FIELDS
```

- [ ] **Step 2: Run, expect `AttributeError: ... 'record_event'`**

- [ ] **Step 3: Implement**

```python
    def record_event(
        self, *, event_type: str, payload: str, room_id: str | None,
        active_battle_count: int,
    ) -> dict:
        """Buffer one asynchronous event. NO filesystem access here (C1).

        The invalid-choice PM carries no room -- the loop fans _send_default_choose out to
        EVERY active battle precisely because it cannot tell which one it means. It is
        therefore unattributable in general; `inferred` is permitted only in the degenerate
        single-battle case and is recorded as such, never as `room` (§7).
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
        self._events.append(ev)
        return ev
```

- [ ] **Step 4: Run, expect 4 passed** · **Step 5: Commit**

---

## Task 6: Battle aggregation from the named sources (§8)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

```python
def _clean(rec, room, rqid):
    return rec.record_decision(
        room_id=room, rqid=rqid, book_absent=False, team_preview=False,
        state_build_failed=False, selection_stage="heuristic",
        fallback_reason=None, agent_crash_type=None)


def test_counters_come_from_their_named_sources(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _clean(rec, "R", 1)
    rec.record_decision(room_id="R", rqid=2, book_absent=True, team_preview=False,
                        state_build_failed=False, selection_stage=None,
                        fallback_reason=None, agent_crash_type=None)
    rec.record_decision(room_id="R", rqid=3, book_absent=False, team_preview=False,
                        state_build_failed=True, selection_stage="heuristic",
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


def test_unattributed_event_increments_no_battle_counter(tmp_path):
    """C8: charging an unattributable event to a room -- or to all -- would
    manufacture degradation never observed on that battle."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _clean(rec, "R", 1)
    rec.record_event(event_type="invalid_choice_pm", payload="p",
                     room_id=None, active_battle_count=3)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["own_invalid_choices"] == 0
    assert row["degraded_decisions"] == 0


def test_not_applicable_rows_are_never_counted_as_degraded(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    for i in range(4):
        rec.record_decision(room_id="R", rqid=i, book_absent=True, team_preview=False,
                            state_build_failed=False, selection_stage=None,
                            fallback_reason=None, agent_crash_type=None)
    row = rec.build_battle_row(room_id="R", end_reason="win")
    assert row["decisions_not_applicable"] == 4 and row["degraded_decisions"] == 0
```

- [ ] **Step 2: Run, expect `AttributeError: ... 'build_battle_row'`**

- [ ] **Step 3: Implement**

```python
    def build_battle_row(self, *, room_id: str, end_reason: str) -> dict:
        """Aggregate one battle from the sources named per counter (§8).

        Not every counter comes from decisions.jsonl: own_invalid_choices and
        server_errors come from the event stream, and write_errors from the in-memory
        failure counter -- necessarily, since the rows are what could not be written.
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
                if e["event_type"] == "invalid_choice_pm" and e["attribution"] == "inferred"),
            "server_errors": sum(1 for e in evs if e["event_type"] == "server_error"),
            "end_reason": end_reason,
            "write_errors": self._room_write_errors.get(room_id, 0),
        }
```

- [ ] **Step 4: Run, expect 3 passed** · **Step 5: Commit**

---

## Task 7: Flush, write-failure accounting, completion, exit status (§10.2–§10.4)

**Files:** Modify `live_degradation.py`; add to `tests/test_live_degradation.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_flush_writes_decisions_events_and_battle(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _clean(rec, "R", 1)
    rec.record_event(event_type="server_error", payload="p",
                     room_id="R", active_battle_count=1)
    rec.flush_battle(room_id="R", end_reason="win")
    dec = (rec.run_dir / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    bat = (rec.run_dir / "battles.jsonl").read_text(encoding="utf-8").splitlines()
    evt = (rec.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(dec) == 1 and len(bat) == 1 and len(evt) == 1
    assert json.loads(bat[0])["end_reason"] == "win"


def test_flush_appends_and_never_truncates(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _clean(rec, "A", 1)
    rec.flush_battle(room_id="A", end_reason="win")
    _clean(rec, "B", 1)
    rec.flush_battle(room_id="B", end_reason="tie")
    assert len((rec.run_dir / "battles.jsonl").read_text(
        encoding="utf-8").splitlines()) == 2


def test_flush_failure_is_counted_and_never_raises(tmp_path, monkeypatch):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _clean(rec, "R", 1)

    def boom(*a, **k):
        raise OSError("disk gone")

    monkeypatch.setattr("showdown_bot.client.live_degradation._append_jsonl", boom)
    rec.flush_battle(room_id="R", end_reason="win")   # must NOT raise (C1/§10.2)
    assert rec.write_errors_total > 0
    assert rec.exit_status() != 0


def test_exit_status_zero_on_a_clean_run(tmp_path):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    _clean(rec, "R", 1)
    rec.flush_battle(room_id="R", end_reason="win")
    rec.write_completion()
    assert rec.exit_status() == 0


def test_completion_is_best_effort_and_absence_is_a_failure_signal(tmp_path, monkeypatch):
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr("showdown_bot.client.live_degradation._write_json_exclusive", boom_json)
    rec.write_completion()                      # must not raise
    assert not (rec.run_dir / "completion.json").exists()
    assert rec.exit_status() != 0               # the machine-checkable signal (§10.3)
```

Add at module scope of the test file:

```python
def boom_json(*a, **k):
    raise OSError("disk gone")
```

- [ ] **Step 2: Run, expect `AttributeError: ... 'flush_battle'`**

- [ ] **Step 3: Implement**

```python
def _append_jsonl(path: Path, rows: list[dict]) -> None:
    """Append-only. Never opens in a truncating mode (C9)."""
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _write_json_exclusive(path: Path, payload: dict) -> None:
    """Exclusive create (C9). Mode "w" would truncate; inside a run directory that is
    by construction ours, an EXISTING completion.json means something already wrote
    here -- that is a refusal, not a file to overwrite."""
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
```

```python
    def flush_battle(self, *, room_id: str, end_reason: str) -> None:
        """Flush one battle at its boundary. Synchronous, with NO latency bound (C2).

        Called BEFORE _room_raw.pop(room) discards the raw log -- that pop is where
        today's evidence is thrown away (§9). Errors are counted and logged, never
        propagated into the battle (§10.2). This is deliberately not backgrounded (C3);
        the accepted consequence is that a stalled disk here can delay message processing
        for other active battles, and no upper bound is claimed.
        """
        rows = self._decisions.pop(room_id, [])
        evs = [e for e in self._events if e["room_id"] == room_id]
        battle_row = self.build_battle_row(room_id=room_id, end_reason=end_reason)
        for path, payload in (
            (self.run_dir / "decisions.jsonl", rows),
            (self.run_dir / "events.jsonl", evs),
            (self.run_dir / "battles.jsonl", [battle_row]),
        ):
            if not payload:
                continue
            try:
                _append_jsonl(path, payload)
            except OSError as exc:                       # noqa: BLE001 - never reaches the battle
                self.write_errors_total += 1
                self._room_write_errors[room_id] = self._room_write_errors.get(room_id, 0) + 1
                logger.error("live-degradation flush failed for %s -> %s: %s",
                             room_id, path.name, exc)
        self._events = [e for e in self._events if e["room_id"] != room_id]
        self._seq.pop(room_id, None)

    def flush_unterminated(self, rooms) -> None:
        for room_id in list(rooms):
            self.unterminated_rooms.append(room_id)
            self.flush_battle(room_id=room_id, end_reason="unterminated")

    def write_completion(self) -> None:
        """Best-effort (§10.3). Its ABSENCE is meaningful, not neutral."""
        payload = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "battles_finished": self.battles_finished,
            "unterminated_rooms": self.unterminated_rooms,
            "write_errors_total": self.write_errors_total,
            "preflight_ok": True,
        }
        try:
            _write_json_exclusive(self.run_dir / "completion.json", payload)
        except OSError as exc:                            # noqa: BLE001
            self.write_errors_total += 1
            logger.error("live-degradation completion write failed: %s", exc)

    def exit_status(self) -> int:
        """The machine-checkable signal (§10.3): depends on no file being writable."""
        return 1 if self.write_errors_total else 0
```

- [ ] **Step 4: Run, expect 5 passed** · **Step 5: Commit**

---

## Task 8: Runner wiring — decisions, crash re-raise, events

**Files:** Modify `client/runner.py`; create `tests/test_live_degradation_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from showdown_bot.client import runner
from showdown_bot.client.live_degradation import LiveDegradationRecorder


def test_chooser_exception_is_recorded_then_re_raised(tmp_path, monkeypatch):
    """C5: the chooser call is unguarded today, so the exception propagates.
    Adding a default-choose fallback would change what the bot DOES."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(runner, "_recorder", rec)
    monkeypatch.setattr(runner, "choose_for_request",
                        lambda req: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(ValueError, match="boom"):
        runner_handle_one_request(room="battle-x-1", team_preview=False)
    row = rec._decisions["battle-x-1"][0]
    assert row["agent_crash_type"] == "ValueError"


def test_chosen_action_is_unchanged_by_recording(tmp_path, monkeypatch):
    """C5: recording must not alter the action string."""
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(runner, "_recorder", rec)
    sent = capture_sent_action(room="battle-x-1")
    assert sent == expected_action_without_recorder(room="battle-x-1")
```

> `runner_handle_one_request`, `capture_sent_action` and
> `expected_action_without_recorder` are local helpers defined at the top of this test
> module; each builds a `BattleRequest` from the fixture payload in
> `showdown_bot/tests/fixtures/` and drives `runner.handle_battle_message` against a stub
> connection that records what was sent.

- [ ] **Step 2: Run, expect failures on the missing `runner._recorder`**

- [ ] **Step 3: Implement in `runner.py`**

Module scope:

```python
from showdown_bot.battle.decision import SelectionStageSink
from showdown_bot.client.live_degradation import LiveDegradationRecorder

_recorder: LiveDegradationRecorder | None = None
```

In `handle_battle_message`, replace the chooser block:

```python
    book = _get_book(_active_format)
    book_absent = book is None
    state_build_failed = False
    ...
        try:
            state = BattleState.from_log_text("\n".join(_room_raw.get(room, [])))
            merge_request(req, state)
        except Exception as exc:  # noqa: BLE001 - never block a turn on state build
            logger.warning("state build failed in %s: %s", room, exc)
            state = None
            state_build_failed = True          # §5: attempted AND failed, not `state is None`

    stage_sink = SelectionStageSink() if _recorder is not None else None
    crash_type: str | None = None
    try:
        if book is not None:
            choose = choose_with_fallback(..., stage_sink=stage_sink)
        else:
            choose = choose_for_request(req)
    except Exception as exc:   # NOT BaseException: CancelledError/KeyboardInterrupt/
                               # SystemExit are not agent crashes (C5 scope)
        crash_type = type(exc).__name__
        if _recorder is not None:
            _recorder.record_decision(
                room_id=room, rqid=req.rqid, book_absent=book_absent,
                team_preview=bool(req.team_preview),
                state_build_failed=state_build_failed,
                selection_stage=getattr(stage_sink, "selection_stage", None),
                fallback_reason=getattr(stage_sink, "fallback_reason", None),
                agent_crash_type=crash_type)
        raise                                   # C5: unchanged exception, no new fallback

    if _recorder is not None:
        _recorder.record_decision(
            room_id=room, rqid=req.rqid, book_absent=book_absent,
            team_preview=bool(req.team_preview), state_build_failed=state_build_failed,
            selection_stage=getattr(stage_sink, "selection_stage", None),
            fallback_reason=getattr(stage_sink, "fallback_reason", None),
            agent_crash_type=None)

    await conn.send(f"{room}|{choose}")
```

In `_run_battle_loop`, add event recording at the two existing sites:

```python
            if parsed.prefix == "pm" and parsed.args and "Invalid choice" in parsed.args[-1]:
                if _recorder is not None:
                    only = next(iter(active_battles)) if len(active_battles) == 1 else None
                    _recorder.record_event(
                        event_type="invalid_choice_pm", payload=parsed.args[-1],
                        room_id=only, active_battle_count=len(active_battles))
                ...

                if parsed.prefix == "error":
                    if _recorder is not None:
                        _recorder.record_event(
                            event_type="server_error", payload=parsed.payload,
                            room_id=parsed.room, active_battle_count=len(active_battles))
                    await _send_default_choose(conn, parsed.room)
```

- [ ] **Step 4: Run, expect the two tests passing** · **Step 5: Commit**

---

## Task 9: Boundaries, `finally`, preflight call site (§9, §10.1)

**Files:** Modify `client/runner.py`; add to `tests/test_live_degradation_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_flush_happens_before_room_raw_is_popped(tmp_path):
    """§9: that pop is where today's evidence is thrown away."""
    ...  # drive |init|battle, one request, then |win|; assert battles.jsonl has the row
    #     AND runner._room_raw no longer holds the room


def test_stream_end_flushes_active_rooms_as_unterminated(tmp_path):
    ...  # end the message iterator with a room still active


def test_exception_exit_flushes_active_rooms_as_unterminated(tmp_path):
    ...  # raise inside the loop (the `not ladderable` popup path)


def test_cancellation_flushes_active_rooms_as_unterminated(tmp_path):
    ...  # cancel the task mid-loop; assert end_reason == "unterminated"


def test_preflight_failure_aborts_before_connect(tmp_path, monkeypatch):
    """§10.1: the one place a recording failure may stop the run."""
    ...  # assert _connect_and_login was never called
```

> Each ellipsis is filled with the stub-connection driver from Task 8; the assertions are
> stated above and are not optional.

- [ ] **Step 2: Run, expect all five failing**

- [ ] **Step 3: Implement**

`_run_battle_loop` gains a `finally` — a post-loop statement is skipped on exactly the exception
and cancellation paths where the evidence matters most:

```python
    try:
        async for raw in conn.messages():
            ...
                if parsed.prefix in ("win", "tie"):
                    if parsed.room in active_battles:
                        if _recorder is not None:
                            _recorder.flush_battle(
                                room_id=parsed.room, end_reason=parsed.prefix)
                            _recorder.battles_finished += 1
                        battles_finished += 1
                        active_battles.discard(parsed.room)
                        _room_raw.pop(parsed.room, None)     # flush is ABOVE this line
            ...
    finally:
        if _recorder is not None:
            _recorder.flush_unterminated(active_battles)
            _recorder.write_completion()
    return battles_finished
```

Each of `run_ladder_search`, `run_challenge`, `run_smoke_battle` calls preflight **before**
`_connect_and_login`:

```python
    global _recorder
    _recorder = LiveDegradationRecorder.preflight()   # raises PreflightError -> run aborts
    conn = await _connect_and_login(settings)
```

and returns a non-zero status when `_recorder.exit_status()` is non-zero.

- [ ] **Step 4: Run, expect 5 passed** · **Step 5: Commit**

---

## Task 10: Smoke proof, sample output, closeout

**Files:** add to `tests/test_live_degradation_runner.py`

- [ ] **Step 1: Write the failing test**

```python
def test_smoke_records_every_decision_not_applicable(tmp_path):
    """run_smoke_battle uses gen9randomdoublesbattle, where _get_book returns None,
    so `state is None` on every decision while NOTHING is degraded. A naive rule
    would report smoke as 100% degraded."""
    ...  # drive a smoke-shaped run with book_absent=True throughout
    rows = [json.loads(l) for l in (run_dir / "decisions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert rows and all(r["derivation_applicable"] is False for r in rows)
    assert all(r["is_degraded"] is None for r in rows)
    assert all(r["outcome"] == "not_applicable" for r in rows)
    battle = json.loads((run_dir / "battles.jsonl").read_text(
        encoding="utf-8").splitlines()[0])
    assert battle["degraded_decisions"] == 0
    assert battle["decisions_not_applicable"] == len(rows)
```

- [ ] **Step 2: Run, expect failure** · **Step 3: no new code should be needed — if this
      fails, the §5.1 gate is wrong, not the test** · **Step 4: Run, expect 1 passed**

- [ ] **Step 5: Capture a real sample**

Run a single real smoke battle and paste the produced `decisions.jsonl` first row,
`battles.jsonl` row and `completion.json` verbatim into the closeout report at
`docs/projects/champions/reports/2026-07-29-live-path-degradation-closeout.md`. A sample that
was hand-written rather than produced does not satisfy this step.

- [ ] **Step 6: Closeout gates**

```bash
git diff --check
```

```bash
python -m pytest showdown_bot -q
```

Expected: `git diff --check` silent; suite at or above the 3860 passed / 2 skipped / 1 xfailed
baseline from `main @ 43f08af`, with the new tests added and no new failures.

- [ ] **Step 7: Confirm the seven local artifacts are untouched**

```bash
git status --porcelain
```

Expected: only the intended files; `.claude/`, `docs/projects/evaluation/specs/2026-07-22-*`,
`reports/2026-07-16-*` (×2), `showdown_bot/uv.lock`,
`showdownbot_studio/docs/plans/2026-07-26-*` and `tools/_pkmn_differential_audit/` still listed
as untracked and unmodified.

---

## Coverage matrix — decision record §4–§10

| § | Requirement | Task |
|---|---|---|
| §4 | Raw facts, own seat only | 4, 5 |
| §4 | Context layer (`book_absent`, `team_preview`) | 1, 4 |
| §4 | Derivation gated | 4 |
| §4 | Aggregation, no cross-seat mixing | 6 (C7 test in 1) |
| §4 | Transport via `SelectionStageSink` | 8 |
| §4 | Persistence = `live-degradation-v1` | 1, 7 |
| §5 | `state_build_failed` ≠ `state is None` | 8 |
| §5.1 | Gate; `not_applicable` counts nothing | 4, 6, 10 |
| §6 | Crash recorded, re-raised unchanged | 8 |
| §7 | `\|error\|` room-scoped, not pre-classified | 5, 8 |
| §7 | PM unattributable; `inferred` only at count 1 | 5 |
| §8 | Closed schema, join keys, null rules | 1, 4, 5, 6 |
| §8 | Counters from their named sources | 6 |
| §8.1 | Exclusive dir, override, no overwrite | 3 |
| §8.1 | `NON_BEHAVIORAL` classification | 2 |
| §9 | Flush before `_room_raw.pop` | 9 |
| §9 | `finally` for stream end, exception, cancellation | 9 |
| §10.1 | Preflight fails closed before connect/search | 3, 9 |
| §10.2 | No turn-path write; no propagation; no bound claimed | 7 |
| §10.3 | Counter + log + best-effort completion + exit status | 7 |
| §10.4 | Residual limit documented, not fixed here | — (docs) |

## Coverage matrix — #125 acceptance criteria

| Criterion | Task |
|---|---|
| Raw facts recorded, always on, no enabling flag | 3, 9 |
| Flush before the room log is discarded; loop-exit flush | 9 |
| Write failure blocks nothing, counted, surfaces at completion | 7 |
| Non-zero exit; missing `completion.json` counts as failure | 7 |
| No `hero_`/`villain_` names | 1 |
| `state_build_failed` not raised for preview/missing book/smoke | 8, 10 |
| Derivation gated | 4, 10 |
| `is_degraded` persisted, `null` when gated; `degraded_decisions` | 4, 6 |
| Counters from named sources; `unattributed` increments nothing | 6 |
| `SHOWDOWN_LIVE_DEGRADATION_DIR` in `NON_BEHAVIORAL` | 2 |
| Integration tests: end-to-end, unterminated ×3, failed write, preflight, refused dir, smoke | 3, 7, 9, 10 |
| `pytest showdown_bot -q` passes | 10 |

---

## Non-claims

This slice records. It makes no strength claim, no production-readiness claim, no latency claim,
and changes no chosen action. `_abort_on_degradation` stays narrower than what is recorded —
that asymmetry is the decision record's explicit non-goal (C4), not a gap to close later.

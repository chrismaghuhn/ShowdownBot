# Phase 3 Slice 1b-B2: `learning/export.py` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `DatasetExporter` that takes finished `Row` objects, validates each, and
writes **byte-identical, stably-sorted** JSONL — with deterministic ID helpers and a
default-`"all"` sampling policy. No client wiring (that is 1b-B3).

**Architecture:** Pure `learning/export.py`: deterministic sha1 ID helpers
(`make_run_id`/`make_game_id`/`make_decision_id`), a `SamplingPolicy`, and a
`DatasetExporter(add / flush_sorted / rows_for_test)`. Mechanical + fully testable
with fake schema-valid Rows — no Node, no Trace/State, no client.

**Tech Stack:** Python stdlib (`hashlib`, `dataclasses`). Spec:
`docs/projects/learning/specs/2026-06-30-ml-reranker-1b-feature-extraction-export-design.md`.
Reuses `learning/schema.py` (`Row`, `validate_row`, `to_jsonl_line`). Run tests from
`showdown_bot/`.

---

## The 7 gates (acceptance criteria — each is a test below)
1. `DatasetExporter.add` takes finished `Row` objects (never Trace/State).
2. Every row is `schema.validate_row`-checked **before** it is buffered/written.
3. Deterministic IDs: `run_id`, `game_id`, `decision_id`, `candidate_index`.
4. Stable sort: rows ordered by `(game_id, decision_id, candidate_index)`.
5. Byte-identical JSONL: same rows + same seed/config/context ⇒ exact same bytes.
6. `SamplingPolicy` default = `"all"`.
7. No wall-clock, no UUIDs, no unseeded randomness anywhere.

## File Structure
- Create: `src/showdown_bot/learning/export.py`.
- Test: `tests/test_export.py`.

---

## Task 1: deterministic ID helpers

**Files:** Create `src/showdown_bot/learning/export.py`; Test `tests/test_export.py`.

- [ ] **Step 1: failing tests**

```python
# tests/test_export.py
from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id


def test_ids_are_deterministic():
    a = make_run_id("sha", False, "team", "cfg", 7)
    b = make_run_id("sha", False, "team", "cfg", 7)
    assert a == b and isinstance(a, str) and len(a) == 16

def test_ids_differ_on_any_input():
    base = make_run_id("sha", False, "team", "cfg", 7)
    assert base != make_run_id("sha2", False, "team", "cfg", 7)
    assert base != make_run_id("sha", True, "team", "cfg", 7)
    assert base != make_run_id("sha", False, "team", "cfg", 8)

def test_game_and_decision_ids_chain():
    run = make_run_id("sha", False, "team", "cfg", 7)
    g0, g1 = make_game_id(run, 0), make_game_id(run, 1)
    assert g0 != g1
    assert make_decision_id(g0, 0, 1, "p1") != make_decision_id(g0, 1, 1, "p1")
    assert make_decision_id(g0, 0, 1, "p1") == make_decision_id(g0, 0, 1, "p1")

def test_ids_avoid_delimiter_collision():
    # canonical JSON, not ":".join -> these must NOT collide
    assert make_run_id("a:b", False, "c", "cfg", 0) != make_run_id("a", False, "b:c", "cfg", 0)

def test_export_module_has_no_nondeterministic_imports():
    # gate 7: no wall-clock / uuid / unseeded randomness in the module
    import inspect
    import showdown_bot.learning.export as export
    src = inspect.getsource(export)
    assert "import uuid" not in src
    assert "import time" not in src
    assert "import random" not in src
    assert "datetime.now" not in src
```

- [ ] **Step 2: run → FAIL** (`ImportError`). `cd showdown_bot && python -m pytest tests/test_export.py -q`

- [ ] **Step 3: implement** the top of `export.py`:

```python
"""Deterministic JSONL export for the reranker dataset (Phase 3 slice 1b-B2).

Takes finished schema Rows -> validated, stably-sorted, byte-identical JSONL. No
Trace/State, no client wiring (that is 1b-B3). No wall-clock, no UUIDs, no unseeded
randomness — IDs are content/seed-derived sha1.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from showdown_bot.learning.schema import Row, validate_row, to_jsonl_line


def _sha16(*parts) -> str:
    # canonical JSON (not ":".join) so delimiters cannot collide:
    # ("a:b", "c") and ("a", "b:c") must hash differently.
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def make_run_id(git_sha, dirty_flag, team_hash, config_hash, run_seed) -> str:
    return _sha16(git_sha, dirty_flag, team_hash, config_hash, run_seed)


def make_game_id(run_id, game_index) -> str:
    return _sha16(run_id, game_index)


def make_decision_id(game_id, decision_local_index, turn_number, our_side) -> str:
    return _sha16(game_id, decision_local_index, turn_number, our_side)
```

- [ ] **Step 4: run → PASS** + full suite. `cd showdown_bot && python -m pytest tests/test_export.py -q` then `cd showdown_bot && python -m pytest -q` (was 306; +3).

- [ ] **Step 5: commit** `feat(learning): deterministic dataset ID helpers (sha1, no wall-clock/uuid)`

---

## Task 2: `SamplingPolicy` (default "all")

**Files:** Modify `export.py`; Test `tests/test_export.py`.

- [ ] **Step 1: failing tests**

```python
def test_sampling_policy_default_is_all():
    from showdown_bot.learning.export import SamplingPolicy
    p = SamplingPolicy()
    assert p.policy == "all"
    assert all(p.should_sample(i) for i in range(10))

def test_sampling_policy_every_nth():
    from showdown_bot.learning.export import SamplingPolicy
    p = SamplingPolicy(policy="every_nth", rate=3)
    assert [i for i in range(9) if p.should_sample(i)] == [0, 3, 6]

def test_sampling_policy_rejects_unknown():
    import pytest
    from showdown_bot.learning.export import SamplingPolicy
    with pytest.raises(ValueError, match="unknown sampling"):
        SamplingPolicy(policy="bogus").should_sample(0)

def test_sampling_policy_rejects_nonpositive_rate():
    import pytest
    from showdown_bot.learning.export import SamplingPolicy
    with pytest.raises(ValueError, match="rate"):
        SamplingPolicy(policy="every_nth", rate=0).should_sample(0)
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement** (append to `export.py`):

```python
@dataclass
class SamplingPolicy:
    policy: str = "all"      # "all" | "every_nth"
    rate: int = 1            # used by every_nth
    seed: int = 0            # reserved for future seeded sampling; deterministic

    def should_sample(self, decision_index: int) -> bool:
        if self.policy == "all":
            return True
        if self.policy == "every_nth":
            if self.rate <= 0:                       # fail-fast, never silently normalize
                raise ValueError("every_nth sampling rate must be > 0")
            return decision_index % self.rate == 0
        raise ValueError(f"unknown sampling policy: {self.policy}")
```

- [ ] **Step 4: run → PASS** + full suite (+3).
- [ ] **Step 5: commit** `feat(learning): SamplingPolicy (default all, every_nth; deterministic)`

---

## Task 3: `DatasetExporter` (validate-on-add, stable sort, byte-identical JSONL)

**Files:** Modify `export.py`; Test `tests/test_export.py`.

- [ ] **Step 1: failing tests**

```python
import io, pytest
from showdown_bot.learning.schema import Row, FEATURE_COLUMNS, METADATA_KEYS, LABEL_KEYS
from showdown_bot.learning.export import DatasetExporter


def _row(game_id, decision_id, cand_idx):
    features = {c: 0 for c in FEATURE_COLUMNS}
    metadata = {k: "x" for k in METADATA_KEYS}
    metadata.update(game_id=game_id, decision_id=decision_id, candidate_index=cand_idx)
    label = {k: 0 for k in LABEL_KEYS}
    return Row(features=features, metadata=metadata, label=label)


def test_add_validates_each_row():
    exp = DatasetExporter()
    bad = _row("g", "d", 0)
    bad.features["not_a_real_feature"] = 1   # breaks schema
    with pytest.raises(ValueError):
        exp.add(bad)
    assert exp.rows_for_test() == []         # invalid rows are never buffered

def test_flush_is_stable_sorted_and_byte_identical():
    rows = [_row("g1", "d2", 1), _row("g1", "d1", 0), _row("g1", "d1", 1), _row("g2", "d1", 0)]
    a, b = DatasetExporter(), DatasetExporter()
    for r in rows:                 # add in one order
        a.add(r)
    for r in reversed(rows):       # add in the REVERSE order
        b.add(r)
    out_a, out_b = io.StringIO(), io.StringIO()
    a.flush_sorted(out_a); b.flush_sorted(out_b)
    assert out_a.getvalue() == out_b.getvalue()        # byte-identical regardless of add order
    # ordered by (game_id, decision_id, candidate_index)
    order = [(r.metadata["game_id"], r.metadata["decision_id"], r.metadata["candidate_index"])
             for r in a.rows_for_test()]
    assert order == sorted(order, key=lambda t: (t[0], t[1], int(t[2])))

def test_flush_writes_one_jsonl_line_per_row():
    exp = DatasetExporter()
    for i in range(3):
        exp.add(_row("g", "d", i))
    buf = io.StringIO(); exp.flush_sorted(buf)
    lines = buf.getvalue().splitlines()
    assert len(lines) == 3
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement** (append to `export.py`):

```python
class DatasetExporter:
    """Buffers finished, validated Rows; writes stably-sorted byte-identical JSONL.
    Takes Row objects only — never Trace/State. Sampling is applied upstream (1b-B3);
    this holds a SamplingPolicy for that caller to consult."""

    def __init__(self, sampling_policy: SamplingPolicy | None = None) -> None:
        self.sampling_policy = sampling_policy or SamplingPolicy()
        self._rows: list[Row] = []

    def add(self, row: Row) -> None:
        validate_row(row)        # gate 2: never buffer an invalid row
        self._rows.append(row)

    def _sorted(self) -> list[Row]:
        return sorted(
            self._rows,
            key=lambda r: (
                str(r.metadata.get("game_id", "")),
                str(r.metadata.get("decision_id", "")),
                int(r.metadata.get("candidate_index", 0)),
            ),
        )

    def rows_for_test(self) -> list[Row]:
        return self._sorted()

    def to_jsonl(self) -> str:
        return "".join(to_jsonl_line(r) + "\n" for r in self._sorted())

    def flush_sorted(self, file_or_path) -> None:
        text = self.to_jsonl()
        if hasattr(file_or_path, "write"):
            file_or_path.write(text)
        else:
            # newline="\n" => byte-identical across OSes (no CRLF translation)
            with open(file_or_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
```

- [ ] **Step 4: run → PASS** + full suite (+3). `cd showdown_bot && python -m pytest tests/test_export.py -q` then `cd showdown_bot && python -m pytest -q`.
- [ ] **Step 5: commit** `feat(learning): DatasetExporter (validate-on-add, stable sort, byte-identical JSONL)`

---

## Self-Review notes
- **7 gates mapped:** add-takes-Row (T3 `_row`), validate-on-add (T3), deterministic IDs (T1), stable sort (T3), byte-identical (T3 reverse-order), default `"all"` (T2), no wall-clock/uuid/random (T1: pure sha1; nothing imports `uuid`/`time`/`random`).
- **`flush_sorted` accepts a file-like OR a path**; `newline="\n"` keeps bytes identical across OSes. `to_jsonl_line` already uses `sort_keys=True`.
- **Deferred to 1b-B3:** the optional `client/` hook (`exporter=None` bit-identical), wiring `SamplingPolicy.should_sample` per decision, minting the IDs from a real `FeatureContext`, and the hermetic trace→rows→JSONL E2E.

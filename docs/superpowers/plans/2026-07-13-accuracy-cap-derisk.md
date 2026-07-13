# Accuracy Branch-Cap / Ambiguous-Candidate De-Risk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure `SHOWDOWN_ACCURACY_BRANCH_CAP ∈ {6, 8}` against the frozen cap=4 gate result on
the same 85-battle/944-decision corpus (cap-hit rate, decision diffs, latency), and diagnose the 63
ambiguous-candidate decisions Task 10 of the accuracy-offline-gate plan correctly excluded — pure
measurement/diagnosis, no production code change, no default flip, no strength claim.

**Architecture:** One new eval module (`accuracy_cap_derisk.py`) holds pure, unit-tested logic
(`decision_id`, `compare_action_tables`, the candidate-resolution row-builder, the two-tier
ambiguous-case classifier). A chain of small driver scripts under `showdown_bot/scripts/` reuses
this module plus the ALREADY-UNCHANGED `room_raw_replay.py`/`accuracy_gate_b.py`/
`accuracy_gate_stats.py` to produce real artifacts under `data/eval/accuracy-cap-derisk/`, strictly
read-only against `data/eval/accuracy-gate/`. The cap=4 auxiliary run is validation-gated (two
stages: raw reproduction, then semantic diff) before any cap=6/8 comparison may use it.

**Tech Stack:** Python 3.14, pytest, existing `showdown_bot` package (`room_raw_replay`,
`accuracy_gate_b`, `accuracy_gate_stats`, `accuracy_baseline`, `decision_capture`, `decision_diff`).

**Spec:** `docs/superpowers/specs/2026-07-13-accuracy-cap-derisk-design.md` (§ references below are
to this document).

---

## Real API facts this plan is built on (verified against the actual current code this session, not assumed)

- `ExtractedDecision` (`eval/room_raw_replay.py`): `state, request, kind, side, turn, request_hash,
  log_prefix_hash, _debug_prefix_line_count`. No `seed_base`/`seed_index`/`rqid` field directly —
  `rqid` is available via `decision.request.rqid` (`BattleRequest.rqid: int = 0`); `seed_base`/
  `seed_index` live on `SeedIdentity`, associated with the KEPT FILE a decision came from, via
  `DedupReport.kept_identities: dict[Path, SeedIdentity]` — **confirmed via
  `data/eval/accuracy-gate/dedup-report.json`: all 85 kept files have an entry (no
  content-hash-fallback-kept file lacks a `SeedIdentity` in this corpus)**, so every decision can be
  paired with its file's `SeedIdentity` at extraction time.
- `extract_decisions_from_log(path: str | Path) -> list[ExtractedDecision]` — per-file, so pairing
  each returned decision with `dedup_report.kept_identities[path]` is natural at the call site
  (same pattern `run_accuracy_gate_b.py`'s `battle_id_for` closure already uses for battle IDs).
- `deduplicate_battle_logs(*, log_files, manifest_files, keep_priority) -> DedupReport` — exact glob
  dirs/manifest files/keep_priority reused verbatim from `run_accuracy_gate_b.py` (Task 11 of the
  accuracy-offline-gate plan), reproduced in Task 4 below.
- `accuracy_baseline.py`'s `BaselineRow`: `request_hash, log_prefix_hash, side, turn, chosen_action,
  score, accuracy_mode, source_commit, config_hash, python_version, dependency_lock_hash` —
  `pre-refactor-baseline.jsonl`'s exact real schema, confirmed by reading the file. `canonical_float
  (value, ndigits=10) -> str` already exists and is reused, not reimplemented.
- **Verified: the frozen baseline's `score` is NOT provably equivalent to this plan's
  `chosen_candidate_score`.** `scripts/run_accuracy_baseline_freeze.py`'s original `_chooser`
  resolves the chosen candidate via `exact = [c for c in trace.candidates if c.candidate_id ==
  chosen]` then `exact[0].aggregate_score` (or a tera-suffix-fallback equivalent) — **first match,
  with no `len(exact) > 1` ambiguity check** (Task 10's `_chosen_candidate` ambiguity guard came
  later and was never applied to this driver). This means `legacy_frozen_score` could be silently
  wrong on any off-path label collision — per spec §2.3, off-vs-cap score comparisons are **skipped**
  in this plan (Task 8), not attempted, given this verified lack of an ambiguity guarantee.
- `JointAction` (`battle/actions.py`) is `@dataclass(frozen=True)` with default (all-field) equality
  over `slot0, slot1: SlotAction`. `SlotAction` (`models/actions.py`): `kind, move_index, target,
  terastallize, target_ident`. **Verified: object/dataclass equality DOES discriminate different
  switch targets** (via `target_ident`, a real field `_label_ja` drops when rendering non-move
  slots as the bare string `sa.kind`) — this is the structural fix for `label_collision/
  switch_target_omitted`. **Verified: object equality does NOT automatically solve the Tera-overlay
  case** — `terastallize` is also a real `SlotAction` field, and `_maybe_tera`'s post-hoc overlay
  changes exactly that field on `best_ja` relative to the pre-overlay candidate stored in
  `trace.candidates`, so a naive `best_ja == c.joint_action` check would still fail after a Tera
  overlay and need the same kind of Tera-aware comparison `_strip_tera_suffix` already does for
  strings. This is real, load-bearing evidence for Task 11's fix-feasibility write-up — verify it
  again directly against the code before writing it up, don't just trust this summary.
- `CandidateTrace.joint_action: JointAction` already stores the real object per candidate (set at
  `decision.py:687`, `cands.append(CandidateTrace(candidate_id=_label_ja(req, ja), joint_action=ja,
  ...))`). `DecisionTrace.chosen_candidate_id: str | None` is the ONLY chosen-candidate pointer at
  the trace level — there is **no** `chosen_joint_action` field exposing `best_ja` itself. This is
  the concrete structural gap Task 11's fix-feasibility investigation (§3.2, spec) must report on.
- `TOP_K_TRACE_CANDIDATES = 6` (`decision.py:34`).
- `normalize_choose(choose: str, request: BattleRequest) -> dict` (`eval/decision_capture.py:141`),
  `classify_action_diff(baseline: dict, candidate: dict, *, baseline_stage=None,
  candidate_stage=None) -> ActionDiff` (`ActionDiff(primary: str, markers: tuple[str, ...])`,
  `eval/decision_diff.py:79-98`) — reused as-is.
- `gate-b-report.json`'s real schema (`data/eval/accuracy-gate/gate-b-report.json`):
  `acceptance.exceptions` is a list of `{"request_hash": ..., "exception": "ExceptionType:
  message"}` objects (63 entries — the historical ambiguous-candidate exclusions), `diffs` is the 20
  cap4-vs-off decision-diff rows, `dedup.unique_battles_final_g == 85`.
- Real corpus-extraction pattern (glob dirs, manifest files, keep_priority, calc/oracle
  construction, `PYTHONPATH`-shadowing, `SHOWDOWN_CALC_BACKEND=persistent`) copied verbatim from
  `showdown_bot/scripts/run_accuracy_gate_b.py` (Task 11 of the accuracy-offline-gate plan) —
  reproduced exactly in Task 4 below, reused by every later real-run task.

## CRITICAL environment gotcha (every task, every script)

The machine has an editable pip install of `showdown-bot` pointing at the MAIN repo checkout, not
this worktree. Every Python/pytest invocation MUST either run with `PYTHONPATH="$(pwd)/src"` set
(from `showdown_bot/`), or — for scripts meant to be run directly, matching `run_accuracy_gate_b.py`'s
own convention — insert `sys.path` at the top of the script itself. Verify with
`PYTHONPATH="$(pwd)/src" python -c "import showdown_bot; print(showdown_bot.__file__)"` before
trusting any test/script result — it must resolve under this worktree
(`.claude/worktrees/accuracy-cap-derisk/...`).

---

## Task 1: `decision_id` — composite key computation + uniqueness assertion

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py`
- Create: `showdown_bot/tests/eval/test_accuracy_cap_derisk.py`

Implements spec §2.2.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from __future__ import annotations

import pytest

from showdown_bot.eval.accuracy_cap_derisk import (
    DecisionIdComponents,
    DuplicateDecisionIdError,
    assert_decision_ids_unique,
    compute_decision_id,
)


def test_compute_decision_id_is_deterministic():
    c = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    assert compute_decision_id(c) == compute_decision_id(c)


def test_compute_decision_id_changes_with_any_field():
    base = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    variants = [
        DecisionIdComponents(seed_base="XXX", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=99, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="XXX", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="XXX", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p2", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=99, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=99),
    ]
    base_id = compute_decision_id(base)
    for v in variants:
        assert compute_decision_id(v) != base_id


def test_compute_decision_id_is_a_hex_sha256():
    c = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    did = compute_decision_id(c)
    assert len(did) == 64
    int(did, 16)  # raises if not valid hex


def test_assert_decision_ids_unique_passes_on_unique_ids():
    assert_decision_ids_unique(["a", "b", "c"])  # no raise


def test_assert_decision_ids_unique_raises_on_duplicate():
    with pytest.raises(DuplicateDecisionIdError) as exc_info:
        assert_decision_ids_unique(["a", "b", "a", "c", "b"])
    msg = str(exc_info.value)
    assert "a" in msg and "b" in msg  # both duplicated ids named, not just a count
```

- [ ] **Step 2: Run tests to verify they fail**

Run (with PYTHONPATH prefix, from `showdown_bot/`): `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'showdown_bot.eval.accuracy_cap_derisk'`

- [ ] **Step 3: Implement `accuracy_cap_derisk.py` (decision_id part)**

```python
# showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py
"""Accuracy branch-cap / ambiguous-candidate de-risk study (spec:
docs/superpowers/specs/2026-07-13-accuracy-cap-derisk-design.md). Pure, unit-tested logic only --
real corpus runs live in showdown_bot/scripts/. The cap=4 gate verdict
(data/eval/accuracy-gate/gate-b-report.json) is never recomputed here; this module only supports
the auxiliary action-capture / cross-cap comparison / ambiguous-candidate diagnostic described in
the spec.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionIdComponents:
    seed_base: str
    seed_index: int
    request_hash: str
    log_prefix_hash: str
    side: str
    rqid: int
    turn: int


def compute_decision_id(c: DecisionIdComponents) -> str:
    """Spec Sec.2.2's fixed schema: sha256(canonical_json([seed_base, seed_index, request_hash,
    log_prefix_hash, side, rqid, turn])). Canonical JSON here means: a fixed-order list (not a
    dict, so key-ordering ambiguity can't exist), compact separators, ensure_ascii -- deterministic
    across processes/machines by construction, not by convention."""
    payload = [
        c.seed_base, c.seed_index, c.request_hash, c.log_prefix_hash, c.side, c.rqid, c.turn,
    ]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DuplicateDecisionIdError(Exception):
    pass


def assert_decision_ids_unique(decision_ids: list[str]) -> None:
    """Fail-closed uniqueness check, spec Sec.2.2 -- raise (not warn, not dedupe) the instant a
    collision is found, naming every duplicated id so the caller can investigate immediately."""
    counts = Counter(decision_ids)
    dupes = {did: n for did, n in counts.items() if n > 1}
    if dupes:
        raise DuplicateDecisionIdError(
            f"{len(dupes)} decision_id collision(s) out of {len(decision_ids)} total: {dupes}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py showdown_bot/tests/eval/test_accuracy_cap_derisk.py
git commit -m "feat(eval): decision_id composite key + fail-closed uniqueness assertion"
```

---

## Task 2: `compare_action_tables` — the study's own comparator, not `diff_against_baseline`

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py`
- Modify: `showdown_bot/tests/eval/test_accuracy_cap_derisk.py`

Implements spec §2.4. `accuracy_baseline_diff.py` stays completely untouched (verify with
`git diff` after this task — it must show zero changes to that file).

- [ ] **Step 1: Write the failing tests**

```python
# appended to showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from showdown_bot.eval.accuracy_cap_derisk import (
    ActionTableRow,
    DecisionIdPairingError,
    compare_action_tables,
)


def _row(decision_id, action, *, top_rank_score=1.0, chosen_candidate_score=1.0,
         candidate_resolution_status="exact"):
    return ActionTableRow(
        decision_id=decision_id, chosen_action=action,
        candidate_resolution_status=candidate_resolution_status,
        chosen_candidate_rank=0, chosen_rank_mismatch=False,
        top_rank_score=top_rank_score, chosen_candidate_score=chosen_candidate_score,
    )


def test_compare_action_tables_pairs_by_decision_id_not_position():
    ref = [_row("id2", "/choose move 1"), _row("id1", "/choose move 2")]
    cand = [_row("id1", "/choose move 2"), _row("id2", "/choose move 1")]
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert result.direction == "cap4 -> cap6"
    assert len(result.rows) == 2
    assert all(not r.action_changed for r in result.rows)


def test_compare_action_tables_detects_action_change_via_normalize_choose():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 2")]
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6", request=None)
    assert result.rows[0].action_changed is True


def test_compare_action_tables_does_not_count_pure_score_change_as_action_diff():
    ref = [_row("id1", "/choose move 1", top_rank_score=5.0)]
    cand = [_row("id1", "/choose move 1", top_rank_score=7.0)]  # same action, different score
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    row = result.rows[0]
    assert row.action_changed is False
    assert row.top_rank_score_delta == pytest.approx(2.0)
    assert row.top_rank_score_changed is True  # score change tracked, but NOT an action diff


def test_compare_action_tables_fails_closed_on_missing_id_in_candidate():
    ref = [_row("id1", "/choose move 1"), _row("id2", "/choose move 2")]
    cand = [_row("id1", "/choose move 1")]  # id2 missing
    with pytest.raises(DecisionIdPairingError) as exc_info:
        compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert "id2" in str(exc_info.value)


def test_compare_action_tables_fails_closed_on_extra_id_in_candidate():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 1"), _row("id_extra", "/choose move 2")]
    with pytest.raises(DecisionIdPairingError) as exc_info:
        compare_action_tables(ref, cand, direction="cap4 -> cap6")
    assert "id_extra" in str(exc_info.value)


def test_compare_action_tables_fails_closed_on_duplicate_id_within_one_table():
    ref = [_row("id1", "/choose move 1"), _row("id1", "/choose move 2")]
    cand = [_row("id1", "/choose move 1")]
    with pytest.raises(DecisionIdPairingError):
        compare_action_tables(ref, cand, direction="cap4 -> cap6")


def test_compare_action_tables_uses_correctly_named_reference_candidate_fields_not_baseline_replay():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 2")]
    result = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    row = result.rows[0]
    assert row.reference_action == "/choose move 1"
    assert row.candidate_action == "/choose move 2"
    assert not hasattr(row, "baseline_action")
    assert not hasattr(row, "replay_action")


def test_compare_action_tables_direction_is_not_inferred_from_argument_order():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 2")]
    r1 = compare_action_tables(ref, cand, direction="cap4 -> cap6")
    r2 = compare_action_tables(cand, ref, direction="cap6 -> cap4")  # swapped args, swapped label
    assert r1.direction == "cap4 -> cap6"
    assert r2.direction == "cap6 -> cap4"
    # swapping which table is "reference" flips reference/candidate labeling on the SAME
    # underlying decision, proving the function has no baked-in "first arg is always off" bias
    assert r1.rows[0].reference_action == r2.rows[0].candidate_action
    assert r1.rows[0].candidate_action == r2.rows[0].reference_action


def test_compare_action_tables_refuses_incompatible_score_semantics():
    ref = [_row("id1", "/choose move 1")]
    cand = [_row("id1", "/choose move 1")]
    result = compare_action_tables(
        ref, cand, direction="off -> cap6", score_comparable=False,
        score_incompatible_reason="legacy_frozen_score not proven equivalent to top_rank_score",
    )
    row = result.rows[0]
    assert row.score_comparable is False
    assert row.top_rank_score_delta is None  # never silently computed
    assert "not proven equivalent" in row.score_incompatible_reason
```

`normalize_choose` requires a real `BattleRequest` in general, but for these unit tests the actions
are already in canonical `/choose move N` form and don't exercise team-preview/default-string
special cases, so `request=None` with a pass-through canonicalization is acceptable for this
module's own tests (the real driver scripts, Task 5/8, always pass a real request). Confirm
`normalize_choose`'s actual behavior on `request=None` before relying on this — if it raises, adapt
`compare_action_tables` to accept a `canonicalize: Callable[[str], str]` injection point instead of
calling `normalize_choose` directly, defaulting to the real `normalize_choose` in production call
sites (Task 5/8) and a trivial identity/strip function in these unit tests. Verify against the real
current `normalize_choose` source before deciding which approach to take.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v -k compare_action_tables`
Expected: FAIL with `ImportError: cannot import name 'ActionTableRow'`

- [ ] **Step 3: Implement `compare_action_tables`**

```python
# appended to showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py

from dataclasses import field


@dataclass(frozen=True)
class ActionTableRow:
    """One row of a per-decision action-capture table (spec Sec.2.3's row schema). Resolution
    status, rank, and score are intentionally orthogonal fields, not one collapsed enum -- a
    candidate can resolve only via Tera-suffix stripping AND independently sit at a non-zero rank;
    collapsing these into a single status would force losing one fact to keep the other."""
    decision_id: str
    chosen_action: str  # raw string from heuristic_choose_for_request, never mutated here
    candidate_resolution_status: str  # exact | tera_stripped | ambiguous_label | chosen_missing | other_resolution_error
    chosen_candidate_rank: int | None
    chosen_rank_mismatch: bool | None  # True when chosen_candidate_rank not in (0, None)
    top_rank_score: float | None  # nullable: an empty/rank-corrupt trace must not drop the row
    chosen_candidate_score: float | None  # nullable: only when candidate_resolution_status resolved one


@dataclass(frozen=True)
class ActionDiffRow:
    decision_id: str
    reference_action: str
    candidate_action: str
    action_changed: bool
    top_rank_score_delta: float | None
    top_rank_score_changed: bool | None
    chosen_candidate_score_delta: float | None
    chosen_candidate_score_changed: bool | None
    score_comparable: bool
    score_incompatible_reason: str | None


@dataclass(frozen=True)
class ActionTableDiff:
    direction: str  # e.g. "cap4 -> cap6", "off -> cap8" -- explicit, never inferred from arg order
    rows: list[ActionDiffRow]

    @property
    def action_changed_count(self) -> int:
        return sum(1 for r in self.rows if r.action_changed)


class DecisionIdPairingError(Exception):
    pass


def _canonical_action(action: str, request) -> str:
    if request is None:
        return action.strip()
    from showdown_bot.eval.decision_capture import normalize_choose
    return json.dumps(normalize_choose(action, request), sort_keys=True)


def compare_action_tables(
    reference_rows: list[ActionTableRow],
    candidate_rows: list[ActionTableRow],
    *,
    direction: str,
    request=None,
    score_comparable: bool = True,
    score_incompatible_reason: str | None = None,
) -> ActionTableDiff:
    """Spec Sec.2.4's comparator -- decision_id-paired, fail-closed, action_changed computed only
    from normalize_choose-canonicalized chosen_action (never influenced by score), score changes
    reported separately and only when score_comparable=True (spec Sec.2.3's score-semantics rule --
    the caller decides comparability, this function enforces it rather than silently subtracting
    incompatible values). `direction` is a required, explicit label -- never inferred from which
    table is passed first."""
    ref_by_id: dict[str, ActionTableRow] = {}
    for r in reference_rows:
        if r.decision_id in ref_by_id:
            raise DecisionIdPairingError(f"duplicate decision_id in reference_rows: {r.decision_id!r}")
        ref_by_id[r.decision_id] = r
    cand_by_id: dict[str, ActionTableRow] = {}
    for r in candidate_rows:
        if r.decision_id in cand_by_id:
            raise DecisionIdPairingError(f"duplicate decision_id in candidate_rows: {r.decision_id!r}")
        cand_by_id[r.decision_id] = r

    missing_from_candidate = set(ref_by_id) - set(cand_by_id)
    extra_in_candidate = set(cand_by_id) - set(ref_by_id)
    if missing_from_candidate or extra_in_candidate:
        raise DecisionIdPairingError(
            f"decision_id mismatch for direction={direction!r}: "
            f"missing_from_candidate={sorted(missing_from_candidate)} "
            f"extra_in_candidate={sorted(extra_in_candidate)}"
        )

    rows: list[ActionDiffRow] = []
    for decision_id, ref in sorted(ref_by_id.items()):
        cand = cand_by_id[decision_id]
        action_changed = (
            _canonical_action(ref.chosen_action, request)
            != _canonical_action(cand.chosen_action, request)
        )

        def _delta(a: float | None, b: float | None):
            if not score_comparable or a is None or b is None:
                return None, None
            d = b - a
            return d, (d != 0.0)

        top_delta, top_changed = _delta(ref.top_rank_score, cand.top_rank_score)
        cc_delta, cc_changed = _delta(ref.chosen_candidate_score, cand.chosen_candidate_score)

        rows.append(ActionDiffRow(
            decision_id=decision_id,
            reference_action=ref.chosen_action, candidate_action=cand.chosen_action,
            action_changed=action_changed,
            top_rank_score_delta=top_delta, top_rank_score_changed=top_changed,
            chosen_candidate_score_delta=cc_delta, chosen_candidate_score_changed=cc_changed,
            score_comparable=score_comparable,
            score_incompatible_reason=None if score_comparable else score_incompatible_reason,
        ))

    return ActionTableDiff(direction=direction, rows=rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v`
Expected: PASS (13 passed — 5 from Task 1 + 8 from this task)

- [ ] **Step 5: Confirm `accuracy_baseline_diff.py` is untouched**

Run: `git diff --stat -- showdown_bot/src/showdown_bot/eval/accuracy_baseline_diff.py`
Expected: empty output (zero changes)

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py showdown_bot/tests/eval/test_accuracy_cap_derisk.py
git commit -m "feat(eval): compare_action_tables comparator, decision_id-paired, score-semantic-guarded"
```

---

## Task 3: Candidate-resolution row builder (the honest score-resolution split)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py`
- Modify: `showdown_bot/tests/eval/test_accuracy_cap_derisk.py`

Implements spec §2.3's row-schema construction from a real `DecisionTrace`. This is the function
Task 5's real driver calls per decision to build an `ActionTableRow`.

Before writing this: read `showdown_bot/src/showdown_bot/eval/accuracy_gate_b.py`'s
`_chosen_candidate`/`_strip_tera_suffix` in full — this function follows the SAME exact/tera-fallback
resolution logic, but must NEVER raise (unlike `_chosen_candidate`) — on ambiguity or a missing
match, it returns a status-flagged row instead, since the whole point of this table is to still have
a `chosen_action` row for every decision, including the 63 that `run_gate_b` excludes via exception.

- [ ] **Step 1: Write the failing tests**

```python
# appended to showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.eval.accuracy_cap_derisk import build_action_table_row


def _candidate(candidate_id, rank, score):
    return CandidateTrace(
        candidate_id=candidate_id, joint_action=None, rank=rank, aggregate_score=score,
        score_vector=[score], outcome_breakdowns=[], aggregate_breakdown=None,
    )


def test_build_action_table_row_exact_match_rank_zero():
    trace = DecisionTrace(chosen_candidate_id="A", candidates=[
        _candidate("A", 0, 5.0), _candidate("B", 1, 3.0),
    ])
    row = build_action_table_row("d1", "/choose move 1", trace)
    assert row.candidate_resolution_status == "exact"
    assert row.chosen_candidate_rank == 0
    assert row.chosen_rank_mismatch is False
    assert row.top_rank_score == 5.0
    assert row.chosen_candidate_score == 5.0


def test_build_action_table_row_tera_stripped_and_rank_mismatch_simultaneously():
    """Both facts survive independently -- neither status collapses the other (spec Sec.2.3)."""
    trace = DecisionTrace(chosen_candidate_id="(protect, moonblast->1 tera)", candidates=[
        _candidate("(protect, shadowball->1)", 0, 6.0),
        _candidate("(protect, moonblast->1)", 1, 5.0),  # the real chosen line, at rank 1
    ])
    row = build_action_table_row("d1", "/choose move 1, move 2", trace)
    assert row.candidate_resolution_status == "tera_stripped"
    assert row.chosen_candidate_rank == 1
    assert row.chosen_rank_mismatch is True  # BOTH tera_stripped and rank_mismatch present
    assert row.top_rank_score == 6.0  # rank-0's score, independent of which one is chosen
    assert row.chosen_candidate_score == 5.0


def test_build_action_table_row_ambiguous_label_has_null_chosen_candidate_score():
    trace = DecisionTrace(chosen_candidate_id="(switch, pass)", candidates=[
        _candidate("(switch, pass)", 0, 4.0), _candidate("(switch, pass)", 1, 2.0),
    ])
    row = build_action_table_row("d1", "/choose switch 2, pass", trace)
    assert row.candidate_resolution_status == "ambiguous_label"
    assert row.chosen_candidate_rank is None
    assert row.chosen_rank_mismatch is None
    assert row.chosen_candidate_score is None
    assert row.top_rank_score == 4.0  # top_rank_score still populated -- independent of resolution


def test_build_action_table_row_chosen_missing():
    trace = DecisionTrace(chosen_candidate_id="(nothing matches)", candidates=[
        _candidate("A", 0, 5.0),
    ])
    row = build_action_table_row("d1", "/choose move 3", trace)
    assert row.candidate_resolution_status == "chosen_missing"
    assert row.chosen_candidate_score is None
    assert row.top_rank_score == 5.0


def test_build_action_table_row_empty_trace_keeps_the_action_row():
    """An empty/rank-corrupt trace must not make the whole decision (and its chosen_action)
    disappear -- only the score fields go null, with the status visibly reflecting why."""
    trace = DecisionTrace(chosen_candidate_id=None, candidates=[])
    row = build_action_table_row("d1", "/choose move 1", trace)
    assert row.chosen_action == "/choose move 1"  # action always present
    assert row.top_rank_score is None
    assert row.chosen_candidate_score is None
    assert row.chosen_candidate_rank is None
    assert row.candidate_resolution_status in ("chosen_missing", "other_resolution_error")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v -k build_action_table_row`
Expected: FAIL with `ImportError: cannot import name 'build_action_table_row'`

- [ ] **Step 3: Implement `build_action_table_row`**

```python
# appended to showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py


def _strip_tera(candidate_id: str) -> str:
    # Mirrors accuracy_gate_b.py's _strip_tera_suffix exactly -- Tera is never itself a dimension
    # of the enumerated candidate space, so stripping " tera" is a safe, non-lossy normalization.
    return candidate_id.replace(" tera", "")


def build_action_table_row(decision_id: str, chosen_action: str, trace) -> ActionTableRow:
    """Spec Sec.2.3: resolve the structurally-chosen candidate the SAME way
    accuracy_gate_b.py::_chosen_candidate does (exact match, then tera-suffix-stripped fallback),
    but NEVER raise -- report a status instead, since this table must still carry a row (with its
    real chosen_action) for decisions where trace-based resolution fails, unlike run_gate_b's own
    exception path."""
    candidates = list(trace.candidates)
    top = next((c for c in candidates if c.rank == 0), None)
    top_rank_score = top.aggregate_score if top is not None else None

    chosen_id = trace.chosen_candidate_id
    if chosen_id is None:
        return ActionTableRow(
            decision_id=decision_id, chosen_action=chosen_action,
            candidate_resolution_status="chosen_missing",
            chosen_candidate_rank=None, chosen_rank_mismatch=None,
            top_rank_score=top_rank_score, chosen_candidate_score=None,
        )

    exact = [c for c in candidates if c.candidate_id == chosen_id]
    if len(exact) == 1:
        resolved, status = exact[0], "exact"
    elif len(exact) > 1:
        return ActionTableRow(
            decision_id=decision_id, chosen_action=chosen_action,
            candidate_resolution_status="ambiguous_label",
            chosen_candidate_rank=None, chosen_rank_mismatch=None,
            top_rank_score=top_rank_score, chosen_candidate_score=None,
        )
    else:
        stripped_target = _strip_tera(chosen_id)
        fallback = [c for c in candidates if _strip_tera(c.candidate_id) == stripped_target]
        if len(fallback) == 1:
            resolved, status = fallback[0], "tera_stripped"
        elif len(fallback) > 1:
            return ActionTableRow(
                decision_id=decision_id, chosen_action=chosen_action,
                candidate_resolution_status="ambiguous_label",
                chosen_candidate_rank=None, chosen_rank_mismatch=None,
                top_rank_score=top_rank_score, chosen_candidate_score=None,
            )
        else:
            return ActionTableRow(
                decision_id=decision_id, chosen_action=chosen_action,
                candidate_resolution_status="chosen_missing",
                chosen_candidate_rank=None, chosen_rank_mismatch=None,
                top_rank_score=top_rank_score, chosen_candidate_score=None,
            )

    return ActionTableRow(
        decision_id=decision_id, chosen_action=chosen_action,
        candidate_resolution_status=status,
        chosen_candidate_rank=resolved.rank, chosen_rank_mismatch=(resolved.rank != 0),
        top_rank_score=top_rank_score, chosen_candidate_score=resolved.aggregate_score,
    )
```

Note: the `test_build_action_table_row_empty_trace_keeps_the_action_row` fixture has
`chosen_candidate_id=None` — check the real `DecisionTrace` dataclass default for
`chosen_candidate_id` before assuming `None` is a valid/reachable value in practice (it's declared
`str | None = None`, so this is a legitimate default-constructed-trace edge case, not a fabricated
one) — the implementation above already handles it by treating `None` as `chosen_missing`, matching
the test's `in ("chosen_missing", "other_resolution_error")` assertion.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v`
Expected: PASS (18 passed)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py showdown_bot/tests/eval/test_accuracy_cap_derisk.py
git commit -m "feat(eval): build_action_table_row -- orthogonal resolution/rank/score, never raises"
```

---

## Task 4: `decision-id-manifest.jsonl` — real 944-decision extraction + frozen-baseline enrichment

**Files:**
- Create: `showdown_bot/scripts/build_decision_id_manifest.py`

Implements spec §2.2's real run: extracts all 944 decisions with per-file `SeedIdentity`, computes
`decision_id` for each, asserts 944 unique, then does the ONE-TIME enrichment of the frozen
`pre-refactor-baseline.jsonl` into `decision_id` space (join on `request_hash`, cross-check
`log_prefix_hash`/`side`/`turn`, fail-closed on 0 or 2+ matches), preserving the legacy score
verbatim as `legacy_frozen_score`. Writes `data/eval/accuracy-cap-derisk/decision-id-manifest.jsonl`
— never touches the frozen baseline file itself.

- [ ] **Step 1: Write the script**

```python
# showdown_bot/scripts/build_decision_id_manifest.py
"""Real run: extract all 944 decisions from the full deduplicated corpus, compute decision_id
(spec Sec.2.2) for each, assert uniqueness, then do the ONE-TIME enrichment of the frozen
data/eval/accuracy-gate/pre-refactor-baseline.jsonl into decision_id space (join on request_hash,
cross-checked against log_prefix_hash/side/turn, fail-closed on ambiguous/missing matches).

Writes data/eval/accuracy-cap-derisk/decision-id-manifest.jsonl. The frozen baseline file itself
is read-only and untouched.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/build_decision_id_manifest.py
"""

from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
FROZEN_BASELINE = DATA_EVAL / "accuracy-gate" / "pre-refactor-baseline.jsonl"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
OUT_PATH = OUT_DIR / "decision-id-manifest.jsonl"
EXPECTED_FINAL_G = 85
EXPECTED_DECISION_COUNT = 944


def main() -> None:
    from showdown_bot.eval.accuracy_cap_derisk import (
        DecisionIdComponents,
        assert_decision_ids_unique,
        compute_decision_id,
    )
    from showdown_bot.eval.room_raw_replay import (
        RequestKind,
        deduplicate_battle_logs,
        extract_decisions_from_log,
    )

    # --- corpus extraction, byte-identical to run_accuracy_gate_b.py (Task 11 of the
    # accuracy-offline-gate plan) ---
    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw",
        DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw",
        DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)

    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl",
        DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl",
        DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(
            f"BLOCKED: expected final_g == {EXPECTED_FINAL_G}, got {dedup_report.final_g}. "
            f"Refusing to build decision_ids over an unverified corpus."
        )
    print(f"dedup: kept={len(dedup_report.kept)} final_g={dedup_report.final_g}")

    missing_identity = [p for p in dedup_report.kept if p not in dedup_report.kept_identities]
    if missing_identity:
        raise SystemExit(
            f"BLOCKED: {len(missing_identity)} kept file(s) have no SeedIdentity in "
            f"kept_identities (content-hash-fallback-kept) -- this plan's decision_id scheme "
            f"assumes every kept file has one, verified true for this corpus as of writing; "
            f"re-verify before proceeding. Files: {missing_identity}"
        )

    # --- extract, computing decision_id per row as we go (needs each file's SeedIdentity) ---
    manifest_rows: list[dict] = []
    kind_counts: Counter = Counter()
    for p in sorted(dedup_report.kept, key=str):
        identity = dedup_report.kept_identities[p]
        decisions = extract_decisions_from_log(p)
        for d in decisions:
            kind_counts[d.kind] += 1
            if d.kind != RequestKind.MOVE:
                continue
            did = compute_decision_id(DecisionIdComponents(
                seed_base=identity.seed_base, seed_index=identity.seed_index,
                request_hash=d.request_hash, log_prefix_hash=d.log_prefix_hash,
                side=d.side, rqid=d.request.rqid, turn=d.turn,
            ))
            manifest_rows.append({
                "decision_id": did,
                "seed_base": identity.seed_base, "seed_index": identity.seed_index,
                "request_hash": d.request_hash, "log_prefix_hash": d.log_prefix_hash,
                "side": d.side, "rqid": d.request.rqid, "turn": d.turn,
                "source_file": str(p),
            })

    print(f"decision kinds: {dict(kind_counts)}")
    if len(manifest_rows) != EXPECTED_DECISION_COUNT:
        raise SystemExit(
            f"BLOCKED: expected {EXPECTED_DECISION_COUNT} MOVE decisions, got "
            f"{len(manifest_rows)}. Investigate before proceeding."
        )

    assert_decision_ids_unique([r["decision_id"] for r in manifest_rows])
    print(f"decision_id uniqueness confirmed: {len(manifest_rows)} unique ids")

    # --- one-time frozen-baseline enrichment: join on request_hash, cross-check
    # log_prefix_hash/side/turn, fail-closed on 0 or 2+ matches ---
    by_request_hash: dict[str, list[dict]] = {}
    for r in manifest_rows:
        by_request_hash.setdefault(r["request_hash"], []).append(r)

    frozen_rows = [json.loads(line) for line in FROZEN_BASELINE.read_text(encoding="utf-8").splitlines() if line]
    print(f"frozen baseline: {len(frozen_rows)} rows read (read-only)")

    enriched = 0
    for r in manifest_rows:
        r["legacy_frozen_score"] = None
        r["legacy_frozen_chosen_action"] = None

    manifest_by_did = {r["decision_id"]: r for r in manifest_rows}
    for frow in frozen_rows:
        candidates = [
            r for r in by_request_hash.get(frow["request_hash"], [])
            if r["log_prefix_hash"] == frow["log_prefix_hash"]
            and r["side"] == frow["side"] and r["turn"] == frow["turn"]
        ]
        if len(candidates) != 1:
            raise SystemExit(
                f"BLOCKED: frozen baseline row request_hash={frow['request_hash']!r} "
                f"log_prefix_hash={frow['log_prefix_hash']!r} side={frow['side']!r} "
                f"turn={frow['turn']!r} matched {len(candidates)} decision_id candidates "
                f"(expected exactly 1) -- fail-closed, investigate before proceeding."
            )
        did = candidates[0]["decision_id"]
        manifest_by_did[did]["legacy_frozen_score"] = frow["score"]
        manifest_by_did[did]["legacy_frozen_chosen_action"] = frow["chosen_action"]
        enriched += 1

    print(f"frozen-baseline enrichment: {enriched}/{len(frozen_rows)} rows matched "
          f"exactly one decision_id (fail-closed on any other outcome, none occurred)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        for r in sorted(manifest_rows, key=lambda x: x["decision_id"]):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"wrote {OUT_PATH} ({len(manifest_rows)} rows)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run for real**

Run (from `showdown_bot/`): `PYTHONPATH="$(pwd)/src" python scripts/build_decision_id_manifest.py`

Expected: `dedup: kept=85 final_g=85`, `decision_id uniqueness confirmed: 944 unique ids`,
`frozen-baseline enrichment: 944/944 rows matched exactly one decision_id`, and
`data/eval/accuracy-cap-derisk/decision-id-manifest.jsonl` written with 944 rows. **If uniqueness
assertion or the enrichment fail-closed check raises: STOP, do not proceed to Task 5, investigate.**

- [ ] **Step 3: Confirm the frozen baseline was not touched**

Run: `git status --short -- data/eval/accuracy-gate/`
Expected: empty (no changes)

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/scripts/build_decision_id_manifest.py data/eval/accuracy-cap-derisk/decision-id-manifest.jsonl
git commit -m "feat(eval): real decision_id manifest for all 944 decisions + frozen-baseline enrichment"
```

---

## Task 5: Real action-capture runs — cap=4 auxiliary, cap=6, cap=8

**Files:**
- Create: `showdown_bot/scripts/run_cap_action_capture.py`

Implements spec §2.3's real action-capture tables. Parametrized by `SHOWDOWN_ACCURACY_BRANCH_CAP`;
run three times (4, 6, 8). The cap=4 run is explicitly tagged `cap4_auxiliary` throughout — never a
new gate verdict.

- [ ] **Step 1: Write the script**

```python
# showdown_bot/scripts/run_cap_action_capture.py
"""Real run: for a given SHOWDOWN_ACCURACY_BRANCH_CAP value, replay all 944 MOVE decisions through
heuristic_choose_for_request(trace=...) with SHOWDOWN_ACCURACY_MODE=1, and build a full
{decision_id, chosen_action, candidate_resolution_status, chosen_candidate_rank,
chosen_rank_mismatch, top_rank_score, chosen_candidate_score} table (spec Sec.2.3).

cap=4's run is an AUXILIARY action-capture -- explicitly labeled as such, never a new gate verdict
(data/eval/accuracy-gate/gate-b-report.json stays the sole authoritative cap=4 result). cap=6/cap=8
are this study's own primary action-capture runs.

Usage (from showdown_bot/):
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 4 --label cap4_auxiliary
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 6 --label cap6
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 8 --label cap8
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("SHOWDOWN_CALC_BACKEND", "persistent")

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, required=True, choices=[4, 6, 8])
    parser.add_argument("--label", type=str, required=True)  # e.g. "cap4_auxiliary", "cap6", "cap8"
    args = parser.parse_args()

    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_cap_derisk import (
        DecisionIdComponents, build_action_table_row, compute_decision_id,
    )
    from showdown_bot.eval.room_raw_replay import (
        RequestKind, deduplicate_battle_logs, extract_decisions_from_log,
    )

    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw", DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw", DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)

    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl", DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl", DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl", DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(f"BLOCKED: expected final_g == {EXPECTED_FINAL_G}, got {dedup_report.final_g}")

    all_decisions = []
    for p in sorted(dedup_report.kept, key=str):
        identity = dedup_report.kept_identities[p]
        for d in extract_decisions_from_log(p):
            if d.kind != RequestKind.MOVE:
                continue
            did = compute_decision_id(DecisionIdComponents(
                seed_base=identity.seed_base, seed_index=identity.seed_index,
                request_hash=d.request_hash, log_prefix_hash=d.log_prefix_hash,
                side=d.side, rqid=d.request.rqid, turn=d.turn,
            ))
            all_decisions.append((did, d))
    print(f"{len(all_decisions)} MOVE decisions to replay at cap={args.cap}")

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
    os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(args.cap)

    rows = []
    t0 = time.perf_counter()
    for decision_id, d in all_decisions:
        trace = DecisionTrace()
        chosen = heuristic_choose_for_request(
            d.request, state=copy.deepcopy(d.state), book=book, our_side=d.side,
            calc=calc, oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=dex, trace=trace,
        )
        rows.append(build_action_table_row(decision_id, chosen, trace))
    elapsed = time.perf_counter() - t0
    print(f"cap={args.cap} action-capture complete in {elapsed:.1f}s "
          f"({(elapsed / len(all_decisions)) * 1000:.1f} ms/decision)")

    os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{args.label}-action-capture.jsonl"
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        for r in sorted(rows, key=lambda x: x.decision_id):
            fh.write(json.dumps(asdict(r), sort_keys=True) + "\n")
    print(f"wrote {out_path} ({len(rows)} rows)")

    status_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r.candidate_resolution_status] = status_counts.get(r.candidate_resolution_status, 0) + 1
    print(f"candidate_resolution_status breakdown: {status_counts}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run for real, three times**

```bash
PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 4 --label cap4_auxiliary
PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 6 --label cap6
PYTHONPATH="$(pwd)/src" python scripts/run_cap_action_capture.py --cap 8 --label cap8
```

Expected: each run reports `944 MOVE decisions to replay`, completes, writes
`data/eval/accuracy-cap-derisk/cap4_auxiliary-action-capture.jsonl` /
`cap6-action-capture.jsonl` / `cap8-action-capture.jsonl` with 944 rows each, and prints a
`candidate_resolution_status` breakdown (expect `ambiguous_label` counts roughly in the ballpark of
the historical 63 for cap=4, though not necessarily identical — that comparison is Task 6's job, not
this one).

- [ ] **Step 3: Commit**

```bash
git add showdown_bot/scripts/run_cap_action_capture.py data/eval/accuracy-cap-derisk/*-action-capture.jsonl
git commit -m "feat(eval): real cap=4/6/8 action-capture runs, full 944-decision tables"
```

---

## Task 6: Two-stage validation gate for the cap=4 auxiliary table — HARD CHECKPOINT

**Files:**
- Create: `showdown_bot/scripts/validate_cap4_auxiliary.py`
- Modify: `showdown_bot/tests/eval/test_accuracy_cap_derisk.py`

Implements spec §2.3's Stage 1 (raw reproduction on the historical 881-eligible set) then Stage 2
(normalized semantic diff, `compare_action_tables`). **Cap=6/8 must never be compared against the
cap=4 auxiliary table until this passes** — this task is a hard checkpoint for Task 7/8.

**Confirmed real fact (checked this session, not left open):** `showdown_bot/scripts/` has no
`__init__.py` — it is not an importable Python package — and `pyproject.toml` scopes pytest to
`testpaths = ["tests"]` only. So the testable Stage-1/Stage-2 logic lives in
`showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py` (an already-importable, already-tested
module from Tasks 1-3), and `validate_cap4_auxiliary.py` is a thin, untested-by-pytest real-run
wrapper around it — exactly the same "pure logic in the eval module, real-run driver in scripts/"
split every other task in this plan already follows. The test file therefore lives at
`showdown_bot/tests/eval/test_accuracy_cap_derisk.py` (appended to the existing file from Tasks
1-3), not a separate `tests/eval/test_validate_cap4_auxiliary.py`.

- [ ] **Step 1: Write the failing unit tests for the two-stage logic**

```python
# appended to showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from showdown_bot.eval.accuracy_cap_derisk import (
    ActionTableRow,
    Stage1ReproductionError,
    run_stage1_raw_reproduction,
    run_stage2_semantic_diff,
)


def _aux_row(decision_id, action):
    return ActionTableRow(
        decision_id=decision_id, chosen_action=action, candidate_resolution_status="exact",
        chosen_candidate_rank=0, chosen_rank_mismatch=False, top_rank_score=1.0, chosen_candidate_score=1.0,
    )


def test_stage1_passes_when_raw_diff_set_matches_frozen_exactly():
    aux = [_aux_row("id1", "/choose move 1"), _aux_row("id2", "/choose move 2")]
    frozen_actions = {"id1": "/choose move 1", "id2": "/choose move 3"}  # id2 differs -> 1 known diff
    frozen_20_decision_ids = {"id2"}
    result = run_stage1_raw_reproduction(aux, frozen_actions, frozen_20_decision_ids)
    assert result.passed is True
    assert result.raw_diff_decision_ids == {"id2"}


def test_stage1_raises_on_unexpected_raw_diff():
    aux = [_aux_row("id1", "/choose move 99")]  # unexpectedly differs
    frozen_actions = {"id1": "/choose move 1"}
    frozen_20_decision_ids = set()  # id1 was NOT one of the frozen 20
    with pytest.raises(Stage1ReproductionError) as exc_info:
        run_stage1_raw_reproduction(aux, frozen_actions, frozen_20_decision_ids)
    assert "id1" in str(exc_info.value)


def test_stage1_raises_on_missing_expected_diff():
    aux = [_aux_row("id1", "/choose move 1")]  # now matches, but frozen report said it should diff
    frozen_actions = {"id1": "/choose move 1"}
    frozen_20_decision_ids = {"id1"}  # expected a diff here
    with pytest.raises(Stage1ReproductionError):
        run_stage1_raw_reproduction(aux, frozen_actions, frozen_20_decision_ids)


def test_stage2_smaller_normalized_set_than_raw_20_is_not_a_failure():
    """If Stage 1 passed (raw matches the historical 20) but two of those raw diffs turn out to
    be pure representational differences (normalize_choose folds them to the same action), Stage 2
    reports 18 semantic diffs -- honestly, not as a validation failure."""
    aux = [_aux_row("id1", "/choose move 1"), _aux_row("id2", "/choose move 2 ")]  # trailing space
    frozen_actions = {"id1": "/choose move 9", "id2": "/choose move 2"}  # id2: raw differs, normalized doesn't
    result = run_stage2_semantic_diff(aux, frozen_actions, request=None)
    # id1: genuinely different action -> action_changed True; id2: pure whitespace -> False
    changed = {r.decision_id for r in result.rows if r.action_changed}
    assert changed == {"id1"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v -k stage1_or_stage2` (or just
`-k stage`) — adjust the `-k` filter to match the actual test names above.
Expected: FAIL with `ImportError: cannot import name 'Stage1ReproductionError'`

- [ ] **Step 3: Implement the two-stage logic**

Put the pure, testable Stage-1/Stage-2 functions in `accuracy_cap_derisk.py` (reusing the module
from Tasks 1-3), and make `validate_cap4_auxiliary.py` a thin real-run driver that reads the real
artifacts and calls them — this avoids the `scripts/`-as-package import question entirely and
matches this module's existing "pure logic here, real-run driver separately" split.

```python
# appended to showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py

@dataclass(frozen=True)
class Stage1Result:
    passed: bool
    raw_diff_decision_ids: set[str]


class Stage1ReproductionError(Exception):
    pass


def run_stage1_raw_reproduction(
    auxiliary_rows: list[ActionTableRow],
    frozen_actions_by_decision_id: dict[str, str],
    frozen_20_decision_ids: set[str],
) -> Stage1Result:
    """Spec Sec.2.3 Stage 1: raw (un-normalized) string comparison only, restricted to the
    historical 881-eligible set (callers must pre-filter both inputs to that set before calling).
    Must exactly reproduce the frozen 20 -- any deviation raises immediately."""
    aux_by_id = {r.decision_id: r for r in auxiliary_rows}
    if set(aux_by_id) != set(frozen_actions_by_decision_id):
        raise Stage1ReproductionError(
            f"decision_id set mismatch between auxiliary rows and frozen actions: "
            f"only-in-auxiliary={set(aux_by_id) - set(frozen_actions_by_decision_id)} "
            f"only-in-frozen={set(frozen_actions_by_decision_id) - set(aux_by_id)}"
        )
    raw_diff_ids = {
        did for did, frozen_action in frozen_actions_by_decision_id.items()
        if aux_by_id[did].chosen_action != frozen_action
    }
    if raw_diff_ids != frozen_20_decision_ids:
        raise Stage1ReproductionError(
            f"raw reproduction FAILED: expected diff set {sorted(frozen_20_decision_ids)}, "
            f"got {sorted(raw_diff_ids)} -- unexpected={sorted(raw_diff_ids - frozen_20_decision_ids)} "
            f"missing={sorted(frozen_20_decision_ids - raw_diff_ids)}"
        )
    return Stage1Result(passed=True, raw_diff_decision_ids=raw_diff_ids)


def run_stage2_semantic_diff(
    auxiliary_rows: list[ActionTableRow],
    frozen_actions_by_decision_id: dict[str, str],
    *,
    request=None,
) -> ActionTableDiff:
    """Spec Sec.2.3 Stage 2: only meaningful after Stage 1 passes. normalize_choose-based semantic
    diff via compare_action_tables -- answers "how many semantically distinct decisions", not "is
    this the same run"."""
    frozen_rows = [
        ActionTableRow(
            decision_id=did, chosen_action=action, candidate_resolution_status="exact",
            chosen_candidate_rank=0, chosen_rank_mismatch=False, top_rank_score=None, chosen_candidate_score=None,
        )
        for did, action in frozen_actions_by_decision_id.items()
    ]
    aux_by_id = {r.decision_id: r for r in auxiliary_rows if r.decision_id in frozen_actions_by_decision_id}
    return compare_action_tables(
        frozen_rows, list(aux_by_id.values()), direction="off -> cap4_auxiliary",
        request=request, score_comparable=False,
        score_incompatible_reason="legacy_frozen_score not proven equivalent (see Task 4's verified finding)",
    )
```

```python
# showdown_bot/scripts/validate_cap4_auxiliary.py
"""Real run: validates the cap=4 auxiliary action-capture table (Task 5) against the frozen
gate-b-report.json's historical 20 diffs, two-stage (spec Sec.2.3). HARD CHECKPOINT -- if this
fails, STOP, do not run Task 7/8's cap6/cap8 comparisons against this table.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/validate_cap4_auxiliary.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
GATE_B_REPORT = DATA_EVAL / "accuracy-gate" / "gate-b-report.json"
MANIFEST_PATH = DATA_EVAL / "accuracy-cap-derisk" / "decision-id-manifest.jsonl"
AUX_PATH = DATA_EVAL / "accuracy-cap-derisk" / "cap4_auxiliary-action-capture.jsonl"
OUT_PATH = DATA_EVAL / "accuracy-cap-derisk" / "cap4-auxiliary-validation-report.json"


def main() -> None:
    from showdown_bot.eval.accuracy_cap_derisk import (
        ActionTableRow, run_stage1_raw_reproduction, run_stage2_semantic_diff,
    )

    gate_b = json.loads(GATE_B_REPORT.read_text(encoding="utf-8"))
    manifest_rows = [json.loads(l) for l in MANIFEST_PATH.read_text(encoding="utf-8").splitlines() if l]
    aux_rows_raw = [json.loads(l) for l in AUX_PATH.read_text(encoding="utf-8").splitlines() if l]
    aux_rows = [ActionTableRow(**r) for r in aux_rows_raw]

    manifest_by_request_hash = {r["request_hash"]: r for r in manifest_rows}
    excluded_request_hashes = {e["request_hash"] for e in gate_b["acceptance"]["exceptions"]}
    if len(excluded_request_hashes) != 63:
        raise SystemExit(f"BLOCKED: expected 63 historical exceptions, found {len(excluded_request_hashes)}")

    eligible_881_decision_ids = {
        manifest_by_request_hash[rh]["decision_id"]
        for rh in manifest_by_request_hash if rh not in excluded_request_hashes
    }
    if len(eligible_881_decision_ids) != 881:
        raise SystemExit(f"BLOCKED: expected 881 eligible decision_ids, got {len(eligible_881_decision_ids)}")

    frozen_20_by_request_hash = {d["request_hash"]: d["on_chosen_action"] for d in gate_b["diffs"]}
    frozen_20_decision_ids = {
        manifest_by_request_hash[rh]["decision_id"] for rh in frozen_20_by_request_hash
    }

    frozen_actions_881 = {
        manifest_by_request_hash[rh]["decision_id"]: manifest_by_request_hash[rh]["legacy_frozen_chosen_action"]
        for rh in manifest_by_request_hash if rh not in excluded_request_hashes
    }
    aux_881 = [r for r in aux_rows if r.decision_id in eligible_881_decision_ids]

    print(f"Stage 1: raw reproduction check on {len(aux_881)} eligible decisions "
          f"(expecting exactly {len(frozen_20_decision_ids)} raw diffs)...")
    stage1 = run_stage1_raw_reproduction(aux_881, frozen_actions_881, frozen_20_decision_ids)
    print(f"Stage 1 PASSED: raw diff set exactly matches the frozen 20.")

    print("Stage 2: normalized semantic diff on the same 881...")
    stage2 = run_stage2_semantic_diff(aux_881, frozen_actions_881)
    print(f"Stage 2: {stage2.action_changed_count} semantically distinct action changes "
          f"(raw Stage-1 diff count was {len(stage1.raw_diff_decision_ids)} -- if smaller, "
          f"the difference is pre-existing representational diffs, not a failure).")

    # --- the 63 historical exclusions, evaluated separately, never folded into Stage 1/2 above ---
    excluded_decision_ids = {manifest_by_request_hash[rh]["decision_id"] for rh in excluded_request_hashes}
    aux_63 = [r for r in aux_rows if r.decision_id in excluded_decision_ids]
    frozen_actions_63 = {
        manifest_by_request_hash[rh]["decision_id"]: manifest_by_request_hash[rh]["legacy_frozen_chosen_action"]
        for rh in excluded_request_hashes
    }
    diffs_among_63 = sum(
        1 for r in aux_63 if r.chosen_action != frozen_actions_63.get(r.decision_id)
    )
    print(f"Among the 63 historical exclusions: {diffs_among_63} raw action diffs found "
          f"(diagnostic bonus info for Task 10/11 -- NOT part of Stage 1/2, frozen gate unchanged).")

    OUT_PATH.write_text(json.dumps({
        "stage1_passed": stage1.passed,
        "stage1_raw_diff_count": len(stage1.raw_diff_decision_ids),
        "stage2_semantic_diff_count": stage2.action_changed_count,
        "diffs_among_historical_63": diffs_among_63,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print("\nVALIDATION GATE PASSED. Cap=6/8 may now be compared against the cap4_auxiliary table.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run unit tests, then the real validation**

```bash
python -m pytest tests/eval/test_accuracy_cap_derisk.py -v
```
Expected: PASS (all tests from Tasks 1-3 plus the 4 new Stage-1/Stage-2 tests from this task)

```bash
PYTHONPATH="$(pwd)/src" python scripts/validate_cap4_auxiliary.py
```
Expected: `Stage 1 PASSED`, a Stage 2 semantic-diff count printed, a diffs-among-63 count printed,
`data/eval/accuracy-cap-derisk/cap4-auxiliary-validation-report.json` written, ending with
`VALIDATION GATE PASSED`. **If Stage 1 raises: STOP. Do not proceed to Task 7 or Task 8. Root-cause
the discrepancy — do not weaken the gate to force a pass.**

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py showdown_bot/scripts/validate_cap4_auxiliary.py showdown_bot/tests/eval/test_accuracy_cap_derisk.py data/eval/accuracy-cap-derisk/cap4-auxiliary-validation-report.json
git commit -m "feat(eval): two-stage cap4-auxiliary validation gate (raw then semantic), real run PASSED"
```

---

## Task 7: Cap=6/Cap=8 Gate B verdicts — unchanged `run_gate_b`, full G=85 corpus

**Files:**
- Create: `showdown_bot/scripts/run_cap_gate_verdicts.py`

Implements spec §2.5. Directly mirrors `run_accuracy_gate_b.py` (Task 11 of the accuracy-offline-gate
plan) but parametrized by cap, run for cap=6 and cap=8 (never cap=4 — that verdict stays frozen).

- [ ] **Step 1: Write the script**

```python
# showdown_bot/scripts/run_cap_gate_verdicts.py
"""Real run: SHOWDOWN_ACCURACY_BRANCH_CAP in {6, 8}, full G=85 corpus, via the UNCHANGED
accuracy_gate_b.run_gate_b / accuracy_gate_stats.verdict_for_cap_hit_rate (spec Sec.2.5). Mirrors
run_accuracy_gate_b.py exactly except for the branch-cap env var and output path. cap=4 is never
run here -- data/eval/accuracy-gate/gate-b-report.json stays the sole authoritative cap=4 result.

Usage (from showdown_bot/):
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_gate_verdicts.py --cap 6
    PYTHONPATH="$(pwd)/src" python scripts/run_cap_gate_verdicts.py --cap 8
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("SHOWDOWN_CALC_BACKEND", "persistent")

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, required=True, choices=[6, 8])
    args = parser.parse_args()

    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_gate_b import run_gate_b
    from showdown_bot.eval.room_raw_replay import (
        RequestKind, deduplicate_battle_logs, extract_decisions_from_log,
    )

    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw", DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw", DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)

    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl", DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl", DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl", DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(f"BLOCKED: expected final_g == {EXPECTED_FINAL_G}, got {dedup_report.final_g}")

    all_decisions = []
    decision_to_battle_id: dict[int, str] = {}
    kind_counts: Counter = Counter()
    for p in sorted(dedup_report.kept, key=str):
        battle_id = _rel(p)
        for d in extract_decisions_from_log(p):
            kind_counts[d.kind] += 1
            decision_to_battle_id[id(d)] = battle_id
            all_decisions.append(d)

    def battle_id_for(d):
        return decision_to_battle_id[id(d)]

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(args.cap)
    print(f"running Gate B (unchanged run_gate_b) at cap={args.cap}, full corpus...")
    t0 = time.perf_counter()
    result = run_gate_b(
        decisions=all_decisions, battle_id_for=battle_id_for,
        book=book, calc=calc, oracle_factory=lambda: DamageOracle(calc),
        speed_oracle=speed_oracle, dex=dex,
    )
    elapsed = time.perf_counter() - t0
    os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
    print(f"cap={args.cap} Gate B complete in {elapsed:.1f}s")

    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception:
        source_commit = None

    move_decision_count = kind_counts[RequestKind.MOVE]
    payload = {
        "report_schema_version": "cap-derisk-gate-report-v1",
        "branch_cap": args.cap,
        "source_commit": source_commit,
        "elapsed_seconds": round(elapsed, 1),
        "dedup": {
            "files_found": dedup_report.files_found, "unique_battles_final_g": dedup_report.final_g,
        },
        "decision_kind_counts": {k.value: v for k, v in kind_counts.items()},
        "n_decisions_compared": result.n_decisions_compared,
        "cap_hit_verdict": result.cap_hit_verdict.value if result.cap_hit_verdict else None,
        "cap_hit_verdict_detail": result.cap_hit_verdict_detail,
        "acceptance": {
            "no_exceptions": result.acceptance.no_exceptions,
            "no_nans": result.acceptance.no_nans,
            "exception_count": len(result.acceptance.exceptions),
            "exceptions": [{"request_hash": rh, "exception": msg} for rh, msg in result.acceptance.exceptions],
        },
        "diff_count": len(result.diffs),
        "diffs": [
            {
                "request_hash": d.request_hash, "off_chosen_action": d.off_chosen_action,
                "on_chosen_action": d.on_chosen_action, "off_score": d.off_score, "on_score": d.on_score,
                "tera_changed": d.tera_changed, "action_diff_kind": d.action_diff_kind,
                "events_complete": d.events_complete, "mechanically_explained": d.mechanically_explained,
                "left_top_k": d.left_top_k, "entered_top_k": d.entered_top_k,
            }
            for d in result.diffs
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"cap{args.cap}-report.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"n_decisions_compared={result.n_decisions_compared} exceptions={len(result.acceptance.exceptions)} "
          f"diff_count={len(result.diffs)} cap_hit_verdict={result.cap_hit_verdict}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run for real, both caps**

```bash
PYTHONPATH="$(pwd)/src" python scripts/run_cap_gate_verdicts.py --cap 6
PYTHONPATH="$(pwd)/src" python scripts/run_cap_gate_verdicts.py --cap 8
```

Expected: both complete, write `data/eval/accuracy-cap-derisk/cap6-report.json` /
`cap8-report.json` with real `cap_hit_verdict`/`cap_hit_verdict_detail`/`diffs`/`acceptance` data.
Report the actual numbers — do not assume or pre-guess the verdict.

- [ ] **Step 3: Commit**

```bash
git add showdown_bot/scripts/run_cap_gate_verdicts.py data/eval/accuracy-cap-derisk/cap6-report.json data/eval/accuracy-cap-derisk/cap8-report.json
git commit -m "feat(eval): real cap=6/cap=8 Gate B verdicts, unchanged run_gate_b, full G=85 corpus"
```

---

## Task 8: Cross-cap/cross-mode diffs — `compare_action_tables` applied for real

**Files:**
- Create: `showdown_bot/scripts/run_cap_cross_diffs.py`

Implements spec §2.4's four real diffs (cap6-vs-cap4, cap6-vs-off, cap8-vs-cap4, cap8-vs-off),
respecting the score-semantic rules from Task 3/§2.3 (off-vs-cap score comparisons skipped, per the
verified `legacy_frozen_score` non-equivalence finding at the top of this plan).

- [ ] **Step 1: Write the script**

```python
# showdown_bot/scripts/run_cap_cross_diffs.py
"""Real run: cap6-vs-cap4, cap6-vs-off, cap8-vs-cap4, cap8-vs-off action diffs, via
compare_action_tables (Task 2), reading the action-capture tables from Task 5 and the
decision-id-manifest from Task 4. off-vs-cap score comparisons are explicitly SKIPPED (spec
Sec.2.3 -- legacy_frozen_score's construction is verified non-equivalent to chosen_candidate_score,
see this plan's "Real API facts" section).

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/run_cap_cross_diffs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"


def _load_rows(path: Path):
    from showdown_bot.eval.accuracy_cap_derisk import ActionTableRow
    return [ActionTableRow(**json.loads(l)) for l in path.read_text(encoding="utf-8").splitlines() if l]


def main() -> None:
    from dataclasses import asdict

    from showdown_bot.eval.accuracy_cap_derisk import ActionTableRow, compare_action_tables

    manifest_rows = [
        json.loads(l) for l in (OUT_DIR / "decision-id-manifest.jsonl").read_text(encoding="utf-8").splitlines() if l
    ]
    off_rows = [
        ActionTableRow(
            decision_id=r["decision_id"], chosen_action=r["legacy_frozen_chosen_action"],
            candidate_resolution_status="exact", chosen_candidate_rank=0, chosen_rank_mismatch=False,
            top_rank_score=None, chosen_candidate_score=None,
        )
        for r in manifest_rows
    ]
    cap4_rows = _load_rows(OUT_DIR / "cap4_auxiliary-action-capture.jsonl")
    cap6_rows = _load_rows(OUT_DIR / "cap6-action-capture.jsonl")
    cap8_rows = _load_rows(OUT_DIR / "cap8-action-capture.jsonl")

    pairs = [
        ("cap4 -> cap6", cap4_rows, cap6_rows, True, None),
        ("cap4 -> cap8", cap4_rows, cap8_rows, True, None),
        ("off -> cap6", off_rows, cap6_rows, False, "legacy_frozen_score not proven equivalent to top_rank_score/chosen_candidate_score"),
        ("off -> cap8", off_rows, cap8_rows, False, "legacy_frozen_score not proven equivalent to top_rank_score/chosen_candidate_score"),
    ]

    results = {}
    for direction, ref, cand, score_comparable, reason in pairs:
        diff = compare_action_tables(
            ref, cand, direction=direction, score_comparable=score_comparable,
            score_incompatible_reason=reason,
        )
        print(f"{direction}: {diff.action_changed_count}/{len(diff.rows)} action changes "
              f"(score_comparable={score_comparable})")
        results[direction] = {
            "action_changed_count": diff.action_changed_count,
            "total": len(diff.rows),
            "rows": [asdict(r) for r in diff.rows if r.action_changed],  # only the changed rows, full table is large
        }

    out_path = OUT_DIR / "cross-cap-diffs.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run for real**

Run: `PYTHONPATH="$(pwd)/src" python scripts/run_cap_cross_diffs.py`

Expected: 4 lines of real diff counts printed, `data/eval/accuracy-cap-derisk/cross-cap-diffs.json`
written. **This task depends on Task 6's validation gate having passed** — if it hasn't, stop and go
back, do not run this against an unvalidated cap4 auxiliary table.

- [ ] **Step 3: Commit**

```bash
git add showdown_bot/scripts/run_cap_cross_diffs.py data/eval/accuracy-cap-derisk/cross-cap-diffs.json
git commit -m "feat(eval): real cross-cap/cross-mode action diffs via compare_action_tables"
```

---

## Task 9: Latency sweep — full corpus, both trace modes, confound-controlled

**Files:**
- Create: `showdown_bot/scripts/run_cap_latency_sweep.py`

Implements spec §2.6. Full 944-decision corpus, `cap4_auxiliary`/cap6/cap8, trace-none and
trace-enabled measured separately, cap order rotated per game rather than fixed 4→6→8, backend
warmed once up front.

- [ ] **Step 1: Write the script**

```python
# showdown_bot/scripts/run_cap_latency_sweep.py
"""Real run: full-corpus latency, both trace modes (none / DecisionTrace()), for
SHOWDOWN_ACCURACY_BRANCH_CAP in {4 (cap4_auxiliary), 6, 8}, spec Sec.2.6. Cap order is rotated per
game (not fixed 4->6->8 every time) to avoid confounding cap effects with warm-up/ordering/
backend-state effects; the persistent calc backend is warmed once, up front, before any timed
measurement.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/run_cap_latency_sweep.py
"""
from __future__ import annotations

import copy
import glob
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("SHOWDOWN_CALC_BACKEND", "persistent")

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"
EXPECTED_FINAL_G = 85
CAPS = [4, 6, 8]  # cap=4 here is cap4_auxiliary latency, per spec Sec.2.3's explicit allowance
ORDER_SEED = 20260713  # pre-pinned, matches this plan's other pinned seeds' convention


def _percentile(sorted_ms: list[float], q: float) -> float:
    idx = min(len(sorted_ms) - 1, max(0, int(round(q * (len(sorted_ms) - 1)))))
    return sorted_ms[idx]


def main() -> None:
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.room_raw_replay import (
        RequestKind, deduplicate_battle_logs, extract_decisions_from_log,
    )

    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw", DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw", DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)
    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl", DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl", DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl", DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(f"BLOCKED: expected final_g == {EXPECTED_FINAL_G}, got {dedup_report.final_g}")

    # group decisions by game (source file) for per-game cap-order rotation
    by_game: dict[str, list] = {}
    for p in sorted(dedup_report.kept, key=str):
        decisions = [d for d in extract_decisions_from_log(p) if d.kind == RequestKind.MOVE]
        by_game[str(p)] = decisions
    total_decisions = sum(len(v) for v in by_game.values())
    print(f"{total_decisions} MOVE decisions across {len(by_game)} games")

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    def decide(d, cap, with_trace):
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
        os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(cap)
        trace = DecisionTrace() if with_trace else None
        t0 = time.perf_counter()
        heuristic_choose_for_request(
            d.request, state=copy.deepcopy(d.state), book=book, our_side=d.side,
            calc=calc, oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=dex, trace=trace,
        )
        return (time.perf_counter() - t0) * 1000.0

    # --- warm the backend once, controlled, before ANY timed measurement ---
    print("warming persistent calc backend...")
    first_game_decisions = next(iter(by_game.values()))
    for d in first_game_decisions[:3]:
        decide(d, cap=4, with_trace=False)
    print("warm-up complete")

    # --- deterministic per-game cap-order rotation, not a fixed 4->6->8 sequence ---
    rng = random.Random(ORDER_SEED)
    game_ids = sorted(by_game)
    results: dict[str, dict[str, list[float]]] = {
        f"cap{c}": {"trace_none": [], "trace_enabled": []} for c in CAPS
    }
    exception_counts: dict[str, int] = {f"cap{c}": 0 for c in CAPS}
    measured_counts: dict[str, int] = {f"cap{c}": 0 for c in CAPS}

    for game_id in game_ids:
        order = CAPS[:]
        rng.shuffle(order)  # per-game rotation, deterministic given ORDER_SEED
        for cap in order:
            for d in by_game[game_id]:
                for with_trace, key in [(False, "trace_none"), (True, "trace_enabled")]:
                    try:
                        ms = decide(d, cap, with_trace)
                        results[f"cap{cap}"][key].append(ms)
                        measured_counts[f"cap{cap}"] += 1
                    except Exception as exc:  # noqa: BLE001
                        exception_counts[f"cap{cap}"] += 1
                        print(f"EXCEPTION cap={cap} trace={with_trace}: {exc}")

    os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass

    summary = {}
    for cap_key, series in results.items():
        summary[cap_key] = {}
        for mode_key, values in series.items():
            values_sorted = sorted(values)
            summary[cap_key][mode_key] = {
                "n": len(values_sorted),
                "p50": _percentile(values_sorted, 0.50) if values_sorted else None,
                "p95": _percentile(values_sorted, 0.95) if values_sorted else None,
                "max": values_sorted[-1] if values_sorted else None,
            }
        summary[cap_key]["exceptions"] = exception_counts[cap_key]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "latency-results.json"
    out_path.write_text(json.dumps({
        "order_seed": ORDER_SEED, "total_decisions": total_decisions,
        "sampled": False, "results": summary,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    for cap_key, s in summary.items():
        print(f"{cap_key}: trace_none p50={s['trace_none']['p50']:.1f}ms p95={s['trace_none']['p95']:.1f}ms | "
              f"trace_enabled p50={s['trace_enabled']['p50']:.1f}ms p95={s['trace_enabled']['p95']:.1f}ms | "
              f"exceptions={s['exceptions']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run for real**

Run: `PYTHONPATH="$(pwd)/src" python scripts/run_cap_latency_sweep.py`

This measures 944 decisions × 3 caps × 2 trace modes = 5,664 real `heuristic_choose_for_request`
calls — expect several minutes. **Full corpus, no sampling, per spec §2.6's "full-corpus-first, not
by default" rule** — if this proves genuinely infeasible (many hours, not minutes), STOP, do not
silently switch to sampling; report the real elapsed time and escalate rather than deciding
unilaterally to sample. Report the actual p50/p95/max/exception-count numbers — do not pre-guess
them.

- [ ] **Step 3: Commit**

```bash
git add showdown_bot/scripts/run_cap_latency_sweep.py data/eval/accuracy-cap-derisk/latency-results.json
git commit -m "feat(eval): real full-corpus latency sweep, cap4_auxiliary/6/8, trace-none+enabled separately"
```

---

## Task 10: Ambiguous-candidate two-tier classification scheme

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py`
- Modify: `showdown_bot/tests/eval/test_accuracy_cap_derisk.py`

Implements spec §3.1's exclusive-primary-cause + non-exclusive-companion-flags scheme.

- [ ] **Step 1: Write the failing tests**

```python
# appended to showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from showdown_bot.eval.accuracy_cap_derisk import classify_ambiguous_case


def test_classify_label_collision_switch_target_omitted():
    result = classify_ambiguous_case(
        chosen_candidate_id="(switch, pass)",
        matching_candidate_ids=["(switch, pass)", "(switch, pass)"],
        matching_joint_actions_distinct_switch_targets=True,
        matching_joint_actions_distinct_tera=False,
        matching_joint_actions_distinct_move_or_target=False,
        exact_score_tie=False, chosen_rank_mismatch=False,
    )
    assert result.primary_cause == "label_collision"
    assert result.label_collision_subtype == "switch_target_omitted"
    assert "distinct_switch_targets_same_label" in result.companion_flags


def test_classify_chosen_missing():
    result = classify_ambiguous_case(
        chosen_candidate_id="(nothing)", matching_candidate_ids=[],
        matching_joint_actions_distinct_switch_targets=False,
        matching_joint_actions_distinct_tera=False,
        matching_joint_actions_distinct_move_or_target=False,
        exact_score_tie=False, chosen_rank_mismatch=False,
        top_k_truncated=True,
    )
    assert result.primary_cause == "chosen_candidate_missing"
    assert "top_k_truncated" in result.companion_flags


def test_classify_primary_and_companion_flags_are_independent():
    """A label collision WITH a simultaneous exact score tie and rank mismatch -- both companion
    facts survive, neither forces a different primary cause (spec Sec.3.1)."""
    result = classify_ambiguous_case(
        chosen_candidate_id="(switch, pass)",
        matching_candidate_ids=["(switch, pass)", "(switch, pass)"],
        matching_joint_actions_distinct_switch_targets=True,
        matching_joint_actions_distinct_tera=False,
        matching_joint_actions_distinct_move_or_target=False,
        exact_score_tie=True, chosen_rank_mismatch=True,
    )
    assert result.primary_cause == "label_collision"  # unaffected by the companion facts
    assert "exact_score_tie" in result.companion_flags
    assert "chosen_rank_nonzero" in result.companion_flags


def test_classify_other_pipeline_error_requires_rationale():
    with pytest.raises(ValueError, match="rationale"):
        classify_ambiguous_case(
            chosen_candidate_id="(weird)", matching_candidate_ids=["(weird)"],
            matching_joint_actions_distinct_switch_targets=False,
            matching_joint_actions_distinct_tera=False,
            matching_joint_actions_distinct_move_or_target=False,
            exact_score_tie=False, chosen_rank_mismatch=False,
            force_other_pipeline_error=True,  # no rationale provided -> must raise
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v -k classify_ambiguous_case`
Expected: FAIL with `ImportError: cannot import name 'classify_ambiguous_case'`

- [ ] **Step 3: Implement the classifier**

```python
# appended to showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py


@dataclass(frozen=True)
class AmbiguousCaseClassification:
    primary_cause: str  # label_collision | chosen_candidate_missing | invalid_or_nonreconstructable_request | other_pipeline_error
    label_collision_subtype: str | None  # switch_target_omitted | ... (only when primary_cause == label_collision)
    companion_flags: frozenset[str]


def classify_ambiguous_case(
    *,
    chosen_candidate_id: str,
    matching_candidate_ids: list[str],
    matching_joint_actions_distinct_switch_targets: bool,
    matching_joint_actions_distinct_tera: bool,
    matching_joint_actions_distinct_move_or_target: bool,
    exact_score_tie: bool,
    chosen_rank_mismatch: bool,
    top_k_truncated: bool = False,
    request_reconstructable: bool = True,
    force_other_pipeline_error: bool = False,
    other_pipeline_error_rationale: str | None = None,
) -> AmbiguousCaseClassification:
    """Spec Sec.3.1's two-tier scheme. Primary cause is exactly one of 4 (5 with the optional
    other_resolution_error); companion flags are zero-or-more, independent of the primary cause."""
    flags: set[str] = set()
    if exact_score_tie:
        flags.add("exact_score_tie")
    if chosen_rank_mismatch:
        flags.add("chosen_rank_nonzero")
    if matching_joint_actions_distinct_switch_targets:
        flags.add("distinct_switch_targets_same_label")
    if matching_joint_actions_distinct_tera:
        flags.add("distinct_tera_state_same_label")
    if matching_joint_actions_distinct_move_or_target:
        flags.add("distinct_move_or_target_same_label")
    if top_k_truncated:
        flags.add("top_k_truncated")
    if len(matching_candidate_ids) >= 2:
        flags.add("multiple_structurally_equal_candidates")

    if force_other_pipeline_error:
        if not other_pipeline_error_rationale:
            raise ValueError("other_pipeline_error requires a concrete rationale, never a bare 'other'")
        return AmbiguousCaseClassification(
            primary_cause="other_pipeline_error", label_collision_subtype=None,
            companion_flags=frozenset(flags),
        )

    if not request_reconstructable:
        return AmbiguousCaseClassification(
            primary_cause="invalid_or_nonreconstructable_request", label_collision_subtype=None,
            companion_flags=frozenset(flags),
        )

    if len(matching_candidate_ids) == 0:
        return AmbiguousCaseClassification(
            primary_cause="chosen_candidate_missing", label_collision_subtype=None,
            companion_flags=frozenset(flags),
        )

    if len(matching_candidate_ids) >= 2:
        if matching_joint_actions_distinct_switch_targets:
            subtype = "switch_target_omitted"
        elif matching_joint_actions_distinct_tera:
            subtype = "tera_state_omitted"
        elif matching_joint_actions_distinct_move_or_target:
            subtype = "move_or_target_omitted"
        else:
            subtype = "unspecified_collision"
        return AmbiguousCaseClassification(
            primary_cause="label_collision", label_collision_subtype=subtype,
            companion_flags=frozenset(flags),
        )

    # exactly one match, none of the above -- shouldn't be reachable for a genuinely "ambiguous"
    # case, but fail with a clear reason rather than silently miscategorizing.
    raise ValueError(
        f"classify_ambiguous_case called on a non-ambiguous case (1 match, "
        f"chosen_candidate_id={chosen_candidate_id!r}) -- caller should only invoke this for "
        f"cases accuracy_gate_b's _chosen_candidate actually flagged as unresolved/ambiguous."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/eval/test_accuracy_cap_derisk.py -v`
Expected: PASS (22 passed)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py showdown_bot/tests/eval/test_accuracy_cap_derisk.py
git commit -m "feat(eval): two-tier ambiguous-case classifier -- exclusive primary cause + companion flags"
```

---

## Task 11: Apply classification to real cases (cap4/6/8) + fix-feasibility write-up

**Files:**
- Create: `showdown_bot/scripts/run_ambiguous_candidate_diagnostic.py`

Implements spec §3.3 (real classification run, overlap-by-decision_id across caps) and §3.2 (the
fix-feasibility investigation write-up).

- [ ] **Step 1: Write the script**

Before writing this, re-derive (don't just copy) the trace object for each of cap4's historical 63 /
cap6's / cap8's ambiguous cases — `run_gate_b`'s `acceptance.exceptions` only stores
`(request_hash, message)`, not the trace itself (traces aren't persisted). This script must
**re-run** `heuristic_choose_for_request(trace=...)` for exactly the ambiguous decision_ids at each
cap (a small, targeted re-run — dozens of decisions, not the full 944) to get a live `DecisionTrace`
to classify against, reusing the SAME real book/calc/oracle construction pattern as every other task
in this plan.

```python
# showdown_bot/scripts/run_ambiguous_candidate_diagnostic.py
"""Real run: classify every ambiguous/excluded decision at cap=4 (historical 63), cap=6, and
cap=8 (spec Sec.3.3), via a small targeted re-run (only the ambiguous decision_ids, not the full
944) to get a live trace to inspect. Also writes the fix-feasibility investigation (spec Sec.3.2)
into the same report -- investigation only, no decision.py code change.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/run_ambiguous_candidate_diagnostic.py
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SHOWDOWN_CALC_BACKEND", "persistent")

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"


def _classify_from_trace(trace, decision_request):
    """Bridges a real DecisionTrace to classify_ambiguous_case's structural inputs."""
    from showdown_bot.eval.accuracy_cap_derisk import _strip_tera, classify_ambiguous_case

    chosen_id = trace.chosen_candidate_id
    exact = [c for c in trace.candidates if c.candidate_id == chosen_id]
    matches = exact
    if not matches:
        stripped = _strip_tera(chosen_id) if chosen_id else None
        matches = [c for c in trace.candidates if stripped and _strip_tera(c.candidate_id) == stripped]

    ja_list = [c.joint_action for c in matches if c.joint_action is not None]
    distinct_switch = len({ja.slot0.target_ident if ja.slot0.kind == "switch" else None for ja in ja_list} | {ja.slot1.target_ident if ja.slot1.kind == "switch" else None for ja in ja_list}) > 1
    distinct_tera = len({(ja.slot0.terastallize, ja.slot1.terastallize) for ja in ja_list}) > 1
    distinct_move_target = len({(ja.slot0.move_index, ja.slot0.target, ja.slot1.move_index, ja.slot1.target) for ja in ja_list}) > 1

    scores = {c.aggregate_score for c in matches}
    exact_tie = len(scores) == 1 and len(matches) > 1
    ranks = {c.rank for c in matches}
    chosen_rank_mismatch = any(r != 0 for r in ranks) if matches else False

    return classify_ambiguous_case(
        chosen_candidate_id=chosen_id or "<none>",
        matching_candidate_ids=[c.candidate_id for c in matches],
        matching_joint_actions_distinct_switch_targets=distinct_switch,
        matching_joint_actions_distinct_tera=distinct_tera,
        matching_joint_actions_distinct_move_or_target=distinct_move_target,
        exact_score_tie=exact_tie, chosen_rank_mismatch=chosen_rank_mismatch,
    )


def _decisions_for_request_hashes(target_hashes: set[str]):
    from showdown_bot.eval.room_raw_replay import (
        RequestKind, deduplicate_battle_logs, extract_decisions_from_log,
    )
    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw", DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw", DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl", DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl", DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl", DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=sorted(set(log_files), key=str), manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    found = {}
    for p in sorted(dedup_report.kept, key=str):
        for d in extract_decisions_from_log(p):
            if d.kind == RequestKind.MOVE and d.request_hash in target_hashes:
                found[d.request_hash] = d
    return found


def main() -> None:
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle

    gate_b_cap4 = json.loads((DATA_EVAL / "accuracy-gate" / "gate-b-report.json").read_text(encoding="utf-8"))
    cap6 = json.loads((OUT_DIR / "cap6-report.json").read_text(encoding="utf-8"))
    cap8 = json.loads((OUT_DIR / "cap8-report.json").read_text(encoding="utf-8"))
    manifest = {
        r["request_hash"]: r
        for r in (json.loads(l) for l in (OUT_DIR / "decision-id-manifest.jsonl").read_text(encoding="utf-8").splitlines() if l)
    }

    per_cap_hashes = {
        "cap4": {e["request_hash"] for e in gate_b_cap4["acceptance"]["exceptions"]},
        "cap6": {e["request_hash"] for e in cap6["acceptance"]["exceptions"]},
        "cap8": {e["request_hash"] for e in cap8["acceptance"]["exceptions"]},
    }
    all_hashes = set().union(*per_cap_hashes.values())
    print(f"re-running {len(all_hashes)} distinct ambiguous decisions across cap4/6/8 for classification...")
    decisions_by_hash = _decisions_for_request_hashes(all_hashes)

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    report: dict = {"per_cap": {}}
    for cap_label, cap_value, hashes in [("cap4", 4, per_cap_hashes["cap4"]), ("cap6", 6, per_cap_hashes["cap6"]), ("cap8", 8, per_cap_hashes["cap8"])]:
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
        os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(cap_value)
        cases = []
        for rh in sorted(hashes):
            d = decisions_by_hash.get(rh)
            if d is None:
                cases.append({"request_hash": rh, "error": "decision not found in re-extraction"})
                continue
            trace = DecisionTrace()
            heuristic_choose_for_request(
                d.request, state=copy.deepcopy(d.state), book=book, our_side=d.side,
                calc=calc, oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=dex, trace=trace,
            )
            classification = _classify_from_trace(trace, d.request)
            decision_id = manifest[rh]["decision_id"]
            cases.append({
                "request_hash": rh, "decision_id": decision_id,
                "primary_cause": classification.primary_cause,
                "label_collision_subtype": classification.label_collision_subtype,
                "companion_flags": sorted(classification.companion_flags),
            })
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
        os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
        report["per_cap"][cap_label] = {"count": len(cases), "cases": cases}
        print(f"{cap_label}: classified {len(cases)} ambiguous cases")

    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass

    # --- overlap by decision_id across caps ---
    ids_by_cap = {
        cap: {c["decision_id"] for c in report["per_cap"][cap]["cases"] if "decision_id" in c}
        for cap in ("cap4", "cap6", "cap8")
    }
    report["overlap"] = {
        "cap4_only": sorted(ids_by_cap["cap4"] - ids_by_cap["cap6"] - ids_by_cap["cap8"]),
        "cap6_only": sorted(ids_by_cap["cap6"] - ids_by_cap["cap4"] - ids_by_cap["cap8"]),
        "cap8_only": sorted(ids_by_cap["cap8"] - ids_by_cap["cap4"] - ids_by_cap["cap6"]),
        "all_three": sorted(ids_by_cap["cap4"] & ids_by_cap["cap6"] & ids_by_cap["cap8"]),
    }

    out_path = OUT_DIR / "ambiguous-candidate-diagnostic.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
```

**Also add `_strip_tera` to `accuracy_cap_derisk.py`'s public surface** if not already (Task 3 defined
it as a private `_strip_tera` helper — either export it or duplicate the one-liner in this script;
prefer exporting since the logic must stay byte-identical to `accuracy_gate_b.py::_strip_tera_suffix`).

- [ ] **Step 2: Run for real**

Run: `PYTHONPATH="$(pwd)/src" python scripts/run_ambiguous_candidate_diagnostic.py`

Expected: classifies every ambiguous case across cap4 (63)/cap6/cap8, writes
`data/eval/accuracy-cap-derisk/ambiguous-candidate-diagnostic.json` with per-cap primary-cause/
companion-flag breakdowns and cross-cap overlap. Report the real `primary_cause` distribution — do
not assume `label_collision` dominates without checking the actual output.

- [ ] **Step 3: Write the fix-feasibility investigation**

By hand, as a markdown section (not generated code) — append to
`data/eval/accuracy-cap-derisk/ambiguous-candidate-diagnostic.md` (create this file). Re-verify (do
not just copy) this plan's "Real API facts" findings on `JointAction`/`SlotAction` field coverage
and `DecisionTrace`'s missing `chosen_joint_action` pointer directly against the current code, then
answer spec §3.2's five questions explicitly:
1. Can `best_ja` be traced directly back to its originating `scored`/`items` entry within the same
   call, without `_label_ja`? (Re-check `decision.py`'s trace-population block, ~line 679-702.)
2. Does that traceability survive K-world/single-world/Depth-2 code paths? (Check whether any of
   these paths deep-copies or reconstructs `JointAction` objects rather than passing the same
   instances through.)
3. Is a canonical structural key stable across accuracy off vs on? (Should be yes by construction —
   `JointAction` doesn't carry any accuracy-mode-dependent field — but verify directly.)
4. Which fields must the key include so switch-target/move-target/Tera variants never collide?
   (Based on this plan's verified `SlotAction` fields: `kind, move_index, target, target_ident` at
   minimum; `terastallize` needs a Tera-aware comparison, not raw inclusion, per the verified
   overlay-timing issue.)
5. Could a future fix generate the chosen candidate's telemetry without raising
   `TOP_K_TRACE_CANDIDATES` globally? (Assess whether resolving via `best_ja` object/key match at
   the SAME point `_label_ja` currently runs — i.e. before/alongside trace population, not as a
   later out-of-band lookup — avoids needing more candidates in the top-K at all, since the
   resolution problem is about IDENTIFYING the chosen one among however many are already there,
   not about needing more of them.)

Present the three variants' verdicts explicitly (object identity: short-lived only; object
equality: solves switch-collision, needs a Tera-aware wrapper; structural key: preferred, needs a
new `DecisionTrace.chosen_joint_action`-style field or an assigned-at-enumeration key) — this is a
report, not a code change to `decision.py`.

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/scripts/run_ambiguous_candidate_diagnostic.py showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py data/eval/accuracy-cap-derisk/ambiguous-candidate-diagnostic.json data/eval/accuracy-cap-derisk/ambiguous-candidate-diagnostic.md
git commit -m "feat(eval): real ambiguous-candidate classification (cap4/6/8) + fix-feasibility investigation"
```

---

## Task 12: Reports, closeout, full test suite, ROADMAP update

**Files:**
- Create: `showdown_bot/scripts/render_cap_derisk_reports.py`
- Create: `data/eval/accuracy-cap-derisk/cap6-report.md`, `cap8-report.md` (rendered)
- Create: `reports/2026-07-13-accuracy-cap-derisk-verdict.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Write the renderer**

Mirrors `render_accuracy_gate_reports.py`'s `build_report_object`/`render_markdown` split — read
that file first for the exact pattern to follow (already read in the accuracy-offline-gate plan's
Task 11). Render `cap6-report.json`/`cap8-report.json` (Task 7) plus `cross-cap-diffs.json` (Task 8)
plus `latency-results.json` (Task 9) into `cap6-report.md`/`cap8-report.md`, each stating: cap-hit
numerator/denominator/rate/verdict; action-changed counts vs cap=4 and vs off (off comparison
explicitly noting the score axis is skipped, action axis is not); latency p50/p95/max for both
trace modes; a note that leaf/event/incomplete distributions are reported against their own real
telemeterable denominator (per spec §2.7), not claimed to cover all 944. No strength/winrate claim
anywhere — mirror `gate-b-report.md`'s own disclaimer convention.

- [ ] **Step 2: Write the closeout report**

`reports/2026-07-13-accuracy-cap-derisk-verdict.md` — mirror
`reports/2026-07-13-accuracy-offline-gate-verdict.md`'s structure exactly, including its boxed
"this report is not allowed to bury" disclaimer pattern, adapted to this study:
- State plainly: cap=4's gate verdict is unchanged (cite `data/eval/accuracy-gate/gate-b-report.json`
  by content hash — 114/881 = 12.9%, FAIL).
- Cap=6/8's real cap-hit rates, verdicts, and whether either clears the 5% threshold — report the
  actual numbers from Task 7, do not pre-guess.
- Cap=6/8's real latency figures from Task 9 and whether they clear the existing 1000ms×5-scaled
  gate the original accuracy-hit-probability slice used (cite
  `reports/2026-07-12-accuracy-slice-latency-gate.md`'s own single-board cap=6/8 FAIL finding as
  prior evidence, and state whether this study's real-corpus numbers agree or disagree).
- The ambiguous-candidate diagnostic's headline finding (primary-cause distribution, overlap across
  caps) and the fix-feasibility investigation's bottom line.
- **Explicitly, prominently: no default-on decision, no strength claim, no Depth-2 Stage 3 work
  follows from this report alone** — same requirement as the parent accuracy-offline-gate report,
  restated here since this is a new, separate report a future reader could encounter on its own.
- Non-contamination confirmation (spec §3.4): no diagnostically-reconstructed telemetry was written
  back into the frozen cap=4 verdict or its artifacts — confirm via `git status --short --
  data/eval/accuracy-gate/` showing no changes across this entire plan's execution.

- [ ] **Step 3: Run the full test suite as the final regression gate**

Run: `cd showdown_bot && PYTHONPATH="$(pwd)/src" python -m pytest tests/ -v`
Expected: PASS, 0 failures, matching or exceeding the merged accuracy-offline-gate plan's
last-known-green count (1705 passed / 1 skipped / 1 xfailed on `main`) plus this plan's new tests.
**Hard gate — do not close out this task until this is genuinely green.**

- [ ] **Step 4: Update `docs/ROADMAP.md`**

Extend the existing P0 item 6 (added when the accuracy-offline-gate FAIL verdict was recorded, see
`docs/ROADMAP.md`) with this study's real results — cap=6/8's actual cap-hit rates/verdicts and
latency findings, and the ambiguous-candidate diagnostic's headline finding. Do not add a new
top-level roadmap item; this is the direct continuation of the existing one. Do not add any new
default-on/strength/Depth-2 item — those remain the user's own separate next steps.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/scripts/render_cap_derisk_reports.py data/eval/accuracy-cap-derisk/cap6-report.md data/eval/accuracy-cap-derisk/cap8-report.md reports/2026-07-13-accuracy-cap-derisk-verdict.md docs/ROADMAP.md
git commit -m "docs(accuracy-cap-derisk): reports, closeout verdict, ROADMAP update"
```

---

## Self-Review

**1. Spec coverage:** §2.1 (corpus/rule reuse) → Task 4-9's shared extraction pattern. §2.2
(decision_id) → Task 1, 4. §2.3 (auxiliary capture, row schema, score-resolution split, two-stage
gate) → Task 3, 5, 6. §2.4 (comparator) → Task 2, 8. §2.5 (cap-hit verdicts) → Task 7. §2.6
(latency) → Task 9. §2.7 (report contents) → Task 12. §3.1 (classification) → Task 10. §3.2
(fix-feasibility) → Task 11. §3.3 (scope: cap4/6/8) → Task 11. §3.4 (non-contamination) → Task 12's
closeout confirmation. §1 (non-goals) → verified nowhere in this plan does any task touch
`decision.py`/`evaluate.py`/`accuracy_gate_b.py`/`accuracy_gate_stats.py`/`accuracy_baseline_diff.py`,
recompute the cap=4 verdict, or implement a fallback-strategy change.

**2. Placeholder scan:** no TBD/TODO/"add appropriate handling" found in the above — every step has
real, complete code or an exact real command with expected real-run behavior described.

**3. Type consistency:** `ActionTableRow`'s fields (Task 3) match `compare_action_tables`'s usage
(Task 2) and every real-run script's construction (Task 5, 6, 8) — same field names throughout.
`decision_id` is computed identically (via `compute_decision_id`) in Task 4 and Task 5, consumed
identically by Task 6/8/11. `DecisionIdComponents`'s 7 fields match spec §2.2's exact schema.

**4. Resolved during this plan's own writing (not left as a placeholder):** confirmed `scripts/` has
no `__init__.py` and `pyproject.toml` scopes pytest to `testpaths = ["tests"]` — so Task 6's
testable logic was placed in `accuracy_cap_derisk.py` (the already-established, already-importable
module) from the start, not deferred to the implementer to discover mid-task.

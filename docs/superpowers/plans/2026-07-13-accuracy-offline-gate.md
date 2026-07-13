# Accuracy Off/On Offline Decision-Diff Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline (no live server) measurement harness that compares the bot's decisions
with `SHOWDOWN_ACCURACY_MODE` off vs on, across a smoke-test board sweep (Gate A) and a real
replayed corpus of past battle logs (Gate B), producing a reviewable PASS/INCONCLUSIVE/FAIL
verdict that gates three later decisions (default-on flip, new strength baseline, Depth-2 Stage 3)
without making any of those decisions itself.

**Architecture:** A private `LineEvaluation`/`_evaluate_line_details()` refactor in
`battle/evaluate.py` that `evaluate_line()` becomes a byte-identical-behavior wrapper around,
exposing per-decision accuracy telemetry (branch/event counts, tie-order-merged cap-hit data)
without adding any new `resolve_turn_branches` calls beyond what already happens today. A new
`eval/room_raw_replay.py` module that extracts real `(state, request)` pairs from committed
`room_raw` protocol logs, deduplicates them at the battle level using each run's own `results.jsonl`
provenance (not room/battle IDs, which are proven not to work here), and feeds the deduplicated
corpus through `heuristic_choose_for_request` off vs on. A small statistics module implementing a
pinned game-clustered bootstrap plus a required zero-event Clopper-Pearson fallback. Two report
scripts (Gate A, Gate B) that apply the spec's pinned acceptance rules and produce a markdown/JSON
report artifact.

**Tech Stack:** Python 3 (this repo's existing `showdown_bot` package), `pytest`, dataclasses,
`hashlib`/`json` for provenance hashing (matching `eval/decision_capture.py`'s established
canonical-JSON-then-sha256 pattern) — no new external dependencies.

---

## Spec

Full design: `docs/superpowers/specs/2026-07-13-accuracy-offline-gate-design.md` (5 correction
rounds; read section references below against the real file, this plan does not restate every
rationale). Prior, already-merged slice this builds on:
`docs/superpowers/plans/2026-07-12-accuracy-hit-probability.md` (merged local main `3fd3b09`).

## Hard sequencing constraint (do not reorder Tasks 1-5)

Spec §7 pins an exact, non-negotiable order: the `room_raw_replay` extraction module *including its
dedup step* must be finished first; the pre-refactor baseline must be frozen from **current,
unmodified** `evaluate_line` **before** any `LineEvaluation`/`_evaluate_line_details` code lands;
that refactor only starts once the baseline artifact is committed. Tasks 1-5 below encode this
order. Do not start Task 5 (the `evaluate.py` refactor) before Task 4 (baseline freeze) is
committed.

## Provenance facts this plan relies on (verified directly against real files, twice — once when
this plan was first written, and again after a real bug was found in the first pass; see the
correction note below)

**Correction (found via direct data verification after the first version of this plan was
written): the manifest join sources below are NOT the top-level `data/eval/t4/t4-{run1,run2,
prefix}.jsonl` files.** Those are the ORIGINAL (buggy, pre-fix) T4 smoke run's manifests
(`seed_base=t4smoke2026`) — they describe a *different* room_raw dump (`C:/tmp/t4/full_room_raw/…`)
than what's actually committed under `data/eval/t4/rerun/room_raw/`. Joining the committed
`.log.gz` files against them matches **0 of 112** t4 files. The committed `room_raw/` files are the
**re-run's** output (the T4 smoke report: *"T4 must be re-run after the fix; this run's data is
committed as evidence, not fixture… After the fix, a full T4 re-run… That run's artifacts become
the T5 fixture"*), whose manifests live at `data/eval/t4/rerun/t4rerun-{run1,run2,prefix}.jsonl`
(`seed_base=t4rerun2026`) — joining against **these** matches **112/112**.

**Second correction, found while re-verifying the first: the dedup identity key must be
`(seed_base, seed_index)`, NOT `(schedule_hash, seed_base, seed_index)`.** `schedule_hash` hashes
the *schedule YAML file's content* — it is not part of battle identity.
`derive_battle_seed(seed_base, seed_index)` (`eval/seeding.py`) is a pure function of those two
fields alone. Directly verified: `t4rerun-prefix.jsonl` carries a *different* `schedule_hash` from
`t4rerun-run1.jsonl` (different YAML file — `t4_smoke_v001_prefix.yaml` vs `t4_smoke_v001.yaml`)
despite sharing `seed_base=t4rerun2026`, yet the actual `seed` **values** at matching `seed_index`
0-9 are byte-identical between `t4rerun-run1.jsonl`, `t4rerun-prefix.jsonl`, and
`kaggle-validation/results.jsonl`. Including `schedule_hash` in the key would treat
`prefix`/`kaggle-validation` as a *third independent* 10-battle group; they are actually duplicates
of `run1`'s own first 10 battles.

**Verified final numbers** (join all 190 regular-directory files — the 197-file corpus minus
`room_raw_divergent`'s 7, which are excluded a-priori, never manifest-joined or content-hashed —
against `data/eval/t4/rerun/t4rerun-{run1,run2,prefix}.jsonl`, `data/eval/t6/t6-run1.jsonl`,
`data/eval/t6/t6-run2.jsonl`, `data/eval/kaggle-validation/results.jsonl`, keyed on `(seed_base,
seed_index)`): **190/190 files match exactly one manifest row; the 190 rows collapse to exactly 85
unique identities** — `t4`'s 51 (`run1`'s own seeds) + `t6`'s 34 (`run1`'s own seeds). `t4`'s
`run2` (51 files) and `prefix` (10 files) are each fully redundant with `run1`'s seeds;
`kaggle-validation` (10 files) is fully redundant with `prefix`'s (= `run1`'s first 10) seeds;
`t6`'s `run2` (34 files) is fully redundant with `t6 run1`'s seeds. **The canonical, deduplicated
Gate B corpus is exactly `data/eval/t4/rerun/room_raw/run1/` (51 files) +
`data/eval/t6/room_raw/run1/` (34 files) = 85 files, G = 85** — everything else in the 197-file
corpus is either a confirmed duplicate (excluded with reason `duplicate_seed_identity`) or
`room_raw_divergent` (excluded with reason `excluded_diagnostic_artifact`). This exact-collapse
result and the resulting `G=85` are also now reflected in
`docs/superpowers/specs/2026-07-13-accuracy-offline-gate-design.md` (round 6) — this plan and the
spec are consistent; do not reintroduce the `schedule_hash`-inclusive key or the wrong manifest
paths from this plan's own first draft.

- `data/eval/t4/rerun/t4rerun-run1.jsonl`, `t4rerun-run2.jsonl`, `t4rerun-prefix.jsonl`,
  `data/eval/t6/t6-run1.jsonl`, `t6-run2.jsonl`, `data/eval/kaggle-validation/results.jsonl` are
  **results manifests**, one JSON row per battle, each row containing `schedule_hash`, `seed_base`,
  `seed_index`, `seed`, `battle_id`, and `room_raw_path` (e.g.
  `"room_raw_path": "C:/tmp/t4/full_room_raw\\HeuristicBot1167__battle-gen9vgc2025regi-310.log"`).
  This is the **single, sufficient join source** — there is no need to cross-reference the separate
  `*-seedlog.jsonl` files (which only carry `{battle_index, seed, seed_base}`, no
  `schedule_hash`/`seed_index`) or the schedule YAMLs directly. `schedule_hash` is read and reported
  (for the dedup report's provenance detail) but is **not** part of the identity/grouping key.
- `room_raw_path`'s basename (final path component, `.log` suffix) matches the on-disk committed
  `.log.gz` filename in `data/eval/t4/rerun/room_raw/run1/` etc. 1:1 (confirmed:
  `HeuristicBot1167__battle-gen9vgc2025regi-310.log` in the manifest row vs
  `HeuristicBot1084__battle-gen9vgc2025regi-487.log.gz` as an on-disk example — same naming
  pattern, differing only by the trailing `.gz`).
- `data/eval/t4/room_raw_divergent/` has **no results.jsonl of its own, and must never be
  manifest-joined or content-hash-deduplicated** — its 7 files (`run1-idx09-regi-319.log.gz`,
  `run2-idx19-regi-401.log.gz`, `prefix-idx09-regi-380.log.gz`, ...) are diagnostic captures of
  specific, already-counted `(seed_base, seed_index)` positions that diverged between `run1`/`run2`
  due to a since-fixed determinism bug — their content is *deliberately* different from their
  source file's, so a content-hash fallback would wrongly admit them as new independent battles and
  inflate `G`. Recognize and exclude them by directory before either the manifest-join or
  content-hash path runs (Task 2).
- `BattleRequest` (`models/request.py:44-55`) has an `rqid: int` field — Showdown's own
  reconnect-detection request ID. Used directly for in-log reconnect-duplicate detection (Task 1).
- `client/gauntlet.py`'s exact causality-relevant chain (`_state_for`, lines 474-483; called from
  `handle_request`, lines 488-494) is:
  ```python
  def _state_for(self, room: str, req: BattleRequest) -> BattleState | None:
      if self.book is None or req.team_preview:
          return None
      try:
          st = BattleState.from_log_text("\n".join(self.room_raw.get(room, [])))
          merge_request(req, st)
          return st
      except Exception as exc:
          logger.warning("[%s] state build failed: %s", self.name, exc)
          return None
  ```
  `self.room_raw[room]` accumulates raw websocket messages in arrival order, and the message
  containing the current `|request|` line is **already appended before** `handle_request` runs —
  so the causality boundary is "every line up to and including the line carrying this request,"
  not "strictly before." `room_raw_replay` (Task 1) mirrors this exactly.
- `eval/room_dump.py`'s `read_room_log_frames(path)` (lines 107-123) returns a **single-element
  list**: `[<entire file content as one string>]`, gzip-aware via `.gz` suffix. The original
  per-message frame boundaries are not recoverable from a committed log — only line boundaries
  (`\n`-separated) are, which is all `room_raw_replay` needs.
- `eval/decision_capture.py`'s established hashing convention (lines ~90-108, reused throughout
  `eval/`): `_canonical_json(payload) = json.dumps(payload, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False)`, `_sha256(payload) = hashlib.sha256(_canonical_json(payload).encode()).hexdigest()`.
  `room_raw_replay` follows this exact pattern for `request_hash`/`log_prefix_hash`.

---

## Task 1: `room_raw_replay` — causality-safe extraction, reconnect dedup, hero side, request classification

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/room_raw_replay.py`
- Create: `showdown_bot/tests/eval/test_room_raw_replay.py`

Implements spec §6 items 1-4.

- [ ] **Step 1: Write the failing tests against real, already-committed data**

The corpus already contains a specific, previously-analyzed log:
`data/eval/t4/room_raw_divergent/prefix-idx09-regi-380.log.gz` — confirmed in the spec's own
investigation to open with a team-preview request and to carry `|player|p1|HeuristicBot3519|...`.
Use it as the TDD anchor.

```python
# showdown_bot/tests/eval/test_room_raw_replay.py
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from showdown_bot.eval.room_raw_replay import (
    ExtractedDecision,
    RequestKind,
    extract_decisions_from_log,
)

REAL_LOG = (
    Path(__file__).resolve().parents[3]
    / "data" / "eval" / "t4" / "room_raw_divergent" / "prefix-idx09-regi-380.log.gz"
)


def _write_log(tmp_path: Path, lines: list[str], *, gzip_it: bool = False) -> Path:
    text = "\n".join(lines)
    if gzip_it:
        path = tmp_path / "synthetic.log.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        path = tmp_path / "synthetic.log"
        path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.skipif(not REAL_LOG.exists(), reason="real corpus log not present in this checkout")
def test_real_log_first_decision_is_team_preview():
    decisions = extract_decisions_from_log(REAL_LOG)
    assert decisions, "expected at least one decision point in the real log"
    first = decisions[0]
    assert first.kind == RequestKind.TEAM_PREVIEW
    assert first.state is None  # matches gauntlet.py's _state_for: team-preview -> no state
    assert first.request.team_preview is True


@pytest.mark.skipif(not REAL_LOG.exists(), reason="real corpus log not present in this checkout")
def test_real_log_hero_side_matches_player_frame():
    decisions = extract_decisions_from_log(REAL_LOG)
    sides = {d.side for d in decisions}
    assert sides == {"p1"}, f"expected every decision to be p1's own requests, got {sides}"


def test_causality_excludes_frames_after_the_request(tmp_path):
    # A minimal synthetic log: turn 1 move request, then turn 2's board-mutating lines,
    # then a turn 2 move request. Extracting turn 1's decision must NOT see turn 2's HP change.
    lines = [
        ">battle-gen9vgc2025regi-1",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
        "|-damage|p2a: Wobbuffet|50/100",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":2}',
        "|turn|2",
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert len(decisions) == 2
    first_prefix = decisions[0].log_prefix_hash
    second_prefix = decisions[1].log_prefix_hash
    assert first_prefix != second_prefix
    # The damage line must only be visible to the SECOND decision's prefix, not the first's.
    assert "-damage" not in "\n".join(lines[:2])  # sanity: line 3 (index 2) carries it
    # first decision's own prefix text must end at/before the first |request| line (index 1)
    assert decisions[0]._debug_prefix_line_count <= 2  # noqa: SLF001 (test-only introspection)


def test_reconnect_duplicate_request_kept_once(tmp_path):
    req_line = (
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":7}'
    )
    lines = [
        ">battle-gen9vgc2025regi-2",
        req_line,
        "|turn|1",
        req_line,  # reconnect resend: identical rqid, identical payload
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert len(decisions) == 1


def test_force_switch_request_classified_separately(tmp_path):
    lines = [
        ">battle-gen9vgc2025regi-3",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
        "|faint|p1a: Wobbuffet",
        '|request|{"forceSwitch":[true],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":2}',
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert [d.kind for d in decisions] == [RequestKind.MOVE, RequestKind.FORCE_SWITCH]


def test_gzip_and_plain_logs_produce_identical_decisions(tmp_path):
    lines = [
        ">battle-gen9vgc2025regi-4",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
    ]
    plain = _write_log(tmp_path, lines, gzip_it=False)
    gz = _write_log(tmp_path, lines, gzip_it=True)
    d_plain = extract_decisions_from_log(plain)
    d_gz = extract_decisions_from_log(gz)
    assert [d.request_hash for d in d_plain] == [d.request_hash for d in d_gz]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_replay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'showdown_bot.eval.room_raw_replay'`

- [ ] **Step 3: Implement `room_raw_replay.py`**

```python
# showdown_bot/src/showdown_bot/eval/room_raw_replay.py
"""Extract real (state, request) decision points from committed room_raw protocol logs.

Mirrors client/gauntlet.py's own BattleState.from_log_text / merge_request /
BattleRequest.model_validate chain exactly -- this module adds no new resolution logic,
only offline replay of what the live client already does per-request.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.eval.room_dump import read_room_log_frames
from showdown_bot.models.request import BattleRequest


class RequestKind(Enum):
    TEAM_PREVIEW = "team_preview"
    FORCE_SWITCH = "force_switch"
    MOVE = "move"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExtractedDecision:
    state: BattleState | None  # None for team-preview requests (matches gauntlet._state_for)
    request: BattleRequest
    kind: RequestKind
    side: str  # "p1" | "p2"
    turn: int  # 0 if no |turn| line has been seen yet (team preview)
    request_hash: str
    log_prefix_hash: str
    _debug_prefix_line_count: int  # test-only introspection, not used by any consumer


def _request_kind(req: BattleRequest) -> RequestKind:
    if req.team_preview:
        return RequestKind.TEAM_PREVIEW
    if req.force_switch and any(req.force_switch):
        return RequestKind.FORCE_SWITCH
    return RequestKind.MOVE


def _hero_side(req: BattleRequest) -> str:
    side_id = (req.side.id or "").strip()
    if side_id in ("p1", "p2"):
        return side_id
    raise ValueError(f"request carries no resolvable side.id: {req.side!r}")


def extract_decisions_from_log(path: str | Path) -> list[ExtractedDecision]:
    frames = read_room_log_frames(path)
    full_text = frames[0] if frames else ""
    lines = full_text.split("\n")

    decisions: list[ExtractedDecision] = []
    seen_rqids: set[int] = set()
    current_turn = 0

    for i, line in enumerate(lines):
        if line.startswith("|turn|"):
            try:
                current_turn = int(line.split("|", 2)[2])
            except (IndexError, ValueError):
                pass
            continue
        if not line.startswith("|request|"):
            continue

        payload = line[len("|request|"):]
        req = BattleRequest.model_validate(json.loads(payload))

        if req.rqid in seen_rqids:
            continue  # reconnect resend of an already-processed request
        seen_rqids.add(req.rqid)

        if req.wait:
            continue  # opponent's turn -- nothing was chosen here, not a decision point

        prefix_lines = lines[: i + 1]  # up to AND including this line -- matches gauntlet.py
        prefix_text = "\n".join(prefix_lines)

        state: BattleState | None = None
        if not req.team_preview:
            state = BattleState.from_log_text(prefix_text)
            merge_request(req, state)

        decisions.append(ExtractedDecision(
            state=state,
            request=req,
            kind=_request_kind(req),
            side=_hero_side(req),
            turn=current_turn,
            request_hash=_sha256(_canonical_json(
                req.model_dump(mode="json", by_alias=True, exclude_none=False)
            )),
            log_prefix_hash=_sha256(prefix_text),
            _debug_prefix_line_count=len(prefix_lines),
        ))

    return decisions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_replay.py -v`
Expected: PASS (7 passed, or 5 passed + 2 skipped if the real log isn't present in this checkout —
it is committed, so expect all 7 to run and pass)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/room_raw_replay.py showdown_bot/tests/eval/test_room_raw_replay.py
git commit -m "feat(eval): room_raw_replay causality-safe decision extraction"
```

---

## Task 2: Global battle-level deduplication

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/room_raw_replay.py`
- Modify: `showdown_bot/tests/eval/test_room_raw_replay.py`
- Create: `showdown_bot/tests/eval/test_room_raw_dedup.py`

Implements spec §6 item 5 — the highest-stakes piece of this plan's non-`battle/` work: a wrong
dedup silently invalidates every downstream statistic (G, the bootstrap, the Clopper-Pearson
bound). **Extra scrutiny on this task's review.** This task's design was itself corrected once
already (see the plan's provenance-facts section above) — the manifest join sources and the
identity key below are the **verified-correct** versions, not the original draft.

Three-part design:
1. **A-priori exclusion, before anything else runs.** Any file under a directory named
   `room_raw_divergent` is excluded outright — never manifest-joined, never content-hashed. Its
   filenames encode already-known run/index references (`run1-idx09`, `run2-idx19`,
   `prefix-idx09`, ...) and its content is *deliberately* divergent from its source (diagnostic
   capture of a determinism-bug-triggered difference), so a content-hash fallback would wrongly
   treat it as new independent content. Excluded with reason `excluded_diagnostic_artifact`.
2. **Primary: manifest join, keyed on `(seed_base, seed_index)` only.** For each remaining
   on-disk `.log.gz`/`.log` file, find the results-manifest row (`t4rerun-run1.jsonl`,
   `t4rerun-run2.jsonl`, `t4rerun-prefix.jsonl`, `t6-run1.jsonl`, `t6-run2.jsonl`,
   `kaggle-validation/results.jsonl`) whose `room_raw_path` basename matches this file's basename
   (stripping `.gz`). That row's `(seed_base, seed_index)` — **not** `schedule_hash`, which is
   YAML-file provenance, not battle identity (verified: `derive_battle_seed(seed_base, seed_index)`
   is a pure function of those two fields alone; `prefix`'s rows carry a different `schedule_hash`
   from `run1`'s despite byte-identical `seed` values at matching indices) — is the file's identity.
   `schedule_hash` is still read and reported per-row for the dedup report's own provenance detail,
   just not used for grouping.
3. **Fallback: content hash**, for files with no matching manifest row at all (should not occur
   for any file outside `room_raw_divergent`, given step 1 already removed the one confirmed
   real case — this path exists as defense-in-depth, not because a real un-joinable file is
   expected). Uses the **normalized room-log content hash**
   (`eval.room_dump.normalized_room_log_sha256`, already used elsewhere in this project for
   exactly this "are these two logs the same battle" question) against every already-kept file's
   own normalized hash.
4. **Fail-closed on ambiguity.** If a file's basename matches manifest rows with **different**
   `(seed_base, seed_index)` identities (should never happen given each manifest's own internal
   consistency, but must not be silently resolved by picking one), raise
   `AmbiguousManifestMatchError` rather than guessing.
5. **Fail-closed content-agreement invariant (added after real-corpus verification found this
   exact fact holds today, but must never be assumed without checking): every file grouped under
   the same `(seed_base, seed_index)` identity must agree on BOTH the full `seed` value (from its
   own manifest row) AND its normalized room-log content hash
   (`eval.room_dump.normalized_room_log_sha256`).** Verified directly against the real, frozen
   190-file corpus before this task was greenlit: it collapses to exactly 85 groups (histogram
   `{2: 75, 4: 10}` — no group of any other size), and every single group's members agree on both
   the seed value and the normalized content hash. This makes `(seed_base, seed_index)` a *verified
   valid* replicate key for *this specific, frozen corpus* — **not** a claim that the key is
   universally sufficient without a content check. If a future corpus addition ever violates this
   (same `(seed_base, seed_index)`, different seed or different normalized content), `
   deduplicate_battle_logs` must **not** silently pick one and discard the rest, and must **not**
   silently accept both as independent — it raises `SeedIdentityConflictError` and refuses to
   proceed.

Within a group of files sharing one identity that passes step 5's invariant check, keep exactly
one — priority order `run1` > `run2` > `prefix` > `kaggle-validation` (source-directory name,
lexicographic tie-break if still ambiguous) — and record the rest as excluded.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/eval/test_room_raw_dedup.py
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from showdown_bot.eval.room_raw_replay import (
    AmbiguousManifestMatchError,
    DedupReport,
    SeedIdentityConflictError,
    deduplicate_battle_logs,
)

REPO_ROOT = Path(__file__).resolve().parents[3].parent  # .../SHowdown BOt
DATA_T4 = REPO_ROOT / "data" / "eval" / "t4"
DATA_T6 = REPO_ROOT / "data" / "eval" / "t6"
DATA_KAGGLE = REPO_ROOT / "data" / "eval" / "kaggle-validation"


def _make_manifest_row(
    room_raw_path: str, schedule_hash: str, seed_base: str, seed_index: int,
    seed: str | None = None,
) -> dict:
    return {
        "room_raw_path": room_raw_path,
        "seed": seed if seed is not None else f"sodium,synthetic-{seed_base}-{seed_index}",
        "schedule_hash": schedule_hash,
        "seed_base": seed_base,
        "seed_index": seed_index,
        "battle_id": f"synthetic-{seed_index}",
    }


def _write_synthetic_log(dirpath: Path, name: str, lines: list[str]) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / f"{name}.log.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def _write_manifest(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_manifest_join_dedups_run1_vs_run2_reproduction(tmp_path):
    battle_lines = [
        ">battle-x-1",
        '|request|{"active":[{"moves":[]}],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
    ]
    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"
    p1 = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-abc-1", battle_lines)
    p2 = _write_synthetic_log(run2_dir, "HeuristicBot2__battle-xyz-2", battle_lines)

    manifest1 = tmp_path / "run1.jsonl"
    manifest2 = tmp_path / "run2.jsonl"
    _write_manifest(manifest1, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-abc-1.log", "SCHEDULE_A", "seedbaseA", 0,
    )])
    _write_manifest(manifest2, [_make_manifest_row(
        "C:/tmp/run2/HeuristicBot2__battle-xyz-2.log", "SCHEDULE_A", "seedbaseA", 0,  # SAME identity
    )])

    report = deduplicate_battle_logs(
        log_files=[p1, p2],
        manifest_files=[manifest1, manifest2],
        keep_priority=["run1", "run2"],
    )
    assert report.files_found == 2
    assert len(report.kept) == 1
    assert report.kept[0] == p1  # run1 wins the priority order
    assert len(report.excluded) == 1
    assert report.excluded[0].reason == "duplicate_seed_identity"
    assert report.final_g == 1


def test_manifest_join_ignores_schedule_hash_and_dedups_prefix_against_run1(tmp_path):
    """The core round-6 regression: two files with DIFFERENT schedule_hash but the SAME
    (seed_base, seed_index) must be recognized as the same battle -- this is exactly the real
    run1-vs-prefix relationship, and a schedule_hash-inclusive key would wrongly miss it."""
    battle_lines = [
        ">battle-p",
        '|request|{"active":[{"moves":[]}],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
    ]
    run1_dir = tmp_path / "run1"
    prefix_dir = tmp_path / "prefix"
    p1 = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-run1-0", battle_lines)
    p2 = _write_synthetic_log(prefix_dir, "HeuristicBot2__battle-prefix-0", battle_lines)

    manifest1 = tmp_path / "run1.jsonl"
    manifest2 = tmp_path / "prefix.jsonl"
    _write_manifest(manifest1, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-run1-0.log", "SCHEDULE_FULL", "sharedbase", 0,
    )])
    _write_manifest(manifest2, [_make_manifest_row(
        "C:/tmp/prefix/HeuristicBot2__battle-prefix-0.log", "SCHEDULE_PREFIX_DIFFERENT_HASH",
        "sharedbase", 0,  # same (seed_base, seed_index), DIFFERENT schedule_hash
    )])

    report = deduplicate_battle_logs(
        log_files=[p1, p2], manifest_files=[manifest1, manifest2], keep_priority=["run1", "prefix"],
    )
    assert report.final_g == 1
    assert report.kept == [p1]
    assert report.excluded[0].reason == "duplicate_seed_identity"


def test_manifest_join_keeps_genuinely_distinct_seeds(tmp_path):
    battle_lines_a = [">battle-a", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    battle_lines_b = [">battle-b", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-a", battle_lines_a)
    p2 = _write_synthetic_log(d, "HeuristicBot2__battle-b", battle_lines_b)
    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [
        _make_manifest_row("C:/tmp/run1/HeuristicBot1__battle-a.log", "SCHED_T4", "t4base", 0),
        _make_manifest_row("C:/tmp/run1/HeuristicBot2__battle-b.log", "SCHED_T6", "t6base", 0),
    ])
    report = deduplicate_battle_logs(log_files=[p1, p2], manifest_files=[manifest], keep_priority=["run1"])
    assert report.final_g == 2
    assert set(report.kept) == {p1, p2}


def test_seed_identity_conflict_fails_closed_on_content_mismatch(tmp_path):
    """The fail-closed hardening: two files share (seed_base, seed_index) per their manifest
    rows AND the same full seed value, but their normalized room-log CONTENT genuinely differs
    (simulating e.g. manifest corruption or a future corpus violating the invariant verified for
    today's frozen 85-group corpus). Must raise, not silently pick one or accept both."""
    lines_a = [">battle-f", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}', "|turn|1"]
    lines_b = [  # same seed/identity claimed, but genuinely different resolved content
        ">battle-f",
        '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
        "|switch|p1a: SomeOtherMon",
    ]
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-f", lines_a)
    p2 = _write_synthetic_log(d, "HeuristicBot2__battle-f2", lines_b)
    manifest = tmp_path / "run1.jsonl"
    same_seed = "sodium,deadbeefdeadbeefdeadbeefdeadbeef"
    _write_manifest(manifest, [
        _make_manifest_row("C:/tmp/run1/HeuristicBot1__battle-f.log", "SCHED_X", "base", 5, seed=same_seed),
        _make_manifest_row("C:/tmp/run1/HeuristicBot2__battle-f2.log", "SCHED_X", "base", 5, seed=same_seed),
    ])
    with pytest.raises(SeedIdentityConflictError):
        deduplicate_battle_logs(log_files=[p1, p2], manifest_files=[manifest], keep_priority=["run1"])


def test_seed_identity_conflict_fails_closed_on_seed_value_mismatch(tmp_path):
    """Same (seed_base, seed_index) but a DIFFERENT full seed value across manifest rows --
    must also fail closed, independent of whether content happens to match."""
    battle_lines = [">battle-g", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-g", battle_lines)
    p2 = _write_synthetic_log(d, "HeuristicBot2__battle-g2", battle_lines)
    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [
        _make_manifest_row("C:/tmp/run1/HeuristicBot1__battle-g.log", "SCHED_X", "base", 9,
                            seed="sodium,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        _make_manifest_row("C:/tmp/run1/HeuristicBot2__battle-g2.log", "SCHED_X", "base", 9,
                            seed="sodium,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),  # different seed
    ])
    with pytest.raises(SeedIdentityConflictError):
        deduplicate_battle_logs(log_files=[p1, p2], manifest_files=[manifest], keep_priority=["run1"])


@pytest.mark.skipif(
    not (DATA_T4 / "rerun" / "t4rerun-run1.jsonl").exists(),
    reason="real t4/t6/kaggle-validation corpus not present",
)
def test_real_corpus_satisfies_seed_identity_invariant_for_all_85_groups():
    """Confirms, against the REAL frozen corpus, the exact fact the user verified independently
    before authorizing this task: 85 groups, sizes {2: 75, 4: 10}, zero seed mismatches, zero
    normalized-content-hash mismatches. This documents (seed_base, seed_index) as a VERIFIED
    valid replicate key for THIS corpus specifically -- deduplicate_battle_logs itself enforces
    this on every run (it would have raised SeedIdentityConflictError here if it didn't hold), so
    this test's job is to prove the real corpus runs through cleanly, not to re-derive the check."""
    import glob
    from collections import Counter

    regular_log_files = [
        Path(p) for p in glob.glob(str(DATA_T4 / "rerun" / "room_raw" / "**" / "*.log.gz"), recursive=True)
    ]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_T6 / "room_raw" / "**" / "*.log.gz"), recursive=True)]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_KAGGLE / "room_raw" / "*.log.gz"))]
    manifests = [
        DATA_T4 / "rerun" / "t4rerun-run1.jsonl", DATA_T4 / "rerun" / "t4rerun-run2.jsonl",
        DATA_T4 / "rerun" / "t4rerun-prefix.jsonl",
        DATA_T6 / "t6-run1.jsonl", DATA_T6 / "t6-run2.jsonl", DATA_KAGGLE / "results.jsonl",
    ]
    # No SeedIdentityConflictError means the invariant held for every one of the 85 groups --
    # that IS the assertion; a raised exception fails this test automatically.
    report = deduplicate_battle_logs(
        log_files=regular_log_files, manifest_files=manifests,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    assert report.final_g == 85
    group_sizes = Counter()
    # Reconstruct group sizes from files_found vs excluded reasons, matching the user's own
    # independently-verified histogram {2: 75, 4: 10} (85 groups, 190 files, no other size).
    dup_count_by_winner = Counter(e.duplicate_of for e in report.excluded if e.reason == "duplicate_seed_identity")
    for winner in report.kept:
        group_sizes[dup_count_by_winner.get(winner, 0) + 1] += 1
    assert dict(group_sizes) == {2: 75, 4: 10}, (
        f"expected the verified {{2: 75, 4: 10}} group-size histogram; got {dict(group_sizes)} -- "
        f"if the corpus genuinely changed, re-verify the invariant manually before touching this "
        f"assertion, don't just widen it"
    )


def test_room_raw_divergent_excluded_a_priori_never_content_hash_admitted(tmp_path):
    """Round-5/6 requirement: files under a `room_raw_divergent` directory must be excluded
    outright, even when their content genuinely differs from any kept file's (they were
    deliberately preserved AS evidence of divergence -- admitting them via content-hash
    mismatch would wrongly inflate G)."""
    kept_lines = [">battle-d", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    divergent_lines = [  # deliberately DIFFERENT content -- a divergent-outcome capture
        ">battle-d",
        '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
        "|switch|p1a: SomethingElse",
    ]
    run1_dir = tmp_path / "run1"
    divergent_dir = tmp_path / "room_raw_divergent"
    kept = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-d", kept_lines)
    divergent = _write_synthetic_log(divergent_dir, "run1-idx00-battle-d", divergent_lines)

    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-d.log", "SCHED_T4", "t4base", 0,
    )])

    report = deduplicate_battle_logs(
        log_files=[kept, divergent], manifest_files=[manifest], keep_priority=["run1"],
    )
    assert report.final_g == 1
    assert report.kept == [kept]
    assert report.excluded[0].source_file == divergent
    assert report.excluded[0].reason == "excluded_diagnostic_artifact"


def test_ambiguous_manifest_match_fails_closed(tmp_path):
    battle_lines = [">battle-e", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-e", battle_lines)
    manifest_a = tmp_path / "a.jsonl"
    manifest_b = tmp_path / "b.jsonl"
    # Two manifests disagreeing about the SAME file's identity -- must never be silently resolved.
    _write_manifest(manifest_a, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-e.log", "SCHED_X", "baseX", 0,
    )])
    _write_manifest(manifest_b, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-e.log", "SCHED_Y", "baseY", 7,  # different (seed_base, seed_index)
    )])
    with pytest.raises(AmbiguousManifestMatchError):
        deduplicate_battle_logs(
            log_files=[p1], manifest_files=[manifest_a, manifest_b], keep_priority=["run1"],
        )


@pytest.mark.skipif(
    not (DATA_T4 / "rerun" / "t4rerun-run1.jsonl").exists(),
    reason="real t4/t6/kaggle-validation corpus not present",
)
def test_real_corpus_dedup_collapses_190_regular_files_to_85():
    """Integration check against the REAL committed corpus, per spec §7's
    test_global_dedup_uses_seed_schedule_not_room_id -- the 197-files-to-85-unique-battles ratio
    is itself a load-bearing claim this gate's credibility depends on, so this must run against
    real data, not only synthetic fixtures. G=85 is VERIFIED (not an estimate) -- see this plan's
    provenance-facts section for the exact join performed to arrive at it."""
    import glob

    regular_log_files = [
        Path(p) for p in glob.glob(str(DATA_T4 / "rerun" / "room_raw" / "**" / "*.log.gz"), recursive=True)
    ]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_T6 / "room_raw" / "**" / "*.log.gz"), recursive=True)]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_KAGGLE / "room_raw" / "*.log.gz"))]
    divergent_log_files = [Path(p) for p in glob.glob(str(DATA_T4 / "room_raw_divergent" / "*.log.gz"))]

    assert len(regular_log_files) == 190, (
        f"expected 190 regular-directory files (t4 run1+run2+prefix=112, t6 run1+run2=68, "
        f"kaggle-validation=10); got {len(regular_log_files)} -- the corpus itself changed, "
        f"re-derive every downstream number in this plan and the spec before proceeding"
    )
    assert len(divergent_log_files) == 7

    manifests = [
        DATA_T4 / "rerun" / "t4rerun-run1.jsonl", DATA_T4 / "rerun" / "t4rerun-run2.jsonl",
        DATA_T4 / "rerun" / "t4rerun-prefix.jsonl",
        DATA_T6 / "t6-run1.jsonl", DATA_T6 / "t6-run2.jsonl", DATA_KAGGLE / "results.jsonl",
    ]
    all_log_files = regular_log_files + divergent_log_files
    report = deduplicate_battle_logs(
        log_files=all_log_files, manifest_files=manifests,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    assert report.files_found == 197

    # Every regular-directory file must resolve to exactly one manifest match -- none may
    # silently fall through to the content-hash fallback (that path is defense-in-depth only;
    # a real fallback hit here would mean a manifest/on-disk mismatch worth investigating).
    fallback_reasons = {e.source_file: e.reason for e in report.excluded}
    for f in regular_log_files:
        assert fallback_reasons.get(f) != "duplicate_content_hash", (
            f"{f} silently fell through to content-hash dedup instead of matching a manifest row"
        )

    # room_raw_divergent's 7 files must be excluded with their own dedicated reason, never
    # counted toward kept/G, regardless of content.
    divergent_excluded = {e.source_file: e.reason for e in report.excluded if e.source_file in divergent_log_files}
    assert len(divergent_excluded) == 7
    assert all(r == "excluded_diagnostic_artifact" for r in divergent_excluded.values())

    # The verified number: 190 regular files -> exactly 85 unique (seed_base, seed_index)
    # identities. Do not loosen this to a range if it fails -- it is a directly re-derivable,
    # exact fact (see the provenance-facts section), not an estimate.
    assert report.final_g == 85, (
        f"expected the VERIFIED G=85 (t4's 51 unique seeds + t6's 34); got {report.final_g} -- "
        f"if the corpus genuinely changed since this plan was written, re-run the provenance "
        f"verification in the plan's own provenance-facts section and update every downstream "
        f"number (this test, Task 4/9/11, and the spec's §1/§4/§6) together, don't just widen this"
    )
    unique_identities = {(i.seed_base, i.seed_index) for i in report.kept_identities}
    assert len(unique_identities) == 85
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_dedup.py -v`
Expected: FAIL with `ImportError: cannot import name 'DedupReport'`

- [ ] **Step 3: Implement the dedup logic**

Add to `showdown_bot/src/showdown_bot/eval/room_raw_replay.py`:

```python
class AmbiguousManifestMatchError(Exception):
    """Raised when a file's basename matches manifest rows with conflicting identities --
    fail closed rather than silently picking one (spec §6 item 5's fail-closed requirement)."""


class SeedIdentityConflictError(Exception):
    """Raised when files sharing a (seed_base, seed_index) manifest identity do NOT agree on
    the full seed value or normalized room-log content. (seed_base, seed_index) is a verified
    valid replicate key for the specific, frozen corpus this module was built against (85
    groups, sizes {2, 4}, zero conflicts -- checked directly) -- it is NOT assumed universally
    sufficient without this content-agreement check for any future/different corpus."""


@dataclass(frozen=True)
class SeedIdentity:
    seed_base: str
    seed_index: int
    schedule_hash: str  # provenance detail only -- NOT part of equality/grouping
    seed: str           # the full seed value -- used ONLY for the fail-closed invariant check
    # below, NOT part of equality/grouping either (grouping is (seed_base, seed_index) alone;
    # `seed` and `schedule_hash` are verified to AGREE within a group, not used to form it).

    def __hash__(self) -> int:
        return hash((self.seed_base, self.seed_index))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SeedIdentity):
            return NotImplemented
        return (self.seed_base, self.seed_index) == (other.seed_base, other.seed_index)


@dataclass(frozen=True)
class ExcludedBattle:
    source_file: Path
    reason: str  # "duplicate_seed_identity" | "duplicate_content_hash" | "excluded_diagnostic_artifact"
    duplicate_of: Path | None  # None for excluded_diagnostic_artifact (excluded a-priori, not vs. a specific file)


@dataclass(frozen=True)
class DedupReport:
    files_found: int
    kept: list[Path]
    kept_identities: list[SeedIdentity]  # parallel-ish, only for files with a manifest match
    excluded: list[ExcludedBattle]
    final_g: int


_DIVERGENT_DIR_NAME = "room_raw_divergent"


def _is_diagnostic_artifact(path: Path) -> bool:
    return any(part == _DIVERGENT_DIR_NAME for part in path.parts)


def _load_manifest_rows(manifest_files: list[Path]) -> dict[str, SeedIdentity]:
    """basename (with .log, no .gz) -> SeedIdentity, across all given manifest files.
    Fails closed (AmbiguousManifestMatchError) if two manifests disagree about one file's
    (seed_base, seed_index) identity."""
    by_basename: dict[str, SeedIdentity] = {}
    for manifest_path in manifest_files:
        if not manifest_path.exists():
            continue
        with open(manifest_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                raw_path = row["room_raw_path"].replace("\\", "/")
                basename = raw_path.rsplit("/", 1)[-1]
                identity = SeedIdentity(
                    seed_base=row["seed_base"], seed_index=row["seed_index"],
                    schedule_hash=row["schedule_hash"], seed=row["seed"],
                )
                existing = by_basename.get(basename)
                if existing is not None and (existing.seed_base, existing.seed_index) != (
                    identity.seed_base, identity.seed_index,
                ):
                    raise AmbiguousManifestMatchError(
                        f"{basename} matches conflicting identities: "
                        f"{(existing.seed_base, existing.seed_index)} vs "
                        f"{(identity.seed_base, identity.seed_index)}"
                    )
                by_basename[basename] = identity
    return by_basename


def _content_hash(path: Path) -> str:
    from showdown_bot.eval.room_dump import normalized_room_log_sha256
    frames = read_room_log_frames(path)
    return normalized_room_log_sha256(frames)


def _source_priority(path: Path, keep_priority: list[str]) -> int:
    parts = {p.lower() for p in path.parts}
    for rank, name in enumerate(keep_priority):
        if name.lower() in parts:
            return rank
    return len(keep_priority)  # unknown source -- lowest priority


def _verify_seed_identity_invariant(
    key: tuple[str, int], entries: list[tuple[Path, SeedIdentity]],
    content_hash_cache: dict[Path, str],
) -> None:
    """Fail-closed check: every file claiming this (seed_base, seed_index) identity must agree
    on BOTH the full seed value AND the normalized room-log content hash. Verified to hold for
    every one of the real corpus's 85 groups before this check was added -- this function is
    what ENFORCES that fact stays true on every future run, rather than trusting it silently."""
    seeds = {identity.seed for _p, identity in entries}
    if len(seeds) > 1:
        raise SeedIdentityConflictError(
            f"{key}: files claim the same (seed_base, seed_index) but disagree on the full "
            f"seed value: {sorted((str(p), i.seed) for p, i in entries)}"
        )
    hashes: dict[Path, str] = {}
    for path, _identity in entries:
        if path not in content_hash_cache:
            content_hash_cache[path] = _content_hash(path)
        hashes[path] = content_hash_cache[path]
    if len(set(hashes.values())) > 1:
        raise SeedIdentityConflictError(
            f"{key}: files share (seed_base, seed_index) and seed value, but normalized room-log "
            f"content differs -- refusing to treat them as duplicates: "
            f"{sorted((str(p), h) for p, h in hashes.items())}"
        )


def deduplicate_battle_logs(
    *, log_files: list[Path], manifest_files: list[Path], keep_priority: list[str],
) -> DedupReport:
    manifest_by_basename = _load_manifest_rows(manifest_files)

    # Step 0: a-priori exclusion, before either matching path runs.
    diagnostic_files = [p for p in log_files if _is_diagnostic_artifact(p)]
    remaining_files = [p for p in log_files if not _is_diagnostic_artifact(p)]
    excluded: list[ExcludedBattle] = [
        ExcludedBattle(p, "excluded_diagnostic_artifact", None) for p in diagnostic_files
    ]

    # Step 1: manifest join, grouped on the RAW (seed_base, seed_index) tuple -- each file's
    # OWN full SeedIdentity (with its own seed/schedule_hash) is kept alongside it, not
    # collapsed into whichever identity object happened to be inserted first, so the fail-closed
    # invariant check below can see every member's real seed/content, not just one.
    groups: dict[tuple[str, int], list[tuple[Path, SeedIdentity]]] = {}
    unmatched: list[Path] = []
    for path in remaining_files:
        basename = path.name
        if basename.endswith(".gz"):
            basename = basename[: -len(".gz")]
        identity = manifest_by_basename.get(basename)
        if identity is None:
            unmatched.append(path)
        else:
            key = (identity.seed_base, identity.seed_index)
            groups.setdefault(key, []).append((path, identity))

    kept: list[Path] = []
    kept_identities: list[SeedIdentity] = []
    content_hash_cache: dict[Path, str] = {}

    for key, entries in groups.items():
        _verify_seed_identity_invariant(key, entries, content_hash_cache)
        paths_sorted = sorted(
            (p for p, _i in entries), key=lambda p: (_source_priority(p, keep_priority), str(p))
        )
        winner = paths_sorted[0]
        winner_identity = next(i for p, i in entries if p == winner)
        kept.append(winner)
        kept_identities.append(winner_identity)
        for loser in paths_sorted[1:]:
            excluded.append(ExcludedBattle(loser, "duplicate_seed_identity", winner))

    # Step 2: content-hash fallback, defense-in-depth for files with no manifest row at all.
    # Reuses content_hash_cache where the invariant check above already computed a kept file's
    # hash, avoiding a redundant re-read.
    hash_to_kept: dict[str, Path] = {}
    for k in kept:
        if k not in content_hash_cache:
            content_hash_cache[k] = _content_hash(k)
        hash_to_kept[content_hash_cache[k]] = k

    unmatched_sorted = sorted(unmatched, key=lambda p: (_source_priority(p, keep_priority), str(p)))
    for path in unmatched_sorted:
        h = _content_hash(path)
        if h in hash_to_kept:
            excluded.append(ExcludedBattle(path, "duplicate_content_hash", hash_to_kept[h]))
            continue
        hash_to_kept[h] = path
        kept.append(path)

    return DedupReport(
        files_found=len(log_files),
        kept=kept,
        kept_identities=kept_identities,
        excluded=excluded,
        final_g=len(kept),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_dedup.py -v`
Expected: PASS (9 passed; the two real-corpus tests only skip if the committed manifests are
somehow absent from the checkout, which they are not). Both
`test_real_corpus_dedup_collapses_190_regular_files_to_85` and
`test_real_corpus_satisfies_seed_identity_invariant_for_all_85_groups` assert **exact** facts
(`report.final_g == 85`, group-size histogram `{2: 75, 4: 10}`) — verified directly against the
real corpus both when this plan was written and independently re-verified before this task was
authorized, not estimates; **do not loosen either to a range if they fail** — investigate whether
the dedup logic has a bug, don't paper over it.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/room_raw_replay.py showdown_bot/tests/eval/test_room_raw_dedup.py
git commit -m "feat(eval): global battle-level dedup via (seed_base, seed_index) identity + fail-closed content-agreement invariant"
```

---

## Task 3: Hermetic edge-case fixtures for `room_raw_replay`

**Files:**
- Modify: `showdown_bot/tests/eval/test_room_raw_replay.py`

Implements spec §6 item 9 — small hand-built fixtures beyond the one real log and Task 1/2's own
synthetic cases, specifically for the causality-boundary-detectability case the spec calls out as
"the requirement most likely to be silently gotten wrong."

- [ ] **Step 1: Write the failing test**

Add to `showdown_bot/tests/eval/test_room_raw_replay.py`:

```python
def test_causality_boundary_wrong_by_one_line_is_detectable(tmp_path):
    """A fixture specifically constructed so that reading ONE frame too many produces an
    OBSERVABLY different, wrong state -- not a state that happens to look the same either way.
    A KO strictly AFTER the first request must not be visible when building that request's state."""
    lines = [
        ">battle-gen9vgc2025regi-9",
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":['
        '{"ident":"p2a: Wobbuffet","condition":"100/100","active":false}]},"rqid":1}',
        "|turn|1",
        "|faint|p2a: Wobbuffet",  # this KO must be invisible to decision 0's state
        '|request|{"active":[{"moves":[{"move":"Tackle","id":"tackle"}]}],'
        '"side":{"name":"Hero","id":"p1","pokemon":['
        '{"ident":"p2a: Wobbuffet","condition":"0 fnt","active":false}]},"rqid":2}',
    ]
    path = _write_log(tmp_path, lines)
    decisions = extract_decisions_from_log(path)
    assert len(decisions) == 2
    # decision 0's prefix text must end at-or-before line index 1 (the first |request| line);
    # the |faint| line is at index 3, strictly after -- asserting the line count catches an
    # off-by-one boundary bug that a same-looking-either-way fixture would miss.
    assert decisions[0]._debug_prefix_line_count == 2
    assert decisions[1]._debug_prefix_line_count == 5


def test_hermetic_fixtures_do_not_require_the_real_log():
    """Sanity check that Task 1/2/3's synthetic-fixture tests collectively exercise every
    §6 requirement (causality, reconnect dedup, force-switch classification, dedup) without
    depending on the real on-disk corpus -- so this module's core correctness is provable even
    in a checkout that doesn't have data/eval/ committed."""
    import inspect

    from showdown_bot.eval import room_raw_replay as module

    assert hasattr(module, "extract_decisions_from_log")
    assert hasattr(module, "deduplicate_battle_logs")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_replay.py::test_causality_boundary_wrong_by_one_line_is_detectable -v`
Expected: FAIL if `_debug_prefix_line_count` doesn't match (would indicate the off-by-one boundary
bug the fixture is designed to catch) — otherwise verify it PASSES against the Task 1
implementation, since Task 1 already implements the correct "up to and including" boundary. If it
fails here, fix `extract_decisions_from_log`'s prefix-line slicing in Task 1's file, not this test.

- [ ] **Step 3: Run to verify it passes**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_replay.py -v`
Expected: PASS (all tests in this file green)

- [ ] **Step 4: Commit**

```bash
git add showdown_bot/tests/eval/test_room_raw_replay.py
git commit -m "test(eval): hermetic causality-boundary fixture for room_raw_replay"
```

---

## Task 4: Pre-refactor baseline freeze (hard checkpoint)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/accuracy_baseline.py`
- Create: `showdown_bot/tests/eval/test_accuracy_baseline.py`
- Create (generated by running the script, then committed): `data/eval/accuracy-gate/pre-refactor-baseline.jsonl`

Implements spec §7's hard checkpoint. **This task must run against the current, unmodified
`evaluate_line`/`heuristic_choose_for_request` — do not start Task 5 (the `LineEvaluation` refactor)
until this task's artifact is committed.**

Before writing code, read `showdown_bot/src/showdown_bot/battle/decision.py`'s
`heuristic_choose_for_request` entry point (or the actual current top-level decision function name
— confirm it in the current source; the accuracy-hit-probability plan's Task 5/9 already exercised
it under `SHOWDOWN_ACCURACY_MODE`, follow that same call pattern) to get its exact signature before
writing Step 3's driver code below.

- [ ] **Step 1: Write the failing test**

```python
# showdown_bot/tests/eval/test_accuracy_baseline.py
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.eval.accuracy_baseline import BaselineRow, canonical_float, freeze_baseline


def test_canonical_float_representation_is_stable():
    assert canonical_float(1.0) == canonical_float(1.00000000)
    assert canonical_float(0.1 + 0.2) == canonical_float(0.3)  # rounds away fp noise
    assert isinstance(canonical_float(1.5), str)


def test_freeze_baseline_produces_one_row_per_decision(tmp_path, monkeypatch):
    # A minimal fake corpus of 2 ExtractedDecision-shaped inputs, using a stub chooser so this
    # test doesn't require the real calc backend -- freeze_baseline's job is the FILE FORMAT and
    # provenance capture, not re-testing heuristic_choose_for_request itself.
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    calls = []

    def fake_choose(decision, *, accuracy_mode):
        calls.append((decision, accuracy_mode))
        return f"move 1", 0.42

    decisions = [
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=1,
            request_hash="reqhash0", log_prefix_hash="prefixhash0", _debug_prefix_line_count=1,
        ),
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=2,
            request_hash="reqhash1", log_prefix_hash="prefixhash1", _debug_prefix_line_count=1,
        ),
    ]

    out_path = tmp_path / "baseline.jsonl"
    rows = freeze_baseline(
        decisions, out_path=out_path, chooser=fake_choose,
        source_commit="deadbeef", config_hash="cafef00d",
        python_version="3.11.0", dependency_lock_hash="lockhash123",
    )
    assert len(rows) == 2
    assert [c[1] for c in calls] == [False, False]  # accuracy_mode explicitly off, every call

    with open(out_path, "r", encoding="utf-8") as fh:
        written = [json.loads(line) for line in fh]
    assert len(written) == 2
    for row in written:
        assert row["source_commit"] == "deadbeef"
        assert row["config_hash"] == "cafef00d"
        assert row["python_version"] == "3.11.0"
        assert row["dependency_lock_hash"] == "lockhash123"
        assert row["accuracy_mode"] is False
        assert isinstance(row["score"], str)  # canonical float, not a raw Python float
        assert "request_hash" in row and "log_prefix_hash" in row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_baseline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'showdown_bot.eval.accuracy_baseline'`

- [ ] **Step 3: Implement `accuracy_baseline.py`**

```python
# showdown_bot/src/showdown_bot/eval/accuracy_baseline.py
"""Freeze a pre-refactor baseline of chosen actions/scores over the deduplicated corpus,
in SHOWDOWN_ACCURACY_MODE=off, BEFORE the LineEvaluation/_evaluate_line_details refactor lands.

This artifact is a hard checkpoint (spec Sec.7): once committed, never regenerated. A later
diff against it is the true refactor-regression check -- unset-vs-explicit-off alone cannot
catch a bug in a wrapper that both paths route through post-refactor.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from showdown_bot.eval.room_raw_replay import ExtractedDecision


def canonical_float(value: float, *, ndigits: int = 10) -> str:
    """Fixed serialization so a harmless formatting/precision difference can never be
    misread as a scoring regression when diffing against this frozen baseline."""
    return f"{round(value, ndigits):.{ndigits}f}"


@dataclass(frozen=True)
class BaselineRow:
    request_hash: str
    log_prefix_hash: str
    side: str
    turn: int
    chosen_action: str
    score: str  # canonical_float output
    accuracy_mode: bool
    source_commit: str
    config_hash: str
    python_version: str
    dependency_lock_hash: str


ChooserFn = Callable[[ExtractedDecision], tuple[str, float]]


def freeze_baseline(
    decisions: Sequence[ExtractedDecision],
    *,
    out_path: str | Path,
    chooser: Callable[[ExtractedDecision], tuple[str, float]] | Callable[..., tuple[str, float]],
    source_commit: str,
    config_hash: str,
    python_version: str,
    dependency_lock_hash: str,
) -> list[BaselineRow]:
    rows: list[BaselineRow] = []
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        for decision in decisions:
            chosen_action, score = chooser(decision, accuracy_mode=False)
            row = BaselineRow(
                request_hash=decision.request_hash,
                log_prefix_hash=decision.log_prefix_hash,
                side=decision.side,
                turn=decision.turn,
                chosen_action=chosen_action,
                score=canonical_float(score),
                accuracy_mode=False,
                source_commit=source_commit,
                config_hash=config_hash,
                python_version=python_version,
                dependency_lock_hash=dependency_lock_hash,
            )
            rows.append(row)
            fh.write(json.dumps(asdict(row), sort_keys=True) + "\n")
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_baseline.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Write and run the real driver script against the full deduplicated corpus**

Create `showdown_bot/scripts/run_accuracy_baseline_freeze.py` (or the project's established
location for one-off eval driver scripts — check `showdown_bot/scripts/` or `cli.py`'s subcommand
pattern for the convention before placing this; match it). The script must:

1. Glob every `.log.gz` under `data/eval/t4/rerun/room_raw/`, `data/eval/t4/room_raw_divergent/`,
   `data/eval/t6/room_raw/`, `data/eval/kaggle-validation/room_raw/`.
2. Call `deduplicate_battle_logs(...)` (Task 2) with the manifest files
   `data/eval/t4/rerun/t4rerun-run1.jsonl`, `t4rerun-run2.jsonl`, `t4rerun-prefix.jsonl`,
   `data/eval/t6/t6-run1.jsonl`, `t6-run2.jsonl`, `data/eval/kaggle-validation/results.jsonl` (this
   plan's provenance-facts section — **not** the top-level `data/eval/t4/t4-run1.jsonl`-shaped
   files, which are a different, superseded run) and `keep_priority=["run1", "run2", "prefix",
   "kaggle-validation"]`.
3. For every kept file, call `extract_decisions_from_log(...)` (Task 1) and filter to
   `RequestKind.MOVE` only (team-preview/force-switch decisions have no move-accuracy content —
   spec §6 item 4 — exclude them from the primary baseline sample, but report their counts).
4. Run a 50-decision timed dry-run first and print the extrapolated full-corpus runtime estimate.
   **This dry-run is for runtime estimation only** — per spec §6 item 6, Gate B's confirmatory run
   (Task 10) always uses the full deduplicated corpus; if it turns out infeasible there, the
   result is `INCONCLUSIVE / BLOCKED FOR COMPUTE`, not a silent fallback sample. This baseline
   freeze follows the identical rule: freeze the full deduplicated corpus, or don't proceed.
5. Call `freeze_baseline(...)` with `chooser` wired to the current, **unmodified**
   `heuristic_choose_for_request` (read its real signature in `battle/decision.py` before wiring
   this — do not guess it), `source_commit` from `git rev-parse HEAD`, `config_hash` from this
   project's existing `build_config_manifest`/`config_hash` computation in `eval/config_env.py`
   (reuse it, don't reinvent), `python_version` from `sys.version`, and `dependency_lock_hash` from
   a sha256 of the project's lock file (`pyproject.toml`'s pinned deps or `requirements*.txt`,
   whichever this project actually uses — check before writing).
6. Write output to `data/eval/accuracy-gate/pre-refactor-baseline.jsonl` and a sibling
   `dedup-report.json` (from `DedupReport`: files found, unique battles kept, excluded
   duplicates/partial-copies with reasons, final G — spec §6 item 5's required separate reporting).

Run it for real:

```bash
cd showdown_bot && python scripts/run_accuracy_baseline_freeze.py
```

Expected: completes without exceptions, `data/eval/accuracy-gate/pre-refactor-baseline.jsonl` has
one row per non-team-preview/non-force-switch decision in the deduplicated corpus (canonically
`data/eval/t4/rerun/room_raw/run1/` (51 files) + `data/eval/t6/room_raw/run1/` (34 files) = 85
files — everything else in the 197-file corpus is a confirmed duplicate or the excluded
`room_raw_divergent` set), `dedup-report.json`'s `final_g` is exactly `85` (matching Task 2's
real-corpus test — verified, not a range) unless the corpus itself changed since this plan was
written, in which case stop and re-derive every downstream number, don't silently proceed.

- [ ] **Step 6: Commit — this is the hard checkpoint, never regenerate after this**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_baseline.py \
        showdown_bot/tests/eval/test_accuracy_baseline.py \
        showdown_bot/scripts/run_accuracy_baseline_freeze.py \
        data/eval/accuracy-gate/pre-refactor-baseline.jsonl \
        data/eval/accuracy-gate/dedup-report.json
git commit -m "feat(eval): freeze pre-refactor accuracy-off baseline over full deduplicated corpus (hard checkpoint, never regenerate)"
```

**Do not proceed to Task 5 in the same commit or before this one is committed.**

---

## Task 5: `LineEvaluation`/`_evaluate_line_details` refactor (HIGH RISK — extra scrutiny)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/evaluate.py`
- Modify: `showdown_bot/tests/battle/test_evaluate.py` (or the project's actual existing test file
  for `evaluate.py` — confirm its real path before writing; the merged accuracy slice's Task 5
  established this file, reuse it)

Implements spec §2.1-2.3. Same risk class as the original accuracy slice's Task 4/5 — this touches
the score-producing core of every live decision. **Two-stage review (spec compliance, then code
quality) is required, do not compress this task's review.**

Read `showdown_bot/src/showdown_bot/battle/evaluate.py` fully before starting (already read this
session — `evaluate_line`, `_one`, `_has_genuine_tie`, `score_outcome`, `AccuracyDiagnostics` are at
their spec-cited line numbers as of this session; re-verify, since Tasks 1-4 do not touch this
file and should not have shifted them, but confirm before editing).

- [ ] **Step 1: Write the failing tests**

```python
# added to the evaluate.py test file
import dataclasses

from showdown_bot.battle.evaluate import (
    AccuracyEventDetail,
    LineEvaluation,
    TieOrderEvaluation,
    _accuracy_events_from_leaves,
    _evaluate_line_details,
    evaluate_line,
)
from showdown_bot.battle.resolve import PlannedAction, TurnOutcome, resolve_turn_branches


def test_evaluate_line_wraps_evaluate_line_details_off_path(basic_state, basic_damage_fn):
    # off-path: byte-identical to today's evaluate_line -- construct with accuracy_mode=False
    # and assert the wrapper's (score, outcome) equals a direct resolve_turn-based expectation.
    score, outcome = evaluate_line(
        basic_state, [], [], basic_damage_fn, our_side="p1", accuracy_mode=False,
    )
    detail = _evaluate_line_details(
        basic_state, [], [], basic_damage_fn, our_side="p1", accuracy_mode=False,
    )
    assert (score, outcome) == (detail.score, detail.representative_outcome)
    assert detail.leaves is None
    assert detail.fork_records is None
    assert detail.fallback_leaves == 0
    assert detail.accuracy_events == []


def test_evaluate_line_details_repeat_call_identical(scripted_accuracy_state):
    kwargs = dict(
        state=scripted_accuracy_state.state,
        my_actions=scripted_accuracy_state.my_actions,
        opp_actions=scripted_accuracy_state.opp_actions,
        damage_fn=scripted_accuracy_state.damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
    )
    d1 = _evaluate_line_details(**kwargs)
    d2 = _evaluate_line_details(**kwargs)
    assert d1.score == d2.score
    assert d1.fallback_leaves == d2.fallback_leaves
    assert [dataclasses.astuple(e) for e in d1.accuracy_events] == \
           [dataclasses.astuple(e) for e in d2.accuracy_events]
    assert [dataclasses.astuple(t) for t in d1.tie_order_details] == \
           [dataclasses.astuple(t) for t in d2.tie_order_details]


def test_accuracy_events_use_full_leaf_union_not_leaves_zero_only(ko_dependent_accuracy_state):
    """Regression test for the round-3 discovery bug: an event only attempted in a miss-branch
    must still appear in accuracy_events, even though it's absent from leaves[0]'s attempted_hits.
    Mirrors the merged slice's Task 4 KO-dependent regression test shape."""
    state, actions, damage_fn = (
        ko_dependent_accuracy_state.state,
        ko_dependent_accuracy_state.actions,
        ko_dependent_accuracy_state.damage_fn,
    )
    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        state, actions, damage_fn, our_side="p1", branch_cap=8,
    )
    # Sanity: the scripted fixture must actually exercise the bug shape (an attempted_hit
    # absent from leaves[0] but present in some other leaf).
    leaves0_pairs = {(ah.attacker, ah.target, ah.move_id) for ah in leaves[0][1].attempted_hits}
    all_pairs = {
        (ah.attacker, ah.target, ah.move_id)
        for _w, out in leaves for ah in out.attempted_hits
    }
    assert all_pairs - leaves0_pairs, "fixture doesn't exercise a miss-branch-only event"

    events = _accuracy_events_from_leaves(actions, state, leaves, state.field, tie_order="ours_last")
    found_pairs = {(e.attacker, e.target, e.move_id) for e in events}
    assert all_pairs & {p for p in found_pairs if True} == all_pairs.intersection(found_pairs)
    missing_from_leaves0 = all_pairs - leaves0_pairs
    assert missing_from_leaves0 <= found_pairs, (
        "an event only reachable via a miss-branch was dropped -- leaves[0]-only bug reintroduced"
    )


def test_tie_averaging_preserves_asymmetric_cap_hit_and_event(tie_scripted_state):
    """Round-4 fix regression: a genuine tie where ours_first's KO-before-act ordering makes an
    attacker act (attempting an accuracy event) before ours_last's ordering removes that same
    action via an earlier KO. The merged result must retain it even though ours_last alone
    wouldn't have it."""
    detail = _evaluate_line_details(
        tie_scripted_state.state, tie_scripted_state.my_actions, tie_scripted_state.opp_actions,
        tie_scripted_state.damage_fn, our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
    )
    ours_last_only = _evaluate_line_details(
        tie_scripted_state.state, tie_scripted_state.my_actions, tie_scripted_state.opp_actions,
        tie_scripted_state.damage_fn, our_side="p1", accuracy_mode=True, accuracy_branch_cap=8,
        _force_tie_break="ours_last",
    )
    assert len(detail.accuracy_events) > len(ours_last_only.accuracy_events), (
        "merged tie telemetry must be a strict superset of ours_last-alone for this fixture"
    )
    assert detail.representative_outcome == ours_last_only.representative_outcome, (
        "representative_outcome must stay on the unchanged ours_last-only convention"
    )
    tie_orders = {t.tie_order for t in detail.tie_order_details}
    assert tie_orders == {"ours_first", "ours_last"}


def test_events_complete_reflects_branch_cap(capped_accuracy_state):
    detail_capped = _evaluate_line_details(
        capped_accuracy_state.state, capped_accuracy_state.my_actions,
        capped_accuracy_state.opp_actions, capped_accuracy_state.damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=1,  # force an early cap
    )
    assert detail_capped.fallback_leaves >= 1
    assert any(t.events_complete is False for t in detail_capped.tie_order_details)

    detail_uncapped = _evaluate_line_details(
        capped_accuracy_state.state, capped_accuracy_state.my_actions,
        capped_accuracy_state.opp_actions, capped_accuracy_state.damage_fn,
        our_side="p1", accuracy_mode=True, accuracy_branch_cap=64,
    )
    assert detail_uncapped.fallback_leaves == 0
    assert all(t.events_complete for t in detail_uncapped.tie_order_details)
```

The fixtures `basic_state`/`basic_damage_fn`, `scripted_accuracy_state`,
`ko_dependent_accuracy_state`, `tie_scripted_state`, `capped_accuracy_state` should already exist
(or have close analogues) in the merged accuracy slice's own test file — reuse/extend those
fixtures rather than re-deriving scripted `PlannedAction`/`BattleState` setups from scratch; read
that file's existing fixtures first (`test_resolve_turn_branches` and neighboring tests from Task
4/5 of the merged slice) and adapt.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/battle/test_evaluate.py -k "line_details or leaf_union or tie_averaging or events_complete" -v`
Expected: FAIL with `ImportError: cannot import name 'LineEvaluation'`

- [ ] **Step 3: Implement the refactor in `evaluate.py`**

Add these new pieces (exact placement: after `_has_genuine_tie`, before `AccuracyDiagnostics`,
matching the spec's own code layout):

```python
@dataclass
class AccuracyEventDetail:
    attacker: SlotId
    target: SlotId
    move_id: str
    hit_probability: float
    tie_order: str  # "ours_first" | "ours_last"


@dataclass
class TieOrderEvaluation:
    tie_order: str
    weight: float
    accuracy_leaf_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool


@dataclass
class LineEvaluation:
    score: float
    representative_outcome: TurnOutcome
    leaves: list[tuple[float, TurnOutcome]] | None = None
    fork_records: list[ForkRecord] | None = None
    fallback_leaves: int = 0
    accuracy_events: list[AccuracyEventDetail] = field(default_factory=list)
    tie_order_details: list[TieOrderEvaluation] = field(default_factory=list)


def _accuracy_events_from_leaves(
    actions: list[PlannedAction],
    state: BattleState,
    leaves: list[tuple[float, TurnOutcome]],
    field: FieldState | None,
    tie_order: str,
) -> list[AccuracyEventDetail]:
    actions_by_key = {a.key: a for a in actions}
    seen: dict[tuple[SlotId, SlotId, str], float] = {}
    for _weight, out in leaves:
        for ah in out.attempted_hits:
            key3 = (ah.attacker, ah.target, ah.move_id)
            if key3 in seen:
                continue
            attacker_action = actions_by_key.get(ah.attacker)
            if attacker_action is None or attacker_action.move is None:
                continue
            attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
            target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
            if attacker_mon is None or target_mon is None:
                continue
            p = hit_probability(attacker_action.move, attacker_mon, target_mon, field)
            if p is None or p >= 1.0:
                continue
            seen[key3] = p
    return [AccuracyEventDetail(a, t, m, p, tie_order) for (a, t, m), p in seen.items()]


def _evaluate_line_details(
    state: BattleState,
    my_actions: list[PlannedAction],
    opp_actions: list[PlannedAction],
    damage_fn,
    *,
    our_side: str,
    weights: EvalWeights | None = None,
    field: FieldState | None = None,
    rollout_horizon: int = 0,
    rollout_gamma: float = 0.7,
    endgame: bool = False,
    fast_board: bool = False,
    accuracy_mode: bool = False,
    accuracy_branch_cap: int = 4,
    _force_tie_break: str | None = None,
) -> LineEvaluation:
    field = field or state.field
    all_actions = my_actions + opp_actions

    def _scored(out: TurnOutcome) -> float:
        sc = score_outcome(out, our_side, weights, endgame=endgame, fast_board=fast_board)
        if rollout_horizon > 0:
            sc += _rollout_value(
                state, all_actions, out, our_side, weights or EvalWeights(),
                field, rollout_horizon, rollout_gamma,
            )
        return sc

    def _one(tb: str) -> LineEvaluation:
        if not accuracy_mode:
            out = resolve_turn(state, all_actions, damage_fn, our_side=our_side, field=field, tie_break=tb)
            return LineEvaluation(score=_scored(out), representative_outcome=out)
        leaves, fallback_leaves, fork_records = resolve_turn_branches(
            state, all_actions, damage_fn, our_side=our_side, field=field,
            tie_break=tb, branch_cap=accuracy_branch_cap,
        )
        total = sum(w * _scored(out) for w, out in leaves)
        representative = leaves[0][1]
        representative.accuracy_branch_cap_hits = fallback_leaves
        events = _accuracy_events_from_leaves(all_actions, state, leaves, field, tie_order=tb)
        return LineEvaluation(
            score=total, representative_outcome=representative, leaves=leaves,
            fork_records=fork_records, fallback_leaves=fallback_leaves, accuracy_events=events,
            tie_order_details=[TieOrderEvaluation(
                tie_order=tb, weight=1.0, accuracy_leaf_count=len(leaves),
                accuracy_branch_cap_hits=fallback_leaves, events_complete=(fallback_leaves == 0),
            )],
        )

    if _force_tie_break is not None:
        return _one(_force_tie_break)
    if _has_genuine_tie(all_actions, field):
        d_first = _one("ours_first")
        d_last = _one("ours_last")
        return LineEvaluation(
            score=0.5 * (d_first.score + d_last.score),
            representative_outcome=d_last.representative_outcome,
            leaves=d_last.leaves, fork_records=d_last.fork_records,
            fallback_leaves=d_first.fallback_leaves + d_last.fallback_leaves,
            accuracy_events=d_first.accuracy_events + d_last.accuracy_events,
            tie_order_details=[
                TieOrderEvaluation(
                    tie_order="ours_first", weight=0.5,
                    accuracy_leaf_count=len(d_first.leaves) if d_first.leaves else 0,
                    accuracy_branch_cap_hits=d_first.fallback_leaves,
                    events_complete=(d_first.fallback_leaves == 0),
                ),
                TieOrderEvaluation(
                    tie_order="ours_last", weight=0.5,
                    accuracy_leaf_count=len(d_last.leaves) if d_last.leaves else 0,
                    accuracy_branch_cap_hits=d_last.fallback_leaves,
                    events_complete=(d_last.fallback_leaves == 0),
                ),
            ],
        )
    return _one("ours_last")
```

Then replace the existing `evaluate_line` body (keep its exact signature unchanged) with:

```python
def evaluate_line(
    state: BattleState,
    my_actions: list[PlannedAction],
    opp_actions: list[PlannedAction],
    damage_fn,
    *,
    our_side: str,
    weights: EvalWeights | None = None,
    field: FieldState | None = None,
    rollout_horizon: int = 0,
    rollout_gamma: float = 0.7,
    endgame: bool = False,
    fast_board: bool = False,
    accuracy_mode: bool = False,
    accuracy_branch_cap: int = 4,
    _force_tie_break: str | None = None,
) -> tuple[float, TurnOutcome]:
    d = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn, our_side=our_side, weights=weights,
        field=field, rollout_horizon=rollout_horizon, rollout_gamma=rollout_gamma,
        endgame=endgame, fast_board=fast_board, accuracy_mode=accuracy_mode,
        accuracy_branch_cap=accuracy_branch_cap, _force_tie_break=_force_tie_break,
    )
    return d.score, d.representative_outcome
```

Delete the old `_one`-based body entirely — `_evaluate_line_details` now owns that logic. Add
`from dataclasses import field` to the existing `from dataclasses import dataclass` import line if
not already present (check — the file already imports `dataclass`, confirm whether `field` is
already imported too before adding a duplicate import).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/battle/test_evaluate.py -v`
Expected: PASS, including every pre-existing test in this file (the refactor must not regress any
of the merged slice's original Task 4/5/6 tests — if any fail, this is a real regression, stop and
fix before proceeding, do not skip or weaken an existing test to make it pass)

- [ ] **Step 5: Run the full existing accuracy-slice test suite as a regression check**

Run: `cd showdown_bot && python -m pytest tests/ -k "accuracy or evaluate_line or resolve_turn" -v`
Expected: PASS, 0 failures

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/evaluate.py showdown_bot/tests/battle/test_evaluate.py
git commit -m "refactor(battle): LineEvaluation/_evaluate_line_details, fix event-union and tie-averaging telemetry gaps"
```

---

## Task 6: `decision.py` trace wiring — `CandidateTrace.accuracy_details` (HIGH RISK — extra scrutiny)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/decision_trace.py`
- Modify: `showdown_bot/src/showdown_bot/battle/decision.py`
- Modify: `showdown_bot/tests/battle/test_decision_trace.py` (or the project's actual existing file
  — confirm; the merged slice's trace-population tests live somewhere under `tests/battle/`)

Implements spec §2.4. Touches the live decision pipeline's trace-population block
(`_breakdowns_for`, currently `decision.py:598-612`, and its caller around `decision.py:657-668` —
**re-verify these line numbers before editing**, since Task 5 only touched `evaluate.py`, but
confirm decision.py is unchanged since the session's earlier reads before trusting them blindly).

- [ ] **Step 1: Write the failing tests**

```python
# added to the decision_trace test file
from showdown_bot.battle.decision_trace import (
    AccuracyEventTrace,
    AccuracyResponseDetail,
    AccuracyTieOrderTrace,
    CandidateTrace,
)


def test_accuracy_response_detail_fields_exist():
    detail = AccuracyResponseDetail(
        accuracy_leaf_count=4, accuracy_event_count=2, accuracy_branch_cap_hits=0,
        events_complete=True, tie_orders=[], events=[],
    )
    assert detail.accuracy_leaf_count == 4
    assert detail.events_complete is True


def test_candidate_trace_accuracy_details_defaults_empty():
    ct = CandidateTrace(
        candidate_id="x", joint_action=None, rank=0, aggregate_score=0.0,
        score_vector=[], outcome_breakdowns=[], aggregate_breakdown=None,
    )
    assert ct.accuracy_details == []


def test_decision_with_accuracy_mode_populates_accuracy_details(
    scripted_request, scripted_state, monkeypatch,
):
    """Integration test through the real decision.py entry point with a DecisionTrace passed
    and SHOWDOWN_ACCURACY_MODE forced on -- mirrors the merged slice's own
    tests/test_accuracy_mode_wiring.py integration-test pattern (Task 5's precedent), not a new
    access pattern."""
    import os

    from showdown_bot.battle.decision import _choose_best  # or the project's real public entry
    from showdown_bot.battle.decision_trace import DecisionTrace

    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    trace = DecisionTrace()
    _choose_best(scripted_request, state=scripted_state, trace=trace)  # adapt args to the real signature

    assert trace.candidates, "expected at least one candidate in the trace"
    for candidate in trace.candidates:
        assert isinstance(candidate.accuracy_details, list)
        for detail in candidate.accuracy_details:
            assert isinstance(detail, AccuracyResponseDetail)
            assert detail.accuracy_branch_cap_hits >= 0
            assert isinstance(detail.events_complete, bool)
            for tie_order in detail.tie_orders:
                assert isinstance(tie_order, AccuracyTieOrderTrace)
            for event in detail.events:
                assert isinstance(event, AccuracyEventTrace)
                assert event.tie_order in ("ours_first", "ours_last")


def test_decision_trace_candidates_rank_sorted(scripted_request, scripted_state, monkeypatch):
    """Spec §5's point-8 fix: candidates must be provably rank-sorted, not just observed to be
    by accident of the current construction code."""
    from showdown_bot.battle.decision import _choose_best
    from showdown_bot.battle.decision_trace import DecisionTrace

    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "0")
    trace = DecisionTrace()
    _choose_best(scripted_request, state=scripted_state, trace=trace)
    assert [c.rank for c in trace.candidates] == list(range(len(trace.candidates)))
```

Adapt `scripted_request`/`scripted_state`/the exact call to `_choose_best` (or whatever the real
top-level function is named and however trace gets threaded in — confirm the real signature in
`decision.py` before writing this; the merged slice's `tests/test_accuracy_mode_wiring.py` already
has a working example of exactly this "force accuracy on via env var, pass a trace, inspect it"
pattern — copy its scripted fixture setup rather than inventing a new one).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/battle/test_decision_trace.py -k accuracy -v`
Expected: FAIL with `ImportError: cannot import name 'AccuracyEventTrace'`

- [ ] **Step 3: Add the trace dataclasses to `decision_trace.py`**

```python
@dataclass
class AccuracyEventTrace:
    attacker: Any  # SlotId = tuple[str, str]
    target: Any
    move_id: str
    hit_probability: float
    response_index: int
    tie_order: str


@dataclass
class AccuracyTieOrderTrace:
    tie_order: str
    weight: float
    accuracy_leaf_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool


@dataclass
class AccuracyResponseDetail:
    accuracy_leaf_count: int
    accuracy_event_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool
    tie_orders: list[AccuracyTieOrderTrace] = field(default_factory=list)
    events: list[AccuracyEventTrace] = field(default_factory=list)
```

Add `accuracy_details: list[AccuracyResponseDetail] = field(default_factory=list)` as a new field
on `CandidateTrace`, appended after the existing `model_features` field (do not reorder existing
fields — this is a dataclass with positional-construction call sites elsewhere in the codebase;
appending at the end with a default keeps every existing `CandidateTrace(...)` call site
byte-compatible).

Import `SlotId` from `showdown_bot.battle.resolve` at the top of `decision_trace.py` and use it as
the real type for `attacker`/`target` instead of `Any`, matching this file's existing style
(check: does `decision_trace.py` currently import anything from `battle.resolve`? If not, this is
a new import — verify it doesn't create a circular import, since `resolve.py` doesn't import
`decision_trace.py`, so it should be safe).

- [ ] **Step 4: Wire `_breakdowns_for` in `decision.py` to populate `accuracy_details`**

Modify the existing `_breakdowns_for` function (currently around `decision.py:598-612`):

```python
def _breakdowns_for(plan):
    out = []
    acc_details = []
    for ri, ra in enumerate(rep_resps):
        d = _evaluate_line_details(
            state, plan, ra, model.damage_fn, our_side=our_side,
            weights=weights, field=state.field, rollout_horizon=0,
            endgame=endgame, fast_board=fast_board,
            accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
        )
        out.append(
            score_outcome_with_breakdown(
                d.representative_outcome, our_side, weights, endgame=endgame, fast_board=fast_board
            )[1]
        )
        acc_details.append(AccuracyResponseDetail(
            accuracy_leaf_count=sum(t.accuracy_leaf_count for t in d.tie_order_details),
            accuracy_event_count=len(d.accuracy_events),
            accuracy_branch_cap_hits=d.fallback_leaves,
            events_complete=(d.fallback_leaves == 0),
            tie_orders=[
                AccuracyTieOrderTrace(
                    t.tie_order, t.weight, t.accuracy_leaf_count,
                    t.accuracy_branch_cap_hits, t.events_complete,
                )
                for t in d.tie_order_details
            ],
            events=[
                AccuracyEventTrace(
                    e.attacker, e.target, e.move_id, e.hit_probability,
                    response_index=ri, tie_order=e.tie_order,
                )
                for e in d.accuracy_events
            ],
        ))
    return out, acc_details
```

Update the import at the top of `decision.py`'s trace block (currently imports `CandidateModelFeatures,
CandidateTrace, DecisionTrace as _DT` and `OutcomeBreakdown, score_outcome_with_breakdown` — add
`AccuracyResponseDetail, AccuracyTieOrderTrace, AccuracyEventTrace` to the `decision_trace` import,
and `_evaluate_line_details` to the `battle.evaluate` import alongside the existing `evaluate_line`
import, or replace `evaluate_line` with `_evaluate_line_details` in this specific block's imports
if `evaluate_line` is no longer called anywhere else in this function once this change lands — check
before removing).

Update the single call site that invokes `_breakdowns_for` (currently `decision.py:657-668`, inside
the `for rank, (ja, scores, agg) in enumerate(scored[:TOP_K_TRACE_CANDIDATES]):` loop):

```python
        for rank, (ja, scores, agg) in enumerate(scored[:TOP_K_TRACE_CANDIDATES]):
            bds, acc_details = _breakdowns_for(plans[ja])
            cands.append(CandidateTrace(
                candidate_id=_label_ja(req, ja), joint_action=ja, rank=rank,
                aggregate_score=agg, score_vector=list(scores),
                outcome_breakdowns=bds, aggregate_breakdown=_weighted_mean_breakdown(bds),
                model_features=CandidateModelFeatures(
                    ko_secured_count=_ko_secured_for(plans[ja]),
                    ko_threatened_count=dec_threatened,
                    survives_for_sure_count=dec_survives,
                ),
                accuracy_details=acc_details,
            ))
```

(Only the `bds, acc_details = _breakdowns_for(plans[ja])` line and the new
`accuracy_details=acc_details` kwarg change — every other line in this block is unchanged from the
current source; verify against the real current file before editing, since re-typing this whole
block risks a transcription error in a live decision-pipeline function.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/battle/test_decision_trace.py -v`
Expected: PASS

- [ ] **Step 6: Run the full battle/ test suite as a regression check**

Run: `cd showdown_bot && python -m pytest tests/battle/ -v`
Expected: PASS, 0 failures — this is the live decision pipeline, any regression here blocks merge

- [ ] **Step 7: Commit**

```bash
git add showdown_bot/src/showdown_bot/battle/decision_trace.py showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/tests/battle/test_decision_trace.py
git commit -m "feat(battle): wire per-response accuracy telemetry into CandidateTrace"
```

---

## Task 7: Post-refactor baseline diff + env-parser unset-vs-off test

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/accuracy_baseline_diff.py`
- Create: `showdown_bot/tests/eval/test_accuracy_baseline_diff.py`
- Create: `showdown_bot/tests/battle/test_accuracy_env_parser.py` (or add to an existing env-parser
  test file from the merged slice — the accuracy-hit-probability plan's Task 5 already built and
  tested `_accuracy_mode()`'s env-flag parser; this task adds ONE more test on top of that
  existing, already-fixed parser, it does not rebuild it)

Implements spec §4's "runs twice, for two different purposes" requirement and closes the loop on
Task 4's hard checkpoint.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/eval/test_accuracy_baseline_diff.py
from __future__ import annotations

from showdown_bot.eval.accuracy_baseline_diff import BaselineDiffResult, diff_against_baseline


def test_identical_rows_produce_zero_regressions():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.5000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.5000000000"},
    ]
    result = diff_against_baseline(baseline, replay)
    assert result.regressions == []
    assert result.matched == 1


def test_action_change_is_a_regression():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.5000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 2", "score": "1.5000000000"},
    ]
    result = diff_against_baseline(baseline, replay)
    assert len(result.regressions) == 1
    assert result.regressions[0].request_hash == "a"


def test_missing_row_in_replay_is_flagged_not_silently_dropped():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
        {"request_hash": "b", "log_prefix_hash": "p2", "chosen_action": "move 1", "score": "1.0000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
    ]
    result = diff_against_baseline(baseline, replay)
    assert result.missing_from_replay == ["b"]
```

```python
# showdown_bot/tests/battle/test_accuracy_env_parser.py
import os

from showdown_bot.battle.decision import _accuracy_mode


def test_unset_and_explicit_off_are_equivalent_post_refactor(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)
    unset = _accuracy_mode()
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "0")
    explicit_off = _accuracy_mode()
    assert unset == explicit_off == False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_baseline_diff.py tests/battle/test_accuracy_env_parser.py -v`
Expected: FAIL — `test_accuracy_env_parser.py`'s test may actually PASS already if the merged
slice's Task 5 env-parser fix is already correct (it was fixed and tested in that slice); if so,
that's expected and fine, this is a defense-in-depth regression pin, not a new bug hunt. The
`accuracy_baseline_diff` tests should FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `accuracy_baseline_diff.py`**

```python
# showdown_bot/src/showdown_bot/eval/accuracy_baseline_diff.py
"""Diff a post-refactor replay of the deduplicated corpus (accuracy off) against the frozen
pre-refactor baseline (Task 4). This is the true refactor-regression check -- unset-vs-explicit-off
alone cannot catch a bug in a wrapper both paths route through after the LineEvaluation refactor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Regression:
    request_hash: str
    baseline_action: str
    replay_action: str
    baseline_score: str
    replay_score: str


@dataclass(frozen=True)
class BaselineDiffResult:
    matched: int
    regressions: list[Regression]
    missing_from_replay: list[str]
    extra_in_replay: list[str]


def diff_against_baseline(baseline_rows: list[dict], replay_rows: list[dict]) -> BaselineDiffResult:
    baseline_by_hash = {r["request_hash"]: r for r in baseline_rows}
    replay_by_hash = {r["request_hash"]: r for r in replay_rows}

    matched = 0
    regressions: list[Regression] = []
    for req_hash, brow in baseline_by_hash.items():
        rrow = replay_by_hash.get(req_hash)
        if rrow is None:
            continue
        matched += 1
        if brow["chosen_action"] != rrow["chosen_action"] or brow["score"] != rrow["score"]:
            regressions.append(Regression(
                request_hash=req_hash,
                baseline_action=brow["chosen_action"], replay_action=rrow["chosen_action"],
                baseline_score=brow["score"], replay_score=rrow["score"],
            ))

    missing_from_replay = sorted(set(baseline_by_hash) - set(replay_by_hash))
    extra_in_replay = sorted(set(replay_by_hash) - set(baseline_by_hash))

    return BaselineDiffResult(
        matched=matched, regressions=regressions,
        missing_from_replay=missing_from_replay, extra_in_replay=extra_in_replay,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_baseline_diff.py tests/battle/test_accuracy_env_parser.py -v`
Expected: PASS

- [ ] **Step 5: Run the real post-refactor replay and diff against the frozen baseline**

Write a small driver (extend `scripts/run_accuracy_baseline_freeze.py` with a `--replay-and-diff`
mode, or a new `scripts/run_accuracy_baseline_diff.py` — match whichever pattern reads more
naturally given Task 4's script) that: loads `data/eval/accuracy-gate/pre-refactor-baseline.jsonl`
(the Task 4 artifact — **read-only, never regenerate it**), re-extracts the identical deduplicated
corpus via `room_raw_replay`, re-runs `heuristic_choose_for_request` with
`SHOWDOWN_ACCURACY_MODE=off` (now going through the Task 5/6-refactored code), and calls
`diff_against_baseline(...)`.

Run:

```bash
cd showdown_bot && python scripts/run_accuracy_baseline_diff.py
```

Expected: `regressions == []`, `missing_from_replay == []`, `extra_in_replay == []`. **If this
fails, the refactor introduced a real behavioral change on the off-path — stop, do not proceed to
Task 8, investigate and fix Task 5/6 first.** This is the load-bearing check the whole
sequencing constraint (Tasks 1-4 before Task 5) exists to enable.

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_baseline_diff.py \
        showdown_bot/tests/eval/test_accuracy_baseline_diff.py \
        showdown_bot/tests/battle/test_accuracy_env_parser.py \
        showdown_bot/scripts/run_accuracy_baseline_diff.py
git commit -m "test(eval): post-refactor baseline diff confirms byte-identical off-path"
```

---

## Task 8: Statistics — pinned bootstrap + zero-event Clopper-Pearson branch + verdict bands

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/accuracy_gate_stats.py`
- Create: `showdown_bot/tests/eval/test_accuracy_gate_stats.py`

Implements spec §4 exactly. No new resolution/decision logic — pure statistics on already-collected
per-decision/per-game data.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/eval/test_accuracy_gate_stats.py
from __future__ import annotations

import math

from showdown_bot.eval.accuracy_gate_stats import (
    Verdict,
    clopper_pearson_zero_upper_bound,
    game_clustered_bootstrap_upper_bound,
    minimum_g_for_zero_event_pass,
    verdict_for_cap_hit_rate,
)


def test_clopper_pearson_zero_upper_bound_matches_known_values():
    assert math.isclose(clopper_pearson_zero_upper_bound(85), 0.0346, abs_tol=1e-3)
    assert math.isclose(clopper_pearson_zero_upper_bound(197), 0.0151, abs_tol=1e-3)
    assert math.isclose(clopper_pearson_zero_upper_bound(30), 0.095, abs_tol=1e-3)


def test_minimum_g_for_zero_event_pass_is_59():
    assert minimum_g_for_zero_event_pass() == 59
    assert clopper_pearson_zero_upper_bound(59) <= 0.05
    assert clopper_pearson_zero_upper_bound(58) > 0.05


def test_bootstrap_zero_events_uses_game_level_bound():
    # 10 games, 0 decisions with a cap-hit in any of them.
    per_game_cap_hit = {f"game{i}": False for i in range(10)}
    per_decision = []  # no cap-hit decisions at all
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision, per_game_any_cap_hit=per_game_cap_hit,
        n_decisions=200, rng_seed=20260713,
    )
    assert detail["bootstrap_ci_upper"] == 0.0
    assert detail["bootstrap_ci_degenerate"] is True
    assert "clopper_pearson_upper_bound" in detail
    assert detail["clopper_pearson_upper_bound"] == clopper_pearson_zero_upper_bound(10)
    assert verdict == Verdict.INCONCLUSIVE  # G=10 is far below the G>=59 floor


def test_zero_events_passes_when_g_clears_the_floor():
    per_game_cap_hit = {f"game{i}": False for i in range(85)}
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=[], per_game_any_cap_hit=per_game_cap_hit,
        n_decisions=1186, rng_seed=20260713,
    )
    assert verdict == Verdict.PASS
    assert detail["clopper_pearson_upper_bound"] <= 0.05


def test_nonzero_events_uses_bootstrap_pass_band():
    # 100 decisions across 20 games, 1 cap-hit decision (0.5% point estimate) -- should PASS
    # given a tight bootstrap CI at this scale.
    per_decision = [False] * 99 + [True]
    game_ids = [f"game{i % 20}" for i in range(100)]
    per_game_any_cap_hit = {f"game{i}": False for i in range(20)}
    per_game_any_cap_hit["game19"] = True  # the one cap-hit decision's game
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=list(zip(game_ids, per_decision)),
        per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=100, rng_seed=20260713,
    )
    assert detail["point_estimate"] == 0.01
    assert verdict in (Verdict.PASS, Verdict.INCONCLUSIVE)  # depends on bootstrap variance at n=20 games


def test_nonzero_events_fails_above_five_percent():
    per_decision = [(f"game{i}", True) for i in range(10)] + [(f"game{i}", False) for i in range(10, 100)]
    per_game_any_cap_hit = {f"game{i}": (i < 10) for i in range(100)}
    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision, per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=100, rng_seed=20260713,
    )
    assert detail["point_estimate"] == 0.10
    assert verdict == Verdict.FAIL
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'showdown_bot.eval.accuracy_gate_stats'`

- [ ] **Step 3: Implement `accuracy_gate_stats.py`**

```python
# showdown_bot/src/showdown_bot/eval/accuracy_gate_stats.py
"""Pinned statistics for the chosen-line cap-hit rate acceptance rule (spec Sec.4).

Bootstrap params are pinned, not chosen after seeing results: B=10,000 resamples, one-sided
95% upper bound (95th percentile, NOT the 97.5th -- a two-sided CI's upper endpoint is a
different, more conservative quantity), RNG seeded 20260713 as its own dedicated stream.

A plain game-clustered bootstrap degenerates to a false [0%, 0%] CI when zero cap-hit events
are observed -- every possible resample can only redraw from all-zero games. The zero-event
branch instead uses the exact one-sided 95% Clopper-Pearson upper bound on a game-level
"did any decision in this game cap-hit" indicator.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from enum import Enum

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260713
PASS_THRESHOLD = 0.05


class Verdict(Enum):
    PASS = "PASS"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAIL = "FAIL"


def clopper_pearson_zero_upper_bound(g: int) -> float:
    """Exact one-sided 95% Clopper-Pearson upper bound at 0 observed successes out of g trials.
    Closed form: 1 - 0.05^(1/g). Equivalent to the "rule of three" approximation ~3/g for large g."""
    if g <= 0:
        raise ValueError("g must be positive")
    return 1.0 - 0.05 ** (1.0 / g)


def minimum_g_for_zero_event_pass() -> int:
    """Smallest integer G such that clopper_pearson_zero_upper_bound(G) <= 0.05."""
    g = 1
    while clopper_pearson_zero_upper_bound(g) > PASS_THRESHOLD:
        g += 1
    return g


def game_clustered_bootstrap_upper_bound(
    per_game_rate: dict[str, float], *, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
) -> float:
    """One-sided 95% upper bound (95th percentile) of the resampled rate distribution,
    resampling whole games with replacement."""
    games = list(per_game_rate.items())
    if not games:
        raise ValueError("no games to resample")
    rng = random.Random(seed)
    n = len(games)
    resampled_rates = []
    for _ in range(resamples):
        draw = [games[rng.randrange(n)][1] for _ in range(n)]
        resampled_rates.append(sum(draw) / n)
    resampled_rates.sort()
    idx = int(0.95 * (len(resampled_rates) - 1))
    return resampled_rates[idx]


def verdict_for_cap_hit_rate(
    *,
    per_decision_cap_hit: list[tuple[str, bool]] | list[bool],
    per_game_any_cap_hit: dict[str, bool],
    n_decisions: int,
    rng_seed: int = BOOTSTRAP_SEED,
) -> tuple[Verdict, dict]:
    numerator = sum(
        1 for row in per_decision_cap_hit
        if (row[1] if isinstance(row, tuple) else row)
    )
    point_estimate = (numerator / n_decisions) if n_decisions else 0.0
    g = len(per_game_any_cap_hit)

    if numerator == 0:
        cp_upper = clopper_pearson_zero_upper_bound(g) if g > 0 else 1.0
        detail = {
            "point_estimate": 0.0,
            "numerator": 0,
            "n_decisions": n_decisions,
            "g": g,
            "bootstrap_ci_upper": 0.0,
            "bootstrap_ci_degenerate": True,
            "clopper_pearson_upper_bound": cp_upper,
        }
        verdict = Verdict.PASS if cp_upper <= PASS_THRESHOLD else Verdict.INCONCLUSIVE
        return verdict, detail

    per_game_rate = {
        game: (1.0 if any_hit else 0.0) for game, any_hit in per_game_any_cap_hit.items()
    }
    bootstrap_upper = game_clustered_bootstrap_upper_bound(per_game_rate, seed=rng_seed)
    detail = {
        "point_estimate": point_estimate,
        "numerator": numerator,
        "n_decisions": n_decisions,
        "g": g,
        "bootstrap_ci_upper": bootstrap_upper,
        "bootstrap_ci_degenerate": False,
    }
    if point_estimate > PASS_THRESHOLD:
        verdict = Verdict.FAIL
    elif bootstrap_upper <= PASS_THRESHOLD:
        verdict = Verdict.PASS
    else:
        verdict = Verdict.INCONCLUSIVE
    return verdict, detail
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_stats.py -v`
Expected: PASS (6 passed). If `test_nonzero_events_uses_bootstrap_pass_band` is flaky at the
pinned seed (bootstrap variance at n=20 games could tip either PASS or INCONCLUSIVE), that's
already accounted for by the test's `in (Verdict.PASS, Verdict.INCONCLUSIVE)` assertion — this is
intentional, not a bug to chase.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_gate_stats.py showdown_bot/tests/eval/test_accuracy_gate_stats.py
git commit -m "feat(eval): pinned bootstrap + zero-event Clopper-Pearson verdict statistics"
```

---

## Task 9: Gate A — smoke test script

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/accuracy_gate_a.py`
- Create: `showdown_bot/tests/eval/test_accuracy_gate_a.py`

Implements spec §1's Gate A. Verified against real source this session (not a placeholder-driven
draft):

- `heuristic_choose_for_request` (`battle/decision.py:750-800`) is the real top-level entry point.
  Exact signature: `heuristic_choose_for_request(req: BattleRequest, *, state: BattleState, book:
  SpreadBook, our_side: str | None = None, calc: CalcClient | None = None, oracle: DamageOracle |
  None = None, speed_oracle: SpeedOracle | None = None, dex: SpeciesDex | None = None, priors=None,
  weights: EvalWeights | None = None, risk_lambda: float | None = None, tera_margin: float = 1.0,
  rollout_horizon: int | None = None, report: list[str] | None = None, our_spreads: dict | None =
  None, opp_sets: dict | None = None, trace=None) -> str`. Returns the `/choose` string directly.
  **It does not take an `accuracy_mode` kwarg** — accuracy on/off is controlled *purely* by the
  `SHOWDOWN_ACCURACY_MODE` environment variable, read internally by `_choose_best`. Confirmed
  directly from `scratchpad/bench_accuracy_latency.py`'s own usage: it never passes
  `accuracy_mode=...` to `heuristic_choose_for_request`, only sets/unsets
  `os.environ["SHOWDOWN_ACCURACY_MODE"]` around each call.
- `scratchpad/bench_accuracy_latency.py`'s `make_state()`/`REQ`/`BOOK`/`CALC`/`SPEED`/`DEX`
  construction (lines 49-74) is the real, working board this task reuses verbatim: p1
  Incineroar+Rillaboom (Rillaboom's Heat Wave is a 90%-accuracy spread move) vs p2 Flutter
  Mane+Tornadus (Tornadus's Bleakwind Storm is an 80%-accuracy spread move) — genuinely exercises
  accuracy branching on both sides, not a board picked for convenience.
- `FieldState` (`engine/state.py:75-79`) is a plain dataclass: `weather: str | None`,
  `terrain: str | None`, `trick_room: bool = False`, `tailwind: dict[str, bool] =
  {"p1": False, "p2": False}`. The 7 field-bucket variants are constructed directly from this —
  the Depth-2 Stage 2 script this pattern was originally attributed to no longer exists on disk
  (`scratchpad/stage2_decision_diff.py` was transient, never committed); its own report
  (`reports/2026-07-12-2c-depth2-derisk-verdict.md`) confirms the *approach* ("vary `FieldState`
  on the fixed realistic board") but not exact code, so this task writes the 7 variants fresh,
  directly against `FieldState`'s real fields, rather than reusing since-deleted code.
- **Scope decision, stated plainly rather than left implicit:** the spec's "1-2 additional real
  archetypes pulled from `config/eval/panels/panel_v001.yaml`" requirement assumes a
  team-file-to-`BattleState` loader for offline direct calls. No such loader exists in this
  codebase — team files are only ever turned into battle state via the live server/gauntlet
  protocol flow (`client/gauntlet.py`), which Gate A explicitly does not use (spec §1: "no
  server"). Rather than block on building a new team-file loader (out of scope for this gate) or
  leave a placeholder, this task adds 1-2 **additional hand-constructed boards**, in the exact same
  style as `make_state()`, chosen to have a genuinely different accuracy profile (e.g. a board with
  a single-target <100%-accuracy move instead of a spread move) — satisfying the spirit of "more
  than one board" without a fabricated panel-loading call. If a real panel-team loader is ever
  built for another purpose, swapping these in is a natural, isolated follow-up, not part of this
  gate.

- [ ] **Step 1: Write the failing test**

```python
# showdown_bot/tests/eval/test_accuracy_gate_a.py
from __future__ import annotations

from showdown_bot.eval.accuracy_gate_a import FIELD_VARIANTS, GateAResult, run_gate_a


def test_run_gate_a_produces_one_result_per_board_x_field_combo():
    result = run_gate_a(board_names=["primary"], field_variants=["neutral", "sun"])
    assert isinstance(result, GateAResult)
    assert len(result.rows) == 2
    for row in result.rows:
        assert row.board == "primary"
        assert row.field_variant in ("neutral", "sun")
        assert isinstance(row.off_chosen_action, str) and row.off_chosen_action
        assert isinstance(row.on_chosen_action, str) and row.on_chosen_action
        assert row.exception is None


def test_run_gate_a_default_sweeps_all_7_field_variants_and_both_boards():
    result = run_gate_a()
    assert len(FIELD_VARIANTS) == 7
    assert {r.board for r in result.rows} == {"primary", "single_target"}
    assert {r.field_variant for r in result.rows} == set(FIELD_VARIANTS)
    assert len(result.rows) == 2 * 7
    assert result.exception_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_a.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `accuracy_gate_a.py`**

```python
# showdown_bot/src/showdown_bot/eval/accuracy_gate_a.py
"""Gate A: a smoke test sweeping a small number of fixed boards across 7 field-bucket variants,
comparing SHOWDOWN_ACCURACY_MODE off vs on via direct heuristic_choose_for_request calls, no
server. Explicitly a smoke test (spec Sec.1) -- cannot license anything on its own."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.opponent import SpeciesDex
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, FieldState, PokemonState
from showdown_bot.models.request import BattleRequest

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"

FIELD_VARIANTS = ["neutral", "tailwind_both", "tailwind_p1", "tailwind_p2", "trick_room", "sun", "rain"]


def _make_field(variant: str) -> FieldState:
    if variant == "neutral":
        return FieldState()
    if variant == "tailwind_both":
        return FieldState(tailwind={"p1": True, "p2": True})
    if variant == "tailwind_p1":
        return FieldState(tailwind={"p1": True, "p2": False})
    if variant == "tailwind_p2":
        return FieldState(tailwind={"p1": False, "p2": True})
    if variant == "trick_room":
        return FieldState(trick_room=True)
    if variant == "sun":
        return FieldState(weather="Sun")
    if variant == "rain":
        return FieldState(weather="Rain")
    raise ValueError(f"unknown field variant: {variant!r}")


def _make_primary_state() -> BattleState:
    # Verbatim reproduction of scratchpad/bench_accuracy_latency.py's make_state(): p1
    # Incineroar+Rillaboom (Heat Wave 90% spread) vs p2 FlutterMane+Tornadus (Bleakwind Storm
    # 80% spread) -- exercises accuracy branching on both sides.
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


def _make_single_target_state() -> BattleState:
    # A second board with a single-target (not spread) <100%-accuracy move, so Gate A's smoke
    # test isn't only exercising spread-move accuracy branching -- Focus Blast (70% acc).
    st = BattleState()
    gar = PokemonState(species="Gholdengo", hp=133, max_hp=133)
    gar.move_names = {"Shadow Ball", "Focus Blast"}
    st.sides["p1"]["a"] = gar
    st.sides["p1"]["b"] = PokemonState(species="Landorus-Therian", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Amoonguss", hp=176, max_hp=176)
    st.sides["p2"]["b"] = PokemonState(species="Urshifu", hp=139, max_hp=139)
    return st


_BOARDS = {
    "primary": _make_primary_state,
    "single_target": _make_single_target_state,
}

_REQ = BattleRequest.model_validate(
    json.loads((_FIXTURE_DIR / "request_doubles_moves.json").read_text())
)
_BOOK = load_spread_book(load_format_config("gen9vgc2025regi").meta_path("default_spreads"))
_CALC = CalcClient()
_SPEED = SpeedOracle(stats_backend=_CALC.backend)
_DEX = SpeciesDex(_CALC.backend)


@dataclass(frozen=True)
class GateARow:
    board: str
    field_variant: str
    off_chosen_action: str
    on_chosen_action: str
    action_changed: bool
    exception: str | None


@dataclass(frozen=True)
class GateAResult:
    rows: list[GateARow]

    @property
    def diff_count(self) -> int:
        return sum(1 for r in self.rows if r.action_changed)

    @property
    def exception_count(self) -> int:
        return sum(1 for r in self.rows if r.exception is not None)


def _decide(board_name: str, field: FieldState, *, accuracy_on: bool) -> str:
    st = copy.deepcopy(_BOARDS[board_name]())
    st.field = field
    if accuracy_on:
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
    else:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    oracle = DamageOracle(_CALC)
    return heuristic_choose_for_request(
        _REQ, state=st, book=_BOOK, our_side="p1",
        calc=_CALC, oracle=oracle, speed_oracle=_SPEED, dex=_DEX,
    )


def run_gate_a(
    *, board_names: list[str] | None = None, field_variants: list[str] = FIELD_VARIANTS,
) -> GateAResult:
    board_names = board_names if board_names is not None else list(_BOARDS)
    rows: list[GateARow] = []
    try:
        for board in board_names:
            for variant in field_variants:
                field = _make_field(variant)
                try:
                    off_action = _decide(board, field, accuracy_on=False)
                    on_action = _decide(board, field, accuracy_on=True)
                    rows.append(GateARow(
                        board=board, field_variant=variant,
                        off_chosen_action=off_action, on_chosen_action=on_action,
                        action_changed=(off_action != on_action), exception=None,
                    ))
                except Exception as exc:  # noqa: BLE001
                    rows.append(GateARow(
                        board=board, field_variant=variant,
                        off_chosen_action="", on_chosen_action="",
                        action_changed=False, exception=str(exc),
                    ))
    finally:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)  # never leak state into other test runs
    return GateAResult(rows=rows)
```

- [ ] **Step 4: Run the tests**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_a.py -v`
Expected: PASS (2 passed), with real `/choose`-shaped `off_chosen_action`/`on_chosen_action`
strings (e.g. `"move 1, move 2"`), zero exceptions.

- [ ] **Step 5: Run Gate A for real across both boards and produce a report**

```bash
cd showdown_bot && python -c "
from showdown_bot.eval.accuracy_gate_a import run_gate_a
result = run_gate_a()
print(f'diffs: {result.diff_count}/{len(result.rows)}, exceptions: {result.exception_count}')
for row in result.rows:
    print(row.board, row.field_variant, row.off_chosen_action, '->', row.on_chosen_action, row.action_changed)
"
```

Expected: `exceptions: 0/14` (2 boards × 7 field variants; spec §4's "no exceptions" acceptance
rule). Write the row-level output to `data/eval/accuracy-gate/gate-a-report.json` (reuse this
project's established JSON report-writing convention from `eval/decision_diff_report.py`).

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_gate_a.py showdown_bot/tests/eval/test_accuracy_gate_a.py data/eval/accuracy-gate/gate-a-report.json
git commit -m "feat(eval): Gate A smoke-test sweep script"
```

---

## Task 10: Gate B — confirmatory run over the full deduplicated corpus

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/accuracy_gate_b.py`
- Create: `showdown_bot/tests/eval/test_accuracy_gate_b.py`

Implements spec §1's Gate B, §4's acceptance rules, §5's per-diff capture schema, §6's "full
deduplicated corpus only, INCONCLUSIVE/BLOCKED FOR COMPUTE if infeasible" policy. **This is the
core of the whole study — no placeholders, every rule below is real, executable code, verified
against the real API this session.**

Real API facts this task is built on (verified, not assumed):

- `heuristic_choose_for_request(req, *, state, book, our_side, calc, oracle, speed_oracle, dex,
  trace=None, ...) -> str` (`battle/decision.py:750-800`) accepts `trace=` directly and forwards it
  through to the trace-population code (Task 6's wiring). Accuracy on/off is controlled **only**
  via the `SHOWDOWN_ACCURACY_MODE` environment variable — there is no `accuracy_mode` kwarg.
- `CandidateTrace.accuracy_details: list[AccuracyResponseDetail]` (Task 6) already carries, per
  scored opponent response, a `accuracy_branch_cap_hits: int` that is **already tie-order-summed**
  (Task 6's `_breakdowns_for` wiring reads `LineEvaluation.fallback_leaves`, which Task 5's
  tie-merge already combines across both evaluated orderings). This means spec §4's "any
  response, any tie order" cap-hit rule collapses to a single flat check:
  `any(d.accuracy_branch_cap_hits >= 1 for d in candidate.accuracy_details)` — no separate nested
  tie-order loop needed at this layer.
- `eval/decision_capture.py`'s `normalize_choose(choose: str, request: BattleRequest) -> dict`
  turns a raw `/choose ...` string into the exact `{"kind": "joint", "slots": [...]}` shape
  `eval/decision_diff.py`'s `classify_action_diff(baseline: dict, candidate: dict, ...)` already
  consumes (its own taxonomy: `FALLBACK > TERA > SWITCH > PROTECT > ATTACK_MOVE > ATTACK_TARGET >
  OTHER_ACTION`, plus a `tera_changed` marker) — this task reuses both directly rather than
  reimplementing diff classification.
- `_label_ja`-derived `candidate_id` values are stable across `SHOWDOWN_ACCURACY_MODE` (confirmed
  in the spec's own investigation — `_label_ja` is a pure function of `req`+`ja`, and legal-action
  enumeration doesn't depend on accuracy scoring), so pairing off-run and on-run candidates by
  `candidate_id` (not rank or list position) is valid.
- **`trace.chosen_candidate_id` is not always found verbatim in `trace.candidates` — a real,
  confirmed pre-existing bug, not a hypothetical.** Found and independently verified during Task 4:
  `_maybe_tera` (`decision.py:536`) can overlay a Tera flag onto the chosen line **after**
  `trace.candidates` was already built from the pre-Tera candidate set (`items`/`plans`, computed
  earlier). `_label_ja` appends `" tera"` per-slot when that slot terastallizes, so
  `trace.chosen_candidate_id` can carry a `" tera"` suffix matching no `candidate_id` in
  `trace.candidates` verbatim. This is not scope creep to fix here — Task 4's own driver hit this
  for real (1/944 decisions) and proved the fix: try an exact match first, then a match with `"
  tera"` stripped from both sides (guaranteed unique when it exists, since Tera is never itself a
  dimension of the enumerated candidate space — at most one slot of the *chosen* line can carry
  it). `_chosen_candidate` below implements this and **raises**, rather than silently returning
  `None`, when even the fallback can't resolve — a silent `None` here would make the cap-hit rule
  quietly default to "not capped" for exactly the decisions this bug affects, biasing the gate's
  own verdict without anyone noticing.

- [ ] **Step 1: Write the failing tests**

These test the **exact rules** (any-response/any-tie-order cap-hit, candidate-ID pairing,
entered/left-top-K, incomplete-event-list handling) against hand-built `DecisionTrace`/
`CandidateTrace`/`AccuracyResponseDetail` objects — this is deliberately more rigorous than an
end-to-end call for these specific rules, since constructing a real scripted battle that triggers
a cap-hit in exactly one tie-order of exactly one response is fragile to script reliably, while the
rule itself is pure data-shape logic that deserves precise, deterministic unit coverage. A lighter
end-to-end integration test (Step 1b) proves the real wiring connects.

```python
# showdown_bot/tests/eval/test_accuracy_gate_b.py
from __future__ import annotations

import pytest

from showdown_bot.battle.decision_trace import (
    AccuracyEventTrace,
    AccuracyResponseDetail,
    AccuracyTieOrderTrace,
    CandidateTrace,
    DecisionTrace,
)
from showdown_bot.eval.accuracy_gate_b import (
    GateBResult,
    _chosen_candidate,
    candidate_any_cap_hit,
    candidate_events_complete,
    pair_candidates_by_id,
    run_gate_b,
)


def _detail(*, cap_hits: int, complete: bool, tie_orders: list[AccuracyTieOrderTrace] | None = None) -> AccuracyResponseDetail:
    return AccuracyResponseDetail(
        accuracy_leaf_count=4, accuracy_event_count=1, accuracy_branch_cap_hits=cap_hits,
        events_complete=complete, tie_orders=tie_orders or [], events=[],
    )


def _candidate(candidate_id: str, rank: int, score: float, details: list[AccuracyResponseDetail]) -> CandidateTrace:
    return CandidateTrace(
        candidate_id=candidate_id, joint_action=None, rank=rank, aggregate_score=score,
        score_vector=[score] * len(details), outcome_breakdowns=[], aggregate_breakdown=None,
        accuracy_details=details,
    )


def test_any_response_cap_hit_true_when_only_second_response_capped():
    # Response 0 clean, response 1 capped -- the OR rule must still flag the candidate.
    c = _candidate("A", 0, 1.0, [_detail(cap_hits=0, complete=True), _detail(cap_hits=1, complete=False)])
    assert candidate_any_cap_hit(c) is True
    assert candidate_events_complete(c) is False  # NOT complete, because response 1 isn't


def test_any_response_cap_hit_false_when_all_responses_clean():
    c = _candidate("A", 0, 1.0, [_detail(cap_hits=0, complete=True), _detail(cap_hits=0, complete=True)])
    assert candidate_any_cap_hit(c) is False
    assert candidate_events_complete(c) is True


def test_any_tie_order_cap_hit_is_already_folded_into_accuracy_branch_cap_hits():
    # A response whose OWN accuracy_branch_cap_hits is 2 (summed across two tie orders, one of
    # which capped) must still trip the any-response rule -- proving the "any tie order" case
    # is already covered by reading accuracy_branch_cap_hits directly, per Task 6's wiring.
    tie_orders = [
        AccuracyTieOrderTrace(tie_order="ours_first", weight=0.5, accuracy_leaf_count=2,
                                accuracy_branch_cap_hits=0, events_complete=True),
        AccuracyTieOrderTrace(tie_order="ours_last", weight=0.5, accuracy_leaf_count=2,
                                accuracy_branch_cap_hits=1, events_complete=False),
    ]
    detail = _detail(cap_hits=1, complete=False, tie_orders=tie_orders)  # summed: 0 + 1 = 1
    c = _candidate("A", 0, 1.0, [detail])
    assert candidate_any_cap_hit(c) is True
    assert any(t.accuracy_branch_cap_hits >= 1 for t in c.accuracy_details[0].tie_orders)


def test_chosen_candidate_falls_back_across_tera_suffix_mismatch():
    """Regression test for a real, confirmed pre-existing decision.py bug (found during Task 4):
    _maybe_tera can overlay a Tera flag onto the chosen line AFTER trace.candidates was already
    built from the pre-Tera candidate set, so trace.chosen_candidate_id can carry a ' tera' suffix
    matching no candidate_id verbatim. _chosen_candidate must recover via the tera-stripped
    fallback match (the same proven pattern Task 4's accuracy_baseline.py driver already
    validated against a real occurrence), not silently misbehave."""
    trace = DecisionTrace(
        chosen_candidate_id="(protect, moonblast->1 tera)",  # note the ' tera' suffix
        candidates=[
            _candidate("(protect, moonblast->1)", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
            _candidate("(protect, shadowball->1)", 1, 3.0, [_detail(cap_hits=0, complete=True)]),
        ],
    )
    resolved = _chosen_candidate(trace)
    assert resolved.candidate_id == "(protect, moonblast->1)"


def test_chosen_candidate_raises_when_unresolvable():
    """Fail loud, never silently None -- a silent miss here would make run_gate_b's cap-hit
    rule default to "not capped" for exactly the decisions where this occurs, silently biasing
    the gate's own verdict. This must surface as an exception (caught by run_gate_b's existing
    per-decision try/except and reported), not disappear into a false negative."""
    trace = DecisionTrace(
        chosen_candidate_id="(this matches nothing, not even stripped)",
        candidates=[
            _candidate("(protect, moonblast->1)", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        ],
    )
    with pytest.raises(RuntimeError):
        _chosen_candidate(trace)


def test_pair_candidates_by_id_stable_across_reordering():
    # accuracy_mode changing scores can reorder rank -- candidate_id pairing must not care.
    off_trace = DecisionTrace(candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("B", 1, 3.0, [_detail(cap_hits=0, complete=True)]),
    ])
    on_trace = DecisionTrace(candidates=[
        _candidate("B", 0, 6.0, [_detail(cap_hits=0, complete=True)]),  # B now ranks first
        _candidate("A", 1, 4.0, [_detail(cap_hits=1, complete=False)]),
    ])
    paired, entered, left = pair_candidates_by_id(off_trace, on_trace)
    assert set(paired) == {"A", "B"}
    off_a, on_a = paired["A"]
    assert off_a.rank == 0 and on_a.rank == 1  # correctly paired despite rank flip
    assert entered == [] and left == []


def test_pair_candidates_detects_entered_and_left_top_k():
    off_trace = DecisionTrace(candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("C", 1, 1.0, [_detail(cap_hits=0, complete=True)]),  # drops out on-run
    ])
    on_trace = DecisionTrace(candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("D", 1, 4.5, [_detail(cap_hits=0, complete=True)]),  # newly enters top-K
    ])
    paired, entered, left = pair_candidates_by_id(off_trace, on_trace)
    assert set(paired) == {"A"}
    assert entered == ["D"]
    assert left == ["C"]


def test_incomplete_event_list_never_reported_as_fully_explained():
    """Spec Sec.4: if events_complete is False, mechanically_explained must be False -- a
    diff whose event list is known-partial must never claim a complete explanation."""
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    class _StubTraceRun:
        """Minimal stand-in wired through a monkeypatched _decide_with_trace in the next test;
        this test exercises the pure row-construction helper directly."""

    from showdown_bot.eval.accuracy_gate_b import _diff_row_from_traces

    off_trace = DecisionTrace(chosen_candidate_id="A", candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("B", 1, 4.0, [_detail(cap_hits=0, complete=True)]),
    ])
    on_trace = DecisionTrace(chosen_candidate_id="B", candidates=[
        _candidate("B", 0, 6.0, [_detail(cap_hits=1, complete=False)]),  # capped, incomplete
        _candidate("A", 1, 4.0, [_detail(cap_hits=0, complete=True)]),
    ])
    row = _diff_row_from_traces(
        request_hash="req0", off_action="/choose move 1, move 1|rqid",
        on_action="/choose move 2, move 1|rqid", off_trace=off_trace, on_trace=on_trace,
        request=None,
    )
    assert row.events_complete is False
    assert row.mechanically_explained is False


def test_run_gate_b_reports_dropped_or_excluded_decisions_explicitly():
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    decisions = [
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.TEAM_PREVIEW, side="p1", turn=0,
            request_hash="tp0", log_prefix_hash="p0", _debug_prefix_line_count=1,
        ),
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.FORCE_SWITCH, side="p1", turn=3,
            request_hash="fs0", log_prefix_hash="p1", _debug_prefix_line_count=1,
        ),
    ]
    result = run_gate_b(decisions=decisions, battle_id_for=lambda d: "game0")
    assert result.excluded_team_preview_count == 1
    assert result.excluded_force_switch_count == 1
    assert result.n_decisions_compared == 0
```

- [ ] **Step 1b: Write a lighter end-to-end wiring test**

```python
# appended to showdown_bot/tests/eval/test_accuracy_gate_b.py
def test_run_gate_b_end_to_end_on_the_conftest_fixture_board(decision_fixture, monkeypatch):
    """Proves run_gate_b's real heuristic_choose_for_request(trace=...) wiring connects, using
    this project's existing decision_fixture/fake-backend convention (same one
    tests/test_accuracy_mode_wiring.py already uses) -- not a full real-calc integration run,
    just a connectivity/shape proof."""
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    req, kw = decision_fixture
    decision = ExtractedDecision(
        state=kw["state"], request=req, kind=RequestKind.MOVE, side="p1", turn=1,
        request_hash="real0", log_prefix_hash="realprefix0", _debug_prefix_line_count=1,
    )
    result = run_gate_b(
        decisions=[decision], battle_id_for=lambda d: "game0",
        book=kw["book"], calc=kw["calc"], oracle_factory=lambda: kw["oracle"],
        speed_oracle=kw["speed_oracle"], dex=kw["dex"],
    )
    assert result.n_decisions_compared == 1
    assert result.acceptance.no_exceptions is True
    assert result.acceptance.exceptions == []
    assert result.cap_hit_verdict is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_b.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `accuracy_gate_b.py`**

```python
# showdown_bot/src/showdown_bot/eval/accuracy_gate_b.py
"""Gate B: the confirmatory run. Replays real (state, request) pairs from the deduplicated
room_raw corpus through heuristic_choose_for_request off vs on, applies spec Sec.4's acceptance
rules, and produces the per-diff capture schema from spec Sec.5. Full deduplicated corpus only --
if infeasible, the caller reports INCONCLUSIVE/BLOCKED FOR COMPUTE, this module does not silently
sub-sample (spec Sec.6 item 6)."""

from __future__ import annotations

import copy
import os
from collections.abc import Callable
from dataclasses import dataclass, field

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.eval.accuracy_gate_stats import Verdict, verdict_for_cap_hit_rate
from showdown_bot.eval.decision_capture import normalize_choose
from showdown_bot.eval.decision_diff import classify_action_diff
from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind


@dataclass(frozen=True)
class AcceptanceSummary:
    no_exceptions: bool
    exceptions: list[tuple[str, str]]  # (request_hash, error message)
    off_path_byte_identical: bool | None  # verified separately by Task 4/7's frozen-baseline
    # diff, not recomputed here -- Gate B's own job is the off-vs-on comparison, not the
    # unset-vs-explicit-off env-parser check.
    latency_within_budget: bool | None  # None if not measured in this run


@dataclass(frozen=True)
class DecisionDiffRow:
    request_hash: str
    off_chosen_action: str
    on_chosen_action: str
    off_score: float | None
    on_score: float | None
    off_margin_to_runner_up: float | None
    on_margin_to_runner_up: float | None
    tera_changed: bool
    action_diff_kind: str  # classify_action_diff's taxonomy: FALLBACK/TERA/SWITCH/PROTECT/
    # ATTACK_MOVE/ATTACK_TARGET/OTHER_ACTION
    events_complete: bool
    mechanically_explained: bool  # NEVER True when events_complete is False (spec Sec.4)
    left_top_k: list[str]      # candidate_ids present off-run, absent on-run
    entered_top_k: list[str]   # candidate_ids present on-run, absent off-run


@dataclass
class GateBResult:
    n_decisions_compared: int
    excluded_team_preview_count: int
    excluded_force_switch_count: int
    diffs: list[DecisionDiffRow] = field(default_factory=list)
    acceptance: AcceptanceSummary | None = None
    cap_hit_verdict: Verdict | None = None
    cap_hit_verdict_detail: dict = field(default_factory=dict)


def _by_rank(trace: DecisionTrace, rank: int) -> CandidateTrace | None:
    """Spec Sec.5: select by rank FIELD, never list position -- candidates aren't guaranteed
    sorted by construction alone (see decision_trace.py's own rank-sortedness test)."""
    for c in trace.candidates:
        if c.rank == rank:
            return c
    return None


def _strip_tera_suffix(candidate_id: str) -> str:
    """`_label_ja` (decision.py) appends ' tera' per-slot when that slot terastallizes. Needed
    because of a confirmed pre-existing bug (found and independently verified during Task 4):
    `_maybe_tera` can overlay a Tera flag onto the chosen line AFTER `trace.candidates` was
    already built from the pre-Tera candidate set, so `trace.chosen_candidate_id` can legitimately
    contain a ' tera' suffix that matches no `candidate_id` in `trace.candidates` verbatim. Tera is
    never part of the enumerated candidate space itself, so at most one slot's suffix needs
    stripping and the stripped match is guaranteed unique when it exists -- same proof Task 4's
    `accuracy_baseline.py` driver already established and validated against a real occurrence
    (1/944 real decisions)."""
    return candidate_id.replace(" tera", "")


def _chosen_candidate(trace: DecisionTrace) -> CandidateTrace:
    """Raises RuntimeError (not silently returns None) if no candidate matches -- a silent
    None here would make `run_gate_b`'s cap-hit rule default to "not capped" for exactly the
    decisions where a Tera-related mismatch occurred, silently biasing the gate's own verdict.
    Fail loud instead; `run_gate_b`'s existing per-decision try/except already turns this into
    a reported exception rather than crashing the whole run."""
    for c in trace.candidates:
        if c.candidate_id == trace.chosen_candidate_id:
            return c
    stripped_target = _strip_tera_suffix(trace.chosen_candidate_id)
    fallback = [c for c in trace.candidates if _strip_tera_suffix(c.candidate_id) == stripped_target]
    if len(fallback) == 1:
        return fallback[0]
    raise RuntimeError(
        f"no candidate matches chosen_candidate_id={trace.chosen_candidate_id!r} "
        f"(exact or tera-stripped); found {len(fallback)} stripped matches, expected exactly 1 -- "
        f"candidate_ids present: {[c.candidate_id for c in trace.candidates]}"
    )


def candidate_any_cap_hit(candidate: CandidateTrace) -> bool:
    """Spec Sec.4's numerator rule: ANY of the candidate's scored opponent-response
    accuracy_details has accuracy_branch_cap_hits >= 1. That field is already summed across
    BOTH evaluated tie orderings when a response was scored under a genuine tie (Task 5/6's
    wiring), so this single flat check already covers "any response, any tie order" -- no
    separate nested tie-order loop is needed here."""
    return any(d.accuracy_branch_cap_hits >= 1 for d in candidate.accuracy_details)


def candidate_events_complete(candidate: CandidateTrace) -> bool:
    """True only if EVERY scored response's event list is complete (no branch_cap truncation
    anywhere for this candidate) -- False if any single response is incomplete."""
    return all(d.events_complete for d in candidate.accuracy_details)


def pair_candidates_by_id(
    off_trace: DecisionTrace, on_trace: DecisionTrace,
) -> tuple[dict[str, tuple[CandidateTrace, CandidateTrace]], list[str], list[str]]:
    """Spec Sec.5: off-run and on-run candidates for the "same" nominal action are paired by
    candidate_id, never by rank or list position -- accuracy_mode can reorder or reshuffle
    top-K membership. Returns (paired_by_id, entered_top_k, left_top_k), both sorted lists."""
    off_by_id = {c.candidate_id: c for c in off_trace.candidates}
    on_by_id = {c.candidate_id: c for c in on_trace.candidates}
    common = set(off_by_id) & set(on_by_id)
    left_top_k = sorted(set(off_by_id) - set(on_by_id))
    entered_top_k = sorted(set(on_by_id) - set(off_by_id))
    paired = {cid: (off_by_id[cid], on_by_id[cid]) for cid in common}
    return paired, entered_top_k, left_top_k


def _diff_row_from_traces(
    *, request_hash: str, off_action: str, on_action: str,
    off_trace: DecisionTrace, on_trace: DecisionTrace, request,
) -> DecisionDiffRow:
    _paired, entered_top_k, left_top_k = pair_candidates_by_id(off_trace, on_trace)
    off_top = _by_rank(off_trace, 0)
    on_top = _by_rank(on_trace, 0)
    off_runner_up = _by_rank(off_trace, 1)
    on_runner_up = _by_rank(on_trace, 1)
    on_chosen = _chosen_candidate(on_trace)  # raises if unresolvable; never silently None
    events_complete = candidate_events_complete(on_chosen)

    off_norm = normalize_choose(off_action.split("|", 1)[0].strip(), request) if request else {"kind": "joint", "slots": []}
    on_norm = normalize_choose(on_action.split("|", 1)[0].strip(), request) if request else {"kind": "joint", "slots": []}
    action_diff = classify_action_diff(off_norm, on_norm)

    return DecisionDiffRow(
        request_hash=request_hash, off_chosen_action=off_action, on_chosen_action=on_action,
        off_score=off_top.aggregate_score if off_top else None,
        on_score=on_top.aggregate_score if on_top else None,
        off_margin_to_runner_up=(
            off_top.aggregate_score - off_runner_up.aggregate_score
            if off_top and off_runner_up else None
        ),
        on_margin_to_runner_up=(
            on_top.aggregate_score - on_runner_up.aggregate_score
            if on_top and on_runner_up else None
        ),
        tera_changed="tera_changed" in action_diff.markers,
        action_diff_kind=action_diff.primary,
        events_complete=events_complete,
        mechanically_explained=events_complete,  # spec Sec.4: never claim a complete
        # mechanical explanation when the underlying event list is known-partial
        left_top_k=left_top_k, entered_top_k=entered_top_k,
    )


def _decide_with_trace(
    decision: ExtractedDecision, *, accuracy_on: bool, book, calc, oracle_factory, speed_oracle, dex,
) -> tuple[str, DecisionTrace]:
    if accuracy_on:
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
    else:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    trace = DecisionTrace()
    chosen = heuristic_choose_for_request(
        decision.request, state=copy.deepcopy(decision.state), book=book, our_side=decision.side,
        calc=calc, oracle=oracle_factory(), speed_oracle=speed_oracle, dex=dex, trace=trace,
    )
    return chosen, trace


def run_gate_b(
    *,
    decisions: list[ExtractedDecision],
    battle_id_for: Callable[[ExtractedDecision], str],
    book=None, calc=None, oracle_factory=None, speed_oracle=None, dex=None,
) -> GateBResult:
    move_decisions = [d for d in decisions if d.kind == RequestKind.MOVE]
    excluded_team_preview = sum(1 for d in decisions if d.kind == RequestKind.TEAM_PREVIEW)
    excluded_force_switch = sum(1 for d in decisions if d.kind == RequestKind.FORCE_SWITCH)

    diffs: list[DecisionDiffRow] = []
    per_decision_cap_hit: list[tuple[str, bool]] = []
    per_game_any_cap_hit: dict[str, bool] = {}
    exceptions: list[tuple[str, str]] = []

    try:
        for d in move_decisions:
            game_id = battle_id_for(d)
            per_game_any_cap_hit.setdefault(game_id, False)
            try:
                off_action, off_trace = _decide_with_trace(
                    d, accuracy_on=False, book=book, calc=calc,
                    oracle_factory=oracle_factory, speed_oracle=speed_oracle, dex=dex,
                )
                on_action, on_trace = _decide_with_trace(
                    d, accuracy_on=True, book=book, calc=calc,
                    oracle_factory=oracle_factory, speed_oracle=speed_oracle, dex=dex,
                )
                # _chosen_candidate can raise RuntimeError (a real, confirmed possibility --
                # see its own docstring on the tera/trace mismatch) -- deliberately kept INSIDE
                # this try block so such a decision is recorded as a per-decision exception,
                # not an uncaught crash that would lose every already-accumulated result.
                on_chosen = _chosen_candidate(on_trace)
                cap_hit_this_decision = candidate_any_cap_hit(on_chosen)
                if off_action != on_action:
                    diff_row = _diff_row_from_traces(
                        request_hash=d.request_hash, off_action=off_action, on_action=on_action,
                        off_trace=off_trace, on_trace=on_trace, request=d.request,
                    )
                else:
                    diff_row = None
            except Exception as exc:  # noqa: BLE001
                exceptions.append((d.request_hash, str(exc)))
                continue

            per_decision_cap_hit.append((game_id, cap_hit_this_decision))
            if cap_hit_this_decision:
                per_game_any_cap_hit[game_id] = True
            if diff_row is not None:
                diffs.append(diff_row)
    finally:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)

    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision_cap_hit,
        per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=len(per_decision_cap_hit),
    )

    return GateBResult(
        n_decisions_compared=len(per_decision_cap_hit),
        excluded_team_preview_count=excluded_team_preview,
        excluded_force_switch_count=excluded_force_switch,
        diffs=diffs,
        acceptance=AcceptanceSummary(
            no_exceptions=(len(exceptions) == 0), exceptions=exceptions,
            off_path_byte_identical=None, latency_within_budget=None,
        ),
        cap_hit_verdict=verdict,
        cap_hit_verdict_detail=detail,
    )
```

`classify_action_diff`'s real signature (`eval/decision_diff.py:96-98`) is
`classify_action_diff(baseline: dict, candidate: dict, *, baseline_stage=None,
candidate_stage=None) -> ActionDiff`, returning `ActionDiff(primary: str, markers: tuple[str,
...])` (`eval/decision_diff.py:79-81` — verified directly; note the field is `primary`, not
`kind`, despite `DecisionDiffRow.action_diff_kind`'s own name). `normalize_choose` expects the raw
`/choose ...` string (drop the trailing `|rqid` suffix `encode_choose` appends, as
`_diff_row_from_traces` already does via `.split("|", 1)[0]`).

- [ ] **Step 4: Run tests**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_b.py -v`
Expected: PASS (10 passed — 8 from the original design plus
`test_chosen_candidate_falls_back_across_tera_suffix_mismatch` and
`test_chosen_candidate_raises_when_unresolvable`, added to harden `_chosen_candidate` against a
real, confirmed pre-existing `decision.py` bug found during Task 4 — see that helper's own
docstring)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_gate_b.py showdown_bot/tests/eval/test_accuracy_gate_b.py
git commit -m "feat(eval): Gate B confirmatory-run orchestration, real trace-based cap-hit/diff rules"
```

---

## Task 11: Run Gate A + Gate B for real, produce report artifacts, closeout

**Files:**
- Create: `data/eval/accuracy-gate/gate-a-report.md`, `data/eval/accuracy-gate/gate-b-report.md`
  (or `.json` + rendered `.md`, matching `eval/decision_diff_report.py`'s existing
  `build_report_object`/`render_markdown` split — reuse that pattern, don't invent a new one)
- Create: `reports/2026-07-13-accuracy-offline-gate-verdict.md` (this project's established
  `reports/` convention for a closeout summary — see `reports/2026-07-12-accuracy-slice-closeout.md`
  for the exact style to match)

- [ ] **Step 1: Run the 50-decision dry-run, record the runtime extrapolation**

```bash
cd showdown_bot && python scripts/run_accuracy_baseline_freeze.py --dry-run-only
```

Record the extrapolated full-corpus runtime in the closeout report. If prohibitive, the entire
Gate B run's outcome is `INCONCLUSIVE / BLOCKED FOR COMPUTE` per spec §6 item 6 — report that
honestly rather than substituting a sample.

- [ ] **Step 2: Run Gate A across both boards × all 7 field variants**

```bash
cd showdown_bot && python -c "
from showdown_bot.eval.accuracy_gate_a import run_gate_a
result = run_gate_a()  # default: both boards (primary, single_target) x all 7 FIELD_VARIANTS
print(result.diff_count, len(result.rows), result.exception_count)
"
```

Write `data/eval/accuracy-gate/gate-a-report.md`, reporting per spec §4: no exceptions, diff count,
and explicitly labeled as a smoke test that "cannot license anything on its own" (spec §1).

- [ ] **Step 3: Run Gate B across the full deduplicated corpus**

```bash
cd showdown_bot && python -c "
import glob
from pathlib import Path
from showdown_bot.eval.room_raw_replay import deduplicate_battle_logs, extract_decisions_from_log
from showdown_bot.eval.accuracy_gate_b import run_gate_b
# Reuses Task 4 Step 5's real dedup wiring (correct manifest paths, verified G=85) and Task 2's
# deduplicate_battle_logs directly -- glob the same 4 room_raw directories, join against
# data/eval/t4/rerun/t4rerun-{run1,run2,prefix}.jsonl + data/eval/t6/t6-{run1,run2}.jsonl +
# data/eval/kaggle-validation/results.jsonl, then extract_decisions_from_log(...) on every kept
# file and pass the flattened decision list + a battle_id_for(d) closure (keyed off which kept
# file d came from) into run_gate_b(..., book=..., calc=..., oracle_factory=..., speed_oracle=...,
# dex=...) using the SAME real CalcClient/DamageOracle/SpeedOracle/SpeciesDex construction Task 9
# established, not a fresh ad-hoc one.
"
```

Write `data/eval/accuracy-gate/gate-b-report.md`: numerator/denominator/rate, bootstrap or
Clopper-Pearson detail (per which branch applied), the verdict (PASS/INCONCLUSIVE/FAIL), latency
figures, every decision diff with its full per-diff capture schema (spec §5, including
`left_top_k`/`entered_top_k`/`events_complete`/`mechanically_explained` from Task 10's
`DecisionDiffRow`), and the dedup report's separate files-found/unique-battles/
excluded-duplicates/final-G breakdown (spec §6 item 5's required separate reporting — do not fold
this into a single opaque number).

- [ ] **Step 4: Write the closeout report**

`reports/2026-07-13-accuracy-offline-gate-verdict.md` — summarize both gates' verdicts, restate
explicitly that **no default-on decision, strength claim, or Depth-2 Stage 3 work follows from this
report alone** (spec §1, §8), confirm the final deduplicated `G` equals the verified `85` (or, if
it doesn't, explain precisely why the corpus changed and that every downstream number in the plan
and spec was re-derived, not just this report), and flag the
`AccuracyDiagnostics.accuracy_required` naming-bug follow-up as still open and untouched (spec §3,
§8).

- [ ] **Step 5: Run the full test suite as a final regression gate**

Run: `cd showdown_bot && python -m pytest tests/ -v`
Expected: PASS, 0 failures, matching or exceeding the merged accuracy slice's last known-green
count (1645 passed / 1 skipped / 1 xfailed) plus this plan's new tests.

- [ ] **Step 6: Commit**

```bash
git add data/eval/accuracy-gate/ reports/2026-07-13-accuracy-offline-gate-verdict.md
git commit -m "docs(accuracy-gate): Gate A + Gate B results and closeout verdict"
```

- [ ] **Step 7: Update `docs/ROADMAP.md` and memory**

Update the P0 item 5 (`AccuracyDiagnostics`→`DecisionTrace`) status line to note this plan's
`CandidateTrace.accuracy_details` wiring partially addresses it (per spec §2.4's explicit "does not
close the whole item" scoping — do not overclaim). Do not add a new ROADMAP item for the
default-on/strength-baseline/Depth-2-Stage-3 decisions this gate feeds — those remain the user's
own separate, explicit next steps, not something this plan schedules.

---

## Self-Review

**1. Spec coverage:**
- §1 (Gate A/B split, verified-G framing) → Task 9, 10, and the Task 2 integration test's exact
  `report.final_g == 85` real-corpus assertion.
- §2.1-2.3 (`LineEvaluation`/`_evaluate_line_details`, event-union fix, tie-averaging merge,
  determinism proof) → Task 5.
- §2.4 (`CandidateTrace.accuracy_details` wiring) → Task 6.
- §3 (accuracy_required naming bug, out of scope) → explicitly noted as untouched in Task 11 Step
  4's closeout report; no task modifies `AccuracyDiagnostics`.
- §4 (acceptance rules: byte-identical twice, cap-hit rate + bootstrap + zero-event Clopper-Pearson,
  latency, mechanically-plausible-cause + events_complete) → Task 4/7 (byte-identical twice), Task
  8 (statistics), Task 10 (`candidate_any_cap_hit`/`candidate_events_complete`/
  `mechanically_explained`, unit-tested directly against the exact any-response/any-tie-order rule),
  Task 11 (applied in the real run).
- §5 (per-diff capture schema: rank-field lookup via `_by_rank`, `candidate_id` pairing via
  `pair_candidates_by_id` with dedicated entered/left-top-K tests, events_complete flagging) →
  Task 10's `DecisionDiffRow`/`_diff_row_from_traces`, real code against the real
  `heuristic_choose_for_request(trace=...)`/`DecisionTrace`/`CandidateTrace` API — no placeholder.
- §6 items 1-4 (causality, reconnect dedup, hero side, request classification) → Task 1.
- §6 item 5 (global dedup, corrected identity key and manifest sources) → Task 2.
- §6 item 6 (full-corpus-only policy, INCONCLUSIVE/BLOCKED FOR COMPUTE, G>=59 fallback floor) →
  Task 4 Step 5, Task 10/11, Task 8's `minimum_g_for_zero_event_pass`.
- §6 items 7-8 (manifest, game clustering) → Task 4 Step 5's dedup-report output, Task 8's
  game-clustered bootstrap.
- §6 item 9 (hermetic fixtures) → Task 3.
- §7 (exact test list, hard-checkpoint sequencing, environment/commit/float provenance) → Tasks
  1-8 collectively implement every named test; Task 4/7 implement the checkpoint sequencing and
  provenance fields exactly.
- §8 (out of scope: 05 panel, accuracy_required fix, ranking-to-trace caching refactor,
  default-on/strength/Depth-2) → none of Tasks 1-11 touch any of these; Task 11 Step 4 states this
  explicitly in the closeout report.

**2. Placeholder scan (re-run after the round-7 correction that removed the two placeholders
originally in Tasks 9 and 10):** grepping this plan for `PLACEHOLDER`, `TBD`, and semantically
empty stand-ins (`pass  # TODO`, hardcoded `False`/`""` standing in for real logic) finds **zero**
remaining instances. Both tasks that previously carried an explicit "must be replaced before done"
placeholder are now fully concrete:
- Task 9 (Gate A) builds its 7 `FieldState` variants directly against the real dataclass, reuses
  `bench_accuracy_latency.py`'s real board verbatim, and adds one additional real hand-built board
  — no team-file loader was invented or stubbed; the "1-2 panel archetypes" spec wording is
  explicitly and honestly reinterpreted (stated inline in Task 9, not silently) given no
  team-file-to-`BattleState` loader exists for offline direct calls.
- Task 10 (Gate B) computes the cap-hit rule, candidate pairing, and diff classification against
  the real `CandidateTrace.accuracy_details`/`DecisionTrace`/`heuristic_choose_for_request(
  trace=...)` API, reusing `eval/decision_capture.py`'s `normalize_choose` and
  `eval/decision_diff.py`'s `classify_action_diff` rather than reimplementing diff logic. Every
  rule the user's review specifically named (any-response/any-tie-order cap-hit, candidate-ID
  pairing stable across rank reordering, entered/left-top-K, incomplete-event-list handling) has
  its own dedicated unit test against hand-built trace objects (Task 10 Step 1), plus one lighter
  end-to-end wiring test (Step 1b) using this project's existing `decision_fixture` fake-backend
  convention.
- **Executing agent/reviewer: re-run this exact scan** (`grep -riE "PLACEHOLDER|\bTBD\b"` across
  every file this plan creates) as part of Task 10's own code-quality review before marking it
  complete — this is a standing requirement for this specific plan, not a one-time check done
  while writing it, since a subagent re-implementing these tasks from the plan's prose could
  reintroduce a stub without noticing.

**3. Type consistency:** `AccuracyEventDetail`/`TieOrderEvaluation`/`LineEvaluation` (Task 5,
`evaluate.py`) and `AccuracyEventTrace`/`AccuracyTieOrderTrace`/`AccuracyResponseDetail` (Task 6,
`decision_trace.py`) intentionally use matching-but-distinct names across the two layers (`Detail`
suffix = internal evaluate.py working type, `Trace` suffix = exported decision_trace.py schema
type, matching the spec's own naming convention) — verified field-for-field consistent between
Task 5's construction code and Task 6's `_breakdowns_for` consumption code (same field names:
`tie_order`, `weight`, `accuracy_leaf_count`, `accuracy_branch_cap_hits`, `events_complete`).
`ExtractedDecision` (Task 1) is consumed identically by Task 4 (`freeze_baseline`), Task 9/10 (Gate
A/B orchestration) — same field names (`request_hash`, `log_prefix_hash`, `side`, `turn`, `kind`,
`state`, `request`) throughout. `DedupReport`/`SeedIdentity` (Task 2, renamed from the first
draft's `ScheduleIdentity` to reflect the corrected `(seed_base, seed_index)`-only key) are
consumed by Task 4 Step 5's driver script with matching field names (`kept`, `excluded`,
`final_g`). `Task 10`'s `candidate_any_cap_hit`/`candidate_events_complete`/
`pair_candidates_by_id` are pure functions over `CandidateTrace`/`DecisionTrace` (Task 6's real
types, not a parallel ad-hoc shape) — verified their field accesses
(`c.accuracy_details[i].accuracy_branch_cap_hits`, `.events_complete`, `c.candidate_id`, `c.rank`)
match Task 6's dataclass definitions exactly.

**4. Round-7 correction summary** (for the reviewer's context — this plan went through one
real-data-verification correction cycle after its first draft): the first draft's Task 2 joined
`data/eval/t4/rerun/room_raw/{run1,run2,prefix}` against the wrong manifest files (0/112 t4 files
matched) and used a `schedule_hash`-inclusive identity key that would have under-counted
`prefix`/`kaggle-validation` as a third independent group (95 instead of the correct 85). Both are
fixed in this version — see the plan's provenance-facts section for the exact verification
performed. Tasks 9 and 10 also went from placeholder-driven drafts to fully real implementations
against the actual `heuristic_choose_for_request`/`FieldState`/`DecisionTrace` APIs, verified this
session rather than assumed from the spec's prose.

Execution choice, per this project's established pattern for plans this size (the merged
accuracy-hit-probability slice used subagent-driven-development with two-stage review per task,
extra scrutiny on the two highest-risk `battle/` tasks):

**1. Subagent-Driven (recommended)** — fresh subagent per task, spec-compliance review then
code-quality review between tasks, matching exactly how the prior accuracy slice was executed this
session. Given Tasks 5 and 6 touch the live decision pipeline (same risk class as that slice's Task
4/5), and Task 2's dedup logic is similarly high-stakes for this plan's own statistical validity,
recommend the same "two-stage review, no batching, extra scrutiny on the flagged tasks" discipline
— with Task 2 specifically getting an additional provenance/dedup-focused review pass, and Task 9/10
getting a review pass that checks their reported numbers against a real (even if small-scale) run,
not just code inspection, per the user's explicit request this round.

**2. Inline Execution** — batch execution in this session with checkpoints.

**Which approach?**

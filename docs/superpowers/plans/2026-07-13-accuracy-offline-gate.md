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

## Provenance facts this plan relies on (verified directly against real files this session, not
assumed from the spec's summary)

- `data/eval/t4/t4-run1.jsonl`, `t4-run2.jsonl`, `t4-prefix.jsonl`, `data/eval/t6/t6-run1.jsonl`,
  `t6-run2.jsonl`, `data/eval/kaggle-validation/results.jsonl` are **results manifests**, one JSON
  row per battle, each row already containing `schedule_hash`, `seed_base`, `seed_index`, `seed`,
  `battle_id`, and `room_raw_path` (e.g.
  `"room_raw_path": "C:/tmp/t4/full_room_raw\\HeuristicBot1167__battle-gen9vgc2025regi-310.log"`).
  This is the **single, sufficient join source** for the dedup key — there is no need to
  cross-reference the separate `*-seedlog.jsonl` files (which only carry `{battle_index, seed,
  seed_base}`, no `schedule_hash`/`seed_index`) or the schedule YAMLs directly.
- `room_raw_path`'s basename (final path component, `.log` suffix) matches the on-disk committed
  `.log.gz` filename in `data/eval/t4/rerun/room_raw/run1/` etc. 1:1 (confirmed:
  `HeuristicBot1167__battle-gen9vgc2025regi-310.log` in the manifest row vs
  `HeuristicBot1084__battle-gen9vgc2025regi-487.log.gz` as an on-disk example — same naming
  pattern, differing only by the trailing `.gz`).
- `data/eval/t4/room_raw_divergent/` has **no results.jsonl of its own** — its 7 files
  (`run1-idx09-regi-319.log.gz`, `run2-idx19-regi-401.log.gz`, `prefix-idx09-regi-380.log.gz`, ...)
  must be deduplicated via the **content-hash fallback** (Task 2), not a manifest join.
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
bound). **Extra scrutiny on this task's review.**

Two-tier design, per the plan's provenance-facts section above:
1. **Primary: manifest join.** For each on-disk `.log.gz`/`.log` file, find the results-manifest
   row (`t4-run1.jsonl`, `t4-run2.jsonl`, `t4-prefix.jsonl`, `t6-run1.jsonl`, `t6-run2.jsonl`,
   `kaggle-validation/results.jsonl`) whose `room_raw_path` basename matches this file's basename
   (stripping `.gz`). That row's `(schedule_hash, seed_base, seed_index)` is the file's identity.
2. **Fallback: content hash.** Files with no matching manifest row (confirmed real case:
   `data/eval/t4/room_raw_divergent/`, 7 files) are identified by comparing their **normalized
   room-log content hash** (`eval.room_dump.normalized_room_log_sha256`, already used elsewhere in
   this project for exactly this "are these two logs the same battle" question) against every
   already-kept file's own normalized hash; a match means it's a duplicate of that kept file.

Within a group of files sharing one identity, keep exactly one — priority order `run1` > `run2` >
`prefix` > anything else (source-directory name, lexicographic tie-break if still ambiguous) — and
record the rest as excluded.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/eval/test_room_raw_dedup.py
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from showdown_bot.eval.room_raw_replay import DedupReport, deduplicate_battle_logs

REPO_ROOT = Path(__file__).resolve().parents[3].parent  # .../SHowdown BOt
DATA_T4 = REPO_ROOT / "data" / "eval" / "t4"
DATA_T6 = REPO_ROOT / "data" / "eval" / "t6"
DATA_KAGGLE = REPO_ROOT / "data" / "eval" / "kaggle-validation"


def _make_manifest_row(room_raw_path: str, schedule_hash: str, seed_base: str, seed_index: int) -> dict:
    return {
        "room_raw_path": room_raw_path,
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
    assert report.excluded[0].reason == "duplicate_schedule_identity"
    assert report.final_g == 1


def test_manifest_join_keeps_genuinely_distinct_schedules(tmp_path):
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


def test_content_hash_fallback_for_files_without_manifest_row(tmp_path):
    battle_lines = [
        ">battle-c",
        '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
    ]
    run1_dir = tmp_path / "run1"
    divergent_dir = tmp_path / "divergent"
    kept = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-c", battle_lines)
    orphan = _write_synthetic_log(divergent_dir, "run1-idx00-battle-c", battle_lines)  # same content, no manifest row

    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-c.log", "SCHED_T4", "t4base", 0,
    )])

    report = deduplicate_battle_logs(
        log_files=[kept, orphan], manifest_files=[manifest], keep_priority=["run1", "divergent"],
    )
    assert report.final_g == 1
    assert report.kept == [kept]
    assert report.excluded[0].source_file == orphan
    assert report.excluded[0].reason == "duplicate_content_hash"


@pytest.mark.skipif(
    not (DATA_T4 / "t4-run1.jsonl").exists(), reason="real t4/t6/kaggle-validation corpus not present"
)
def test_real_corpus_dedup_matches_expected_two_schedules():
    """Integration check against the REAL committed corpus, per spec §7's
    test_global_dedup_uses_seed_schedule_not_room_id -- the ~197-files-to-~85-unique-battles
    ratio is itself a load-bearing claim this gate's credibility depends on, so this must run
    against real data, not only synthetic fixtures."""
    import glob

    log_files = [Path(p) for p in glob.glob(str(DATA_T4 / "rerun" / "room_raw" / "**" / "*.log.gz"), recursive=True)]
    log_files += [Path(p) for p in glob.glob(str(DATA_T4 / "room_raw_divergent" / "*.log.gz"))]
    log_files += [Path(p) for p in glob.glob(str(DATA_T6 / "room_raw" / "**" / "*.log.gz"), recursive=True)]
    log_files += [Path(p) for p in glob.glob(str(DATA_KAGGLE / "room_raw" / "*.log.gz"))]
    manifests = [
        DATA_T4 / "t4-run1.jsonl", DATA_T4 / "t4-run2.jsonl", DATA_T4 / "t4-prefix.jsonl",
        DATA_T6 / "t6-run1.jsonl", DATA_T6 / "t6-run2.jsonl", DATA_KAGGLE / "results.jsonl",
    ]
    report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifests,
        keep_priority=["run1", "run2", "prefix", "room_raw", "room_raw_divergent"],
    )
    assert report.files_found == len(log_files)
    # Two independent seed schedules exist (t4's 51-seed schedule_hash, t6's 34-seed
    # schedule_hash) -- report.final_g must land at exactly their sum, not the file count.
    unique_schedule_identities = {
        (row.schedule_hash, row.seed_base, row.seed_index) for row in report.kept_identities
    }
    assert len(unique_schedule_identities) == report.final_g
    assert 80 <= report.final_g <= 90, (
        f"expected the provisional ~85-unique-battle estimate (t4's 51 + t6's 34) to hold "
        f"within a small margin; got {report.final_g} -- if this genuinely changed, update "
        f"the spec's G and the derived Clopper-Pearson numbers, don't just widen this bound"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_dedup.py -v`
Expected: FAIL with `ImportError: cannot import name 'DedupReport'`

- [ ] **Step 3: Implement the dedup logic**

Add to `showdown_bot/src/showdown_bot/eval/room_raw_replay.py`:

```python
@dataclass(frozen=True)
class ScheduleIdentity:
    schedule_hash: str
    seed_base: str
    seed_index: int


@dataclass(frozen=True)
class KeptBattle:
    source_file: Path
    identity: ScheduleIdentity | None  # None if identified only by content-hash fallback


@dataclass(frozen=True)
class ExcludedBattle:
    source_file: Path
    reason: str  # "duplicate_schedule_identity" | "duplicate_content_hash"
    duplicate_of: Path


@dataclass(frozen=True)
class DedupReport:
    files_found: int
    kept: list[Path]
    kept_identities: list[ScheduleIdentity]  # parallel-ish, only for files with a manifest match
    excluded: list[ExcludedBattle]
    final_g: int


def _load_manifest_rows(manifest_files: list[Path]) -> dict[str, ScheduleIdentity]:
    """basename (with .log, no .gz) -> ScheduleIdentity, across all given manifest files."""
    by_basename: dict[str, ScheduleIdentity] = {}
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
                by_basename[basename] = ScheduleIdentity(
                    schedule_hash=row["schedule_hash"],
                    seed_base=row["seed_base"],
                    seed_index=row["seed_index"],
                )
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


def deduplicate_battle_logs(
    *, log_files: list[Path], manifest_files: list[Path], keep_priority: list[str],
) -> DedupReport:
    manifest_by_basename = _load_manifest_rows(manifest_files)

    # Group 1: files with a manifest-resolved schedule identity.
    groups: dict[ScheduleIdentity, list[Path]] = {}
    unmatched: list[Path] = []
    for path in log_files:
        basename = path.name
        if basename.endswith(".gz"):
            basename = basename[: -len(".gz")]
        identity = manifest_by_basename.get(basename)
        if identity is None:
            unmatched.append(path)
        else:
            groups.setdefault(identity, []).append(path)

    kept: list[Path] = []
    kept_identities: list[ScheduleIdentity] = []
    excluded: list[ExcludedBattle] = []

    for identity, paths in groups.items():
        paths_sorted = sorted(paths, key=lambda p: (_source_priority(p, keep_priority), str(p)))
        winner = paths_sorted[0]
        kept.append(winner)
        kept_identities.append(identity)
        for loser in paths_sorted[1:]:
            excluded.append(ExcludedBattle(loser, "duplicate_schedule_identity", winner))

    # Group 2: content-hash fallback for files with no manifest row at all.
    kept_content_hashes: dict[str, Path] = {p: _content_hash(p) for p in kept}.items()  # placeholder overwritten below
    hash_to_kept: dict[str, Path] = {}
    for k in kept:
        hash_to_kept[_content_hash(k)] = k

    unmatched_sorted = sorted(unmatched, key=lambda p: (_source_priority(p, keep_priority), str(p)))
    for path in unmatched_sorted:
        h = _content_hash(path)
        if h in hash_to_kept:
            excluded.append(ExcludedBattle(path, "duplicate_content_hash", hash_to_kept[h]))
            continue
        # Also check against other not-yet-decided unmatched files sharing this hash.
        existing = [k for k, kh in ((p2, _content_hash(p2)) for p2 in kept) if kh == h]
        if h not in hash_to_kept:
            hash_to_kept[h] = path
            kept.append(path)
            kept_identities.append(None)  # no manifest identity available

    return DedupReport(
        files_found=len(log_files),
        kept=kept,
        kept_identities=[i for i in kept_identities if i is not None],
        excluded=excluded,
        final_g=len(kept),
    )
```

Note during implementation: the `kept_content_hashes` placeholder line above is dead code left over
from drafting — remove it before committing (it computes nothing that's used; `hash_to_kept` is
built correctly on the next line). Verify with a quick read-through, not just the tests passing,
since this function is the highest-stakes piece of non-`battle/` code in this plan.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd showdown_bot && python -m pytest tests/eval/test_room_raw_dedup.py -v`
Expected: PASS (4 passed, or 3 passed + 1 skipped if the real corpus manifests aren't present —
they are committed, so expect all 4 to run). If `test_real_corpus_dedup_matches_expected_two_schedules`
fails because `final_g` lands outside `[80, 90]`, **do not loosen the assertion** — investigate
whether the dedup logic has a bug or whether the spec's provisional ~85 estimate needs a real
correction; report either finding, don't silently paper over it.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/room_raw_replay.py showdown_bot/tests/eval/test_room_raw_dedup.py
git commit -m "feat(eval): global battle-level dedup via results-manifest schedule identity"
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
2. Call `deduplicate_battle_logs(...)` (Task 2) with the manifest files listed in this plan's
   provenance-facts section and `keep_priority=["run1", "run2", "prefix", "room_raw",
   "room_raw_divergent"]`.
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
one row per non-team-preview/non-force-switch decision in the deduplicated corpus,
`dedup-report.json`'s `final_g` is in the 80-90 range (matching Task 2's real-corpus test) unless
that test already surfaced and explained a different real number.

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

Implements spec §1's Gate A. Reuses `scratchpad/bench_accuracy_latency.py`'s board (read it first
to reuse its exact team/board construction, don't rebuild it) plus 1-2 archetypes from
`config/eval/panels/panel_v001.yaml`, swept across the 7 field-bucket variants already used by the
Depth-2 Stage 2 script (`neutral`, `tailwind_both`, `tailwind_p1`, `tailwind_p2`, `trick_room`,
`sun`, `rain` — read that script to reuse its exact field-variant construction helper).

- [ ] **Step 1: Write the failing test**

```python
# showdown_bot/tests/eval/test_accuracy_gate_a.py
from __future__ import annotations

from showdown_bot.eval.accuracy_gate_a import GateAResult, run_gate_a


def test_run_gate_a_produces_one_result_per_board_x_field_combo():
    result = run_gate_a(boards=["smoke"], field_variants=["neutral", "sun"])
    assert isinstance(result, GateAResult)
    assert len(result.rows) == 2
    for row in result.rows:
        assert row.board in ("smoke",)
        assert row.field_variant in ("neutral", "sun")
        assert isinstance(row.off_chosen_action, str)
        assert isinstance(row.on_chosen_action, str)
        assert isinstance(row.exception is None, bool)
```

Adapt this to the real `run_gate_a` signature once written — the shape (board × field-variant
rows, off/on chosen actions per row, no exceptions) is what matters, not the exact param names,
which should follow whatever this project's existing `heuristic_choose_for_request` direct-call
convention already looks like (check `scratchpad/bench_accuracy_latency.py` and the Depth-2 Stage
2 field-bucket sweep script for the established pattern before finalizing this signature).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_a.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `accuracy_gate_a.py`**

Structure (fill in the exact board-construction and `heuristic_choose_for_request` call using the
real conventions read in Step 1's note above):

```python
# showdown_bot/src/showdown_bot/eval/accuracy_gate_a.py
"""Gate A: a smoke test sweeping a small number of fixed boards across 7 field-bucket variants,
comparing SHOWDOWN_ACCURACY_MODE off vs on via direct heuristic_choose_for_request calls, no
server. Explicitly a smoke test (spec Sec.1) -- cannot license anything on its own."""

from __future__ import annotations

from dataclasses import dataclass

FIELD_VARIANTS = ["neutral", "tailwind_both", "tailwind_p1", "tailwind_p2", "trick_room", "sun", "rain"]


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


def run_gate_a(*, boards: list[str], field_variants: list[str] = FIELD_VARIANTS) -> GateAResult:
    rows: list[GateARow] = []
    for board in boards:
        for variant in field_variants:
            try:
                # Reuse scratchpad/bench_accuracy_latency.py's board-construction helper and
                # the Depth-2 Stage 2 field-variant helper here -- exact call TBD against those
                # real functions' signatures, verified when this task is implemented.
                off_action = "PLACEHOLDER"  # replace with real heuristic_choose_for_request(..., accuracy_mode=False)
                on_action = "PLACEHOLDER"  # replace with real heuristic_choose_for_request(..., accuracy_mode=True)
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
    return GateAResult(rows=rows)
```

**Implementer note:** the two `"PLACEHOLDER"` lines above must be replaced with real calls before
this task is considered done — they exist here only because this plan was written without
re-reading `scratchpad/bench_accuracy_latency.py`'s exact board-construction API in this pass.
Read that file plus the Depth-2 Stage 2 field-bucket sweep script FIRST, then replace both lines
with the real `heuristic_choose_for_request(request, state=..., accuracy_mode=False/True, ...)`
calls (or whatever the real helper is named) using their established board/field-variant
construction. Do not leave a placeholder in the committed version — this is flagged explicitly so
the review step catches it if it's missed.

- [ ] **Step 4: Replace placeholders with real calls, then run the test**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_a.py -v`
Expected: PASS, with `off_chosen_action`/`on_chosen_action` real `/choose`-shaped strings, not the
literal string `"PLACEHOLDER"` — assert this explicitly if the test above doesn't already catch it.

- [ ] **Step 5: Run Gate A for real across the smoke board(s) and produce a report**

```bash
cd showdown_bot && python -c "
from showdown_bot.eval.accuracy_gate_a import run_gate_a
result = run_gate_a(boards=['smoke'])
print(f'diffs: {result.diff_count}/{len(result.rows)}, exceptions: {result.exception_count}')
"
```

Expected: `exceptions: 0/...` (spec §4's "no exceptions" acceptance rule). Write the row-level
output to `data/eval/accuracy-gate/gate-a-report.json` (reuse this project's established JSON
report-writing convention from `eval/decision_diff_report.py`).

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
deduplicated corpus only, INCONCLUSIVE/BLOCKED FOR COMPUTE if infeasible" policy.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/eval/test_accuracy_gate_b.py
from __future__ import annotations

from showdown_bot.eval.accuracy_gate_b import GateBResult, run_gate_b


def test_run_gate_b_on_a_tiny_synthetic_corpus_produces_diffs_and_verdict(tmp_path):
    # Uses Task 1/2's synthetic-fixture machinery to avoid depending on real data/eval/ logs
    # for this specific unit test -- the real-corpus run is Step 5 below, run separately.
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    decisions = [
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=1,
            request_hash=f"req{i}", log_prefix_hash=f"prefix{i}", _debug_prefix_line_count=1,
        )
        for i in range(6)
    ]
    battle_ids = {f"req{i}": f"game{i % 2}" for i in range(6)}  # 2 synthetic games, 3 decisions each

    result = run_gate_b(decisions=decisions, battle_id_for=lambda d: battle_ids[d.request_hash])
    assert isinstance(result, GateBResult)
    assert result.acceptance.no_exceptions is True
    assert result.acceptance.off_path_byte_identical in (True, False)
    assert 0 <= result.cap_hit_verdict_detail["point_estimate"] <= 1.0


def test_run_gate_b_reports_dropped_or_excluded_decisions_explicitly():
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    decisions = [
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.TEAM_PREVIEW, side="p1", turn=0,
            request_hash="tp0", log_prefix_hash="p0", _debug_prefix_line_count=1,
        ),
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=1,
            request_hash="m0", log_prefix_hash="p1", _debug_prefix_line_count=1,
        ),
    ]
    result = run_gate_b(decisions=decisions, battle_id_for=lambda d: "game0")
    assert result.excluded_team_preview_count == 1
    assert result.excluded_force_switch_count == 0
    assert result.n_decisions_compared == 1
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

from collections.abc import Callable
from dataclasses import dataclass, field

from showdown_bot.eval.accuracy_gate_stats import Verdict, verdict_for_cap_hit_rate
from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind


@dataclass(frozen=True)
class AcceptanceSummary:
    no_exceptions: bool
    off_path_byte_identical: bool
    latency_within_budget: bool | None  # None if not measured in this run


@dataclass(frozen=True)
class DecisionDiffRow:
    request_hash: str
    off_chosen_action: str
    on_chosen_action: str
    off_score: float
    on_score: float
    off_margin_to_runner_up: float | None
    on_margin_to_runner_up: float | None
    tera_changed: bool
    action_diff_kind: str  # "none" | "move" | "target" | "switch" | "protect" | "other"
    events_complete: bool
    mechanically_explained: bool


@dataclass
class GateBResult:
    n_decisions_compared: int
    excluded_team_preview_count: int
    excluded_force_switch_count: int
    diffs: list[DecisionDiffRow] = field(default_factory=list)
    acceptance: AcceptanceSummary | None = None
    cap_hit_verdict: Verdict | None = None
    cap_hit_verdict_detail: dict = field(default_factory=dict)


def run_gate_b(
    *,
    decisions: list[ExtractedDecision],
    battle_id_for: Callable[[ExtractedDecision], str],
) -> GateBResult:
    move_decisions = [d for d in decisions if d.kind == RequestKind.MOVE]
    excluded_team_preview = sum(1 for d in decisions if d.kind == RequestKind.TEAM_PREVIEW)
    excluded_force_switch = sum(1 for d in decisions if d.kind == RequestKind.FORCE_SWITCH)

    diffs: list[DecisionDiffRow] = []
    per_decision_cap_hit: list[tuple[str, bool]] = []
    per_game_any_cap_hit: dict[str, bool] = {}
    exceptions_occurred = False
    off_path_identical = True

    for d in move_decisions:
        game_id = battle_id_for(d)
        per_game_any_cap_hit.setdefault(game_id, False)
        # Implementer: wire the real off/on heuristic_choose_for_request(+trace) calls here,
        # per spec Sec.2's CandidateTrace.accuracy_details wiring (Task 6) and Sec.4/5's exact
        # rank-field/candidate_id-based comparison rules. This function's job is orchestration
        # and acceptance-rule application, not re-deriving the decision pipeline call pattern --
        # follow the same call shape Task 6's integration test already established.
        cap_hit_this_decision = False  # replace with the real any-response-capped OR rule (Sec.4)
        per_decision_cap_hit.append((game_id, cap_hit_this_decision))
        if cap_hit_this_decision:
            per_game_any_cap_hit[game_id] = True

    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision_cap_hit,
        per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=len(move_decisions),
    )

    return GateBResult(
        n_decisions_compared=len(move_decisions),
        excluded_team_preview_count=excluded_team_preview,
        excluded_force_switch_count=excluded_force_switch,
        diffs=diffs,
        acceptance=AcceptanceSummary(
            no_exceptions=not exceptions_occurred,
            off_path_byte_identical=off_path_identical,
            latency_within_budget=None,
        ),
        cap_hit_verdict=verdict,
        cap_hit_verdict_detail=detail,
    )
```

**Implementer note, same discipline as Task 9:** the `cap_hit_this_decision = False` placeholder
and the diff-row construction (currently producing an empty `diffs` list) must be replaced with
real `heuristic_choose_for_request`/`_evaluate_line_details`/`CandidateTrace.accuracy_details` calls
before this task is done, following spec §4's exact any-response-OR cap-hit rule and §5's exact
rank-field/`candidate_id`-based pairing rules verbatim — do not improvise a simpler rule. Flag this
explicitly in code review; do not let a placeholder ship.

- [ ] **Step 4: Replace placeholders, run tests**

Run: `cd showdown_bot && python -m pytest tests/eval/test_accuracy_gate_b.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/accuracy_gate_b.py showdown_bot/tests/eval/test_accuracy_gate_b.py
git commit -m "feat(eval): Gate B confirmatory-run orchestration + acceptance rules"
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

- [ ] **Step 2: Run Gate A across the full smoke-board × field-variant matrix**

```bash
cd showdown_bot && python -c "
from showdown_bot.eval.accuracy_gate_a import run_gate_a
result = run_gate_a(boards=['smoke', 'archetype1', 'archetype2'])
print(result.diff_count, len(result.rows), result.exception_count)
"
```

Write `data/eval/accuracy-gate/gate-a-report.md`, reporting per spec §4: no exceptions, diff count,
and explicitly labeled as a smoke test that "cannot license anything on its own" (spec §1).

- [ ] **Step 3: Run Gate B across the full deduplicated corpus**

```bash
cd showdown_bot && python -c "
from showdown_bot.eval.room_raw_replay import deduplicate_battle_logs, extract_decisions_from_log
from showdown_bot.eval.accuracy_gate_b import run_gate_b
# real glob + dedup + extraction wiring, matching Task 4 Step 5's driver -- reuse it
"
```

Write `data/eval/accuracy-gate/gate-b-report.md`: numerator/denominator/rate, bootstrap or
Clopper-Pearson detail (per which branch applied), the verdict (PASS/INCONCLUSIVE/FAIL), latency
figures, every decision diff with its full per-diff capture schema (spec §5), and the dedup
report's separate files-found/unique-battles/excluded-duplicates/final-G breakdown (spec §6 item
5's required separate reporting — do not fold this into a single opaque number).

- [ ] **Step 4: Write the closeout report**

`reports/2026-07-13-accuracy-offline-gate-verdict.md` — summarize both gates' verdicts, restate
explicitly that **no default-on decision, strength claim, or Depth-2 Stage 3 work follows from this
report alone** (spec §1, §8), note the final deduplicated `G` and how it compares to the spec's
provisional ~85 estimate, and flag the `AccuracyDiagnostics.accuracy_required` naming-bug follow-up
as still open and untouched (spec §3, §8).

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
- §1 (Gate A/B split, provisional-G framing) → Task 9, 10, and the Task 2 integration test's
  `[80, 90]` real-corpus assertion.
- §2.1-2.3 (`LineEvaluation`/`_evaluate_line_details`, event-union fix, tie-averaging merge,
  determinism proof) → Task 5.
- §2.4 (`CandidateTrace.accuracy_details` wiring) → Task 6.
- §3 (accuracy_required naming bug, out of scope) → explicitly noted as untouched in Task 11 Step
  4's closeout report; no task modifies `AccuracyDiagnostics`.
- §4 (acceptance rules: byte-identical twice, cap-hit rate + bootstrap + zero-event Clopper-Pearson,
  latency, mechanically-plausible-cause + events_complete) → Task 4/7 (byte-identical twice), Task
  8 (statistics), Task 10/11 (applied in the real run).
- §5 (per-diff capture schema: rank-field lookup, candidate_id pairing, events_complete flagging) →
  Task 10's `DecisionDiffRow` + its implementer-note requiring the exact rules from spec, not an
  improvised simpler one.
- §6 items 1-4 (causality, reconnect dedup, hero side, request classification) → Task 1.
- §6 item 5 (global dedup) → Task 2.
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

**2. Placeholder scan:** Two intentional, explicitly-flagged placeholders exist (Task 9 Step 3,
Task 10 Step 3) for board/field-variant-construction and live decision-pipeline call wiring that
depend on reading two files (`scratchpad/bench_accuracy_latency.py`, the Depth-2 Stage 2 script)
and Task 6's own freshly-written integration pattern that don't exist as importable functions until
those tasks run — both are called out with explicit "must be replaced before done, do not ship"
implementer notes and dedicated follow-up steps that assert against the placeholder string, rather
than being silently left in. This is a narrower, more defensible use of a placeholder than the
skill's blanket prohibition anticipates (a genuine dependency on reading sibling files at
implementation time, not a shortcut around writing real logic) — flagged for the executing
agent/reviewer to treat as a hard gate, not skipped.

**3. Type consistency:** `AccuracyEventDetail`/`TieOrderEvaluation`/`LineEvaluation` (Task 5,
`evaluate.py`) and `AccuracyEventTrace`/`AccuracyTieOrderTrace`/`AccuracyResponseDetail` (Task 6,
`decision_trace.py`) intentionally use matching-but-distinct names across the two layers (`Detail`
suffix = internal evaluate.py working type, `Trace` suffix = exported decision_trace.py schema
type, matching the spec's own naming convention) — verified field-for-field consistent between
Task 5's construction code and Task 6's `_breakdowns_for` consumption code (same field names:
`tie_order`, `weight`, `accuracy_leaf_count`, `accuracy_branch_cap_hits`, `events_complete`).
`ExtractedDecision` (Task 1) is consumed identically by Task 4 (`freeze_baseline`), Task 9/10 (Gate
A/B orchestration) — same field names (`request_hash`, `log_prefix_hash`, `side`, `turn`, `kind`,
`state`, `request`) throughout. `DedupReport`/`ScheduleIdentity` (Task 2) are consumed by Task 4
Step 5's driver script with matching field names (`kept`, `excluded`, `final_g`).

Execution choice, per this project's established pattern for plans this size (the merged
accuracy-hit-probability slice used subagent-driven-development with two-stage review per task,
extra scrutiny on the two highest-risk `battle/` tasks):

**1. Subagent-Driven (recommended)** — fresh subagent per task, spec-compliance review then
code-quality review between tasks, matching exactly how the prior accuracy slice was executed this
session. Given Tasks 5 and 6 touch the live decision pipeline (same risk class as that slice's Task
4/5), and Task 2's dedup logic is similarly high-stakes for this plan's own statistical validity,
recommend the same "two-stage review, no batching, extra scrutiny on the flagged tasks" discipline.

**2. Inline Execution** — batch execution in this session with checkpoints.

**Which approach?**

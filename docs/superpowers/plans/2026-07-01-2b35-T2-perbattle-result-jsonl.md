# 2b-3.5 T2 — Per-Battle-Result-JSONL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused). Steps use `- [ ]`. Parent plan:
> `docs/superpowers/plans/2026-07-01-2b35-diverse-opponent-eval-harness.md` (this is its T2, after
> T0/T1a/T1b/T1c landed). **Plan only — no code until reviewed.**

**Goal:** Emit **one validated JSONL row per battle** carrying everything a later pairing/report step
(T5 McNemar/Wilson) needs — while building none of that yet. This is the pairing *substrate*.

**Architecture:** A new `eval/result_jsonl.py` (frozen row schema + validate-on-write + append-only
writer) and a best-effort `eval/battle_parse.py` (winner/turns/end_hp from `room_raw`). The gauntlet
gains an **optional per-battle callback** (`on_battle_result`, default None → bit-identical); the
schedule runner assembles a row per schedule row and appends it. `battle/` untouched (INV-1).

**Tech Stack:** Python stdlib (json/hashlib), the existing `client/gauntlet.py`, `eval/schedule.py`,
`eval/seeding.py`, `eval/room_dump.py`, `learning/provenance.git_sha_and_dirty`.

---

## Row schema (frozen contract — the whole point of T2)
One row per battle. **Required** (validate-on-write fails fast if missing/None): `battle_id`,
**`config_id`**, **`format_id`**, **`config_hash`**, `schedule_hash`, `seed_index`, `opp_policy`,
`hero_team_path`, `opp_team_path`, `seed`, `winner`, `turns`, `invalid_choices`, `crashes`,
`decision_latency_p95_ms`, `git_sha`.
**Nullable** (present, may be `null`): `end_hp_diff` (best-effort from `room_raw`), `timeouts`
(not tracked yet), `room_raw_path` (null when dumping is off), `panel_hash` (null until T3).

**Config provenance (Fix 1 — so T5/reports never have to break the row schema again):**
- `config_id` = the **evaluated bot config/version** that played hero, e.g. `heuristic`, `shadow`,
  `override`, `prev_version`. In T2 it is the `hero_agent` (currently always `"heuristic"`); it
  becomes meaningful once shadow/override/prev_version are compared. **Not the format.**
- `format_id` = the Showdown format, e.g. `gen9vgc2025regi`. **NOTE:** the T1c schedule row's field is
  historically named `config_id` but *is the format* — so the T2 row maps `format_id = schedule_row.config_id`.
  (Renaming the schedule field is out of T2 scope; documented here so the mapping is explicit.)
- `config_hash` = a **stable hash of the effective eval config**. In T2 it may be simple — 
  `sha1(canonical({"config_id": config_id, "format_id": format_id}))[:16]` — but the field MUST exist
  now (later slices fold in fusion weights / thresholds / prev_version pin without a schema break).

- `battle_id` = `sha1(canonical([schedule_hash, seed_index, seed]))[:16]` — deterministic, joins a
  battle to its schedule row + seed.
- `winner` ∈ `{"hero","villain","tie"}` (role, **not** the suffixed bot name — see Fix 2 mapping).
- `seed` = `derive_battle_seed(base, seed_index)` (matches the server seed log; the T1b/T1c gate already
  proves equality). `seed_index` doubles as the "schedule_index" the spec lists (they are identical in T1c).

---

## Cross-cutting rules
- **T2-CC-1 — validate on WRITE, fail fast.** `BattleResultWriter.write(row)` calls `validate_battle_row`
  before appending; a missing/None required field raises `ResultRowError` (never a half-written row).
- **T2-CC-2 — empty-file-at-start, append-within-run (Fix 3).** `--result-out` MUST point to a
  **non-existing or empty** file at run start; if it already contains rows, **fail fast**
  (`ResultRowError`). Within a run, rows are appended (`newline="\n"`, canonical JSON, sorted keys) so
  the file is byte-stable + diffable. This resolves the append-vs-`row-count` tension (T2-CC-4):
  because the file starts empty, final `row-count == len(schedule.rows)` is unambiguous.
  **Resume / de-duplication is out of scope for T2.**
- **T2-CC-3 — off by default = bit-identical.** No `--result-out` / `on_battle_result=None` → the
  gauntlet path is unchanged (same discipline as export/shadow/room-dump seams).
- **T2-CC-4 — one row per schedule row.** The schedule runs `games=1` per row, so exactly one battle =
  one row. The runner asserts row-count == `len(schedule.rows)` at the end (ties to T1c's seed-log
  alignment; a retry/extra battle already fails there).

---

## Task 1 — `eval/result_jsonl.py` (schema + validate-on-write + append-only writer)

**Files:** Create `showdown_bot/src/showdown_bot/eval/result_jsonl.py`; Test
`showdown_bot/tests/test_result_jsonl.py`.

- [ ] **Step 1 — failing test** `test_result_jsonl.py`:
```python
import json
import pytest
from showdown_bot.eval.result_jsonl import (
    REQUIRED_FIELDS, ResultRowError, make_battle_id, validate_battle_row, BattleResultWriter,
)

def _row(**over):
    row = {
        "battle_id": "abc", "config_id": "heuristic", "format_id": "gen9vgc2025regi",
        "config_hash": "cfg123", "schedule_hash": "h",
        "seed_index": 0, "opp_policy": "heuristic", "hero_team_path": "teams/fixed_team.txt",
        "opp_team_path": "teams/opp_variant_a.txt", "seed": "sodium,00", "winner": "hero",
        "turns": 13, "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 200,
        "git_sha": "deadbeef", "end_hp_diff": None, "timeouts": None,
        "room_raw_path": None, "panel_hash": None,
    }
    row.update(over)
    return row

def test_valid_row_passes():
    validate_battle_row(_row())  # no raise

@pytest.mark.parametrize("missing", sorted(REQUIRED_FIELDS))
def test_missing_required_field_fails_fast(missing):
    row = _row(); del row[missing]
    with pytest.raises(ResultRowError):
        validate_battle_row(row)

def test_none_required_field_fails_fast():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(winner=None))

def test_bad_winner_fails_fast():
    with pytest.raises(ResultRowError):
        validate_battle_row(_row(winner="HeuristicBot123"))  # must be role hero/villain/tie

def test_make_battle_id_deterministic():
    assert make_battle_id("h", 0, "sodium,00") == make_battle_id("h", 0, "sodium,00")
    assert make_battle_id("h", 0, "sodium,00") != make_battle_id("h", 1, "sodium,00")

def test_writer_appends_and_validates(tmp_path):
    p = tmp_path / "results.jsonl"
    w = BattleResultWriter(str(p))
    w.write(_row(seed_index=0)); w.write(_row(seed_index=1))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["seed_index"] == 0
    with pytest.raises(ResultRowError):
        w.write(_row(winner=None))  # validate-on-write
```
- [ ] **Step 2 — run, expect fail** (`ModuleNotFoundError`).
- [ ] **Step 3 — implement** `eval/result_jsonl.py`:
```python
"""Per-battle result JSONL (T2): the pairing substrate for later reporting (T5).

One validated row per battle; append-only + validate-on-write (T2-CC-1/2). No stats,
no McNemar/Wilson, no report — those are T5.
"""
from __future__ import annotations
import hashlib
import json

REQUIRED_FIELDS = frozenset({
    "battle_id", "config_id", "format_id", "config_hash", "schedule_hash", "seed_index",
    "opp_policy", "hero_team_path", "opp_team_path", "seed", "winner", "turns",
    "invalid_choices", "crashes", "decision_latency_p95_ms", "git_sha",
})
NULLABLE_FIELDS = frozenset({"end_hp_diff", "timeouts", "room_raw_path", "panel_hash"})
_WINNERS = frozenset({"hero", "villain", "tie"})


class ResultRowError(ValueError):
    """A battle-result row is missing a required field or has an invalid value."""


def make_battle_id(schedule_hash: str, seed_index: int, seed: str) -> str:
    payload = json.dumps([schedule_hash, seed_index, seed], separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def validate_battle_row(row: dict) -> None:
    for f in REQUIRED_FIELDS:
        if f not in row:
            raise ResultRowError(f"missing required field: {f}")
        if row[f] is None:
            raise ResultRowError(f"required field is None: {f}")
    if row["winner"] not in _WINNERS:
        raise ResultRowError(f"winner must be one of {sorted(_WINNERS)}, got {row['winner']!r}")
    unknown = set(row) - REQUIRED_FIELDS - NULLABLE_FIELDS
    if unknown:
        raise ResultRowError(f"unknown fields: {sorted(unknown)}")


def to_jsonl_line(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


class BattleResultWriter:
    """Append-only writer: validate-on-write, one JSON row per line."""

    def __init__(self, path: str):
        self.path = path

    def write(self, row: dict) -> None:
        validate_battle_row(row)  # T2-CC-1: fail fast before appending
        with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(to_jsonl_line(row) + "\n")
```
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T2): battle-result JSONL schema + append-only writer`.

## Task 2 — `eval/battle_parse.py` (raw parse from room_raw — **side-agnostic**, best-effort)

The parser knows **nothing** about hero/villain (Fix 2); it returns raw slot data and the
`|player|p1|NAME|` / `|player|p2|NAME|` name map, so Task 3 can do an **explicit** side mapping.

**Files:** Create `showdown_bot/src/showdown_bot/eval/battle_parse.py`; Test
`showdown_bot/tests/test_battle_parse.py`.

- [ ] **Step 1 — failing test:** feed a small synthetic `room_raw` frame list; assert
  `parse_battle_result(frames)` returns a dict with:
  - `winner_name` (raw arg of `|win|`, or `None`), `is_tie` (True iff a `|tie` line), `turns`
    (count of `|turn|` lines),
  - `players` = `{"p1": name, "p2": name}` from the `|player|` lines (or `{}` if absent),
  - `hp_by_slot` = `{"p1": <fraction sum>, "p2": <fraction sum>}` or `None` if not confidently parseable.
  Include: a `|win|` + 3 `|turn|` + both `|player|` lines case; a `|tie` case; and a malformed case →
  `winner_name=None`, `hp_by_slot=None`, no crash.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `parse_battle_result(frames) -> dict`:
  - `turns` = number of `|turn|` lines; `winner_name` = `|win|` arg; `is_tie` = any `|tie` line.
  - `players` from `|player|p1|NAME|...` / `|player|p2|NAME|...`.
  - `hp_by_slot` (best-effort): track each **position**'s latest HP fraction (`|switch|`/`|drag|` set
    from the `hp/maxhp` field; `|-damage|`/`|-heal|` update; `faint` / `0 fnt` → 0.0), aggregate to a
    per-**player** (`p1`/`p2`) sum. Wrap the whole HP walk in try/except → `hp_by_slot=None` on any
    surprise (never crashes; downstream sets `end_hp_diff=null`).
  - Reuse `room_dump._iter_lines` for line splitting (single source). Operates on **raw** frames
    (so `|player|` lines are present — they are stripped only by `normalize_battle_log`).
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T2): side-agnostic battle-result parser (winner/turns/hp-by-slot)`.

## Task 3 — gauntlet per-battle callback seam

**Files:** Modify `showdown_bot/src/showdown_bot/client/gauntlet.py`; Test
`showdown_bot/tests/test_gauntlet_battle_result.py`.

- [ ] **Step 1 — failing test** for the **pure assembler** (Fix 2 — explicit hero/villain mapping;
  no live server needed): `_battle_result_record(winner_name, is_tie, hero_name, villain_name, frames,
  stats, room_raw_path)`:
  - `winner_name == hero_name` → `winner="hero"`; `== villain_name` → `"villain"`; `is_tie` (or a
    `|tie` in frames) → `"tie"`; **any other `winner_name` → `ResultRowError`** (never silently guess).
  - `end_hp_diff` = **hero-side HP sum − villain-side HP sum**, resolving hero/villain → `p1`/`p2` via
    `parse_battle_result(frames)["players"]` matched to `hero_name`/`villain_name`. If the `players`
    map is incomplete, a name doesn't match a slot, or `hp_by_slot is None` → **`end_hp_diff = None`**
    (Fix 2: never fall back to a blind `p1 − p2`).
  - Tests: hero-wins→"hero"; villain-wins→"villain"; tie→"tie"; unknown name→`ResultRowError`;
    end_hp_diff correct when `players`+`hp_by_slot` resolve; `None` when the side mapping is unreliable.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:**
  - Add `on_battle_result=None` param to `run_local_gauntlet` (default None → **no behavior change**, T2-CC-3).
  - `_battle_result_record(...)` (pure) as above (uses `parse_battle_result` for turns/players/hp_by_slot).
  - Call it in the `win`/`tie` handler (where the T1a dump already runs and `room_raw` is still
    present), passing **both** `hero.name` and `villain.name`; then `if on_battle_result:
    on_battle_result(record)`. `record` also carries `turns`, `invalid_choices`, `crashes`,
    `decision_latency_p95_ms` (from `stats`/latencies) and `room_raw_path` (returned by the T1a dump,
    else `None`).
- [ ] **Step 4 — run, expect pass** (existing gauntlet tests still green: `on_battle_result=None`).
- [ ] **Step 5 — commit** `feat(2b-3.5 T2): optional per-battle on_battle_result callback + explicit side mapping`.

## Task 4 — schedule runner emits rows + smoke

**Files:** Modify `showdown_bot/src/showdown_bot/cli.py` (`run_schedule`); Report
`reports/2026-07-01-2b35-T2-result-jsonl-smoke.md`.

- [ ] **Step 1** — CLI `gauntlet --schedule ... --result-out <path>`. At start (Fix 3, T2-CC-2):
  if `--result-out` exists and is **non-empty**, **fail fast** (`ResultRowError`). For each row, pass an
  `on_battle_result` that assembles the full row and `BattleResultWriter.write(row)`:
  - `format_id` = `schedule_row.config_id` (the schedule field is the format — Fix 1 mapping note);
  - `config_id` = the evaluated bot config = `hero_agent` (T2: `"heuristic"`);
  - `config_hash` = `sha1(canonical({"config_id": config_id, "format_id": format_id}))[:16]`;
  - `battle_id` = `make_battle_id(schedule_hash, seed_index, seed)`;
    `seed` = `derive_battle_seed(base, seed_index)`; `git_sha` = `git_sha_and_dirty()[0]`;
  - `opp_policy`/`hero_team_path`/`opp_team_path`/`seed_index`/`schedule_hash` from the row/schedule;
  - `winner`/`turns`/`end_hp_diff`/`invalid_choices`/`crashes`/`decision_latency_p95_ms`/`room_raw_path`
    from the callback record; `timeouts=None`; `panel_hash=None`.
  `--result-out` unset → no rows written (T2-CC-3, bit-identical).
- [ ] **Step 2** — after all rows: assert row-count == `len(schedule.rows)` (T2-CC-4, unambiguous
  because the file started empty); keep the existing T1c seed-log alignment gate.
- [ ] **Step 3 — smoke** (manual, in the report): run `smoke_nonmirror.yaml` with `--result-out`; assert
  2 valid rows, each joins to its schedule row by `seed_index`, `seed` == server seed log, winner ∈ roles,
  `turns>0`, 0 invalid/crash. (No JSONL committed — data artifact.)
- [ ] **Step 4 — report + commit** `feat(2b-3.5 T2): schedule runner emits per-battle result JSONL + smoke`.

**Phase T2 gate:** a schedule run with `--result-out` writes exactly one valid row per battle;
rows validate-on-write; every row joins to the schedule by `(schedule_hash, seed_index)` and its `seed`
matches the server seed log; `--result-out` unset stays bit-identical; suite green.

---

## Out of scope (explicitly NOT T2)
No T3 panel / `panel_hash` population, no report generator, no Wilson CI, no McNemar (only the *fields*
T5 will need), no held-out gate, no 2b-4 override. `battle/` untouched.

## Self-review (writing-plans)
- Spec coverage: every field the T2 prompt lists maps to a schema field — incl. `end_hp_diff`
  (nullable/best-effort), `timeouts` (nullable), `trace_path`→`room_raw_path`, `panel_hash` (nullable
  until T3). ✓
- Review fixes applied: **(1)** `config_id` (bot version) split from `format_id` + required `config_hash`;
  **(2)** `_battle_result_record(winner_name, is_tie, hero_name, villain_name, …)` with exact hero/villain
  mapping (unknown → `ResultRowError`) and hero-side-minus-villain-side `end_hp_diff` via explicit
  `|player|`-slot resolution (null if unreliable, never `p1−p2`); **(3)** `--result-out` empty-file-required,
  fail fast if non-empty. ✓
- Placeholders: none — all code shown; deferred values are `panel_hash=None` (T3) and `config_id`
  always `"heuristic"` until shadow/override/prev_version comparisons (intended).
- Type consistency: `make_battle_id(schedule_hash, seed_index, seed)` used identically in Task 1 test +
  Task 4; `parse_battle_result` returns `{winner_name, is_tie, turns, players, hp_by_slot}` — the exact
  keys `_battle_result_record` consumes (Task 3) and the runner assembles (Task 4). ✓

# 2b-3.5 T1-proper — Per-Battle Seed + Non-Mirror Scheduling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused for this slice). Steps use `- [ ]`. Parent plan:
> `docs/superpowers/plans/2026-07-01-2b35-diverse-opponent-eval-harness.md` (this is its T1, now that
> **T1a is done** — seed patch merged, demonstrated PASS_STRONG). **No code until this plan is reviewed.**

**Goal:** Turn the proven single-seed patch (T1a) into (T1b) a **distinct, reproducible per-battle
seed** and (T1c) a **non-mirror** gauntlet driven by a versioned schedule — the two remaining pieces of
T1 before T2 (per-battle JSONL) can pair on `(schedule_index, seed)`.

**Architecture:** T1b keeps the seed **server-side** (extends the T1a `ladders.ts` patch) with a
process-local battle counter + a seed derivation shared byte-for-byte with a Python helper, so a fresh
server session reproduces the whole seed *sequence*. T1c teaches `run_local_gauntlet` to load a
per-side team from a schedule row instead of mirroring one packed team. The live decision path
(`battle/`) stays untouched; everything is an isolated gauntlet/eval addition.

**Tech Stack:** Python (stdlib hashlib for the derivation), the existing `client/gauntlet.py` + the
local patched `node pokemon-showdown` (@ f8ac140 + `tools/eval/patches/`). No new sim, no training.

---

## Cross-cutting rules (inherit parent plan CC-1…CC-5; plus)
- **T1-CC-A — one derivation, two call sites.** `derive_battle_seed(base, index)` is defined once in
  Python and mirrored **character-for-character** in the server patch. A test pins known vectors on the
  Python side; the server proof (re-run compare) pins that the server matches. If they ever diverge,
  reproduction breaks silently — so the formula is dead simple and both copies carry the same comment.
- **T1-CC-B — reproduction requires a fresh server per version run.** The per-battle counter resets at
  process start. Two runs to be paired (version A vs B) MUST each start a fresh server (counter from 0)
  and create battles in the **same schedule order**, or the seed sequences won't align. Stated in every
  runner + report.
- **T1-CC-C — the seed sequence is content-independent.** `seed_i = derive(base, i)` depends only on
  `(base, battle index)`, never on the teams/policies. That is what makes A-vs-B a fair paired
  comparison (same luck, different policy). Never fold policy/team into the seed.

---

## Design decision (resolve at review): per-battle seed channel
Chosen = **(A) server-side base + process-local counter**, because it needs no per-battle Python→server
protocol and gives an aligned seed sequence across fresh sessions. Rejected alternatives, for the record:
- **(B) thread the seed through `/challenge`** — most robust (seed tied to the schedule row, not to
  creation order), but needs a challenge-protocol/custom-rule parse extension. Hold as the fallback if
  counter/order coupling ever bites (e.g. retried challenges desyncing the counter).
- **(C) restart the server per battle** — trivially correct but far too slow for a schedule.
Self-check baked in: T1b's gate re-runs and compares `room_raw` per battle, so any counter/order
desync surfaces as a mismatch rather than a silent wrong number.

---

# Phase T1b — Deterministic per-battle seed  *(first PR; independently mergeable)*

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/seeding.py`
- Create: `showdown_bot/tests/test_seeding.py`
- Modify (external clone, then re-export artifact): `~/.cache/showdownbot/pokemon-showdown/server/ladders.ts`
- Modify: `tools/eval/patches/pokemon-showdown-seeded-battle.patch` + `tools/eval/patches/README.md`
- Create: `reports/2026-07-01-2b35-T1b-perbattle-seed.md`

### Task 1: Python seed derivation
- [ ] **Step 1 — failing test** `tests/test_seeding.py`:
```python
from showdown_bot.eval.seeding import derive_battle_seed

def test_deterministic_and_distinct_per_index():
    a0 = derive_battle_seed("run2026", 0)
    a0b = derive_battle_seed("run2026", 0)
    a1 = derive_battle_seed("run2026", 1)
    assert a0 == a0b                 # same (base,index) -> same seed
    assert a0 != a1                  # distinct per index
    assert a0.startswith("sodium,")  # valid PRNGSeed form
    assert len(a0.split(",")[1]) == 32 and int(a0.split(",")[1], 16) >= 0  # 16-byte hex

def test_base_changes_sequence():
    assert derive_battle_seed("A", 0) != derive_battle_seed("B", 0)

def test_known_vector():   # pins the formula so the server copy can be checked against it
    assert derive_battle_seed("run2026", 0) == "sodium,<FILL_FROM_FIRST_RUN>"
```
- [ ] **Step 2 — run, expect fail** (`ModuleNotFoundError`).
- [ ] **Step 3 — implement** `eval/seeding.py`:
```python
"""Deterministic per-battle sim seed derivation (T1b).

MIRRORED CHARACTER-FOR-CHARACTER in the server patch (tools/eval/patches/): seed_i =
"sodium," + first 16 bytes of sha256(f"{base}:{index}") as hex. Depends ONLY on
(base, battle index) so a fresh server session reproduces the whole seed sequence
and A-vs-B paired runs share luck (T1-CC-A / T1-CC-C).
"""
from __future__ import annotations
import hashlib

def derive_battle_seed(base: str, index: int) -> str:
    digest = hashlib.sha256(f"{base}:{index}".encode()).hexdigest()
    return f"sodium,{digest[:32]}"
```
- [ ] **Step 4 — run, expect pass** (fill `test_known_vector` from the first computed value).
- [ ] **Step 5 — commit** `feat(2b-3.5 T1b): deterministic per-battle seed derivation`.

### Task 2: mirror the derivation in the server patch
- [ ] **Step 1** — extend `Ladder.match` (`server/ladders.ts`, the T1a block): keep `SHOWDOWN_BATTLE_SEED`
  (fixed) as-is; add a `SHOWDOWN_BATTLE_SEED_BASE` branch with a module-local counter:
```ts
// module scope (top of ladders.ts, near imports)
let evalBattleCounter = 0;
// inside Ladder.match, replacing the T1a evalSeed line:
let evalSeed = process.env.SHOWDOWN_BATTLE_SEED;                 // fixed-seed mode (T1a)
const seedBase = process.env.SHOWDOWN_BATTLE_SEED_BASE;          // per-battle mode (T1b)
if (!evalSeed && seedBase) {
    const crypto = require('crypto');
    const digest = crypto.createHash('sha256').update(`${seedBase}:${evalBattleCounter}`).digest('hex');
    evalSeed = `sodium,${digest.slice(0, 32)}` as any;
    evalBattleCounter++;
}
```
  (Same formula as Python — verify equality against `test_known_vector` in Task 3's proof, T1-CC-A.)
- [ ] **Step 2** — `node build` in the clone; expect exit 0.
- [ ] **Step 3** — re-export the artifact: `git -C ~/.cache/.../pokemon-showdown diff server/ladders.ts`
  → overwrite `tools/eval/patches/pokemon-showdown-seeded-battle.patch`; update README (document
  `SHOWDOWN_BATTLE_SEED_BASE` + fresh-session requirement T1-CC-B).
- [ ] **Step 4 — commit** `feat(2b-3.5 T1b): server per-battle seed (base+counter) + artifact`.

### Task 3: N-battle reproduction proof + PYTHONHASHSEED
- [ ] **Step 1** — pin bot cross-process determinism: set `PYTHONHASHSEED=0` for gauntlet runs used in
  paired eval (document in the report + any runner). Rationale: if any heuristic tie-break iterates a
  set, cross-process ordering must be fixed too (T1a only proved within-process).
- [ ] **Step 2 — proof run** (manual, scripted in the report): start a fresh server with
  `SHOWDOWN_BATTLE_SEED_BASE=run2026`; run `--games 4 --villain heuristic` twice (fresh server each
  time, `PYTHONHASHSEED=0`, `SHOWDOWN_ROOM_RAW_DUMP` set). Using `eval/room_dump.compare_battle_logs`,
  assert: (a) run1 battle_i ≡ run2 battle_i for every i (per-battle reproduction), and (b) battle_i ≢
  battle_j for i≠j (distinct seeds → generally distinct battles). Also assert the server's first seed ==
  `derive_battle_seed("run2026", 0)` (T1-CC-A) by reading it back from the battle (or by the room_raw
  match to a Python-seeded control).
- [ ] **Step 3 — report** `reports/2026-07-01-2b35-T1b-perbattle-seed.md`: the per-battle identity table
  + the distinctness check + the PYTHONHASHSEED note + T1-CC-A/B confirmation. Verdict:
  per-battle-reproducible or a precise failure reason.
- [ ] **Step 4 — commit** `docs(2b-3.5 T1b): per-battle seed reproduction report`.

**Phase T1b gate:** 4-battle schedule reproduces across two fresh-server runs; seeds distinct per index;
Python↔server derivation confirmed equal; suite green; safety floor holds. **STOP for review before T1c.**

---

# Phase T1c — Non-mirror team scheduling  *(second PR; after T1b review)*

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/schedule.py` (+ `tests/test_schedule.py`)
- Create: `config/eval/schedules/smoke_nonmirror.yaml` (a 2-row example; teams referenced by path)
- Modify: `showdown_bot/src/showdown_bot/client/gauntlet.py` (`run_local_gauntlet` per-side team)
- Modify: `showdown_bot/src/showdown_bot/cli.py` (a `--schedule` path for gauntlet)
- Create: `reports/2026-07-01-2b35-T1c-nonmirror-smoke.md`

### Task 4: schedule file + loader
- [ ] **Step 1 — failing test** `tests/test_schedule.py`: a versioned schedule YAML loads into rows
  `ScheduleRow(config_id, hero_team_path, opp_policy, opp_team_path, seed_index)`; `schedule_hash` is
  stable; unknown/ missing fields fail-fast; `seed_index` unique + contiguous from 0.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `eval/schedule.py`: `load_schedule(path) -> Schedule` (frozen rows +
  `schedule_hash` = canonical-json sha1, reusing the export ID-hash style). No battle logic here.
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T1c): schedule file + loader`.

### Task 5: gauntlet plays two different teams
- [ ] **Step 1 — failing test:** a gauntlet-level unit/smoke asserting `run_local_gauntlet` accepts
  `hero_team_path` + `opp_team_path` (distinct) and builds each `_Client` with its own `packed_team`
  (currently both get the same `packed`, `gauntlet.py:327,347-348`). Assert `hero.packed_team !=
  villain.packed_team` when two paths are given; mirror still works when one path is given (back-compat).
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** extend `run_local_gauntlet` signature with optional `opp_team_path`
  (default None → mirror, unchanged). Load a second packed team; pass it to the villain `_Client`;
  `our_spreads` for the villain from its own packed team. `battle/` untouched (INV-1).
- [ ] **Step 4 — run, expect pass** (existing gauntlet tests still green = mirror back-compat).
- [ ] **Step 5 — commit** `feat(2b-3.5 T1c): per-side teams in run_local_gauntlet`.

### Task 6: schedule-driven run + non-mirror smoke
- [ ] **Step 1** — CLI `--schedule <path>` for `gauntlet`: iterate rows, run each battle with the row's
  `hero_team_path`/`opp_team_path`/`opp_policy`, `SHOWDOWN_BATTLE_SEED_BASE` set so battle *i* uses
  `derive_battle_seed(base, row.seed_index)` (fresh server, T1-CC-B). (No per-battle JSONL yet — that is
  T2; a plain aggregate/console result is fine here.)
- [ ] **Step 2 — smoke:** `config/eval/schedules/smoke_nonmirror.yaml` (2 rows, hero team vs a *different*
  opp team). Run it twice; assert (via `room_dump`) each non-mirror battle reproduces (T1a-level) and the
  two teams really differ in-battle.
- [ ] **Step 3 — report** `reports/2026-07-01-2b35-T1c-nonmirror-smoke.md`: the non-mirror battles ran,
  0 invalid/crash, reproduced per-battle; the schedule_hash recorded.
- [ ] **Step 4 — commit** `feat(2b-3.5 T1c): schedule-driven non-mirror gauntlet + smoke report`.

**Phase T1c gate (= parent-plan T1 done):** a 2-row schedule plays two *different*-team battles,
reproducible to the T1a level; mirror path still bit-identical; safety floor holds. Unlocks T2
(per-battle JSONL) → T3 panel → T4 smoke → T5 report → T6 held-out gate.

---

## Out of scope (explicitly not T1)
No per-battle JSONL (T2), no panel/opponent policies beyond the existing `heuristic`/`max_damage`/`random`
(T3), no report generator (T5), no held-out gate (T6), no 2b-4 override.

## Self-review (writing-plans)
- Spec coverage: parent-plan T1 ("two different teams, per-battle seed") = T1c Task 5/6 + T1b. ✓
- Placeholders: `test_known_vector`'s `<FILL_FROM_FIRST_RUN>` is an intentional pin-after-first-compute,
  called out in the step. No other TODOs.
- Type consistency: `derive_battle_seed(base:str,index:int)->str` used identically in Task 1/2/3;
  `ScheduleRow.seed_index` feeds `derive_battle_seed(base, seed_index)` in Task 6. ✓

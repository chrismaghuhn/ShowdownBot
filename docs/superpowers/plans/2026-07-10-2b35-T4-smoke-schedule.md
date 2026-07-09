# 2b-3.5 T4 — First Real Smoke Schedule (51 games) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused). Steps use `- [ ]`. Implements the accepted design in
> `docs/superpowers/reviews/2026-07-02-fable-t4-smoke-schedule-design.md` (T4 review §1–§10).
> **Plan only — no code until reviewed.**

**Goal:** Prove the whole eval pipeline at scale — a 51-game weighted dev matrix runs clean under the
full T3e/T3f provenance stack, plus cheap fresh-server reproduction evidence via a stratified 10-row
prefix schedule. Pipeline validation ONLY: no strength claims, no reranker evidence, no 2b-4 input.

**Depends on:** T3f merged (`927c7fa`: effective `config_hash`, `seed_base`/`run_id`+manifest/
`panel_split`/`end_reason`, pinned latency budget in `config/eval/gates.yaml`). Suite baseline: 659.

**Architecture:** Two bounded generator extensions on `eval/panel_schedule.py` (per-policy
`seeds_per_cell` mapping; explicit `prefix_cells` first-rows ordering) + a `prefix_schedule()`
extractor; the pinned T4 matrix lives in a new tiny `eval/t4_matrix.py`; both schedules are committed
YAMLs with a drift test. Then two operational runs (full 51 + prefix 10) against a fresh seeded
server, a hand-assembled report, and the run artifacts committed under `data/eval/t4/`
(**user decision 2026-07-10: COMMIT result JSONL + seed log — they become T5's development fixture**).

**Tech Stack:** stdlib + pyyaml; existing `eval/{panel,panel_schedule,schedule,result_jsonl,
run_manifest,gates,room_dump,seeding}`, `cli.run_schedule`, the seeded pokemon-showdown clone at
`~/.cache/showdownbot/pokemon-showdown` (@ `f8ac140` + versioned patch).

---

## Cross-cutting rules

- **T4-CC-1 — no battle-level retry, fresh server, whole-run-or-nothing.** One stalled/crashed battle
  voids the ENTIRE run (Channel-A counter discipline). A voided run is diagnosed, documented, and the
  whole run repeated against a fresh server — never resumed, never partially kept.
- **T4-CC-2 — run outputs live OUTSIDE the repo while battles run** (`C:/tmp/t4/...`), then get copied
  into `data/eval/t4/` afterwards. Rationale: the `dirty=false` gate — files appearing inside the repo
  mid-run could flip `git_sha_and_dirty()`. Copy + commit happens only in Task 7.
- **T4-CC-3 — single config, shadow OFF.** No `SHOWDOWN_RERANKER_*`, no behavior flags beyond the
  documented run env. `SHOWDOWN_EVAL_POLICY_TELEMETRY` and `SHOWDOWN_ROOM_RAW_DUMP` are classified
  NON_BEHAVIORAL (`eval/config_env.py:45-57`), so setting them does not perturb `config_hash`.
- **T4-CC-4 — non-evidentiary phrasing is mandatory** (review §6): per-policy numbers only, never a
  pooled headline win rate; losses reported without alarm framing; the verbatim ceiling caveat (Task 7)
  must appear in the report.
- **T4-CC-5 — Windows/Git-Bash paths:** always `MSYS_NO_PATHCONV=1` + explicit `C:/tmp/...` paths
  (never bare `/tmp` — see the operational note in
  `reports/2026-07-09-2b35-T3f-run-provenance-smoke.md`).
- **Execution setup:** work on a new branch `feat/slice-2b35-t4-smoke-schedule` off `main`. Test
  command from repo root: `python -m pytest showdown_bot/tests -q`. `battle/` untouched (INV-1).

---

## The pinned matrix (review §3, constants for Task 4)

| opp_policy | seeds per (policy, team) cell | games (× 3 dev teams) |
|---|---|---|
| heuristic | 5 | 15 |
| max_damage | 5 | 15 |
| simple_heuristic | 3 | 9 |
| greedy_protect | 2 | 6 |
| scripted_vgc | 2 | 6 |
| **Total** | | **51** |

Rows 0–9 = stratified reproduction prefix (all 5 policies, all 3 teams):
`(heuristic, trickroom)`, `(heuristic, sun)`, `(heuristic, rain)`, `(max_damage, trickroom)`,
`(max_damage, sun)`, `(max_damage, rain)`, `(simple_heuristic, trickroom)`, `(greedy_protect, sun)`,
`(scripted_vgc, rain)`, `(heuristic, trickroom)` — the extra 10th pick goes to the most informative
cell. `random` is excluded by design. Panel: `panel_v001`, `panel_hash 760c1e5935fe0474`, hero =
`teams/fixed_team.txt`.

Because `seed_i = derive_battle_seed(seed_base, seed_index)` depends ONLY on `(base, index)`, a
separate 10-row schedule containing exactly rows 0–9 re-run with the same `seed_base` reproduces
exactly those battles' seeds on a fresh server — reproduction evidence at ~20 % of a full double run.

---

### Task 1: Per-policy `seeds_per_cell` mapping

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/panel_schedule.py` (`_build` + two new helpers)
- Test: `showdown_bot/tests/test_panel_schedule.py`

- [ ] **Step 1: Write the failing tests** (append to `test_panel_schedule.py`; `_panel()` fixture
  already exists there):

```python
# --- T4: per-policy seeds_per_cell mapping ---------------------------------------------

def test_seeds_per_cell_mapping_counts_and_order():
    sched = generate_dev_schedule(
        _panel(), policies=["heuristic", "max_damage"],
        seeds_per_cell={"heuristic": 3, "max_damage": 1},
    )
    # 2 teams x (3 + 1) = 8 rows, team-major then policy order, contiguous seed_index
    assert len(sched.rows) == 8
    assert [r.seed_index for r in sched.rows] == list(range(8))
    assert [r.opp_policy for r in sched.rows] == (
        ["heuristic"] * 3 + ["max_damage"] + ["heuristic"] * 3 + ["max_damage"]
    )


def test_seeds_per_cell_mapping_missing_policy_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(
            _panel(), policies=["heuristic", "max_damage"], seeds_per_cell={"heuristic": 3},
        )


def test_seeds_per_cell_mapping_unknown_policy_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(
            _panel(), policies=["heuristic"], seeds_per_cell={"heuristic": 1, "scripted_vgc": 2},
        )


def test_seeds_per_cell_mapping_invalid_value_raises():
    for bad in (0, -1, True, "2"):
        with pytest.raises(PanelScheduleError):
            generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell={"heuristic": bad})


def test_seeds_per_cell_int_backcompat_unchanged():
    a = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=3)
    b = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell={"heuristic": 3})
    assert a.schedule_hash == b.schedule_hash  # mapping == uniform int when counts agree
```

- [ ] **Step 2: Run tests, expect FAIL**
  `python -m pytest showdown_bot/tests/test_panel_schedule.py -q` — the mapping tests fail
  (`TypeError`/no `PanelScheduleError`), the back-compat test errors.

- [ ] **Step 3: Implement** in `panel_schedule.py` — add above `_build`:

```python
def _validate_seeds_per_cell(seeds_per_cell, policies) -> None:
    if isinstance(seeds_per_cell, bool):
        raise PanelScheduleError(f"seeds_per_cell must be an int or a mapping, got {seeds_per_cell!r}")
    if isinstance(seeds_per_cell, int):
        if seeds_per_cell < 1:
            raise PanelScheduleError("seeds_per_cell must be >= 1")
        return
    unknown = set(seeds_per_cell) - set(policies)
    if unknown:
        raise PanelScheduleError(
            f"seeds_per_cell has policies not in the chosen set: {sorted(unknown)}"
        )
    missing = set(policies) - set(seeds_per_cell)
    if missing:
        raise PanelScheduleError(f"seeds_per_cell missing policies: {sorted(missing)}")
    for p, n in seeds_per_cell.items():
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise PanelScheduleError(f"seeds_per_cell[{p!r}] must be an int >= 1, got {n!r}")


def _seeds_for(policy: str, seeds_per_cell) -> int:
    """Per-cell seed count: a plain int applies to every cell; a mapping is per-policy."""
    return seeds_per_cell if isinstance(seeds_per_cell, int) else seeds_per_cell[policy]
```

  In `_build`: replace the `if seeds_per_cell < 1: ...` check with
  `_validate_seeds_per_cell(seeds_per_cell, policies)` and the inner loop's
  `range(seeds_per_cell)` with `range(_seeds_for(policy, seeds_per_cell))`. Update the module
  docstring (one line: `seeds_per_cell` accepts an int or a per-policy mapping, T4).

- [ ] **Step 4: Run tests, expect PASS** — same command; whole file green.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/panel_schedule.py showdown_bot/tests/test_panel_schedule.py
git commit -m "feat(2b-3.5 T4): per-policy seeds_per_cell in panel schedule generator"
```

### Task 2: Stratified prefix-first ordering (`prefix_cells`)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/panel_schedule.py` (`_build`, `generate_dev_schedule`)
- Test: `showdown_bot/tests/test_panel_schedule.py`

- [ ] **Step 1: Write the failing tests:**

```python
# --- T4: prefix_cells — stratified reproduction-prefix ordering --------------------------

def test_prefix_cells_come_first_then_canonical_remainder():
    sched = generate_dev_schedule(
        _panel(), policies=["heuristic", "max_damage"],
        seeds_per_cell={"heuristic": 2, "max_damage": 1},
        prefix_cells=[("max_damage", "d2"), ("heuristic", "d1")],
    )
    # 2 teams x (2 + 1) = 6 rows total; prefix picks occupy seed_index 0 and 1 in given order.
    assert len(sched.rows) == 6
    assert (sched.rows[0].opp_policy, sched.rows[0].opp_team_path) == (
        "max_damage", "teams/panel_v001/sun_dev.txt")
    assert (sched.rows[1].opp_policy, sched.rows[1].opp_team_path) == (
        "heuristic", "teams/panel_v001/trickroom_dev.txt")
    # Remainder is canonical (team-major, policy order), each cell reduced by its prefix picks:
    assert [(r.opp_policy, r.opp_team_path) for r in sched.rows[2:]] == [
        ("heuristic", "teams/panel_v001/trickroom_dev.txt"),
        ("heuristic", "teams/panel_v001/sun_dev.txt"),
        ("heuristic", "teams/panel_v001/sun_dev.txt"),
        ("max_damage", "teams/panel_v001/trickroom_dev.txt"),
    ]
    assert [r.seed_index for r in sched.rows] == list(range(6))  # still contiguous


def test_prefix_cells_preserve_per_cell_totals():
    sched = generate_dev_schedule(
        _panel(), policies=["heuristic"], seeds_per_cell=2,
        prefix_cells=[("heuristic", "d2")],
    )
    from collections import Counter
    assert Counter((r.opp_policy, r.opp_team_path) for r in sched.rows) == Counter({
        ("heuristic", "teams/panel_v001/trickroom_dev.txt"): 2,
        ("heuristic", "teams/panel_v001/sun_dev.txt"): 2,
    })


def test_prefix_cells_overconsuming_a_cell_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(
            _panel(), policies=["heuristic"], seeds_per_cell=1,
            prefix_cells=[("heuristic", "d1"), ("heuristic", "d1")],  # cell has only 1 seed
        )


def test_prefix_cells_unknown_policy_or_team_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["heuristic"], prefix_cells=[("max_damage", "d1")])
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["heuristic"], prefix_cells=[("heuristic", "nope")])


def test_prefix_cells_none_is_unchanged():
    a = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=2)
    b = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=2, prefix_cells=None)
    assert a.schedule_hash == b.schedule_hash
```

- [ ] **Step 2: Run tests, expect FAIL** (unexpected keyword `prefix_cells`).

- [ ] **Step 3: Implement** — add helper above `_build`:

```python
def _ordered_cells(teams, policies, seeds_per_cell, prefix_cells):
    """One (team, policy) entry per battle: explicit prefix picks first (in the given order),
    then the canonical remainder (team-major, then policy list order), each cell's remaining
    seed budget reduced by its prefix picks. Fail-fast on unknown cells / over-consumption."""
    remaining = {
        (team.team_id, policy): _seeds_for(policy, seeds_per_cell)
        for team in teams for policy in policies
    }
    teams_by_id = {t.team_id: t for t in teams}
    ordered = []
    for policy, team_id in (prefix_cells or ()):
        if policy not in policies or team_id not in teams_by_id:
            raise PanelScheduleError(f"prefix cell ({policy!r}, {team_id!r}) not in the matrix")
        key = (team_id, policy)
        if remaining[key] < 1:
            raise PanelScheduleError(
                f"prefix over-consumes cell ({policy!r}, {team_id!r}): more prefix picks than seeds"
            )
        remaining[key] -= 1
        ordered.append((teams_by_id[team_id], policy))
    for team in teams:
        for policy in policies:
            ordered.extend((team, policy) for _ in range(remaining[(team.team_id, policy)]))
    return ordered
```

  Change `_build` to take `prefix_cells=None` as its last parameter and replace its triple loop with:

```python
    rows: list[ScheduleRow] = []
    for idx, (team, policy) in enumerate(
        _ordered_cells(teams, policies, seeds_per_cell, prefix_cells)
    ):
        rows.append(ScheduleRow(
            format_id=format_id, hero_team_path=hero_team_path,
            opp_policy=policy, opp_team_path=team.team_path, seed_index=idx,
            hero_team_hash=hero_team_hash,
            opp_team_hash=team.team_hash,
            panel_split=panel_split,
        ))
```

  `generate_dev_schedule` gains `prefix_cells=None` and passes it through to `_build`.
  `generate_heldout_schedule` stays as-is (passes nothing → default None; YAGNI).

- [ ] **Step 4: Run tests, expect PASS** — plus the full file (Task 1 + T3d/T3e/T3f tests all green:
  the None path must be byte-identical in behavior).

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/panel_schedule.py showdown_bot/tests/test_panel_schedule.py
git commit -m "feat(2b-3.5 T4): stratified prefix-first row ordering (prefix_cells)"
```

### Task 3: `prefix_schedule()` extractor

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/panel_schedule.py`
- Test: `showdown_bot/tests/test_panel_schedule.py`

- [ ] **Step 1: Write the failing tests:**

```python
# --- T4: prefix_schedule — first-n-rows reproduction schedule ----------------------------

def test_prefix_schedule_first_n_rows_same_indices():
    full = generate_dev_schedule(_panel(), policies=["heuristic", "max_damage"], seeds_per_cell=2)
    pre = prefix_schedule(full, 3)
    assert len(pre.rows) == 3
    assert pre.rows == full.rows[:3]                    # identical rows incl. seed_index 0..2
    assert pre.version == full.version
    assert pre.panel_hash == full.panel_hash
    assert pre.schedule_hash != full.schedule_hash      # different row set = different identity


def test_prefix_schedule_roundtrips_via_loader(tmp_path):
    full = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=2)
    pre = prefix_schedule(full, 2)
    out = tmp_path / "prefix.yaml"
    write_schedule_yaml(pre, str(out))
    reloaded = load_schedule(str(out))
    assert reloaded.schedule_hash == pre.schedule_hash


def test_prefix_schedule_invalid_n_raises():
    full = generate_dev_schedule(_panel(), policies=["heuristic"])
    for bad in (0, -1, len(full.rows) + 1, True, "2"):
        with pytest.raises(PanelScheduleError):
            prefix_schedule(full, bad)
```

  Add `prefix_schedule` to the test file's import list from `panel_schedule`.

- [ ] **Step 2: Run tests, expect FAIL** (ImportError).

- [ ] **Step 3: Implement** in `panel_schedule.py`:

```python
def prefix_schedule(schedule: Schedule, n: int) -> Schedule:
    """The first ``n`` rows as their own schedule (seed_index already 0..n-1). Under Channel A
    ``seed_i`` depends only on (seed_base, seed_index), so re-running just this schedule with
    the same seed_base reproduces exactly those battles — cheap fresh-server reproduction
    evidence (T4 review §5). schedule_hash is recomputed; version/panel_hash preserved."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1 or n > len(schedule.rows):
        raise PanelScheduleError(f"prefix length must be 1..{len(schedule.rows)}, got {n!r}")
    rows = schedule.rows[:n]
    return Schedule(
        version=schedule.version, rows=rows,
        schedule_hash=compute_schedule_hash(schedule.version, rows),
        panel_hash=schedule.panel_hash,
    )
```

- [ ] **Step 4: Run tests, expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/panel_schedule.py showdown_bot/tests/test_panel_schedule.py
git commit -m "feat(2b-3.5 T4): prefix_schedule extraction for reproduction runs"
```

### Task 4: Pinned T4 matrix module + committed schedule YAMLs + drift test

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/t4_matrix.py`
- Create: `config/eval/schedules/t4_smoke_v001.yaml` + `config/eval/schedules/t4_smoke_v001_prefix.yaml` (generated)
- Test: `showdown_bot/tests/test_t4_matrix.py`

- [ ] **Step 1: Write the failing test** (`showdown_bot/tests/test_t4_matrix.py`):

```python
"""T4 pinned matrix: committed schedules must match the generator (drift guard)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.panel_schedule import generate_dev_schedule
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.t4_matrix import (
    T4_PREFIX_CELLS,
    T4_PREFIX_LEN,
    T4_SEEDS_PER_CELL,
    generate_t4_schedules,
)

_REPO = Path(__file__).resolve().parents[2]
_PANEL = _REPO / "config" / "eval" / "panels" / "panel_v001.yaml"
_FULL = _REPO / "config" / "eval" / "schedules" / "t4_smoke_v001.yaml"
_PREFIX = _REPO / "config" / "eval" / "schedules" / "t4_smoke_v001_prefix.yaml"
_TEAMS_ROOT = str(_REPO / "showdown_bot")


def _generated():
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    return generate_t4_schedules(panel, teams_root=_TEAMS_ROOT)


def test_matrix_constants_pinned():
    assert T4_SEEDS_PER_CELL == {
        "heuristic": 5, "max_damage": 5, "simple_heuristic": 3,
        "greedy_protect": 2, "scripted_vgc": 2,
    }
    assert T4_PREFIX_LEN == 10 == len(T4_PREFIX_CELLS)


def test_full_schedule_shape_and_weights():
    full, pre = _generated()
    assert len(full.rows) == 51
    assert Counter(r.opp_policy for r in full.rows) == {
        "heuristic": 15, "max_damage": 15, "simple_heuristic": 9,
        "greedy_protect": 6, "scripted_vgc": 6,
    }
    assert full.reproducible is True
    assert {r.panel_split for r in full.rows} == {"dev"}
    # Stratified prefix: rows 0..9 cover all 5 policies and all 3 dev teams.
    head = full.rows[:T4_PREFIX_LEN]
    assert {r.opp_policy for r in head} == set(T4_SEEDS_PER_CELL)
    assert len({r.opp_team_path for r in head}) == 3
    # Prefix schedule == first 10 rows of the full schedule.
    assert pre.rows == head
    assert pre.panel_hash == full.panel_hash


def test_committed_yamls_match_generator():
    full, pre = _generated()
    committed_full = load_schedule(str(_FULL))
    committed_pre = load_schedule(str(_PREFIX))
    assert committed_full.schedule_hash == full.schedule_hash
    assert committed_pre.schedule_hash == pre.schedule_hash
    assert committed_full.panel_hash == full.panel_hash == "760c1e5935fe0474"
    # Full field equality incl. provenance (team hashes, panel_split) — not covered by the hash.
    assert committed_full.rows == full.rows
    assert committed_pre.rows == pre.rows


def test_t3e_six_battle_regression_hash_unchanged():
    # The T3e/T3f smoke schedule regenerated with the extended generator must keep its
    # historical identity — proves the extensions changed nothing for existing call shapes.
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    sched = generate_dev_schedule(
        panel, policies=["simple_heuristic", "greedy_protect"], teams_root=_TEAMS_ROOT,
    )
    assert sched.schedule_hash == "db4d0a7a31070a62"
```

- [ ] **Step 2: Run, expect FAIL** (no module `t4_matrix`, no YAML files).

- [ ] **Step 3: Implement** `showdown_bot/src/showdown_bot/eval/t4_matrix.py`:

```python
"""T4 smoke-schedule matrix (2b-3.5 T4): the pinned 51-game weighted dev matrix.

Weights per the accepted design (docs/superpowers/reviews/2026-07-02-fable-t4-smoke-schedule-
design.md §2-3): heuristic and max_damage are the only informative opponents (5 seeds/cell);
the three weak policies are calibration rungs (3/2/2). Rows 0-9 form a stratified reproduction
prefix (all 5 policies + all 3 dev teams), so a fresh-server re-run of just the prefix schedule
with the same seed_base reproduces exactly those battles (seed_i depends only on
(seed_base, seed_index)).
"""
from __future__ import annotations

from showdown_bot.eval.panel_schedule import generate_dev_schedule, prefix_schedule

T4_SEEDS_PER_CELL = {
    "heuristic": 5,
    "max_damage": 5,
    "simple_heuristic": 3,
    "greedy_protect": 2,
    "scripted_vgc": 2,
}
T4_POLICIES = list(T4_SEEDS_PER_CELL)  # insertion order == canonical remainder policy order

# (opp_policy, team_id) picks for seed_index 0..9 — all 5 policies + all 3 dev teams;
# the extra 10th pick goes to the most informative cell.
T4_PREFIX_CELLS = [
    ("heuristic", "trickroom"), ("heuristic", "sun"), ("heuristic", "rain"),
    ("max_damage", "trickroom"), ("max_damage", "sun"), ("max_damage", "rain"),
    ("simple_heuristic", "trickroom"), ("greedy_protect", "sun"), ("scripted_vgc", "rain"),
    ("heuristic", "trickroom"),
]
T4_PREFIX_LEN = len(T4_PREFIX_CELLS)


def generate_t4_schedules(panel, *, teams_root="."):
    """(full 51-row schedule, 10-row reproduction-prefix schedule) for the T4 smoke."""
    full = generate_dev_schedule(
        panel, policies=T4_POLICIES, seeds_per_cell=T4_SEEDS_PER_CELL,
        prefix_cells=T4_PREFIX_CELLS, teams_root=teams_root,
    )
    return full, prefix_schedule(full, T4_PREFIX_LEN)
```

- [ ] **Step 4: Generate the committed YAMLs** (from repo root, Git Bash):

```bash
cd showdown_bot
python -c "from pathlib import Path; \
from showdown_bot.eval.panel import load_panel; \
from showdown_bot.eval.panel_schedule import write_schedule_yaml; \
from showdown_bot.eval.t4_matrix import generate_t4_schedules; \
sb = Path.cwd(); \
panel = load_panel(str(sb.parent/'config/eval/panels/panel_v001.yaml'), teams_root=str(sb)); \
full, pre = generate_t4_schedules(panel, teams_root=str(sb)); \
write_schedule_yaml(full, str(sb.parent/'config/eval/schedules/t4_smoke_v001.yaml')); \
write_schedule_yaml(pre, str(sb.parent/'config/eval/schedules/t4_smoke_v001_prefix.yaml')); \
print('full', len(full.rows), full.schedule_hash); print('prefix', len(pre.rows), pre.schedule_hash)"
cd ..
```

  Record both printed `schedule_hash` values — they go into the Task 7 report.

- [ ] **Step 5: Run tests, expect PASS** — `python -m pytest showdown_bot/tests/test_t4_matrix.py -q`,
  then the FULL suite (`python -m pytest showdown_bot/tests -q`, expect 659 + new tests, 0 failures).

- [ ] **Step 6: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/t4_matrix.py showdown_bot/tests/test_t4_matrix.py \
        config/eval/schedules/t4_smoke_v001.yaml config/eval/schedules/t4_smoke_v001_prefix.yaml
git commit -m "feat(2b-3.5 T4): pinned 51-game T4 matrix + committed schedules + drift test"
```

### Task 5: Full 51-game run (operational — no source changes)

**Files:** none in the repo during this task (outputs under `C:/tmp/t4/`, T4-CC-2). If any gate fails
or a battle stalls: capture evidence, kill the server, report BLOCKED — do NOT patch code, do NOT
retry a single battle (T4-CC-1).

- [ ] **Step 1: Preconditions.** `git status --porcelain` EMPTY (clean tree — the `dirty=false` gate);
  server clone check: `git -C ~/.cache/showdownbot/pokemon-showdown rev-parse HEAD` must equal the
  `showdown_commit` in `config/eval/provenance.yaml` (`f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`);
  no process listening on port 8000; `mkdir -p C:/tmp/t4`.

- [ ] **Step 2: Start the fresh seeded server** (background, Git Bash):

```bash
cd ~/.cache/showdownbot/pokemon-showdown
MSYS_NO_PATHCONV=1 SHOWDOWN_BATTLE_SEED_BASE=t4smoke2026 \
  SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t4/full_seeds.jsonl \
  node pokemon-showdown start 8000 --no-security
```

- [ ] **Step 3: Client run** (from `showdown_bot/`; expect ~1–2 h, 51 sequential battles; the
  per-battle timeout is the existing `games × 150 s` budget — one stall voids the run):

```bash
cd showdown_bot
MSYS_NO_PATHCONV=1 PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent \
  SHOWDOWN_BATTLE_SEED_BASE=t4smoke2026 \
  SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t4/full_seeds.jsonl \
  SHOWDOWN_EVAL_POLICY_TELEMETRY=C:/tmp/t4/full_telemetry.jsonl \
  SHOWDOWN_ROOM_RAW_DUMP=C:/tmp/t4/full_room_raw \
  python -m showdown_bot.cli gauntlet \
    --schedule ../config/eval/schedules/t4_smoke_v001.yaml \
    --result-out C:/tmp/t4/full_results.jsonl
```

  Expected console: 51 `seed_index=…` lines, `result JSONL: 51 rows written`, `seed-log alignment OK`.
  Kill the server afterwards.

- [ ] **Step 4: Gate verification.** Save this as
  `<scratchpad>/verify_t4.py`, run `python <scratchpad>/verify_t4.py C:/tmp/t4/full_results.jsonl ../config/eval/schedules/t4_smoke_v001.yaml C:/tmp/t4/full_seeds.jsonl C:/tmp/t4/full_telemetry.jsonl`
  from `showdown_bot/`. Every gate must print PASS; exit code 0. (This is a throwaway checker —
  the real report generator is T5's job; do NOT commit it.)

```python
"""T4 §4 gate checker (throwaway; T5 builds the real generator). All gates must PASS."""
import json, sys
from collections import Counter
from pathlib import Path

from showdown_bot.eval.gates import load_latency_budget_ms
from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.result_jsonl import validate_battle_row
from showdown_bot.eval.schedule import load_schedule, verify_schedule_alignment

RESULTS, SCHEDULE, SEEDLOG, TELEMETRY = sys.argv[1:5]
BASE = "t4smoke2026"
PANEL = Path(__file__).resolve()  # unused anchor; panel path given explicitly below
panel = load_panel("../config/eval/panels/panel_v001.yaml", teams_root=".")
sched = load_schedule(SCHEDULE)
rows = [json.loads(l) for l in open(RESULTS, encoding="utf-8") if l.strip()]
fails = []

def gate(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    if not ok:
        fails.append(name)

for r in rows:
    validate_battle_row(r)
gate("rows == 51 == schedule", len(rows) == 51 == len(sched.rows))
gate("invalid total == 0", sum(r["invalid_choices"] for r in rows) == 0)
gate("crashes total == 0", sum(r["crashes"] for r in rows) == 0)
gate("end_reason all normal", {r["end_reason"] for r in rows} == {"normal"})
budget = load_latency_budget_ms()
worst = max(r["decision_latency_p95_ms"] for r in rows)
gate(f"p95 latency < {budget} on every row", worst < budget, f"worst={worst}")
records = verify_schedule_alignment(sched, SEEDLOG, BASE)
gate("seed-log alignment (51 contiguous, derived)", len(records) == 51)
gate("no duplicate (battle_id, config_hash)",
     len({(r["battle_id"], r["config_hash"]) for r in rows}) == 51)
gate("panel_hash all == panel file", {r["panel_hash"] for r in rows} == {panel.panel_hash}
     and panel.panel_hash == "760c1e5935fe0474")
gate("dirty all false", {r["dirty"] for r in rows} == {False})
dev_hashes = {t.team_hash for t in panel.dev_teams}
held_hashes = {t.team_hash for t in panel.heldout_teams}
opp_hashes = {r["opp_team_hash"] for r in rows}
gate("hero/opp team hashes present", all(r["hero_team_hash"] and r["opp_team_hash"] for r in rows))
gate("opp hashes subset of dev teams", opp_hashes <= dev_hashes)
gate("no held-out anywhere", not (opp_hashes & held_hashes)
     and {r["panel_split"] for r in rows} == {"dev"})
gate("schedule reproducible-only", sched.reproducible is True)
for field in ("config_hash", "schedule_hash", "seed_base", "run_id", "git_sha"):
    gate(f"one {field} across rows", len({r[field] for r in rows}) == 1)
manifest = json.load(open(RESULTS + ".manifest.json", encoding="utf-8"))
gate("manifest matches rows",
     manifest["run_id"] == rows[0]["run_id"] and manifest["config_hash"] == rows[0]["config_hash"]
     and manifest["schedule_hash"] == sched.schedule_hash and manifest["seed_base"] == BASE
     and manifest["pythonhashseed"] == "0" and manifest["dirty"] is False
     and bool(manifest["server_patch_hash"]) and bool(manifest["showdown_commit"]))
events = Counter(json.loads(l)["event"] for l in open(TELEMETRY, encoding="utf-8") if l.strip())
gate("type_effectiveness_fired > 0", events.get("type_effectiveness_fired", 0) > 0,
     str(events.get("type_effectiveness_fired", 0)))
gate("hp_gated_protect_fired > 0", events.get("hp_gated_protect_fired", 0) > 0,
     str(events.get("hp_gated_protect_fired", 0)))
# Per-cell table for the report (policy x opp_team): n / W-L-T / turns range / mean hp diff.
cells = {}
for r in rows:
    cells.setdefault((r["opp_policy"], r["opp_team_path"]), []).append(r)
print("\nper-cell (policy, team): n W/L/T turns_min-max mean_end_hp_diff")
for key in sorted(cells):
    cs = cells[key]
    w = sum(1 for r in cs if r["winner"] == "hero")
    l = sum(1 for r in cs if r["winner"] == "villain")
    t = sum(1 for r in cs if r["winner"] == "tie")
    turns = [r["turns"] for r in cs]
    hp = [r["end_hp_diff"] for r in cs if r["end_hp_diff"] is not None]
    print(f"  {key}: n={len(cs)} {w}/{l}/{t} {min(turns)}-{max(turns)} "
          f"{(sum(hp)/len(hp)):+.3f}" if hp else f"  {key}: n={len(cs)} {w}/{l}/{t}")
print(f"\n{'ALL GATES PASS' if not fails else 'FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
```

- [ ] **Step 5:** Record the console per-cell table + gate output for the Task 7 report. No commit.

### Task 6: 10-row prefix reproduction run + comparison (operational)

- [ ] **Step 1: Fresh server again** — kill the old one, restart EXACTLY as Task 5 Step 2 but with
  `SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t4/prefix_seeds.jsonl` (same `SHOWDOWN_BATTLE_SEED_BASE=t4smoke2026`
  — the whole point: same base ⇒ rows 0–9 get the same seeds).

- [ ] **Step 2: Prefix client run** (from `showdown_bot/`):

```bash
MSYS_NO_PATHCONV=1 PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent \
  SHOWDOWN_BATTLE_SEED_BASE=t4smoke2026 \
  SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t4/prefix_seeds.jsonl \
  SHOWDOWN_ROOM_RAW_DUMP=C:/tmp/t4/prefix_room_raw \
  python -m showdown_bot.cli gauntlet \
    --schedule ../config/eval/schedules/t4_smoke_v001_prefix.yaml \
    --result-out C:/tmp/t4/prefix_results.jsonl
```

  Kill the server afterwards.

- [ ] **Step 3: Compare** — save as `<scratchpad>/compare_prefix.py`, run from `showdown_bot/`.
  Expect: 10/10 battles byte-identical normalized logs AND 10/10 identical winners + seeds.

```python
"""T4 reproduction evidence: prefix run must byte-identically reproduce full-run rows 0-9."""
import json, re, sys
from pathlib import Path

from showdown_bot.eval.room_dump import GAUNTLET_NAME_SUBS, compare_battle_logs

FULL_DIR, PRE_DIR = Path("C:/tmp/t4/full_room_raw"), Path("C:/tmp/t4/prefix_room_raw")
FULL_RES, PRE_RES = "C:/tmp/t4/full_results.jsonl", "C:/tmp/t4/prefix_results.jsonl"

def by_room_number(d):
    files = sorted(d.glob("*.log"), key=lambda p: int(re.search(r"(\d+)$", p.stem).group(1)))
    return files

full_logs, pre_logs = by_room_number(FULL_DIR)[:10], by_room_number(PRE_DIR)
assert len(pre_logs) == 10, f"expected 10 prefix dumps, got {len(pre_logs)}"
bad = 0
for i, (fa, fb) in enumerate(zip(full_logs, pre_logs)):
    identical, diff = compare_battle_logs(
        fa.read_text(encoding="utf-8").splitlines(),
        fb.read_text(encoding="utf-8").splitlines(),
        name_subs=GAUNTLET_NAME_SUBS,
    )
    print(f"battle {i}: {'identical' if identical else 'DIFFERS'}")
    if not identical:
        bad += 1
        print(diff[:2000])
full_rows = [json.loads(l) for l in open(FULL_RES, encoding="utf-8") if l.strip()][:10]
pre_rows = [json.loads(l) for l in open(PRE_RES, encoding="utf-8") if l.strip()]
for i, (a, b) in enumerate(zip(full_rows, pre_rows)):
    ok = a["winner"] == b["winner"] and a["seed"] == b["seed"] and a["turns"] == b["turns"]
    print(f"row {i}: winner {a['winner']}=={b['winner']} seed match={a['seed']==b['seed']}")
    if not ok:
        bad += 1
print("REPRODUCTION PASS" if bad == 0 else f"REPRODUCTION FAIL ({bad})")
sys.exit(1 if bad else 0)
```

  Note: `battle_id` differs between the runs by design (it hashes `schedule_hash`, which differs
  between the 51-row and 10-row schedules) — the comparison is over room_raw + winner + seed + turns,
  never battle_id. If room-log filenames don't carry a trailing room number as assumed, adapt
  `by_room_number` to the actual `dump_room_raw` naming (`<name>__<room>.log`) — pairing must be by
  battle creation order in both runs.

- [ ] **Step 4 (opportunistic, only if the full run took < ~90 min):** repeat Task 5 Steps 2–3 into
  `C:/tmp/t4/full2_*` and diff all 51 normalized logs the same way. Strictly better evidence; the
  prefix check remains the gate.

### Task 7: Commit artifacts + hand-assembled report

**Files:**
- Create: `data/eval/t4/` — `t4-smoke.jsonl`, `t4-smoke.jsonl.manifest.json`, `t4-seedlog.jsonl`,
  `t4-telemetry.jsonl`, `t4-prefix.jsonl`, `t4-prefix.jsonl.manifest.json`, `t4-prefix-seedlog.jsonl`,
  `room_raw/full/*.log.gz`, `room_raw/prefix/*.log.gz`
- Create: `reports/<RUN-DATE>-2b35-T4-smoke.md` (use the actual run date)

- [ ] **Step 1: Copy artifacts into the repo** (only now — T4-CC-2), gzip each room log:

```bash
mkdir -p data/eval/t4/room_raw/full data/eval/t4/room_raw/prefix
cp C:/tmp/t4/full_results.jsonl                data/eval/t4/t4-smoke.jsonl
cp C:/tmp/t4/full_results.jsonl.manifest.json  data/eval/t4/t4-smoke.jsonl.manifest.json
cp C:/tmp/t4/full_seeds.jsonl                  data/eval/t4/t4-seedlog.jsonl
cp C:/tmp/t4/full_telemetry.jsonl              data/eval/t4/t4-telemetry.jsonl
cp C:/tmp/t4/prefix_results.jsonl              data/eval/t4/t4-prefix.jsonl
cp C:/tmp/t4/prefix_results.jsonl.manifest.json data/eval/t4/t4-prefix.jsonl.manifest.json
cp C:/tmp/t4/prefix_seeds.jsonl                data/eval/t4/t4-prefix-seedlog.jsonl
for f in C:/tmp/t4/full_room_raw/*.log;   do gzip -c "$f" > "data/eval/t4/room_raw/full/$(basename "$f").gz"; done
for f in C:/tmp/t4/prefix_room_raw/*.log; do gzip -c "$f" > "data/eval/t4/room_raw/prefix/$(basename "$f").gz"; done
sha256sum data/eval/t4/*.jsonl data/eval/t4/*.json
```

  Record the sha256 lines for the report. Add `data/eval/t4/** -text` plus
  `data/eval/t4/room_raw/** binary` to `.gitattributes` (same platform-stability class as
  `models/reranker/**` and `*.patch`).

- [ ] **Step 2: Write the report** `reports/<RUN-DATE>-2b35-T4-smoke.md`, following the structure of
  `reports/2026-07-09-2b35-T3f-run-provenance-smoke.md`, with exactly these sections (review §8):
  1. **Verdict line** — PASS/FAIL + "pipeline validation; non-evidentiary; does not touch 2b-4".
  2. **Provenance block** — schedule_hash (full + prefix), panel_hash, config_hash, run_ids, seed_base
     `t4smoke2026`, git_sha + dirty, hero/opp team hashes, server patch hash + showdown_commit,
     PYTHONHASHSEED, sha256s of every committed artifact.
  3. **Safety-gates table** — every Task 5 gate with its measured value.
  4. **Reproduction evidence** — per-battle identical/differs, winner + seed match, for all 10.
  5. **Activation telemetry** — both event counts, per policy.
  6. **Per-cell results table** — policy × team: n, W/L/T, turns range, mean end_hp_diff;
     heuristic/max_damage visually separated from the calibration cells, the latter labeled
     "calibration cells — non-evidentiary".
  7. **Reference numbers** — per-policy win counts, labeled "informal pre-baseline; superseded by T6
     pinning". NO pooled all-policy win rate anywhere.
  8. **Mandatory caveats — include verbatim:** "T4 is a pipeline validation at ~50 games. No cell has
     enough games for a confidence interval that could support any strength claim. Nothing in this
     report is evidence for or against the reranker, and this report does not contribute to the 2b-4
     unblock decision — that requires T5 statistics on T6's pinned baseline with the positive-evidence
     rule." Plus the one-sentence why-not-2b-4: "2b-4 requires paired McNemar vs a pinned baseline
     with n_discordant ≥ 10 and positive delta (T5/T6); T4 has no comparison config at all — it is a
     single-config run by design."
  9. **Reproduction commands** — the exact Task 5/6 server + client command lines and the
     re-runnable alignment check:
     `python -c "from showdown_bot.eval.schedule import load_schedule, verify_schedule_alignment; verify_schedule_alignment(load_schedule('../config/eval/schedules/t4_smoke_v001.yaml'), '../data/eval/t4/t4-seedlog.jsonl', 't4smoke2026')"`.

- [ ] **Step 3: Full suite green** — `python -m pytest showdown_bot/tests -q` (nothing in Tasks 5–7
  touched source; this is the pre-commit sanity).

- [ ] **Step 4: Commit**

```bash
git add data/eval/t4 .gitattributes reports/<RUN-DATE>-2b35-T4-smoke.md
git commit -m "docs(2b-3.5 T4): 51-game smoke report + committed run artifacts"
```

---

## Out of scope (T5/T6, not T4 — review §9)

No Wilson/McNemar or any report *generator* (the gate checker above is throwaway, uncommitted); no
T5 statistics; no T6 held-out gate/ledger/baseline pinning; no held-out teams touched; no
reranker/shadow involvement (env OFF); no panel growth; no policy tuning (odd weak-policy behavior is
filed, not fixed here); no parallel battle execution; no battle-level retries. `battle/` untouched.

## Self-review (writing-plans)

- **Spec coverage vs review:** §3 matrix + weights (Task 4), §3 prefix ordering (Tasks 2+4), §10.1
  generator capability (Tasks 1–2), §5 reproduction evidence via prefix schedule (Tasks 3, 6), §4 all
  14 gates (Task 5 checker incl. activation telemetry, dirty, duplicates, held-out exclusion, latency
  budget via the T3f loader), §6 phrasing rules + §8 report outline (Task 7), §7 artifact paths
  (Task 7; JSONL committed per the user's 2026-07-10 decision), §10.2 T3f preconditions (met, merged),
  §10.3 commit decision (resolved: commit). ✓
- **Placeholder scan:** all code complete; the two operational scripts are full programs; the only
  open token is `<RUN-DATE>` (unknowable until execution) and the recorded schedule hashes (printed at
  Task 4 Step 4). The prefix-comparison pairing assumption (trailing room number) is flagged with the
  concrete fallback rule (pair by creation order). ✓
- **Type consistency:** `prefix_cells` is `(opp_policy, team_id)` everywhere (Task 2 helper, tests,
  `T4_PREFIX_CELLS`); `seeds_per_cell` int-or-mapping flows through `_validate_seeds_per_cell`/
  `_seeds_for` only; `prefix_schedule(schedule, n)` matches its Task 4 call
  `prefix_schedule(full, T4_PREFIX_LEN)`. ✓
- **Regression guards:** T3e 6-battle `schedule_hash db4d0a7a31070a62` re-pinned (Task 4); `None`
  prefix + int seeds paths hash-identical to today (Tasks 1–2); loader untouched (committed YAMLs go
  through `load_schedule` in the drift test). ✓

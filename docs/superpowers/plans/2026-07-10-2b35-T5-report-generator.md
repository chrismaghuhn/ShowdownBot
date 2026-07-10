# 2b-3.5 T5 — Report Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude.** Steps use `- [ ]`. Implements the approved spec
> `docs/superpowers/specs/2026-07-10-t5-report-generator-design.md`; the statistical rationale lives
> in `docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-architecture-review.md`. The spec is the
> authority on section order, verdict vocabulary, and verbatim texts — read BOTH before any task.

**Goal:** `eval/stats.py` + `eval/pairing.py` + `eval/report.py` + CLI `eval-report`: deterministic
md+json eval reports with safety-gates-before-statistics, Wilson per-cell tables, exact-binomial
McNemar (paired mode), positive-evidence-only verdicts, and a committed golden report against the
T4-rerun fixture.

**Architecture:** three new modules with one-way deps (`report` → `pairing` → `stats`; `report` →
existing `eval/{schedule,panel,gates,seeding,result_jsonl,run_manifest}`). No changes to writers,
gauntlet, or `battle/`. stdlib only.

**Suite baseline:** 688 passed. Branch: create `feat/slice-2b35-t5-report-generator` off `main`.

---

### Task 1: `eval/stats.py` — pure statistics + pinned verdict constants

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/stats.py`
- Test: `showdown_bot/tests/test_eval_stats.py`

- [ ] **Step 1: Failing tests** (`test_eval_stats.py`):

```python
"""T5 stats: exact values pinned so the verdict gates rest on verified math."""
import math

import pytest

from showdown_bot.eval.stats import (
    LOSING_CELL_WILSON_UPPER,
    N_DISCORDANT_CLAIM_MIN,
    N_DISCORDANT_MATH_FLOOR,
    TIE_FLAG_RATE,
    McnemarCounts,
    exact_binom_two_sided_p,
    mcnemar_counts,
    wilson_interval,
)


def test_constants_pinned():
    assert N_DISCORDANT_MATH_FLOOR == 6
    assert N_DISCORDANT_CLAIM_MIN == 10
    assert LOSING_CELL_WILSON_UPPER == 0.5
    assert TIE_FLAG_RATE == 0.02


def test_exact_binom_pinned_values():
    assert exact_binom_two_sided_p(6, 6) == pytest.approx(0.03125)
    assert exact_binom_two_sided_p(0, 6) == pytest.approx(0.03125)   # symmetric
    assert exact_binom_two_sided_p(5, 6) == pytest.approx(0.21875)
    assert exact_binom_two_sided_p(3, 6) == pytest.approx(1.0)       # dead center
    assert exact_binom_two_sided_p(0, 0) == 1.0                      # no data -> no evidence
    assert exact_binom_two_sided_p(9, 10) == pytest.approx(22 / 1024)  # 2*(1+10)/1024


def test_wilson_known_values():
    lo, hi = wilson_interval(0, 0)
    assert (lo, hi) == (0.0, 1.0)                                    # no data -> maximal interval
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3)                     # published Wilson 95% values
    assert hi == pytest.approx(0.7634, abs=1e-3)
    lo, hi = wilson_interval(10, 10)
    assert lo == pytest.approx(0.7225, abs=1e-3)
    assert hi == 1.0
    lo, hi = wilson_interval(0, 5)
    assert lo == 0.0
    assert hi == pytest.approx(0.4345, abs=1e-3)


def test_mcnemar_counts_and_delta():
    # pairs as (hero_win_a, hero_win_b); ties were already mapped to False upstream
    pairs = [(True, True)] * 3 + [(False, False)] * 2 + [(True, False)] * 4 + [(False, True)] * 1
    c = mcnemar_counts(pairs)
    assert (c.n11, c.n00, c.n10, c.n01) == (3, 2, 4, 1)
    assert c.n_discordant == 5
    assert c.delta == pytest.approx((4 - 1) / 10)
    assert McnemarCounts(0, 0, 0, 0).delta == 0.0                    # empty-safe
```

- [ ] **Step 2: Run, expect FAIL** (module missing).

- [ ] **Step 3: Implement** `eval/stats.py`:

```python
"""T5 statistics primitives (stdlib only) + the pinned verdict constants.

The thresholds are CODE, not prose (review §3): the exact binomial test cannot reach
p < 0.05 below 6 discordant pairs (a 6/6 split gives p = 2/64 = 0.03125), and no claim
may appear in a verdict line below 10. A cell whose Wilson upper bound is below 0.5 is
a "losing cell" and must surface in the verdict. Tie shares above 2% get flagged
(degeneracy suspicion). Rationale: docs/superpowers/reviews/2026-07-01-fable-t5-t6-
eval-architecture-review.md §3-4.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

N_DISCORDANT_MATH_FLOOR = 6    # below: p<0.05 mathematically unreachable
N_DISCORDANT_CLAIM_MIN = 10    # below: no claim in any verdict line (UNDERPOWERED)
LOSING_CELL_WILSON_UPPER = 0.5
TIE_FLAG_RATE = 0.02


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% interval on a win proportion (ties counted as losses upstream)."""
    if n == 0:
        return (0.0, 1.0)
    phat = wins / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def exact_binom_two_sided_p(k: int, n: int) -> float:
    """Exact two-sided binomial test at p=0.5 ("small p-values" method): the sum of
    P(X=i) over all outcomes no more likely than the observed one. Chi-square is
    invalid at this N — this is exact by construction (math.comb)."""
    if n == 0:
        return 1.0
    total = 2 ** n
    pk = math.comb(n, k)
    return min(1.0, sum(math.comb(n, i) for i in range(n + 1) if math.comb(n, i) <= pk) / total)


@dataclass(frozen=True)
class McnemarCounts:
    n11: int  # both won
    n00: int  # both lost (ties land here — tie = not-a-win)
    n10: int  # A won, B lost
    n01: int  # B won, A lost

    @property
    def n_discordant(self) -> int:
        return self.n10 + self.n01

    @property
    def total(self) -> int:
        return self.n11 + self.n00 + self.n10 + self.n01

    @property
    def delta(self) -> float:
        """(n10 - n01) / N == winrate_A - winrate_B; 0.0 on empty input."""
        return 0.0 if self.total == 0 else (self.n10 - self.n01) / self.total


def mcnemar_counts(pairs) -> McnemarCounts:
    """pairs: iterable of (hero_win_a: bool, hero_win_b: bool)."""
    n11 = n00 = n10 = n01 = 0
    for a, b in pairs:
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif b and not a:
            n01 += 1
        else:
            n00 += 1
    return McnemarCounts(n11, n00, n10, n01)
```

- [ ] **Step 4: Tests green; full suite green (688 + new).**
- [ ] **Step 5: Commit** `feat(2b-3.5 T5): stats primitives + pinned verdict constants`

### Task 2: `eval/pairing.py` — the pairing validator

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/pairing.py`
- Test: `showdown_bot/tests/test_eval_pairing.py`

- [ ] **Step 1: Failing tests.** Build a small synthetic-row helper in the test file:

```python
def _row(seed_index, *, config_hash="cfgA", winner="hero", schedule_hash="sched1",
         seed_base="base1", panel_hash="pan1", format_id="gen9vgc2025regi",
         opp_policy="heuristic", opp_team_hash="team1", seed=None, battle_id=None):
    return {
        "battle_id": battle_id or f"b{seed_index}", "config_hash": config_hash,
        "schedule_hash": schedule_hash, "seed_base": seed_base, "panel_hash": panel_hash,
        "format_id": format_id, "seed_index": seed_index, "opp_policy": opp_policy,
        "opp_team_hash": opp_team_hash, "seed": seed or f"sodium,{seed_index:032x}",
        "winner": winner,
    }
```

Cover, each with `pytest.raises` on the SPECIFIC exception: `SelfComparisonError`
(config_hash equal), `RunMismatchError` (schedule_hash / seed_base / panel_hash / format_id
differ — parametrize), `PairSeedMismatchError` (same battle_id, different seed),
`DuplicateRowError` (duplicate (battle_id, config_hash) within one run), `MissingPairError`
(row counts differ / a battle_id present on one side only), plus the happy path:

```python
def test_pair_runs_happy_path_and_tie_semantics():
    a = [_row(0, winner="hero"), _row(1, winner="villain"), _row(2, winner="tie")]
    b = [_row(0, winner="villain", config_hash="cfgB"),
         _row(1, winner="hero", config_hash="cfgB"),
         _row(2, winner="hero", config_hash="cfgB")]
    pairs = pair_runs(a, b)
    assert [(p.hero_win_a, p.hero_win_b) for p in pairs] == [
        (True, False), (False, True), (False, True)]          # tie = not-a-win
    assert pairs[0].cell == ("heuristic", "team1")
    counts = mcnemar_counts([(p.hero_win_a, p.hero_win_b) for p in pairs])
    assert (counts.n10, counts.n01) == (1, 2)
```

Also: `expected_rows=` kwarg enforcement (`RowCountError` when len != expected, e.g. schedule
row count), and ordering: returned pairs sorted by seed_index.

- [ ] **Step 2: FAIL run.**
- [ ] **Step 3: Implement** `eval/pairing.py`: exception hierarchy (`PairingError(ValueError)` +
  the five subclasses above + `RowCountError`), `Pair` frozen dataclass
  `(battle_id, seed_index, cell, hero_win_a, hero_win_b, row_a, row_b)`,
  `pair_runs(rows_a, rows_b, *, expected_rows=None) -> list[Pair]` implementing exactly the spec
  §1.2 checks in this order: per-run duplicates → per-run constant
  (schedule_hash, seed_base, panel_hash, format_id, config_hash) with `RunMismatchError` on
  non-constant-within-run too → cross-run pairability (those four equal; config_hash MUST differ)
  → row counts equal (+ expected_rows) → battle_id sets equal → per-pair seed equality →
  build sorted pairs with `hero_win = (winner == "hero")`.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit** `feat(2b-3.5 T5): pairing validator (fail-fast, positive-evidence substrate)`

### Task 3: `eval/report.py` part 1 — RunBundle, input audit, safety gates, single-run report

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/report.py`
- Test: `showdown_bot/tests/test_eval_report.py`

Read first: `eval/result_jsonl.py` (row fields + `validate_battle_row`), `eval/run_manifest.py`
(manifest fields, `manifest_path_for`), `eval/schedule.py` (`load_schedule`,
`verify_schedule_alignment`), `eval/panel.py` (`load_panel`, team hashes), `eval/gates.py`,
`eval/policies.py` (`is_reproducible`). The REAL fixture for happy-path tests is
`data/eval/t4/rerun/` (run 1 bundle: `t4rerun-run1.jsonl` + its manifest + `t4rerun-run1-seedlog.jsonl`
+ `config/eval/schedules/t4_smoke_v001.yaml` + `config/eval/panels/panel_v001.yaml`,
seed base `t4rerun2026`).

- [ ] **Step 1: Failing tests** — structure:
  - `RunBundle.load(results_path, seedlog_path, schedule_path, panel_path, teams_root)` loads +
    audits: rows validate, manifest sidecar found + cross-checked (run_id/config_hash/seed_base/
    git_sha/dirty constant across rows AND == manifest), seed-log alignment RE-RUN via
    `verify_schedule_alignment`, panel_hash recomputed from the panel file == rows', input sha256s
    recorded. On the real fixture: loads clean.
  - Safety gates (spec §1.3 list) return a table of `(gate, status, measured)`; on the real
    fixture all PASS.
  - `generate_report(bundle, mode="gate") -> (md: str, json_obj: dict)`: first line
    `# VERDICT: SINGLE-RUN SAFETY-PASS`, sections in spec §1.3 order, `schema_version: 1`,
    per-cell Wilson table matches hand-computed values for the fixture (spot-check 2 cells:
    scripted_vgc/rain = 2/2 wins, heuristic/sun = 0/5).
  - Determinism: `generate_report` twice → identical strings.
  - Tamper tests (R6) on tmp copies of the fixture: flip one winner in the JSONL → row/manifest
    cross-check or gate flips verdict to `SINGLE-RUN SAFETY-FAIL`; edit one seed-log line →
    SAFETY-FAIL; point at a panel file with one team path swapped → SAFETY-FAIL. (Copy fixture
    files to tmp_path, mutate, expect the loader/gates to catch each.)
  - `mode="dev"` downgrades ONLY latency + dirty to WARN (craft a synthetic row set with dirty=True).
- [ ] **Step 2: FAIL run.**
- [ ] **Step 3: Implement.** Keep `report.py` focused: `RunBundle` (load + audit), `run_safety_gates`,
  cell/aggregate builders (`wilson_interval` from Task 1), md renderer + json builder (shared data
  dict → two renderers, NO timestamps except manifest values). Verbatim-text constants module-level.
  Losing-cell + worst-cell computed here (single-run mode reports them descriptively, no GO/NO-GO).
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit** `feat(2b-3.5 T5): run bundle audit + safety gates + single-run report`

### Task 4: `eval/report.py` part 2 — paired mode + verdict logic

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/report.py`
- Test: `showdown_bot/tests/test_eval_report_paired.py`

- [ ] **Step 1: Failing tests** — synthetic bundle pairs (build tiny JSONL+seedlog+schedule
  fixtures in tmp_path via helpers, or a lighter `generate_report_paired(rows_a, rows_b, ...)`
  seam — follow what Task 3's structure suggests; document the choice). Verdict paths, each one test:
  - **GO:** n_discordant ≥ 10, delta > 0, exact p < 0.05, no losing-cell flip, improvement present
    on heuristic/max_damage cells → first line `# VERDICT: GO`, worst-cell callout present.
  - **NO-GO (p too high):** n_discordant ≥ 10 but p ≥ 0.05.
  - **NO-GO (cell flip):** aggregate GO-worthy but one cell flips winning→losing vs run A → NO-GO
    with the cell named.
  - **NO-GO (weak-policy-only):** delta driven by greedy_protect/scripted_vgc cells while
    heuristic+max_damage delta ≤ 0 → NO-GO with the §9 wording.
  - **UNDERPOWERED:** n_discordant < 10 → verbatim banner, NO p-value in the verdict line,
    discordant-battle list present (n ≤ 12) with battle_id/cell/turns/end_hp_diff.
  - **SAFETY-FAIL dominates:** inject one crash row → SAFETY-FAIL even with GO-worthy stats.
  - **Zero-discordant ambiguity:** n_discordant == 0 → report text contains the
    "behaviorally identical OR mislabeled duplicate" wording, never "stable".
  - **Tie flag:** tie share > 2% → flagged line present.
  - Paired section adjacency (spec §1.3 last bullet): md contains NO side-by-side independent
    CI comparison of A vs B outside the paired section.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** paired flow: `pair_runs` → `mcnemar_counts` → verdict decision tree
  (SAFETY-FAIL > UNDERPOWERED > GO > NO-GO, exactly spec §1.3), paired md/json sections,
  discordant list builder.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit** `feat(2b-3.5 T5): paired McNemar report + positive-evidence verdicts`

### Task 5: CLI `eval-report`

**Files:**
- Modify: `showdown_bot/src/showdown_bot/cli.py` (new subcommand, mirroring the existing
  argparse structure)
- Test: `showdown_bot/tests/test_cli_eval_report.py`

- [ ] Failing tests: invoking the CLI entry function on the real fixture writes `report.md` +
  `report.json` to `--out` dir with the SAFETY-PASS verdict, exit code 0; a tampered copy →
  exit code 1; `--run-b` without `--seedlog-b` → SystemExit with a clear message; `--mode dev`
  accepted, default `gate`. (Call the command function directly like existing CLI tests do —
  read `tests/` for the pattern, e.g. how run_schedule/gauntlet CLI paths are tested.)
- [ ] Implement: `eval-report` subparser (`--run-a --seedlog-a [--run-b --seedlog-b] --schedule
  --panel --out [--mode gate|dev] [--teams-root]`), manifest sidecars via `manifest_path_for`
  convention, exit 1 iff SAFETY-FAIL.
- [ ] Green + full suite. **Commit** `feat(2b-3.5 T5): eval-report CLI`

### Task 6: Golden report against the T4-rerun fixture

**Files:**
- Create: `data/eval/t4/rerun/golden-report.md` + `data/eval/t4/rerun/golden-report.json` (generated)
- Test: `showdown_bot/tests/test_eval_report_golden.py`

- [ ] Generate via the Task 5 CLI on the committed fixture (run 1 bundle, mode gate, out to a
  temp dir), then copy both files into `data/eval/t4/rerun/`. Inspect them once by hand
  (verdict `SINGLE-RUN SAFETY-PASS`, per-cell numbers match
  `reports/2026-07-10-2b35-T4-rerun.md`).
- [ ] Test: regenerate in tmp_path and assert BYTE-identical equality with the committed golden
  files (this is the R5 determinism proof AND a drift guard on the whole pipeline).
  Note: `.gitattributes` already has `data/eval/t4/** -text` — byte-compare via `rb` reads.
- [ ] Full suite green. **Commit** `feat(2b-3.5 T5): golden report fixture (byte-identical drift guard)`

### Task 7: Closeout

- [ ] Full suite (expect ~730±, 0 failures), skim `git diff main --stat` for scope discipline
  (only the planned files + tests + golden artifacts).
- [ ] Update `docs/architecture/brain-v1-northstar.md`? NO — out of scope (T6 will).
- [ ] Report back to controller for final review + merge decision.

---

## Out of scope
T6 (ledger/baseline/held-out), gauntlet/writer changes, `battle/`, new deps, panel/schedule
changes, any new runs (the fixture suffices).

## Self-review (writing-plans)
- Spec coverage: R1→Task 1, R2→Task 2, R3/R4→Tasks 3-4, R5→Tasks 3+6, R6→Task 3, R7→Tasks 3+6,
  R8→every task's full-suite step. CLI incl. `--mode` →Task 5. Verbatim texts + section order
  delegated to the spec §1.3 (the authority) rather than duplicated here — deliberate, both docs
  are committed and cross-referenced. ✓
- Placeholder scan: Task 1-2 fully coded; Tasks 3-5 specify exact test cases, fixture paths, field
  sources, and structure but leave renderer internals to the implementer WITH the spec's exact
  section list — acceptable altitude for a generator; the golden test (Task 6) pins the output
  byte-exactly afterwards. Verified pinned math: p(6,6)=2/64, p(5,6)=14/64, p(9,10)=22/1024. ✓
- Type consistency: `mcnemar_counts(pairs)` consumes `(bool, bool)` tuples — Task 2's
  `pair_runs` exposes `hero_win_a/b` for exactly that; `wilson_interval` consumed by report
  builders; CLI exit semantics match spec §1.4. ✓

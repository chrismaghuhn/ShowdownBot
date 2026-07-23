# Gate B — baseline-immutability history rewrite: pre→post SHA map

**Status: durable record of an authorized history rewrite on branch
`feat/champions-gate-b-task-1-schedule`.** No code or contract change is described here; this file
exists so that every commit SHA cited elsewhere in the branch stays resolvable after the rewrite,
even once the local backup branch is deleted.

## Why the rewrite happened

The Gate B static baseline manifest `config/eval/baselines/champions-strength-holdout-v0.json` had
been committed **twice**: once as a schema-loadable placeholder (Task 6) and once back-filled with
real values (Task 13 step 3). A baseline manifest is **immutable after its first commit** — the
generic T6 contract enforces this with `test_baseline_manifest_git_immutability`
(`showdown_bot/tests/test_baseline.py`), whose message is explicit: *"a change requires a NEW
versioned file."* The double commit failed that test.

Under **explicit owner authorization** (2026-07-23), the feature branch was rewritten with
`git filter-branch` so the baseline manifest is **created exactly once**, with its final real
values, in the (rewritten) step-3 commit. Constraints honored: the generic immutability test was
**not** changed and **no** exemption was added; the final tree is **byte-identical** to the
pre-rewrite HEAD `0f98e0e` except for the authorized Rev. 25 plan correction; a backup branch
`backup/pre-immutability-rewrite` was created at `0f98e0e` before the rewrite. The post-rewrite full
offline suite is green (**3586 passed, 3 skipped, 1 xfailed, 0 failed**).

## How to read cited SHAs

**Every commit SHA cited anywhere in this branch's documentation, plan revision notes, audits, and
inline code/test comments that predates 2026-07-23 is a PRE-REWRITE ID.** Those references are left
in place (they are historically accurate for the pre-rewrite history) but must be resolved through
the table below to find the commit that carries the same change in the current, rewritten history.

Known pre-rewrite references still present in the tree (non-exhaustive, all resolvable via the table):

- `docs/projects/champions/plans/2026-07-21-gate-b-independent-strength-holdout.md` — revision-note
  SHAs in §1r/§1s/§1t and the Task 10/11 sync notes (e.g. `24ada4b`, `895d1d2`, `53e6c9c`,
  `b71923f`, `6658625`, `cdf893a`, `9d31265`).
- `docs/projects/champions/audits/2026-07-22-gate-b-source-proof-independent-review.md` — "Repo
  state at review, HEAD `cebf99f`".
- `showdown_bot/tests/test_strength_holdout_runner.py` — an inline comment referencing `24ada4b`.

These are **not** rewritten in place: editing the test comment would be a code change (and would
force a re-run) for no functional benefit, and the plan/audit revision notes are historical records
of what happened at each pre-rewrite SHA. This table is the single authoritative resolver.

## Pre → post SHA map (38 rewritten commits, oldest first)

The parent of the rewritten range, `12b2170` (Task 5 era), and everything before it are **unchanged**.

| # | pre-rewrite | post-rewrite | subject |
|---|---|---|---|
| 1 | `b7bbd4e` | `9ffb63d` | feat(champions): new Champions strength-holdout baseline manifest |
| 2 | `8feef4c` | `2e92c2c` | feat(champions): full closed-schema verification for the I8-D and Coverage upstream verdicts |
| 3 | `8120626` | `20497e0` | fix(champions): close two Gate B verdict-verifier gaps from review |
| 4 | `a0c14de` | `1c182aa` | feat(champions): wire Gate B into the real report.py cell-flip/strength-delta McNemar pipeline |
| 5 | `02b7ca1` | `e435aeb` | fix(champions): close three Gate B verdict-rendering gaps from review |
| 6 | `eae0946` | `98bcbaf` | feat(champions): Gate B single-arm battle execution with injectable gauntlet runner |
| 7 | `6658625` | `b112f61` | fix(champions): close five P1 trust gaps and one P2 in Gate B single-arm execution |
| 8 | `765784e` | `8973c69` | docs(champions): synchronize Gate B Task 10 with sealed arm manifests |
| 9 | `24ada4b` | `aed1d32` | feat(champions): combine Gate B arms with all guards and sealed evidence |
| 10 | `895d1d2` | `369a6c1` | fix(champions): close three P1 and two P2 trust gaps in Gate B combine |
| 11 | `53e6c9c` | `a92c3c4` | fix(champions): bind Gate B result rows to canonical battle identity |
| 12 | `cdf893a` | `413cf2e` | docs(champions): sync Gate B Task 10 with its merged implementation (Rev. 20) |
| 13 | `b71923f` | `2cef85d` | feat(champions): add Gate B arm and combine CLI subcommands |
| 14 | `9d31265` | `7344dcc` | docs(champions): sync Gate B Task 11 with flat CLI implementation |
| 15 | `8dd093c` | `822810d` | feat(champions): add fail-closed Gate B team sealing |
| 16 | `cebf99f` | `ad04305` | fix(champions): bind the .packed sibling to teams_root when sealing |
| 17 | `3815d4c` | `44fa159` | docs(champions): bind Gate B Task 13 to complete published VGCPastes |
| 18 | `7a3504c` | `a95820b` | docs(champions): freeze the Task 13 selection proof and close four contract gaps |
| 19 | `a8b2601` | `ec02fcb` | docs(champions): freeze the format declarations and fix the plan status block |
| 20 | `5c98ab1` | `550a72d` | docs(champions): reconcile the four Gate B plan status surfaces |
| 21 | `0b9e581` | `3ef6db5` | docs(champions): reconcile Gate B Rev. 22 execution status |
| 22 | `1c2a31b` | `e8927a1` | feat(champions): seal six published M-A holdout teams |
| 23 | `7f1198a` | `40273d3` | feat(champions): opaque holdout ids and a bounded source-evidence allowlist |
| 24 | `1b4efe2` | `e9101c0` | docs(champions): record APPROVED Amendment A1 for Gate B |
| 25 | `a0e9e12` | `c18f274` | fix(champions): regression-test the source-evidence allowlist and correct A1.1 |
| 26 | `ce6cd6b` | `3168229` | docs(champions): sync Task 13 status with the landed team artifacts |
| 27 | `18d4208` | `280de23` | feat(champions): add the Gate B static baseline contract |
| 28 | `6449288` | `4b34419` | feat(champions): wire the Gate B combiner onto its own baseline contract |
| 29 | `699dbdb` | `1f79c2d` | fix(champions): bind the Gate B baseline to hero, holdout manifest and pythonhashseed |
| 30 | `7d3f214` | `f0d4d79` | feat(champions): enforce PYTHONHASHSEED across the Gate B arm and combine flow |
| 31 | `b0cb3bf` | `a5e5e72` | fix(champions): make Gate B reproducibility guards load-bearing (P1/P2) |
| 32 | `1cf4f0c` | `549137f` | docs(champions): sync Gate B plan to Rev. 23 (Task 13 step 3 active) |
| 33 | `9b913e2` | `aff2308` | feat(champions): freeze Gate B panel, baseline values, and hash constants **(now the single commit that creates the baseline JSON)** |
| 34 | `2de3041` | `b08cf8a` | feat(champions): wire Gate B CLI to real holdout data (remove Task-13 stub) |
| 35 | `f56d3d9` | `5f4723f` | docs(champions): record Gate B reference near-duplicate audit (Task 13 step 3) |
| 36 | `5902e56` | `b771e80` | fix(champions): enforce frozen Gate B identity before battle 1 (P1/P2) |
| 37 | `9541d0c` | `31eea63` | fix(champions): verify baseline in the arm + harden manifest hash (P1/P2) |
| 38 | `0f98e0e` | `3003d99` | fix(champions): enforce unique source_team_id + close stale §19 conclusion (P2) |

## Post-rewrite-only commits (no pre-rewrite counterpart)

| post-rewrite | subject |
|---|---|
| `c5ad3f2` | docs(champions): align Gate B plan with single-commit baseline (Rev. 25) |
| _this file_ | docs(champions): record the baseline-immutability rewrite SHA map |

**Backup branch:** `backup/pre-immutability-rewrite` → `0f98e0e` (local only; not pushed). It is the
authoritative pre-rewrite reference until the branch is merged; delete it only after merge, since
this table then becomes the sole resolver for the pre-rewrite SHAs above.

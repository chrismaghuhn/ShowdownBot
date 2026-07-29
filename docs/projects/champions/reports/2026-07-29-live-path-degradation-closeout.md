# Live-path degradation recording — closeout

**Slice:** #125 · **Branch:** `claude/125-live-degradation-impl` · **Base:** `main @ 21e5b14`
**Contract:** `docs/projects/champions/decisions/2026-07-28-live-path-degradation-recording.md`
(including the §8.0 amendment, PR #146)
**Plan:** `docs/projects/champions/plans/2026-07-29-live-path-degradation-recording.md` (PR #145)

This report records what was executed and verified. It makes **no strength claim and no
production-readiness claim**. The slice records evidence; it changes no chosen action.

---

## 1. What was built

`client/live_degradation.py` (new) owns the `live-degradation-v1` schema, its four validators,
the recorder and the aggregation. `client/runner.py` gained call sites only. `cli.py` gained one
wrapper. `eval/config_env.py` gained one classification. `.gitignore` gained two entries.

Twelve tasks, executed test-first in plan order. Each task's tests were verified RED for the
stated reason before its implementation existed.

| # | Task | Content |
|---|---|---|
| 1 | 1 | schema constants, closed vocabularies |
| 2 | 2 (partial) | four validators, decision-grain mutations |
| 3 | 2 | stable rule identifiers, restored messages, full coverage |
| 4 | 3 | `SHOWDOWN_LIVE_DEGRADATION_DIR` classified, run dirs ignored |
| 5 | 4 | exclusive run directory, env override, writer preflight |
| 6 | 4 (fix) | two over-specifications withdrawn |
| 7 | 5 | gated decision rows, persisted `is_degraded` |
| 8 | 6, 7 | event attribution, battle aggregation |
| 9 | 8 | boundary flush, write-failure accounting, completion |
| 10 | 9, 10 | runner wiring, boundaries, preflight call sites |
| 11 | 11, 12 (local) | non-masking exit status, smoke shape, artifact invariant |
| 12 | 11 (fix) | AST guard narrowed to `ExceptHandler` |
| 13 | 12 | closeout, narrow battle-log ignore rule |
| 14 | 12 | final suite figure |

This branch contains **only** the #125 implementation. Five user-commissioned working-agreement
commits were made during the same session and initially shared this branch; they were split onto
`claude/working-agreement` before review, so that a contract change and a code change are reviewed
separately rather than as one enlarged surface. Nothing was lost in the split: the `showdown_bot`,
`.gitignore` and `docs/projects` trees are byte-identical to the pre-split state, and the three
contract files are byte-identical on the other branch.

---

## 2. The public smoke — Task 12 Step 5

Executed once, on explicit approval, against the public server. One battle, as approved.

| | |
|---|---|
| Server | `wss://sim3.psim.us/showdown/websocket` (default; `SHOWDOWN_SERVER` unset) |
| Credentials | generated throwaway name, `SHOWDOWN_PASSWORD` empty → guest assertion path |
| Sink | default path; `SHOWDOWN_LIVE_DEGRADATION_DIR` unset |
| Working directory | repository root |
| Run directory | `logs/live-degradation/20260729T013112Z-67129f` |
| Battle | `battle-gen9randomdoublesbattle-2656428978`, 14 decisions, ended `win` |
| Process status | `exit=0` |

No name collision occurred, so the plan's retry did not apply.

**The run directory existed before login.** The preflight therefore held §10.1's boundary in a
real run, not only under test.

### 2.1 Artifacts, verbatim

First `decisions.jsonl` row:

```json
{"schema_version": "live-degradation-v1", "run_id": "20260729T013112Z-67129f", "room_id": "battle-gen9randomdoublesbattle-2656428978", "decision_seq": 0, "rqid": 3, "book_absent": true, "team_preview": false, "state_build_failed": false, "selection_stage": null, "fallback_reason": null, "agent_crash_type": null, "derivation_applicable": false, "is_degraded": null, "outcome": "not_applicable"}
```

`battles.jsonl`:

```json
{"schema_version": "live-degradation-v1", "run_id": "20260729T013112Z-67129f", "room_id": "battle-gen9randomdoublesbattle-2656428978", "decisions_total": 14, "decisions_not_applicable": 14, "degraded_decisions": 0, "state_build_failures": 0, "agent_crashes": 0, "fallback_decisions": 0, "own_invalid_choices": 0, "server_errors": 0, "end_reason": "win", "write_errors": 0}
```

`completion.json`:

```json
{
  "schema_version": "live-degradation-v1",
  "run_id": "20260729T013112Z-67129f",
  "battles_finished": 1,
  "unterminated_rooms": [],
  "write_errors_total": 0,
  "schema_errors_total": 0,
  "recorder_errors_total": 0,
  "preflight_ok": true
}
```

`events.jsonl` is **absent**. That is the no-events shape of the artifact invariant, and with all
three counters at zero the absence means zero rows, not loss (§8.0).

### 2.2 What was checked on the real artifacts

Every row was passed through the production validators, not merely eyeballed:

- 14 decision rows, 1 battle row and the completion object all validate.
- `validate_completion_row(..., expected_run_id=...)` passes.
- **Artifact invariant:** every JSONL line present carries one and the same `run_id`, and it
  equals the run-directory name.
- Verdict combination: `exit=0` **and** a present, parsing, validating, three-zero
  `completion.json` — §8.0's only combination that establishes a successful run.

**The §5 consequence for smoke is confirmed on real data.** All 14 decisions:
`book_absent = true`, `derivation_applicable = false`, `is_degraded = null`,
`outcome = "not_applicable"`, `state_build_failed = false`, and `decision_seq` runs 0…13 with no
gaps. A naive `state is None` rule would have reported this run as **100 % degraded**. It is not
degraded at all; the state path was never entered, because `gen9randomdoublesbattle` has no
spread book.

### 2.3 Credential handling

The generated name was searched for in all three artifacts: **0 occurrences**. No substitution
was required, and the name is deliberately not reproduced in this report. The console capture
that contains it is retained outside the repository.

`SHOWDOWN_PASSWORD` was empty, so `fetch_assertion` took the guest path
(`client/auth.py:106-110`). No password, assertion or cookie appears anywhere in this report.

### 2.4 Artifact retention

The run directory is evidence and is **not committed** — it is covered by the `.gitignore` entry
from Task 3, and the repository-hygiene rule keeps raw logs out of commits. Only the excerpts
above enter git. A copy of the directory and the console output is retained outside the working
tree so the excerpts remain traceable if the tree is cleaned.

---

## 3. A pre-existing hygiene defect the smoke exposed

The plan's Task 12 Step 7 gate says no `logs/` entry may appear in `git status`, and adds: *"if
one does, the Task 3 gitignore entry is wrong."* After the smoke, `?? logs/` appeared. **The
plan's diagnosis was wrong.** Measured:

| Path | Ignored |
|---|---|
| `logs/live-degradation/…/decisions.jsonl` | yes |
| `logs/live-degradation/…/battles.jsonl` | yes |
| `logs/live-degradation/…/completion.json` | yes |
| `logs/battle-gen9randomdoublesbattle-…_20260729_033119.log` | **no** |

The Task 3 entry works exactly as intended. The untracked entry comes from `_log_battle_line`
(`runner.py:133-136`) writing raw per-battle protocol logs to `LOG_DIR = Path("logs")`
(`runner.py:29`) — **pre-existing code this slice neither introduced nor touched.** It had simply
never been observed, because no live command had previously been run from the repository root.

Resolved narrowly, on instruction, by one `.gitignore` line:

```
# Raw per-battle protocol logs written by client/runner.py when live commands run from repo root.
logs/battle-*.log
```

Deliberately **not** `logs/` wholesale: the narrow glob changes no bot behaviour, destroys no
evidence, keeps `logs/live-degradation/` ignored by its own separate rule, and leaves the battle
log on disk. Verified with `git check-ignore -v` on both paths.

---

## 4. Closeout gates

| Gate | Result |
|---|---|
| `git diff --check` | clean |
| Full offline suite | see §5 |
| `git status --porcelain` | only the seven known local artifacts |
| Working tree | no uncommitted slice changes |

The seven local artifacts — `.claude/`, the evaluation research note, two 2026-07-16 reports,
`showdown_bot/uv.lock`, the Studio phase-3 plan and `tools/_pkmn_differential_audit/` — are
unchanged and untracked throughout.

---

## 5. Suite

Baseline at `main @ 21e5b14`: `3860 passed, 2 skipped, 1 xfailed`.

The suite was run in full three times during this slice: once before the public smoke, once after
it, and once more after the working-agreement commits were split off this branch, which rewrote
every commit here. Only the last one describes the branch as it now stands; it is §6.

---

## 6. Final verification

**Tested head: `98b09860`.** That is the head of `claude/125-live-degradation-impl` after the
branch split, with every task, the smoke, the closeout and the narrow ignore rule in place.

```
python -m pytest showdown_bot -q
4056 passed, 2 skipped, 1 xfailed in 763.18s (0:12:43)
```

Against the `main @ 21e5b14` baseline of `3860 passed, 2 skipped, 1 xfailed` this is **+196** —
exactly the 164 module tests and 32 runner tests this slice adds, with no regression among the
pre-existing 3860.

**One commit follows the tested head: this one, and it changes only this report.** The suite was
therefore not run on the final commit of the branch, and this report does not claim it was. Nothing
that could affect a test result lies between `98b09860` and the tip: no source file, no test, no
`.gitignore` line, no configuration — only prose in `docs/projects/champions/reports/`.

| Gate | Result on `98b09860` |
|---|---|
| `python -m pytest showdown_bot -q` | 4056 passed, 2 skipped, 1 xfailed |
| `git diff --check` | clean |
| `git status --porcelain` | the seven known local artifacts only |
| Public smoke | one battle, `exit=0`, artifacts validated |

No commit hashes appear anywhere else in this report. The split invalidated a full set of them
once already, and this file's own contract forbids duplicating volatile identifiers. Section 1's
table is ordinal for that reason; read the branch history for the mapping.

What was verified locally versus reported elsewhere: everything in this report was run and read
here. Nothing in it rests on CI. That distinction matters in this repository — no workflow runs
the full offline suite; `.github/workflows/pytest.yml` runs a named slice smoke plus a
two-platform provenance matrix, and the Studio lanes cover Studio only.

---

## 7. Carry-forward note: a coupling a later reader must know

`client/live_degradation.py`'s decision validator encodes invariants read off
`battle/decision.py`'s **control flow**, not off a specification:

- `LIVE_STAGES` and `STAGES_REQUIRING_A_REASON`;
- the two-route rule for `deterministic_default_pair` — reason-less is reachable only on the
  state-is-None path, which with the gate true requires `state_build_failed`;
- "the stage may be absent only when a crash was recorded".

If a route in `choose_with_fallback` changes, those rules break loudly — by design;
`test_the_stage_vocabulary_of_choose_with_fallback_is_fully_classifiable` exists for exactly
that. The consequence: **`battle/decision.py` and `live_degradation.py` must be read together.**

## 8. Non-claims

No strength claim. No production-readiness claim. No latency claim — §10.2's boundary flush is
synchronous with no bound, and this slice does not measure it. No chosen action changed; a test
asserts the sent string is byte-identical with and without a recorder installed.
`_abort_on_degradation` remains narrower than what is recorded, which is the decision record's
explicit non-goal (C4), not a gap to close later by accident.

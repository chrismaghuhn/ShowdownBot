# T4c Provenance Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind result rows to their room logs (normalized sha), let `eval-report` re-derive
outcomes from logs fail-closed, and record an informational environment block in run manifests.

**Architecture:** Three seams, no schema breaks: (1) row write site in
`client/gauntlet.py` (already parses room logs, T3f) adds one field; (2) `eval/report.py`
gains an optional room_raw input + `LogIntegrityError`; (3) `eval/run_manifest.py` gains an
`environment` section outside `config_hash`. Spec:
`docs/projects/evaluation/specs/2026-07-11-t4c-provenance-hardening-design.md`.

**Tech stack:** existing repo only (pytest, committed fixtures `data/eval/t4/rerun/`).
**Hard constraint:** NO battles/servers; run only touched test files per task; full suite once
at closeout (1 strict-xfail in test_baseline.py is the known state).

---

### Task 1: `normalized_room_log_sha256` in result rows (Sonnet)

**Files:** Modify `showdown_bot/src/showdown_bot/client/gauntlet.py` (the result-record
assembly around line ~630-690 where `parse_battle_result` runs on `room_frames`); test in the
existing result-row test file (find via `grep -l end_reason showdown_bot/tests`).

- [ ] Locate the T4-identity normalize call (grep `normalize_battle_log` across
  `showdown_bot/src` + `tools/`) and mirror its exact `name_subs` convention.
- [ ] Failing test: assembled result record for fixture frames contains
  `normalized_room_log_sha256` == hashlib.sha256 over `normalize_battle_log(frames,
  name_subs=<same convention>)` output bytes (encode exactly as the identity check does).
- [ ] Implement: compute in-process at the write site (frames already in hand); on any
  exception during sha computation → field `None` + debug log (never fail the battle record).
- [ ] Legacy-tolerance test: rows WITHOUT the field load fine through the result-row loader
  used by report/eval (find it; assert no KeyError).
- [ ] Run touched test files. Commit `feat(t4c): bind result rows to normalized room-log sha`.

### Task 2: report re-parse + `LogIntegrityError` (Sonnet)

**Files:** Modify `showdown_bot/src/showdown_bot/eval/report.py` (+ its CLI entry in
`cli.py` eval-report), test `showdown_bot/tests/test_report*.py` (follow existing structure).

- [ ] `LogIntegrityError(Exception)` with a message listing every offending row
  (battle_id/seed_index + which field mismatched, expected vs actual).
- [ ] Optional `room_raw_dir` param threaded from a new `--room-raw` CLI flag. Absent → code
  path untouched (golden-report byte-identity tests must stay green untouched).
- [ ] Present → for EVERY row: resolve log via `room_raw_path` basename in the dir (missing →
  LogIntegrityError); `parse_battle_result` → compare winner/turns/end_reason/end_hp_diff;
  recompute normalized sha → compare when row sha non-null.
- [ ] Tests on committed fixtures `data/eval/t4/rerun/` (copy to tmp, point report at run1 +
  its room_raw subset): clean pass; a tampered turns value → LogIntegrityError naming the row.
- [ ] Run touched test files. Commit `feat(t4c): eval-report re-derives outcomes from room
  logs (fail-closed)`.

### Task 3: winner-flip pin inversion (Sonnet)

**Files:** the T5 pin test file containing `winner_flip_is_undetectable` (grep it).

- [ ] Keep the no-logs pin as-is (documenting the limitation without logs).
- [ ] New test: t4/rerun fixture copy, flip one row's `winner`, run report WITH room_raw →
  LogIntegrityError identifying exactly that row.
- [ ] Run the file. Commit `test(t4c): winner flip IS detected when room logs are present`.

### Task 4: environment block in run manifest (Sonnet)

**Files:** Modify `showdown_bot/src/showdown_bot/eval/run_manifest.py`, report provenance
rendering in `eval/report.py`; tests `test_run_manifest.py` + report goldens.

- [ ] `collect_environment()` → dict: `python` (sys.version split), `node` (`node --version`
  via subprocess, None on failure), `platform` (platform.platform()), `deps` {pydantic,
  websockets, lightgbm→None if not importable} via importlib.metadata.version.
- [ ] Manifest gains `environment` key. **Pin test: `config_hash` is UNCHANGED by the
  environment block** (hash inputs must not include it — verify against the existing
  config_hash construction and assert equality with/without).
- [ ] Report provenance section renders it informationally. Golden reports: if the golden
  fixtures' manifests lack the block, rendering must tolerate absence (legacy) — goldens stay
  byte-identical. New-manifest rendering covered by a unit test, not by regenerating goldens.
- [ ] Run touched files. Commit `feat(t4c): informational environment block in run manifests`.

### Task 5: closeout

- [ ] Full suite once (`python -m pytest showdown_bot -q`): expect all green + 1 xfailed
  (test_baseline strict-xfail — known).
- [ ] Short report `reports/2026-07-11-t4c-provenance-hardening.md`: what binds, what
  re-derives, the inverted pin, environment block, limitations (legacy rows null; Channel-B
  out of scope). Commit `docs(t4c): closeout report`.
- [ ] `git diff main --stat` scope summary → controller → merge decision.

## Self-review (writing-plans)

- Spec coverage: R1→Task 1, R2→Task 2, R3→Task 3, R4→Task 4. ✓
- No battles anywhere; all fixture-based. ✓
- Golden-report byte-identity preserved on both new code paths (flag absent; legacy manifest
  tolerance). ✓
- Placeholders: file/line anchors resolved by each implementer via the greps given (exact
  line numbers intentionally not pinned — main moved since recon). ✓

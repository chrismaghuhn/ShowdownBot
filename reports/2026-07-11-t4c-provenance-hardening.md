# T4c — Provenance Hardening Closeout (2026-07-11)

Mini-slice binding result rows to their room logs, fail-closed re-derivation in `eval-report`,
and an informational environment block in run manifests. Spec:
`docs/superpowers/specs/2026-07-11-t4c-provenance-hardening-design.md`. Branch
`feat/slice-t4c-provenance-hardening`, `git HEAD` `0004dd9`. All-fixture, no battles run for
this slice (hard constraint).

## What T4c binds

Every result row now carries `normalized_room_log_sha256` (`client/gauntlet.py`, computed
in-process at write time from the frames already in hand): sha256 hex over
`room_dump.normalize_battle_log(frames, name_subs=GAUNTLET_NAME_SUBS)` — the same
normalization recipe the T4 identity checks use (`eval/room_dump.normalized_room_log_sha256`
is the single shared implementation both call sites delegate to). Any exception during sha
computation yields `None` + a debug log, never a failed battle record. Legacy rows (pre-T4c)
simply lack the field; every loader tolerates its absence.

## What the report re-derives (fail-closed)

`eval-report` gains an optional `--room-raw <dir>` flag (`RunBundle.load(...,
room_raw_dir=...)`). Absent: behavior is byte-identical to before (golden reports untouched).
Present: for **every** row — resolve its log under the dir by `room_raw_path` basename
(missing file → hard error), re-parse via `eval/battle_parse.parse_battle_result` and compare
winner/turns/end_reason/end_hp_diff against the row, and recompute the normalized sha to
compare against `normalized_room_log_sha256` (skipped only when the row's sha is null —
legacy rows — but the parse cross-check still runs). Any mismatch raises `LogIntegrityError`
listing every offending row (battle_id/seed_index + field + expected vs actual) in one pass —
fail-closed, no partial verdict on corrupted evidence.

## The inverted winner-flip pin

- `test_eval_report.py::test_winner_flip_is_undetectable_documents_deviation` — unchanged;
  still pins the no-logs limitation (a winner flip alone touches no field any no-logs
  cross-check covers, so the bundle loads clean and reports SAFETY-PASS).
- `test_eval_report.py::test_winner_flip_is_detected_with_room_raw_logs` — new twin, identical
  tamper on a copy of the committed `data/eval/t4/rerun/` fixtures, but with `room_raw_dir`
  supplied. Now raises `LogIntegrityError` naming the exact row (`seed_index`, `battle_id`,
  `winner mismatch`, `row='villain'` vs `recomputed='hero'`). The no-logs gap is now scoped
  precisely to the absence of `--room-raw`, not to log-based detection being impossible.

## Environment block

`eval/run_manifest.collect_environment()` adds an informational `environment` dict to run
manifests: `python` (`sys.version`), `node` (`node --version` via subprocess, `None` on
failure), `platform` (`platform.platform()`), and `deps` (pydantic/websockets/lightgbm
versions via `importlib.metadata`, `None` if not importable). It is deliberately **not** an
input to `config_hash` — pinned by a dedicated test asserting `config_hash` is byte-identical
with and without the block, so environment drift can never fork config lineage. The report's
provenance section renders it when present and tolerates its absence on legacy manifests
(goldens stay byte-identical).

## Commits (this slice, `main..HEAD`)

```
0004dd9 feat(t4c): informational environment block in run manifests
905a457 test(t4c): winner flip IS detected when room logs are present
9563422 feat(t4c): eval-report re-derives outcomes from room logs (fail-closed)
c8ab012 feat(t4c): bind result rows to normalized room-log sha
ce01c78 docs(t4c): provenance hardening spec + plan
```

## Limitations

- **Legacy rows** (written before T4c) have `normalized_room_log_sha256 = None`; the sha
  cross-check is skipped for them but the winner/turns/end_reason/end_hp_diff parse
  cross-check still runs against `--room-raw`, so partial integrity checking remains available.
- **Channel-B** (explicit per-battle seed protocol channel) stays out of scope — carried over
  from the design doc, not addressed here.
- **Room-log evidence must be present** for any integrity checking to happen at all: absence of
  `--room-raw` means no check runs (byte-identical to pre-T4c behavior), by design — the flag
  is explicit, there is no auto-magic discovery of a room-raw directory.

## Verification

`cd showdown_bot && python -m pytest -q` → **982 passed, 1 xfailed** (the known
`test_baseline.py` strict-xfail). No other change.

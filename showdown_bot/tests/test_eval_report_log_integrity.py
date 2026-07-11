"""T4c Task 2: eval-report re-derives outcomes from room logs (fail-closed).

Spec: docs/superpowers/specs/2026-07-11-t4c-provenance-hardening-design.md R2. Plan:
docs/superpowers/plans/2026-07-11-t4c-provenance-hardening.md Task 2.

``RunBundle.load(..., room_raw_dir=...)`` is the seam under test: when given, EVERY row is
re-derived from its room log (winner/turns/end_reason/end_hp_diff via
``eval.battle_parse.parse_battle_result``, plus the normalized sha when the row carries one)
and any mismatch — or a missing log file — raises ``LogIntegrityError`` naming every offending
row. Absent (the default in every other report test), this is byte-identical to before T4c;
that is covered by test_eval_report_golden.py / test_eval_report.py, which are left untouched.

Fixtures: the committed ``data/eval/t4/rerun/t4rerun-run1.jsonl`` + its
``room_raw/run1/*.log.gz`` subset (51 rows, all legacy — no ``normalized_room_log_sha256``
field — so the real-fixture tests below exercise the parse cross-check path only). The sha
match/mismatch path is exercised on a small synthetic single-row copy augmented with a real
row's recomputed sha (there is no committed fixture with the sha field yet, since it postdates
these rows -- T4c R1).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from showdown_bot.eval.report import LogIntegrityError, ReportInputError, RunBundle
from showdown_bot.eval.room_dump import normalized_room_log_sha256, read_room_log_frames

_REPO_ROOT = Path(__file__).resolve().parents[2]          # <repo>/
_SB = Path(__file__).resolve().parents[1]                  # <repo>/showdown_bot/
_RERUN = _REPO_ROOT / "data" / "eval" / "t4" / "rerun"
_RESULTS = _RERUN / "t4rerun-run1.jsonl"
_SEEDLOG = _RERUN / "t4rerun-run1-seedlog.jsonl"
_MANIFEST = _RERUN / "t4rerun-run1.jsonl.manifest.json"
_SCHEDULE = _REPO_ROOT / "config" / "eval" / "schedules" / "t4_smoke_v001.yaml"
_PANEL = _REPO_ROOT / "config" / "eval" / "panels" / "panel_v001.yaml"
_ROOM_RAW_RUN1 = _RERUN / "room_raw" / "run1"


def _copy_bundle(tmp_path, *, with_room_raw=True):
    """Copy the fixture (results + sidecar + seedlog [+ room_raw/run1]) into tmp_path."""
    results = tmp_path / "run1.jsonl"
    manifest = tmp_path / "run1.jsonl.manifest.json"   # resolves via <results>.manifest.json
    seedlog = tmp_path / "run1-seedlog.jsonl"
    shutil.copy(_RESULTS, results)
    shutil.copy(_MANIFEST, manifest)
    shutil.copy(_SEEDLOG, seedlog)
    room_raw = tmp_path / "room_raw"
    if with_room_raw:
        shutil.copytree(_ROOM_RAW_RUN1, room_raw)
    return results, seedlog, room_raw


def _basename(room_raw_path: str) -> str:
    return room_raw_path.replace("\\", "/").rsplit("/", 1)[-1]


def _actual_log_file(directory: Path, room_raw_path: str) -> Path:
    """The committed fixtures are gzip-compressed (``<basename>.gz``); resolve to whichever of
    ``<basename>`` / ``<basename>.gz`` actually exists under ``directory`` (mirrors
    ``report._resolve_room_log_path``, kept independent here so the test doesn't trivially
    pass by construction)."""
    base = _basename(room_raw_path)
    for candidate in (directory / base, directory / (base + ".gz")):
        if candidate.exists():
            return candidate
    raise AssertionError(f"no log file for {room_raw_path!r} under {directory}")


# --- 1. clean pass on the real committed fixture (parse cross-check path; legacy rows have
#        no sha field, so the sha compare is skipped -- the parse cross-check still runs). ----

def test_log_integrity_clean_pass_on_real_fixture():
    b = RunBundle.load(
        str(_RESULTS), str(_SEEDLOG), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB),
        room_raw_dir=str(_ROOM_RAW_RUN1),
    )
    assert len(b.rows) == 51


def test_log_integrity_absent_flag_is_unaffected_by_room_raw_existing():
    # Sanity: the flag genuinely gates the behavior -- loading the SAME fixture with
    # room_raw_dir=None (the default, exercised everywhere else) still works, unchanged.
    b = RunBundle.load(
        str(_RESULTS), str(_SEEDLOG), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB),
    )
    assert len(b.rows) == 51


# --- 2. missing log file -> LogIntegrityError naming the row --------------------------------

def test_log_integrity_missing_log_file_raises(tmp_path):
    results, seedlog, room_raw = _copy_bundle(tmp_path)
    rows = [json.loads(line) for line in _RESULTS.read_text(encoding="utf-8").splitlines()]
    victim = rows[0]
    victim_file = _actual_log_file(room_raw, victim["room_raw_path"])
    victim_file.unlink()

    with pytest.raises(LogIntegrityError) as excinfo:
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    msg = str(excinfo.value)
    assert f"seed_index={victim['seed_index']}" in msg
    assert victim["battle_id"] in msg
    assert "not found" in msg


# --- 3. tampered turns value -> LogIntegrityError naming the row ----------------------------

def test_log_integrity_tampered_turns_raises(tmp_path):
    results, seedlog, room_raw = _copy_bundle(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    real_turns = row["turns"]
    row["turns"] = real_turns + 137   # a wrong-but-plausible turn count
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(LogIntegrityError) as excinfo:
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    msg = str(excinfo.value)
    assert f"seed_index={row['seed_index']}" in msg
    assert row["battle_id"] in msg
    assert "turns mismatch" in msg
    assert f"row={row['turns']!r}" in msg
    assert f"recomputed={real_turns!r}" in msg


def test_log_integrity_tampered_winner_raises(tmp_path):
    """R3 preview (the actual pin-inversion test lives in the T5 winner-flip pin file per
    Task 3): a flipped winner IS caught once room logs are available, unlike the no-logs path
    documented in test_eval_report.py::test_winner_flip_is_undetectable_documents_deviation."""
    results, seedlog, room_raw = _copy_bundle(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    assert row["winner"] == "hero"
    row["winner"] = "villain"
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(LogIntegrityError) as excinfo:
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    msg = str(excinfo.value)
    assert f"seed_index={row['seed_index']}" in msg
    assert "winner mismatch" in msg
    assert "row='villain'" in msg
    assert "recomputed='hero'" in msg


# --- 4. every offending row is listed, not just the first -----------------------------------

def test_log_integrity_lists_every_offending_row(tmp_path):
    results, seedlog, room_raw = _copy_bundle(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row0, row1 = json.loads(lines[0]), json.loads(lines[1])
    row0["turns"] += 1
    row1["turns"] += 1
    lines[0] = json.dumps(row0, sort_keys=True, separators=(",", ":"))
    lines[1] = json.dumps(row1, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(LogIntegrityError) as excinfo:
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    msg = str(excinfo.value)
    assert f"seed_index={row0['seed_index']}" in msg
    assert f"seed_index={row1['seed_index']}" in msg
    assert msg.startswith("2 row(s) failed")


# --- 5. normalized_room_log_sha256: match passes, mismatch raises ---------------------------
#
# The committed fixture rows are all legacy (no sha field), so these tests build a small
# synthetic single-row results.jsonl from a REAL fixture row (unmodified battle_id/seed/turns/
# etc. -- only the nullable sha field is added), so RunBundle.load's existing tamper audit
# (battle_id/seed recomputation) still passes untouched. `rows_match_schedule` etc. are safety
# GATES computed later by run_safety_gates, not load-time checks, so a 1-row results file loads
# fine here.

def _single_row_bundle(tmp_path, *, sha_override=None):
    rows = [json.loads(line) for line in _RESULTS.read_text(encoding="utf-8").splitlines()]
    row = dict(rows[0])
    log_path = _actual_log_file(_ROOM_RAW_RUN1, row["room_raw_path"])
    real_sha = normalized_room_log_sha256(read_room_log_frames(log_path))
    row["normalized_room_log_sha256"] = sha_override if sha_override is not None else real_sha

    results = tmp_path / "run1.jsonl"
    manifest = tmp_path / "run1.jsonl.manifest.json"
    seedlog = tmp_path / "run1-seedlog.jsonl"
    results.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    shutil.copy(_MANIFEST, manifest)
    shutil.copy(_SEEDLOG, seedlog)
    room_raw = tmp_path / "room_raw"
    shutil.copytree(_ROOM_RAW_RUN1, room_raw)
    return results, seedlog, room_raw, row, real_sha


def test_log_integrity_correct_sha_passes(tmp_path):
    results, seedlog, room_raw, row, real_sha = _single_row_bundle(tmp_path)
    b = RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    assert len(b.rows) == 1
    assert b.rows[0]["normalized_room_log_sha256"] == real_sha


def test_log_integrity_wrong_sha_raises(tmp_path):
    rows = [json.loads(line) for line in _RESULTS.read_text(encoding="utf-8").splitlines()]
    log_path = _actual_log_file(_ROOM_RAW_RUN1, rows[0]["room_raw_path"])
    real_sha = normalized_room_log_sha256(read_room_log_frames(log_path))
    wrong_sha = ("0" if real_sha[0] != "0" else "1") + real_sha[1:]

    results, seedlog, room_raw, row, _ = _single_row_bundle(tmp_path, sha_override=wrong_sha)
    with pytest.raises(LogIntegrityError) as excinfo:
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    msg = str(excinfo.value)
    assert f"seed_index={row['seed_index']}" in msg
    assert "normalized_room_log_sha256 mismatch" in msg


# --- 6. gzip vs plain .log resolution (the committed fixtures are gzipped; the row's
#        room_raw_path basename has no .gz suffix -- resolution must try both). -------------

def test_log_integrity_resolves_gz_and_plain_log(tmp_path):
    results, seedlog, room_raw = _copy_bundle(tmp_path)
    rows = [json.loads(line) for line in _RESULTS.read_text(encoding="utf-8").splitlines()]
    base = _basename(rows[0]["room_raw_path"])
    gz_path = room_raw / (base + ".gz")
    assert gz_path.exists()   # committed fixtures ship gzipped
    plain_path = room_raw / base
    # Decompress to a plain .log so the OTHER resolution branch is exercised too.
    frames = read_room_log_frames(gz_path)
    plain_path.write_text("\n".join(frames), encoding="utf-8")
    gz_path.unlink()

    b = RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    assert len(b.rows) == 51


# --- 7. missing sidecar manifest still raises ReportInputError (not swallowed by the new
#        LogIntegrityError path -- both can apply, but load-time input errors are checked
#        first / independently). --------------------------------------------------------------

def test_log_integrity_still_requires_manifest(tmp_path):
    results, seedlog, room_raw = _copy_bundle(tmp_path)
    (tmp_path / "run1.jsonl.manifest.json").unlink()
    with pytest.raises(ReportInputError):
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))

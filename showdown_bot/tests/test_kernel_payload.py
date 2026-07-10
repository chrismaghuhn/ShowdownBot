"""2b-2.5a Task 2: tests for the LOCALLY-TESTABLE parts of tools/kaggle/kernel_payload.py.

HARD CONSTRAINT (2026-07-10): no local battle runs / Showdown servers. The operational
run-functions (bootstrap_node's install branch, setup_showdown, run_schedule_seeded,
copy_outputs) start subprocesses (node/git/the gauntlet CLI) and are exercised only on Kaggle
(Task 3) -- not unit-tested here, mirroring test_kaggle_driver.py's split for the network
functions.

What IS tested here:
- ``_parse_node_major`` (pure version-string parsing).
- ``validate_prefix_reproduction`` against the committed T4b prefix-reproduction fixture
  (``data/eval/t4/rerun/t4rerun-prefix.jsonl`` + `.../room_raw/prefix/*.log.gz``) -- every case
  builds a synthetic ``out_dir`` by COPYING that same committed fixture (a "fresh" run that
  happens to be byte-identical to the reference), then perturbs it to prove each failure path
  is actually detected. No battle is ever run.
- ``print_verdict``'s exact wire format (matches ``kaggle_driver.parse_verdict``).

tools/ is not an installed package, so the module under test is loaded directly from its file
path via importlib, same pattern as test_kaggle_driver.py.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "kernel_payload.py"

_spec = importlib.util.spec_from_file_location("kernel_payload", _MODULE_PATH)
kernel_payload = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kernel_payload)

_PREFIX_REFERENCE_JSONL = _REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "t4rerun-prefix.jsonl"
_PREFIX_REFERENCE_ROOM_RAW_DIR = _REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "room_raw" / "prefix"


def _build_matching_out_dir(tmp_path) -> Path:
    """A synthetic out_dir that reproduces the committed prefix fixture byte-for-byte, built by
    COPYING the committed artifacts themselves (results jsonl + gunzipped room logs). Reads
    committed files only -- runs no battle."""
    out_dir = tmp_path / "out"
    room_raw_dir = out_dir / "room_raw"
    room_raw_dir.mkdir(parents=True)

    shutil.copy(_PREFIX_REFERENCE_JSONL, out_dir / "results.jsonl")

    for gz_path in _PREFIX_REFERENCE_ROOM_RAW_DIR.glob("*.log.gz"):
        dest = room_raw_dir / gz_path.name[: -len(".gz")]
        with gzip.open(gz_path, "rt", encoding="utf-8") as src, \
                open(dest, "w", encoding="utf-8", newline="\n") as dst:
            dst.write(src.read())

    return out_dir


def _rows_of(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# _parse_node_major
# ---------------------------------------------------------------------------

def test_parse_node_major_v_prefixed():
    assert kernel_payload._parse_node_major("v20.1.0") == 20


def test_parse_node_major_no_v_prefix():
    assert kernel_payload._parse_node_major("18.19.1") == 18


def test_parse_node_major_double_digit():
    assert kernel_payload._parse_node_major("v22.3.0") == 22


def test_parse_node_major_unparseable_raises():
    with pytest.raises(ValueError):
        kernel_payload._parse_node_major("not a version string")


# ---------------------------------------------------------------------------
# validate_prefix_reproduction
# ---------------------------------------------------------------------------

def test_validate_prefix_reproduction_matching_copy_passes(tmp_path):
    out_dir = _build_matching_out_dir(tmp_path)

    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_ROOT), str(out_dir))

    assert ok is True
    assert "10/10" in detail


def test_validate_prefix_reproduction_winner_flip_fails(tmp_path):
    out_dir = _build_matching_out_dir(tmp_path)
    results_path = out_dir / "results.jsonl"
    rows = _rows_of(results_path)
    rows[0]["winner"] = "villain" if rows[0]["winner"] == "hero" else "hero"
    _write_rows(results_path, rows)

    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_ROOT), str(out_dir))

    assert ok is False
    assert "winner" in detail.lower()


def test_validate_prefix_reproduction_seed_mismatch_fails(tmp_path):
    out_dir = _build_matching_out_dir(tmp_path)
    results_path = out_dir / "results.jsonl"
    rows = _rows_of(results_path)
    rows[3]["seed"] = "sodium,deadbeefdeadbeefdeadbeefdeadbeef"
    _write_rows(results_path, rows)

    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_ROOT), str(out_dir))

    assert ok is False
    assert "seed" in detail.lower() or "mismatch" in detail.lower()


def test_validate_prefix_reproduction_log_truncation_fails(tmp_path):
    out_dir = _build_matching_out_dir(tmp_path)
    logs = sorted((out_dir / "room_raw").glob("*.log"))
    text = logs[0].read_text(encoding="utf-8")
    lines = text.split("\n")
    logs[0].write_text("\n".join(lines[:-1]), encoding="utf-8")  # drop the trailing |win| line

    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_ROOT), str(out_dir))

    assert ok is False
    assert "room log mismatch" in detail


def test_validate_prefix_reproduction_missing_results_file_fails_cleanly(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_ROOT), str(out_dir))

    assert ok is False
    assert detail  # some explanatory message, not a crash


def test_validate_prefix_reproduction_missing_room_logs_fails_cleanly(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    shutil.copy(_PREFIX_REFERENCE_JSONL, out_dir / "results.jsonl")
    (out_dir / "room_raw").mkdir()

    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_ROOT), str(out_dir))

    assert ok is False
    assert "count mismatch" in detail


# ---------------------------------------------------------------------------
# print_verdict
# ---------------------------------------------------------------------------

def test_print_verdict_pass_format(capsys):
    line = kernel_payload.print_verdict("KAGGLE-REPRO", True, "10/10 winner+seed match")

    assert line == "KAGGLE-REPRO: PASS (10/10 winner+seed match)"
    assert capsys.readouterr().out.strip() == line


def test_print_verdict_fail_format(capsys):
    line = kernel_payload.print_verdict("KAGGLE-REPRO", False, "winner mismatch at game 4")

    assert line == "KAGGLE-REPRO: FAIL (winner mismatch at game 4)"
    assert capsys.readouterr().out.strip() == line


def test_print_verdict_datagen_tag(capsys):
    line = kernel_payload.print_verdict("DATAGEN", True, "hero=fixed rows=1234 games=75")

    assert line == "DATAGEN: PASS (hero=fixed rows=1234 games=75)"


# ---------------------------------------------------------------------------
# Module hygiene: mirrors kaggle_driver's pattern of keeping heavy/absent-locally deps out
# of module-import scope where practical. kernel_payload legitimately imports showdown_bot.eval
# modules at top level (they're already an installed local dependency for every other test in
# this suite), so this just guards against accidentally importing anything Kaggle-only
# (e.g. a hard dependency on being inside /kaggle/working) at module scope.
# ---------------------------------------------------------------------------

def test_module_has_no_kaggle_path_at_import_time():
    assert not str(_MODULE_PATH.parent).startswith("/kaggle")
    # Importing the module (already done at collection time, above) must not have raised.
    assert hasattr(kernel_payload, "validate_prefix_reproduction")

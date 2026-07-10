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
import time
from pathlib import Path

import pytest

from showdown_bot.eval.datagen_2b25a import SEED_BASES
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.learning.schema import FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS, Row, to_jsonl_line

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "kernel_payload.py"

_spec = importlib.util.spec_from_file_location("kernel_payload", _MODULE_PATH)
kernel_payload = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kernel_payload)

_PREFIX_REFERENCE_JSONL = _REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "t4rerun-prefix.jsonl"
_PREFIX_REFERENCE_ROOM_RAW_DIR = _REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "room_raw" / "prefix"

# 2b-2.5a Task 5: committed hero used to exercise validate_datagen_output against a REAL
# schedule (config/eval/schedules/datagen_2b25a_hero_fixed.yaml, 75 rows) + its seed base --
# no battle is ever run, only the committed YAML is read and a synthetic seed log/dataset/
# client-log/results companion is built to match it (same technique as
# _build_matching_out_dir above for validate_prefix_reproduction).
_DATAGEN_HERO = "fixed"


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


def _datagen_schedule():
    return load_schedule(str(_REPO_ROOT / "config" / "eval" / "schedules" /
                              f"datagen_2b25a_hero_{_DATAGEN_HERO}.yaml"))


def _write_seed_log(path: Path, base: str, n: int) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for i in range(n):
            fh.write(json.dumps(
                {"battle_index": i, "seed": derive_battle_seed(base, i), "seed_base": base}) + "\n")


def _valid_dataset_row_line(*, game_id="g0", decision_id="d0", candidate_index=0) -> str:
    """One schema-valid dataset.jsonl line (learning/schema.py's frozen contract) -- same
    minimal-row pattern as test_ml_schema.py's `_row()` helper."""
    features = {c: 0 for c in FEATURE_COLUMNS}
    metadata = {k: "x" for k in METADATA_KEYS}
    metadata.update({"game_id": game_id, "decision_id": decision_id, "candidate_index": candidate_index})
    label = {k: 0 for k in LABEL_KEYS}
    return to_jsonl_line(Row(features=features, metadata=metadata, label=label))


def _build_datagen_out_dir(tmp_path, *, n_results=None) -> Path:
    """A synthetic out_dir that PASSES validate_datagen_output for hero='fixed': a seed log
    matching the committed 75-row schedule + SEED_BASES['fixed'], one valid dataset row PER
    scheduled game (distinct game_ids g0..g74 -- the full-game-coverage check added after the
    Task-6 attempt-1 overwrite finding requires exactly one distinct game_id per schedule
    row), a clean client.log, and one results.jsonl row per schedule row. Reads the committed
    schedule YAML only -- runs no battle."""
    schedule = _datagen_schedule()
    n = len(schedule.rows) if n_results is None else n_results

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _write_seed_log(out_dir / "seeds.jsonl", SEED_BASES[_DATAGEN_HERO], len(schedule.rows))
    dataset_lines = [
        _valid_dataset_row_line(game_id=f"g{i}", decision_id=f"d{i}")
        for i in range(len(schedule.rows))
    ]
    (out_dir / "dataset.jsonl").write_text("\n".join(dataset_lines) + "\n", encoding="utf-8")
    (out_dir / "client.log").write_text("battle started\nturn 1\nbattle ended\n", encoding="utf-8")
    with open(out_dir / "results.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for i in range(n):
            fh.write(json.dumps({"seed_index": i, "winner": "hero"}) + "\n")
    return out_dir


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
# validate_datagen_output (2b-2.5a Task 5)
# ---------------------------------------------------------------------------

def test_validate_datagen_output_matching_synthetic_out_dir_passes(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is True
    assert detail == "rows=75 games=75"


def test_validate_datagen_output_seed_log_wrong_base_fails(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)
    schedule = _datagen_schedule()
    _write_seed_log(out_dir / "seeds.jsonl", "wrong-base", len(schedule.rows))

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "seed-log alignment failed" in detail


def test_validate_datagen_output_missing_seed_log_fails_cleanly(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)
    (out_dir / "seeds.jsonl").unlink()

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "seed-log alignment failed" in detail


def test_validate_datagen_output_bad_dataset_row_fails(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)
    bad_row = json.loads(_valid_dataset_row_line())
    del bad_row["features"][FEATURE_COLUMNS[0]]
    (out_dir / "dataset.jsonl").write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "dataset validation failed" in detail


def test_validate_datagen_output_missing_dataset_fails_cleanly(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)
    (out_dir / "dataset.jsonl").unlink()

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "dataset validation failed" in detail


def test_validate_datagen_output_falling_back_warning_fails(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)
    (out_dir / "client.log").write_text(
        "turn 1\nheuristic timed out after 5s, falling back\nturn 2\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "warning line" in detail
    assert "falling back" in detail


def test_validate_datagen_output_frame_error_warning_fails(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)
    (out_dir / "client.log").write_text(
        "turn 1\n[p1] frame error (|move|): boom\nturn 2\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "warning line" in detail
    assert "frame error" in detail


def test_validate_datagen_output_missing_game_coverage_fails(tmp_path):
    """One scheduled game absent from the export (74 distinct game_ids, not 75) -> FAIL."""
    out_dir = _build_datagen_out_dir(tmp_path)
    schedule = _datagen_schedule()
    dataset_lines = [
        _valid_dataset_row_line(game_id=f"g{i}", decision_id=f"d{i}")
        for i in range(len(schedule.rows) - 1)  # drop the last game
    ]
    (out_dir / "dataset.jsonl").write_text("\n".join(dataset_lines) + "\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "game coverage" in detail
    assert "74" in detail and "75" in detail


def test_validate_datagen_output_single_game_overwrite_signature_fails(tmp_path):
    """The Task-6 trickroom attempt-1 corruption signature: many schema-valid rows that ALL
    share one game_id (a battle-scoped export runtime overwrote dataset.jsonl each battle,
    leaving only the last battle's rows). Schema validation passes; coverage must FAIL."""
    out_dir = _build_datagen_out_dir(tmp_path)
    dataset_lines = [
        _valid_dataset_row_line(game_id="g_last", decision_id=f"d{i}")
        for i in range(21)  # same row count as the real attempt-1 salvage
    ]
    (out_dir / "dataset.jsonl").write_text("\n".join(dataset_lines) + "\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "game coverage" in detail
    assert "1 distinct game_id" in detail


def test_validate_datagen_output_result_row_count_mismatch_fails(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path, n_results=74)

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "result row count mismatch" in detail
    assert "74" in detail and "75" in detail


def test_validate_datagen_output_unknown_hero_fails_cleanly(tmp_path):
    out_dir = _build_datagen_out_dir(tmp_path)

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), "not_a_hero")

    assert ok is False
    assert detail  # some explanatory message, not a crash


# ---------------------------------------------------------------------------
# copy_outputs -- dataset.jsonl gzip handling (2b-2.5a Task 5)
# ---------------------------------------------------------------------------

def test_copy_outputs_gzips_dataset_when_present(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "dataset.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
    working_dir = tmp_path / "working"

    written = kernel_payload.copy_outputs(str(out_dir), working_dir=str(working_dir))

    dest = working_dir / "dataset.jsonl.gz"
    assert str(dest) in written
    with gzip.open(dest, "rt", encoding="utf-8") as fh:
        assert fh.read() == '{"a": 1}\n'


def test_copy_outputs_no_dataset_file_writes_nothing_for_it(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    working_dir = tmp_path / "working"

    kernel_payload.copy_outputs(str(out_dir), working_dir=str(working_dir))

    assert not (working_dir / "dataset.jsonl.gz").exists()


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


# ---------------------------------------------------------------------------
# MEMTRACE (2b-2.5a, added 2026-07-10): memory telemetry sampler, added after datagen VMs
# OOM'd at deterministic battle counts (see kernel_payload.py's run_datagen docstring / module
# docstring for the incident). format_memtrace and collect_memtrace_sample are pure/injectable
# and fully unit-tested here; start_memtrace is exercised with injected fakes + a short
# interval (no real /proc/meminfo or ps dependency).
# ---------------------------------------------------------------------------

def test_format_memtrace_golden_line():
    line = kernel_payload.format_memtrace(
        12.7, 3, 4096, 16384,
        [("node", 1234, 512), ("python3", 5678, 256)],
    )

    assert line == "MEMTRACE t=12 done=3 availMB=4096/16384 top=[node:1234:512MB python3:5678:256MB]"


def test_collect_memtrace_sample_with_injected_fakes(tmp_path):
    meminfo_text = (
        "MemTotal:       16777216 kB\n"
        "MemFree:         1000000 kB\n"
        "MemAvailable:    4194304 kB\n"
        "Buffers:           50000 kB\n"
    )
    # 10 rows, already sorted desc by rss (kB); header row first, like real `ps` output.
    ps_lines = ["  PID   RSS COMMAND"]
    procs = [
        (1, 2000000, "node"),
        (2, 1500000, "python3"),
        (3, 900000, "node"),
        (4, 800000, "python3"),
        (5, 700000, "chrome"),
        (6, 600000, "node"),
        (7, 500000, "python3"),
        (8, 400000, "node"),
        (9, 300000, "python3"),
        (10, 200000, "node"),
    ]
    for pid, rss, comm in procs:
        ps_lines.append(f"{pid:5d} {rss:6d} {comm}")
    ps_text = "\n".join(ps_lines) + "\n"

    results_path = tmp_path / "results.jsonl"
    results_path.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n', encoding="utf-8")

    battles_done, avail_mb, total_mb, top = kernel_payload.collect_memtrace_sample(
        str(results_path),
        read_meminfo=lambda: meminfo_text,
        run_ps=lambda: ps_text,
    )

    assert battles_done == 3
    assert avail_mb == 4194304 // 1024
    assert total_mb == 16777216 // 1024
    assert len(top) == 8
    assert top[0] == ("node", 1, 2000000 // 1024)
    assert top[1] == ("python3", 2, 1500000 // 1024)
    assert top[-1] == ("node", 8, 400000 // 1024)


def test_collect_memtrace_sample_missing_results_file_done_zero(tmp_path):
    meminfo_text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\n"
    ps_text = "  PID   RSS COMMAND\n    1  1000 node\n"
    missing_path = tmp_path / "does_not_exist.jsonl"

    battles_done, avail_mb, total_mb, top = kernel_payload.collect_memtrace_sample(
        str(missing_path),
        read_meminfo=lambda: meminfo_text,
        run_ps=lambda: ps_text,
    )

    assert battles_done == 0


def test_start_memtrace_smoke(tmp_path, capsys):
    meminfo_text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\n"
    ps_text = "  PID   RSS COMMAND\n    1  1000 node\n"
    results_path = tmp_path / "results.jsonl"
    results_path.write_text("", encoding="utf-8")

    stop = kernel_payload.start_memtrace(
        str(results_path), interval_s=0.01,
        read_meminfo=lambda: meminfo_text, run_ps=lambda: ps_text,
    )
    time.sleep(0.05)  # let ~a few ticks happen
    stop()

    out_after_stop = capsys.readouterr().out
    assert out_after_stop.count("MEMTRACE") >= 1

    time.sleep(0.05)  # stop() must actually stop the thread -- no further output
    out_after_wait = capsys.readouterr().out
    assert "MEMTRACE" not in out_after_wait

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

from showdown_bot.eval import datagen_2b25a
from showdown_bot.eval.datagen_2b25a import SEED_BASES
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.learning.schema import FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS, Row, to_jsonl_line

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "kernel_payload.py"
_DATAGEN_KERNEL_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "datagen_kernel.py"

_spec = importlib.util.spec_from_file_location("kernel_payload", _MODULE_PATH)
kernel_payload = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kernel_payload)

# 2b-2.5a EXTRA_ENV passthrough (2026-07-11): datagen_kernel.py's own env-header helper
# (``_extra_env_from_header``) is pure (just dict shape validation, no clone/subprocess), so it
# is loaded + unit-tested directly here too, same importlib-from-path technique as
# kernel_payload above -- the kernel itself is never run.
_datagen_kernel_spec = importlib.util.spec_from_file_location(
    "datagen_kernel", _DATAGEN_KERNEL_MODULE_PATH)
datagen_kernel = importlib.util.module_from_spec(_datagen_kernel_spec)
_datagen_kernel_spec.loader.exec_module(datagen_kernel)

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
# run_schedule_seeded env assembly (2b-2.5a, 2026-07-11): SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S
# ---------------------------------------------------------------------------
#
# run_schedule_seeded itself starts real subprocesses (server + gauntlet CLI) and is NOT
# unit-tested elsewhere in this module (see the module docstring / this file's docstring) --
# HARD CONSTRAINT: no local battle runs or Showdown servers. This test stays inside that
# constraint by monkeypatching subprocess.Popen/subprocess.run and _wait_for_port to fakes
# that never spawn anything and only record the env dicts the function builds, mirroring how
# SHOWDOWN_EVAL_ROOM_DEALLOC was added to both server_env and client_env at 3b8f1fc.

class _FakeServerProc:
    def terminate(self):
        pass

    def wait(self, timeout=None):
        pass


def test_run_schedule_seeded_sets_gauntlet_battle_timeout_env(tmp_path, monkeypatch):
    captured = {}

    def fake_popen(cmd, cwd=None, env=None):
        captured["server_env"] = env
        return _FakeServerProc()

    def fake_run(cmd, cwd=None, env=None, stdout=None, stderr=None, timeout=None, check=None):
        captured["client_env"] = env

    monkeypatch.setattr(kernel_payload.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(kernel_payload.subprocess, "run", fake_run)
    monkeypatch.setattr(kernel_payload, "_wait_for_port", lambda *a, **k: None)

    out_dir = tmp_path / "out"
    kernel_payload.run_schedule_seeded(
        str(_REPO_ROOT), str(tmp_path / "showdown_dir_fake"),
        "config/eval/schedules/datagen_2b25a_hero_fixed.yaml", "seedbase-x", str(out_dir),
    )

    assert captured["server_env"]["SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S"] == "900"
    assert captured["client_env"]["SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S"] == "900"


# ---------------------------------------------------------------------------
# run_datagen extra_env passthrough (2b-2.5a, 2026-07-11): the controller needs to inject an
# extra SHOWDOWN_* env var (e.g. SHOWDOWN_FAST_BOARD_PROTECT_PENALTY) into a datagen run without
# disturbing default behavior. run_datagen itself is NOT otherwise unit-tested (starts real
# subprocesses via run_schedule_seeded) -- these tests monkeypatch run_schedule_seeded to a fake
# that only records its extra_env kwarg, staying inside the no-battles constraint. The fake
# creates out_dir but leaves it otherwise empty, so validate_datagen_output (called for real,
# unmonkeypatched) fails cleanly (missing seeds.jsonl etc., exactly like the "fails cleanly"
# tests above) -- that's fine, these tests only assert on the captured extra_env kwarg.
# ---------------------------------------------------------------------------

def _fake_run_schedule_seeded_capturing_extra_env(captured):
    def fake(repo_root, showdown_dir, schedule_relpath, seed_base, out_dir, *,
             dataset_export=None, extra_env=None, timeout_s=9000):
        captured["extra_env"] = extra_env
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return {"results": str(Path(out_dir) / "results.jsonl")}
    return fake


def test_run_datagen_extra_env_none_is_byte_identical_to_teacher_only(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_extra_env(captured),
    )

    kernel_payload.run_datagen(
        str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
    )

    assert captured["extra_env"] == {"SHOWDOWN_DATASET_TEACHER": "rollout"}


def test_run_datagen_extra_env_merges_caller_keys_over_teacher_default(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_extra_env(captured),
    )

    kernel_payload.run_datagen(
        str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
        extra_env={"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0"},
    )

    assert captured["extra_env"] == {
        "SHOWDOWN_DATASET_TEACHER": "rollout",
        "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0",
    }


def test_run_datagen_extra_env_caller_can_explicitly_override_teacher_key(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_extra_env(captured),
    )

    kernel_payload.run_datagen(
        str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
        extra_env={"SHOWDOWN_DATASET_TEACHER": "heuristic"},
    )

    assert captured["extra_env"] == {"SHOWDOWN_DATASET_TEACHER": "heuristic"}


# ---------------------------------------------------------------------------
# shard_rows (2b-2.5a schedule sharding, 2026-07-11): pure index-math split, extracted so it is
# unit-testable without touching run_datagen/subprocesses at all.
# ---------------------------------------------------------------------------

def test_shard_rows_75_over_3_splits_into_three_equal_25s():
    rows = list(range(75))

    assert kernel_payload.shard_rows(rows, 0, 3) == (0, 25, rows[0:25])
    assert kernel_payload.shard_rows(rows, 1, 3) == (25, 50, rows[25:50])
    assert kernel_payload.shard_rows(rows, 2, 3) == (50, 75, rows[50:75])


def test_shard_rows_75_over_4_covers_all_rows_no_gaps_or_overlaps():
    rows = list(range(75))

    starts_ends = [kernel_payload.shard_rows(rows, i, 4)[:2] for i in range(4)]
    sizes = [end - start for start, end in starts_ends]

    assert sizes == [19, 19, 19, 18]
    assert starts_ends[0][0] == 0
    for i in range(3):
        assert starts_ends[i][1] == starts_ends[i + 1][0]  # no gap, no overlap
    assert starts_ends[-1][1] == 75

    # every row appears in exactly one shard
    covered = []
    for i in range(4):
        _, _, sliced = kernel_payload.shard_rows(rows, i, 4)
        covered.extend(sliced)
    assert covered == rows


def test_shard_rows_shard_count_one_is_full_range():
    rows = list(range(75))

    start, end, sliced = kernel_payload.shard_rows(rows, 0, 1)

    assert (start, end, sliced) == (0, 75, rows)


def test_shard_rows_shard_index_out_of_range_raises():
    rows = list(range(75))

    with pytest.raises(ValueError):
        kernel_payload.shard_rows(rows, 3, 3)
    with pytest.raises(ValueError):
        kernel_payload.shard_rows(rows, -1, 3)


def test_shard_rows_shard_count_less_than_one_raises():
    with pytest.raises(ValueError):
        kernel_payload.shard_rows(list(range(75)), 0, 0)


def test_shard_rows_shard_count_larger_than_rows_raises_for_empty_shard():
    # 5 rows, 10 shards -> size=ceil(5/10)=1, shard_index=5 starts at row 5 >= total (5).
    with pytest.raises(ValueError):
        kernel_payload.shard_rows(list(range(5)), 5, 10)


# ---------------------------------------------------------------------------
# run_datagen shard passthrough (2b-2.5a schedule sharding, 2026-07-11): run_datagen itself is
# NOT otherwise unit-tested (starts real subprocesses via run_schedule_seeded) -- these tests
# monkeypatch BOTH run_schedule_seeded and validate_datagen_output to fakes that only record
# their arguments, staying inside the no-battles constraint (same technique as the extra_env
# tests above).
# ---------------------------------------------------------------------------

def _fake_run_schedule_seeded_capturing_shard(captured):
    def fake(repo_root, showdown_dir, schedule_relpath, seed_base, out_dir, *,
             dataset_export=None, extra_env=None, timeout_s=9000):
        captured["schedule_relpath"] = schedule_relpath
        captured["seed_base"] = seed_base
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return {"results": str(Path(out_dir) / "results.jsonl")}
    return fake


def _fake_validate_datagen_output_capturing(captured):
    def fake(repo_root, out_dir, hero_key, *, schedule=None, seed_base=None):
        captured["validate_schedule"] = schedule
        captured["validate_seed_base"] = seed_base
        return True, "rows=1 games=1"
    return fake


def test_run_datagen_shard_count_one_is_byte_identical_to_unsharded(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_shard(captured),
    )
    monkeypatch.setattr(
        kernel_payload, "validate_datagen_output",
        _fake_validate_datagen_output_capturing(captured),
    )

    kernel_payload.run_datagen(
        str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
    )  # default shard_index=0, shard_count=1

    assert captured["schedule_relpath"] == datagen_2b25a.schedule_relpath(_DATAGEN_HERO)
    assert captured["seed_base"] == SEED_BASES[_DATAGEN_HERO]
    assert captured["validate_schedule"] is None
    assert captured["validate_seed_base"] is None


def test_run_datagen_shard_path_uses_suffixed_seed_base_and_sliced_schedule(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_shard(captured),
    )
    monkeypatch.setattr(
        kernel_payload, "validate_datagen_output",
        _fake_validate_datagen_output_capturing(captured),
    )

    result = kernel_payload.run_datagen(
        str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
        shard_index=1, shard_count=3,
    )

    full_schedule = _datagen_schedule()  # 75 rows, hero='fixed'
    expected_seed_base = f"{SEED_BASES[_DATAGEN_HERO]}-s1"
    assert captured["seed_base"] == expected_seed_base

    # schedule_relpath must point at a REAL written YAML sized to this shard (rows 25:50 of 75).
    sliced = load_schedule(captured["schedule_relpath"])
    assert len(sliced.rows) == 25
    assert [r.seed_index for r in sliced.rows] == list(range(25))  # renumbered 0-contiguous
    assert sliced.rows[0].opp_team_path == full_schedule.rows[25].opp_team_path
    assert sliced.rows[0].opp_policy == full_schedule.rows[25].opp_policy
    assert sliced.rows[-1].opp_team_path == full_schedule.rows[49].opp_team_path

    # validate_datagen_output must be pointed at the SAME sliced schedule + suffixed seed_base,
    # not the full 75-row schedule / base seed_base.
    assert captured["validate_seed_base"] == expected_seed_base
    assert len(captured["validate_schedule"].rows) == 25

    assert "shard=1/3" in result["verdict"]
    assert "rows=25" in result["verdict"]


def test_run_datagen_last_shard_gets_the_remainder(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_shard(captured),
    )
    monkeypatch.setattr(
        kernel_payload, "validate_datagen_output",
        _fake_validate_datagen_output_capturing(captured),
    )

    result = kernel_payload.run_datagen(
        str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
        shard_index=3, shard_count=4,
    )

    expected_seed_base = f"{SEED_BASES[_DATAGEN_HERO]}-s3"
    assert captured["seed_base"] == expected_seed_base

    sliced = load_schedule(captured["schedule_relpath"])
    assert len(sliced.rows) == 18  # 75 = 19+19+19+18
    assert [r.seed_index for r in sliced.rows] == list(range(18))

    assert "shard=3/4" in result["verdict"]
    assert "rows=18" in result["verdict"]


def test_run_datagen_shard_index_out_of_range_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded",
        _fake_run_schedule_seeded_capturing_shard({}),
    )
    monkeypatch.setattr(
        kernel_payload, "validate_datagen_output",
        _fake_validate_datagen_output_capturing({}),
    )

    with pytest.raises(ValueError):
        kernel_payload.run_datagen(
            str(_REPO_ROOT), "fake_showdown_dir", _DATAGEN_HERO, str(tmp_path / "out"),
            shard_index=5, shard_count=3,
        )


# ---------------------------------------------------------------------------
# datagen_kernel._extra_env_from_header (2b-2.5a EXTRA_ENV passthrough, 2026-07-11): pure
# header-field parsing/validation, tested directly -- the kernel's main() is never run here.
# ---------------------------------------------------------------------------

def test_extra_env_from_header_absent_field_returns_none():
    assert datagen_kernel._extra_env_from_header({"REPO_SHA": "abc", "HERO_KEY": "rain"}) is None


def test_extra_env_from_header_dict_passes_through():
    env = {
        "REPO_SHA": "abc", "HERO_KEY": "rain",
        "EXTRA_ENV": {"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0"},
    }

    assert datagen_kernel._extra_env_from_header(env) == {
        "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0",
    }


def test_extra_env_from_header_empty_dict_passes_through():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "EXTRA_ENV": {}}

    assert datagen_kernel._extra_env_from_header(env) == {}


def test_extra_env_from_header_non_dict_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "EXTRA_ENV": "not a dict"}

    with pytest.raises(ValueError, match="EXTRA_ENV"):
        datagen_kernel._extra_env_from_header(env)


def test_extra_env_from_header_non_string_value_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain",
           "EXTRA_ENV": {"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": -3.0}}

    with pytest.raises(ValueError, match="EXTRA_ENV"):
        datagen_kernel._extra_env_from_header(env)


def test_extra_env_from_header_non_string_key_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "EXTRA_ENV": {1: "x"}}

    with pytest.raises(ValueError, match="EXTRA_ENV"):
        datagen_kernel._extra_env_from_header(env)


def test_extra_env_from_header_list_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "EXTRA_ENV": ["not", "a", "dict"]}

    with pytest.raises(ValueError, match="EXTRA_ENV"):
        datagen_kernel._extra_env_from_header(env)


# ---------------------------------------------------------------------------
# datagen_kernel._shard_from_header (2b-2.5a schedule sharding, 2026-07-11): pure header-field
# parsing/validation, tested directly -- the kernel's main() is never run here.
# ---------------------------------------------------------------------------

def test_shard_from_header_absent_fields_default_to_zero_one():
    assert datagen_kernel._shard_from_header({"REPO_SHA": "abc", "HERO_KEY": "rain"}) == (0, 1)


def test_shard_from_header_explicit_valid_values_pass_through():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": 2, "SHARD_COUNT": 5}

    assert datagen_kernel._shard_from_header(env) == (2, 5)


def test_shard_from_header_only_shard_count_given_index_defaults_zero():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_COUNT": 4}

    assert datagen_kernel._shard_from_header(env) == (0, 4)


def test_shard_from_header_non_int_shard_index_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": "2", "SHARD_COUNT": 5}

    with pytest.raises(ValueError, match="SHARD_INDEX"):
        datagen_kernel._shard_from_header(env)


def test_shard_from_header_non_int_shard_count_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": 0, "SHARD_COUNT": 2.5}

    with pytest.raises(ValueError, match="SHARD_COUNT"):
        datagen_kernel._shard_from_header(env)


def test_shard_from_header_shard_count_less_than_one_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": 0, "SHARD_COUNT": 0}

    with pytest.raises(ValueError, match="SHARD_COUNT"):
        datagen_kernel._shard_from_header(env)


def test_shard_from_header_shard_index_out_of_range_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": 5, "SHARD_COUNT": 3}

    with pytest.raises(ValueError, match="SHARD_INDEX"):
        datagen_kernel._shard_from_header(env)


def test_shard_from_header_negative_shard_index_raises():
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": -1, "SHARD_COUNT": 3}

    with pytest.raises(ValueError, match="SHARD_INDEX"):
        datagen_kernel._shard_from_header(env)


def test_shard_from_header_bool_shard_index_raises():
    # JSON true/false decode to Python bool, a subclass of int -- must be rejected, not silently
    # treated as 0/1.
    env = {"REPO_SHA": "abc", "HERO_KEY": "rain", "SHARD_INDEX": True, "SHARD_COUNT": 3}

    with pytest.raises(ValueError, match="SHARD_INDEX"):
        datagen_kernel._shard_from_header(env)


# ---------------------------------------------------------------------------
# EXTRA_ENV header round-trip through kaggle_driver's env-header injection (pure -- confirms
# json.dumps/json.loads nest an EXTRA_ENV object without any special-casing needed in
# kaggle_driver.push, which reuses inject_env_header/parse_env_header for the whole header).
# ---------------------------------------------------------------------------

def test_extra_env_round_trips_through_kaggle_driver_env_header():
    kaggle_driver_path = _REPO_ROOT / "tools" / "kaggle" / "kaggle_driver.py"
    spec = importlib.util.spec_from_file_location("kaggle_driver_for_extra_env_test", kaggle_driver_path)
    kaggle_driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kaggle_driver)

    env = {
        "REPO_URL": "https://example.invalid/repo.git",
        "REPO_SHA": "deadbeef",
        "HERO_KEY": "rain",
        "EXTRA_ENV": {"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0"},
    }
    injected = kaggle_driver.inject_env_header("print(1)\n", env)

    assert kaggle_driver.parse_env_header(injected) == env
    assert datagen_kernel._extra_env_from_header(kaggle_driver.parse_env_header(injected)) == {
        "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0",
    }


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


def _dataset_lines_for_n_games(n: int) -> list[str]:
    return [_valid_dataset_row_line(game_id=f"g{i}", decision_id=f"d{i}") for i in range(n)]


def test_validate_datagen_output_missing_game_coverage_fails(tmp_path):
    """67/75 distinct game_ids -- one below ceil(0.9 * 75) == 68 -- must FAIL: below the 90%
    coverage threshold (2026-07-11: the coverage check is now a threshold, not exact equality,
    see the module docstring's COVERAGE THRESHOLD note)."""
    out_dir = _build_datagen_out_dir(tmp_path)
    dataset_lines = _dataset_lines_for_n_games(67)
    (out_dir / "dataset.jsonl").write_text("\n".join(dataset_lines) + "\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is False
    assert "game coverage" in detail
    assert "67" in detail and "75" in detail and "68" in detail


def test_validate_datagen_output_below_threshold_game_coverage_passes_with_detail(tmp_path):
    """74/75 distinct game_ids (one legitimate zero-row blowout game, e.g. trickroom's final
    run) is AT/ABOVE the 90% threshold (ceil(0.9*75) == 68) -> PASS, with the shortfall
    surfaced in the detail string rather than silently swallowed."""
    out_dir = _build_datagen_out_dir(tmp_path)
    dataset_lines = _dataset_lines_for_n_games(74)
    (out_dir / "dataset.jsonl").write_text("\n".join(dataset_lines) + "\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is True
    assert detail == "rows=74 games=74/75 (1 game(s) with zero sampled rows — below-threshold OK)"


def test_validate_datagen_output_exactly_at_threshold_passes(tmp_path):
    """68/75 distinct game_ids == ceil(0.9 * 75) exactly -> PASS (the boundary case)."""
    out_dir = _build_datagen_out_dir(tmp_path)
    dataset_lines = _dataset_lines_for_n_games(68)
    (out_dir / "dataset.jsonl").write_text("\n".join(dataset_lines) + "\n", encoding="utf-8")

    ok, detail = kernel_payload.validate_datagen_output(str(_REPO_ROOT), str(out_dir), _DATAGEN_HERO)

    assert ok is True
    assert detail == "rows=68 games=68/75 (7 game(s) with zero sampled rows — below-threshold OK)"


def test_validate_datagen_output_single_game_overwrite_signature_fails(tmp_path):
    """The Task-6 trickroom attempt-1 corruption signature: many schema-valid rows that ALL
    share one game_id (a battle-scoped export runtime overwrote dataset.jsonl each battle,
    leaving only the last battle's rows). Schema validation passes; coverage must still FAIL --
    1 distinct game is far below the 90% threshold, not just below exact equality."""
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
# MEMTRACE (2b-2.5a, added 2026-07-10, extended to v2 same day, v3 2026-07-11): memory telemetry
# sampler, added after datagen VMs OOM'd at deterministic battle counts while the top-8 RSS view
# stayed flat (see kernel_payload.py's run_datagen / module docstring for the incident). v2 added
# per-comm RSS aggregates across ALL processes (not just the top-8) plus kernel-level meminfo
# fields (Shmem/Slab/Cached/Buffers); v2 proved the leak was ~70 NEW "node" processes per battle,
# but ``comm`` is always just "node" -- it cannot say WHAT script or WHO spawned it. v3 switches
# the ps invocation to include the full command line (``args``) and PPID, classifies each process
# into a short signature (``_proc_signature``: calc.mjs / pokemon-showdown / node:<script> /
# <program>) instead of the useless "node" comm, and adds per-signature parent attribution
# (``_parse_ps_parent_attribution``) so a swarm of leaked processes can be traced to WHO spawns
# them. format_memtrace/_parse_meminfo/_parse_ps_rows/_proc_signature/_parse_ps_top/
# _parse_ps_aggregates/_parse_ps_parent_attribution/collect_memtrace_sample are pure/injectable
# and fully unit-tested here; start_memtrace is exercised with injected fakes + a short interval
# (no real /proc/meminfo or ps dependency).
# ---------------------------------------------------------------------------

def test_format_memtrace_golden_line():
    meminfo = {
        "avail_mb": 4096, "total_mb": 16384,
        "shmem_mb": 1, "slab_mb": 2048, "cached_mb": 3000, "buffers_mb": 128,
    }
    aggregates = {
        "calc.mjs": (3, 900),
        "python3": (4, 700),
        "pokemon-showdown": (2, 500),
        "sh": (5, 100),
    }
    parents = {
        "calc.mjs": ("python3", 3),
        "python3": ("?", 4),
        "pokemon-showdown": ("node:launcher.js", 2),
        "sh": ("python3", 5),
    }
    top_procs = [("calc.mjs", 1234, 50, 512), ("python3", 5678, 1, 256)]

    line = kernel_payload.format_memtrace(12.7, 3, meminfo, 20, 2300, aggregates, parents, top_procs)

    assert line == (
        "MEMTRACE t=12 done=3 availMB=4096/16384 shmem=1 slab=2048 cached=3000 buffers=128 "
        "procs=20:2300MB "
        "agg=[calc.mjs:n=3:900MB python3:n=4:700MB pokemon-showdown:n=2:500MB sh:n=5:100MB] "
        "parents=[calc.mjs<-python3:3 python3<-?:4 pokemon-showdown<-node:launcher.js:2 sh<-python3:5] "
        "top=[calc.mjs:1234:50:512MB python3:5678:1:256MB]"
    )


def test_format_memtrace_agg_keeps_only_top_4_by_sum_rss_desc():
    meminfo = {
        "avail_mb": 0, "total_mb": 0, "shmem_mb": 0, "slab_mb": 0, "cached_mb": 0, "buffers_mb": 0,
    }
    # 5 signatures -- only the top 4 by sum_rss_mb desc should appear, "z" (lowest sum) dropped
    # from BOTH agg=[...] and parents=[...].
    aggregates = {
        "a": (1, 100),
        "b": (1, 500),
        "c": (1, 300),
        "d": (1, 400),
        "z": (1, 10),
    }
    parents = {
        "a": ("x", 1), "b": ("x", 1), "c": ("x", 1), "d": ("x", 1), "z": ("x", 1),
    }

    line = kernel_payload.format_memtrace(0.0, 0, meminfo, 5, 1310, aggregates, parents, [])

    assert line.endswith(
        "agg=[b:n=1:500MB d:n=1:400MB c:n=1:300MB a:n=1:100MB] "
        "parents=[b<-x:1 d<-x:1 c<-x:1 a<-x:1] top=[]"
    )
    assert "z:" not in line
    assert "z<-" not in line


def test_parse_meminfo_reads_all_fields_kb_to_mb():
    text = (
        "MemTotal:       16777216 kB\n"
        "MemFree:         1000000 kB\n"
        "MemAvailable:    4194304 kB\n"
        "Buffers:           51200 kB\n"
        "Cached:           102400 kB\n"
        "SwapCached:            0 kB\n"
        "Shmem:               2048 kB\n"
        "Slab:             204800 kB\n"
    )

    meminfo = kernel_payload._parse_meminfo(text)

    assert meminfo == {
        "avail_mb": 4194304 // 1024,
        "total_mb": 16777216 // 1024,
        "shmem_mb": 2048 // 1024,
        "slab_mb": 204800 // 1024,
        "cached_mb": 102400 // 1024,
        "buffers_mb": 51200 // 1024,
    }


def test_parse_meminfo_missing_fields_default_to_zero():
    text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\n"

    meminfo = kernel_payload._parse_meminfo(text)

    assert meminfo == {
        "avail_mb": 4194304 // 1024,
        "total_mb": 16777216 // 1024,
        "shmem_mb": 0,
        "slab_mb": 0,
        "cached_mb": 0,
        "buffers_mb": 0,
    }


def test_parse_meminfo_cached_does_not_match_swapcached():
    # SwapCached only, no bare Cached: line -- must not false-match and must default to 0.
    text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\nSwapCached:    999999 kB\n"

    meminfo = kernel_payload._parse_meminfo(text)

    assert meminfo["cached_mb"] == 0


def _build_ps_text(procs):
    # header row first, like real `ps -eo pid,ppid,rss,args` output. `procs` entries are
    # (pid, ppid, rss_kb, args) -- args is LAST and may itself contain spaces.
    lines = ["  PID  PPID   RSS COMMAND"]
    for pid, ppid, rss, args in procs:
        lines.append(f"{pid:5d} {ppid:5d} {rss:6d} {args}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# _parse_ps_rows (v3: pid,ppid,rss,args -- args is last and may contain spaces)
# ---------------------------------------------------------------------------

def test_parse_ps_rows_splits_args_with_spaces_correctly():
    text = (
        "  PID  PPID   RSS COMMAND\n"
        "  100     1  2048 node /repo/showdown_bot/tools/calc/calc.mjs --port 9001 --verbose\n"
        "  200     1  4096 python3 -m showdown_bot.cli gauntlet --schedule x.yaml\n"
    )

    rows = kernel_payload._parse_ps_rows(text)

    assert rows == [
        (100, 1, 2048, "node /repo/showdown_bot/tools/calc/calc.mjs --port 9001 --verbose"),
        (200, 1, 4096, "python3 -m showdown_bot.cli gauntlet --schedule x.yaml"),
    ]


# ---------------------------------------------------------------------------
# _proc_signature (v3: process identity classifier)
# ---------------------------------------------------------------------------

def test_proc_signature_calc_mjs_server_line():
    args = "node /kaggle/working/repo/showdown_bot/tools/calc/calc.mjs --port 9001"
    assert kernel_payload._proc_signature(args) == "calc.mjs"


def test_proc_signature_pokemon_showdown_start_line():
    args = "node pokemon-showdown start 8000 --no-security"
    assert kernel_payload._proc_signature(args) == "pokemon-showdown"


def test_proc_signature_bare_node_script():
    args = "node /kaggle/working/repo/some/leaked-script.js --flag value"
    assert kernel_payload._proc_signature(args) == "node:leaked-script.js"


def test_proc_signature_bare_node_no_script_argument():
    assert kernel_payload._proc_signature("node") == "node:?"


def test_proc_signature_python3():
    args = "python3 -m showdown_bot.cli gauntlet --schedule x.yaml"
    assert kernel_payload._proc_signature(args) == "python3"


def test_proc_signature_ps():
    args = "ps -eo pid,ppid,rss,args --sort=-rss"
    assert kernel_payload._proc_signature(args) == "ps"


# ---------------------------------------------------------------------------
# _parse_ps_parent_attribution (v3: who spawns each signature)
# ---------------------------------------------------------------------------

def test_parse_ps_parent_attribution_resolves_shared_parents():
    # 5 calc.mjs children of one python3 parent (pid 50), 2 pokemon-showdown children of one
    # node parent (pid 60) -- the exact shape MEMTRACE v3 exists to surface: many leaked
    # processes of ONE kind, all spawned by the SAME parent.
    procs = [
        (50, 1, 20000, "python3 -m showdown_bot.cli gauntlet"),
        (60, 1, 30000, "node /kaggle/working/launcher.js"),
        (100, 50, 5000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 1"),
        (101, 50, 5000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 2"),
        (102, 50, 5000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 3"),
        (103, 50, 5000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 4"),
        (104, 50, 5000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 5"),
        (200, 60, 9000, "node pokemon-showdown start 8000 --no-security"),
        (201, 60, 9000, "node pokemon-showdown start 8000 --no-security"),
    ]
    ps_text = _build_ps_text(procs)
    rows = kernel_payload._parse_ps_rows(ps_text)

    parents = kernel_payload._parse_ps_parent_attribution(rows)

    assert parents["calc.mjs"] == ("python3", 5)
    assert parents["pokemon-showdown"] == ("node:launcher.js", 2)
    # pid 1 (the parents' own parent) is not in this snapshot -> unresolvable, "?".
    assert parents["python3"] == ("?", 1)
    assert parents["node:launcher.js"] == ("?", 1)


# ---------------------------------------------------------------------------
# collect_memtrace_sample / start_memtrace
# ---------------------------------------------------------------------------

def test_collect_memtrace_sample_with_injected_fakes(tmp_path):
    meminfo_text = (
        "MemTotal:       16777216 kB\n"
        "MemFree:         1000000 kB\n"
        "MemAvailable:    4194304 kB\n"
        "Buffers:           50000 kB\n"
    )
    # 10 rows, already sorted desc by rss (kB); header row first, like real `ps` output.
    procs = [
        (1, 0, 2000000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 1"),
        (2, 1, 1500000, "python3 -m showdown_bot.cli gauntlet"),
        (3, 1, 900000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 2"),
        (4, 1, 800000, "python3 -m showdown_bot.cli gauntlet"),
        (5, 1, 700000, "chrome --type=renderer"),
        (6, 1, 600000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 3"),
        (7, 1, 500000, "python3 -m showdown_bot.cli gauntlet"),
        (8, 1, 400000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 4"),
        (9, 1, 300000, "python3 -m showdown_bot.cli gauntlet"),
        (10, 1, 200000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 5"),
    ]
    ps_text = _build_ps_text(procs)

    results_path = tmp_path / "results.jsonl"
    results_path.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n', encoding="utf-8")

    sample = kernel_payload.collect_memtrace_sample(
        str(results_path),
        read_meminfo=lambda: meminfo_text,
        run_ps=lambda: ps_text,
    )

    assert sample["battles_done"] == 3
    assert sample["meminfo"]["avail_mb"] == 4194304 // 1024
    assert sample["meminfo"]["total_mb"] == 16777216 // 1024
    top = sample["top_procs"]
    assert len(top) == 8
    assert top[0] == ("calc.mjs", 1, 0, 2000000 // 1024)
    assert top[1] == ("python3", 2, 1, 1500000 // 1024)
    assert top[-1] == ("calc.mjs", 8, 1, 400000 // 1024)
    assert sample["total_proc_count"] == 10
    assert sample["total_rss_mb"] == sum(rss for _pid, _ppid, rss, _args in procs) // 1024


def test_collect_memtrace_sample_missing_results_file_done_zero(tmp_path):
    meminfo_text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\n"
    ps_text = _build_ps_text([(1, 0, 1000, "node /repo/showdown_bot/tools/calc/calc.mjs")])
    missing_path = tmp_path / "does_not_exist.jsonl"

    sample = kernel_payload.collect_memtrace_sample(
        str(missing_path),
        read_meminfo=lambda: meminfo_text,
        run_ps=lambda: ps_text,
    )

    assert sample["battles_done"] == 0


def test_collect_memtrace_sample_aggregates_cover_all_rows_not_just_top8():
    # 12 rows across 3 signatures -- deliberately more than the top-8 cutoff, so this proves the
    # aggregate covers ALL processes, not just the individually-listed top-8 (the whole point of
    # the per-signature aggregate: surface a hog made of MANY small processes each below the
    # top-8 cutoff).
    procs = [
        (1, 1, 100, "sh -c true"), (2, 1, 100, "sh -c true"), (3, 1, 100, "sh -c true"),
        (4, 1, 100, "sh -c true"), (5, 1, 100, "sh -c true"), (6, 1, 100, "sh -c true"),
        (7, 1, 100, "sh -c true"), (8, 1, 100, "sh -c true"), (9, 1, 100, "sh -c true"),
        (10, 1, 100, "sh -c true"),
        (11, 1, 5000, "node /repo/showdown_bot/tools/calc/calc.mjs --port 1"),
        (12, 1, 3000, "python3 -m showdown_bot.cli gauntlet"),
    ]
    ps_text = _build_ps_text(procs)
    meminfo_text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\n"

    sample = kernel_payload.collect_memtrace_sample(
        str(Path("does_not_exist_results.jsonl")),
        read_meminfo=lambda: meminfo_text,
        run_ps=lambda: ps_text,
    )

    assert sample["total_proc_count"] == 12
    assert sample["total_rss_mb"] == (10 * 100 + 5000 + 3000) // 1024

    agg = sample["aggregates"]
    assert agg["sh"] == (10, 1000 // 1024)
    assert agg["calc.mjs"] == (1, 5000 // 1024)
    assert agg["python3"] == (1, 3000 // 1024)

    # top-8 individual list is still just the 8 highest-RSS individual processes (calc.mjs,
    # python3, then 6 of the 10 "sh" rows) -- "sh" as a GROUP outweighs calc.mjs/python3, which
    # only the aggregate reveals.
    assert len(sample["top_procs"]) == 8
    top_sigs = [sig for sig, _pid, _ppid, _rss in sample["top_procs"]]
    assert top_sigs[0] == "calc.mjs"
    assert top_sigs[1] == "python3"

    # parent attribution: every process here has ppid=1, and pid 1 itself is one of the "sh"
    # rows -- so every signature (including "sh" itself) resolves its parent to "sh".
    parents = sample["parents"]
    assert parents["sh"] == ("sh", 10)
    assert parents["calc.mjs"] == ("sh", 1)
    assert parents["python3"] == ("sh", 1)


def test_start_memtrace_smoke(tmp_path, capsys):
    meminfo_text = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\n"
    ps_text = _build_ps_text([(1, 0, 1000, "node /repo/showdown_bot/tools/calc/calc.mjs")])
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

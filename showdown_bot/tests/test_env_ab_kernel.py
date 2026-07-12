"""2c-1: tests for the generic paired dev-strength env-A/B machinery --
``kernel_payload.run_devstrength_env_ab`` (tools/kaggle/kernel_payload.py) and the new thin
kernel script's header parsing (tools/kaggle/env_ab_kernel.py).

Mirrors test_kernel_payload.py's conventions throughout:

- HARD CONSTRAINT (no local battle runs / Showdown servers): ``run_devstrength_env_ab`` starts
  real subprocesses (via ``run_schedule_seeded``) and does real file I/O (via ``copy_outputs``).
  Both are monkeypatched to argument-capturing fakes here -- this file never runs a battle or
  touches a real ``/kaggle/working``-rooted path.
- ``tools/`` is not an installed package, so both modules under test are loaded directly from
  their file paths via importlib, same technique as test_kernel_payload.py's
  ``kernel_payload``/``datagen_kernel`` loads and test_kaggle_driver.py's ``kaggle_driver`` load.

This slice is explicitly additive: it must NOT touch ``run_gated_override_determinism``,
``run_gated_override_strength``, ``_2b4_override_env``, or ``gated_override_kernel.py`` at all --
none of those are imported or exercised by this file.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from showdown_bot.eval import schedule_2b4

_REPO_ROOT = Path(__file__).resolve().parents[2]
_KERNEL_PAYLOAD_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "kernel_payload.py"
_ENV_AB_KERNEL_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "env_ab_kernel.py"

_spec = importlib.util.spec_from_file_location("kernel_payload", _KERNEL_PAYLOAD_MODULE_PATH)
kernel_payload = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kernel_payload)

_env_ab_kernel_spec = importlib.util.spec_from_file_location(
    "env_ab_kernel", _ENV_AB_KERNEL_MODULE_PATH)
env_ab_kernel = importlib.util.module_from_spec(_env_ab_kernel_spec)
_env_ab_kernel_spec.loader.exec_module(env_ab_kernel)


# ---------------------------------------------------------------------------
# kernel_payload.run_devstrength_env_ab -- argument-capture tests (no real subprocess/file I/O:
# both run_schedule_seeded and copy_outputs are monkeypatched to recording fakes).
# ---------------------------------------------------------------------------

def _fake_run_schedule_seeded_capturing(calls):
    def fake(repo_root, showdown_dir, schedule_relpath, seed_base, out_dir, *,
             dataset_export=None, extra_env=None, timeout_s=9000):
        calls.append({
            "schedule_relpath": schedule_relpath,
            "seed_base": seed_base,
            "out_dir": out_dir,
            "extra_env": extra_env,
        })
        return {"results": str(Path(out_dir) / "results.jsonl")}
    return fake


def _fake_copy_outputs_capturing(calls):
    def fake(out_dir, working_dir="/kaggle/working"):
        calls.append({"out_dir": out_dir, "working_dir": working_dir})
        return []
    return fake


def test_run_devstrength_env_ab_calls_run_schedule_seeded_exactly_twice(tmp_path, monkeypatch):
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        candidate_env={"SHOWDOWN_MUST_REACT_LAMBDA": "0.3"},
    )

    assert len(run_calls) == 2


def test_run_devstrength_env_ab_uses_same_seed_base_both_times(tmp_path, monkeypatch):
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        candidate_env={"SHOWDOWN_MUST_REACT_LAMBDA": "0.3"},
    )

    assert run_calls[0]["seed_base"] == kernel_payload._MUSTREACT_AB_SEED_BASE
    assert run_calls[1]["seed_base"] == kernel_payload._MUSTREACT_AB_SEED_BASE
    assert run_calls[0]["seed_base"] == run_calls[1]["seed_base"]


def test_run_devstrength_env_ab_seed_base_is_distinct_from_gated_override_devstrength():
    # Load-bearing per eval.pairing.pair_runs' _CROSS_RUN_MATCH_FIELDS: a distinct seed_base
    # from the existing gated-override strength gate's constant, so this A/B's battle seeds never
    # collide with (or get mistaken for) a 2b-4 gated-override strength run's.
    assert kernel_payload._MUSTREACT_AB_SEED_BASE != kernel_payload._2B4_DEVSTRENGTH_SEED_BASE
    assert kernel_payload._MUSTREACT_AB_SEED_BASE == "2c1-mustreact-v001"


def test_run_devstrength_env_ab_passes_baseline_then_candidate_extra_env(tmp_path, monkeypatch):
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    baseline_env = {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"}
    candidate_env = {"SHOWDOWN_MUST_REACT_LAMBDA": "0.3"}
    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env=baseline_env, candidate_env=candidate_env,
    )

    assert run_calls[0]["extra_env"] == baseline_env
    assert run_calls[1]["extra_env"] == candidate_env


def test_run_devstrength_env_ab_out_dirs_end_baseline_then_candidate(tmp_path, monkeypatch):
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
    )

    assert run_calls[0]["out_dir"].replace("\\", "/").endswith("/baseline")
    assert run_calls[1]["out_dir"].replace("\\", "/").endswith("/candidate")


def test_run_devstrength_env_ab_uses_devstrength_schedule_relpath(tmp_path, monkeypatch):
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
    )

    expected = schedule_2b4.schedule_relpath("devstrength")
    assert run_calls[0]["schedule_relpath"] == expected
    assert run_calls[1]["schedule_relpath"] == expected


def test_run_devstrength_env_ab_schedule_and_seed_base_override(tmp_path, monkeypatch):
    # Held-out retarget: supplying schedule_relpath + seed_base makes BOTH arms use them (still one
    # schedule + one seed_base across arms, so eval.pairing.pair_runs still pairs). The gate run.
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        candidate_env={"SHOWDOWN_MUST_REACT_LAMBDA": "0.8"},
        schedule_relpath="config/eval/schedules/t6_heldout_v001.yaml",
        seed_base="t6heldout2026",
    )

    assert run_calls[0]["schedule_relpath"] == "config/eval/schedules/t6_heldout_v001.yaml"
    assert run_calls[1]["schedule_relpath"] == "config/eval/schedules/t6_heldout_v001.yaml"
    assert run_calls[0]["seed_base"] == "t6heldout2026"
    assert run_calls[1]["seed_base"] == "t6heldout2026"


def test_run_devstrength_env_ab_defaults_preserved_when_overrides_explicitly_none(tmp_path, monkeypatch):
    # Explicit None (what env_ab_kernel passes when the header omits the fields) is byte-identical
    # to the original dev-strength behaviour -- guards the backward-compat contract.
    run_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing(run_calls))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
        schedule_relpath=None, seed_base=None,
    )

    assert run_calls[0]["schedule_relpath"] == schedule_2b4.schedule_relpath("devstrength")
    assert run_calls[0]["seed_base"] == kernel_payload._MUSTREACT_AB_SEED_BASE
    assert run_calls[1]["seed_base"] == kernel_payload._MUSTREACT_AB_SEED_BASE


def test_run_devstrength_env_ab_copies_both_arms_out(tmp_path, monkeypatch):
    copy_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing([]))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing(copy_calls))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
        working_dir=str(tmp_path / "working"),
    )

    assert len(copy_calls) == 2
    assert copy_calls[0]["out_dir"].replace("\\", "/").endswith("/baseline")
    assert copy_calls[0]["working_dir"].replace("\\", "/").endswith("/working/baseline")
    assert copy_calls[1]["out_dir"].replace("\\", "/").endswith("/candidate")
    assert copy_calls[1]["working_dir"].replace("\\", "/").endswith("/working/candidate")


def test_run_devstrength_env_ab_copy_defaults_to_kaggle_working(tmp_path, monkeypatch):
    copy_calls = []
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing([]))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing(copy_calls))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
    )  # no working_dir override -- must default to /kaggle/working, mirroring copy_outputs itself

    assert copy_calls[0]["working_dir"] == str(Path("/kaggle/working") / "baseline")
    assert copy_calls[1]["working_dir"] == str(Path("/kaggle/working") / "candidate")


def test_run_devstrength_env_ab_returns_paths_and_verdict_mirroring_strength_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing([]))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    result = kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
    )

    assert set(result.keys()) == {"baseline", "candidate", "verdict"}
    assert result["baseline"]["results"].replace("\\", "/").endswith("/baseline/results.jsonl")
    assert result["candidate"]["results"].replace("\\", "/").endswith("/candidate/results.jsonl")
    assert result["verdict"].startswith("ENV-AB-STRENGTH: DONE")


def test_run_devstrength_env_ab_prints_verdict(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing([]))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
    )

    out = capsys.readouterr().out
    assert "ENV-AB-STRENGTH: DONE" in out


def test_run_devstrength_env_ab_does_not_touch_gated_override_env_helper(tmp_path, monkeypatch):
    """Spec: 'Do NOT modify the existing gated-override code.' -- confirms
    run_devstrength_env_ab never calls _2b4_override_env (the reranker-override env builder)."""
    calls = []
    monkeypatch.setattr(
        kernel_payload, "_2b4_override_env",
        lambda repo_root: calls.append(repo_root) or {"SHOULD_NOT": "BE_CALLED"},
    )
    monkeypatch.setattr(
        kernel_payload, "run_schedule_seeded", _fake_run_schedule_seeded_capturing([]))
    monkeypatch.setattr(
        kernel_payload, "copy_outputs", _fake_copy_outputs_capturing([]))

    kernel_payload.run_devstrength_env_ab(
        str(_REPO_ROOT), "fake_showdown_dir", str(tmp_path / "out"),
        baseline_env={"A": "1"}, candidate_env={"A": "2"},
    )

    assert calls == []


# ---------------------------------------------------------------------------
# env_ab_kernel header parsing -- pure, directly unit-tested (main() itself starts real
# subprocesses via git clone/checkout and is not exercised here, same rationale as
# datagen_kernel.py's/gated_override_kernel.py's main() -- only _env_dict_from_header and
# _parsed_header_fields are pure and tested directly).
# ---------------------------------------------------------------------------

def test_env_dict_from_header_valid_dict_passes_through():
    env = {"BASELINE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"}}

    assert env_ab_kernel._env_dict_from_header(env, "BASELINE_ENV") == {
        "SHOWDOWN_MUST_REACT_LAMBDA": "0.6",
    }


def test_env_dict_from_header_empty_dict_passes_through():
    env = {"CANDIDATE_ENV": {}}

    assert env_ab_kernel._env_dict_from_header(env, "CANDIDATE_ENV") == {}


def test_env_dict_from_header_missing_field_raises_value_error():
    env = {"REPO_SHA": "abc"}

    with pytest.raises(ValueError, match="BASELINE_ENV"):
        env_ab_kernel._env_dict_from_header(env, "BASELINE_ENV")


def test_env_dict_from_header_non_dict_raises_value_error():
    env = {"BASELINE_ENV": "not a dict"}

    with pytest.raises(ValueError, match="BASELINE_ENV"):
        env_ab_kernel._env_dict_from_header(env, "BASELINE_ENV")


def test_env_dict_from_header_list_raises_value_error():
    env = {"CANDIDATE_ENV": ["not", "a", "dict"]}

    with pytest.raises(ValueError, match="CANDIDATE_ENV"):
        env_ab_kernel._env_dict_from_header(env, "CANDIDATE_ENV")


def test_env_dict_from_header_non_string_value_raises_value_error():
    env = {"BASELINE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": 0.6}}

    with pytest.raises(ValueError, match="BASELINE_ENV"):
        env_ab_kernel._env_dict_from_header(env, "BASELINE_ENV")


def test_env_dict_from_header_non_string_key_raises_value_error():
    env = {"CANDIDATE_ENV": {1: "0.3"}}

    with pytest.raises(ValueError, match="CANDIDATE_ENV"):
        env_ab_kernel._env_dict_from_header(env, "CANDIDATE_ENV")


def test_parsed_header_fields_valid_header_parses_baseline_and_candidate_to_dicts():
    env = {
        "REPO_SHA": "deadbeef",
        "BASELINE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        "CANDIDATE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.3"},
    }

    repo_url, repo_sha, baseline_env, candidate_env = env_ab_kernel._parsed_header_fields(env)

    assert repo_url == env_ab_kernel._DEFAULT_REPO_URL
    assert repo_sha == "deadbeef"
    assert baseline_env == {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"}
    assert candidate_env == {"SHOWDOWN_MUST_REACT_LAMBDA": "0.3"}


def test_parsed_header_fields_explicit_repo_url_passes_through():
    env = {
        "REPO_URL": "https://example.invalid/repo.git",
        "REPO_SHA": "deadbeef",
        "BASELINE_ENV": {}, "CANDIDATE_ENV": {},
    }

    repo_url, _repo_sha, _baseline, _candidate = env_ab_kernel._parsed_header_fields(env)

    assert repo_url == "https://example.invalid/repo.git"


def test_parsed_header_fields_missing_repo_sha_raises():
    env = {"BASELINE_ENV": {}, "CANDIDATE_ENV": {}}

    with pytest.raises(KeyError):
        env_ab_kernel._parsed_header_fields(env)


def test_parsed_header_fields_missing_baseline_env_raises_value_error():
    env = {"REPO_SHA": "abc", "CANDIDATE_ENV": {}}

    with pytest.raises(ValueError, match="BASELINE_ENV"):
        env_ab_kernel._parsed_header_fields(env)


def test_parsed_header_fields_missing_candidate_env_raises_value_error():
    env = {"REPO_SHA": "abc", "BASELINE_ENV": {}}

    with pytest.raises(ValueError, match="CANDIDATE_ENV"):
        env_ab_kernel._parsed_header_fields(env)


def test_parsed_header_fields_non_dict_candidate_env_raises_value_error():
    env = {"REPO_SHA": "abc", "BASELINE_ENV": {}, "CANDIDATE_ENV": "nope"}

    with pytest.raises(ValueError, match="CANDIDATE_ENV"):
        env_ab_kernel._parsed_header_fields(env)


# ---------------------------------------------------------------------------
# _optional_run_overrides -- the OPTIONAL SCHEDULE_RELPATH/SEED_BASE retarget surface (held-out
# gate). Absent -> (None, None) -> dev-strength defaults preserved. Additive: does not touch the
# required-field _parsed_header_fields contract or its tests.
# ---------------------------------------------------------------------------

def test_optional_run_overrides_absent_returns_none_none():
    env = {
        "REPO_SHA": "abc",
        "BASELINE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        "CANDIDATE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.8"},
    }

    assert env_ab_kernel._optional_run_overrides(env) == (None, None)


def test_optional_run_overrides_present_passes_through():
    env = {
        "SCHEDULE_RELPATH": "config/eval/schedules/t6_heldout_v001.yaml",
        "SEED_BASE": "t6heldout2026",
    }

    assert env_ab_kernel._optional_run_overrides(env) == (
        "config/eval/schedules/t6_heldout_v001.yaml", "t6heldout2026")


def test_optional_run_overrides_partial_schedule_only():
    env = {"SCHEDULE_RELPATH": "config/eval/schedules/t6_heldout_v001.yaml"}

    assert env_ab_kernel._optional_run_overrides(env) == (
        "config/eval/schedules/t6_heldout_v001.yaml", None)


def test_optional_run_overrides_non_string_schedule_raises():
    with pytest.raises(ValueError, match="SCHEDULE_RELPATH"):
        env_ab_kernel._optional_run_overrides({"SCHEDULE_RELPATH": 123})


def test_optional_run_overrides_non_string_seed_base_raises():
    with pytest.raises(ValueError, match="SEED_BASE"):
        env_ab_kernel._optional_run_overrides({"SEED_BASE": ["nope"]})


def test_optional_run_overrides_survives_kaggle_driver_env_header_round_trip():
    kaggle_driver_path = _REPO_ROOT / "tools" / "kaggle" / "kaggle_driver.py"
    spec = importlib.util.spec_from_file_location(
        "kaggle_driver_for_env_ab_override_test", kaggle_driver_path)
    kaggle_driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kaggle_driver)

    env = {
        "REPO_SHA": "deadbeef",
        "BASELINE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        "CANDIDATE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.8"},
        "SCHEDULE_RELPATH": "config/eval/schedules/t6_heldout_v001.yaml",
        "SEED_BASE": "t6heldout2026",
    }
    injected = kaggle_driver.inject_env_header("print(1)\n", env)
    parsed = kaggle_driver.parse_env_header(injected)

    assert env_ab_kernel._optional_run_overrides(parsed) == (
        "config/eval/schedules/t6_heldout_v001.yaml", "t6heldout2026")


# ---------------------------------------------------------------------------
# BASELINE_ENV/CANDIDATE_ENV header round-trip through kaggle_driver's env-header injection
# (pure -- confirms nested JSON objects survive inject_env_header/parse_env_header unchanged,
# same proof as test_kernel_payload.py's EXTRA_ENV round-trip test).
# ---------------------------------------------------------------------------

def test_baseline_candidate_env_round_trips_through_kaggle_driver_env_header():
    kaggle_driver_path = _REPO_ROOT / "tools" / "kaggle" / "kaggle_driver.py"
    spec = importlib.util.spec_from_file_location(
        "kaggle_driver_for_env_ab_test", kaggle_driver_path)
    kaggle_driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kaggle_driver)

    env = {
        "REPO_SHA": "deadbeef",
        "BASELINE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.6"},
        "CANDIDATE_ENV": {"SHOWDOWN_MUST_REACT_LAMBDA": "0.3"},
    }
    injected = kaggle_driver.inject_env_header("print(1)\n", env)

    assert kaggle_driver.parse_env_header(injected) == env
    parsed = kaggle_driver.parse_env_header(injected)
    assert env_ab_kernel._env_dict_from_header(parsed, "BASELINE_ENV") == {
        "SHOWDOWN_MUST_REACT_LAMBDA": "0.6",
    }
    assert env_ab_kernel._env_dict_from_header(parsed, "CANDIDATE_ENV") == {
        "SHOWDOWN_MUST_REACT_LAMBDA": "0.3",
    }


# ---------------------------------------------------------------------------
# Module hygiene -- mirrors test_kernel_payload.py's
# test_module_has_no_kaggle_path_at_import_time.
# ---------------------------------------------------------------------------

def test_env_ab_kernel_module_has_no_kaggle_path_at_import_time():
    assert not str(_ENV_AB_KERNEL_MODULE_PATH.parent).startswith("/kaggle")
    assert hasattr(env_ab_kernel, "main")


def test_env_ab_kernel_does_not_import_gated_override_kernel_module():
    # Spec: "Do NOT modify the existing gated-override code" -- env_ab_kernel.py must be fully
    # self-contained and never import gated_override_kernel (prose cross-references to it in the
    # module docstring, mirroring the existing kernels' documentation convention, are fine).
    assert not hasattr(env_ab_kernel, "gated_override_kernel")
    source_lines = _ENV_AB_KERNEL_MODULE_PATH.read_text(encoding="utf-8").splitlines()
    import_lines = [ln for ln in source_lines if ln.startswith(("import ", "from "))]
    assert not any("gated_override_kernel" in ln for ln in import_lines)

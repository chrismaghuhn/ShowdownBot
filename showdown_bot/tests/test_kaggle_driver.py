"""2b-2.5a T1: tests for the PURE parts of tools/kaggle/kaggle_driver.py
(build_kernel_metadata, inject_env_header/parse_env_header, parse_verdict).

The thin network functions (push/status/wait/download_output) are NOT
unit-tested (no real Kaggle API calls in tests) -- exercised operationally
in Task 3/6, per the module's own docstring.

tools/ is not an installed package (it sits at the repo root, alongside
showdown_bot/, not inside it), so the module under test is loaded directly
from its file path via importlib rather than a normal import.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "kaggle" / "kaggle_driver.py"

_spec = importlib.util.spec_from_file_location("kaggle_driver", _MODULE_PATH)
kaggle_driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kaggle_driver)


# ---------------------------------------------------------------------------
# build_kernel_metadata
# ---------------------------------------------------------------------------

def test_build_kernel_metadata_shape():
    meta = kaggle_driver.build_kernel_metadata("sb-repro-validation", "tools/kaggle/repro_validation.py")
    assert meta == {
        "id": "chrismaghuhn/sb-repro-validation",
        "title": "sb-repro-validation",
        "code_file": "repro_validation.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": False,
        "enable_internet": True,
    }


def test_build_kernel_metadata_uses_code_file_basename():
    meta = kaggle_driver.build_kernel_metadata("slug", "/abs/path/to/script.py")
    assert meta["code_file"] == "script.py"


def test_build_kernel_metadata_gpu_and_internet_overrides():
    meta = kaggle_driver.build_kernel_metadata("slug", "script.py", enable_gpu=True, enable_internet=False)
    assert meta["enable_gpu"] is True
    assert meta["enable_internet"] is False


def test_build_kernel_metadata_defaults():
    meta = kaggle_driver.build_kernel_metadata("slug", "script.py")
    assert meta["enable_gpu"] is False
    assert meta["enable_internet"] is True
    assert meta["is_private"] is True
    assert meta["kernel_type"] == "script"
    assert meta["language"] == "python"


# ---------------------------------------------------------------------------
# env header inject/parse
# ---------------------------------------------------------------------------

def test_inject_env_header_prepends_line():
    script = "import sys\nprint('hi')\n"
    injected = kaggle_driver.inject_env_header(script, {"REPO_SHA": "abc123"})
    lines = injected.splitlines()
    assert lines[0] == '# KAGGLE_ENV: {"REPO_SHA": "abc123"}'
    assert lines[1:] == ["import sys", "print('hi')"]


def test_env_header_round_trip():
    env = {"REPO_SHA": "deadbeef", "HERO_KEY": "fixed", "n": 3}
    injected = kaggle_driver.inject_env_header("print(1)\n", env)
    assert kaggle_driver.parse_env_header(injected) == env


def test_inject_env_header_replaces_existing_header_no_duplicate():
    script = "print(1)\n"
    once = kaggle_driver.inject_env_header(script, {"REPO_SHA": "aaa"})
    twice = kaggle_driver.inject_env_header(once, {"REPO_SHA": "bbb"})
    lines = twice.splitlines()
    assert sum(1 for l in lines if l.startswith("# KAGGLE_ENV:")) == 1
    assert kaggle_driver.parse_env_header(twice) == {"REPO_SHA": "bbb"}
    assert lines[1:] == ["print(1)"]


def test_inject_env_header_preserves_no_trailing_newline():
    injected = kaggle_driver.inject_env_header("print(1)", {"a": 1})
    assert not injected.endswith("\n")


def test_parse_env_header_returns_empty_dict_when_absent():
    assert kaggle_driver.parse_env_header("print(1)\n") == {}


def test_parse_env_header_empty_string():
    assert kaggle_driver.parse_env_header("") == {}


# ---------------------------------------------------------------------------
# parse_verdict
# ---------------------------------------------------------------------------

def test_parse_verdict_pass():
    log = "some log noise\nKAGGLE-REPRO: PASS (10/10 winner+seed match)\ntrailer\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "PASS"
    assert line == "KAGGLE-REPRO: PASS (10/10 winner+seed match)"


def test_parse_verdict_fail():
    log = "KAGGLE-REPRO: FAIL (winner mismatch at game 4)\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "FAIL"
    assert "winner mismatch" in line


def test_parse_verdict_env_ab_strength_done():
    # 2c-1: tools/kaggle/env_ab_kernel.py's verdict prefix.
    log = "some log noise\nENV-AB-STRENGTH: DONE (baseline=x candidate=y)\ntrailer\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "DONE"
    assert line == "ENV-AB-STRENGTH: DONE (baseline=x candidate=y)"


def test_parse_verdict_env_ab_strength_fail():
    log = "ENV-AB-STRENGTH: FAIL (exception: boom)\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "FAIL"
    assert "boom" in line


def test_parse_verdict_done():
    log = "DATAGEN: DONE hero=fixed rows=1234 games=75\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "DONE"
    assert line == "DATAGEN: DONE hero=fixed rows=1234 games=75"


def test_parse_verdict_none_when_absent():
    verdict, line = kaggle_driver.parse_verdict("just some ordinary log output\nno verdict here\n")
    assert verdict is None
    assert line == ""


def test_parse_verdict_empty_log():
    verdict, line = kaggle_driver.parse_verdict("")
    assert verdict is None
    assert line == ""


def test_parse_verdict_last_line_wins_same_prefix():
    log = (
        "KAGGLE-REPRO: FAIL (transient network error)\n"
        "retrying...\n"
        "KAGGLE-REPRO: PASS (10/10 winner+seed match)\n"
    )
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "PASS"
    assert "PASS" in line


def test_parse_verdict_last_line_wins_mixed_prefixes():
    log = "DATAGEN: DONE hero=fixed rows=1 games=1\nKAGGLE-REPRO: PASS (ok)\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "PASS"
    assert line == "KAGGLE-REPRO: PASS (ok)"


def test_parse_verdict_kaggle_json_stream_log():
    # Live-API shape (Task 3): download_output's <slug>.log is a JSON array of
    # {stream_name, time, data} records, not plain text.
    import json as _json
    records = [
        {"stream_name": "stdout", "time": 1.0, "data": "cloning...\n"},
        {"stream_name": "stdout", "time": 15.4, "data": "KAGGLE-REPRO: FAIL (exception: No module named 'showdown_bot')\n"},
        {"stream_name": "stderr", "time": 15.5, "data": "Traceback (most recent call last):\n"},
    ]
    verdict, line = kaggle_driver.parse_verdict(_json.dumps(records))
    assert verdict == "FAIL"
    assert "No module named" in line


def test_parse_verdict_kaggle_json_stream_log_data_split_across_records():
    # The verdict line itself arriving as one record among many, with other
    # lines split across records arbitrarily.
    import json as _json
    records = [
        {"stream_name": "stdout", "time": 1.0, "data": "setup "},
        {"stream_name": "stdout", "time": 1.1, "data": "done\n"},
        {"stream_name": "stdout", "time": 99.0, "data": "KAGGLE-REPRO: PASS (10/10 winner+seed match)\n"},
    ]
    verdict, line = kaggle_driver.parse_verdict(_json.dumps(records))
    assert verdict == "PASS"
    assert line == "KAGGLE-REPRO: PASS (10/10 winner+seed match)"


def test_parse_verdict_bracket_leading_plain_text_still_works():
    # Plain-text logs that merely START with '[' (e.g. "[NbConvertApp] ...")
    # must not be mistaken for the JSON-stream shape.
    log = "[NbConvertApp] Converting notebook\nKAGGLE-REPRO: PASS (ok)\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "PASS"
    assert line == "KAGGLE-REPRO: PASS (ok)"


# ---------------------------------------------------------------------------
# 2b-4 Task 3: gated_override_kernel.py's 2B4-DETERMINISM:/2B4-STRENGTH: verdict lines
# ---------------------------------------------------------------------------

def test_parse_verdict_2b4_determinism_pass():
    log = "2B4-DETERMINISM: PASS (24 battles compared, 0 diff(s))\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "PASS"
    assert line == "2B4-DETERMINISM: PASS (24 battles compared, 0 diff(s))"


def test_parse_verdict_2b4_determinism_fail():
    log = "2B4-DETERMINISM: FAIL (24 battles compared, 3 diff(s))\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "FAIL"
    assert "3 diff(s)" in line


def test_parse_verdict_2b4_strength_done():
    log = "2B4-STRENGTH: DONE (heuristic=/tmp/sb_out/heuristic/results.jsonl override=/tmp/sb_out/override/results.jsonl)\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "DONE"
    assert line.startswith("2B4-STRENGTH: DONE")


def test_parse_verdict_2b4_last_line_wins_mixed_with_other_prefixes():
    log = "DATAGEN: DONE hero=fixed rows=1 games=1\n2B4-DETERMINISM: PASS (24 battles compared, 0 diff(s))\n"
    verdict, line = kaggle_driver.parse_verdict(log)
    assert verdict == "PASS"
    assert line.startswith("2B4-DETERMINISM:")


# ---------------------------------------------------------------------------
# _is_stale_terminal (2b-2.5a Task 5: stale previous-run-status guard for `wait`)
# ---------------------------------------------------------------------------

def test_is_stale_terminal_true_for_terminal_status_before_min_elapsed():
    assert kaggle_driver._is_stale_terminal("COMPLETE", 10.0, 90) is True


def test_is_stale_terminal_false_for_terminal_status_after_min_elapsed():
    assert kaggle_driver._is_stale_terminal("COMPLETE", 91.0, 90) is False


def test_is_stale_terminal_false_exactly_at_min_elapsed():
    # elapsed_s == min_elapsed_s is NOT stale (the guard uses a strict '<').
    assert kaggle_driver._is_stale_terminal("ERROR", 90.0, 90) is False


def test_is_stale_terminal_false_for_non_terminal_status_regardless_of_elapsed():
    assert kaggle_driver._is_stale_terminal("RUNNING", 0.0, 90) is False
    assert kaggle_driver._is_stale_terminal("QUEUED", 0.0, 90) is False


def test_is_stale_terminal_true_for_every_terminal_status_when_early():
    for state in ("COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED"):
        assert kaggle_driver._is_stale_terminal(state, 0.0, 90) is True


# ---------------------------------------------------------------------------
# Module hygiene: kaggle must be imported lazily (inside functions only), so
# importing/testing this module never requires kaggle credentials.
# ---------------------------------------------------------------------------

def test_kaggle_package_only_imported_lazily():
    source = _MODULE_PATH.read_text(encoding="utf-8")
    for line in source.splitlines():
        assert not line.startswith("import kaggle"), f"top-level kaggle import found: {line!r}"
        assert not line.startswith("from kaggle"), f"top-level kaggle import found: {line!r}"

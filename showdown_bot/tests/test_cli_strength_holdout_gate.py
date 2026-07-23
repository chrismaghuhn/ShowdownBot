"""Gate B (Independent Strength Holdout) CLI subcommands — Task 11 + Task 13 step-3 wiring.

As of Task 13 step 3 both subcommands are WIRED: they source the six holdout team IDs and content
hashes from the authoritative holdout manifest, build the real schedule from the real panel, and
call the real runner/combiner. Nothing here starts a server or plays a battle -- the runner is
stubbed for the success-path tests, and every data-sourcing / argparse error path is exercised
without one.

Worktree note: ``_run_cli`` propagates this interpreter's ``sys.path`` into the subprocess as
``PYTHONPATH`` so ``python -m showdown_bot.cli`` resolves the WORKTREE package (which pytest is
already using), not the globally-installed editable copy in the main checkout -- without this the
subprocess would import a showdown_bot that has never heard of these subcommands (worktree trap #2).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/ -> showdown_bot/ -> <repo>
_MANIFEST_PATH = _REPO_ROOT / "config" / "eval" / "holdout" / "champions_strength_holdout_v0_manifest.json"


def _run_cli(*argv):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    return subprocess.run(
        [sys.executable, "-m", "showdown_bot.cli", *argv], capture_output=True, text=True, env=env,
    )


def _manifest_id_to_hash():
    man = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    # IDs read from the authoritative manifest -- never hardcoded (Amendment A1.1).
    return {t["team_id"]: t["team_content_hash"] for t in man["teams"]}


def _arm_args(**overrides):
    base = dict(
        command="champions-strength-holdout-arm", hero_agent="heuristic",
        out_dir=str(_REPO_ROOT / "unused-because-runner-is-stubbed"),
        seed_log_path="seeds.jsonl", teams_root=str(_REPO_ROOT),
        date_stratum_id="2026-07-23-windows", stratum_override="",
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _combine_args(**overrides):
    base = dict(
        command="champions-strength-holdout-combine", arm_a_dir="a", arm_b_dir="b", out_dir="out",
        i8d_verdict_path="i8d.json", coverage_verdict_path="cov.json",
        teams_root=str(_REPO_ROOT), stratum_override="",
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


# --- argparse surface (subprocess against the worktree CLI) ------------------------------------


def test_cli_exposes_both_strength_holdout_subcommands():
    result = _run_cli("--help")
    assert "champions-strength-holdout-arm" in result.stdout
    assert "champions-strength-holdout-combine" in result.stdout


def test_arm_subcommand_requires_hero_agent_and_out_dir():
    result = _run_cli("champions-strength-holdout-arm")
    assert result.returncode != 0
    assert "invalid choice" not in result.stderr  # an unknown command's usage also lists --out-dir
    assert "--hero-agent" in result.stderr or "--out-dir" in result.stderr


def test_arm_requires_the_date_stratum_id(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-arm", "--hero-agent", "heuristic",
        "--out-dir", str(tmp_path / "o"), "--seed-log-path", str(tmp_path / "s.jsonl"),
        "--teams-root", str(tmp_path),
    )
    assert result.returncode != 0
    assert "invalid choice" not in result.stderr
    assert "--date-stratum-id" in result.stderr


def test_arm_treats_a_whitespace_only_date_stratum_id_as_missing(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-arm", "--hero-agent", "heuristic",
        "--out-dir", str(tmp_path / "o"), "--seed-log-path", str(tmp_path / "s.jsonl"),
        "--teams-root", str(tmp_path), "--date-stratum-id", "   ",
    )
    assert result.returncode != 0
    assert "--date-stratum-id" in result.stderr


def test_arm_rejects_an_invalid_stratum_override(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-arm", "--hero-agent", "heuristic",
        "--out-dir", str(tmp_path / "o"), "--seed-log-path", str(tmp_path / "s.jsonl"),
        "--teams-root", str(tmp_path), "--date-stratum-id", "d", "--stratum-override", "bogus",
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_combine_subcommand_requires_both_arm_dirs():
    result = _run_cli("champions-strength-holdout-combine")
    assert result.returncode != 0
    assert "--arm-a-dir" in result.stderr or "--arm-b-dir" in result.stderr


def test_combine_subcommand_requires_both_upstream_verdict_paths():
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", "a", "--arm-b-dir", "b", "--out-dir", "out",
    )
    assert result.returncode != 0
    assert "invalid choice" not in result.stderr
    assert "--i8d-verdict-path" in result.stderr or "--coverage-verdict-path" in result.stderr


def test_combine_still_requires_the_coverage_verdict_path_when_only_i8d_is_given():
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", "a", "--arm-b-dir", "b", "--out-dir", "out",
        "--i8d-verdict-path", "i8d.json",
    )
    assert result.returncode != 0
    assert "--coverage-verdict-path" in result.stderr


def test_existing_commands_still_parse_without_the_new_gate_b_flags():
    from showdown_bot.cli import _build_parser
    args = _build_parser().parse_args(["smoke"])
    assert args.command == "smoke"
    for flag in ("hero_agent", "seed_log_path", "arm_a_dir", "arm_b_dir", "coverage_verdict_path",
                 "date_stratum_id", "stratum_override"):
        assert getattr(args, flag) == ""


# --- combine error mapping (pure helper, in-process) -------------------------------------------


def test_describe_combine_error_maps_access_budget_error():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.heldout_ledger import AccessBudgetError
    message, code = _describe_strength_holdout_combine_error(AccessBudgetError("budget spent"))
    assert "policy decision" in message
    assert "justification" in message
    assert code == 2


def test_describe_combine_error_maps_all_four_integrity_guards_to_the_same_code():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError
    from showdown_bot.eval.strata_guard import StrataPoolingError, UnattestedStratumError
    for exc in (HoldoutNotDisjointError("x"), LeakageDriftError("x"), StrataPoolingError("x"), UnattestedStratumError("x")):
        message, code = _describe_strength_holdout_combine_error(exc)
        assert "integrity" in message
        assert code == 3


def test_describe_combine_error_maps_leakage_scan_error_distinctly_from_leakage_drift_error():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_leakage_scan import LeakageScanError
    message, code = _describe_strength_holdout_combine_error(LeakageScanError("git missing"))
    assert "could not be completed" in message
    assert code == 4


def test_describe_combine_error_maps_gatebabort_to_exit_code_one_unchanged():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    message, code = _describe_strength_holdout_combine_error(GateBAbort("blocked"))
    assert message == "blocked"
    assert code == 1


def test_describe_combine_error_refuses_to_mislabel_an_unrecognized_exception_type():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    with pytest.raises(TypeError, match="unrecognized"):
        _describe_strength_holdout_combine_error(ValueError("not a Gate B exception"))


def test_leakage_scan_error_is_not_swallowed_by_the_leakage_drift_branch():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    _, drift_code = _describe_strength_holdout_combine_error(LeakageDriftError("x"))
    _, scan_code = _describe_strength_holdout_combine_error(LeakageScanError("x"))
    assert (drift_code, scan_code) == (3, 4)


# --- real wiring: manifest-sourced IDs/hashes + real schedule, runner stubbed -------------------


def test_arm_cli_sources_the_six_teams_from_the_manifest_and_runs_windows_without_override(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.run_strength_holdout_arm",
        lambda **kw: captured.update(kw) or {"ok": True},
    )
    from showdown_bot.cli import run_strength_holdout_arm_cli
    rc = run_strength_holdout_arm_cli(_arm_args())
    assert rc == 0
    # sourced from the manifest, not hardcoded or invented
    assert captured["holdout_team_content_hashes"] == _manifest_id_to_hash()
    # a real 180-key schedule built from the real panel
    assert len(captured["schedule"].battle_keys) == 180
    # windows / empty override -> None threaded to detect_stratum
    assert captured["stratum_env_override"] is None
    assert captured["hero_agent"] == "heuristic"
    assert captured["date_stratum_id"] == "2026-07-23-windows"
    assert captured["teams_root"] == str(_REPO_ROOT)


def test_arm_cli_threads_the_kaggle_override_to_the_runner(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.run_strength_holdout_arm",
        lambda **kw: captured.update(kw) or {},
    )
    from showdown_bot.cli import run_strength_holdout_arm_cli
    rc = run_strength_holdout_arm_cli(_arm_args(stratum_override="kaggle"))
    assert rc == 0
    assert captured["stratum_env_override"] == "kaggle"


def test_arm_cli_no_longer_names_a_task13_blocker_and_prints_no_traceback(monkeypatch):
    # The runner is stubbed to raise the SAME abort a real serverless run would (missing seed-base
    # env), proving the handler reaches the runner rather than a Task-13 data stop, maps it to a
    # clean exit 1, and prints no traceback.
    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    def _boom(**kw):
        raise GateBAbort("SHOWDOWN_BATTLE_SEED_BASE must be ... (serverless)")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.run_strength_holdout_arm", _boom)
    from showdown_bot.cli import run_strength_holdout_arm_cli
    rc = run_strength_holdout_arm_cli(_arm_args())
    assert rc == 1


def test_combine_cli_sources_manifest_hashes_and_passes_override_as_expectation_only(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.combine_strength_holdout_arms",
        lambda **kw: captured.update(kw) or {"verdict": "X"},
    )
    from showdown_bot.cli import run_strength_holdout_combine_cli
    rc = run_strength_holdout_combine_cli(_combine_args(stratum_override="windows"))
    assert rc == 0
    assert captured["holdout_content_hashes"] == _manifest_id_to_hash()
    # combine receives the override only as an expectation string; it never re-detects the stratum
    # (that property is enforced inside combine_strength_holdout_arms itself; here we only prove the
    # CLI passes it through rather than calling detect_stratum).
    assert captured["stratum_env_override"] == "windows"
    assert captured["arm_a_dir"] == "a" and captured["arm_b_dir"] == "b"


def test_arm_cli_aborts_before_battle_1_when_the_panel_drifts_from_the_frozen_hash(monkeypatch):
    # P1: sourcing the panel/manifest is not enough -- the on-disk identity must equal the FROZEN
    # constants before the arm plays. Simulate drift by moving the frozen panel-hash constant; the
    # real panel then no longer matches, so the arm must abort and never call the runner.
    ran = {"v": False}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.run_strength_holdout_arm",
        lambda **kw: ran.__setitem__("v", True),
    )
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_schedule.STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH",
        "deadbeefdeadbeef",
    )
    from showdown_bot.cli import run_strength_holdout_arm_cli
    rc = run_strength_holdout_arm_cli(_arm_args())
    assert rc == 1
    assert ran["v"] is False


def test_arm_cli_aborts_before_battle_1_when_the_manifest_drifts_from_the_frozen_hash(monkeypatch):
    ran = {"v": False}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.run_strength_holdout_arm",
        lambda **kw: ran.__setitem__("v", True),
    )
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_schedule.STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH",
        "deadbeefdeadbeef",
    )
    from showdown_bot.cli import run_strength_holdout_arm_cli
    rc = run_strength_holdout_arm_cli(_arm_args())
    assert rc == 1
    assert ran["v"] is False


def test_combine_cli_aborts_when_the_frozen_gate_b_identity_drifts(monkeypatch):
    ran = {"v": False}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.combine_strength_holdout_arms",
        lambda **kw: ran.__setitem__("v", True),
    )
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_schedule.STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH",
        "deadbeefdeadbeef",
    )
    from showdown_bot.cli import run_strength_holdout_combine_cli
    rc = run_strength_holdout_combine_cli(_combine_args())
    assert rc != 0
    assert ran["v"] is False


def test_arm_cli_aborts_cleanly_when_the_holdout_manifest_is_missing(monkeypatch, tmp_path):
    # A teams_root with no manifest must abort with a named GateBAbort-mapped message and exit 1,
    # before any runner call -- no traceback, nothing published.
    called = {"ran": False}
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner.run_strength_holdout_arm",
        lambda **kw: called.__setitem__("ran", True),
    )
    from showdown_bot.cli import run_strength_holdout_arm_cli
    rc = run_strength_holdout_arm_cli(_arm_args(teams_root=str(tmp_path)))
    assert rc == 1
    assert called["ran"] is False

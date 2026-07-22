"""Gate B (Independent Strength Holdout) CLI subcommands — Task 11, plan §14.

Both subcommands are deliberately, honestly blocked until Task 13 seals the six holdout teams:
they name that blocker and exit non-zero rather than raising NotImplementedError, printing a
traceback, or (worse) silently "succeeding" against empty inputs. Nothing here starts a server,
plays a battle, or needs a team file.
"""
from __future__ import annotations

import subprocess
import sys

import pytest


def _run_cli(*argv):
    return subprocess.run(
        [sys.executable, "-m", "showdown_bot.cli", *argv], capture_output=True, text=True,
    )


def test_cli_exposes_both_strength_holdout_subcommands():
    result = _run_cli("--help")
    assert "champions-strength-holdout-arm" in result.stdout
    assert "champions-strength-holdout-combine" in result.stdout


def test_arm_subcommand_requires_hero_agent_and_out_dir():
    result = _run_cli("champions-strength-holdout-arm")
    assert result.returncode != 0
    # Without this the assertion below is vacuous: an UNKNOWN command makes argparse print the
    # full usage line, which already contains "--out-dir" -- so the test would pass just as well
    # against a CLI that has never heard of this subcommand (verified: it did, before Task 11).
    assert "invalid choice" not in result.stderr
    assert "--hero-agent" in result.stderr or "--out-dir" in result.stderr


def test_combine_subcommand_requires_both_arm_dirs():
    result = _run_cli("champions-strength-holdout-combine")
    assert result.returncode != 0
    assert "--arm-a-dir" in result.stderr or "--arm-b-dir" in result.stderr


def test_combine_subcommand_requires_both_upstream_verdict_paths():
    # Rev. 3 fix: these must be genuinely required, not silently optional (Task 10's core-function
    # bug, mirrored here at the CLI layer). Supplying everything EXCEPT the two verdict paths is
    # what isolates this check -- the bare invocation above would already fail on the arm dirs.
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", "a", "--arm-b-dir", "b", "--out-dir", "out",
    )
    assert result.returncode != 0
    assert "invalid choice" not in result.stderr  # see the arm test above for why
    assert "--i8d-verdict-path" in result.stderr or "--coverage-verdict-path" in result.stderr


def test_combine_still_requires_the_coverage_verdict_path_when_only_i8d_is_given():
    # Guards against a check that stops at the first missing path: the coverage verdict is not
    # optional just because the I8-D one was supplied.
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", "a", "--arm-b-dir", "b", "--out-dir", "out",
        "--i8d-verdict-path", "i8d.json",
    )
    assert result.returncode != 0
    assert "--coverage-verdict-path" in result.stderr


# NF4 fix (Rev. 8): _describe_strength_holdout_combine_error is a pure function, fully testable
# today independent of Task 13 -- these tests do NOT go through the CLI subprocess above (which
# can't reach the real combine_strength_holdout_arms call yet), they call the mapping helper
# directly.
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
    assert code == 4  # NOT 3 -- "couldn't check" must never read as "checked, found a problem"


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
    # LeakageScanError and LeakageDriftError live in the same module and are easy to collapse into
    # one isinstance tuple. If they ever share a branch this test fails, because "the scan could
    # not run" (4) and "the scan ran and found a leak" (3) are different operator decisions.
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    _, drift_code = _describe_strength_holdout_combine_error(LeakageDriftError("x"))
    _, scan_code = _describe_strength_holdout_combine_error(LeakageScanError("x"))
    assert (drift_code, scan_code) == (3, 4)


# --- End-to-end handler regressions: the honest Task-13 blocker, no teams/server/battles -------


def test_full_arm_invocation_reaches_the_named_task13_blocker_without_a_traceback(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-arm",
        "--hero-agent", "heuristic",
        "--out-dir", str(tmp_path / "arm_out"),
        "--seed-log-path", str(tmp_path / "seeds.jsonl"),
        "--teams-root", str(tmp_path),
    )
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "NotImplementedError" not in result.stderr
    assert "champions-strength-holdout-arm:" in result.stderr
    assert "Task 13" in result.stderr
    # Nothing was published: an honest stop must not leave a half-built artifact behind.
    assert not (tmp_path / "arm_out").exists()


def test_full_combine_invocation_reaches_the_named_task13_blocker_without_a_traceback(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", str(tmp_path / "arm_a"),
        "--arm-b-dir", str(tmp_path / "arm_b"),
        "--out-dir", str(tmp_path / "combined"),
        "--i8d-verdict-path", str(tmp_path / "i8d.json"),
        "--coverage-verdict-path", str(tmp_path / "cov.json"),
    )
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "NotImplementedError" not in result.stderr
    assert "champions-strength-holdout-combine:" in result.stderr
    assert "Task 13" in result.stderr
    assert not (tmp_path / "combined").exists()


def test_existing_commands_still_parse_without_the_new_gate_b_flags():
    # The new flags are global (this CLI has no subparsers), so they must keep an empty default --
    # marking any of them required=True would break every other command's invocation.
    from showdown_bot.cli import _build_parser
    args = _build_parser().parse_args(["smoke"])
    assert args.command == "smoke"
    for flag in ("hero_agent", "seed_log_path", "arm_a_dir", "arm_b_dir", "coverage_verdict_path"):
        assert getattr(args, flag) == ""

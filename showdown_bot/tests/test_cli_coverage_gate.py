"""Task 7: an executable, provenance-locked coverage gate entry point. The champions-coverage-gate
command hard-locks the coverage panel/manifest, requires --out-dir + SHOWDOWN_EVAL_SEED_LOG, derives
provenance INSIDE the runner (no caller git_sha/config_hash), re-verifies the panel + teams from
disk, and reaches run_coverage_gate. No server/battles: the schedule build, verify and run are
stubbed at the module seam.
"""
from __future__ import annotations

import argparse

import pytest


class _Sched:
    schedule_hash = "sched-cov"
    panel_hash = "a9ba2ad60ef16595"
    rows = ()


def _install_cli_stubs(monkeypatch, captured):
    import showdown_bot.eval.coverage_runner as cr
    import showdown_bot.eval.coverage_schedule as cs

    def _fake_build(panel_path, manifest_path, *, n_battles, teams_root):
        captured["panel_path"] = panel_path
        captured["manifest_path"] = manifest_path
        captured["n_battles"] = n_battles
        captured["built"] = _Sched()
        return captured["built"]

    def _fake_verify(schedule, *, teams_root, **kw):
        captured["verified"] = (schedule, teams_root)

    def _fake_run(**kw):
        captured["run_kwargs"] = kw
        return {"verdict": "FAIL", "stop_reason": "schedule_exhausted", "safety_violations": 0,
                "candidate_identity": "cand0123456789ab", "battles_played": 0}

    monkeypatch.setattr(cr, "build_coverage_live_schedule", _fake_build)
    monkeypatch.setattr(cr, "run_coverage_gate", _fake_run)
    monkeypatch.setattr(cs, "verify_coverage_panel_and_teams", _fake_verify)


def test_command_locks_the_coverage_panel_derives_provenance_and_reaches_the_runner(tmp_path, monkeypatch):
    from showdown_bot import cli
    from showdown_bot.eval.coverage_schedule import COVERAGE_MANIFEST_PATH, COVERAGE_PANEL_PATH
    captured: dict = {}
    _install_cli_stubs(monkeypatch, captured)
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(tmp_path / "seed.log"))
    cli.run_coverage_gate_cli(argparse.Namespace(out_dir=str(tmp_path / "out"), teams_root="."))
    kw = captured["run_kwargs"]
    assert kw["expected_battles"] == 200                        # locked to the cap, not caller-set
    assert kw["seed_log_path"] == str(tmp_path / "seed.log")
    assert kw["out_dir"] == str(tmp_path / "out")
    assert kw["schedule"] is captured["built"]                  # BUILT from the LOCKED panel
    assert captured["panel_path"] == COVERAGE_PANEL_PATH        # the coverage panel, not caller-chosen
    assert captured["manifest_path"] == COVERAGE_MANIFEST_PATH
    assert captured["n_battles"] == 200
    assert captured["verified"] == (captured["built"], ".")     # panel+teams re-verified from disk


def test_the_command_takes_no_provenance_flags(tmp_path, monkeypatch):
    # provenance is DERIVED inside run_coverage_gate; the command never forwards git_sha/config_hash.
    from showdown_bot import cli
    captured: dict = {}
    _install_cli_stubs(monkeypatch, captured)
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(tmp_path / "seed.log"))
    cli.run_coverage_gate_cli(argparse.Namespace(out_dir=str(tmp_path / "out"), teams_root="."))
    kw = captured["run_kwargs"]
    assert not ({"git_sha", "config_hash", "candidate_identity"} & set(kw))


def test_command_requires_out_dir(tmp_path, monkeypatch):
    from showdown_bot import cli
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(tmp_path / "seed.log"))
    with pytest.raises(SystemExit, match="requires --out-dir"):
        cli.run_coverage_gate_cli(argparse.Namespace(out_dir="", teams_root="."))


def test_command_requires_the_server_seed_log(tmp_path, monkeypatch):
    from showdown_bot import cli
    captured: dict = {}
    _install_cli_stubs(monkeypatch, captured)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)
    with pytest.raises(SystemExit, match="requires SHOWDOWN_EVAL_SEED_LOG"):
        cli.run_coverage_gate_cli(argparse.Namespace(out_dir=str(tmp_path / "out"), teams_root="."))
    assert "run_kwargs" not in captured

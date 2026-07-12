import sys
import pytest

from showdown_bot import cli


def test_main_dispatches_plan_without_starting_battles(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(cli, "run_generalisation_plan", lambda args: called.update(out=args.out))
    monkeypatch.setattr(sys, "argv", ["showdown-bot", "generalisation-plan",
        "--analysis-policy", "p.yaml", "--team-catalog", "c.json", "--exposure", "e.json",
        "--generalisation-manifest", "m.yaml", "--panel", "panel.yaml", "--out", str(tmp_path)])
    cli.main()
    assert called["out"] == str(tmp_path)


def test_analyze_exit_one_for_inconclusive(monkeypatch):
    monkeypatch.setattr("showdown_bot.analysis.generalisation.runner.analyze_runs",
                        lambda **kwargs: {"status": "INCONCLUSIVE"})
    args = type("Args", (), {"analysis_policy": "p", "team_catalog": "c", "exposure": "e",
        "taxonomy": "t", "generalisation_manifest": "m", "panel": "panel", "schedule": "s",
        "run_a": "a", "seedlog_a": "sa", "room_raw_a": "ra", "manifest_a": None,
        "run_b": None, "seedlog_b": None, "room_raw_b": None, "manifest_b": None,
        "teams_root": ".", "out": "out", "overwrite": False})()
    with pytest.raises(SystemExit) as exc:
        cli.run_generalisation_analyze(args)
    assert exc.value.code == 1

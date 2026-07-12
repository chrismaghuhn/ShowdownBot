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


def test_single_run_analyze_forwards_empty_optional_args_as_none(monkeypatch):
    """Real argparse defaults the optional b-run + manifest args to "" (not None).
    run_generalisation_analyze must normalize them to None (the file's `or None`
    convention), else _analyze_runs' `if run_b is not None` wrongly enters the
    paired branch on a single-run analyze and raises an uncaught ValueError.
    Regression for the "" vs None sentinel crash (Task 10 review)."""
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return {"status": "DESCRIPTIVE_COMPLETE"}

    monkeypatch.setattr("showdown_bot.analysis.generalisation.runner.analyze_runs", _capture)
    args = type("Args", (), {"analysis_policy": "p", "team_catalog": "c", "exposure": "e",
        "taxonomy": "t", "generalisation_manifest": "m", "panel": "panel", "schedule": "s",
        "run_a": "a", "seedlog_a": "sa", "room_raw_a": "ra", "manifest_a": "",
        "run_b": "", "seedlog_b": "", "room_raw_b": "", "manifest_b": "",
        "teams_root": ".", "out": "out", "overwrite": False})()
    cli.run_generalisation_analyze(args)  # must NOT raise
    assert captured["run_b"] is None
    assert captured["seedlog_b"] is None
    assert captured["room_raw_b"] is None
    assert captured["run_manifest_a"] is None
    assert captured["run_manifest_b"] is None

import json
from pathlib import Path

from showdown_bot.analysis.generalisation.runner import analyze_runs


from .real_fixture import run_real_fixture


def test_paired_fixture_runs_end_to_end(tmp_path):
    report = run_real_fixture(tmp_path)
    assert report["status"] == "INCONCLUSIVE"
    assert report["side_capability"] == "NOT_EVALUABLE"
    assert len(report["coverage"]) == 15
    assert report["comparison"]["pairing_coverage"] == 1.0
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["status"] == "INCONCLUSIVE"


def test_all_artifacts_are_byte_identical(tmp_path):
    left, right = tmp_path / "left/report", tmp_path / "right/report"
    run_real_fixture(left)
    run_real_fixture(right)
    names = ("generalisation-manifest.json", "matchup-observations.jsonl",
             "coverage-matrix.csv", "cell-metrics.csv",
             "paired-deltas.csv", "findings.json", "report.json", "report.md")
    assert {name: (left / name).read_bytes() for name in names} == {
        name: (right / name).read_bytes() for name in names}

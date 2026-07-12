import json
import pytest

from showdown_bot.analysis.generalisation.reporting import (
    OutputError, write_analysis_outputs, write_fatal_report,
)


def test_outputs_are_complete_sorted_and_protected(tmp_path):
    observations = [{"config_hash": "z", "seed_index": 1, "battle_id": "b2", "cell_id": "c"},
                    {"config_hash": "a", "seed_index": 0, "battle_id": "b1", "cell_id": "c"}]
    report = {"status": "DESCRIPTIVE_COMPLETE", "analysis_id": "id", "findings": [],
              "generalisation_manifest": {"manifest_hash": "m", "cells": []},
              "coverage": [{"cell_id": "c", "n": 2}],
              "cells": [{"cell_id": "c", "n": 2, "win_rate": 0.5}], "paired": []}
    paths = write_analysis_outputs(tmp_path, report, observations)
    assert {path.name for path in paths} == {"generalisation-manifest.json",
        "matchup-observations.jsonl", "coverage-matrix.csv",
        "cell-metrics.csv", "paired-deltas.csv", "findings.json", "report.json", "report.md"}
    lines = (tmp_path / "matchup-observations.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["battle_id"] == "b1"
    with pytest.raises(OutputError, match="exists"):
        write_analysis_outputs(tmp_path, report, observations)


def test_fatal_report_contains_no_fake_metrics(tmp_path):
    report = write_fatal_report(tmp_path, ValueError("broken input"))
    assert report["status"] == "INVALID"
    assert "coverage" not in report and "cells" not in report

"""T3f Task 6: pin the decision-latency p95 budget as a config constant."""
from __future__ import annotations

import pytest

from showdown_bot.eval.gates import GatesConfigError, load_latency_budget_ms


def test_load_latency_budget_ms_from_repo_config():
    assert load_latency_budget_ms() == 1000  # default path = config/eval/gates.yaml


def test_load_latency_budget_ms_custom_value(tmp_path):
    p = tmp_path / "gates.yaml"
    p.write_text("decision_latency_p95_budget_ms: 2500\n", encoding="utf-8")
    assert load_latency_budget_ms(str(p)) == 2500


def test_load_latency_budget_ms_missing_file_raises(tmp_path):
    with pytest.raises(GatesConfigError):
        load_latency_budget_ms(str(tmp_path / "nope.yaml"))


def test_load_latency_budget_ms_missing_key_raises(tmp_path):
    p = tmp_path / "gates.yaml"
    p.write_text("something_else: 1\n", encoding="utf-8")
    with pytest.raises(GatesConfigError):
        load_latency_budget_ms(str(p))

from __future__ import annotations

import copy
import json

import pytest

from showdown_bot.eval.decision_diff import DecisionDiffError
from showdown_bot.eval.decision_diff_report import build_report_object, render_markdown


@pytest.fixture
def analysis_fixture():
    return {
        "capability_mode": "full",
        "provenance": {"baseline": {"config_hash": "a"},
                       "candidate": {"config_hash": "b"}},
        "integrity": {"paired_battles": 2, "directly_comparable_decisions": 3},
        "strength": {"n_discordant": 2, "exact_two_sided_p": 1.0},
        "outcomes": {"BOTH_WIN": 0, "BOTH_LOSS": 0,
                     "CANDIDATE_FLIP_TO_WIN": 1,
                     "CANDIDATE_REGRESSION_TO_LOSS": 1, "NON_BINARY": 0},
        "decision_differences": {"by_primary_class": {"ATTACK_TARGET": 2}},
        "matchup_buckets": [
            {"hero_archetype": "balance", "opponent_archetype": "rain",
             "opponent_policy": "max_damage", "lead": "A+B", "n": 2,
             "candidate_win_rate": 0.5, "underpowered": True},
        ],
        "stability": {"baseline": {"status": "not_provided"},
                      "candidate": {"status": "not_provided"}},
        "regressions": {"candidate_regression_to_loss": 1},
        "top_positive_associations": [{"primary": "ATTACK_TARGET", "associated_battles": 1}],
        "top_negative_associations": [{"primary": "ATTACK_TARGET", "associated_battles": 1}],
    }


def reversed_fixture(source):
    copy_ = copy.deepcopy(source)
    copy_["matchup_buckets"] = list(reversed(copy_["matchup_buckets"]))
    return copy_


def test_report_is_verdict_first_but_not_a_new_gate(analysis_fixture):
    obj = build_report_object(analysis_fixture)
    md = render_markdown(obj)
    assert obj["report_schema_version"] == "decision-diff-report-v1"
    assert obj["strength"]["source"] == "existing paired statistics"
    assert "new_strength_verdict" not in json.dumps(obj)
    assert md.startswith("# Candidate-vs-Baseline Differential Report\n")
    assert "## Existing paired strength evidence" in md
    assert "## First direct divergences" in md
    assert "## Regressions" in md
    assert "association, not causal proof" in md


def test_report_is_deterministic(analysis_fixture):
    first = render_markdown(build_report_object(analysis_fixture))
    second = render_markdown(build_report_object(reversed_fixture(analysis_fixture)))
    assert first == second


def test_report_rejects_non_finite_numbers(analysis_fixture):
    bad = copy.deepcopy(analysis_fixture)
    bad["strength"]["exact_two_sided_p"] = float("nan")
    with pytest.raises(DecisionDiffError):
        build_report_object(bad)

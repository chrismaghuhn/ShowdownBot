from __future__ import annotations

import pytest

from showdown_bot.eval.accuracy_baseline_diff import BaselineDiffResult, diff_against_baseline


def test_identical_rows_produce_zero_regressions():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.5000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.5000000000"},
    ]
    result = diff_against_baseline(baseline, replay)
    assert result.regressions == []
    assert result.matched == 1


def test_action_change_is_a_regression():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.5000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 2", "score": "1.5000000000"},
    ]
    result = diff_against_baseline(baseline, replay)
    assert len(result.regressions) == 1
    assert result.regressions[0].request_hash == "a"


def test_missing_row_in_replay_is_flagged_not_silently_dropped():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
        {"request_hash": "b", "log_prefix_hash": "p2", "chosen_action": "move 1", "score": "1.0000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
    ]
    result = diff_against_baseline(baseline, replay)
    assert result.missing_from_replay == ["b"]


def test_duplicate_request_hash_in_baseline_raises():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
        {"request_hash": "a", "log_prefix_hash": "p2", "chosen_action": "move 2", "score": "2.0000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
    ]
    with pytest.raises(ValueError, match="duplicate request_hash"):
        diff_against_baseline(baseline, replay)


def test_duplicate_request_hash_in_replay_raises():
    baseline = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
    ]
    replay = [
        {"request_hash": "a", "log_prefix_hash": "p1", "chosen_action": "move 1", "score": "1.0000000000"},
        {"request_hash": "a", "log_prefix_hash": "p2", "chosen_action": "move 2", "score": "2.0000000000"},
    ]
    with pytest.raises(ValueError, match="duplicate request_hash"):
        diff_against_baseline(baseline, replay)

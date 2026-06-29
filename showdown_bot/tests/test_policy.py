from __future__ import annotations

from showdown_bot.battle.policy import aggregate_scores, pick_best, tera_decision
from showdown_bot.engine.belief.game_mode import GameMode


def test_must_react_uses_min():
    assert aggregate_scores([5.0, -2.0, 3.0], GameMode.MUST_REACT) == -2.0


def test_ahead_uses_mean():
    assert aggregate_scores([4.0, 2.0], GameMode.AHEAD) == 3.0


def test_neutral_penalizes_variance():
    safe = aggregate_scores([3.0, 3.0], GameMode.NEUTRAL)
    risky = aggregate_scores([6.0, 0.0], GameMode.NEUTRAL)
    assert safe == 3.0
    assert risky < safe  # same mean, higher variance is penalized


def test_pick_best_must_react_prefers_safe_line():
    items = [
        ("risky", [10.0, -5.0]),  # min -5
        ("safe", [3.0, 2.0]),     # min 2
    ]
    key, val = pick_best(items, GameMode.MUST_REACT)
    assert key == "safe"
    assert val == 2.0


def test_pick_best_ahead_prefers_high_mean():
    items = [
        ("aggressive", [10.0, 6.0]),  # mean 8
        ("passive", [3.0, 3.0]),      # mean 3
    ]
    key, _ = pick_best(items, GameMode.AHEAD)
    assert key == "aggressive"


def test_tera_decision_margin():
    assert tera_decision(5.0, 5.5, margin=1.0) is False
    assert tera_decision(5.0, 7.0, margin=1.0) is True

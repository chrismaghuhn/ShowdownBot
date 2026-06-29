from __future__ import annotations

from statistics import mean

from showdown_bot.battle.policy import aggregate_scores, pick_best, tera_decision
from showdown_bot.engine.belief.game_mode import GameMode


def test_must_react_softens_worst_case():
    # No longer pure min (which turtled): worst-case-leaning but between min and mean.
    scores = [5.0, -2.0, 3.0]  # min -2.0, mean 2.0
    val = aggregate_scores(scores, GameMode.MUST_REACT)
    assert min(scores) < val < mean(scores)


def test_ahead_uses_mean():
    assert aggregate_scores([4.0, 2.0], GameMode.AHEAD) == 3.0


def test_neutral_penalizes_variance():
    safe = aggregate_scores([3.0, 3.0], GameMode.NEUTRAL)
    risky = aggregate_scores([6.0, 0.0], GameMode.NEUTRAL)
    assert safe == 3.0
    assert risky < safe  # same mean, higher variance is penalized


def test_pick_best_must_react_prefers_safe_line():
    # Risk-aversion still holds: the high-variance "risky" line is penalized and
    # the steady "safe" line wins -- just no longer by pure min.
    items = [
        ("risky", [10.0, -5.0]),  # huge downside
        ("safe", [3.0, 2.0]),     # steady
    ]
    key, _ = pick_best(items, GameMode.MUST_REACT)
    assert key == "safe"


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

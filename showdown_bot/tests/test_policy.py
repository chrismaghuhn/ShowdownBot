from __future__ import annotations

from statistics import mean, pvariance

import pytest

from showdown_bot.battle.policy import (
    _risk_lambda,
    aggregate_scores,
    cvar_lower,
    pick_best,
    risk_lambda,
    tera_decision,
)
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


# --- _risk_lambda: SHOWDOWN_RISK_LAMBDA env tunability (2c-1), mirrors _must_react_lambda -

def test_risk_lambda_defaults_to_half_when_unset(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_RISK_LAMBDA", raising=False)
    assert _risk_lambda() == 0.5


def test_risk_lambda_reads_env_float(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "0.1")
    assert _risk_lambda() == 0.1


def test_risk_lambda_clamps_above_one(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "5")
    assert _risk_lambda() == 1.0


def test_risk_lambda_clamps_below_zero(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "-3")
    assert _risk_lambda() == 0.0


def test_risk_lambda_falls_back_to_half_on_bad_value(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "abc")
    assert _risk_lambda() == 0.5


def test_risk_lambda_public_accessor_mirrors_private(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "0.3")
    assert risk_lambda() == _risk_lambda() == 0.3


# --- NEUTRAL CVaR operator toggle (2c-cvar): SHOWDOWN_NEUTRAL_CVAR / _ALPHA / _LAMBDA ---

def test_neutral_off_is_unchanged_variance(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_NEUTRAL_CVAR", raising=False)
    scores = [1.0, 2.0, 3.0, 4.0]
    expected = mean(scores) - 0.5 * pvariance(scores)
    assert aggregate_scores(scores, GameMode.NEUTRAL, risk_lambda=0.5) == pytest.approx(expected)


def test_neutral_on_uses_cvar_unweighted(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.setenv("SHOWDOWN_CVAR_ALPHA", "0.25")
    monkeypatch.setenv("SHOWDOWN_CVAR_LAMBDA", "0.5")
    scores = [1.0, 2.0, 3.0, 4.0]
    m = mean(scores)
    expected = m - 0.5 * (m - cvar_lower(scores, None, 0.25))
    assert aggregate_scores(scores, GameMode.NEUTRAL) == pytest.approx(expected)


def test_neutral_on_uses_cvar_weighted(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.setenv("SHOWDOWN_CVAR_ALPHA", "0.25")
    monkeypatch.setenv("SHOWDOWN_CVAR_LAMBDA", "0.5")
    scores = [1.0, 2.0, 3.0]
    weights = [0.1, 0.1, 0.8]
    wmean = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    expected = wmean - 0.5 * (wmean - cvar_lower(scores, weights, 0.25))
    assert aggregate_scores(scores, GameMode.NEUTRAL, weights=weights) == pytest.approx(expected)


def test_neutral_on_lambda_zero_is_pure_mean(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.setenv("SHOWDOWN_CVAR_LAMBDA", "0")
    scores = [1.0, 5.0, 9.0]
    assert aggregate_scores(scores, GameMode.NEUTRAL) == pytest.approx(mean(scores))


def test_must_react_unaffected_by_cvar_env(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    monkeypatch.delenv("SHOWDOWN_MUST_REACT_LAMBDA", raising=False)
    scores = [1.0, 2.0, 3.0, 4.0]
    expected = mean(scores) - 0.6 * (mean(scores) - min(scores))
    assert aggregate_scores(scores, GameMode.MUST_REACT) == pytest.approx(expected)


def test_ahead_unaffected_by_cvar_env(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_NEUTRAL_CVAR", "1")
    scores = [1.0, 2.0, 3.0, 4.0]
    assert aggregate_scores(scores, GameMode.AHEAD) == pytest.approx(mean(scores))

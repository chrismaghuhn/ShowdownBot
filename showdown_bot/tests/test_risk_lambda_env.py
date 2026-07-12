"""SHOWDOWN_RISK_LAMBDA env tunability (2c-1): the NEUTRAL-mode risk_lambda
aggregation knob (``policy.aggregate_scores`` / ``pick_best``), mirroring the
existing SHOWDOWN_MUST_REACT_LAMBDA pattern (``policy._must_react_lambda``), so it
can be A/B-tested at runtime with zero further code change.
"""
from __future__ import annotations

from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.decision_trace import DecisionTrace


def _agg_by_id(trace: DecisionTrace) -> dict[str, float]:
    return {c.candidate_id: c.aggregate_score for c in trace.candidates}


# --- byte-identical-off: env unset == explicit risk_lambda=0.5 (current default) --------


def test_byte_identical_risk_lambda_unset_vs_explicit_half(decision_fixture, monkeypatch):
    """CRITICAL invariant: with SHOWDOWN_RISK_LAMBDA unset, decision.py resolves
    risk_lambda to 0.5 -- identical to the pre-2c-1 hardcoded default -- so the
    dispatched decision (chosen action + score) is byte-identical to an explicit
    risk_lambda=0.5 call."""
    monkeypatch.delenv("SHOWDOWN_RISK_LAMBDA", raising=False)
    req, kw = decision_fixture

    ja_unset, val_unset = _choose_best(req, **kw)
    ja_explicit, val_explicit = _choose_best(req, risk_lambda=0.5, **kw)

    assert ja_unset.as_pair() == ja_explicit.as_pair()
    assert val_unset == val_explicit


def test_byte_identical_risk_lambda_env_set_to_half_vs_unset(decision_fixture, monkeypatch):
    """Explicitly setting SHOWDOWN_RISK_LAMBDA=0.5 (the default value) must also be
    byte-identical to leaving it unset."""
    req, kw = decision_fixture

    monkeypatch.delenv("SHOWDOWN_RISK_LAMBDA", raising=False)
    ja_unset, val_unset = _choose_best(req, **kw)

    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "0.5")
    ja_set, val_set = _choose_best(req, **kw)

    assert ja_unset.as_pair() == ja_set.as_pair()
    assert val_unset == val_set


# --- SHOWDOWN_RISK_LAMBDA actually changes the NEUTRAL-mode aggregate/pick --------------


def test_showdown_risk_lambda_changes_neutral_aggregate_and_pick(decision_fixture, monkeypatch):
    """SHOWDOWN_RISK_LAMBDA=1.0 fully penalizes variance in NEUTRAL mode: the
    fixture's high-variance (Protect, Protect) line loses its lead over the lower-
    variance Fake Out + Earth Power line, flipping the pick -- proof the env var
    reaches pick_best/aggregate_scores, not just a hardcoded default."""
    req, kw = decision_fixture

    monkeypatch.delenv("SHOWDOWN_RISK_LAMBDA", raising=False)
    tr_default = DecisionTrace()
    ja_default, _ = _choose_best(req, trace=tr_default, **kw)
    assert tr_default.game_mode == "NEUTRAL"  # test is only meaningful in NEUTRAL mode

    monkeypatch.setenv("SHOWDOWN_RISK_LAMBDA", "1.0")
    tr_high = DecisionTrace()
    ja_high, _ = _choose_best(req, trace=tr_high, **kw)

    assert ja_high.as_pair() != ja_default.as_pair()

    agg_default = _agg_by_id(tr_default)
    agg_high = _agg_by_id(tr_high)
    shared = set(agg_default) & set(agg_high)
    assert shared, "candidate sets should overlap -- same joint actions, different aggregation"
    assert any(agg_default[k] != agg_high[k] for k in shared)

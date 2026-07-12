from __future__ import annotations

import os
from statistics import mean, pvariance
from typing import TypeVar

from showdown_bot.engine.belief.game_mode import GameMode

K = TypeVar("K")


def _must_react_lambda() -> float:
    """How much MUST_REACT weights the worst case: 1.0 = pure min (old behavior,
    too passive), 0.0 = mean. Overridable via ``SHOWDOWN_MUST_REACT_LAMBDA`` for
    tuning. Default leans conservative but no longer turtles on the nightmare."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("SHOWDOWN_MUST_REACT_LAMBDA", "0.6"))))
    except ValueError:
        return 0.6


def _risk_lambda() -> float:
    """How much NEUTRAL (and weighted-AHEAD/NEUTRAL) aggregation penalizes
    variance: 1.0 = full variance penalty, 0.0 = pure mean (ignore variance).
    Overridable via ``SHOWDOWN_RISK_LAMBDA`` for tuning (mirrors
    ``_must_react_lambda`` exactly). Default 0.5 matches the historic hardcoded
    ``risk_lambda`` default used throughout ``aggregate_scores``/``pick_best``."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("SHOWDOWN_RISK_LAMBDA", "0.5"))))
    except ValueError:
        return 0.5


def risk_lambda() -> float:
    """Public accessor for the env-tunable NEUTRAL-mode risk_lambda default (see
    ``_risk_lambda``). Callers that want the current env-resolved value without
    reaching into the private helper should use this."""
    return _risk_lambda()


def aggregate_scores(
    scores: list[float],
    mode: GameMode,
    *,
    risk_lambda: float = 0.5,
    weights: list[float] | None = None,
) -> float:
    """Collapse the per-opponent-response scores of ONE of our actions into a
    single value, with a game_mode-dependent operator:

    - must_react -> mean - mr_lambda * (mean - min)  (worst-case-leaning, but not
                    pure min: pure min turtles into Protect and loses tempo)
    - ahead      -> mean  (we can afford the average line; protect reads net out)
    - neutral    -> mean - lambda * variance  (risk-averse: avoid high-variance lines)

    ``weights`` (opponent-response likelihoods from protect priors) turn the mean
    / variance into weighted versions for the ahead / neutral / must_react ops.
    """
    if not scores:
        return 0.0

    use_weights = weights is not None and len(weights) == len(scores) and sum(weights) > 0

    if mode == GameMode.MUST_REACT:
        worst = min(scores)
        if use_weights:
            wsum = sum(weights)
            avg = sum(s * w for s, w in zip(scores, weights)) / wsum
        else:
            avg = mean(scores)
        return avg - _must_react_lambda() * (avg - worst)

    if use_weights:
        wsum = sum(weights)
        wmean = sum(s * w for s, w in zip(scores, weights)) / wsum
        if mode == GameMode.AHEAD:
            return wmean
        wvar = sum(w * (s - wmean) ** 2 for s, w in zip(scores, weights)) / wsum
        return wmean - risk_lambda * wvar

    if mode == GameMode.AHEAD:
        return mean(scores)
    if len(scores) == 1:
        return scores[0]
    return mean(scores) - risk_lambda * pvariance(scores)


def pick_best(
    items: list[tuple[K, list[float]]],
    mode: GameMode,
    *,
    risk_lambda: float = 0.5,
    weights: list[float] | None = None,
) -> tuple[K, float]:
    """Argmax over our candidate actions of the aggregated score."""
    best_key: K | None = None
    best_val = float("-inf")
    for key, scores in items:
        val = aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=weights)
        if val > best_val:
            best_val = val
            best_key = key
    return best_key, best_val


def tera_decision(base_value: float, tera_value: float, *, margin: float = 1.0) -> bool:
    """Tera is a one-shot resource: only spend it when the Tera line beats the
    non-Tera line by more than ``margin`` (avoid burning Tera for chip)."""
    return tera_value - base_value > margin

"""Fixed-horizon counterfactual teacher (Phase 3, slice 1).

Return = incremental transition rewards + ONE bootstrap leaf, never evaluating the
same state twice. H = follow-up turns after the candidate turn (1 + H transitions).
"""

from __future__ import annotations

from dataclasses import dataclass

US = "us"
THEM = "them"


@dataclass
class RolloutConfig:
    H: int = 4          # heuristic follow-up turns after the fixed candidate turn
    gamma: float = 0.75
    top_k: int = 6
    use_leaf: bool = True


def _rollout_one(start_state, candidate, first_opp, *, decide, resolve, leaf, cfg) -> float:
    # transition 0: the fixed candidate + this opponent response (gamma^0 = 1)
    state, reward = resolve(start_state, candidate, first_opp)
    v = reward
    for t in range(1, cfg.H + 1):  # H follow-up turns, heuristic both sides
        state, reward = resolve(state, decide(state, US), decide(state, THEM))
        v += (cfg.gamma ** t) * reward
    if cfg.use_leaf:
        v += (cfg.gamma ** (cfg.H + 1)) * leaf(state)  # bootstrap, strictly after last transition
    return v


def counterfactual_value(start_state, candidate, responses, *, decide, resolve, leaf, cfg) -> float:
    """Weighted mean over the (candidate-independent) opponent response set.
    ``responses`` is a list of (opponent_action, weight); weights must be
    non-negative and sum to 1 — otherwise the label silently mis-normalizes."""
    if not responses:
        raise ValueError("responses must not be empty")
    total_w = 0.0
    for _, w in responses:
        if w < 0:
            raise ValueError("response weight must be non-negative")
        total_w += w
    if abs(total_w - 1.0) > 1e-6:
        raise ValueError("response weights must sum to 1")
    return sum(
        w * _rollout_one(start_state, candidate, opp, decide=decide, resolve=resolve, leaf=leaf, cfg=cfg)
        for opp, w in responses
    )

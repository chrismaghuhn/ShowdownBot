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

    def __post_init__(self):
        if self.H < 0:
            raise ValueError("H must be >= 0")
        if not (0.0 < self.gamma <= 1.0):
            raise ValueError("gamma must be in (0, 1]")
        if self.top_k <= 0:
            raise ValueError("top_k must be > 0")


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


def _ranks(values: dict) -> dict:
    """0 = best (highest value). Ties broken by candidate id for determinism."""
    order = sorted(values, key=lambda c: (-values[c], str(c)))
    return {c: i for i, c in enumerate(order)}


def label_decision(teacher_values: dict, heuristic_values: dict, heuristic_choice_id) -> dict:
    """Per-candidate labels, all within-decision. ``teacher_values`` and
    ``heuristic_values`` map candidate_id -> value over the SAME candidate set."""
    if not teacher_values:
        raise ValueError("teacher_values must not be empty")
    if set(teacher_values) != set(heuristic_values):
        raise ValueError("teacher and heuristic values must cover the same candidates")
    if heuristic_choice_id not in teacher_values:
        raise ValueError("heuristic_choice_id must be one of the candidates")
    mean = sum(teacher_values.values()) / len(teacher_values)
    best = max(teacher_values.values())
    t_rank = _ranks(teacher_values)
    h_rank = _ranks(heuristic_values)
    best_id = min(t_rank, key=t_rank.get)   # rank 0 — SAME tie-break as _ranks (no inconsistency)
    return {
        cid: {
            "counterfactual_value_raw": v,
            "counterfactual_value_normalized_within_decision": v - mean,
            "value_gap_to_best": v - best,
            "counterfactual_rank": t_rank[cid],
            "teacher_rank": t_rank[cid],
            "heuristic_rank": h_rank[cid],
            "teacher_best": cid == best_id,
            "chosen_by_current_heuristic": cid == heuristic_choice_id,
        }
        for cid, v in teacher_values.items()
    }

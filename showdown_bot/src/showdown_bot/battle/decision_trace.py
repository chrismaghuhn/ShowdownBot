"""Read-only decision artifacts for ML capture (Phase 3 slice 1b).

Plain DTOs only: no logic, no JSONL, no learning import. battle/ populates these;
learning/features.py reads them (learning -> battle, never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from showdown_bot.battle.evaluate import OutcomeBreakdown


@dataclass
class CandidateTrace:
    candidate_id: str
    joint_action: Any
    rank: int                                   # 0 = heuristic's top (by aggregate score)
    aggregate_score: float
    score_vector: list[float]                   # one score per opponent response (parallel to R)
    outcome_breakdowns: list[OutcomeBreakdown]  # parallel to opponent responses
    aggregate_breakdown: OutcomeBreakdown


@dataclass
class DecisionTrace:
    game_mode: str | None = None
    chosen_candidate_id: str | None = None
    opponent_responses: list[Any] = field(default_factory=list)
    opponent_response_weights: list[float] = field(default_factory=list)
    candidates: list[CandidateTrace] = field(default_factory=list)  # ONLY exported top-K, rank-sorted

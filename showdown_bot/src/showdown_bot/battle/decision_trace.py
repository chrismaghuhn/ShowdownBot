"""Read-only decision artifacts for ML capture (Phase 3 slice 1b).

Plain DTOs only: no logic, no JSONL, no learning import. battle/ populates these;
learning/features.py reads them (learning -> battle, never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from showdown_bot.battle.evaluate import OutcomeBreakdown


@dataclass
class DecisionTempoFeatures:
    we_outspeed_count: int = 0
    they_outspeed_count: int = 0
    speed_tie_count: int = 0
    our_fastest_active_speed: int = 0
    opp_fastest_active_speed: int = 0


@dataclass
class CandidateModelFeatures:
    """Per-candidate KO/survive counts for ML feature capture (1b-A).

    Decision-level fields (``ko_threatened_count``, ``survives_for_sure_count``)
    are identical across all candidates in a given decision — they reflect the
    position, not the specific move choice. ``ko_secured_count`` is candidate-
    specific: distinct opponent active slots guaranteed-OHKO'd by this candidate's
    selected damaging moves.
    """

    ko_secured_count: int = 0        # candidate-level: distinct opp slots we OHKO
    ko_threatened_count: int = 0     # decision-level: our mons threatened by opp
    survives_for_sure_count: int = 0  # decision-level: our mons safe from all known opp moves


@dataclass
class CandidateTrace:
    candidate_id: str
    joint_action: Any
    rank: int                                   # 0 = heuristic's top (by aggregate score)
    aggregate_score: float
    score_vector: list[float]                   # one score per opponent response (parallel to R)
    outcome_breakdowns: list[OutcomeBreakdown]  # parallel to opponent responses
    aggregate_breakdown: OutcomeBreakdown
    model_features: CandidateModelFeatures = field(default_factory=CandidateModelFeatures)


@dataclass
class DecisionTrace:
    game_mode: str | None = None
    chosen_candidate_id: str | None = None
    opponent_responses: list[Any] = field(default_factory=list)
    opponent_response_weights: list[float] = field(default_factory=list)
    candidates: list[CandidateTrace] = field(default_factory=list)  # ONLY exported top-K, rank-sorted
    tempo_features: DecisionTempoFeatures = field(default_factory=DecisionTempoFeatures)
    # Optional selection/fallback telemetry (candidate-vs-baseline diff slice,
    # Task 1). Pure side-effect fields set by decision.py / reranker_override.py
    # -- they record WHICH stage produced the chosen /choose string and, on a
    # fallback, WHY. Never read to make a decision; a decision-diff harness
    # reads them offline.
    selection_stage: str | None = None
    fallback_reason: str | None = None
    # Exact aggregation context used by policy.aggregate_scores at this decision
    # (research-only; never read to make a decision). Set by decision.py.
    aggregation_mode: str | None = None
    risk_lambda: float | None = None
    must_react_lambda: float | None = None

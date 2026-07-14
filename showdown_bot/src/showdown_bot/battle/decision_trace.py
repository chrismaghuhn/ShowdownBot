"""Read-only decision artifacts for ML capture (Phase 3 slice 1b).

Plain DTOs only: no logic, no JSONL, no learning import. battle/ populates these;
learning/features.py reads them (learning -> battle, never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from showdown_bot.battle.evaluate import OutcomeBreakdown
from showdown_bot.battle.resolve import SlotId


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
class AccuracyEventTrace:
    """One uncertain (accuracy < 100%) attempted hit surfaced from a single opponent
    response's accuracy-mode evaluation. ``response_index`` ties it back to the parallel
    ``score_vector``/``outcome_breakdowns`` position on the owning ``CandidateTrace`` --
    single-world only; in K-world sampling (``SHOWDOWN_WORLD_SAMPLES>1``) ``score_vector``
    is flattened across ALL sampled worlds, but ``response_index`` only indexes into the
    most-likely world's (``world_ctx[0]``, always present) response list -- see the world-0
    binding note in ``decision.py`` around the ``opp_resps = world_ctx[0][1]`` line."""

    attacker: SlotId
    target: SlotId
    move_id: str
    hit_probability: float
    response_index: int
    tie_order: str  # "ours_first" | "ours_last"


@dataclass
class AccuracyTieOrderTrace:
    """One evaluated tie ordering's accuracy-branching stats for a single opponent
    response. ``weight`` is 0.5 for both orderings on a genuine tie (``ours_first``
    and ``ours_last`` each contribute half the line's value) and 1.0 for the single
    ordering evaluated on a non-tie. ``accuracy_branch_cap_hits`` is THIS ordering's
    own ``fallback_leaves`` count (how many of its own resolve_turn_branches leaves
    hit the branch cap) -- not summed with the other ordering's."""

    tie_order: str
    weight: float
    accuracy_leaf_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool


@dataclass
class AccuracyResponseDetail:
    """Per-response accuracy telemetry (one per opponent response, parallel to
    ``CandidateTrace.score_vector``/``outcome_breakdowns`` -- single-world only; in
    K-world sampling (``SHOWDOWN_WORLD_SAMPLES>1``) ``score_vector`` is flattened across
    ALL sampled worlds, but this list (like ``outcome_breakdowns``) only covers the
    most-likely world (``world_ctx[0]``, always present) -- see the world-0 binding note
    in ``decision.py`` around the ``opp_resps = world_ctx[0][1]`` line). Research-only,
    mirrors ``battle.evaluate.LineEvaluation`` -- never read to make a decision.

    ``accuracy_leaf_count`` is a SUM across both evaluated tie orderings (a cost/effort
    metric -- total resolve-branch leaves evaluated across the ``ours_first``/
    ``ours_last`` trees when genuinely tied, or just the single tree's leaf count
    otherwise), NOT a distinct-outcome count. This is the OPPOSITE convention from its
    sibling ``accuracy_event_count``, which IS deduped/distinct across tie orderings
    (see ``evaluate._union_accuracy_events``). The per-ordering breakdown remains
    recoverable via ``tie_orders[i].accuracy_leaf_count``.
    """

    accuracy_leaf_count: int      # SUMMED across tie orderings -- cost metric, NOT distinct (see class docstring)
    accuracy_event_count: int     # deduped/distinct across tie orderings (see evaluate._union_accuracy_events)
    accuracy_branch_cap_hits: int
    events_complete: bool
    tie_orders: list[AccuracyTieOrderTrace] = field(default_factory=list)
    events: list[AccuracyEventTrace] = field(default_factory=list)


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
    accuracy_details: list[AccuracyResponseDetail] = field(default_factory=list)  # parallel to opponent responses; single-world only -- see AccuracyResponseDetail docstring for the K-world (world_ctx[0]) caveat
    candidate_key: str | None = None


@dataclass
class DecisionTrace:
    game_mode: str | None = None
    chosen_candidate_id: str | None = None
    chosen_candidate_key: str | None = None
    chosen_tera_slot: int | None = None
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

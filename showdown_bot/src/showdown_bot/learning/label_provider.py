"""LabelProvider seam: decouples extract_features from a specific labelling strategy.

Slice 1d-1: introduces the Protocol + StubLabelProvider + _validate_label_prefix.
Slice 1d-2: adds RolloutLabelProvider.
"""
from __future__ import annotations

from typing import Protocol

from showdown_bot.battle.candidate_identity import assert_unique_candidate_identities, candidate_identity
from showdown_bot.learning.schema import LABEL_KEYS


class LabelProvider(Protocol):
    def teacher_config(self) -> dict: ...
    def labels_for_decision(self, trace, state, request, *, context) -> dict: ...


def _validate_label_prefix(trace, labels: dict) -> None:
    """The labeled set must be exactly the first len(labels) candidates, in trace order.

    An EMPTY label dict for a non-empty trace is invalid — a 'no labels possible'
    situation must surface as RolloutLabelError on the rollout path, never as a silent
    0-row export.
    """
    assert_unique_candidate_identities(trace.candidates)
    if trace.candidates and not labels:
        raise ValueError("labels must not be empty for a non-empty trace")
    expected = [candidate_identity(c) for c in trace.candidates[: len(labels)]]
    if list(labels.keys()) != expected:
        raise ValueError("labels must be a candidate prefix in trace order")


class StubLabelProvider:
    def teacher_config(self) -> dict:
        return {"teacher_version": "stub-h0", "trainable_label": False}

    def labels_for_decision(self, trace, state, request, *, context) -> dict:
        zero = {k: 0 for k in LABEL_KEYS}
        assert_unique_candidate_identities(trace.candidates)
        return {candidate_identity(c): dict(zero) for c in trace.candidates}


class RolloutLabelProvider:
    """Real trainable labels via the 1c rollout_labels teacher.

    Builds a BeliefSide for both sides internally (our side from the request,
    opponent side from state + priors), then delegates to rollout_labels.

    On recoverable failure (RolloutLabelError from rollout_labels), the error
    propagates — the runtime catches it and skips the decision.  Integrity bugs
    (plain ValueError from weight mismatch / sum <= 0) also propagate and
    hard-fail the pipeline.

    Args:
        deps:         Decision deps dict (book, oracle, speed_oracle, etc.) —
                      assembled by the runtime, mirroring decision.py:182-186.
        likely_sets:  dict[species_id -> SpeciesSpreads] for speed oracle.
        move_priors:  dict[species_id -> list[str]] ordered move priors.
        cfg:          RolloutConfig (H, gamma, top_k, use_leaf).
        speed_oracle: SpeedOracle | None — forwarded to build_opponent_belief.
    """

    def __init__(self, *, deps: dict, likely_sets: dict, move_priors: dict, cfg,
                 speed_oracle=None):
        self._deps = deps
        self._likely_sets = likely_sets
        self._move_priors = move_priors
        self._cfg = cfg
        self._speed_oracle = speed_oracle

    def teacher_config(self) -> dict:
        return {
            "teacher_version": f"rollout-h{self._cfg.H}-v1",
            "trainable_label": True,
            "rollout_config": {
                "H": self._cfg.H,
                "gamma": self._cfg.gamma,
                "top_k": self._cfg.top_k,
                "use_leaf": self._cfg.use_leaf,
            },
        }

    def labels_for_decision(self, trace, state, request, *, context) -> dict:
        """Build belief for both sides and run rollout_labels.

        Returns:
            dict[candidate_id -> label dict] for the top-K candidates.

        Raises:
            RolloutLabelError: recoverable — no responses / all-switch / chosen not in set.
            ValueError:        integrity bug (weights) — propagates as hard-fail.
        """
        from showdown_bot.learning.rollout import rollout_labels
        from showdown_bot.learning.belief_builder import build_known_side, build_opponent_belief

        root = context.our_side
        opp = "p2" if root == "p1" else "p1"

        # Build beliefs: our side from the real request (fully known),
        # opponent from state + priors (active-only, limited-view-safe).
        us = build_known_side(request.side.pokemon)
        them = build_opponent_belief(
            state, opp,
            likely_sets=self._likely_sets,
            move_priors=self._move_priors,
            speed_oracle=self._speed_oracle,
        )

        roster = {root: us.roster, opp: them.roster}
        movesets = {root: us.movesets, opp: them.movesets}
        stats = {root: us.stats, opp: them.stats}

        return rollout_labels(
            trace, state,
            root_our_side=root,
            roster_by_side=roster,
            movesets_by_side=movesets,
            stats_by_side=stats,
            move_meta=self._deps.get("move_meta") or {},
            deps=self._deps,
            cfg=self._cfg,
        )
        # rollout_labels raises RolloutLabelError on recoverable failure — caller skips.

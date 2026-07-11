"""Slice 2b-4: fail-safe reranker-override choice core. Reuses the heuristic's
own decision trace (its top-K candidates) and the committed reranker model to
re-pick among them, INLINE and deterministically -- unlike ``reranker_shadow``'s
50ms-timeout, off-event-loop, log-only affordance, this scores synchronously on
the live decision path with NO wall-clock branch.

On ANY failure (schema/feature mismatch, predict error, an argmax candidate that
doesn't resolve to a legal ``choose`` string, empty candidates) this returns the
heuristic's OWN ``choose`` string unchanged -- it NEVER raises and is never
worse-behaved than the heuristic on the error path.

Not wired into the live agent dispatch (client/gauntlet.py) yet -- that is 2b-4
Task 2. This module is intentionally lightgbm-import-free: it is constructed
from an ALREADY-LOADED booster (the caller owns loading/from_env, mirroring
``RerankerShadowRuntime.from_env``), so it stays stub-booster-testable with no
lightgbm dependency in tests.
"""
from __future__ import annotations

import logging

from showdown_bot.battle.actions import JointAction
from showdown_bot.learning.reranker_shadow import score_candidates
from showdown_bot.protocol.encoder import encode_choose

logger = logging.getLogger(__name__)


def _fallback(trace, choose: str, reason: str) -> str:
    """Pure side-effect telemetry marker for a failsafe return: records that
    the FINAL choice is the heuristic's own (unchanged) and WHY the override
    declined it. No-op when ``trace`` is None. Never influences ``choose`` --
    it is returned exactly as passed in."""
    if trace is not None:
        trace.selection_stage = "heuristic"
        trace.fallback_reason = reason
    return choose


class RerankerOverride:
    """Constructed from an already-loaded ``booster`` + ``manifest`` (like
    ``RerankerShadowRuntime``, but scores INLINE on the live decision path --
    no executor, no timeout). ``format_id``/``dex``/``move_meta`` mirror the
    shadow's feature-context inputs so the override's features match the
    shadow's exactly (the ``2b2a_move_meta_none`` context mode unless real
    ``dex``/``move_meta`` are supplied -- Task 2 threads the client's decision
    deps through here)."""

    def __init__(self, *, booster, manifest, format_id: str, dex=None, move_meta=None):
        self.booster = booster
        self.manifest = manifest
        self.format_id = format_id
        self.dex = dex
        self.move_meta = move_meta
        self.feature_names = manifest.get("feature_names", [])
        self.categorical_feature_names = manifest.get("categorical_feature_names", [])
        # Checked ONCE at construction (deterministic, no wall clock) -- never
        # raises; any inconsistency just disables the override for its lifetime.
        self._schema_ok = self._check_schema()

    def _check_schema(self) -> bool:
        """INV-7-style self-consistency guard, mirroring
        ``RerankerShadowRuntime.from_env``'s load-time checks: the manifest's own
        ``feature_schema_hash`` must match its recomputed
        (feature_names, categorical_feature_names), and the booster's own
        feature order must match the manifest's ``feature_names``. Never raises
        -- any exception here just disables the override (fail-safe)."""
        try:
            from showdown_bot.learning.reranker_features import feature_schema_hash

            rt_hash = feature_schema_hash(self.feature_names, self.categorical_feature_names)
            if rt_hash != self.manifest.get("feature_schema_hash"):
                return False
            if list(self.booster.feature_name()) != list(self.feature_names):
                return False
            return True
        except Exception as exc:  # noqa: BLE001 - fail-safe
            logger.debug("reranker override: schema check failed, disabling: %s", exc)
            return False

    def override_choice(self, *, trace, state, request, heuristic_choose, our_side) -> str:
        """Score ``trace.candidates`` with the committed model, pick the argmax
        with an EXPLICIT stable tie-break (lowest candidate_index on equal
        score), and resolve that candidate's ``JointAction`` to a legal
        ``choose`` string via the SAME encoder the heuristic uses
        (``encode_choose``). Falls back to ``heuristic_choose`` UNCHANGED on ANY
        failure. NEVER raises -- this is the whole fail-safe contract."""
        try:
            if not self._schema_ok:
                return _fallback(trace, heuristic_choose, "reranker_schema_mismatch")
            candidates = trace.candidates
            scores = score_candidates(
                self.booster, self.manifest, trace=trace, state=state, request=request,
                our_side=our_side, format_id=self.format_id, dex=self.dex, move_meta=self.move_meta,
            )
            if not scores or len(scores) != len(candidates):
                return _fallback(trace, heuristic_choose, "reranker_empty_or_misaligned_scores")

            # Explicit stable tie-break: strict '>' only replaces the current
            # best on a STRICTLY higher score, so the FIRST (lowest-index)
            # candidate among equal top scores always wins -- deterministic
            # across calls, no reliance on Python's max()/sort() tie behavior.
            best_index = 0
            best_score = scores[0]
            for i in range(1, len(scores)):
                if scores[i] > best_score:
                    best_score = scores[i]
                    best_index = i

            joint_action = candidates[best_index].joint_action
            if not isinstance(joint_action, JointAction):
                return _fallback(trace, heuristic_choose, "reranker_non_joint_action")
            choose = encode_choose(joint_action.as_pair(), rqid=request.rqid)
            if not choose:
                return _fallback(trace, heuristic_choose, "reranker_empty_choose")
            if trace is not None:
                trace.selection_stage = "reranker_override"
                trace.fallback_reason = None
            return choose
        except Exception as exc:  # noqa: BLE001 - fail-safe, NEVER raises to the caller
            logger.debug("reranker override: fail-safe to heuristic choose: %s", exc)
            return _fallback(trace, heuristic_choose, "reranker_exception")

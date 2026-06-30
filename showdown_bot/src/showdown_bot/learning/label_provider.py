"""LabelProvider seam: decouples extract_features from a specific labelling strategy.

Slice 1d-1: introduces the Protocol + StubLabelProvider + _validate_label_prefix.
Slice 1d-2: adds RolloutLabelProvider.
"""
from __future__ import annotations

from typing import Protocol

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
    if trace.candidates and not labels:
        raise ValueError("labels must not be empty for a non-empty trace")
    expected = [c.candidate_id for c in trace.candidates[: len(labels)]]
    if list(labels.keys()) != expected:
        raise ValueError("labels must be a candidate prefix in trace order")


class StubLabelProvider:
    def teacher_config(self) -> dict:
        return {"teacher_version": "stub-h0", "trainable_label": False}

    def labels_for_decision(self, trace, state, request, *, context) -> dict:
        zero = {k: 0 for k in LABEL_KEYS}
        return {c.candidate_id: dict(zero) for c in trace.candidates}

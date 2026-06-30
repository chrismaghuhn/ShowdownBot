"""Sampling-gated bridge: a populated DecisionTrace -> schema Rows -> exporter.add.

Keeps the DatasetExporter dumb (it only ever sees finished Rows) and battle/ free of
export logic. The client calls this once per decision.
"""

from __future__ import annotations

from showdown_bot.learning.features import extract_features
from showdown_bot.learning.label_provider import StubLabelProvider


def maybe_observe_decision(exporter, decision_index: int, *, ctx, trace, state, request) -> int:
    """If the exporter's SamplingPolicy includes ``decision_index``, extract one Row
    per candidate and add them (each validated by ``exporter.add``). Returns the row
    count (0 if the decision is not sampled — ``extract_features`` is then NOT called).

    Labels are built via StubLabelProvider for now; slice 1d-3 wires in the real provider.
    """
    if not exporter.sampling_policy.should_sample(decision_index):
        return 0
    labels = StubLabelProvider().labels_for_decision(trace, state, request, context=ctx)
    rows = extract_features(trace, state, request, ctx, labels=labels)
    for row in rows:
        exporter.add(row)
    return len(rows)

"""Label-aware bridge: populated DecisionTrace + pre-computed labels -> schema Rows -> exporter.add.

Keeps the DatasetExporter dumb (it only ever sees finished Rows) and battle/ free of
export logic. The sampling gate is owned by the caller (DatasetExportRuntime.observe);
the driver only validates + extracts + adds.
"""

from __future__ import annotations

from showdown_bot.learning.features import extract_features


def maybe_observe_decision(exporter, *, ctx, trace, state, request, labels) -> int:
    """Extract one Row per labeled candidate and add them (each validated by ``exporter.add``).

    Returns the row count (> 0 unless the trace has no candidates / all were filtered
    out by the label prefix).

    The sampling gate is NOT here — the runtime (DatasetExportRuntime.observe) calls
    ``exporter.sampling_policy.should_sample`` before invoking this function.  The
    driver simply extracts features and persists rows.

    Args:
        exporter: DatasetExporter receiving rows.
        ctx:      FeatureContext for this decision.
        trace:    Populated DecisionTrace from the heuristic.
        state:    BattleState at decision time.
        request:  BattleRequest at decision time.
        labels:   dict[candidate_id -> label dict] — pre-computed by the provider.
    """
    rows = extract_features(trace, state, request, ctx, labels=labels)
    for row in rows:
        exporter.add(row)
    return len(rows)

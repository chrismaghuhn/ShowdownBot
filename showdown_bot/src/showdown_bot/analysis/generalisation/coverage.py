# src/showdown_bot/analysis/generalisation/coverage.py
from __future__ import annotations

from collections import defaultdict
import json


def coverage_matrix(manifest, observations, policy):
    grouped = defaultdict(list)
    for observation in observations:
        grouped[observation.cell_id].append(observation)
    rows = []
    for cell in sorted(manifest.cells, key=lambda item: item.cell_id):
        values = grouped.get(cell.cell_id, [])
        seeds = {value.seed for value in values}
        n = len(seeds)
        rows.append({
            "cell_id": cell.cell_id, "protected": cell.protected,
            "required_unique_seeds": cell.required_unique_seeds, "n": n,
            "rows": len(values), "complete": n >= cell.required_unique_seeds,
            "underpowered": n < policy.descriptive_min_unique_seeds_per_cell,
            "gate_eligible": n >= policy.gate_min_unique_seeds_per_cell,
            "normal": sum(v.end_reason == "normal" for v in values),
            "ties": sum(v.winner == "tie" for v in values),
            "diagnostic_coverage": {
                "hero_lead": sum(v.hero_lead != "unavailable" for v in values),
                "opponent_lead": sum(v.opponent_lead != "unavailable" for v in values),
                "hero_side": sum(v.hero_side in {"p1", "p2"} for v in values),
            },
        })
    return rows

from __future__ import annotations

from collections import defaultdict
import random
from statistics import mean

from showdown_bot.eval.stats import exact_binom_two_sided_p


def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda index: p_values[index])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    total = len(p_values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (total - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def _percentile(values, probability):
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _bootstrap_macro(grouped, policy):
    rng = random.Random(policy.bootstrap_seed)
    values = []
    for _ in range(policy.bootstrap_replicates):
        deltas = []
        for cell_id in sorted(grouped):
            pairs = grouped[cell_id]
            sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
            deltas.append(mean(candidate - baseline for baseline, candidate in sample))
        values.append(mean(deltas))
    tail = (1.0 - policy.confidence_level) / 2.0
    return _percentile(values, tail), _percentile(values, 1.0 - tail)


def _bootstrap_cell(pairs, policy, cell_id):
    rng = random.Random(f"{policy.bootstrap_seed}:{cell_id}")
    values = []
    for _ in range(policy.bootstrap_replicates):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        values.append(mean(candidate - baseline for baseline, candidate in sample))
    tail = (1.0 - policy.confidence_level) / 2.0
    return _percentile(values, tail), _percentile(values, 1.0 - tail)


def compare_observation_pairs(baseline, candidate, policy):
    baseline_configs = {value.config_hash for value in baseline}
    candidate_configs = {value.config_hash for value in candidate}
    if len(baseline_configs) != 1 or len(candidate_configs) != 1 \
            or baseline_configs == candidate_configs:
        return {"status": "INVALID", "reason": "config hashes are not distinct constants",
                "cells": []}
    by_baseline = {value.battle_id: value for value in baseline}
    by_candidate = {value.battle_id: value for value in candidate}
    if set(by_baseline) != set(by_candidate) or len(by_baseline) != len(baseline) \
            or len(by_candidate) != len(candidate):
        return {"status": "INVALID", "reason": "pairing incomplete", "cells": []}
    grouped = defaultdict(list)
    transitions = defaultdict(lambda: defaultdict(int))
    for battle_id in sorted(by_baseline):
        left, right = by_baseline[battle_id], by_candidate[battle_id]
        if left.cell_id != right.cell_id or left.seed != right.seed:
            return {"status": "INVALID", "reason": "paired metadata mismatch", "cells": []}
        grouped[left.cell_id].append((int(left.hero_win), int(right.hero_win)))
        transitions[left.cell_id][(left.winner, right.winner)] += 1
    raw = []
    for cell_id in sorted(grouped):
        pairs = grouped[cell_id]
        baseline_only = sum(left == 1 and right == 0 for left, right in pairs)
        candidate_only = sum(left == 0 and right == 1 for left, right in pairs)
        discordant = baseline_only + candidate_only
        p_value = exact_binom_two_sided_p(min(baseline_only, candidate_only), discordant) \
            if discordant else 1.0
        raw.append({"cell_id": cell_id, "n_pairs": len(pairs),
                    "baseline_only_wins": baseline_only, "candidate_only_wins": candidate_only,
                    "delta": (candidate_only - baseline_only) / len(pairs), "p_value": p_value,
                    "transitions": {f"{a}->{b}": count
                                    for (a, b), count in sorted(transitions[cell_id].items())}})
    adjusted = holm_adjust([cell["p_value"] for cell in raw])
    for cell, value in zip(raw, adjusted):
        cell["bootstrap_lo"], cell["bootstrap_hi"] = _bootstrap_cell(
            grouped[cell["cell_id"]], policy, cell["cell_id"])
        cell["p_adjusted"] = value
        cell["gate_eligible"] = cell["n_pairs"] >= policy.gate_min_unique_seeds_per_cell
        cell["regression"] = (cell["gate_eligible"]
                              and cell["delta"] < -policy.regression_margin
                              and value < policy.alpha
                              and cell["bootstrap_hi"] < -policy.regression_margin)
    macro_delta = mean(cell["delta"] for cell in raw) if raw else None
    ci_lo, ci_hi = _bootstrap_macro(grouped, policy) if grouped else (None, None)
    complete = all(cell["gate_eligible"] for cell in raw)
    if not complete:
        status = "INCONCLUSIVE"
    elif any(cell["regression"] for cell in raw):
        status = "REGRESSION"
    elif ci_lo is not None and ci_lo > policy.improvement_margin:
        status = "IMPROVEMENT"
    else:
        status = "NO_CLEAR_CHANGE"
    return {"status": status, "cells": raw, "macro_delta": macro_delta,
            "macro_ci_lo": ci_lo, "macro_ci_hi": ci_hi, "pairing_coverage": 1.0}

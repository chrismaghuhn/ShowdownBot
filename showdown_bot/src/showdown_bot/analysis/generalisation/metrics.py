from __future__ import annotations

from collections import defaultdict
import json
from statistics import mean, median, quantiles

from showdown_bot.analysis.generalisation.coverage import coverage_matrix
from showdown_bot.eval.stats import wilson_interval


def _rate(wins, n):
    return None if n == 0 else wins / n


def _cell(cell_id, observations, policy):
    values = list(observations)
    n = len(values)
    wins = sum(value.hero_win for value in values)
    ties = sum(value.winner == "tie" for value in values)
    losses = n - wins - ties
    interval = (None, None) if n == 0 else wilson_interval(wins, n)
    hp = [value.end_hp_diff for value in values if value.end_hp_diff is not None]
    turns = [value.turns for value in values]
    turn_q = quantiles(turns, n=4, method="inclusive") if len(turns) >= 2 else [turns[0], turns[0], turns[0]] if turns else [None, None, None]
    return {"cell_id": cell_id, "n": n, "wins": wins, "losses": losses, "ties": ties,
            "win_rate": _rate(wins, n),
            "draw_aware_score": None if n == 0 else (wins + 0.5 * ties) / n,
            "wilson_lo": interval[0], "wilson_hi": interval[1],
            "gate_eligible": n >= policy.gate_min_unique_seeds_per_cell,
            "end_hp_mean": mean(hp) if hp else None, "end_hp_median": median(hp) if hp else None,
            "turns_mean": mean(turns) if turns else None,
            "turns_median": median(turns) if turns else None,
            "turns_q25": turn_q[0], "turns_q75": turn_q[2]}


def cell_metrics(manifest, observations, policy):
    grouped = defaultdict(list)
    for observation in observations:
        grouped[observation.cell_id].append(observation)
    return [_cell(cell.cell_id, grouped.get(cell.cell_id, []), policy)
            for cell in sorted(manifest.cells, key=lambda item: item.cell_id)]


def diagnostic_slices(observations, policy):
    fields = ("hero_lead", "opponent_lead", "hero_side", "hero_static_speed_control",
              "opponent_static_speed_control", "hero_activated_speed_control",
              "opponent_activated_speed_control")
    rows = []
    for field in fields:
        grouped = defaultdict(list)
        for observation in observations:
            value = getattr(observation, field)
            key = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
            grouped[key].append(observation)
        for key in sorted(grouped):
            values = grouped[key]
            wins = sum(value.hero_win for value in values)
            rows.append({"dimension": field, "value": key, "n": len(values),
                         "win_rate": wins / len(values),
                         "underpowered": len(values) < policy.descriptive_min_unique_seeds_per_cell})
    return rows


def single_run_summary(manifest, observations, policy):
    planned_ids = {cell.cell_id for cell in manifest.cells}
    all_observations = list(observations)
    observations = [value for value in all_observations if value.cell_id in planned_ids]
    unplanned = [value for value in all_observations if value.cell_id not in planned_ids]
    cells = cell_metrics(manifest, observations, policy)
    wins = sum(value.hero_win for value in observations)
    ties = sum(value.winner == "tie" for value in observations)
    n = len(observations)
    eligible = [cell for cell in cells if cell["gate_eligible"]]
    macro = mean(cell["win_rate"] for cell in eligible) if eligible else None
    worst = min(eligible, key=lambda cell: (cell["win_rate"], cell["wilson_lo"], cell["cell_id"])) if eligible else None
    archetype_by_cell = {value.cell_id: value.opponent_archetype for value in observations}
    archetype_cells = defaultdict(list)
    for cell in eligible:
        archetype_cells[archetype_by_cell[cell["cell_id"]]].append(cell["win_rate"])
    archetypes = [{"archetype": name, "cell_count": len(values), "win_rate": mean(values)}
                  for name, values in sorted(archetype_cells.items())]
    archetype_macro = mean(row["win_rate"] for row in archetypes) if archetypes else None
    worst_archetype = min(archetypes, key=lambda row: (row["win_rate"], row["archetype"])) \
        if archetypes else None
    leave_one_out = []
    for omitted in eligible:
        retained = [cell["win_rate"] for cell in eligible if cell["cell_id"] != omitted["cell_id"]]
        leave_one_out.append({"omitted_cell_id": omitted["cell_id"],
                              "macro_win_rate": mean(retained) if retained else None})
    coverage = coverage_matrix(manifest, observations, policy)
    complete = all(row["complete"] and row["gate_eligible"] for row in coverage if row["protected"])
    return {"coverage": coverage, "cells": cells, "unplanned_count": len(unplanned),
            "micro": {"n": n, "wins": wins, "ties": ties, "losses": n - wins - ties,
                      "win_rate": _rate(wins, n),
                      "draw_aware_score": None if n == 0 else (wins + 0.5 * ties) / n},
            "macro": {"win_rate": macro, "archetype_equal_win_rate": archetype_macro,
                      "complete": complete, "cell_count": len(eligible)},
            "worst_cell": worst,
            "archetypes": archetypes, "worst_archetype": worst_archetype,
            "stability": {"leave_one_cell_out": leave_one_out},
            "diagnostic_slices": diagnostic_slices(observations, policy),
            "robustness_gap": None if macro is None or worst is None else macro - worst["win_rate"]}

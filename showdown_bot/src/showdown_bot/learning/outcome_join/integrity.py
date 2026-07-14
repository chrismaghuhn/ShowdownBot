from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateResult:
    passed: bool
    coverage_ok: bool
    turn_violations: int
    examples: tuple[str, ...] = ()


def check_group(group, mapping, results_by_seed) -> GateResult:
    """Layer 1: mapping bijectively covers the group's game_ids.
    Layer 2: per game, max turn_number <= results.turns of its seed."""
    coverage_ok = (mapping is not None
                   and frozenset(mapping.game_to_seed) == group.game_ids
                   and len(mapping.game_to_seed) == len(group.game_ids))
    if not coverage_ok:
        return GateResult(False, False, 0)
    violations = []
    for game_id, seed in sorted(mapping.game_to_seed.items()):
        row = results_by_seed.get(seed)
        if row is None:
            violations.append(f"{game_id}:no-result")
            continue
        if group.max_turn_by_game[game_id] > int(row["turns"]):
            violations.append(f"{game_id}:turn>{row['turns']}")
    return GateResult(passed=not violations, coverage_ok=True,
                      turn_violations=len(violations), examples=tuple(violations[:20]))

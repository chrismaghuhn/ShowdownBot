"""Task 3: validated per-cell coverage counts over a v3 live decision-profile dataset.

``coverage_cell_counts`` validates the dataset FIRST (malformed or mixed-version data raises
``DecisionProfileError`` and nothing is counted), then tallies the four opponent-Mega coverage
cells over ``is_active_valid_live_row`` rows only. The safety signal is NOT in this dataset -- it is
server-authoritative (Task 6).
"""
from __future__ import annotations

from showdown_bot.eval.decision_profile import (
    _read_rows,
    is_active_valid_live_row,
    validate_live_profile_dataset,
)

COVERAGE_CELLS = ("slot0", "slot1", "both_foe_slots", "order_tie")


def _row_cells(row: dict) -> list[str]:
    """The coverage cells a single active-valid v3 row credits (spec §2.1)."""
    slots = set(row["foe_mega_slots"])
    cells: list[str] = []
    if 0 in slots:
        cells.append("slot0")
    if 1 in slots:
        cells.append("slot1")
    if {0, 1} <= slots:
        cells.append("both_foe_slots")
    if row["foe_mega_order_tie"] is True:
        cells.append("order_tie")
    return cells


def coverage_cell_counts(path: str) -> dict[str, dict[str, int]]:
    """Validate the live dataset, then count each coverage cell's decisions and distinct battles.

    Returns ``{cell: {"decisions": int, "distinct_battles": int}}`` for the four cells. Counting is
    over ``is_active_valid_live_row`` rows only (live, agent_choose, ``outcome=='ok'``, foe-Mega
    active); a malformed or mixed-version file fails closed via ``validate_live_profile_dataset``.
    """
    validate_live_profile_dataset(path)  # fail closed on malformed / mixed-version data
    decisions = {cell: 0 for cell in COVERAGE_CELLS}
    battles: dict[str, set[str]] = {cell: set() for cell in COVERAGE_CELLS}
    for row in _read_rows(path):
        if not is_active_valid_live_row(row):
            continue
        for cell in _row_cells(row):
            decisions[cell] += 1
            battles[cell].add(row["battle_id"])
    return {
        cell: {"decisions": decisions[cell], "distinct_battles": len(battles[cell])}
        for cell in COVERAGE_CELLS
    }

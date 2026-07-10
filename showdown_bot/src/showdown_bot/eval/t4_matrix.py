"""T4 smoke-schedule matrix (2b-3.5 T4): the pinned 51-game weighted dev matrix.

Weights per the accepted design (docs/superpowers/reviews/2026-07-02-fable-t4-smoke-schedule-
design.md §2-3): heuristic and max_damage are the only informative opponents (5 seeds/cell);
the three weak policies are calibration rungs (3/2/2). Rows 0-9 form a stratified reproduction
prefix (all 5 policies + all 3 dev teams), so a fresh-server re-run of just the prefix schedule
with the same seed_base reproduces exactly those battles (seed_i depends only on
(seed_base, seed_index)).
"""
from __future__ import annotations

from showdown_bot.eval.panel_schedule import generate_dev_schedule, prefix_schedule

T4_SEEDS_PER_CELL = {
    "heuristic": 5,
    "max_damage": 5,
    "simple_heuristic": 3,
    "greedy_protect": 2,
    "scripted_vgc": 2,
}
T4_POLICIES = list(T4_SEEDS_PER_CELL)  # insertion order == canonical remainder policy order

# (opp_policy, team_id) picks for seed_index 0..9 — all 5 policies + all 3 dev teams;
# the extra 10th pick goes to the most informative cell.
T4_PREFIX_CELLS = [
    ("heuristic", "trickroom"), ("heuristic", "sun"), ("heuristic", "rain"),
    ("max_damage", "trickroom"), ("max_damage", "sun"), ("max_damage", "rain"),
    ("simple_heuristic", "trickroom"), ("greedy_protect", "sun"), ("scripted_vgc", "rain"),
    ("heuristic", "trickroom"),
]
T4_PREFIX_LEN = len(T4_PREFIX_CELLS)


def generate_t4_schedules(panel, *, teams_root="."):
    """(full 51-row schedule, 10-row reproduction-prefix schedule) for the T4 smoke."""
    full = generate_dev_schedule(
        panel, policies=T4_POLICIES, seeds_per_cell=T4_SEEDS_PER_CELL,
        prefix_cells=T4_PREFIX_CELLS, teams_root=teams_root,
    )
    return full, prefix_schedule(full, T4_PREFIX_LEN)

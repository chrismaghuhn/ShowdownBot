"""T6 held-out baseline schedule (2b-3.5 T6 Task 4): the pinned 34-game weighted held-out
matrix -- the SAME per-policy seed weights as the T4 dev matrix (``eval.t4_matrix``),
applied to the panel's held-out teams (panel v001: ``balance``, ``tailwind``) instead of
its dev teams. 2 held-out teams x 17 seeds/team (5 heuristic + 5 max_damage +
3 simple_heuristic + 2 greedy_protect + 2 scripted_vgc) = 34 rows. T4 Task 1 built the
``seeds_per_cell`` mapping into ``panel_schedule._build``, shared transparently by
``generate_dev_schedule`` and ``generate_heldout_schedule`` -- reusing
``T4_POLICIES``/``T4_SEEDS_PER_CELL`` here composes for free, no re-derivation.

``T6_HELDOUT_PURPOSE`` is the ledger ``purpose`` string for every held-out access this
schedule produces: the ``schedule`` entry appended at generation time (when a real
``ledger_path`` is given -- this is what BIRTHS ``config/eval/heldout_ledger.jsonl``, its
first-ever entry), and later the ``run`` entry appended after the baseline held-out run
itself (T6 Task 5, spec §3).
"""
from __future__ import annotations

from showdown_bot.eval.panel_schedule import generate_heldout_schedule
from showdown_bot.eval.t4_matrix import T4_POLICIES, T4_SEEDS_PER_CELL

T6_HELDOUT_PURPOSE = "baseline-heldout-v1"


def generate_t6_heldout_schedule(panel, *, teams_root=".", ledger_path=None):
    """The 34-row held-out baseline schedule (2 held-out teams x the T4 policy/seed matrix).

    ``confirm_heldout=True`` is always passed -- this function IS the sanctioned held-out
    access point for the baseline; the T3-CC-1 guard on ``generate_heldout_schedule`` still
    protects any other, unintended caller. When ``ledger_path`` is given, one ``schedule``
    entry is appended to that ledger with ``purpose=T6_HELDOUT_PURPOSE`` (``ledger_path=None``,
    the default, stays pure -- no ledger write, matching ``generate_heldout_schedule``'s own
    default behavior; ``purpose`` is simply unused in that case).
    """
    return generate_heldout_schedule(
        panel, confirm_heldout=True, policies=T4_POLICIES, seeds_per_cell=T4_SEEDS_PER_CELL,
        teams_root=teams_root, ledger_path=ledger_path, purpose=T6_HELDOUT_PURPOSE,
    )

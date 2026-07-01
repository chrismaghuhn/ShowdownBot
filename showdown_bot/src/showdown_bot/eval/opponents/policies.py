"""Eval-only opponent policies: greedy_protect + simple_heuristic (T3c).

Deterministic, request-only (no calc/rollout). Both take ``(req, **_ignored)`` so the eval
dispatch can call them with the same kwargs as the other agents.
"""
from __future__ import annotations

from showdown_bot.eval.opponents._common import PROTECT_IDS, pick_best_pair


def _greedy_protect_slot(meta, action) -> float:
    if meta is None:
        return -1.0  # discourage switch/pass
    if meta.id in PROTECT_IDS:
        return 1000.0  # Protect when available...
    return float(meta.base_power) if meta.is_damaging else 0.0  # ...else the max-damage move


def greedy_protect_choice(req, **_ignored) -> str:
    """Protect on each slot when a Protect-move is available, else the highest-power attack."""
    return pick_best_pair(req, _greedy_protect_slot)


def _simple_heuristic_slot(meta, action) -> float:
    if meta is None:
        return -1.0
    return float(meta.base_power) if meta.is_damaging else 0.0


def simple_heuristic_choice(req, **_ignored) -> str:
    """Highest-base-power damaging move per slot — a power-greedy heuristic, no calc/search."""
    return pick_best_pair(req, _simple_heuristic_slot)

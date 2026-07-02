"""Eval-only opponent policies: greedy_protect + simple_heuristic (T3c).

Deterministic, request-only (no calc/rollout). Both take ``(req, **_ignored)`` so the eval
dispatch can call them with the same kwargs as the other agents. ``simple_heuristic`` also
accepts ``state``/``our_side`` (T3e Task 1) to score damage type-aware when the opposing
active typing is known; without them it degrades to the original base-power behavior.
"""
from __future__ import annotations

from showdown_bot.eval.opponents._common import PROTECT_IDS, pick_best_pair
from showdown_bot.engine.typechart import effectiveness


def _greedy_protect_slot(meta, action) -> float:
    if meta is None:
        return -1.0  # discourage switch/pass
    if meta.id in PROTECT_IDS:
        return 1000.0  # Protect when available...
    return float(meta.base_power) if meta.is_damaging else 0.0  # ...else the max-damage move


def greedy_protect_choice(req, **_ignored) -> str:
    """Protect on each slot when a Protect-move is available, else the highest-power attack."""
    return pick_best_pair(req, _greedy_protect_slot)


def target_types_for_action(meta, action, state, our_side) -> list[tuple[str, ...]]:
    """Defender type-tuples for the opposing active mon(s) a move would hit.

    ``meta`` is needed to tell a spread move (hits BOTH foes) from a single-target one
    (hits the slot named by ``action.target``: 1 -> opp "a", 2 -> opp "b", matching
    ``decision._map_target``). Only foes with KNOWN, non-empty types are returned, so any
    unknown situation — no ``state``, no ``our_side``, non-move action, unknown/no foe
    target, or empty typing — yields ``[]`` and the caller falls back to neutral (1.0).
    """
    if state is None or not our_side or meta is None:
        return []
    if action is None or action.kind != "move":
        return []
    opp_side = "p2" if our_side == "p1" else "p1"
    if meta.is_spread:
        slots = ["a", "b"]
    elif action.target == 1:
        slots = ["a"]
    elif action.target == 2:
        slots = ["b"]
    else:
        slots = []  # None / self / ally / unknown -> no explicit foe target
    out: list[tuple[str, ...]] = []
    for slot in slots:
        mon = state.active(opp_side, slot)
        if mon is not None and mon.types:
            out.append(tuple(mon.types))
    return out


def _simple_heuristic_slot(meta, action, *, state, our_side) -> float:
    if meta is None:
        return -1.0
    if not meta.is_damaging:
        return 0.0
    base_power = float(meta.base_power)
    # move_type may be None for an unknown move -> keep base-power behavior (neutral).
    types_list = target_types_for_action(meta, action, state, our_side)
    if not types_list or meta.move_type is None:
        return base_power
    eff = max(effectiveness(meta.move_type, list(t)) for t in types_list)
    return base_power * eff


def simple_heuristic_choice(req, *, state=None, our_side=None, **_ignored) -> str:
    """Highest-scoring damaging move per slot — power-greedy, no calc/search.

    When ``state``/``our_side`` reveal the opposing active typing, damage is scored as
    ``base_power * effectiveness(move_type, target_types)`` (spread = max over affected
    foes); otherwise it degrades to the original base-power ranking. Deterministic
    tie-break stays ``pick_best_pair``'s first-pair-wins order.
    """
    def slot_score(meta, action) -> float:
        return _simple_heuristic_slot(meta, action, state=state, our_side=our_side)

    return pick_best_pair(req, slot_score)

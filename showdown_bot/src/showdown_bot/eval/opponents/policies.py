"""Eval-only opponent policies: greedy_protect + simple_heuristic (T3c).

Deterministic, request-only (no calc/rollout). Both take ``(req, **_ignored)`` so the eval
dispatch can call them with the same kwargs as the other agents. ``simple_heuristic`` also
accepts ``state``/``our_side`` (T3e Task 1) to score damage type-aware when the opposing
active typing is known; without them it degrades to the original base-power behavior.
"""
from __future__ import annotations

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.typechart import effectiveness
from showdown_bot.eval.opponents._common import PROTECT_IDS, move_meta_for, pick_best_pair
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview

# Situational-Protect thresholds (T3e Task 2). Protect is only worth it defensively when a
# slot is genuinely in danger; a healthy slot Protecting just wastes a turn.
_LOW_HP = 0.4
_PROTECT_LOW_SCORE = 1000.0          # low-HP slot: Protect dominates any attack
_PROTECT_HEALTHY_SCORE = -50.0       # healthy slot: Protect discouraged (below any attack/status)
_DOUBLE_PROTECT_PENALTY = -1_000_000.0  # joint constraint: never Protect on BOTH slots


def _is_protect(meta) -> bool:
    return meta is not None and meta.id in PROTECT_IDS


def _slot_hp_fraction(state, our_side, slot: str) -> float:
    """HP fraction of our active mon in ``slot`` ("a"/"b"); full when unknown/no state."""
    if state is None or not our_side:
        return 1.0
    mon = state.active(our_side, slot)
    return mon.hp_fraction if mon is not None else 1.0


def _greedy_slot_score(meta, hp_fraction: float) -> float:
    if meta is None:
        return -1.0  # discourage switch/pass
    if meta.id in PROTECT_IDS:
        return _PROTECT_LOW_SCORE if hp_fraction < _LOW_HP else _PROTECT_HEALTHY_SCORE
    return float(meta.base_power) if meta.is_damaging else 0.0  # damage by power; other status = 0


def greedy_protect_choice(req, *, state=None, our_side=None, **_ignored) -> str:
    """Situational Protect: a slot Protects only when it is low on HP, and never both slots
    at once (a joint no-double-protect penalty); otherwise it takes the highest-power attack.

    HP is read from ``state`` (slot0 -> our "a", slot1 -> our "b"); without ``state``/``our_side``
    every slot is treated as full, so the policy attacks. A custom pair loop (not independent
    slot scoring) is used because no-double-protect couples the two slots. Deterministic:
    first max-scoring pair in enumeration order wins.
    """
    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        return f"/choose default|{req.rqid}"
    hp0 = _slot_hp_fraction(state, our_side, "a")
    hp1 = _slot_hp_fraction(state, our_side, "b")
    best = pairs[0]
    best_score = float("-inf")
    for pair in pairs:
        meta0 = move_meta_for(req, 0, pair.slot0)
        meta1 = move_meta_for(req, 1, pair.slot1)
        score = _greedy_slot_score(meta0, hp0) + _greedy_slot_score(meta1, hp1)
        if _is_protect(meta0) and _is_protect(meta1):
            score += _DOUBLE_PROTECT_PENALTY
        if score > best_score:  # strict > -> first pair wins ties (deterministic)
            best_score = score
            best = pair
    return encode_choose(best, rqid=req.rqid)


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

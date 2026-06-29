from __future__ import annotations

from itertools import product

from showdown_bot.models.actions import SlotAction, SlotPair
from showdown_bot.models.request import BattleRequest


def _bench_switch_targets(req: BattleRequest, slot_index: int) -> list[SlotAction]:
    actions: list[SlotAction] = []
    for mon in req.side.pokemon:
        if mon.active or "fnt" in mon.condition:
            continue
        ident_suffix = mon.ident.split(": ", 1)[-1]
        actions.append(SlotAction(kind="switch", target_ident=ident_suffix))
    if not actions and req.force_switch and req.force_switch[slot_index]:
        actions.append(SlotAction(kind="pass"))
    return actions


def _move_targets(move_target: str) -> list[int | None]:
    if move_target == "self":
        return [None]
    if move_target in ("adjacentFoe", "normal"):
        return [1, 2]
    if move_target == "adjacentAlly":
        return [-1]
    if move_target in ("allAdjacent", "allAdjacentFoes", "all"):
        return [None]
    return [1, 2]


def _slot_move_actions(active_index: int, req: BattleRequest) -> list[SlotAction]:
    if req.force_switch and req.force_switch[active_index]:
        return _bench_switch_targets(req, active_index)
    active = req.active[active_index]
    actions: list[SlotAction] = []
    for i, move in enumerate(active.moves, start=1):
        if move.disabled:
            continue
        for target in _move_targets(move.target):
            actions.append(SlotAction(kind="move", move_index=i, target=target))
            if active.can_terastallize:
                actions.append(
                    SlotAction(kind="move", move_index=i, target=target, terastallize=True)
                )
    return actions


def enumerate_slot_pairs(req: BattleRequest) -> list[SlotPair]:
    if not req.active:
        return []
    slot0_actions = _slot_move_actions(0, req)
    slot1_actions = _slot_move_actions(1, req) if len(req.active) > 1 else [SlotAction(kind="pass")]
    pairs: list[SlotPair] = []
    for a0, a1 in product(slot0_actions, slot1_actions):
        if a0.kind == "switch" and a1.kind == "switch":
            if a0.target_ident == a1.target_ident:
                continue
        pairs.append(SlotPair(slot0=a0, slot1=a1))
    return pairs

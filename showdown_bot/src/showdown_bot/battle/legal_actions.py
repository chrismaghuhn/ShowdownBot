from __future__ import annotations

from itertools import product

from showdown_bot.engine.moves import get_move_meta
from showdown_bot.models.actions import SlotAction, SlotPair
from showdown_bot.models.request import BattleRequest

_CHOICE_ITEMS = frozenset({"choiceband", "choicespecs", "choicescarf"})


def _active_item_id(req: BattleRequest, active_index: int) -> str:
    """Item id of the ``active_index``-th of our active mons (best-effort)."""
    actives = [p for p in req.side.pokemon if p.active]
    if 0 <= active_index < len(actives):
        return (actives[active_index].item or "").replace(" ", "").lower()
    return ""


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
    forced = bool(
        req.force_switch
        and active_index < len(req.force_switch)
        and req.force_switch[active_index]
    )
    if forced:
        return _bench_switch_targets(req, active_index)
    # During a force-switch phase, non-forced slots simply pass (no `active`).
    if req.force_switch and any(req.force_switch):
        return [SlotAction(kind="pass")]
    if not req.active or active_index >= len(req.active):
        return [SlotAction(kind="pass")]
    active = req.active[active_index]
    # Empty slot (doubles with one mon left): nothing to choose, just pass.
    if active is None:
        return [SlotAction(kind="pass")]
    # Choice items lock the holder into the FIRST move it selects. Clicking a
    # non-damaging move (e.g. Protect) therefore locks the mon into that move
    # forever -- a dead Pokémon and, with Protect, an infinite stall loop. Only
    # offer damaging moves to a Choice-item holder.
    choice_locked = _active_item_id(req, active_index) in _CHOICE_ITEMS

    actions: list[SlotAction] = []
    skipped_nondamaging = False
    for i, move in enumerate(active.moves, start=1):
        if move.disabled:
            continue
        if choice_locked and not get_move_meta(move.move).is_damaging:
            skipped_nondamaging = True
            continue
        for target in _move_targets(move.target):
            actions.append(SlotAction(kind="move", move_index=i, target=target))
            if active.can_terastallize:
                actions.append(
                    SlotAction(kind="move", move_index=i, target=target, terastallize=True)
                )
    # If filtering left nothing selectable (e.g. the mon is already locked into
    # Protect), fall back to the unfiltered list so we never emit zero actions.
    if not actions and skipped_nondamaging:
        for i, move in enumerate(active.moves, start=1):
            if move.disabled:
                continue
            for target in _move_targets(move.target):
                actions.append(SlotAction(kind="move", move_index=i, target=target))
    return actions


def _slot_count(req: BattleRequest) -> int:
    if req.active:
        return len(req.active)
    if req.force_switch:
        return len(req.force_switch)
    return 0


def enumerate_slot_pairs(req: BattleRequest) -> list[SlotPair]:
    in_force_phase = bool(req.force_switch and any(req.force_switch))
    if not req.active and not in_force_phase:
        return []
    n_slots = _slot_count(req)
    slot0_actions = _slot_move_actions(0, req)
    slot1_actions = _slot_move_actions(1, req) if n_slots > 1 else [SlotAction(kind="pass")]
    pairs: list[SlotPair] = []
    for a0, a1 in product(slot0_actions, slot1_actions):
        if a0.kind == "switch" and a1.kind == "switch":
            if a0.target_ident == a1.target_ident:
                continue
        pairs.append(SlotPair(slot0=a0, slot1=a1))
    return pairs

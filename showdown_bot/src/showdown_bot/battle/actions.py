from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product

from showdown_bot.battle.legal_actions import _active_mon_fainted, _slot_move_actions
from showdown_bot.models.actions import SlotAction, SlotPair
from showdown_bot.models.request import BattleRequest


@dataclass(frozen=True)
class JointAction:
    """A both-slots decision for one turn, WITHOUT Tera.

    Tera is intentionally stripped from enumeration (it otherwise doubles the
    action space per move, the Z.43-46 blowup in legal_actions) and re-applied
    as a single overlay in policy via ``with_tera``.
    """

    slot0: SlotAction
    slot1: SlotAction

    def as_pair(self) -> SlotPair:
        return SlotPair(slot0=self.slot0, slot1=self.slot1)

    def with_tera(self, slot_index: int) -> "JointAction":
        """Return a copy where the given slot's move terastallizes.

        No-op for non-move actions (you cannot Tera while switching).
        """
        if slot_index == 0 and self.slot0.kind == "move":
            return replace(self, slot0=replace(self.slot0, terastallize=True))
        if slot_index == 1 and self.slot1.kind == "move":
            return replace(self, slot1=replace(self.slot1, terastallize=True))
        return self


def _voluntary_switches(req: BattleRequest, active_index: int) -> list[SlotAction]:
    """Single-slot voluntary switch targets (legal_actions only emits switches on
    force-switch; the heuristic needs them as defensive options too)."""
    if (
        req.active
        and active_index < len(req.active)
        and req.active[active_index] is not None
        and req.active[active_index].trapped
    ):
        return []
    out: list[SlotAction] = []
    for mon in req.side.pokemon:
        if mon.active or "fnt" in mon.condition:
            continue
        ident_suffix = mon.ident.split(": ", 1)[-1]
        out.append(SlotAction(kind="switch", target_ident=ident_suffix))
    return out


def _slot_actions(active_index: int, req: BattleRequest) -> list[SlotAction]:
    forced = bool(
        req.force_switch
        and active_index < len(req.force_switch)
        and req.force_switch[active_index]
    )
    if forced:
        # legal_actions already yields forced switch targets / pass for this slot.
        return _slot_move_actions(active_index, req)
    if req.force_switch and any(req.force_switch):
        # Force-switch phase but this slot isn't switching -> it just passes.
        return [SlotAction(kind="pass")]
    if req.active and active_index < len(req.active) and req.active[active_index] is None:
        # Empty slot (one mon left in doubles): nothing to choose.
        return [SlotAction(kind="pass")]
    if _active_mon_fainted(req, active_index):
        # Active mon fainted with no replacement -> the dead slot must pass.
        return [SlotAction(kind="pass")]
    moves = [a for a in _slot_move_actions(active_index, req) if not a.terastallize]
    return moves + _voluntary_switches(req, active_index)


def enumerate_my_actions(
    req: BattleRequest, *, allow_double_switch: bool = False
) -> list[JointAction]:
    """Pruned joint-action space for the heuristic.

    Pruning (documented assumptions):
    - Tera stripped (overlay only) -> ~4x smaller space.
    - Double-switches dropped by default (rarely the one-ply optimum, expensive).
    - Same-target double-switch is always illegal and skipped.
    """
    in_force_phase = bool(req.force_switch and any(req.force_switch))
    if not req.active and not in_force_phase:
        return []
    n_slots = len(req.active) if req.active else len(req.force_switch or [])
    s0 = _slot_actions(0, req)
    s1 = _slot_actions(1, req) if n_slots > 1 else [SlotAction(kind="pass")]
    out: list[JointAction] = []
    for a0, a1 in product(s0, s1):
        if a0.kind == "switch" and a1.kind == "switch":
            if a0.target_ident == a1.target_ident:
                continue
            if not allow_double_switch:
                continue
        out.append(JointAction(slot0=a0, slot1=a1))
    return out

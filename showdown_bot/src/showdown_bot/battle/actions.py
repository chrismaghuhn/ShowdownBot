from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product

from showdown_bot.battle.legal_actions import (
    _active_mon_fainted,
    _bench_count,
    _slot_move_actions,
)
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

    def with_mega(self, slot_index: int) -> "JointAction":
        """Return a copy where the given slot's move mega evolves."""
        if slot_index == 0 and self.slot0.kind == "move":
            return replace(self, slot0=replace(self.slot0, mega_evolve=True))
        if slot_index == 1 and self.slot1.kind == "move":
            return replace(self, slot1=replace(self.slot1, mega_evolve=True))
        return self


def _voluntary_switches(req: BattleRequest, active_index: int) -> list[SlotAction]:
    """Single-slot voluntary switch targets (legal_actions only emits switches on
    force-switch; the heuristic needs them as defensive options too).

    Both `trapped` and `maybeTrapped` block a VOLUNTARY switch. For an ability trap the server
    reports the last active slot as `maybeTrapped` purely to avoid leaking which foe ability is
    doing the trapping (sim/pokemon.ts:1098,1135-1138) -- the Pokemon really is trapped, so a
    switch here is an illegal action, not a probe. Offering it is what failed Gate B
    (`invalid_choices`=1). This is the VOLUNTARY path only: a FORCED replacement after a faint is
    still legal while trapped and is emitted by legal_actions._bench_switch_targets, which this
    guard deliberately does not touch.
    """
    slot = req.active[active_index] if req.active and active_index < len(req.active) else None
    if slot is not None and (slot.trapped or slot.maybe_trapped):
        return []
    out: list[SlotAction] = []
    for mon in req.side.pokemon:
        if mon.active or "fnt" in mon.condition:
            continue
        ident_suffix = mon.ident.split(": ", 1)[-1]
        out.append(SlotAction(kind="switch", target_ident=ident_suffix))
    return out


def _slot_actions(
    active_index: int, req: BattleRequest, *, drop_first_turn: bool = False
) -> list[SlotAction]:
    forced = bool(
        req.force_switch
        and active_index < len(req.force_switch)
        and req.force_switch[active_index]
    )
    if forced:
        # legal_actions yields forced switch targets, plus pass when the bench
        # cannot fill every forced slot (T4b pass-supplement lives there).
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
    moves = [
        a
        for a in _slot_move_actions(active_index, req, drop_first_turn=drop_first_turn)
        if not a.terastallize and not a.mega_evolve
    ]
    return moves + _voluntary_switches(req, active_index)


def enumerate_my_actions(
    req: BattleRequest,
    *,
    allow_double_switch: bool = False,
    moved_since_switch: list[bool] | None = None,
) -> list[JointAction]:
    """Pruned joint-action space for the heuristic.

    Pruning (documented assumptions):
    - Tera stripped (overlay only) -> ~4x smaller space.
    - Double-switches dropped by default on VOLUNTARY turns (rarely the one-ply
      optimum, expensive). Force phases (T4b) are exempt: forced replacements
      enumerate the maximal-switch joint assignments per the force-phase
      contract (`docs/projects/evaluation/plans/2026-07-10-2b35-T4b-forced-replacement-determinism.md`) --
      every slot with ``force_switch[i]`` true must switch if the bench allows it.
    - Same-target double-switch is always illegal and skipped.
    - Dead Fake Out / First Impression dropped per slot when ``moved_since_switch``
      (by active index) says the mon already acted since switching in.
    """
    in_force_phase = bool(req.force_switch and any(req.force_switch))
    if not req.active and not in_force_phase:
        return []
    n_slots = len(req.active) if req.active else len(req.force_switch or [])

    def _df(idx: int) -> bool:
        return bool(moved_since_switch and idx < len(moved_since_switch) and moved_since_switch[idx])

    s0 = _slot_actions(0, req, drop_first_turn=_df(0))
    s1 = _slot_actions(1, req, drop_first_turn=_df(1)) if n_slots > 1 else [SlotAction(kind="pass")]
    out: list[JointAction] = []
    n_forced = sum(1 for f in (req.force_switch or []) if f)
    want_switches = min(_bench_count(req), n_forced) if in_force_phase else None
    for a0, a1 in product(s0, s1):
        if a0.kind == "switch" and a1.kind == "switch":
            if a0.target_ident == a1.target_ident:
                continue
            if not allow_double_switch and not in_force_phase:
                continue
        if want_switches is not None:
            n_sw = (a0.kind == "switch") + (a1.kind == "switch")
            if n_sw != want_switches:
                continue
        out.append(JointAction(slot0=a0, slot1=a1))
    return out

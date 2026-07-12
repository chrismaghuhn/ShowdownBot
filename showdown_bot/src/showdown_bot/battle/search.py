from __future__ import annotations

import copy

from showdown_bot.engine.state import BattleState


def approx_turn2_state(state: BattleState, *, our_side: str,
                       applied_damage: dict[tuple[str, str], float]) -> BattleState:
    """Coarse turn-2 successor: deep-copy `state`, subtract `applied_damage`
    (expected HP by (side, slot)) clamped >=0, mark 0-HP mons fainted, advance the
    turn. The FieldState (weather/trick_room/tailwind) has no turn counters, so it
    PERSISTS (a documented approximation). Does NOT model move secondary effects,
    switches beyond the applied damage, or item/ability triggers — that is the
    'coarse' in coarse-depth-2 (see the design spec)."""
    nxt = copy.deepcopy(state)
    for (side, slot), dmg in applied_damage.items():
        mon = nxt.sides.get(side, {}).get(slot)
        if mon is None:
            continue
        mon.hp = max(0, int(mon.hp - dmg))
        if mon.hp == 0:
            mon.fainted = True
    nxt.turn = (nxt.turn or 0) + 1
    return nxt

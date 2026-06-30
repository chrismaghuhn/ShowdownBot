"""Internal turn-simulator primitive (Phase 3 slice 1c-A).

clone_state + apply_outcome_to_state: produce the next BattleState from a resolved
TurnOutcome + the turn's actions/roster. Applies ONLY what the outcome encodes — no
end-of-turn simulation (no residual/weather-chip/status-tick/duration/PP/item, no forced
replacement). The H-loop/decide/limited-view are slices 1c-B/C/D.
"""

from __future__ import annotations

import copy

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.resolve import TurnOutcome
from showdown_bot.engine.state import BattleState

_SLOTS = ("a", "b")


def clone_state(state: BattleState) -> BattleState:
    return copy.deepcopy(state)


def _apply_hp(state: BattleState, outcome: TurnOutcome) -> None:
    for (side, slot), delta in outcome.hp_delta.items():
        mon = state.sides.get(side, {}).get(slot)
        if mon is None:
            continue
        if mon.max_hp is None:
            mon.max_hp = 100  # synthetic denominator so the fraction is representable (v1)
        new_frac = max(0.0, min(1.0, mon.hp_fraction + delta))
        mon.hp = round(new_frac * mon.max_hp)
        if new_frac <= 0.0:
            mon.fainted = True


def apply_outcome_to_state(
    state: BattleState, outcome: TurnOutcome, actions_by_side: dict[str, JointAction],
    *, roster_by_side: dict,
) -> BattleState:
    """Return a NEW BattleState; never mutate the input."""
    nxt = clone_state(state)
    _apply_hp(nxt, outcome)
    return nxt

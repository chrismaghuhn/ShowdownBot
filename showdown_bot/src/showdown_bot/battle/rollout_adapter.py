"""Integration glue between the real ``BattleState`` and the decoupled rollout.

Phase C wiring: turns observed game state into a ``ConditionState`` the engine
can roll forward. Kept in the battle layer so ``engine/conditions.py`` stays
decoupled from ``BattleState``.

v1 seeds the conditions the ConditionEngine actually acts on: major status,
Tailwind, and the residual-bearing weather/terrain (Sandstorm chip, Grassy heal).
Screens are not yet tracked in BattleState, so they are left for a later pass;
Trick Room is passed to the rollout via the budget, not the ConditionState.
"""

from __future__ import annotations

from showdown_bot.engine.conditions import ConditionInstance, ConditionState, MonConditions
from showdown_bot.engine.state import BattleState

# FieldState stores weather/terrain as display-ish strings; map the ones with a
# residual to the ConditionEngine's ids. Other weathers/terrains affect damage
# (already baked into the base calc) but have no residual, so we skip them.
_WEATHER_IDS = {"sand": "sandstorm"}
_TERRAIN_IDS = {"grass": "grassyterrain"}


def _match(value: str | None, table: dict[str, str]) -> str | None:
    if not value:
        return None
    low = value.lower()
    for token, cid in table.items():
        if token in low:
            return cid
    return None


def conditions_from_battle(state: BattleState) -> ConditionState:
    cs = ConditionState()
    for side, slots in state.sides.items():
        for slot, mon in slots.items():
            if slot not in ("a", "b") or mon is None:
                continue
            cs.mons[(side, slot)] = MonConditions(status=mon.status)

    for side, active in state.field.tailwind.items():
        if active:
            cs.sides.setdefault(side, {})["tailwind"] = ConditionInstance("tailwind", duration=None)

    weather = _match(state.field.weather, _WEATHER_IDS)
    if weather:
        cs.field[weather] = ConditionInstance(weather, duration=None)

    terrain = _match(state.field.terrain, _TERRAIN_IDS)
    if terrain:
        cs.field[terrain] = ConditionInstance(terrain, duration=None)

    return cs

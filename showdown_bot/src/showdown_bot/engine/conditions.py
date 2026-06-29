"""Decoupled condition engine (spec §7).

Models v1 conditions (major status, volatiles, side/field conditions) with
duration, decay (residual), stat/speed mods and action_risk. Operates on its own
``ConditionState`` + an ``hp`` fraction dict so it is testable in isolation and
does not depend on ``BattleState``/``PokemonState`` (Phase C wires it in).
"""

from __future__ import annotations

from dataclasses import dataclass, field

SlotId = tuple[str, str]  # (side, slot)

# Major-status residual magnitudes (fraction of max HP lost per turn).
_STATUS_RESIDUAL: dict[str, float] = {
    "brn": 1 / 16,
    "psn": 1 / 8,
}


@dataclass
class ConditionInstance:
    name: str
    duration: int | None = None  # remaining turns; None = until cured/removed
    params: dict = field(default_factory=dict)


@dataclass
class MonConditions:
    status: str | None = None  # brn|par|slp|psn|tox|frz
    status_counter: int = 0  # toxic stage / sleep turns remaining
    volatiles: dict[str, ConditionInstance] = field(default_factory=dict)


@dataclass
class ConditionState:
    mons: dict[SlotId, MonConditions] = field(default_factory=dict)
    sides: dict[str, dict[str, ConditionInstance]] = field(default_factory=dict)
    field: dict[str, ConditionInstance] = field(default_factory=dict)


@dataclass
class ResidualEvent:
    key: SlotId
    source: str
    delta: float  # HP fraction change (negative = damage, positive = heal)


def _apply(hp: dict[SlotId, float], key: SlotId, delta: float, source: str,
           events: list[ResidualEvent]) -> None:
    if key not in hp:
        return
    new = max(0.0, min(1.0, hp[key] + delta))
    actual = new - hp[key]
    hp[key] = new
    events.append(ResidualEvent(key=key, source=source, delta=actual))


def step(cstate: ConditionState, hp: dict[SlotId, float]) -> list[ResidualEvent]:
    """Advance conditions one turn: apply residuals, returning the events.

    (Durations and side/field residuals are added in Task B2.)
    """
    events: list[ResidualEvent] = []
    for key, mon in cstate.mons.items():
        if mon.status == "tox":
            stage = max(1, mon.status_counter)
            _apply(hp, key, -(stage / 16), "tox", events)
            mon.status_counter = stage + 1
            continue
        mag = _STATUS_RESIDUAL.get(mon.status or "")
        if mag:
            _apply(hp, key, -mag, mon.status, events)
    return events

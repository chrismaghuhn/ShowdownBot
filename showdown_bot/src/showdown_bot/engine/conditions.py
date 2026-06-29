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
_WEATHER_RESIDUAL: dict[str, float] = {"sandstorm": -1 / 16}
_TERRAIN_HEAL: dict[str, float] = {"grassyterrain": 1 / 16}
_LEECH_SEED = 1 / 8


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


def _decrement(conditions: dict[str, ConditionInstance]) -> None:
    for name in list(conditions):
        inst = conditions[name]
        if inst.duration is not None:
            inst.duration -= 1
            if inst.duration <= 0:
                del conditions[name]


def step(
    cstate: ConditionState,
    hp: dict[SlotId, float],
    *,
    weather_immune: frozenset[SlotId] | set[SlotId] = frozenset(),
    grounded: set[SlotId] | None = None,
) -> list[ResidualEvent]:
    """Advance conditions one turn in Showdown residual order (spec §7.3):
    field (weather/terrain residual + duration), side durations, status/volatile
    residuals, then volatile durations. Returns the residual events for tracing.

    ``grounded=None`` means "treat every mon as grounded" (terrain affects all).
    """
    events: list[ResidualEvent] = []

    # 1. field: weather/terrain residual, then field durations
    for name in list(cstate.field):
        mag = _WEATHER_RESIDUAL.get(name)
        if mag:
            for key in hp:
                if key not in weather_immune:
                    _apply(hp, key, mag, name, events)
        heal = _TERRAIN_HEAL.get(name)
        if heal:
            for key in hp:
                if grounded is None or key in grounded:
                    _apply(hp, key, heal, name, events)
    _decrement(cstate.field)

    # 2. side durations
    for side_conditions in cstate.sides.values():
        _decrement(side_conditions)

    # 3. status + volatile residuals
    for key, mon in cstate.mons.items():
        if mon.status == "tox":
            stage = max(1, mon.status_counter)
            _apply(hp, key, -(stage / 16), "tox", events)
            mon.status_counter = stage + 1
        else:
            mag = _STATUS_RESIDUAL.get(mon.status or "")
            if mag:
                _apply(hp, key, -mag, mon.status, events)

        seed = mon.volatiles.get("leechseed")
        if seed is not None and key in hp:
            before = hp[key]
            _apply(hp, key, -_LEECH_SEED, "leechseed", events)
            drained = before - hp[key]
            seeder = seed.params.get("seeder")
            if seeder is not None and drained > 0:
                _apply(hp, seeder, drained, "leechseed", events)

    # 4. volatile durations
    for mon in cstate.mons.values():
        _decrement(mon.volatiles)

    return events


# --- read-only modifier queries (the ratio building blocks for the rollout) ---


def speed_multiplier(cstate: ConditionState, key: SlotId) -> float:
    """Speed factor from active conditions: Tailwind x2, Paralysis x0.5."""
    m = 1.0
    if "tailwind" in cstate.sides.get(key[0], {}):
        m *= 2.0
    mon = cstate.mons.get(key)
    if mon is not None and mon.status == "par":
        m *= 0.5
    return m


def atk_multiplier(cstate: ConditionState, key: SlotId) -> float:
    """Physical-attack factor: Burn halves Atk."""
    mon = cstate.mons.get(key)
    if mon is not None and mon.status == "brn":
        return 0.5
    return 1.0


def screen_modifier(
    cstate: ConditionState, defender_side: str, category: str, *, game_type: str = "doubles"
) -> float:
    """Damage factor from the defender's screens. Reflect covers physical, Light
    Screen special, Aurora Veil both. Doubles reduces to x2/3 (not x1/2)."""
    screens = cstate.sides.get(defender_side, {})
    active = "auroraveil" in screens
    if category == "physical":
        active = active or "reflect" in screens
    elif category == "special":
        active = active or "lightscreen" in screens
    if not active:
        return 1.0
    return 2 / 3 if game_type == "doubles" else 0.5


def action_act_probability(cstate: ConditionState, key: SlotId) -> float:
    """Expected probability the mon gets to act (no sampling): sleep/freeze 0,
    paralysis 0.75, confusion x2/3. Composed multiplicatively."""
    mon = cstate.mons.get(key)
    if mon is None:
        return 1.0
    if mon.status in ("slp", "frz"):
        return 0.0
    p = 1.0
    if mon.status == "par":
        p *= 0.75
    if "confusion" in mon.volatiles:
        p *= 2 / 3
    return p

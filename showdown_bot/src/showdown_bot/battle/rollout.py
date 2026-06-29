"""Multi-turn condition rollout (spec §6) — standalone / decoupled build.

After the chosen turn is resolved elsewhere, this rolls the condition state
forward H turns under a fixed follow-up policy (each living actor attacks its
target with its state-0 base damage, scaled by *ratio* modifiers and the
expected act-probability) and returns a discounted horizon value + a
JSON-serializable trace.

Invariants honored here:
- I-2: no opponent decision tree; the follow-up policy is fixed.
- I-4/I-5: damage is ``base_damage_0 * modifier_ratio(state_0 -> state_t)`` so
  effects already baked into base_damage are never double-counted.
- I-6: no damage calc is performed here at all; the rollout is pure arithmetic
  on the ratios + ConditionEngine residuals.
- I-7: ``horizon=0`` contributes nothing.

This module does NOT touch BattleState/PokemonState; Phase C integration adapts
the real state into ``RolloutActor``s + a ``ConditionState`` and calls in here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from showdown_bot.engine.conditions import (
    ConditionState,
    action_act_probability,
    atk_multiplier,
    screen_modifier,
    speed_multiplier,
    step,
)

SlotId = tuple[str, str]


@dataclass
class RolloutActor:
    """One mon's fixed follow-up action: hit ``target`` for ``base_damage``
    (fraction of target max HP, as computed in state 0)."""

    key: SlotId
    target: SlotId
    base_damage: float
    base_speed: int
    category: str = "physical"  # physical | special | status


@dataclass
class RolloutWeights:
    ko: float = 6.0
    faint: float = 6.0
    dmg_dealt: float = 1.5
    dmg_taken: float = 1.2


@dataclass
class RolloutBudget:
    horizon: int = 2
    gamma: float = 0.7
    trick_room: bool = False


@dataclass
class TurnTrace:
    turn: int
    order: list[SlotId]
    kos: list[SlotId]
    hp: dict[str, float]  # string keys ("p1a") so the trace is JSON-serializable
    score: float


@dataclass
class RolloutResult:
    value: float
    final_hp: dict[SlotId, float]
    trace: list[TurnTrace] = field(default_factory=list)


def _score_turn(
    start_hp: dict[SlotId, float],
    end_hp: dict[SlotId, float],
    kos: list[SlotId],
    our_side: str,
    w: RolloutWeights,
) -> float:
    s = 0.0
    for key, start in start_hp.items():
        lost = start - end_hp.get(key, start)
        if lost <= 0:
            continue
        if key[0] == our_side:
            s -= w.dmg_taken * lost
        else:
            s += w.dmg_dealt * lost
    for key in kos:
        if key[0] == our_side:
            s -= w.faint
        else:
            s += w.ko
    return s


def rollout(
    actors: list[RolloutActor],
    cstate: ConditionState,
    hp: dict[SlotId, float],
    *,
    our_side: str,
    budget: RolloutBudget | None = None,
    weights: RolloutWeights | None = None,
    weather_immune: frozenset[SlotId] | set[SlotId] = frozenset(),
    grounded: set[SlotId] | None = None,
) -> RolloutResult:
    budget = budget or RolloutBudget()
    weights = weights or RolloutWeights()
    # Lookahead: never mutate the caller's state.
    cstate = copy.deepcopy(cstate)
    hp = dict(hp)

    alive = {key: value > 0 for key, value in hp.items()}
    # state-0 modifiers, captured once so the per-turn ratio is relative to them.
    base_atk = {a.key: atk_multiplier(cstate, a.key) for a in actors}
    base_screen = {a.key: screen_modifier(cstate, a.target[0], a.category) for a in actors}

    value = 0.0
    trace: list[TurnTrace] = []

    for turn in range(1, budget.horizon + 1):
        start_hp = dict(hp)
        kos: list[SlotId] = []

        living = [a for a in actors if alive.get(a.key)]
        # Faster acts first (slower under Trick Room); KO-before-act emerges here.
        living.sort(
            key=lambda a: a.base_speed * speed_multiplier(cstate, a.key),
            reverse=not budget.trick_room,
        )

        order: list[SlotId] = []
        for a in living:
            order.append(a.key)
            if not alive.get(a.key) or not alive.get(a.target):
                continue
            if a.category == "physical" and base_atk.get(a.key):
                atk_ratio = atk_multiplier(cstate, a.key) / base_atk[a.key]
            else:
                atk_ratio = 1.0
            scr0 = base_screen.get(a.key) or 1.0
            scr_ratio = screen_modifier(cstate, a.target[0], a.category) / scr0
            act_p = action_act_probability(cstate, a.key)
            dealt = a.base_damage * atk_ratio * scr_ratio * act_p
            if dealt > 0 and a.target in hp:
                hp[a.target] = max(0.0, hp[a.target] - dealt)
                if hp[a.target] <= 0.0 and alive.get(a.target):
                    alive[a.target] = False
                    kos.append(a.target)

        step(cstate, hp, weather_immune=weather_immune, grounded=grounded)
        for key in list(hp):
            if hp[key] <= 0.0 and alive.get(key):
                alive[key] = False
                kos.append(key)

        score = _score_turn(start_hp, hp, kos, our_side, weights)
        value += (budget.gamma ** turn) * score
        trace.append(
            TurnTrace(
                turn=turn,
                order=order,
                kos=list(kos),
                hp={f"{k[0]}{k[1]}": round(v, 4) for k, v in hp.items()},
                score=round(score, 4),
            )
        )

    return RolloutResult(value=value, final_hp=hp, trace=trace)

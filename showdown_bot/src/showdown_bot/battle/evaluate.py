from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.resolve import PlannedAction, TurnOutcome, resolve_turn
from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SpreadBook,
    hypothesis_from_state,
)
from showdown_bot.engine.calc.models import DamageRequest
from showdown_bot.engine.state import BattleState, FieldState

SlotId = tuple[str, str]

_WEATHER_MAP = {
    "rain": "Rain", "sun": "Sun", "sand": "Sand", "snow": "Snow", "hail": "Hail",
}


def _our_roll(res) -> float:
    """How optimistically to read OUR own attack's damage roll. Default ``min``
    (guaranteed-KO semantics) makes the bot under-commit to KOs it actually lands;
    ``SHOWDOWN_OUR_ROLL = min | mean | max`` tunes it for play-quality A/Bs."""
    mode = os.environ.get("SHOWDOWN_OUR_ROLL", "min").lower()
    if mode == "max":
        return res.max_damage
    if mode == "mean":
        return (res.min_damage + res.max_damage) / 2.0
    return res.min_damage


def _our_def_preset() -> str:
    """Preset for OUR own mon as the defender (incoming damage). Default ``offense``
    (frail) over-estimates incoming for our bulky mons; ``SHOWDOWN_OUR_DEF_PRESET=
    defense`` is the Stage-B proxy to test whether that over-caution is the lever
    before building the real-team-spread plumbing."""
    return DEFENSE if os.environ.get("SHOWDOWN_OUR_DEF_PRESET", "offense").lower() == "defense" else OFFENSE


def build_field_payload(field: FieldState) -> dict:
    payload: dict[str, object] = {"gameType": "Doubles"}
    if field.weather:
        low = field.weather.lower()
        for token, val in _WEATHER_MAP.items():
            if token in low:
                payload["weather"] = val
                break
    if field.terrain:
        payload["terrain"] = field.terrain.replace(" Terrain", "").replace(" terrain", "").strip()
    return payload


@dataclass
class EvalWeights:
    """Action economy is weighted high on purpose (the plan): tempo plays
    (Fake Out, KO-before-act, Protect reads, forced switches, speed control)
    decide VGC games more than raw chip damage."""

    ko: float = 6.0
    faint: float = -6.0
    dmg_dealt: float = 1.5  # per 100% maxHP dealt to opp
    dmg_taken: float = 1.2  # per 100% maxHP we lose
    tempo_prevent: float = 2.5  # we removed an opp action (KO-before-act / flinch)
    tempo_lost: float = -2.5  # one of our actions got removed
    protect_block: float = 1.8  # we Protected an incoming hit
    wasted_into_protect: float = -1.2  # we attacked into a Protect
    speed_control: float = 2.0  # we set Tailwind / Trick Room
    wasted_move: float = -0.6
    switch_cost: float = -0.3
    # Protect action-economy (contextual, not a blanket "Protect bad"):
    protect_stall: float = -1.0  # our Protect blocked nothing -> wasted tempo
    endgame_protect: float = -3.0  # Protecting with our last mon just defers the loss
    partner_abandon: float = -2.0  # we Protected while a teammate fainted this turn


def score_outcome(
    outcome: TurnOutcome, our_side: str, weights: EvalWeights | None = None, *, endgame: bool = False
) -> float:
    w = weights or EvalWeights()
    s = 0.0
    s += w.ko * outcome.my_kos
    s += w.faint * outcome.my_faints

    for key, delta in outcome.hp_delta.items():
        lost = -delta  # positive when HP was lost
        if lost <= 0:
            continue
        if key[0] == our_side:
            s -= w.dmg_taken * lost
        else:
            s += w.dmg_dealt * lost

    for prevented in outcome.prevented_actions:
        if prevented.side == our_side:
            s += w.tempo_lost
        else:
            s += w.tempo_prevent

    for ph in outcome.protected_hits:
        if ph.target[0] == our_side:
            s += w.protect_block  # our mon was shielded from an opp hit
        else:
            s += w.wasted_into_protect  # we hit into their Protect

    for flag in outcome.flags:
        parts = flag.split(":")
        if parts[0] == "status" and len(parts) == 3:
            move_id, owner = parts[1], parts[2]
            if move_id in ("tailwind", "trickroom") and owner.startswith(our_side):
                s += w.speed_control
        elif flag == "wasted_move":
            s += w.wasted_move
        elif parts[0] == "switch" and len(parts) == 2 and parts[1].startswith(our_side):
            s += w.switch_cost

    # Protect action-economy penalties (contextual, not a blanket "Protect bad").
    # Protect is fine for a concrete purpose (shield a KO threat so a partner can
    # act, sit a Tailwind/TR turn), but: blocking nothing wastes tempo; protecting
    # our last mon only defers the loss; protecting while a partner dies is bad
    # action economy. Counters the observed endgame protect-spam loop.
    if any(f.startswith(f"protect:{our_side}") for f in outcome.flags):
        blocked = any(ph.target[0] == our_side for ph in outcome.protected_hits)
        if not blocked:
            s += w.protect_stall
        if endgame:
            s += w.endgame_protect
        if outcome.my_faints > 0:
            s += w.partner_abandon

    return s


class DamageModel:
    """Wires the DamageOracle + per-slot belief hypotheses into a resolver-shaped
    ``damage_fn`` and the three named spread_mode helpers.

    Worst-case-for-us convention:
    - Our attacks: attacker OFFENSE, defender bulky (DEFENSE), MIN roll
      -> we only "KO" when it is guaranteed (secures_ko semantics).
    - Incoming: attacker OFFENSE, our mon frail (DEFENSE preset = least bulk),
      MAX roll -> we assume we take the most.
    """

    def __init__(
        self,
        state: BattleState,
        our_side: str,
        opp_side: str,
        *,
        book: SpreadBook,
        oracle: DamageOracle | None = None,
        field: FieldState | None = None,
    ) -> None:
        self.state = state
        self.our_side = our_side
        self.opp_side = opp_side
        self.book = book
        self.oracle = oracle or DamageOracle()
        self.field = field or state.field
        self.field_payload = build_field_payload(self.field)
        self.hyps = {
            (side, slot): hypothesis_from_state(mon, book)
            for side, slots in state.sides.items()
            for slot, mon in slots.items()
        }

    def _request(self, action: PlannedAction, target_key: SlotId) -> DamageRequest:
        move = action.move.name
        attacker = self.hyps[(action.side, action.slot)].as_attacker(OFFENSE, move=move)
        def_hyp = self.hyps[target_key]
        defender = def_hyp.as_defender(DEFENSE if action.is_ours else _our_def_preset())
        return DamageRequest(
            attacker=attacker, defender=defender, move=move, field=dict(self.field_payload)
        )

    def _alive_slots(self, side: str) -> list[str]:
        out = []
        for slot, mon in self.state.sides.get(side, {}).items():
            if slot in ("a", "b") and not mon.fainted and mon.hp_fraction > 0:
                out.append(slot)
        return out

    def _candidate_targets(self, action: PlannedAction) -> list[SlotId]:
        """Every slot a damaging move might actually hit this turn, so redirect /
        retarget / spread resolution never needs a calc that wasn't prefetched."""
        def_side = "p2" if action.side == "p1" else "p1"
        targets: list[SlotId] = [(def_side, s) for s in self._alive_slots(def_side)]
        if action.move and action.move.target == "allAdjacent":
            targets += [(action.side, s) for s in self._alive_slots(action.side) if s != action.slot]
        if action.target and action.target not in targets:
            targets.append(action.target)
        return targets

    def prefetch(self, action_groups: Iterable[list[PlannedAction]]) -> None:
        """Enqueue every damaging calc across all candidate lines (against every
        plausible target), then flush once -> a single Node round trip per
        decision regardless of redirect/retarget/spread retargeting."""
        for actions in action_groups:
            for a in actions:
                if a.kind != "move" or not a.move or not a.move.is_damaging:
                    continue
                if (a.side, a.slot) not in self.hyps:
                    continue
                for tgt in self._candidate_targets(a):
                    if tgt in self.hyps:
                        self.oracle.request(self._request(a, tgt))
        self.oracle.flush()

    def damage_fn(self, action: PlannedAction, target_mon) -> float:
        if action.move is None or not action.move.is_damaging or action.target is None:
            return 0.0
        if (action.side, action.slot) not in self.hyps or action.target not in self.hyps:
            return 0.0
        req = self._request(action, action.target)
        res = self.oracle.get(self.oracle.request(req))
        if res.max_hp <= 0:
            return 0.0
        roll = _our_roll(res) if action.is_ours else res.max_damage
        return roll / res.max_hp

    # --- the three named spread_mode helpers (footgun-proof, never one flag) ---

    def secures_ko(self, attacker_key: SlotId, target_key: SlotId, move: str) -> bool:
        req = DamageRequest(
            attacker=self.hyps[attacker_key].as_attacker(OFFENSE, move=move),
            defender=self.hyps[target_key].as_defender(DEFENSE),
            move=move, field=dict(self.field_payload),
        )
        return self.oracle.damage(req).is_guaranteed_ohko

    def has_ko_chance(self, attacker_key: SlotId, target_key: SlotId, move: str) -> bool:
        req = DamageRequest(
            attacker=self.hyps[attacker_key].as_attacker(OFFENSE, move=move),
            defender=self.hyps[target_key].as_defender(OFFENSE),
            move=move, field=dict(self.field_payload),
        )
        return self.oracle.damage(req).can_ohko

    def survives_for_sure(self, defender_key: SlotId, attacker_key: SlotId, move: str) -> bool:
        req = DamageRequest(
            attacker=self.hyps[attacker_key].as_attacker(OFFENSE, move=move),
            defender=self.hyps[defender_key].as_defender(OFFENSE),
            move=move, field=dict(self.field_payload),
        )
        return not self.oracle.damage(req).can_ohko


def _rollout_value(
    state: BattleState,
    all_actions: list[PlannedAction],
    outcome: TurnOutcome,
    our_side: str,
    weights: EvalWeights,
    field: FieldState | None,
    horizon: int,
    gamma: float,
) -> float:
    """Discounted multi-turn condition rollout value for a line (spec §6).

    v1 rolls residual conditions forward (no follow-up attackers yet): seeds the
    ConditionState from the post-turn state, applies the line's inflicted status,
    and sums the discounted residual score. Honors I-5 (no double-count: residuals
    are not in the turn-0 damage) and I-6 (no new calcs).
    """
    from showdown_bot.battle.rollout import RolloutBudget, RolloutWeights, rollout
    from showdown_bot.battle.rollout_adapter import apply_line_effects, conditions_from_battle

    cstate = conditions_from_battle(state)
    apply_line_effects(cstate, all_actions)

    post_hp: dict[SlotId, float] = {}
    for side, slots in state.sides.items():
        for slot, mon in slots.items():
            if slot in ("a", "b") and mon is not None:
                key = (side, slot)
                post_hp[key] = max(0.0, mon.hp_fraction + outcome.hp_delta.get(key, 0.0))

    rw = RolloutWeights(
        ko=weights.ko, faint=-weights.faint, dmg_dealt=weights.dmg_dealt, dmg_taken=weights.dmg_taken
    )
    budget = RolloutBudget(horizon=horizon, gamma=gamma, trick_room=bool(field and field.trick_room))
    return rollout([], cstate, post_hp, our_side=our_side, budget=budget, weights=rw).value


def evaluate_line(
    state: BattleState,
    my_actions: list[PlannedAction],
    opp_actions: list[PlannedAction],
    damage_fn,
    *,
    our_side: str,
    weights: EvalWeights | None = None,
    field: FieldState | None = None,
    rollout_horizon: int = 0,
    rollout_gamma: float = 0.7,
    endgame: bool = False,
) -> tuple[float, TurnOutcome]:
    field = field or state.field
    all_actions = my_actions + opp_actions
    outcome = resolve_turn(state, all_actions, damage_fn, our_side=our_side, field=field)
    score = score_outcome(outcome, our_side, weights, endgame=endgame)
    if rollout_horizon > 0:
        score += _rollout_value(
            state, all_actions, outcome, our_side, weights or EvalWeights(),
            field, rollout_horizon, rollout_gamma,
        )
    return score, outcome

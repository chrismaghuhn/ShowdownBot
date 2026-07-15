from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.resolve import (
    ForkRecord,
    PlannedAction,
    SlotId,
    TurnOutcome,
    resolve_turn,
    resolve_turn_branches,
)
from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SpreadBook,
    hypothesis_from_state,
)
from showdown_bot.engine.calc.models import DamageRequest
from showdown_bot.engine.calc_profile import DEFAULT_CALC_PROFILE, CalcProfile
from showdown_bot.engine.moves import hit_probability
from showdown_bot.engine.spread_lookup import lookup_opp_set, lookup_our_spreads
from showdown_bot.engine.state import BattleState, FieldState, to_id

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
    # [2026-07-11] Atlas-aimed: a wasted Protect (blocked nothing) on a fast board
    # (both sides Tailwind) is extra costly -- tempo is scarcer when everyone acts
    # sooner. Default 0.0 = OFF (env-gated via SHOWDOWN_FAST_BOARD_PROTECT_PENALTY).
    fast_board_protect: float = 0.0


@dataclass
class OutcomeBreakdown:
    total_score: float = 0.0
    predicted_outgoing_damage: float = 0.0
    predicted_incoming_damage: float = 0.0
    my_kos: int = 0
    my_faints: int = 0
    protect_stall_penalty: float = 0.0
    endgame_protect_penalty: float = 0.0
    partner_abandon_penalty: float = 0.0
    fast_board_protect_penalty: float = 0.0


def score_outcome_with_breakdown(
    outcome: TurnOutcome,
    our_side: str,
    weights: EvalWeights | None = None,
    *,
    endgame: bool = False,
    fast_board: bool = False,
) -> tuple[float, OutcomeBreakdown]:
    w = weights or EvalWeights()
    bd = OutcomeBreakdown(my_kos=outcome.my_kos, my_faints=outcome.my_faints)
    s = 0.0
    s += w.ko * outcome.my_kos
    s += w.faint * outcome.my_faints

    for key, delta in outcome.hp_delta.items():
        lost = -delta  # positive when HP was lost
        if lost <= 0:
            continue
        if key[0] == our_side:
            s -= w.dmg_taken * lost
            bd.predicted_incoming_damage += lost
        else:
            s += w.dmg_dealt * lost
            bd.predicted_outgoing_damage += lost

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
            bd.protect_stall_penalty = w.protect_stall
            if fast_board:
                s += w.fast_board_protect
                bd.fast_board_protect_penalty = w.fast_board_protect
        if endgame:
            s += w.endgame_protect
            bd.endgame_protect_penalty = w.endgame_protect
        if outcome.my_faints > 0:
            s += w.partner_abandon
            bd.partner_abandon_penalty = w.partner_abandon

    bd.total_score = s
    return s, bd


def score_outcome(
    outcome: TurnOutcome,
    our_side: str,
    weights: EvalWeights | None = None,
    *,
    endgame: bool = False,
    fast_board: bool = False,
) -> float:
    return score_outcome_with_breakdown(
        outcome, our_side, weights, endgame=endgame, fast_board=fast_board
    )[0]


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
        our_spreads: dict | None = None,
        opp_sets: dict | None = None,
        calc_profile: CalcProfile | None = None,
    ) -> None:
        self._calc_profile = calc_profile or DEFAULT_CALC_PROFILE
        self.state = state
        self.our_side = our_side
        self.opp_side = opp_side
        self.book = book
        self.oracle = oracle or DamageOracle()
        self.field = field or state.field
        self.field_payload = build_field_payload(self.field)
        # For OUR mons, use the real team spread (Stage C) instead of the worst-
        # case book preset: correct in both directions (tanks stay bulky, glass
        # cannons stay frail). Opponent mons keep the worst-case presets.
        self.hyps = {}
        for side, slots in state.sides.items():
            for slot, mon in slots.items():
                hyp = hypothesis_from_state(mon, book)
                if side == our_side and our_spreads:
                    preset = lookup_our_spreads(our_spreads, mon)
                    if preset is not None:
                        hyp.spreads = preset
                elif side == opp_side and opp_sets:
                    preset = lookup_opp_set(opp_sets, mon)
                    if preset is not None:
                        hyp.spreads = preset
                self.hyps[(side, slot)] = hyp

    def _request(self, action: PlannedAction, target_key: SlotId) -> DamageRequest:
        move = action.move.name
        attacker = self.hyps[(action.side, action.slot)].as_attacker(OFFENSE, move=move)
        def_hyp = self.hyps[target_key]
        defender = def_hyp.as_defender(DEFENSE if action.is_ours else _our_def_preset())
        return DamageRequest(
            attacker=attacker,
            defender=defender,
            move=move,
            field=dict(self.field_payload),
            gen=self._calc_profile.generation,
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

    def enqueue(self, action_groups: Iterable[list[PlannedAction]]) -> None:
        """Enqueue every damaging calc across all candidate lines into the oracle
        WITHOUT flushing -- so K models sharing one oracle can be flushed once."""
        for actions in action_groups:
            for a in actions:
                if a.kind != "move" or not a.move or not a.move.is_damaging:
                    continue
                if (a.side, a.slot) not in self.hyps:
                    continue
                for tgt in self._candidate_targets(a):
                    if tgt in self.hyps:
                        self.oracle.request(self._request(a, tgt))

    def prefetch(self, action_groups: Iterable[list[PlannedAction]]) -> None:
        """Enqueue then flush -- a single Node round trip per decision (unchanged)."""
        self.enqueue(action_groups)
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
            move=move,
            field=dict(self.field_payload),
            gen=self._calc_profile.generation,
        )
        return self.oracle.damage(req).is_guaranteed_ohko

    def has_ko_chance(self, attacker_key: SlotId, target_key: SlotId, move: str) -> bool:
        req = DamageRequest(
            attacker=self.hyps[attacker_key].as_attacker(OFFENSE, move=move),
            defender=self.hyps[target_key].as_defender(OFFENSE),
            move=move,
            field=dict(self.field_payload),
            gen=self._calc_profile.generation,
        )
        return self.oracle.damage(req).can_ohko

    def survives_for_sure(self, defender_key: SlotId, attacker_key: SlotId, move: str) -> bool:
        req = DamageRequest(
            attacker=self.hyps[attacker_key].as_attacker(OFFENSE, move=move),
            defender=self.hyps[defender_key].as_defender(OFFENSE),
            move=move,
            field=dict(self.field_payload),
            gen=self._calc_profile.generation,
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


def _has_genuine_tie(all_actions: list[PlannedAction], field: FieldState | None) -> bool:
    """True iff an our-action and an opp-action share the full ordering key
    (order rank, dynamic priority, effective speed) -- a real speed tie, not just
    an equal raw number. Detected after pruning, before sequential execution."""
    from showdown_bot.battle.resolve import _order_rank, move_priority

    tr = bool(field and field.trick_room)

    def base_key(a: PlannedAction):
        pr = move_priority(a.move, field) if (a.kind == "move" and a.move) else (
            4 if a.kind == "protect" else 0
        )
        return (_order_rank(a), -pr, a.speed if tr else -a.speed)

    ours = [base_key(a) for a in all_actions if a.is_ours]
    opp = [base_key(a) for a in all_actions if not a.is_ours]
    return any(k in opp for k in ours)


@dataclass
class AccuracyEventDetail:
    attacker: SlotId
    target: SlotId
    move_id: str
    hit_probability: float
    tie_order: str  # "ours_first" | "ours_last"


@dataclass
class TieOrderEvaluation:
    tie_order: str
    weight: float
    accuracy_leaf_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool


@dataclass
class LineEvaluation:
    """On a genuine tie, ``leaves``/``fork_records``/``representative_outcome`` reflect the
    ``ours_last`` evaluation ONLY (the unchanged pre-refactor convention -- ``representative_
    outcome.accuracy_branch_cap_hits`` is ours_last's own count, not merged). ``fallback_leaves``/
    ``accuracy_events``/``tie_order_details`` are the tie-merged/tie-order-aware fields instead --
    a future caller that needs a tie-merged view must use those three, not the representative
    outcome.
    """

    score: float
    representative_outcome: TurnOutcome
    leaves: list[tuple[float, TurnOutcome]] | None = None
    fork_records: list[ForkRecord] | None = None
    fallback_leaves: int = 0
    accuracy_events: list[AccuracyEventDetail] = field(default_factory=list)
    tie_order_details: list[TieOrderEvaluation] = field(default_factory=list)


def _accuracy_events_from_leaves(
    actions: list[PlannedAction],
    state: BattleState,
    leaves: list[tuple[float, TurnOutcome]],
    field: FieldState | None,
    tie_order: str,
) -> list[AccuracyEventDetail]:
    """Unions attempted_hits across the FULL leaf list (not just leaves[0]) so an event only
    ever attempted in a miss-branch -- e.g. an attacker whose target's death in the all-hit
    leaf normally cancels its own later action -- still surfaces here. See resolve_turn_branches'
    leaves[0]-only pitfall documented on that function."""
    actions_by_key = {a.key: a for a in actions}
    # First-writer-wins by (attacker, target, move_id) is only value-correct because
    # hit_probability is currently a pure function of the pre-turn `state`/`field` passed in
    # here (no mid-turn-state-dependent accuracy modifier exists yet) -- every leaf would compute
    # the identical probability for the same key regardless of which leaf discovers it first. A
    # future accuracy modifier keyed on mid-turn state (e.g. a boost applied earlier in the same
    # turn) would need this revisited.
    seen: dict[tuple[SlotId, SlotId, str], float] = {}
    for _weight, out in leaves:
        for ah in out.attempted_hits:
            key3 = (ah.attacker, ah.target, ah.move_id)
            if key3 in seen:
                continue
            attacker_action = actions_by_key.get(ah.attacker)
            if attacker_action is None or attacker_action.move is None:
                continue
            attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
            target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
            if attacker_mon is None or target_mon is None:
                continue
            p = hit_probability(attacker_action.move, attacker_mon, target_mon, field)
            if p is None or p >= 1.0:
                continue
            seen[key3] = p
    return [AccuracyEventDetail(a, t, m, p, tie_order) for (a, t, m), p in seen.items()]


def _union_accuracy_events(
    first: list[AccuracyEventDetail], last: list[AccuracyEventDetail],
) -> list[AccuracyEventDetail]:
    """True union by (attacker, target, move_id) across both evaluated tie orderings --
    first-occurrence-wins (``first`` -- i.e. ``ours_first`` -- wins any overlap). Safe because
    hit_probability is computed from the shared pre-turn state/field in
    ``_accuracy_events_from_leaves``, so the value for a given key is identical regardless of
    which tie ordering it was discovered under -- a plain concatenation here would double-count
    any event uncertain under both orderings and break the ``len(accuracy_events)`` ==
    distinct-event-count contract downstream callers rely on."""
    seen: dict[tuple[SlotId, SlotId, str], AccuracyEventDetail] = {}
    for e in first + last:
        key3 = (e.attacker, e.target, e.move_id)
        if key3 not in seen:
            seen[key3] = e
    return list(seen.values())


def _evaluate_line_details(
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
    fast_board: bool = False,
    accuracy_mode: bool = False,
    accuracy_branch_cap: int = 4,
    _force_tie_break: str | None = None,
) -> LineEvaluation:
    field = field or state.field
    all_actions = my_actions + opp_actions

    def _scored(out: TurnOutcome) -> float:
        sc = score_outcome(out, our_side, weights, endgame=endgame, fast_board=fast_board)
        if rollout_horizon > 0:
            sc += _rollout_value(
                state, all_actions, out, our_side, weights or EvalWeights(),
                field, rollout_horizon, rollout_gamma,
            )
        return sc

    def _one(tb: str) -> LineEvaluation:
        if not accuracy_mode:
            out = resolve_turn(state, all_actions, damage_fn, our_side=our_side, field=field, tie_break=tb)
            return LineEvaluation(score=_scored(out), representative_outcome=out)
        leaves, fallback_leaves, fork_records = resolve_turn_branches(
            state, all_actions, damage_fn, our_side=our_side, field=field,
            tie_break=tb, branch_cap=accuracy_branch_cap,
        )
        total = sum(w * _scored(out) for w, out in leaves)
        representative = leaves[0][1]
        representative.accuracy_branch_cap_hits = fallback_leaves
        events = _accuracy_events_from_leaves(all_actions, state, leaves, field, tie_order=tb)
        return LineEvaluation(
            score=total, representative_outcome=representative, leaves=leaves,
            fork_records=fork_records, fallback_leaves=fallback_leaves, accuracy_events=events,
            tie_order_details=[TieOrderEvaluation(
                tie_order=tb, weight=1.0, accuracy_leaf_count=len(leaves),
                accuracy_branch_cap_hits=fallback_leaves, events_complete=(fallback_leaves == 0),
            )],
        )

    if _force_tie_break is not None:
        return _one(_force_tie_break)
    if _has_genuine_tie(all_actions, field):
        d_first = _one("ours_first")
        d_last = _one("ours_last")
        return LineEvaluation(
            score=0.5 * (d_first.score + d_last.score),
            representative_outcome=d_last.representative_outcome,
            leaves=d_last.leaves, fork_records=d_last.fork_records,
            fallback_leaves=d_first.fallback_leaves + d_last.fallback_leaves,
            accuracy_events=_union_accuracy_events(d_first.accuracy_events, d_last.accuracy_events),
            tie_order_details=[
                TieOrderEvaluation(
                    tie_order="ours_first", weight=0.5,
                    accuracy_leaf_count=len(d_first.leaves) if d_first.leaves else 0,
                    accuracy_branch_cap_hits=d_first.fallback_leaves,
                    events_complete=(d_first.fallback_leaves == 0),
                ),
                TieOrderEvaluation(
                    tie_order="ours_last", weight=0.5,
                    accuracy_leaf_count=len(d_last.leaves) if d_last.leaves else 0,
                    accuracy_branch_cap_hits=d_last.fallback_leaves,
                    events_complete=(d_last.fallback_leaves == 0),
                ),
            ],
        )
    return _one("ours_last")


@dataclass
class AccuracyDiagnostics:
    ko_probability: dict[SlotId, float]
    survival_probability: dict[SlotId, float]
    accuracy_required: dict[tuple[SlotId, SlotId], float | None]
    miss_punish_value: dict[tuple[SlotId, SlotId], float]


def _final_hp_fraction(state: BattleState, target: SlotId, out: TurnOutcome) -> float:
    mon = state.sides.get(target[0], {}).get(target[1])
    start = mon.hp_fraction if mon is not None else 0.0
    return max(0.0, start + out.hp_delta.get(target, 0.0))


def accuracy_diagnostics(
    leaves: list[tuple[float, TurnOutcome]],
    *,
    targets: list[SlotId],
    state: BattleState,
    actions: list[PlannedAction],
    field: FieldState | None,
    fork_records: list[ForkRecord] = (),
    weights: EvalWeights | None = None,
    our_side: str = "p1",
    endgame: bool = False,
    fast_board: bool = False,
) -> AccuracyDiagnostics:
    """Derived from the leaf list (and fork structure) resolve_turn_branches already returns --
    no extra resolve_turn calls. ko_probability uses each target's STARTING hp_fraction (from
    ``state``) plus the leaf's fractional hp_delta -- a target already below full HP can be KO'd
    by an hp_delta well above -1.0; checking against a flat -1.0 threshold silently misses that."""
    if not leaves:
        raise ValueError("accuracy_diagnostics requires at least one leaf")

    ko_probability: dict[SlotId, float] = {t: 0.0 for t in targets}
    for weight, out in leaves:
        for t in ko_probability:  # deduped -- iterating `targets` directly double-counts dupes
            if _final_hp_fraction(state, t, out) <= 1e-9:
                ko_probability[t] += weight
    survival_probability = {t: 1.0 - p for t, p in ko_probability.items()}

    actions_by_key = {a.key: a for a in actions}
    accuracy_required: dict[tuple[SlotId, SlotId], float | None] = {}
    for ah in leaves[0][1].attempted_hits:
        pair = (ah.attacker, ah.target)
        if pair in accuracy_required:
            continue
        attacker_action = actions_by_key.get(ah.attacker)
        if attacker_action is None or attacker_action.move is None:
            continue
        attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
        target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
        if attacker_mon is None or target_mon is None:
            continue
        accuracy_required[pair] = hit_probability(attacker_action.move, attacker_mon, target_mon, field)

    def _scored(out: TurnOutcome) -> float:
        return score_outcome(out, our_side, weights, endgame=endgame, fast_board=fast_board)

    leaves0_score = _scored(leaves[0][1])
    miss_punish_value: dict[tuple[SlotId, SlotId], float] = {}
    for pair, miss_subtree in fork_records:
        subtree_weight = sum(w for w, _ in miss_subtree)
        if subtree_weight <= 0.0:
            continue
        weighted_avg = sum(w * _scored(out) for w, out in miss_subtree) / subtree_weight
        miss_punish_value[pair] = weighted_avg - leaves0_score

    return AccuracyDiagnostics(
        ko_probability=ko_probability, survival_probability=survival_probability,
        accuracy_required=accuracy_required, miss_punish_value=miss_punish_value,
    )


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
    fast_board: bool = False,
    accuracy_mode: bool = False,
    accuracy_branch_cap: int = 4,
    _force_tie_break: str | None = None,
) -> tuple[float, TurnOutcome]:
    d = _evaluate_line_details(
        state, my_actions, opp_actions, damage_fn, our_side=our_side, weights=weights,
        field=field, rollout_horizon=rollout_horizon, rollout_gamma=rollout_gamma,
        endgame=endgame, fast_board=fast_board, accuracy_mode=accuracy_mode,
        accuracy_branch_cap=accuracy_branch_cap, _force_tie_break=_force_tie_break,
    )
    return d.score, d.representative_outcome

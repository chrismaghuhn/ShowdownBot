from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from showdown_bot.engine.moves import (
    MoveMeta,
    blocks_move,
    can_redirect,
    hit_probability,
    move_priority,
)
from showdown_bot.engine.state import BattleState, FieldState, PokemonState

SPREAD_MULT = 0.75  # doubles damage reduction for spread moves

# Moves that only work on the turn the user switched in (fail otherwise).
_FIRST_TURN_MOVES = frozenset({"fakeout", "firstimpression"})

SlotId = tuple[str, str]  # (side, slot) e.g. ("p1", "a")

# damage_fn(action, target_mon) -> fraction of target's max HP dealt (0..1+)
DamageFn = Callable[["PlannedAction", PokemonState], float]


@dataclass
class PlannedAction:
    """One slot's intended action for a single turn.

    Decoupled from /choose encoding (legal_actions) and from JointAction (Task 4)
    so the resolver can be unit-tested with scripted inputs.
    """

    side: str
    slot: str
    kind: str  # "move" | "switch" | "protect" | "pass"
    speed: int = 0
    move: MoveMeta | None = None
    target: SlotId | None = None
    is_ours: bool = False
    is_tera: bool = False

    @property
    def key(self) -> SlotId:
        return (self.side, self.slot)


@dataclass
class PreventedAction:
    side: str
    slot: str
    reason: str  # "fainted_before_acting" | "flinch"


@dataclass
class ProtectedHit:
    attacker: SlotId
    target: SlotId
    move_id: str


@dataclass
class RedirectedHit:
    attacker: SlotId
    original_target: SlotId
    new_target: SlotId
    move_id: str


@dataclass
class AttemptedHit:
    attacker: SlotId
    target: SlotId
    move_id: str


@dataclass
class MissedHit:
    attacker: SlotId
    target: SlotId
    move_id: str


@dataclass
class SpeedEvent:
    side: str
    slot: str
    speed: int
    order_index: int


@dataclass
class TurnOutcome:
    my_kos: int = 0
    opp_kos: int = 0
    my_faints: int = 0
    opp_faints: int = 0
    hp_delta: dict[SlotId, float] = field(default_factory=dict)  # new_frac - start_frac
    prevented_actions: list[PreventedAction] = field(default_factory=list)
    protected_hits: list[ProtectedHit] = field(default_factory=list)
    redirected_hits: list[RedirectedHit] = field(default_factory=list)
    attempted_hits: list[AttemptedHit] = field(default_factory=list)
    missed_hits: list[MissedHit] = field(default_factory=list)
    speed_events: list[SpeedEvent] = field(default_factory=list)
    tera_used_by_me: bool = False
    tera_used_by_opp: bool = False
    flags: set[str] = field(default_factory=set)


def _order_rank(action: PlannedAction) -> int:
    # Switches resolve before all moves regardless of speed.
    return 0 if action.kind == "switch" else 1


def sort_actions(
    actions: list[PlannedAction], field: FieldState | None = None, *, tie_break: str = "ours_last"
) -> list[PlannedAction]:
    """Approximate PS action queue: order asc, then priority desc, then speed.

    Speed is DESC normally, ASC under Trick Room. ``tie_break`` decides equal-key
    ties: ``ours_last`` (default, pessimistic) or ``ours_first`` -- the two
    orderings the tie-EV averages over.
    """
    tr = bool(field and field.trick_room)

    def keyfn(a: PlannedAction):
        pr = move_priority(a.move, field) if (a.kind == "move" and a.move) else (
            4 if a.kind == "protect" else 0
        )
        speed_sort = a.speed if tr else -a.speed
        if tie_break == "ours_first":
            tie = 0 if a.is_ours else 1
        else:
            tie = 1 if a.is_ours else 0  # ours loses ties (pessimistic default)
        return (_order_rank(a), -pr, speed_sort, tie)

    return sorted(actions, key=keyfn)


def resolve_turn(
    state: BattleState,
    actions: list[PlannedAction],
    damage_fn: DamageFn,
    *,
    our_side: str = "p1",
    field: FieldState | None = None,
    tie_break: str = "ours_last",
    forced_miss: frozenset[tuple[SlotId, SlotId]] = frozenset(),
) -> TurnOutcome:
    """Approximate one-ply tactical resolution (layers 2A + 2B).

    Assumptions (documented, not hidden):
    - One representative damage number per hit (from damage_fn); no roll spread.
    - KO removes the victim's not-yet-taken action (KO-before-act).
    - Protect set by a protect action blocks subsequent foe-targeting moves.
    - Switches are treated as "actor does nothing this turn" (bench unmodeled).
    - Status moves deal no HP damage here (their tempo is scored via flags).
    - 2B: Fake Out flinch, Follow Me / Rage Powder redirection (with immunity
      filter), spread moves (x0.75 to every adjacent target), single-target
      failed-target retargeting, switch-before-move ordering.
    - Speed ties stay pessimistic (our mon acts last).
    - forced_miss: an explicit (attacker, target) pair set that overrides the
      hit into a miss (no damage/hit-effects), recorded in missed_hits; every
      attempted hit is recorded in attempted_hits regardless.
    """
    field = field or state.field
    outcome = TurnOutcome()

    start_frac: dict[SlotId, float] = {}
    cur_frac: dict[SlotId, float] = {}
    alive: dict[SlotId, bool] = {}
    for side, slots in state.sides.items():
        for slot, mon in slots.items():
            key = (side, slot)
            frac = mon.hp_fraction
            start_frac[key] = frac
            cur_frac[key] = frac
            alive[key] = not mon.fainted and frac > 0

    protected: set[SlotId] = set()
    cancelled: set[SlotId] = set()
    flinched: set[SlotId] = set()
    redirect_slot: dict[str, str] = {}
    redirect_move: dict[str, str] = {}

    for action in actions:
        if action.is_tera:
            if action.is_ours:
                outcome.tera_used_by_me = True
            else:
                outcome.tera_used_by_opp = True

    def opp_of(side: str) -> str:
        return "p2" if side == "p1" else "p1"

    def alive_slots(side: str) -> list[str]:
        return [s for (sd, s), ok in alive.items() if sd == side and ok]

    def apply_hit(attacker_key: SlotId, attacker_action: PlannedAction, tgt_key: SlotId, spread: bool) -> None:
        move = attacker_action.move
        if tgt_key in protected and blocks_move(move, field):
            outcome.protected_hits.append(ProtectedHit(attacker_key, tgt_key, move.id))
            return
        tgt_mon = state.sides.get(tgt_key[0], {}).get(tgt_key[1])
        if tgt_mon is None:
            return
        outcome.attempted_hits.append(AttemptedHit(attacker_key, tgt_key, move.id))
        if (attacker_key, tgt_key) in forced_miss:
            outcome.missed_hits.append(MissedHit(attacker_key, tgt_key, move.id))
            return
        act_for_dmg = (
            attacker_action
            if attacker_action.target == tgt_key
            else replace(attacker_action, target=tgt_key)
        )
        dealt = max(0.0, float(damage_fn(act_for_dmg, tgt_mon)))
        if spread:
            dealt *= SPREAD_MULT
        new_frac = max(0.0, cur_frac[tgt_key] - dealt)
        cur_frac[tgt_key] = new_frac
        if "flinch" in move.flags and new_frac > 0.0 and alive.get(tgt_key):
            flinched.add(tgt_key)
        if new_frac <= 0.0 and alive.get(tgt_key):
            alive[tgt_key] = False
            cancelled.add(tgt_key)
            if tgt_key[0] == our_side:
                outcome.opp_kos += 1
                outcome.my_faints += 1
            else:
                outcome.my_kos += 1
                outcome.opp_faints += 1

    for idx, action in enumerate(sort_actions(actions, field, tie_break=tie_break)):
        key = action.key
        if action.kind == "move" and action.move:
            outcome.speed_events.append(
                SpeedEvent(action.side, action.slot, action.speed, idx)
            )

        if key in cancelled or not alive.get(key, True):
            outcome.prevented_actions.append(
                PreventedAction(action.side, action.slot, "fainted_before_acting")
            )
            continue
        if key in flinched:
            outcome.prevented_actions.append(
                PreventedAction(action.side, action.slot, "flinch")
            )
            continue

        if action.kind == "protect":
            amon = state.sides.get(action.side, {}).get(action.slot)
            # Consecutive Protect almost always fails (Showdown: ~1/3 on the 2nd,
            # worse after). Don't rely on it -> model it as failing so the policy
            # stops spamming Protect into a KO.
            if amon is not None and getattr(amon, "consecutive_protect", 0) >= 1:
                outcome.flags.add(f"protect_failed:{action.side}{action.slot}")
                # A failed Protect wastes the whole turn: the mon does nothing
                # and still eats the incoming hit. Charge it the same lost-action
                # tempo cost an interrupted attack pays, otherwise Protect's +4
                # priority lets a doomed Protect dodge the penalty and the policy
                # spams it instead of actually attacking.
                outcome.prevented_actions.append(
                    PreventedAction(action.side, action.slot, "protect_failed")
                )
                continue
            protected.add(key)
            outcome.flags.add(f"protect:{action.side}{action.slot}")
            continue
        if action.kind in ("switch", "pass"):
            if action.kind == "switch":
                outcome.flags.add(f"switch:{action.side}{action.slot}")
            continue

        move = action.move
        if move is None:
            continue

        # Fake Out / First Impression only work the turn the user switched in.
        if move.id in _FIRST_TURN_MOVES:
            amon = state.sides.get(action.side, {}).get(action.slot)
            if amon is not None and getattr(amon, "moved_since_switch", False):
                outcome.flags.add("wasted_move")
                continue

        if move.id in ("followme", "ragepowder"):
            redirect_slot[action.side] = action.slot
            redirect_move[action.side] = move.id
            outcome.flags.add(f"status:{move.id}:{action.side}{action.slot}")
            continue
        if not move.is_damaging:
            outcome.flags.add(f"status:{move.id}:{action.side}{action.slot}")
            continue

        def_side = opp_of(action.side)

        if move.is_spread:
            targets = [(def_side, s) for s in alive_slots(def_side)]
            if move.target == "allAdjacent":
                targets += [(action.side, s) for s in alive_slots(action.side) if s != action.slot]
            if not targets:
                outcome.flags.add("wasted_move")
                continue
            for tgt in targets:
                apply_hit(key, action, tgt, spread=True)
            continue

        tgt = action.target
        rslot = redirect_slot.get(def_side)
        if (
            rslot
            and tgt is not None
            and tgt[0] == def_side
            and tgt[1] != rslot
            and alive.get((def_side, rslot))
        ):
            attacker_mon = state.sides.get(action.side, {}).get(action.slot)
            attacker_types = (
                list(attacker_mon.types)
                if attacker_mon is not None and getattr(attacker_mon, "types", None)
                else None
            )
            if can_redirect(redirect_move.get(def_side, ""), attacker_mon, attacker_types):
                new_tgt = (def_side, rslot)
                outcome.redirected_hits.append(RedirectedHit(key, tgt, new_tgt, move.id))
                tgt = new_tgt

        if tgt is None or not alive.get(tgt, False):
            alt = [(def_side, s) for s in alive_slots(def_side)]
            if alt:
                if tgt is not None:
                    outcome.flags.add("retarget")
                tgt = alt[0]
            else:
                outcome.flags.add("wasted_move")
                continue

        apply_hit(key, action, tgt, spread=False)

    for key in start_frac:
        outcome.hp_delta[key] = cur_frac[key] - start_frac[key]

    return outcome


ForkRecord = tuple[tuple[SlotId, SlotId], list[tuple[float, TurnOutcome]]]


def resolve_turn_branches(
    state: BattleState,
    actions: list[PlannedAction],
    damage_fn: DamageFn,
    *,
    our_side: str = "p1",
    field: FieldState | None = None,
    tie_break: str = "ours_last",
    branch_cap: int = 4,
) -> tuple[list[tuple[float, TurnOutcome]], int, list[ForkRecord]]:
    """Recursively fork ``resolve_turn`` on genuinely uncertain accuracy events, re-discovering
    newly-revealed events after every partial resolve (spec Sec.5).

    A fixed, one-shot "discover events from a single all-hit resolve_turn call" list is WRONG
    whenever a hit/miss outcome changes who gets to act at all (KO-before-act) or who gets
    targeted (redirection): an action that never reaches ``apply_hit`` in one branch's resolve
    is invisible to a list built from that branch alone, so a sibling branch that revives it
    would otherwise be silently scored as if that action always hits.

    Returns ``(leaves, fallback_leaves, fork_records)``:

    - ``leaves``: a probability-weighted list of ``(weight, TurnOutcome)`` pairs whose weights
      sum to 1.0 exactly; ``leaves[0]`` is always the fully-resolved "everything hits" leaf
      (hit-branches are explored before miss-branches, and recursion is depth-first).
    - ``fallback_leaves``: how many recursion paths hit ``branch_cap`` before fully resolving --
      each such leaf keeps its own remaining pending events implicitly hit (today's legacy
      resolution), affecting only that specific subtree.
    - ``fork_records``: for every fork point encountered ON THE PATH TO ``leaves[0]`` (i.e. while
      every earlier decision along the way was the "hit" side), the ``(pair, miss_subtree)`` pair
      where ``miss_subtree`` is that fork's own miss-sibling's full leaf list. This is exactly
      the input a later ``miss_punish_value`` diagnostic (spec Sec.7) needs -- the tree structure
      a flat leaf list alone cannot reconstruct after the fact.
    """
    actions_by_key = {a.key: a for a in actions}
    calls = 0
    fallback_leaves = 0
    fork_records: list[ForkRecord] = []

    def expand(miss_set, decided_hit, weight, on_hit_path):
        nonlocal calls, fallback_leaves
        calls += 1
        out = resolve_turn(
            state, actions, damage_fn, our_side=our_side, field=field,
            tie_break=tie_break, forced_miss=miss_set,
        )
        decided = miss_set | decided_hit
        pending: list[tuple[tuple[SlotId, SlotId], float]] = []
        for ah in out.attempted_hits:
            pair = (ah.attacker, ah.target)
            if pair in decided:
                continue
            attacker_action = actions_by_key.get(ah.attacker)
            if attacker_action is None or attacker_action.move is None:
                continue
            attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
            target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
            if attacker_mon is None or target_mon is None:
                continue
            p = hit_probability(attacker_action.move, attacker_mon, target_mon, field)
            if p is not None and 0.0 < p < 1.0:
                pending.append((pair, p))
        if not pending:
            return [(weight, out)]
        if calls >= branch_cap:
            fallback_leaves += 1
            return [(weight, out)]
        pair, p = pending[0]  # deterministic: first attempted-hit order
        hit_leaves = expand(miss_set, decided_hit | {pair}, weight * p, on_hit_path)
        miss_leaves = expand(miss_set | {pair}, decided_hit, weight * (1.0 - p), False)
        if on_hit_path:
            fork_records.append((pair, miss_leaves))
        return hit_leaves + miss_leaves

    leaves = expand(frozenset(), frozenset(), 1.0, True)
    return leaves, fallback_leaves, fork_records

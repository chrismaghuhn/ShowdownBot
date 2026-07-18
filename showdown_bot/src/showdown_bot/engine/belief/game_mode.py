from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SpreadBook,
    hypothesis_from_state,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc.models import CalcMon, DamageRequest
from showdown_bot.engine.calc_profile import DEFAULT_CALC_PROFILE, CalcProfile
from showdown_bot.engine.state import BattleState, PokemonState


class GameMode(str, Enum):
    MUST_REACT = "must_react"
    AHEAD = "ahead"
    NEUTRAL = "neutral"


def _opp_side(our_side: str) -> str:
    return "p2" if our_side == "p1" else "p1"


def _field_payload(state: BattleState) -> dict:
    payload: dict[str, object] = {"gameType": "Doubles"}
    if state.field.weather:
        payload["weather"] = state.field.weather
    if state.field.terrain:
        payload["terrain"] = state.field.terrain.replace(" Terrain", "")
    return payload


def _active_living(state: BattleState, side: str) -> list[PokemonState]:
    return [m for m in state.side(side).values() if not m.fainted]


def _our_defender(mon: PokemonState, book: SpreadBook) -> CalcMon:
    # We know our own set in practice; absent that, assume max bulk (defense
    # preset) so "do we die" stays a genuine worst-case threat check.
    return hypothesis_from_state(mon, book).as_defender(DEFENSE)


def _our_attacker(mon: PokemonState, book: SpreadBook, move: str) -> CalcMon:
    return hypothesis_from_state(mon, book).as_attacker(OFFENSE, move=move)


def _ko_request(
    attacker_mon: PokemonState,
    move: str,
    defender_mon: PokemonState,
    book: SpreadBook,
    field: dict,
    calc_profile: CalcProfile,
) -> DamageRequest:
    """Build a OFFENSE-vs-DEFENSE DamageRequest (shared by compute_game_mode and helpers)."""
    return DamageRequest(
        attacker=hypothesis_from_state(attacker_mon, book).as_attacker(OFFENSE, move=move),
        defender=hypothesis_from_state(defender_mon, book).as_defender(DEFENSE),
        move=move,
        field=field,
        gen=calc_profile.generation,
    )


def ko_threat_counts(
    state: BattleState,
    our_side: str,
    *,
    calc: CalcClient,
    book: SpreadBook,
    calc_profile: CalcProfile | None = None,
) -> tuple[int, int]:
    """Return ``(ko_threatened_count, survives_for_sure_count)`` over our active
    living mons under the opponent's *known* moves.

    Uses the same OFFENSE-vs-DEFENSE / ``is_guaranteed_ohko`` semantics as
    ``compute_game_mode`` — no drift.

    * ``threatened`` — guaranteed-OHKO'd by at least one known opponent move.
    * ``survives``   — no known opponent move can OHKO (not ``can_ohko`` for all).
    """
    opp_side = _opp_side(our_side)
    field = _field_payload(state)
    profile = calc_profile or DEFAULT_CALC_PROFILE
    our_mons = _active_living(state, our_side)
    opp_mons = _active_living(state, opp_side)
    if not our_mons:
        return 0, 0
    if not opp_mons:
        return 0, len(our_mons)

    flat: list[DamageRequest] = []
    owner: list[int] = []
    for ours in our_mons:
        for opp in opp_mons:
            for move in sorted(opp.move_names):
                flat.append(_ko_request(opp, move, ours, book, field, profile))
                owner.append(id(ours))

    results = calc.damage_batch(flat) if flat else []
    by: dict[int, list] = {id(m): [] for m in our_mons}
    for o, r in zip(owner, results):
        by[o].append(r)

    threatened = survives = 0
    for m in our_mons:
        rs = by[id(m)]
        if not rs:
            survives += 1
        elif any(r.is_guaranteed_ohko for r in rs):
            threatened += 1
        elif not any(r.can_ohko for r in rs):
            survives += 1
    return threatened, survives


def guaranteed_ohko(
    state: BattleState,
    attacker_mon: PokemonState,
    move: str,
    defender_mon: PokemonState,
    *,
    calc: CalcClient,
    book: SpreadBook,
    calc_profile: CalcProfile | None = None,
) -> bool:
    """Return True if the attacker is guaranteed to OHKO the defender with ``move``
    (OFFENSE-vs-DEFENSE preset, same as ``compute_game_mode`` outgoing check)."""
    field = _field_payload(state)
    profile = calc_profile or DEFAULT_CALC_PROFILE
    res = calc.damage_batch([
        _ko_request(attacker_mon, move, defender_mon, book, field, profile)
    ])[0]
    return res.is_guaranteed_ohko


@dataclass
class GameModeHandle:
    """Deferred base classification (Lever A). ``enqueue_base_game_mode`` puts the incoming
    (opponent-attacks-us) ko-threat requests into a shared ``DamageOracle`` without flushing;
    ``resolve_base_game_mode`` reads them after the shared flush. ``degenerate`` reproduces
    ``compute_game_mode``'s ``not our_mons or not opp_mons`` short-circuit to NEUTRAL."""

    degenerate: bool
    keys: list[str]
    owner: list[int]
    our_mon_ids: list[int]
    our_mons: list
    opp_mons: list
    field: dict
    profile: CalcProfile
    book: SpreadBook


def enqueue_base_game_mode(
    state: BattleState,
    *,
    our_side: str,
    oracle,
    book: SpreadBook,
    calc_profile: CalcProfile | None = None,
) -> GameModeHandle:
    """Phase 1: enqueue the incoming ko-threat requests into ``oracle`` (no flush). The requests
    and their per-owner grouping are byte-identical to ``ko_threat_counts``; only the transport
    (``oracle.request`` instead of an immediate ``calc.damage_batch``) differs."""
    opp_side = _opp_side(our_side)
    field = _field_payload(state)
    profile = calc_profile or DEFAULT_CALC_PROFILE
    our_mons = _active_living(state, our_side)
    opp_mons = _active_living(state, opp_side)
    if not our_mons or not opp_mons:
        return GameModeHandle(True, [], [], [], [], [], field, profile, book)
    keys: list[str] = []
    owner: list[int] = []
    for ours in our_mons:
        for opp in opp_mons:
            for move in sorted(opp.move_names):
                keys.append(oracle.request(_ko_request(opp, move, ours, book, field, profile)))
                owner.append(id(ours))
    return GameModeHandle(
        False, keys, owner, [id(m) for m in our_mons], our_mons, opp_mons, field, profile, book
    )


def resolve_base_game_mode(handle: GameModeHandle, *, oracle) -> GameMode:
    """Phase 2: read the incoming results from the flushed ``oracle``. On ``threatened > 0``
    return MUST_REACT **without building any outgoing request** (the base short-circuit). Else
    enqueue the outgoing requests, flush once more, and return AHEAD/NEUTRAL -- byte-identical to
    ``compute_game_mode``'s tail (``we_get_ko`` = any is_guaranteed_ohko, order-independent)."""
    if handle.degenerate:
        return GameMode.NEUTRAL
    by: dict[int, list] = {mid: [] for mid in handle.our_mon_ids}
    for key, o in zip(handle.keys, handle.owner):
        by[o].append(oracle.get(key))
    threatened = 0
    for mid in handle.our_mon_ids:
        rs = by[mid]
        if rs and any(r.is_guaranteed_ohko for r in rs):
            threatened += 1
    if threatened > 0:
        return GameMode.MUST_REACT

    outgoing_keys: list[str] = []
    for ours in handle.our_mons:
        for move in sorted(ours.move_names):
            attacker = _our_attacker(ours, handle.book, move)
            for opp in handle.opp_mons:
                opp_hyp = hypothesis_from_state(opp, handle.book)
                outgoing_keys.append(
                    oracle.request(
                        DamageRequest(
                            attacker=attacker,
                            defender=opp_hyp.as_defender(DEFENSE),
                            move=move,
                            field=handle.field,
                            gen=handle.profile.generation,
                        )
                    )
                )
    oracle.flush()  # second (planned) flush -- only reached when NOT base MUST_REACT
    we_get_ko = any(oracle.get(k).is_guaranteed_ohko for k in outgoing_keys)
    return GameMode.AHEAD if we_get_ko else GameMode.NEUTRAL


def compute_game_mode(
    state: BattleState,
    *,
    our_side: str,
    calc: CalcClient,
    book: SpreadBook,
    calc_profile: CalcProfile | None = None,
) -> GameMode:
    """Classify the position from ``our_side``'s perspective.

    Both checks put the OPPONENT in ``offense_mode`` (max offense) when it is
    attacking -- that is the dangerous worst case:

    * ``must_react``: under the opponent's max-offense, at least one of our
      mons is guaranteed OHKO'd next turn.
    * ``ahead``: under the opponent's max-offense NONE of our mons die, AND we
      still guarantee a KO even when the opponent defends in ``defense_mode``
      (max bulk).
    * ``neutral``: otherwise.

    Single source of truth: this is the two-phase ``enqueue -> flush -> resolve`` over a private
    ``DamageOracle(client=calc)`` (Lever A). The oracle binds the injected ``calc`` so a pinned
    backend / test spy / error stub is never dropped."""
    from showdown_bot.battle.oracle import DamageOracle  # local: avoid engine->battle import cycle

    oracle = DamageOracle(client=calc)
    handle = enqueue_base_game_mode(
        state, our_side=our_side, oracle=oracle, book=book, calc_profile=calc_profile
    )
    oracle.flush()
    return resolve_base_game_mode(handle, oracle=oracle)


def _faints(state: BattleState, side: str) -> int:
    return sum(1 for m in state.side(side).values() if m.fainted)


def enqueue_classification(
    state: BattleState,
    *,
    our_side: str,
    oracle,
    book: SpreadBook,
    calc_profile: CalcProfile | None = None,
) -> GameModeHandle:
    """Phase 1 for the extended classifier. The extended mon-count / speed-control signals are
    non-calc, so the enqueue is identical to the base."""
    return enqueue_base_game_mode(
        state, our_side=our_side, oracle=oracle, book=book, calc_profile=calc_profile
    )


def resolve_classification(
    handle: GameModeHandle,
    *,
    oracle,
    state: BattleState,
    our_side: str,
    low_hp_threshold: float = 0.35,
) -> GameMode:
    """Phase 2 for the extended classifier: resolve the base mode from the flushed oracle, then
    apply the SAME non-calc mon-count / speed-control adjustments as ``classify_game_mode``."""
    base = resolve_base_game_mode(handle, oracle=oracle)
    opp_side = _opp_side(our_side)
    mon_diff = _faints(state, opp_side) - _faints(state, our_side)  # >0 => we are ahead
    opp_tailwind = bool(state.field.tailwind.get(opp_side, False))
    our_tailwind = bool(state.field.tailwind.get(our_side, False))
    opp_low_hp = any(
        0.0 < m.hp_fraction <= low_hp_threshold for m in _active_living(state, opp_side)
    )

    # must_react dominates.
    if base == GameMode.MUST_REACT:
        return GameMode.MUST_REACT
    if mon_diff < 0:
        return GameMode.MUST_REACT
    if opp_tailwind and mon_diff <= 0 and base != GameMode.AHEAD:
        return GameMode.MUST_REACT

    # ahead signals.
    if base == GameMode.AHEAD:
        return GameMode.AHEAD
    if mon_diff > 0:
        return GameMode.AHEAD
    if opp_low_hp:
        return GameMode.AHEAD
    if our_tailwind and mon_diff >= 0:
        return GameMode.AHEAD

    return GameMode.NEUTRAL


def classify_game_mode(
    state: BattleState,
    *,
    our_side: str,
    calc: CalcClient,
    book: SpreadBook,
    low_hp_threshold: float = 0.35,
    calc_profile: CalcProfile | None = None,
) -> GameMode:
    """Extended classifier: the calc-based KO check (``compute_game_mode``) plus
    mon-count and speed-control signals. Single source of truth -- the two-phase
    ``enqueue -> flush -> resolve`` over a private ``DamageOracle(client=calc)`` (Lever A).

    must_react: opponent threatens a guaranteed KO, OR we are down mons, OR the
                opponent has active speed control while we are not ahead.
    ahead:      we guarantee a KO and survive, OR we are up mons, OR the opponent
                has a low-HP target, OR we hold speed control and are not behind.
    neutral:    otherwise.
    """
    from showdown_bot.battle.oracle import DamageOracle  # local: avoid engine->battle import cycle

    oracle = DamageOracle(client=calc)
    handle = enqueue_classification(
        state, our_side=our_side, oracle=oracle, book=book, calc_profile=calc_profile
    )
    oracle.flush()
    return resolve_classification(
        handle, oracle=oracle, state=state, our_side=our_side, low_hp_threshold=low_hp_threshold
    )

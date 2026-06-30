from __future__ import annotations

from enum import Enum

from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SpreadBook,
    hypothesis_from_state,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc.models import CalcMon, DamageRequest
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
) -> DamageRequest:
    """Build a OFFENSE-vs-DEFENSE DamageRequest (shared by compute_game_mode and helpers)."""
    return DamageRequest(
        attacker=hypothesis_from_state(attacker_mon, book).as_attacker(OFFENSE, move=move),
        defender=hypothesis_from_state(defender_mon, book).as_defender(DEFENSE),
        move=move,
        field=field,
    )


def ko_threat_counts(
    state: BattleState,
    our_side: str,
    *,
    calc: CalcClient,
    book: SpreadBook,
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
                flat.append(_ko_request(opp, move, ours, book, field))
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
) -> bool:
    """Return True if the attacker is guaranteed to OHKO the defender with ``move``
    (OFFENSE-vs-DEFENSE preset, same as ``compute_game_mode`` outgoing check)."""
    field = _field_payload(state)
    res = calc.damage_batch([_ko_request(attacker_mon, move, defender_mon, book, field)])[0]
    return res.is_guaranteed_ohko


def compute_game_mode(
    state: BattleState,
    *,
    our_side: str,
    calc: CalcClient,
    book: SpreadBook,
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
    """
    opp_side = _opp_side(our_side)
    field = _field_payload(state)

    our_mons = _active_living(state, our_side)
    opp_mons = _active_living(state, opp_side)
    if not our_mons or not opp_mons:
        return GameMode.NEUTRAL

    # --- incoming threat: delegate to shared helper (same semantics) ---
    threatened, _ = ko_threat_counts(state, our_side, calc=calc, book=book)
    if threatened > 0:
        return GameMode.MUST_REACT

    # --- our KO power: opponent defends in defense_mode (max bulk) ---
    outgoing: list[DamageRequest] = []
    for ours in our_mons:
        for move in sorted(ours.move_names):
            attacker = _our_attacker(ours, book, move)
            for opp in opp_mons:
                opp_hyp = hypothesis_from_state(opp, book)
                outgoing.append(
                    DamageRequest(
                        attacker=attacker,
                        defender=opp_hyp.as_defender(DEFENSE),
                        move=move,
                        field=field,
                    )
                )

    we_get_ko = False
    if outgoing:
        for res in calc.damage_batch(outgoing):
            if res.is_guaranteed_ohko:
                we_get_ko = True
                break

    if we_get_ko:
        return GameMode.AHEAD
    return GameMode.NEUTRAL


def _faints(state: BattleState, side: str) -> int:
    return sum(1 for m in state.side(side).values() if m.fainted)


def classify_game_mode(
    state: BattleState,
    *,
    our_side: str,
    calc: CalcClient,
    book: SpreadBook,
    low_hp_threshold: float = 0.35,
) -> GameMode:
    """Extended classifier: the calc-based KO check (``compute_game_mode``) plus
    mon-count and speed-control signals. Single source of truth -- this wraps
    ``compute_game_mode`` rather than duplicating its damage logic.

    must_react: opponent threatens a guaranteed KO, OR we are down mons, OR the
                opponent has active speed control while we are not ahead.
    ahead:      we guarantee a KO and survive, OR we are up mons, OR the opponent
                has a low-HP target, OR we hold speed control and are not behind.
    neutral:    otherwise.
    """
    base = compute_game_mode(state, our_side=our_side, calc=calc, book=book)
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

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

    # --- incoming threat: opponent attacks in offense_mode ---
    incoming: list[DamageRequest] = []
    for opp in opp_mons:
        opp_hyp = hypothesis_from_state(opp, book)
        for move in sorted(opp.move_names):
            attacker = opp_hyp.as_attacker(OFFENSE, move=move)
            for ours in our_mons:
                incoming.append(
                    DamageRequest(
                        attacker=attacker,
                        defender=_our_defender(ours, book),
                        move=move,
                        field=field,
                    )
                )

    we_get_ohkod = False
    if incoming:
        for res in calc.damage_batch(incoming):
            if res.is_guaranteed_ohko:
                we_get_ohkod = True
                break

    if we_get_ohkod:
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

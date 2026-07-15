from __future__ import annotations

from showdown_bot.engine.state import PokemonState, to_id


def spread_lookup_key(mon: PokemonState) -> str:
    return mon.base_species_id or to_id(mon.species)


def lookup_our_spreads(our_spreads, mon):
    if not our_spreads:
        return None
    key = spread_lookup_key(mon)
    return our_spreads.get(key) or our_spreads.get(mon.species)


def lookup_opp_set(opp_sets, mon):
    if not opp_sets:
        return None
    return opp_sets.get(spread_lookup_key(mon)) or opp_sets.get(to_id(mon.species))

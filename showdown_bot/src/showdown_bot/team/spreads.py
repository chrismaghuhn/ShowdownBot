"""Parse our OWN packed team into per-species real spreads.

The bot models opponents with worst-case presets (offense/defense), but for our
own mons we KNOW the real set. Using it (instead of the crude "everything bulky"
proxy) makes incoming-damage estimates correct in both directions: genuine tanks
stay bulky, genuine glass cannons (Flutter Mane) are correctly frail.

We return, per species, a ``SpeciesSpreads`` whose offense and defense presets
are both the single real spread -- so it is used regardless of the calc mode.
"""

from __future__ import annotations

from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset
from showdown_bot.engine.state import BattleState, parse_details
from showdown_bot.models.request import BattleRequest

# Packed EV order: hp, atk, def, spa, spd, spe.
_EV_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")


def _parse_mon(block: str) -> tuple[str, SpeciesSpreads] | None:
    f = block.split("|")
    if len(f) < 7:
        return None
    species = (f[1] or f[0]).strip()  # species is blank when identical to nickname
    if not species:
        return None
    item = f[2].strip()
    nature = (f[5] or "Hardy").strip()
    evs: dict[str, int] = {}
    for key, raw in zip(_EV_KEYS, f[6].split(",")):
        raw = raw.strip()
        if raw and raw != "0":
            evs[key] = int(raw)
    preset = SpreadPreset(nature=nature, evs=evs, items=[item] if item else [])
    return species, SpeciesSpreads(offense=preset, defense=preset)


def our_spreads_from_packed(packed: str) -> dict[str, SpeciesSpreads]:
    out: dict[str, SpeciesSpreads] = {}
    for block in packed.split("]"):
        block = block.strip()
        if not block:
            continue
        parsed = _parse_mon(block)
        if parsed is not None:
            out[parsed[0]] = parsed[1]
    return out


def apply_own_team_knowledge(
    state: BattleState, request: BattleRequest, our_spreads: dict | None
) -> None:
    """Single source of own-team item truth, run once in decision setup before
    speed / damage / enumeration / evaluation.

    Precedence: live request item (tri-state) > protocol events (already in
    state.py, which set item_lost) > packed-team fallback. A lost item is never
    resurrected by the fallback.
    """
    our_side = request.side.id or "p1"
    side = state.sides.get(our_side, {})
    by_species = {mon.species: mon for mon in side.values()}

    # Rule 1: live request item, tri-state.
    for poke in request.side.pokemon:
        species = parse_details(poke.details).species
        mon = by_species.get(species)
        if mon is None:
            continue
        raw = poke.item
        if raw is None:
            continue  # field missing -> no assertion
        if raw != "":
            mon.item, mon.item_known, mon.item_lost = raw, True, False
        else:
            mon.item, mon.item_known, mon.item_lost = None, True, True

    # Rule 3: packed-team fallback only when still unknown AND not lost.
    if our_spreads:
        for mon in side.values():
            if mon.item_known or mon.item_lost:
                continue
            spreads = our_spreads.get(mon.species)
            items = spreads.defense.items if spreads else []
            if items:
                mon.item, mon.item_known = items[0], True

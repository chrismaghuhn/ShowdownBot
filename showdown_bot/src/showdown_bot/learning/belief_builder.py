"""learning/belief_builder.py — BeliefSide DTO, quality helper, and side builders.

D2a: BeliefSide + _quality + build_known_side (our full known team).
D2b: build_opponent_belief (active-only, prior-based, limited-view-safe) — TODO.
D3:  build_belief_for_side dispatcher — TODO.

PokemonSlot field access (grounded from models/request.py + fixture):
  slot.ident       : str   e.g. "p1: Incineroar"
  slot.details     : str   e.g. "Incineroar, L50, F"
  slot.condition   : str   e.g. "150/150"
  slot.active      : bool
  slot.stats       : dict[str, int]  e.g. {"atk":100,...,"spe":100}
  slot.moves       : list[str]       move ids e.g. ["fakeout","flareblitz",...]

Species is extracted via parse_details(slot.details).species (engine/state.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.engine.state import PokemonState, parse_details

# MUST exist in _move_table() + pass enumerate_my_actions.
# Verified in D2b step 1; update if tackle is missing from engine/moves._move_table().
FALLBACK_BELIEF_MOVE = "tackle"


@dataclass(frozen=True)
class BeliefSide:
    """Belief snapshot for one side of the battle.

    ``frozen=True`` protects the bindings, NOT the inner containers.  Builders
    return fresh dicts/lists; callers treat BeliefSide as immutable (no shared
    mutation).

    Fields
    ------
    roster   : bench-only PokemonState entries  (ident → PokemonState for known
               side; always {} for opponent because bench is hidden).
    movesets : ident|species → ordered list of move ids.
    stats    : ident|species → {"spe": int}.
    quality  : ident|species → belief-quality flags tuple.
    """
    roster: dict[str, PokemonState]
    movesets: dict[str, list[str]]
    stats: dict[str, dict[str, int]]
    quality: dict[str, tuple[str, ...]]


def _quality(*flags: str) -> tuple[str, ...]:
    """Return sorted, deduplicated quality-flag tuple.

    No flags  → ("ok",)
    Any flags → tuple(sorted(set(flags)))
    """
    return ("ok",) if not flags else tuple(sorted(set(flags)))


def build_known_side(team_slots) -> BeliefSide:
    """Build a BeliefSide from our own team (fully known).

    Parameters
    ----------
    team_slots : list[PokemonSlot]
        ``req.side.pokemon`` — all slots in the request (active + bench).

    Returns
    -------
    BeliefSide
        roster   = bench slots only (active=False).
        movesets = all slots, keyed by ident, ordered as slot.moves.
        stats    = all slots, keyed by ident, {"spe": slot.stats["spe"]}.
        quality  = all slots ("ok",) — our team is fully known.
    """
    roster: dict[str, PokemonState] = {}
    movesets: dict[str, list[str]] = {}
    stats: dict[str, dict[str, int]] = {}
    quality: dict[str, tuple[str, ...]] = {}

    for slot in team_slots:
        ident = slot.ident
        movesets[ident] = list(slot.moves)
        stats[ident] = {"spe": int(slot.stats["spe"])}
        quality[ident] = _quality()  # fully known — no flags

        if not slot.active:
            # Build a bench PokemonState.  Parse species from details
            # ("Incineroar, L50, F" → "Incineroar") and hp/max_hp from
            # condition ("150/150").  If condition is missing or malformed,
            # fall back to hp=100/max_hp=None (safe default for bench mons
            # whose exact HP the belief doesn't need).
            parsed = parse_details(slot.details)
            hp = 100
            max_hp: int | None = None
            cond = slot.condition
            if "/" in cond:
                cur_s, rest = cond.split("/", 1)
                max_s = rest.split()[0]
                if cur_s.isdigit():
                    hp = int(cur_s)
                if max_s.isdigit():
                    max_hp = int(max_s)
            roster[ident] = PokemonState(
                species=parsed.species,
                level=parsed.level,
                gender=parsed.gender,
                hp=hp,
                max_hp=max_hp,
            )

    return BeliefSide(roster, movesets, stats, quality)

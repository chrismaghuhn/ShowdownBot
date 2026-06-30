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


# ---------------------------------------------------------------------------
# D2b: build_opponent_belief (active-only, prior-based, limited-view-safe)
# ---------------------------------------------------------------------------

def _merge_moveset(revealed: list[str], prior: list[str]) -> tuple[list[str], list[str]]:
    """Merge revealed moves (first) then prior fill; dedupe (first wins); cap 4.

    Parameters
    ----------
    revealed : list[str]
        Sorted move ids already seen in battle (from mon.moves).
    prior : list[str]
        Ordered move ids from move_priors for this species.

    Returns
    -------
    (merged, flags)
        merged : list[str] — up to 4 deduplicated move ids.
        flags  : list[str] — ["no_move_prior"] if merged is empty after combining.
    """
    flags: list[str] = []
    merged: list[str] = []
    seen: set[str] = set()

    from showdown_bot.engine.state import to_id
    for m in [*revealed, *prior]:          # revealed FIRST (wins), then prior fill
        mid = to_id(m)
        if mid not in seen:
            seen.add(mid)
            merged.append(mid)
        if len(merged) == 4:               # cap 4
            break

    if not merged:                          # no prior AND no revealed -> weak fallback
        merged = [FALLBACK_BELIEF_MOVE]
        flags.append("no_move_prior")

    return merged, flags


def _belief_speed(mon, field, side, spreads, speed_oracle) -> tuple[int, str | None]:
    """Estimate opponent speed via the speed oracle + likely_sets.

    Priority chain:
    1. oracle + spreads entry  -> likely_speed(preset=spreads.offense)      flag=None
    2. oracle only (no entry)  -> likely_speed(preset=SpreadPreset("Hardy",{})) flag="weak_speed_fallback"
    3. no oracle               -> 0                                          flag="weak_speed_fallback"

    Parameters
    ----------
    mon       : PokemonState
    field     : FieldState
    side      : str   — opponent side id
    spreads   : SpeciesSpreads | None  — likely_sets.get(to_id(species))
    speed_oracle : SpeedOracle | None
    """
    if speed_oracle is not None and spreads is not None:
        preset = spreads.offense
        item = preset.items[0] if preset.items else None
        return speed_oracle.likely_speed(mon, field, side, preset, item), None

    if speed_oracle is not None:
        from showdown_bot.engine.belief.hypotheses import SpreadPreset
        return (
            speed_oracle.likely_speed(mon, field, side, SpreadPreset("Hardy", {}), None),
            "weak_speed_fallback",
        )

    return 0, "weak_speed_fallback"


def build_opponent_belief(
    state,
    opp_side: str,
    *,
    likely_sets: dict,
    move_priors: dict,
    dex=None,
    book=None,
    speed_oracle=None,
) -> BeliefSide:
    """Build a BeliefSide for the opponent: active-only, prior-based, limited-view-safe.

    Reads ONLY ``state.sides[opp_side]["a"|"b"]`` (the two active slots) and public
    priors.  The ``roster`` is always ``{}`` — the bench is hidden.

    Parameters
    ----------
    state      : BattleState
    opp_side   : str   e.g. "p2"
    likely_sets: dict  species_id -> SpeciesSpreads (for speed oracle)
    move_priors: dict  species_id -> list[str]  ordered move priors
    dex, book  : unused (reserved for future)
    speed_oracle: SpeedOracle | None

    Structural limited-view guarantee
    ----------------------------------
    * No ``known_team`` / ``team`` / ``full_roster`` parameter (API-guard test).
    * Iterates the literal tuple ``("a", "b")``; any extra keys injected into
      ``state.sides[opp_side]`` (e.g. "c") are invisible to this function.
    """
    from showdown_bot.engine.state import to_id

    roster: dict[str, PokemonState] = {}            # always empty — bench is hidden
    movesets: dict[str, list[str]] = {}
    stats: dict[str, dict[str, int]] = {}
    quality: dict[str, tuple[str, ...]] = {}

    field = state.field

    for slot in ("a", "b"):                          # ONLY the two active slots
        mon = state.sides.get(opp_side, {}).get(slot)
        if mon is None:
            continue

        species = mon.species
        sid = to_id(species)

        # PokemonState.moves is a set[str] (unordered) -> sort for determinism
        revealed_sorted = sorted(mon.moves)
        prior = move_priors.get(sid, [])
        merged, flags = _merge_moveset(revealed_sorted, prior)

        spe, spe_flag = _belief_speed(mon, field, opp_side, likely_sets.get(sid), speed_oracle)
        if spe_flag:
            flags.append(spe_flag)

        # Key all three dicts by species (PokemonState has no ident field)
        movesets[species] = merged
        stats[species] = {"spe": spe}
        quality[species] = _quality(*flags)

    return BeliefSide(roster, movesets, stats, quality)


# ---------------------------------------------------------------------------
# D3: build_belief_for_side — thin dispatcher
# ---------------------------------------------------------------------------

def build_belief_for_side(
    state,
    side: str,
    *,
    our_side: str,
    known_team,
    likely_sets: dict,
    move_priors: dict,
    dex=None,
    book=None,
    speed_oracle=None,
) -> BeliefSide:
    """Thin dispatcher: routes to the appropriate builder based on which side is requested.

    * ``side == our_side`` → ``build_known_side(known_team)`` — full known team.
    * ``side != our_side`` → ``build_opponent_belief(...)`` — active-only, prior-based,
      limited-view-safe.  ``known_team`` is NOT passed to the opponent builder; the
      structural guarantee that the bench is hidden lives in the call site.

    Parameters
    ----------
    state       : BattleState
    side        : The side to build a belief for ("p1" or "p2").
    our_side    : The side we're deciding for (determines which builder to use).
    known_team  : list[PokemonSlot] — req.side.pokemon (only forwarded to known builder).
    likely_sets : dict  species_id -> SpeciesSpreads (for speed oracle in opp builder).
    move_priors : dict  species_id -> list[str]  ordered move priors (opp builder).
    dex, book   : Passed through to build_opponent_belief (unused today; reserved).
    speed_oracle: Passed through to build_opponent_belief.

    Returns
    -------
    BeliefSide
    """
    if side == our_side:
        return build_known_side(known_team)
    return build_opponent_belief(
        state, side,
        likely_sets=likely_sets,
        move_priors=move_priors,
        dex=dex,
        book=book,
        speed_oracle=speed_oracle,
        # known_team is intentionally NOT passed here (structural limited-view)
    )

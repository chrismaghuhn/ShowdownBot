"""Belief-agnostic BattleState -> BattleRequest adapter (Phase 3 slice 1c-B).

Confirmed field names (models/request.py):
  BattleRequest : active, side, rqid, force_switch (alias forceSwitch), team_preview, wait
  SideInfo      : name, id, pokemon
  PokemonSlot   : ident, details, condition, active, stats, moves, base_types, item
  ActiveSlot    : moves, can_terastallize (alias canTerastallize), trapped
  MoveSlot      : move, id, pp, maxpp, target, disabled
  Fainted active slot -> active[i] = None  AND  force_switch[i] = True.
  move_meta source: engine/moves.py  _move_table() / get_move_meta(mid).target
"""
from __future__ import annotations

from showdown_bot.engine.state import BattleState
from showdown_bot.models.request import (
    ActiveSlot,
    BattleRequest,
    MoveSlot,
    PokemonSlot,
    SideInfo,
)

# Active slot keys in the BattleState.sides dict (in order).
_ACTIVE_SLOTS = ("a", "b")


# ---------------------------------------------------------------------------
# Dependency sanitiser (Task 3 — kept here for completeness).
# ---------------------------------------------------------------------------

_CORE_DEP_KEYS = frozenset({
    "book", "calc", "oracle", "speed_oracle", "dex", "priors", "weights",
    "risk_lambda", "tera_margin", "rollout_horizon", "our_spreads", "opp_sets",
})


def _core_deps(deps: dict) -> dict:
    """Return only the keys that _choose_best_ja accepts (never splat state/trace/report)."""
    return {k: v for k, v in deps.items() if k in _CORE_DEP_KEYS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _condition_str(mon) -> str:
    """Return Showdown condition string for a PokemonState."""
    if mon.fainted or mon.hp == 0:
        return "0 fnt"
    max_hp = mon.max_hp if mon.max_hp is not None else 100
    return f"{mon.hp}/{max_hp}"


def _lookup(mapping: dict, ident: str, species: str, side: str) -> object:
    """Try ident, then species; raise ValueError if neither found."""
    if ident in mapping:
        return mapping[ident]
    if species in mapping:
        return mapping[species]
    raise ValueError(
        f"no entry for ident={ident!r} or species={species!r} on side {side!r}"
    )


def _build_move_slot(mid: str, move_meta: dict) -> MoveSlot:
    """Build a MoveSlot for a given move id using the real move-meta map."""
    meta = move_meta.get(mid)
    target = meta.target if meta is not None else "normal"
    return MoveSlot(
        move=mid,
        id=mid,
        pp=1,
        maxpp=1,
        target=target,
        disabled=False,
    )


def _can_terastallize(mon) -> str | None:
    """Return tera type string if the mon has an available tera, else None.

    A mon can terastallize if it has a tera_type recorded and has NOT yet
    terastallized this battle.
    """
    if mon.terastallized:
        return None
    return mon.tera_type  # may be None if not yet observed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesize_request(
    state: BattleState,
    side: str,
    *,
    roster: dict,
    movesets: dict,
    stats: dict,
    move_meta: dict,
) -> BattleRequest:
    """Build a minimal BattleRequest from a BattleState for one side.

    Args:
        state:     The current BattleState (only state.sides[side] active slots a/b are read).
        side:      Which side to synthesize for ("p1" or "p2").
        roster:    dict[side -> dict[ident -> PokemonState]] — bench mons (NOT active).
        movesets:  dict[side -> dict[ident|species -> list[str]]] — move ids per mon.
        stats:     dict[side -> dict[ident|species -> dict[str, int]]] — at minimum {"spe": ...}.
        move_meta: dict[move_id -> MoveMeta] — from engine/moves._move_table().

    Returns:
        A BattleRequest accepted by enumerate_my_actions / _choose_best_ja.

    Raises:
        ValueError: if the caller did not supply roster/movesets/stats for this side
                    (belief guard — never reads hidden opponent state).
    """
    # Belief guard: if this side has no entry in any of the caller-supplied dicts,
    # we raise instead of reading hidden state.
    side_roster = roster.get(side)
    side_movesets = movesets.get(side)
    side_stats = stats.get(side)
    if side_roster is None or side_movesets is None or side_stats is None:
        raise ValueError(
            f"No caller-supplied roster/movesets/stats for side {side!r}. "
            "Pass explicit belief dicts — never read hidden opponent state."
        )

    active_state = state.sides.get(side, {})

    # ------------------------------------------------------------------
    # 1. Collect active mons (slots a, b) from state.sides[side].
    # ------------------------------------------------------------------
    active_mons: list[tuple[str, object | None]] = []   # (slot_key, PokemonState|None)
    for slot_key in _ACTIVE_SLOTS:
        mon = active_state.get(slot_key)
        active_mons.append((slot_key, mon))

    # Trim trailing None slots (e.g. in a 1-mon side the "b" slot may not exist).
    # Keep at least 1 slot so the request is valid.
    while len(active_mons) > 1 and active_mons[-1][1] is None:
        active_mons.pop()

    # Idents for active mons (for bench-dedupe).
    active_idents: set[str] = set()
    for _slot, mon in active_mons:
        if mon is not None:
            ident = f"{side}: {mon.species}"
            active_idents.add(ident)

    # ------------------------------------------------------------------
    # 2. Build PokemonSlot list: active mons first, then bench.
    # ------------------------------------------------------------------
    pokemon_slots: list[PokemonSlot] = []

    for _slot, mon in active_mons:
        if mon is None:
            continue
        ident = f"{side}: {mon.species}"
        fainted = mon.fainted or mon.hp == 0
        if fainted:
            # Fainted active mons need a PokemonSlot so _active_mon_fainted can find
            # "fnt" in condition, but moves/stats are irrelevant — skip costly lookup.
            pokemon_slots.append(
                PokemonSlot(
                    ident=ident,
                    details=mon.species,
                    condition="0 fnt",
                    active=True,
                    stats={},
                    moves=[],
                )
            )
        else:
            moveset = list(_lookup(side_movesets, ident, mon.species, side))
            spe_map = _lookup(side_stats, ident, mon.species, side)
            pokemon_slots.append(
                PokemonSlot(
                    ident=ident,
                    details=mon.species,
                    condition=_condition_str(mon),
                    active=True,
                    stats=dict(spe_map),
                    moves=moveset,
                )
            )

    # Bench: roster entries NOT currently active by ident.
    for bench_ident, bench_mon in side_roster.items():
        if bench_ident in active_idents:
            continue  # skip — already in active list
        moveset = list(_lookup(side_movesets, bench_ident, bench_mon.species, side))
        spe_map = _lookup(side_stats, bench_ident, bench_mon.species, side)
        pokemon_slots.append(
            PokemonSlot(
                ident=bench_ident,
                details=bench_mon.species,
                condition=_condition_str(bench_mon),
                active=False,
                stats=dict(spe_map),
                moves=moveset,
            )
        )

    # ------------------------------------------------------------------
    # 3. Build active list and force_switch.
    # ------------------------------------------------------------------
    active_list: list[ActiveSlot | None] = []
    force_switch: list[bool] = []
    any_force = False

    for _slot, mon in active_mons:
        if mon is None:
            # Empty slot (one mon left in doubles) — pass through as None.
            active_list.append(None)
            force_switch.append(False)
            continue

        fainted = mon.fainted or mon.hp == 0
        if fainted:
            # Fainted active slot: None in active list, True in force_switch.
            active_list.append(None)
            force_switch.append(True)
            any_force = True
        else:
            ident = f"{side}: {mon.species}"
            moveset_ids = _lookup(side_movesets, ident, mon.species, side)
            move_slots = [_build_move_slot(mid, move_meta) for mid in moveset_ids]
            can_tera = _can_terastallize(mon)
            active_list.append(
                ActiveSlot(
                    moves=move_slots,
                    can_terastallize=can_tera,
                )
            )
            force_switch.append(False)

    # ------------------------------------------------------------------
    # 4. Assemble BattleRequest.
    # ------------------------------------------------------------------
    rqid_str = f"rollout-{getattr(state, 'turn', 0)}-{side}"
    # BattleRequest.rqid is int; encode as a deterministic synthetic int.
    rqid_int = hash(rqid_str) % (2**31)

    return BattleRequest(
        active=active_list if not any_force else [],
        side=SideInfo(id=side, pokemon=pokemon_slots),
        rqid=rqid_int,
        force_switch=force_switch if any_force else None,
        team_preview=False,
    )

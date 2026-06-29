from __future__ import annotations

import re
from dataclasses import dataclass, field

from showdown_bot.engine.state import FieldState


def to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass(frozen=True)
class MoveMeta:
    """Minimal move metadata for the resolver.

    Phase 2 ships a small hand table; the API is shaped so the data can later be
    imported wholesale from pokemon-showdown/data/moves.ts (generated JSON):
    priority, target, category and flags all mirror PS field names.
    """

    id: str
    name: str
    priority: int = 0
    category: str = "physical"  # physical | special | status
    target: str = "normal"  # normal | adjacentFoe | allAdjacentFoes | allAdjacent | self | adjacentAlly | all
    base_power: int = 0
    move_type: str | None = None
    flags: frozenset[str] = field(default_factory=frozenset)
    # Terrain that grants +1 priority (Grassy Glide etc.).
    terrain_priority: str | None = None

    @property
    def is_damaging(self) -> bool:
        return self.category in ("physical", "special")

    @property
    def is_spread(self) -> bool:
        return self.target in ("allAdjacentFoes", "allAdjacent")

    @property
    def hits_foe(self) -> bool:
        return self.target in ("normal", "adjacentFoe", "allAdjacentFoes", "allAdjacent", "randomNormal")


def _m(name, priority=0, category="physical", target="normal", base_power=0,
       move_type=None, flags=(), terrain_priority=None) -> MoveMeta:
    base_flags = set(flags)
    # Damaging foe moves and most status moves are blocked by Protect unless
    # they explicitly bypass it; encode "protect" = "affected by Protect".
    return MoveMeta(
        id=to_id(name),
        name=name,
        priority=priority,
        category=category,
        target=target,
        base_power=base_power,
        move_type=move_type,
        flags=frozenset(base_flags),
        terrain_priority=terrain_priority,
    )


_TABLE: dict[str, MoveMeta] = {
    m.id: m
    for m in [
        # Priority / protection
        _m("Fake Out", priority=3, category="physical", target="normal", base_power=40, move_type="Normal", flags={"protect", "contact", "flinch"}),
        _m("Protect", priority=4, category="status", target="self"),
        _m("Detect", priority=4, category="status", target="self"),
        _m("Wide Guard", priority=3, category="status", target="self"),
        _m("Quick Attack", priority=1, base_power=40, move_type="Normal", flags={"protect", "contact"}),
        _m("Extreme Speed", priority=2, base_power=80, move_type="Normal", flags={"protect", "contact"}),
        _m("Aqua Jet", priority=1, base_power=40, move_type="Water", flags={"protect", "contact"}),
        _m("Sucker Punch", priority=1, base_power=70, move_type="Dark", flags={"protect", "contact"}),
        _m("Grassy Glide", priority=0, base_power=55, move_type="Grass", flags={"protect", "contact"}, terrain_priority="Grassy"),
        # Redirection
        _m("Rage Powder", priority=2, category="status", target="self", flags={"powder"}),
        _m("Follow Me", priority=2, category="status", target="self"),
        # Speed control / support
        _m("Tailwind", priority=0, category="status", target="self"),
        _m("Trick Room", priority=-7, category="status", target="self"),
        _m("Icy Wind", priority=0, category="special", target="allAdjacentFoes", base_power=55, move_type="Ice", flags={"protect"}),
        _m("Spore", priority=0, category="status", target="normal", flags={"protect", "powder"}),
        _m("Will-O-Wisp", priority=0, category="status", target="normal", flags={"protect"}),
        # Common damage
        _m("Moonblast", category="special", base_power=95, move_type="Fairy", flags={"protect"}),
        _m("Shadow Ball", category="special", base_power=80, move_type="Ghost", flags={"protect"}),
        _m("Flare Blitz", category="physical", base_power=120, move_type="Fire", flags={"protect", "contact"}),
        _m("Knock Off", category="physical", base_power=65, move_type="Dark", flags={"protect", "contact"}),
        _m("Wood Hammer", category="physical", base_power=120, move_type="Grass", flags={"protect", "contact"}),
        _m("Close Combat", category="physical", base_power=120, move_type="Fighting", flags={"protect", "contact"}),
        _m("Earthquake", category="physical", target="allAdjacent", base_power=100, move_type="Ground", flags={"protect"}),
        _m("Heat Wave", category="special", target="allAdjacentFoes", base_power=95, move_type="Fire", flags={"protect"}),
        _m("Make It Rain", category="special", target="allAdjacentFoes", base_power=120, move_type="Steel", flags={"protect"}),
        _m("Dazzling Gleam", category="special", target="allAdjacentFoes", base_power=80, move_type="Fairy", flags={"protect"}),
    ]
}


def get_move_meta(name_or_id: str) -> MoveMeta:
    """Look up move metadata; unknown moves default to a blockable single-target
    physical move at priority 0 (conservative for the resolver)."""
    mid = to_id(name_or_id)
    if mid in _TABLE:
        return _TABLE[mid]
    return MoveMeta(id=mid, name=name_or_id, base_power=80, flags=frozenset({"protect"}))


def move_priority(meta: MoveMeta, field: FieldState | None = None) -> int:
    pr = meta.priority
    if meta.terrain_priority and field is not None and field.terrain:
        if meta.terrain_priority.lower() in field.terrain.lower():
            pr += 1
    return pr


def blocks_move(meta: MoveMeta, field: FieldState | None = None) -> bool:
    """Whether an active Protect on the target would block this move.

    Kept as a function (not ``damage = 0``) so future flags (sound/bypass/
    spread/Feint/consecutive-fail) extend cleanly.
    """
    if not meta.hits_foe:
        return False
    return "protect" in meta.flags


def can_redirect(redirect_move_id: str, attacker_mon, attacker_types=None) -> bool:
    """Whether a redirector (Follow Me / Rage Powder) pulls a single-target foe
    move from ``attacker_mon``.

    Follow Me redirects everything. Rage Powder is a powder move: Grass-types,
    Safety Goggles and Overcoat are immune (Grass requires known typing, so we
    only filter it when ``attacker_types`` is provided).
    """
    if redirect_move_id == "followme":
        return True
    if redirect_move_id == "ragepowder":
        if attacker_mon is not None:
            if getattr(attacker_mon, "ability", None) == "Overcoat":
                return False
            if getattr(attacker_mon, "item_known", False) and getattr(attacker_mon, "item", None) == "Safety Goggles":
                return False
        if attacker_types and "Grass" in attacker_types:
            return False
        return True
    return False

from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from showdown_bot.engine.state import FieldState, PokemonState

_CONFIG = Path(__file__).resolve().parents[3] / "config"
_MOVEDATA = _CONFIG / "moves" / "movedata.json"
_EFFECT_CLASSES = _CONFIG / "moves" / "effect_classes.yaml"

# Gen-9 terrain-priority moves (the one field @pkmn/dex does not expose as a
# simple value). Grassy Glide gains +1 priority in Grassy Terrain.
_TERRAIN_PRIORITY: dict[str, str] = {"grassyglide": "Grassy"}


def to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _tuple(value) -> tuple | None:
    if value is None:
        return None
    if isinstance(value, list):
        return tuple(value)
    return value


@dataclass(frozen=True)
class MoveMeta:
    """Move metadata for the resolver, data-driven from ``config/moves/movedata.json``
    (generated from @pkmn/dex). The mechanical fields mirror Pokemon-Showdown
    names; the curated ``effect_classes`` overlay (Phase A4) adds heuristic
    semantics.

    The structured effect fields are excluded from ``compare``/``hash`` (they are
    dicts/lists) so ``MoveMeta`` stays hashable on its identity fields.
    """

    id: str
    name: str
    priority: int = 0
    category: str = "physical"  # physical | special | status
    target: str = "normal"
    base_power: int = 0
    accuracy: int | None = None
    move_type: str | None = None
    flags: frozenset[str] = field(default_factory=frozenset)
    terrain_priority: str | None = None
    # --- enriched semantic fields (from @pkmn/dex) ---
    status: str | None = field(default=None, compare=False)
    volatile_status: str | None = field(default=None, compare=False)
    side_condition: str | None = field(default=None, compare=False)
    slot_condition: str | None = field(default=None, compare=False)
    weather: str | None = field(default=None, compare=False)
    terrain: str | None = field(default=None, compare=False)
    boosts: dict | None = field(default=None, compare=False)
    self_effect: dict | None = field(default=None, compare=False)
    secondary: dict | None = field(default=None, compare=False)
    drain: tuple | None = field(default=None, compare=False)
    recoil: tuple | None = field(default=None, compare=False)
    multihit: object | None = field(default=None, compare=False)
    # --- curated overlay (populated in Phase A4) ---
    effect_classes: tuple[str, ...] = field(default=(), compare=False)
    effect_params: dict = field(default_factory=dict, compare=False)

    @property
    def is_damaging(self) -> bool:
        return self.category in ("physical", "special")

    @property
    def is_spread(self) -> bool:
        return self.target in ("allAdjacentFoes", "allAdjacent")

    @property
    def hits_foe(self) -> bool:
        return self.target in ("normal", "adjacentFoe", "allAdjacentFoes", "allAdjacent", "randomNormal")


def _meta_from_record(rec: dict) -> MoveMeta:
    if "accuracy" not in rec:
        raise KeyError(f"move record {rec.get('id', '<unknown>')} is missing 'accuracy' — "
                        f"regenerate movedata.json (tools/gen/gen_movedata.mjs)")
    return MoveMeta(
        id=rec["id"],
        name=rec["name"],
        priority=int(rec.get("priority") or 0),
        category=(rec.get("category") or "Physical").lower(),
        target=rec.get("target") or "normal",
        base_power=int(rec.get("basePower") or 0),
        accuracy=rec["accuracy"],
        move_type=rec.get("type"),
        flags=frozenset(rec.get("flags") or ()),
        terrain_priority=_TERRAIN_PRIORITY.get(rec["id"]),
        status=rec.get("status"),
        volatile_status=rec.get("volatileStatus"),
        side_condition=rec.get("sideCondition"),
        slot_condition=rec.get("slotCondition"),
        weather=rec.get("weather"),
        terrain=rec.get("terrain"),
        boosts=rec.get("boosts"),
        self_effect=rec.get("self"),
        secondary=rec.get("secondary"),
        drain=_tuple(rec.get("drain")),
        recoil=_tuple(rec.get("recoil")),
        multihit=_tuple(rec.get("multihit")),
    )


@functools.lru_cache(maxsize=1)
def _effect_overlay() -> dict[str, dict]:
    """Curated move_id -> {classes, params} overlay. Missing file -> no overlay."""
    try:
        return yaml.safe_load(_EFFECT_CLASSES.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


@functools.lru_cache(maxsize=1)
def _move_table() -> dict[str, MoveMeta]:
    raw = json.loads(_MOVEDATA.read_text(encoding="utf-8"))
    overlay = _effect_overlay()
    table: dict[str, MoveMeta] = {}
    for mid, rec in raw["moves"].items():
        meta = _meta_from_record(rec)
        entry = overlay.get(mid)
        if entry:
            meta = replace(
                meta,
                effect_classes=tuple(entry.get("classes") or ()),
                effect_params=dict(entry.get("params") or {}),
            )
        table[mid] = meta
    return table


def get_move_meta(name_or_id: str) -> MoveMeta:
    """Look up move metadata; unknown moves default to a blockable single-target
    physical move at priority 0 (conservative for the resolver)."""
    mid = to_id(name_or_id)
    table = _move_table()
    meta = table.get(mid)
    if meta is not None:
        return meta
    return MoveMeta(id=mid, name=name_or_id, base_power=80, flags=frozenset({"protect"}))


def is_known_move(name_or_id: str) -> bool:
    """Whether a move id/name exists in the generated move table (vs.
    get_move_meta's conservative damaging default for unknown ids)."""
    return to_id(name_or_id) in _move_table()


def move_priority(meta: MoveMeta, field: FieldState | None = None) -> int:
    pr = meta.priority
    if meta.terrain_priority and field is not None and field.terrain:
        if meta.terrain_priority.lower() in field.terrain.lower():
            pr += 1
    return pr


def hit_probability(
    meta: MoveMeta, attacker: PokemonState, target: PokemonState, field: FieldState | None = None,
) -> float | None:
    """Probability this move connects. ``None`` means unconditionally guaranteed to hit
    (no branching needed): either ``meta.accuracy is None`` (the normalized @pkmn/dex
    always-hit sentinel) or a weather rule that bypasses the stage pipeline entirely
    (Blizzard in Snow, Thunder/Hurricane in Rain).

    v1 scope only: base accuracy, accuracy/evasion boost stages, and exactly the two weather
    rules below -- verified against the pinned pokemon-showdown server commit
    (config/eval/provenance.yaml), not assumed. Ability/item/field modifiers beyond these are
    a documented v1.1 limitation (spec Sec.3), not silently ignored.
    """
    if meta.accuracy is None:
        return None
    weather = (field.weather or "").lower() if field is not None else ""
    base = meta.accuracy
    if meta.id in ("thunder", "hurricane"):
        if "rain" in weather:
            return None  # move.accuracy = true in PS -> stage pipeline bypassed entirely
        if "sun" in weather:
            base = 50  # move.accuracy = 50 in PS -> a NUMBER, still goes through stages below
    elif meta.id == "blizzard" and "snow" in weather:
        return None
    acc_stage = max(-6, min(6, attacker.boosts.get("accuracy", 0)))
    stage = max(-6, min(6, acc_stage - target.boosts.get("evasion", 0)))
    if stage > 0:
        raw = base * (3 + stage) / 3
    elif stage < 0:
        raw = base * 3 / (3 - stage)
    else:
        raw = base
    p = int(raw) / 100.0  # sim/battle-actions.ts truncates the intermediate accuracy to an int
    return max(0.0, min(1.0, p))


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

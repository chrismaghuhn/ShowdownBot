from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from showdown_bot.engine.generated_data_hash import verify_embedded_data_hash

_CONFIG = Path(__file__).resolve().parents[3] / "config"
_ITEMDATA = _CONFIG / "items" / "itemdata.json"
_ITEM_EFFECT_CLASSES = _CONFIG / "items" / "item_effect_classes.yaml"


class ItemdataStaleError(RuntimeError):
    """Raised when itemdata.json embedded data_hash does not match content."""


def to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _verify_itemdata_hash(raw: dict) -> str:
    return verify_embedded_data_hash(
        raw,
        "items",
        label="itemdata.json",
        stale_error=ItemdataStaleError,
    )


def itemdata_content_hash() -> str:
    raw = json.loads(_ITEMDATA.read_text(encoding="utf-8"))
    return _verify_itemdata_hash(raw)


@dataclass(frozen=True)
class ItemMeta:
    """Item metadata, data-driven from ``config/items/itemdata.json`` (generated
    from @pkmn/dex) plus the curated ``item_effect_classes.yaml`` overlay.

    ``classes`` carries the heuristic semantics (residual_heal, threshold_heal,
    speed, damage_stat, effect_block, ...). ``params`` is excluded from
    compare/hash so ItemMeta stays hashable on its identity fields.
    """

    id: str
    name: str
    is_berry: bool = False
    is_choice: bool = False
    classes: tuple[str, ...] = ()
    params: dict = field(default_factory=dict, compare=False)
    mega_stone: dict[str, str] = field(default_factory=dict, compare=False)


@functools.lru_cache(maxsize=1)
def _item_overlay() -> dict[str, dict]:
    try:
        return yaml.safe_load(_ITEM_EFFECT_CLASSES.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


@functools.lru_cache(maxsize=1)
def _item_table() -> dict[str, ItemMeta]:
    raw = json.loads(_ITEMDATA.read_text(encoding="utf-8"))
    _verify_itemdata_hash(raw)
    overlay = _item_overlay()
    table: dict[str, ItemMeta] = {}
    for iid, rec in raw["items"].items():
        entry = overlay.get(iid) or {}
        table[iid] = ItemMeta(
            id=rec["id"],
            name=rec["name"],
            is_berry=bool(rec.get("isBerry")),
            is_choice=bool(rec.get("isChoice")),
            classes=tuple(entry.get("classes") or ()),
            params=dict(entry.get("params") or {}),
            mega_stone={
                to_id(base_species): form_name
                for base_species, form_name in (rec.get("megaStone") or {}).items()
            },
        )
    return table


def get_item_meta(name_or_id: str) -> ItemMeta:
    """Look up item metadata; unknown items default to no semantic classes."""
    iid = to_id(name_or_id)
    meta = _item_table().get(iid)
    if meta is not None:
        return meta
    return ItemMeta(id=iid, name=name_or_id)

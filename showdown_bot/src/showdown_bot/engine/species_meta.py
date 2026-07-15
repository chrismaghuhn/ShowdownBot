from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.engine.items import to_id

_CONFIG = Path(__file__).resolve().parents[3] / "config"
_SPECIESDATA = _CONFIG / "species" / "speciesdata.json"


class SpeciesMetaStaleError(RuntimeError):
    """Raised when speciesdata.json embedded data_hash does not match content."""


@dataclass(frozen=True)
class SpeciesFormMeta:
    form_species_id: str
    form_species_name: str
    base_species_id: str
    base_species_name: str
    types: tuple[str, ...]
    base_stats: dict[str, int]
    ability_slot0: str = ""
    required_item: str | None = None


def _embedded_hash(raw: dict, table_key: str) -> str:
    payload = json.dumps(
        raw[table_key],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def speciesdata_content_hash() -> str:
    raw = json.loads(_SPECIESDATA.read_text(encoding="utf-8"))
    return raw["data_hash"]


@functools.lru_cache(maxsize=1)
def species_meta_table() -> dict[str, SpeciesFormMeta]:
    raw = json.loads(_SPECIESDATA.read_text(encoding="utf-8"))
    expected = raw.get("data_hash")
    if expected is not None:
        actual = _embedded_hash(raw, "species")
        if actual != expected:
            raise SpeciesMetaStaleError(
                f"speciesdata.json stale: embedded {expected!r} != computed {actual!r}"
            )
    table: dict[str, SpeciesFormMeta] = {}
    for sid, rec in raw["species"].items():
        abilities = rec.get("abilities") or {}
        table[sid] = SpeciesFormMeta(
            form_species_id=rec["id"],
            form_species_name=rec["name"],
            base_species_id=to_id(rec["baseSpecies"]),
            base_species_name=rec["baseSpecies"],
            types=tuple(rec.get("types") or ()),
            base_stats=dict(rec.get("baseStats") or {}),
            ability_slot0=abilities.get("0") or "",
            required_item=rec.get("requiredItem"),
        )
    return table


def get_species_form_meta(name_or_id: str) -> SpeciesFormMeta | None:
    return species_meta_table().get(to_id(name_or_id))

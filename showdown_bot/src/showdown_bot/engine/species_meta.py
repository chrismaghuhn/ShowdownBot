from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field
from pathlib import Path

from showdown_bot.engine.generated_data_hash import verify_embedded_data_hash
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
    base_stats: dict[str, int] = field(default_factory=dict, compare=False)
    ability_slot0: str = ""
    required_item: str | None = None


def _verify_speciesdata_hash(raw: dict) -> str:
    return verify_embedded_data_hash(
        raw,
        "species",
        label="speciesdata.json",
        stale_error=SpeciesMetaStaleError,
    )


def speciesdata_content_hash() -> str:
    raw = json.loads(_SPECIESDATA.read_text(encoding="utf-8"))
    return _verify_speciesdata_hash(raw)


@functools.lru_cache(maxsize=1)
def species_meta_table() -> dict[str, SpeciesFormMeta]:
    raw = json.loads(_SPECIESDATA.read_text(encoding="utf-8"))
    _verify_speciesdata_hash(raw)
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

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from showdown_bot.analysis.generalisation.contracts import SchemaError, load_mapping, sha256_id
from showdown_bot.eval.panel import PanelError, team_content_hash


class CatalogError(SchemaError):
    pass


def _norm(value: str) -> str:
    return re.sub(r"\s+", "_", unicodedata.normalize("NFKC", value).strip().lower())


def _move_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


@dataclass(frozen=True)
class TeamRecord:
    team_hash: str
    team_id: str
    team_path: str
    archetype: str
    declared_split: str


@dataclass(frozen=True)
class TeamCatalog:
    by_hash: dict[str, TeamRecord]
    catalog_hash: str


@dataclass(frozen=True)
class ExposureManifest:
    exposure_id: str
    cutoff_utc: str
    exposed_team_hashes: frozenset[str]
    exposed_archetypes: frozenset[str]
    exposure_hash: str


@dataclass(frozen=True)
class SpeedControlTaxonomy:
    categories: dict[str, frozenset[str]]
    taxonomy_hash: str


_TEAM_FIELDS = {"team_hash", "team_id", "team_path", "archetype", "declared_split"}
_SPLITS = {"train", "dev", "heldout", "external"}
_CATEGORIES = {"tailwind", "trick_room", "speed_reduction", "speed_boost"}


def load_team_catalog(path, *, teams_root=".", verify_content=True) -> TeamCatalog:
    raw = load_mapping(path)
    if set(raw) != {"schema_version", "teams"} or raw["schema_version"] != "team-catalog-v1":
        raise CatalogError("team catalog schema must be team-catalog-v1 with teams")
    if not isinstance(raw["teams"], list) or not raw["teams"]:
        raise CatalogError("team catalog teams must be non-empty")
    by_hash = {}
    for index, item in enumerate(raw["teams"]):
        if not isinstance(item, dict) or set(item) != _TEAM_FIELDS:
            raise CatalogError(f"team {index} fields invalid")
        archetype = _norm(str(item["archetype"]))
        split = str(item["declared_split"])
        if not archetype or split not in _SPLITS:
            raise CatalogError(f"team {index} archetype or split invalid")
        record = TeamRecord(str(item["team_hash"]), str(item["team_id"]),
                            str(item["team_path"]), archetype, split)
        if record.team_hash in by_hash:
            raise CatalogError(f"duplicate team hash {record.team_hash}")
        if verify_content:
            try:
                actual = team_content_hash(str(teams_root), record.team_path)
            except PanelError as exc:
                raise CatalogError(str(exc)) from exc
            if actual != record.team_hash:
                raise CatalogError(f"team hash mismatch for {record.team_id}")
        by_hash[record.team_hash] = record
    return TeamCatalog(by_hash, sha256_id(raw))


def load_exposure(path, catalog: TeamCatalog) -> ExposureManifest:
    raw = load_mapping(path)
    required = {"schema_version", "exposure_id", "cutoff_utc", "allowed_sources",
                "exposed_team_hashes", "exposed_archetypes"}
    if set(raw) != required or raw["schema_version"] != "team-exposure-v1":
        raise CatalogError("exposure schema invalid")
    if set(raw["allowed_sources"]) - {"training", "development"}:
        raise CatalogError("exposure contains a forbidden source")
    hashes = frozenset(map(str, raw["exposed_team_hashes"]))
    missing = hashes - set(catalog.by_hash)
    if missing:
        raise CatalogError(f"exposure hashes absent from catalog: {sorted(missing)}")
    heldout = sorted(h for h in hashes if catalog.by_hash[h].declared_split == "heldout")
    if heldout:
        raise CatalogError(f"heldout hashes cannot be exposed: {heldout}")
    archetypes = frozenset(_norm(str(v)) for v in raw["exposed_archetypes"])
    return ExposureManifest(str(raw["exposure_id"]), str(raw["cutoff_utc"]), hashes,
                            archetypes, sha256_id(raw))


def load_speed_taxonomy(path) -> SpeedControlTaxonomy:
    raw = load_mapping(path)
    if set(raw) != {"schema_version", "categories"}:
        raise CatalogError("speed taxonomy fields invalid")
    if raw["schema_version"] != "speed-control-taxonomy-v1":
        raise CatalogError("speed taxonomy schema invalid")
    if not isinstance(raw["categories"], dict) or set(raw["categories"]) != _CATEGORIES:
        raise CatalogError("speed taxonomy categories invalid")
    categories = {key: frozenset(_move_id(str(v)) for v in values)
                  for key, values in raw["categories"].items()}
    seen = set()
    for key in sorted(categories):
        overlap = seen & set(categories[key])
        if overlap:
            raise CatalogError(f"moves appear in multiple categories: {sorted(overlap)}")
        seen.update(categories[key])
    return SpeedControlTaxonomy(categories, sha256_id(raw))


def classify_novelty(team_hash: str | None, catalog: TeamCatalog,
                     exposure: ExposureManifest) -> str:
    if not team_hash or team_hash not in catalog.by_hash:
        return "unknown_provenance"
    if team_hash in exposure.exposed_team_hashes:
        return "known_team"
    if catalog.by_hash[team_hash].archetype in exposure.exposed_archetypes:
        return "unseen_team_known_archetype"
    return "unseen_archetype"


def static_speed_profile(team_path, taxonomy: SpeedControlTaxonomy) -> str:
    try:
        lines = Path(team_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return "unavailable"
    moves = {_move_id(line[2:].strip()) for line in lines if line.startswith("- ")}
    active = [name for name, members in taxonomy.categories.items() if moves & members]
    if not active:
        return "none"
    return f"{active[0]}_only" if len(active) == 1 else "mixed"

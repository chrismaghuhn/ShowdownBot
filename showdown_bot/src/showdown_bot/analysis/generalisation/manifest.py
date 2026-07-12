from __future__ import annotations

from dataclasses import dataclass
from showdown_bot.analysis.generalisation.catalog import (
    ExposureManifest, TeamCatalog, classify_novelty,
)
from showdown_bot.analysis.generalisation.contracts import (
    AnalysisPolicy, SchemaError, load_mapping, sha256_id,
)
from showdown_bot.eval.policies import is_known, is_reproducible


class ManifestError(SchemaError):
    pass


@dataclass(frozen=True)
class CellSpec:
    cell_id: str
    axes: tuple[tuple[str, str], ...]
    protected: bool
    required_unique_seeds: int

    def axis(self, name: str) -> str:
        return dict(self.axes)[name]


@dataclass(frozen=True)
class GeneralisationManifest:
    manifest_id: str
    format_ids: tuple[str, ...]
    splits: tuple[str, ...]
    hero_team_hashes: tuple[str, ...]
    opponent_team_hashes: tuple[str, ...]
    opponent_policies: tuple[str, ...]
    required_axes: tuple[str, ...]
    required_unique_seeds_per_cell: int
    side_control: str
    cells: tuple[CellSpec, ...]
    manifest_hash: str


_FIELDS = {"schema_version", "manifest_id", "format_ids", "splits", "hero_team_hashes",
           "opponent_team_hashes", "opponent_policies", "required_axes", "protected_cells",
           "required_unique_seeds_per_cell", "side_control"}
_AXES = {"hero_team_hash", "hero_archetype", "hero_novelty", "opponent_team_hash",
         "opponent_archetype", "opponent_novelty", "opponent_policy", "panel_split",
         "format_id", "hero_side"}


def _feasible_axis_rows(raw, catalog, exposure):
    rows = []
    for hero_hash in map(str, raw["hero_team_hashes"]):
        hero = catalog.by_hash[hero_hash]
        for opponent_hash in map(str, raw["opponent_team_hashes"]):
            opponent = catalog.by_hash[opponent_hash]
            for split in map(str, raw["splits"]):
                if opponent.declared_split != split:
                    continue
                for opponent_policy in map(str, raw["opponent_policies"]):
                    for format_id in map(str, raw["format_ids"]):
                        base = {
                            "hero_team_hash": hero.team_hash,
                            "hero_archetype": hero.archetype,
                            "hero_novelty": classify_novelty(hero.team_hash, catalog, exposure)
                                if exposure is not None else "unknown_provenance",
                            "opponent_team_hash": opponent.team_hash,
                            "opponent_archetype": opponent.archetype,
                            "opponent_novelty": classify_novelty(opponent.team_hash, catalog, exposure)
                                if exposure is not None else "unknown_provenance",
                            "opponent_policy": opponent_policy, "panel_split": split,
                            "format_id": format_id,
                        }
                        sides = ("p1", "p2") if raw["side_control"] == "verified_executor" \
                            else ("unavailable",)
                        for hero_side in sides:
                            rows.append({**base, "hero_side": hero_side})
    if not rows:
        raise ManifestError("manifest has no feasible concrete team rows")
    return rows


def load_generalisation_manifest(path, catalog: TeamCatalog, policy: AnalysisPolicy,
                                 exposure: ExposureManifest | None = None) -> GeneralisationManifest:
    raw = load_mapping(path)
    if set(raw) != _FIELDS or raw["schema_version"] != "generalisation-manifest-v1":
        raise ManifestError("generalisation manifest fields or version invalid")
    for key in ("format_ids", "splits", "hero_team_hashes", "opponent_team_hashes",
                "opponent_policies", "required_axes"):
        if not isinstance(raw[key], list) or not raw[key]:
            raise ManifestError(f"{key} must be a non-empty list")
    team_hashes = set(map(str, raw["hero_team_hashes"] + raw["opponent_team_hashes"]))
    if team_hashes - set(catalog.by_hash):
        raise ManifestError("manifest contains a team absent from catalog")
    if set(raw["splits"]) - {"dev", "heldout"}:
        raise ManifestError("splits must be dev or heldout")
    if set(raw["required_axes"]) - _AXES or len(set(raw["required_axes"])) != len(raw["required_axes"]):
        raise ManifestError("required_axes contain unknown or duplicate entries")
    if raw["side_control"] not in {"observed_only", "verified_executor"}:
        raise ManifestError("side_control invalid")
    if raw["side_control"] == "observed_only" and "hero_side" in raw["required_axes"]:
        raise ManifestError("hero_side requires verified_executor")
    if exposure is None and ({"hero_novelty", "opponent_novelty"} & set(raw["required_axes"])):
        raise ManifestError("novelty axes require an exposure manifest")
    for opponent_policy in raw["opponent_policies"]:
        if not is_known(str(opponent_policy)):
            raise ManifestError(f"unknown opponent policy {opponent_policy}")
        if not policy.allow_nonreproducible_policies and not is_reproducible(str(opponent_policy)):
            raise ManifestError(f"non-reproducible opponent policy {opponent_policy}")
    required = int(raw["required_unique_seeds_per_cell"])
    if required < policy.gate_min_unique_seeds_per_cell:
        raise ManifestError("protected cells require at least the gate minimum")
    axes = tuple(map(str, raw["required_axes"]))
    protected_raw = raw["protected_cells"]
    provisional_by_id = {}
    for row in _feasible_axis_rows(raw, catalog, exposure):
        pairs = tuple(sorted((name, str(row[name])) for name in axes))
        provisional_by_id[sha256_id(dict(pairs), 20)] = pairs
    provisional = sorted(provisional_by_id.items())
    all_ids = {cell_id for cell_id, _ in provisional}
    if protected_raw == "all_materialized":
        protected_ids = all_ids
    elif isinstance(protected_raw, list) and set(map(str, protected_raw)) <= all_ids:
        protected_ids = set(map(str, protected_raw))
    else:
        raise ManifestError("protected_cells must be all_materialized or valid cell ids")
    cells = tuple(CellSpec(cell_id, pairs, cell_id in protected_ids, required)
                  for cell_id, pairs in sorted(provisional))
    return GeneralisationManifest(
        str(raw["manifest_id"]), tuple(map(str, raw["format_ids"])),
        tuple(map(str, raw["splits"])), tuple(map(str, raw["hero_team_hashes"])),
        tuple(map(str, raw["opponent_team_hashes"])),
        tuple(map(str, raw["opponent_policies"])), axes, required,
        str(raw["side_control"]), cells, sha256_id(raw))


def manifest_to_dict(manifest: GeneralisationManifest) -> dict:
    return {"schema_version": "materialized-generalisation-manifest-v1",
            "manifest_id": manifest.manifest_id, "manifest_hash": manifest.manifest_hash,
            "format_ids": list(manifest.format_ids), "splits": list(manifest.splits),
            "hero_team_hashes": list(manifest.hero_team_hashes),
            "opponent_team_hashes": list(manifest.opponent_team_hashes),
            "opponent_policies": list(manifest.opponent_policies),
            "required_axes": list(manifest.required_axes),
            "required_unique_seeds_per_cell": manifest.required_unique_seeds_per_cell,
            "side_control": manifest.side_control,
            "cells": [{"cell_id": cell.cell_id, "axes": dict(cell.axes),
                       "protected": cell.protected,
                       "required_unique_seeds": cell.required_unique_seeds}
                      for cell in manifest.cells]}

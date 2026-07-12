import json
import pytest

from showdown_bot.analysis.generalisation.catalog import TeamCatalog, TeamRecord
from showdown_bot.analysis.generalisation.contracts import AnalysisPolicy
from showdown_bot.analysis.generalisation.manifest import ManifestError, load_generalisation_manifest


def _catalog():
    teams = {
        "hero": TeamRecord("hero", "hero", "hero.txt", "balance", "train"),
        "opp-a": TeamRecord("opp-a", "a", "a.txt", "rain", "dev"),
        "opp-b": TeamRecord("opp-b", "b", "b.txt", "sun", "dev"),
    }
    return TeamCatalog(teams, "catalog-hash")


def _manifest(tmp_path, **updates):
    value = {"schema_version": "generalisation-manifest-v1", "manifest_id": "m1",
             "format_ids": ["gen9vgc2025regi"], "splits": ["dev"],
             "hero_team_hashes": ["hero"], "opponent_team_hashes": ["opp-a", "opp-b"],
             "opponent_policies": ["heuristic", "max_damage"],
             "required_axes": ["hero_team_hash", "opponent_team_hash", "opponent_policy",
                               "format_id"],
             "protected_cells": "all_materialized", "required_unique_seeds_per_cell": 30,
             "side_control": "observed_only"}
    value.update(updates)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_materializes_exact_cartesian_matrix(tmp_path):
    manifest = load_generalisation_manifest(_manifest(tmp_path), _catalog(), AnalysisPolicy())
    assert len(manifest.cells) == 4
    assert len({cell.cell_id for cell in manifest.cells}) == 4
    assert all(cell.protected and cell.required_unique_seeds == 30 for cell in manifest.cells)


def test_observed_only_rejects_hero_side_axis(tmp_path):
    path = _manifest(tmp_path, required_axes=["hero_team_hash", "opponent_team_hash",
                                             "opponent_policy", "format_id", "hero_side"])
    with pytest.raises(ManifestError, match="hero_side"):
        load_generalisation_manifest(path, _catalog(), AnalysisPolicy())


def test_protected_plan_cannot_be_under_gate_minimum(tmp_path):
    with pytest.raises(ManifestError, match="gate minimum"):
        load_generalisation_manifest(_manifest(tmp_path, required_unique_seeds_per_cell=29),
                                     _catalog(), AnalysisPolicy())

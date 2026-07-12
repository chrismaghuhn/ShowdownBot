import json
import pytest

from showdown_bot.analysis.generalisation.catalog import (
    CatalogError, classify_novelty, load_exposure, load_speed_taxonomy,
    load_team_catalog, static_speed_profile,
)


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_novelty_is_independent_of_split(tmp_path):
    catalog_path = _write(tmp_path / "catalog.json", {
        "schema_version": "team-catalog-v1", "teams": [
            {"team_hash": "known", "team_id": "a", "team_path": "a.txt",
             "archetype": "rain", "declared_split": "train"},
            {"team_hash": "new-rain", "team_id": "b", "team_path": "b.txt",
             "archetype": "rain", "declared_split": "heldout"},
            {"team_hash": "new-sun", "team_id": "c", "team_path": "c.txt",
             "archetype": "sun", "declared_split": "heldout"},
        ]})
    exposure_path = _write(tmp_path / "exposure.json", {
        "schema_version": "team-exposure-v1", "exposure_id": "before-eval",
        "cutoff_utc": "2026-07-12T00:00:00Z",
        "allowed_sources": ["training", "development"],
        "exposed_team_hashes": ["known"], "exposed_archetypes": ["rain"]})
    catalog = load_team_catalog(catalog_path, verify_content=False)
    exposure = load_exposure(exposure_path, catalog)
    assert classify_novelty("known", catalog, exposure) == "known_team"
    assert classify_novelty("new-rain", catalog, exposure) == "unseen_team_known_archetype"
    assert classify_novelty("new-sun", catalog, exposure) == "unseen_archetype"
    assert classify_novelty("missing", catalog, exposure) == "unknown_provenance"


def test_exposure_rejects_heldout_hash(tmp_path):
    catalog = _write(tmp_path / "catalog.json", {
        "schema_version": "team-catalog-v1", "teams": [
            {"team_hash": "h", "team_id": "h", "team_path": "h.txt",
             "archetype": "balance", "declared_split": "heldout"}]})
    exposure = _write(tmp_path / "exposure.json", {
        "schema_version": "team-exposure-v1", "exposure_id": "bad",
        "cutoff_utc": "2026-07-12T00:00:00Z", "allowed_sources": ["training"],
        "exposed_team_hashes": ["h"], "exposed_archetypes": ["balance"]})
    with pytest.raises(CatalogError, match="heldout"):
        load_exposure(exposure, load_team_catalog(catalog, verify_content=False))


def test_static_speed_profile_uses_versioned_taxonomy(tmp_path):
    taxonomy_path = _write(tmp_path / "taxonomy.json", {
        "schema_version": "speed-control-taxonomy-v1", "categories": {
            "tailwind": ["tailwind"], "trick_room": ["trickroom"],
            "speed_reduction": ["icywind"], "speed_boost": ["dragondance"]}})
    team = tmp_path / "team.txt"
    team.write_text("Tornadus\n- Tailwind\n- Icy Wind\n\nAmoonguss\n- Protect\n", encoding="utf-8")
    taxonomy = load_speed_taxonomy(taxonomy_path)
    assert static_speed_profile(team, taxonomy) == "mixed"

from pathlib import Path

import pytest

from showdown_bot.engine.belief.hypotheses import load_likely_sets

_YAML = """
species:
  Incineroar:
    set_id: bulky_support
    nature: Careful
    evs: {hp: 252, atk: 4, spd: 252}
    item: Sitrus Berry
  Landorus-Therian:
    nature: Jolly
    evs: {atk: 252, spe: 252}
    # item omitted -> no item prior
"""


def _write(tmp_path, text):
    p = tmp_path / "likely_sets.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_per_species_spreads_keyed_by_id(tmp_path):
    sets = load_likely_sets(_write(tmp_path, _YAML))
    inc = sets["incineroar"]                       # keyed by to_id
    assert inc.offense == inc.defense              # single set, both roles
    assert inc.defense.nature == "Careful"
    assert inc.defense.evs == {"hp": 252, "atk": 4, "spd": 252}
    assert inc.defense.items == ["Sitrus Berry"]


def test_omitted_item_means_no_item_prior(tmp_path):
    sets = load_likely_sets(_write(tmp_path, _YAML))
    assert sets["landorustherian"].defense.items == []   # item omitted


def test_missing_file_is_empty(tmp_path):
    assert load_likely_sets(tmp_path / "nope.yaml") == {}


def test_invalid_species_key_fails_validation(tmp_path):
    bad = "species:\n  Landorus-T:\n    nature: Jolly\n    evs: {atk: 252}\n"
    known = {"Incineroar", "Landorus-Therian"}
    with pytest.raises(ValueError, match="unknown species"):
        load_likely_sets(_write(tmp_path, bad), is_valid_species=lambda s: s in known)


def test_valid_keys_pass_injected_validator(tmp_path):
    known = {"Incineroar", "Landorus-Therian"}
    sets = load_likely_sets(_write(tmp_path, _YAML), is_valid_species=lambda s: s in known)
    assert set(sets) == {"incineroar", "landorustherian"}


def test_curated_file_loads_and_has_team_species():
    from showdown_bot.engine.format_config import load_format_config
    path = load_format_config("gen9vgc2024regg").meta_path("likely_sets")
    sets = load_likely_sets(path)
    for sid in ("incineroar", "rillaboom", "fluttermane", "landorustherian",
                "tornadus", "urshifurapidstrike"):
        assert sid in sets
    assert sets["fluttermane"].defense.evs == {"spa": 252, "spd": 4, "spe": 252}


def test_champions_likely_sets_panel_derived():
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.state import to_id

    expected = {
        "Aerodactyl", "Archaludon", "Basculegion", "Delphox", "Excadrill", "Froslass",
        "Garchomp", "Glaceon", "Gyarados", "Hydreigon", "Incineroar", "Kingambit",
        "Lucario", "Meganium", "Milotic", "Pelipper", "Roserade", "Rotom-Heat",
        "Rotom-Wash", "Scovillain", "Sinistcha", "Sneasler", "Spiritomb", "Talonflame",
        "Tyranitar",
    }
    cfg = load_format_config("gen9championsvgc2026regma")
    sets = load_likely_sets(cfg.meta_path("likely_sets"))
    assert set(sets) == {to_id(s) for s in expected}
    # spot-check hero-derived spread
    scov = sets["scovillain"]
    assert scov.offense.nature == "Timid"
    assert scov.offense.evs == {"hp": 32, "spa": 32, "spe": 2}
    assert scov.offense.items == ["Scovillainite"]
    for sid, spreads in sets.items():
        assert spreads.offense == spreads.defense
        total = sum(spreads.offense.evs.values())
        assert total <= 66
        assert all(0 < v <= 32 for v in spreads.offense.evs.values())

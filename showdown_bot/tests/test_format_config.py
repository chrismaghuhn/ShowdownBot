from __future__ import annotations

from pathlib import Path

import pytest

from showdown_bot.engine.format_config import (
    DEFAULT_CALC_GENERATION,
    DEFAULT_STAT_INVESTMENT,
    load_format_config,
)


def test_loads_vgc_format():
    cfg = load_format_config("gen9vgc2025regi")
    assert cfg.format_id == "gen9vgc2025regi"
    assert cfg.level == 50
    assert cfg.game_type == "doubles"
    assert cfg.restricted_limit == 2
    assert cfg.tera is True
    assert cfg.mega is False
    assert cfg.stat_investment == DEFAULT_STAT_INVESTMENT
    assert cfg.calc_generation == DEFAULT_CALC_GENERATION


def test_loads_reg_g_format():
    cfg = load_format_config("gen9vgc2024regg")
    assert cfg.format_id == "gen9vgc2024regg"
    assert cfg.tera is True
    assert cfg.mega is False
    assert cfg.stat_investment == DEFAULT_STAT_INVESTMENT
    assert cfg.calc_generation == DEFAULT_CALC_GENERATION


def test_meta_paths_resolved_and_exist():
    cfg = load_format_config("gen9vgc2025regi")
    spreads = cfg.meta_path("default_spreads")
    assert spreads.name == "default_spreads.yaml"
    assert spreads.exists()


def test_missing_format_raises():
    with pytest.raises(FileNotFoundError):
        load_format_config("does_not_exist")


def test_default_fallback_without_new_fields(tmp_path: Path):
    yaml_path = tmp_path / "legacy_format.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "format_id: legacy_format",
                "level: 50",
                "game_type: doubles",
                "tera: true",
                "meta_paths:",
                "  default_spreads: meta/default_spreads.yaml",
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_format_config("legacy_format", config_dir=tmp_path)
    assert cfg.mega is False
    assert cfg.stat_investment == DEFAULT_STAT_INVESTMENT
    assert cfg.calc_generation == DEFAULT_CALC_GENERATION


def test_reads_mega_and_stat_investment(tmp_path: Path):
    yaml_path = tmp_path / "champions_stub.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "format_id: champions_stub",
                "level: 50",
                "game_type: doubles",
                "tera: false",
                "mega: true",
                "stat_investment:",
                "  kind: stat_points",
                "  total: 66",
                "  max_per_stat: 32",
                "  iv_policy: all_31",
                "meta_paths:",
                "  default_spreads: meta/default_spreads.yaml",
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_format_config("champions_stub", config_dir=tmp_path)
    assert cfg.mega is True
    assert cfg.tera is False
    assert cfg.stat_investment.kind == "stat_points"
    assert cfg.stat_investment.total == 66
    assert cfg.stat_investment.max_per_stat == 32
    assert cfg.stat_investment.iv_policy == "all_31"


@pytest.mark.parametrize(
    ("field", "yaml_body"),
    [
        ("kind", "stat_investment:\n  kind: evs\n  total: 510\n  max_per_stat: 252"),
        ("total", "stat_investment:\n  kind: ev\n  total: 0\n  max_per_stat: 252"),
        ("max_per_stat", "stat_investment:\n  kind: ev\n  total: 510\n  max_per_stat: -1"),
    ],
)
def test_invalid_stat_investment_fail_closed(tmp_path: Path, field: str, yaml_body: str):
    yaml_path = tmp_path / "bad_format.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "format_id: bad_format",
                "level: 50",
                "game_type: doubles",
                yaml_body,
                "meta_paths:",
                "  default_spreads: meta/default_spreads.yaml",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="stat_investment"):
        load_format_config("bad_format", config_dir=tmp_path)


def test_invalid_calc_generation_fail_closed(tmp_path: Path):
    yaml_path = tmp_path / "bad_calc_gen.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "format_id: bad_calc_gen",
                "level: 50",
                "game_type: doubles",
                "calc_generation: 8",
                "meta_paths:",
                "  default_spreads: meta/default_spreads.yaml",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="calc_generation"):
        load_format_config("bad_calc_gen", config_dir=tmp_path)


@pytest.mark.parametrize(
    "calc_generation_yaml",
    [
        "calc_generation: false",
        "calc_generation: 9.5",
    ],
)
def test_calc_generation_rejects_non_int_yaml(tmp_path: Path, calc_generation_yaml: str):
    yaml_path = tmp_path / "bad_calc_gen_type.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "format_id: bad_calc_gen_type",
                "level: 50",
                "game_type: doubles",
                calc_generation_yaml,
                "meta_paths:",
                "  default_spreads: meta/default_spreads.yaml",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="calc_generation must be int"):
        load_format_config("bad_calc_gen_type", config_dir=tmp_path)


CHAMPIONS_PANEL_SPECIES = frozenset({
    "Aerodactyl", "Archaludon", "Basculegion", "Delphox", "Excadrill", "Froslass",
    "Garchomp", "Glaceon", "Gyarados", "Hydreigon", "Incineroar", "Kingambit",
    "Lucario", "Meganium", "Milotic", "Pelipper", "Roserade", "Rotom-Heat",
    "Rotom-Wash", "Scovillain", "Sinistcha", "Sneasler", "Spiritomb", "Talonflame",
    "Tyranitar",
})


def _assert_stat_point_spread(evs: dict[str, int], *, max_per_stat: int = 32, total: int = 66) -> None:
    assert sum(evs.values()) <= total
    assert all(0 < v <= max_per_stat for v in evs.values())


def test_loads_champions_format():
    cfg = load_format_config("gen9championsvgc2026regma")
    assert cfg.format_id == "gen9championsvgc2026regma"
    assert cfg.level == 50
    assert cfg.game_type == "doubles"
    assert cfg.restricted_limit == 0
    assert cfg.tera is False
    assert cfg.mega is True
    assert cfg.stat_investment.kind == "stat_points"
    assert cfg.stat_investment.total == 66
    assert cfg.stat_investment.max_per_stat == 32
    assert cfg.stat_investment.iv_policy == "all_31"
    assert cfg.calc_generation == 0
    for key in ("default_spreads", "protect_priors", "likely_sets"):
        assert cfg.meta_path(key).exists()


def test_champions_default_spreads_loads_panel_species():
    from showdown_bot.engine.belief.hypotheses import SpreadBook, load_spread_book

    cfg = load_format_config("gen9championsvgc2026regma")
    book: SpreadBook = load_spread_book(cfg.meta_path("default_spreads"))
    assert set(book.species) == CHAMPIONS_PANEL_SPECIES
    _assert_stat_point_spread(book.default.offense.evs)
    _assert_stat_point_spread(book.default.defense.evs)
    for species, spreads in book.species.items():
        _assert_stat_point_spread(spreads.offense.evs)
        _assert_stat_point_spread(spreads.defense.evs)
        assert spreads.offense.nature
        assert spreads.defense.nature

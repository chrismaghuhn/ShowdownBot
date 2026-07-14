from __future__ import annotations

from pathlib import Path

import pytest

from showdown_bot.engine.format_config import (
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


def test_loads_reg_g_format():
    cfg = load_format_config("gen9vgc2024regg")
    assert cfg.format_id == "gen9vgc2024regg"
    assert cfg.tera is True
    assert cfg.mega is False
    assert cfg.stat_investment == DEFAULT_STAT_INVESTMENT


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

from __future__ import annotations

from showdown_bot.engine.format_config import load_format_config


def test_loads_vgc_format():
    cfg = load_format_config("gen9vgc2026regi")
    assert cfg.format_id == "gen9vgc2026regi"
    assert cfg.level == 50
    assert cfg.game_type == "doubles"
    assert cfg.restricted_limit == 2
    assert cfg.tera is True


def test_meta_paths_resolved_and_exist():
    cfg = load_format_config("gen9vgc2026regi")
    spreads = cfg.meta_path("default_spreads")
    assert spreads.name == "default_spreads.yaml"
    assert spreads.exists()


def test_missing_format_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_format_config("does_not_exist")

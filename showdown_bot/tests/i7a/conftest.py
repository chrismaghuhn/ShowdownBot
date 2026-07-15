from __future__ import annotations

from pathlib import Path

import pytest

SHOWDOWN_BOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]

PANEL_ROWS: list[tuple[str, str, str, str]] = [
    ("scovillainite", "Scovillain", "Scovillain-Mega", "Spicy Spray"),
    ("aerodactylite", "Aerodactyl", "Aerodactyl-Mega", "Tough Claws"),
    ("lucarionite", "Lucario", "Lucario-Mega", "Adaptability"),
    ("delphoxite", "Delphox", "Delphox-Mega", "Levitate"),
    ("meganiumite", "Meganium", "Meganium-Mega", "Mega Sol"),
    ("froslassite", "Froslass", "Froslass-Mega", "Snow Warning"),
    ("tyranitarite", "Tyranitar", "Tyranitar-Mega", "Sand Stream"),
]


@pytest.fixture
def champions_cfg():
    from showdown_bot.engine.format_config import load_format_config

    return load_format_config("gen9championsvgc2026regma")


@pytest.fixture
def our_spreads(champions_cfg):
    from showdown_bot.team.spreads import our_spreads_from_packed

    path = Path(champions_cfg.meta_path("default_spreads"))
    return our_spreads_from_packed(path.read_text(encoding="utf-8"))


@pytest.fixture
def aerodactyl_spreads():
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    return SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
        defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}),
    )


@pytest.fixture
def charizard_y_gt():
    import json

    return json.loads(
        (SHOWDOWN_BOT_ROOT / "tests/fixtures/i7a_charizard_mega_y_gt.json").read_text()
    )


@pytest.fixture
def scovillain_mega_request():
    import json

    from showdown_bot.models.request import BattleRequest

    p = SHOWDOWN_BOT_ROOT / "tests/fixtures/i7a_scovillain_can_mega_request.json"
    return BattleRequest.model_validate(json.loads(p.read_text(encoding="utf-8")))


@pytest.fixture
def scovillain_hero_state():
    from showdown_bot.engine.state import BattleState, PokemonState

    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Scovillain",
        base_species_id="scovillain",
        item="Scovillainite",
        hp=100,
        max_hp=100,
    )
    return st


@pytest.fixture
def scovillain_base_joints(scovillain_mega_request):
    from showdown_bot.battle.actions import enumerate_my_actions

    return enumerate_my_actions(scovillain_mega_request)


@pytest.fixture
def calc_profile(champions_cfg):
    from showdown_bot.engine.calc_profile import calc_profile_from_config

    return calc_profile_from_config(champions_cfg)

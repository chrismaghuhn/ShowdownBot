"""Shared fixtures for tests/i7b/ -- real SpeedOracle/calc_profile/species_meta,
built the same way tests/conftest.py::mega_decision_fixture already does (real
SubprocessCalcBackend, real calc_profile_from_config), never a fake/stub."""
from __future__ import annotations

import pytest


@pytest.fixture
def i7b_projection_env():
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.engine.species_meta import species_meta_table

    cfg = load_format_config("gen9championsvgc2026regma")
    calc_profile = calc_profile_from_config(cfg)
    speed_oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    return {"speed_oracle": speed_oracle, "calc_profile": calc_profile, "species_meta": species_meta_table()}


@pytest.fixture
def opp_sets_meganium():
    """`evs={"hp": 32, "def": 32}` -- matches the project's established modest-
    EV test-double convention (tests/conftest.py::mega_decision_fixture,
    tests/i7a/conftest.py::aerodactyl_spreads), not the standard-competitive
    252-max scale (Rev. 3 audit finding 6b: earlier draft used 252 here,
    inconsistent with every sibling fixture in this suite). Verified via
    direct SpeedOracle._base_speed computation against the real calc backend
    that Meganium (base Speed 60) stays well below Aerodactyl's
    i7b_aerodactyl_spreads (100 vs 200 pre-mega Speed) at this same modest
    investment -- not merely assumed from base-stat intuition."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Bold", evs={"hp": 32, "def": 32}, items=["Meganiumite"])
    return {"meganium": SpeciesSpreads(offense=preset, defense=preset)}


@pytest.fixture
def i7b_aerodactyl_spreads():
    """Deliberately NOT named `aerodactyl_spreads` and NOT imported from the
    sibling `tests/i7a/conftest.py::aerodactyl_spreads` fixture (Rev. 3 audit
    finding 6c, resolved definitively): `tests/i7b/` is a SIBLING of
    `tests/i7a/`, not a subdirectory, so pytest's directory-scoped conftest.py
    discovery does NOT make i7a's fixtures visible here automatically, and a
    `pytest_plugins` cross-import would assert an unverified rootdir-relative
    module path. This project builds its own self-contained, i7b-prefixed
    fixture instead of importing or risking a same-name shadowing collision
    with a fixture of a DIFFERENT shape (i7a's version returns a bare
    `SpeciesSpreads`; every I7b-B call site in this plan expects a
    species-keyed dict, matching `opp_sets_meganium` above) -- same EV values
    as the sibling (32/32/2) for realism-consistency, but a distinct name and
    a distinct (dict) shape, so there is no ambiguity either way."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}, items=["Aerodactylite"])
    return {"aerodactyl": SpeciesSpreads(offense=preset, defense=preset)}


@pytest.fixture
def i7b_froslass_spreads():
    """evs={"spe": 32} (Timid) -- same modest-EV convention as
    i7b_aerodactyl_spreads/opp_sets_meganium (Rev. 3 finding 6b), not 252.
    Verified via direct SpeedOracle._base_speed computation against the real
    calc backend: Froslass, Timid, evs={"spe": 32} -> pre-mega Speed 178,
    unambiguously above i7b_opp_sets_tyranitar's 124 below -- a real,
    checked ordering for test_weather_ordering_follows_the_LAST_processed_
    activator_not_the_first and test_trick_room_reverses_activation_order_
    vs_no_tr (neither test monkeypatches speed here, unlike the Aerodactyl/
    Meganium tie test above, so this ordering must hold for real)."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Timid", evs={"spe": 32}, items=["Froslassite"])
    return {"froslass": SpeciesSpreads(offense=preset, defense=preset)}


@pytest.fixture
def i7b_opp_sets_tyranitar():
    """evs={"spe": 32} (Jolly) -- same modest-EV convention as the fixtures
    above (Rev. 3 finding 6b). Verified: Tyranitar, Jolly, evs={"spe": 32} ->
    pre-mega Speed 124, unambiguously below i7b_froslass_spreads's 178."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Jolly", evs={"spe": 32}, items=["Tyranitarite"])
    return {"tyranitar": SpeciesSpreads(offense=preset, defense=preset)}

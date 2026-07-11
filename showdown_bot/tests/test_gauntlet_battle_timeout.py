"""2b-2.5a, 2026-07-11: configurable per-battle gauntlet timeout.

``run_local_gauntlet``'s hard per-run ``asyncio.wait_for`` timeout used a flat
``max(180.0, games * 150.0)`` formula. Datagen plays ``games=1`` per call (180s), but the
rollout teacher labels every decision (~3-4s each), so legitimate 50+-turn stall wars
(sun_dev vs rain_dev tail cells) can exceed 180s even on a healthy VM (post the memory-leak
fix) -- the battle then yields NO result row and the schedule run fails.

``_effective_battle_timeout`` is the pure/injectable precedence resolver extracted out of
``run_local_gauntlet``'s ``asyncio.wait_for`` call: explicit param > env var
``SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S`` > the pre-existing formula. Tested directly here (no
live server/connection needed -- same "unit seam" testing style as test_gauntlet_teams.py /
test_gauntlet_close.py), so it is exercised without running any battle.
"""
from __future__ import annotations

from showdown_bot.client.gauntlet import _effective_battle_timeout


# --- formula fallback (env unset / not usable) -------------------------------------------

def test_env_absent_falls_back_to_formula():
    assert _effective_battle_timeout(1, None, {}) == max(180.0, 1 * 150.0)


def test_env_empty_string_falls_back_to_formula():
    assert _effective_battle_timeout(1, None, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": ""}) == (
        max(180.0, 1 * 150.0)
    )


def test_env_zero_falls_back_to_formula():
    assert _effective_battle_timeout(1, None, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "0"}) == (
        max(180.0, 1 * 150.0)
    )


def test_env_negative_falls_back_to_formula():
    assert _effective_battle_timeout(1, None, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "-5"}) == (
        max(180.0, 1 * 150.0)
    )


def test_env_unparseable_falls_back_to_formula():
    assert _effective_battle_timeout(1, None, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "nope"}) == (
        max(180.0, 1 * 150.0)
    )


def test_formula_scales_with_games_when_env_and_param_absent():
    assert _effective_battle_timeout(5, None, {}) == max(180.0, 5 * 150.0)


# --- env override ---------------------------------------------------------------------

def test_env_900_wins_over_formula():
    assert _effective_battle_timeout(1, None, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900"}) == 900.0


# --- explicit param takes top precedence -----------------------------------------------

def test_param_wins_over_env():
    result = _effective_battle_timeout(
        1, 42.0, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900"},
    )
    assert result == 42.0


def test_param_wins_over_formula_when_env_absent():
    assert _effective_battle_timeout(1, 42.0, {}) == 42.0


def test_param_zero_is_respected_not_treated_as_absent():
    # battle_timeout_s=0.0 is an explicit (if unusual) caller choice -- distinct from None
    # ("not given") -- so it must NOT fall through to the env/formula precedence tiers.
    assert _effective_battle_timeout(1, 0.0, {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900"}) == 0.0

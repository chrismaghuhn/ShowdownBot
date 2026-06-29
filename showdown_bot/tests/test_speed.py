from __future__ import annotations

import pytest

from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import (
    SpeedOracle,
    effective_speed,
    effective_speed_from_state,
)
from showdown_bot.engine.state import FieldState, PokemonState


def test_effective_speed_base():
    assert effective_speed(100) == 100


def test_effective_speed_tailwind_doubles():
    assert effective_speed(100, tailwind=True) == 200


def test_effective_speed_paralysis_halves():
    assert effective_speed(100, paralyzed=True) == 50


def test_effective_speed_scarf_and_boost():
    # +1 stage (x1.5) then scarf (x1.5): 100 -> 150 -> 225
    assert effective_speed(100, boost_stage=1, scarf=True) == 225


def test_effective_speed_no_trick_room_param():
    # Trick Room must NOT be a parameter here; speed is unaffected by it.
    import inspect

    params = inspect.signature(effective_speed).parameters
    assert "trick_room" not in params
    assert "trickroom" not in params


def test_effective_speed_from_state_reads_modifiers():
    mon = PokemonState(species="Incineroar", boosts={"spe": -1}, status="par")
    field = FieldState(tailwind={"p1": True, "p2": False})
    # base 100, -1 stage (x2/3 -> 66), tailwind (x2 ->132), para (x0.5 ->66)
    assert effective_speed_from_state(100, mon, field, "p1") == 66


class FakeStatsBackend:
    def __init__(self, spe_values):
        self._spe = spe_values

    def stats_batch(self, specs):
        return [{"spe": v} for v in self._spe]


def test_speed_oracle_opponent_range_ordering():
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    oracle = SpeedOracle(stats_backend=FakeStatsBackend([80, 110, 150]))
    mon = PokemonState(species="Flutter Mane")
    rng = oracle.opponent_range(mon, FieldState(), "p2", book=book)
    assert rng.min == 80
    assert rng.likely == 110
    # max assumes Choice Scarf: 150 -> 225
    assert rng.max == 225
    assert rng.min <= rng.likely <= rng.max


@pytest.mark.integration
def test_speed_oracle_real_stats_query():
    cfg = load_format_config("gen9vgc2026regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    oracle = SpeedOracle(stats_backend=SubprocessCalcBackend())
    mon = PokemonState(species="Flutter Mane")
    rng = oracle.opponent_range(mon, FieldState(), "p2", book=book)
    # Flutter Mane base spe 135; max (252+ , scarf) clearly exceeds min.
    assert rng.max > rng.min > 0

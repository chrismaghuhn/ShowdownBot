from __future__ import annotations

import pytest

from showdown_bot.engine.belief.hypotheses import SpreadPreset, load_spread_book
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

    def stats_batch(self, specs, *, gen=9):
        return [{"spe": v} for v in self._spe]


def test_speed_oracle_opponent_range_ordering():
    cfg = load_format_config("gen9vgc2025regi")
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
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    oracle = SpeedOracle(stats_backend=SubprocessCalcBackend())
    mon = PokemonState(species="Flutter Mane")
    rng = oracle.opponent_range(mon, FieldState(), "p2", book=book)
    # Flutter Mane base spe 135; max (252+ , scarf) clearly exceeds min.
    assert rng.max > rng.min > 0


# ---------------------------------------------------------------------------
# T1: SpeedOracle.likely_speed + base-speed cache
# ---------------------------------------------------------------------------


class FakeBackend:
    def __init__(self, spe):
        self.spe = spe
        self.calls = 0

    def stats_batch(self, specs, *, gen=9):
        self.calls += 1
        return [{"spe": self.spe} for _ in specs]

    def types_batch(self, species):
        return [["Normal"] for _ in species]


def test_likely_speed_reads_scarf_only_from_item_for_speed():
    oracle = SpeedOracle(stats_backend=FakeBackend(spe=100))
    mon, field = PokemonState(species="Incineroar"), FieldState()
    preset = SpreadPreset(nature="Careful", evs={"hp": 252}, items=["Sitrus Berry"])
    assert oracle.likely_speed(mon, field, "p2", preset, "Choice Scarf") == 150   # scarf x1.5
    assert oracle.likely_speed(mon, field, "p2", preset, "Booster Energy") == 100  # booster != scarf speed
    assert oracle.likely_speed(mon, field, "p2", preset, None) == 100


class NatureAwareBackend:
    """Returns a distinct spe stat keyed by (species, nature, evs) so a test can
    prove WHICH spread was actually selected, not just that some value came
    back."""

    def __init__(self, table: dict[tuple, int], default: int = 999):
        self.table = table
        self.default = default

    def stats_batch(self, specs, *, gen=9):
        out = []
        for s in specs:
            key = (s.species, s.nature, tuple(sorted(s.evs.items())))
            out.append({"spe": self.table.get(key, self.default)})
        return out


def test_speed_oracle_opponent_range_resolves_post_mega_species_via_base_id():
    """P1.2 integration: engine/speed.py's SpeedOracle.opponent_range calls
    hypothesis_from_state(mon, book) to get the "likely" preset for its middle
    (likely) speed estimate. For a post-Mega mon (species="Aerodactyl-Mega",
    base_species_id="aerodactyl"), the book is keyed by base species id, so the
    likely speed must reflect the committed "aerodactyl" spread's nature/evs,
    not the book default -- proving evaluate/speed consumers get the correct
    identity through the normal hypothesis_from_state call path."""
    committed_offense = SpreadPreset(nature="Naive", evs={"spe": 100})
    committed_defense = SpreadPreset(nature="Impish", evs={"hp": 100})
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook

    book = SpreadBook(
        default=SpeciesSpreads(
            offense=SpreadPreset(nature="Hardy", evs={}),
            defense=SpreadPreset(nature="Hardy", evs={}),
        ),
        species={"aerodactyl": SpeciesSpreads(offense=committed_offense, defense=committed_defense)},
    )
    backend = NatureAwareBackend(
        table={
            ("Aerodactyl-Mega", "Brave", (("spe", 0),)): 80,
            ("Aerodactyl-Mega", "Naive", (("spe", 100),)): 130,  # the committed likely spread
            ("Aerodactyl-Mega", "Jolly", (("spe", 252),)): 200,
            # default-book values, if the lookup wrongly fell back to them:
            ("Aerodactyl-Mega", "Hardy", ()): 999,
        }
    )
    oracle = SpeedOracle(stats_backend=backend)
    mon = PokemonState(species="Aerodactyl-Mega", base_species_id="aerodactyl")

    rng = oracle.opponent_range(mon, FieldState(), "p2", book=book)

    assert rng.likely == effective_speed(130)  # resolved the committed spread, not the 999 default


def test_base_speed_is_cached():
    fb = FakeBackend(spe=100)
    oracle = SpeedOracle(stats_backend=fb)
    mon, field = PokemonState(species="Incineroar"), FieldState()
    preset = SpreadPreset(nature="Careful", evs={"hp": 252}, items=[])
    oracle.likely_speed(mon, field, "p2", preset, None)
    oracle.likely_speed(mon, field, "p2", preset, None)
    assert fb.calls == 1  # second call hit the cache

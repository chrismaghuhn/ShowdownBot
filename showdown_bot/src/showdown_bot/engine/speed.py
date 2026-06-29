from __future__ import annotations

import math
from dataclasses import dataclass

from showdown_bot.engine.belief.hypotheses import OFFENSE, SpreadBook, hypothesis_from_state
from showdown_bot.engine.calc.models import CalcMon
from showdown_bot.engine.state import FieldState, PokemonState

# Boost-stage multiplier for Speed (same table as other stats).
_STAGE_MULT = {
    -6: 2 / 8, -5: 2 / 7, -4: 2 / 6, -3: 2 / 5, -2: 2 / 4, -1: 2 / 3,
    0: 1.0,
    1: 3 / 2, 2: 4 / 2, 3: 5 / 2, 4: 6 / 2, 5: 7 / 2, 6: 8 / 2,
}


def effective_speed(
    base_speed: int,
    *,
    boost_stage: int = 0,
    tailwind: bool = False,
    paralyzed: bool = False,
    scarf: bool = False,
    booster_speed: bool = False,
) -> int:
    """Real in-battle Speed number. Deliberately contains NO Trick Room.

    Trick Room never changes the speed value -- it only flips sort order, which
    lives in ``sort_actions`` (resolver). Keeping it out of here prevents other
    features that need true speed from silently receiving inverted numbers.
    """
    stage = max(-6, min(6, boost_stage))
    spe = math.floor(base_speed * _STAGE_MULT[stage])
    if scarf:
        spe = math.floor(spe * 1.5)
    if booster_speed:
        spe = math.floor(spe * 1.5)
    if tailwind:
        spe *= 2
    if paralyzed:
        spe = math.floor(spe * 0.5)
    return int(spe)


def speed_modifiers_from_state(mon: PokemonState, field: FieldState, side: str) -> dict:
    """Derive effective_speed kwargs from observed state (known info only)."""
    scarf = mon.item_known and mon.item == "Choice Scarf"
    # Booster (Protosynthesis/Quark Drive) on speed is not knowable from state
    # alone; assume off unless a future signal sets it.
    return {
        "boost_stage": mon.boosts.get("spe", 0),
        "tailwind": bool(field.tailwind.get(side, False)),
        "paralyzed": mon.status == "par",
        "scarf": scarf,
        "booster_speed": False,
    }


def effective_speed_from_state(
    base_speed: int, mon: PokemonState, field: FieldState, side: str
) -> int:
    return effective_speed(base_speed, **speed_modifiers_from_state(mon, field, side))


@dataclass(frozen=True)
class SpeedRange:
    min: int
    likely: int
    max: int


class SpeedOracle:
    """Speeds for both sides.

    Our mons: exact base Speed from the request stats. Opponents: a range, since
    EV/nature/item are unknown -- min (-nature, 0 EV), likely (offense preset),
    max (+nature, 252 EV, assume Scarf).
    """

    def __init__(self, stats_backend=None) -> None:
        if stats_backend is None:
            from showdown_bot.engine.calc.client import SubprocessCalcBackend

            stats_backend = SubprocessCalcBackend()
        self.backend = stats_backend

    def our_speed(self, base_speed: int, mon: PokemonState, field: FieldState, side: str) -> int:
        return effective_speed_from_state(base_speed, mon, field, side)

    def opponent_range(
        self, mon: PokemonState, field: FieldState, side: str, *, book: SpreadBook
    ) -> SpeedRange:
        hyp = hypothesis_from_state(mon, book)
        offense_preset = hyp.spreads.offense if hyp.spreads else None
        likely_nature = offense_preset.nature if offense_preset else "Hardy"
        likely_evs = dict(offense_preset.evs) if offense_preset else {}

        specs = [
            CalcMon(species=mon.species, level=mon.level, nature="Brave",
                    evs={"spe": 0}, ivs={"spe": 0}),
            CalcMon(species=mon.species, level=mon.level, nature=likely_nature, evs=likely_evs),
            CalcMon(species=mon.species, level=mon.level, nature="Jolly",
                    evs={"spe": 252}, ivs={"spe": 31}),
        ]
        spe_stats = [s["spe"] for s in self.backend.stats_batch(specs)]
        base_min, base_likely, base_max = spe_stats

        mods = speed_modifiers_from_state(mon, field, side)
        # min: no scarf (slowest plausible); max: assume scarf (fastest plausible).
        spe_min = effective_speed(base_min, **{**mods, "scarf": False})
        spe_likely = effective_speed(base_likely, **mods)
        spe_max = effective_speed(base_max, **{**mods, "scarf": True})
        return SpeedRange(min=spe_min, likely=spe_likely, max=spe_max)

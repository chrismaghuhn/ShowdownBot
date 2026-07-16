from __future__ import annotations

import math
from dataclasses import dataclass

from showdown_bot.engine.belief.hypotheses import OFFENSE, SpreadBook, hypothesis_from_state
from showdown_bot.engine.calc.models import CalcMon
from showdown_bot.engine.calc_profile import DEFAULT_CALC_PROFILE, CalcProfile
from showdown_bot.engine.spread_lookup import lookup_opp_set, lookup_our_spreads
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


def mega_activation_order_key(pre_mega_speed: int, field: FieldState) -> int:
    """Sort key for Mega-activation order (queue priority 104, Showdown pin
    f8ac140): same speed direction as ``battle.resolve.sort_actions`` uses for
    its own queue ordering -- higher pre-mega speed activates first outside
    Trick Room, lower activates first under it. Ascending sort by this key
    reproduces that order; do not invent a different sign convention."""
    return pre_mega_speed if field.trick_room else -pre_mega_speed


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


class MissingMegaSpreadError(RuntimeError):
    """Raised when an own-side mega projection lacks a spread for base_species_id."""


class SpeedOracle:
    """Speeds for both sides.

    Our mons: exact base Speed from the request stats. Opponents: a range, since
    EV/nature/item are unknown -- min (-nature, 0 EV), likely (offense preset),
    max (+nature, profile max spe investment, assume Scarf).
    """

    def __init__(self, stats_backend=None, *, profile: CalcProfile | None = None) -> None:
        if stats_backend is None:
            from showdown_bot.engine.calc.client import SubprocessCalcBackend

            stats_backend = SubprocessCalcBackend()
        self.backend = stats_backend
        self.profile = profile or DEFAULT_CALC_PROFILE
        self._spe_cache: dict = {}

    def our_speed(self, base_speed: int, mon: PokemonState, field: FieldState, side: str) -> int:
        return effective_speed_from_state(base_speed, mon, field, side)

    def _base_speed(self, species: str, nature: str, evs: dict) -> int:
        """Final Speed stat (no in-battle mods) for a spread, cached. VGC level
        50, IVs 31 for any stat the set doesn't specify."""
        key = (
            self.profile.generation,
            species,
            nature,
            tuple(sorted(evs.items())),
        )
        cached = self._spe_cache.get(key)
        if cached is None:
            spec = CalcMon(species=species, level=50, nature=nature, evs=dict(evs), ivs={"spe": 31})
            cached = self.backend.stats_batch([spec], gen=self.profile.generation)[0]["spe"]
            self._spe_cache[key] = cached
        return cached

    def likely_speed(self, mon, field, side, preset, item_for_speed) -> int:
        """Realistic point Speed from a curated set. ONLY Choice Scarf is read
        from the item; everything else (boosts/Tailwind/para/booster) comes from
        observed state -- a curated Booster Energy never inflates speed here."""
        base = self._base_speed(mon.species, preset.nature, preset.evs)
        mods = speed_modifiers_from_state(mon, field, side)
        mods["scarf"] = item_for_speed in ("Choice Scarf", "choicescarf")
        return effective_speed(base, **mods)

    def opponent_range(
        self, mon: PokemonState, field: FieldState, side: str, *, book: SpreadBook
    ) -> SpeedRange:
        hyp = hypothesis_from_state(mon, book)
        offense_preset = hyp.spreads.offense if hyp.spreads else None
        likely_nature = offense_preset.nature if offense_preset else "Hardy"
        likely_evs = dict(offense_preset.evs) if offense_preset else {}

        max_spe = self.profile.max_spe_investment
        specs = [
            CalcMon(species=mon.species, level=mon.level, nature="Brave",
                    evs={"spe": 0}, ivs={"spe": 0}),
            CalcMon(species=mon.species, level=mon.level, nature=likely_nature, evs=likely_evs),
            CalcMon(species=mon.species, level=mon.level, nature="Jolly",
                    evs={"spe": max_spe}, ivs={"spe": 31}),
        ]
        spe_stats = [s["spe"] for s in self.backend.stats_batch(specs, gen=self.profile.generation)]
        base_min, base_likely, base_max = spe_stats

        mods = speed_modifiers_from_state(mon, field, side)
        # min: no scarf (slowest plausible); max: assume scarf (fastest plausible).
        spe_min = effective_speed(base_min, **{**mods, "scarf": False})
        spe_likely = effective_speed(base_likely, **mods)
        spe_max = effective_speed(base_max, **{**mods, "scarf": True})
        return SpeedRange(min=spe_min, likely=spe_likely, max=spe_max)

    def speed_for_species(
        self,
        *,
        species_name: str,
        base_species_id: str,
        side: str,
        mon: PokemonState,
        field: FieldState,
        our_spreads: dict | None,
        opp_sets: dict | None,
        book: SpreadBook | None,
        is_ours: bool,
    ) -> int:
        if is_ours:
            preset = lookup_our_spreads(our_spreads, mon)
            if preset is None:
                raise MissingMegaSpreadError(base_species_id)
            base = self._base_speed(species_name, preset.offense.nature, preset.offense.evs)
            return effective_speed_from_state(base, mon, field, side)
        hyp = hypothesis_from_state(mon, book) if book is not None else None
        offense_preset = hyp.spreads.offense if hyp and hyp.spreads else None
        if offense_preset is None and opp_sets is not None:
            spreads = lookup_opp_set(opp_sets, mon)
            offense_preset = spreads.offense if spreads else None
        if offense_preset is None:
            raise MissingMegaSpreadError(base_species_id)
        base = self._base_speed(species_name, offense_preset.nature, offense_preset.evs)
        return effective_speed_from_state(base, mon, field, side)

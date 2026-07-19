from __future__ import annotations

import math
import os
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

    def _spec_key(self, spec: CalcMon):
        """Exact identity of a base-stat query: generation + the full canonical CalcMon payload
        (species, level, nature, evs, ivs). Two specs share a key iff they yield the same stat,
        so a cache hit is never a wrong stat and a miss is at worst a redundant spawn."""
        return (
            self.profile.generation,
            spec.species,
            spec.level,
            spec.nature,
            tuple(sorted((spec.evs or {}).items())),
            tuple(sorted((spec.ivs or {}).items())),
        )

    def _speeds_for_specs(self, specs: list[CalcMon]) -> list[int]:
        """Cache-first final Speed stat for each spec: check every exact key, compute only the
        cold misses in ONE ``stats_batch`` (deduped, never one-per-spec, never split), populate
        the cache, and return in spec order. The one warmable opponent-speed path (Lever B)."""
        keys = [self._spec_key(s) for s in specs]
        missing: dict = {}
        for key, spec in zip(keys, specs):
            if key not in self._spe_cache and key not in missing:
                missing[key] = spec
        if missing:
            stats = self.backend.stats_batch(list(missing.values()), gen=self.profile.generation)
            for key, st in zip(missing, stats):
                self._spe_cache[key] = st["spe"]
        return [self._spe_cache[k] for k in keys]

    def seed_results(self, results) -> None:
        """Inject pre-computed ``(CalcMon, stats)`` pairs into the speed cache under their exact
        keys -- a pure cache write with NO transport. The decision-start pre-pass computes these
        in the shared ``mixed_batch`` and seeds them here so the lazy speed path is a pure hit;
        behaviour-neutral because a seeded stat equals what ``stats_batch`` returns for the spec."""
        for spec, stats in results:
            self._spe_cache[self._spec_key(spec)] = stats["spe"]

    def _base_spec(self, species: str, nature: str, evs: dict) -> CalcMon:
        """The canonical single base-Speed spec (VGC level 50, spe-IV 31) for a species/spread --
        exactly what ``_base_speed`` queries and what the pre-pass seeds for a likely-set mon."""
        return CalcMon(species=species, level=50, nature=nature, evs=dict(evs), ivs={"spe": 31})

    def _base_speed(self, species: str, nature: str, evs: dict) -> int:
        """Final Speed stat (no in-battle mods) for a spread, cached. VGC level 50, IVs 31 for
        any stat the set doesn't specify."""
        return self._speeds_for_specs([self._base_spec(species, nature, evs)])[0]

    def likely_speed(self, mon, field, side, preset, item_for_speed) -> int:
        """Realistic point Speed from a curated set. ONLY Choice Scarf is read
        from the item; everything else (boosts/Tailwind/para/booster) comes from
        observed state -- a curated Booster Energy never inflates speed here."""
        base = self._base_speed(mon.species, preset.nature, preset.evs)
        mods = speed_modifiers_from_state(mon, field, side)
        mods["scarf"] = item_for_speed in ("Choice Scarf", "choicescarf")
        return effective_speed(base, **mods)

    def _range_specs(self, mon: PokemonState, book: SpreadBook) -> list[CalcMon]:
        """The three opponent_range base-stat specs (min / likely / max) for an opponent mon, in
        that order. Extracted so ``opponent_range`` and the pre-pass collector build IDENTICAL
        specs -- seeding one then guarantees the other is a cache hit."""
        hyp = hypothesis_from_state(mon, book)
        offense_preset = hyp.spreads.offense if hyp.spreads else None
        likely_nature = offense_preset.nature if offense_preset else "Hardy"
        likely_evs = dict(offense_preset.evs) if offense_preset else {}
        max_spe = self.profile.max_spe_investment
        return [
            CalcMon(species=mon.species, level=mon.level, nature="Brave",
                    evs={"spe": 0}, ivs={"spe": 0}),
            CalcMon(species=mon.species, level=mon.level, nature=likely_nature, evs=likely_evs),
            CalcMon(species=mon.species, level=mon.level, nature="Jolly",
                    evs={"spe": max_spe}, ivs={"spe": 31}),
        ]

    def opponent_range(
        self, mon: PokemonState, field: FieldState, side: str, *, book: SpreadBook
    ) -> SpeedRange:
        specs = self._range_specs(mon, book)
        base_min, base_likely, base_max = self._speeds_for_specs(specs)
        mods = speed_modifiers_from_state(mon, field, side)
        # min: no scarf (slowest plausible); max: assume scarf (fastest plausible).
        spe_min = effective_speed(base_min, **{**mods, "scarf": False})
        spe_likely = effective_speed(base_likely, **mods)
        spe_max = effective_speed(base_max, **{**mods, "scarf": True})
        return SpeedRange(min=spe_min, likely=spe_likely, max=spe_max)

    def opp_speed_specs(
        self, mon: PokemonState, field: FieldState, side: str, *, book, opp_sets
    ) -> list[CalcMon]:
        """The base-stat specs the lazy ``_opponent_speed`` (battle/opponent.py) will need for
        this opponent mon, matching its branch EXACTLY so the pre-pass can warm them and the lazy
        path becomes a pure cache hit:

          - a curated set is found AND ``SHOWDOWN_OPP_SPEED != 0`` -> the single defense-preset
            spec (the ``likely_speed`` path); NO range prefetch;
          - otherwise -> the three ``opponent_range`` specs.

        Returns the SAME CalcMon objects those paths build (via ``_base_spec`` / ``_range_specs``),
        so seeding is behaviour-neutral. ``field``/``side`` mirror ``_opponent_speed``'s inputs but
        do not change the base-stat specs (in-battle mods are applied after the base stat)."""
        preset_spreads = lookup_opp_set(opp_sets, mon) if opp_sets else None
        use_likely = (
            os.environ.get("SHOWDOWN_OPP_SPEED", "1") != "0" and preset_spreads is not None
        )
        if use_likely:
            preset = preset_spreads.defense
            return [self._base_spec(mon.species, preset.nature, preset.evs)]
        return self._range_specs(mon, book)

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

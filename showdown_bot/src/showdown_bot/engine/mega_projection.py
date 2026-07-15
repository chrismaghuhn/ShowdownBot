from __future__ import annotations

import copy
from dataclasses import dataclass

from showdown_bot.engine.calc_profile import CalcProfile
from showdown_bot.engine.mega_form import MegaForm
from showdown_bot.engine.species_meta import SpeciesFormMeta
from showdown_bot.engine.speed import MissingMegaSpreadError, SpeedOracle
from showdown_bot.engine.spread_lookup import lookup_our_spreads
from showdown_bot.engine.state import BattleState, FieldState, PokemonState

FAIL_CLOSED_ABILITIES = frozenset({"Spicy Spray"})

_WEATHER_ABILITIES = {
    "Drought": "sunnyday",
    "Sand Stream": "sandstorm",
    "Snow Warning": "snowscape",
}

_SLOT_TO_INDEX = {"a": 0, "b": 1}


class UnsupportedMegaAbilityError(RuntimeError):
    """Raised when a mega form ability is not modeled in v0."""


@dataclass(frozen=True)
class MegaProjectionResult:
    mega_form: MegaForm
    projected_state: BattleState
    mega_slot: str
    own_mega_slot: int | None
    effective_speed: int


def copy_battle_state(state: BattleState) -> BattleState:
    copied = copy.deepcopy(state)
    copied.sides = {
        side: {slot: copy.deepcopy(mon) for slot, mon in slots.items()}
        for side, slots in state.sides.items()
    }
    copied.field = FieldState(
        weather=state.field.weather,
        terrain=state.field.terrain,
        trick_room=state.field.trick_room,
        tailwind=dict(state.field.tailwind),
    )
    copied.side_mega_spent = dict(state.side_mega_spent)
    copied.turn = state.turn
    return copied


def _apply_weather_hook(field: FieldState, ability: str) -> None:
    weather = _WEATHER_ABILITIES.get(ability)
    if weather is not None:
        field.weather = weather


def project_mega(
    state: BattleState,
    side: str,
    slot: str,
    mega_form: MegaForm,
    *,
    species_meta: dict[str, SpeciesFormMeta],
    speed_oracle: SpeedOracle,
    spread_lookup: dict,
    calc_profile: CalcProfile,
) -> MegaProjectionResult:
    if speed_oracle.profile != calc_profile:
        raise ValueError(
            f"speed_oracle.profile {speed_oracle.profile!r} != calc_profile {calc_profile!r}"
        )

    form_meta = species_meta.get(mega_form.form_species_id)
    if form_meta is None:
        raise ValueError(f"unknown mega form {mega_form.form_species_id!r}")

    if form_meta.ability_slot0 in FAIL_CLOSED_ABILITIES:
        raise UnsupportedMegaAbilityError(form_meta.ability_slot0)

    projected_state = copy_battle_state(state)
    mon = projected_state.sides[side][slot]
    mon.species = form_meta.form_species_name
    mon.types = list(form_meta.types)
    mon.ability = form_meta.ability_slot0
    mon.base_species_id = mega_form.base_species_id

    projected_state.side_mega_spent[side] = True
    _apply_weather_hook(projected_state.field, form_meta.ability_slot0)

    preset = lookup_our_spreads(spread_lookup, mon)
    if preset is None:
        raise MissingMegaSpreadError(mega_form.base_species_id)

    effective_speed = speed_oracle.speed_for_species(
        species_name=form_meta.form_species_name,
        base_species_id=mega_form.base_species_id,
        side=side,
        mon=mon,
        field=projected_state.field,
        our_spreads=spread_lookup,
        opp_sets=None,
        book=None,
        is_ours=True,
    )

    return MegaProjectionResult(
        mega_form=mega_form,
        projected_state=projected_state,
        mega_slot=slot,
        own_mega_slot=_SLOT_TO_INDEX.get(slot),
        effective_speed=effective_speed,
    )

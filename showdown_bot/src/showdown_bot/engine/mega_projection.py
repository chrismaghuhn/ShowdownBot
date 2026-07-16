from __future__ import annotations

import copy
from dataclasses import dataclass

from showdown_bot.engine.calc_profile import CalcProfile
from showdown_bot.engine.mega_form import MegaForm
from showdown_bot.engine.species_meta import SpeciesFormMeta
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, FieldState, PokemonState, to_id

FAIL_CLOSED_ABILITIES = frozenset({"Spicy Spray"})

_WEATHER_ABILITIES = {
    "Drought": "sunnyday",
    "Sand Stream": "sandstorm",
    "Snow Warning": "snowscape",
}

_SLOT_TO_INDEX = {"a": 0, "b": 1}


class UnsupportedMegaAbilityError(RuntimeError):
    """Raised when a mega form ability is not modeled in v0."""


class MegaProjectionSpeciesMismatchError(ValueError):
    """The mon at (side, slot) is not the mega_form's base species. In production
    this cannot arise -- battle.opponent.foe_mega_eligibility derives every form
    from mega_form_for(mon.species, mon.item) and is coherent by construction, and
    the own side reads its own request -- so reaching this is a real programming
    error. Fail closed rather than silently rewriting an unrelated mon's species
    (before this check, an Aerodactyl-Mega form projected onto an Incineroar
    "succeeded" without complaint)."""


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
    spread_lookup: dict | None = None,
    calc_profile: CalcProfile,
    is_ours: bool = True,
    opp_sets: dict | None = None,
    book=None,
) -> MegaProjectionResult:
    if speed_oracle.profile != calc_profile:
        raise ValueError(
            f"speed_oracle.profile {speed_oracle.profile!r} != calc_profile {calc_profile!r}"
        )

    form_meta = species_meta.get(mega_form.form_species_id)
    if form_meta is None:
        raise ValueError(f"unknown mega form {mega_form.form_species_id!r}")

    # Coherence BEFORE the ability gate and before any copy/mutation: an incoherent
    # request is malformed input, so the "is this form supported?" question is moot.
    # Ordering matters -- an incoherent AND unsupported form must crash (real bug),
    # not be silently excluded by score_evaluated_variants's UnsupportedMegaAbilityError
    # handler. Match on normalized base_species_id OR species: the `or` keeps valid
    # sub-form mappings working (an already-Mega'd mon reads species "Aerodactyl-Mega"
    # -> to_id "aerodactylmega", which never equals the form's "aerodactyl", while its
    # base_species_id still does).
    src_mon = state.sides[side][slot]
    if mega_form.base_species_id not in {
        to_id(src_mon.base_species_id or ""),
        to_id(src_mon.species or ""),
    }:
        raise MegaProjectionSpeciesMismatchError(
            f"{side}/{slot} is {src_mon.species!r} (base {src_mon.base_species_id!r}) "
            f"but mega_form base is {mega_form.base_species_id!r}"
        )

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

    # Delegate spread resolution to the single central resolver. Do NOT preflight the
    # foe with lookup_opp_set: speed_for_species already implements the binding order
    # (book first, then opp_sets) and raises MissingMegaSpreadError only when both
    # fail -- a manual pre-check would reject a valid book-only hypothesis.
    effective_speed = speed_oracle.speed_for_species(
        species_name=form_meta.form_species_name,
        base_species_id=mega_form.base_species_id,
        side=side,
        mon=mon,
        field=projected_state.field,
        our_spreads=spread_lookup if is_ours else None,
        opp_sets=opp_sets if not is_ours else None,
        book=book,
        is_ours=is_ours,
    )

    return MegaProjectionResult(
        mega_form=mega_form,
        projected_state=projected_state,
        mega_slot=slot,
        own_mega_slot=_SLOT_TO_INDEX.get(slot),
        effective_speed=effective_speed,
    )


@dataclass(frozen=True)
class WeightedMegaProjection:
    projected_state: BattleState
    weight: float
    activation_order: tuple[tuple[str, str], ...]


def compose_mega_projection_branches(
    state: BattleState,
    activations: list[tuple[str, str, MegaForm]],
    *,
    our_side: str,
    speed_oracle: SpeedOracle,
    our_spreads: dict | None,
    opp_sets: dict | None,
    book=None,
    species_meta: dict[str, SpeciesFormMeta],
    calc_profile: CalcProfile,
) -> list[WeightedMegaProjection]:
    """Compose 1+ same-turn Mega activations (at most one per side) onto shared
    branch(es). ``our_side`` disambiguates which activation(s) use the own-side
    spread lookup (``our_spreads``) vs the foe-side lookup (``opp_sets``/``book``)
    via the side-aware ``project_mega`` contract -- never guesses which
    activation is "ours" from list order.

    Unequal pre-mega speed -> one branch, weight 1.0. Equal pre-mega speed ->
    two branches (one per activation-order permutation), each weight 0.5,
    applied sequentially so the LATER activation in that branch's specific
    order overwrites the earlier one's field effects (verified against pinned
    Showdown mechanics -- see the weather-ordering test; this is a single
    consistent rule for both the tied and unequal-speed cases). Never mutates
    ``state``. No RNG."""
    from showdown_bot.engine.speed import mega_activation_order_key

    pre_mega_speeds: dict[tuple[str, str], int] = {}
    for side, slot, _form in activations:
        mon = state.sides[side][slot]
        is_ours = side == our_side
        pre_mega_speeds[(side, slot)] = speed_oracle.speed_for_species(
            species_name=mon.species, base_species_id=mon.base_species_id or mon.species,
            side=side, mon=mon, field=state.field,
            our_spreads=our_spreads if is_ours else None,
            opp_sets=opp_sets if not is_ours else None,
            book=book, is_ours=is_ours,
        )

    sorted_order = tuple(
        sorted(
            ((side, slot) for side, slot, _form in activations),
            key=lambda pair: mega_activation_order_key(pre_mega_speeds[pair], state.field),
        )
    )

    is_tie = len(activations) == 2 and pre_mega_speeds[sorted_order[0]] == pre_mega_speeds[sorted_order[1]]
    orderings = [sorted_order, tuple(reversed(sorted_order))] if is_tie else [sorted_order]
    weight = 0.5 if is_tie else 1.0

    branches: list[WeightedMegaProjection] = []
    by_pair = {(side, slot): form for side, slot, form in activations}
    for order in orderings:
        projected = copy_battle_state(state)
        for side, slot in order:
            form = by_pair[(side, slot)]
            is_ours = side == our_side
            step = project_mega(
                projected, side, slot, form, species_meta=species_meta,
                speed_oracle=speed_oracle, calc_profile=calc_profile,
                is_ours=is_ours,
                spread_lookup=our_spreads if is_ours else None,
                opp_sets=opp_sets if not is_ours else None,
                book=book,
            )
            projected = step.projected_state
        branches.append(WeightedMegaProjection(projected_state=projected, weight=weight, activation_order=order))
    return branches

from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.battle.actions import JointAction
from showdown_bot.engine.calc_profile import CalcProfile
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.mega_projection import (
    UnsupportedMegaAbilityError,
    project_mega,
)
from showdown_bot.engine.species_meta import SpeciesFormMeta
from showdown_bot.engine.speed import MissingMegaSpreadError, SpeedOracle
from showdown_bot.engine.state import BattleState
from showdown_bot.models.request import BattleRequest

_ACTIVE_SLOTS = ("a", "b")


@dataclass(frozen=True)
class ScoredMegaVariant:
    joint: JointAction
    own_mega_slot: int | None


def _active_mon(req: BattleRequest, active_index: int):
    actives = [p for p in req.side.pokemon if p.active]
    if 0 <= active_index < len(actives):
        return actives[active_index]
    return None


def _slot_can_mega(req: BattleRequest, active_index: int, state: BattleState, our_side: str) -> bool:
    if state.side_mega_spent.get(our_side, False):
        return False
    if not req.active or active_index >= len(req.active):
        return False
    active = req.active[active_index]
    if active is None or not active.can_mega_evo:
        return False
    mon = _active_mon(req, active_index)
    if mon is None:
        return False
    from showdown_bot.engine.state import parse_details

    species = parse_details(mon.details).species
    item = mon.item
    if not item:
        return False
    return mega_form_for(species, item) is not None


def expand_mega_variants(
    base_joints: list[JointAction],
    req: BattleRequest,
    state: BattleState,
    our_side: str,
) -> list[ScoredMegaVariant]:
    out: list[ScoredMegaVariant] = []
    for joint in base_joints:
        out.append(ScoredMegaVariant(joint=joint, own_mega_slot=None))
        if _slot_can_mega(req, 0, state, our_side):
            mega_joint = joint.with_mega(0)
            if mega_joint.slot0.mega_evolve:
                out.append(ScoredMegaVariant(joint=mega_joint, own_mega_slot=0))
        if _slot_can_mega(req, 1, state, our_side):
            mega_joint = joint.with_mega(1)
            if mega_joint.slot1.mega_evolve:
                out.append(ScoredMegaVariant(joint=mega_joint, own_mega_slot=1))
    return out

def filter_projectable_variants(
    variants: list[ScoredMegaVariant],
    req: BattleRequest,
    state: BattleState,
    our_side: str,
    *,
    species_meta: dict[str, SpeciesFormMeta],
    speed_oracle: SpeedOracle,
    our_spreads: dict,
    calc_profile: CalcProfile,
) -> list[ScoredMegaVariant]:
    kept: list[ScoredMegaVariant] = []
    projected_slots: set[int] = set()

    for variant in variants:
        if variant.own_mega_slot is None:
            kept.append(variant)
            continue
        if variant.own_mega_slot in projected_slots:
            kept.append(variant)
            continue
        active_index = variant.own_mega_slot
        mon = _active_mon(req, active_index)
        if mon is None:
            continue
        from showdown_bot.engine.state import parse_details

        species = parse_details(mon.details).species
        item = mon.item
        if not item:
            continue
        form = mega_form_for(species, item)
        if form is None:
            continue
        slot = _ACTIVE_SLOTS[active_index]
        try:
            project_mega(
                state,
                our_side,
                slot,
                form,
                species_meta=species_meta,
                speed_oracle=speed_oracle,
                spread_lookup=our_spreads,
                calc_profile=calc_profile,
            )
        except (UnsupportedMegaAbilityError, MissingMegaSpreadError, ValueError):
            continue
        projected_slots.add(variant.own_mega_slot)
        kept.append(variant)

    return kept

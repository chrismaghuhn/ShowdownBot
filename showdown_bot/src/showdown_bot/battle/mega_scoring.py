from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.decision import _plan_my_actions
from showdown_bot.battle.evaluate import DamageModel
from showdown_bot.battle.mega_variants import (
    _active_mon,
    expand_mega_variants,
    filter_projectable_variants,
)
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.calc_profile import CalcProfile
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.mega_projection import (
    MegaProjectionResult,
    UnsupportedMegaAbilityError,
    copy_battle_state,
    project_mega,
)
from showdown_bot.engine.speed import MissingMegaSpreadError, SpeedOracle
from showdown_bot.engine.species_meta import SpeciesFormMeta
from showdown_bot.engine.state import BattleState, FieldState, parse_details
from showdown_bot.models.request import BattleRequest

_ACTIVE_SLOTS = ("a", "b")


@dataclass
class MegaEvaluationContext:
    """One evaluation branch for our own Mega decision (design spec Sec.6.1).

    I7a scope only: ``foe_mega_slot`` is always ``None`` and ``branch_weight``
    is always ``1.0`` (dual-Mega branch weighting is I7b, out of scope here).
    ``plans`` holds only OUR joint-action plans for this branch -- opponent
    responses are not modeled by this DTO.
    """

    context_id: str
    projected_state: BattleState
    own_mega_slot: int | None
    foe_mega_slot: int | None
    branch_weight: float
    activation_order: tuple[tuple[str, str], ...] | None
    field: FieldState
    plans: dict[JointAction, list[PlannedAction]]
    damage_model: DamageModel


def _none_context(
    req: BattleRequest,
    state: BattleState,
    *,
    our_side: str,
    opp_side: str,
    book: SpreadBook,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle | None,
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    my_actions: list[JointAction],
) -> MegaEvaluationContext:
    """The "we did not Mega evolve this turn" branch. Still gets its own
    independently-owned ``projected_state`` copy (never the caller's live
    object) so every context in the returned list has uniform ownership
    semantics, matching the Mega branches."""
    projected_state = copy_battle_state(state)
    plans = {
        ja: _plan_my_actions(
            req, ja, state=projected_state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
        )
        for ja in my_actions
    }
    model = DamageModel(
        projected_state, our_side, opp_side, book=book, oracle=oracle,
        field=projected_state.field, our_spreads=our_spreads, opp_sets=opp_sets,
        calc_profile=calc_profile,
    )
    return MegaEvaluationContext(
        context_id="own_mega:none",
        projected_state=projected_state,
        own_mega_slot=None,
        foe_mega_slot=None,
        branch_weight=1.0,
        activation_order=None,
        field=projected_state.field,
        plans=plans,
        damage_model=model,
    )


def _mega_context(
    req: BattleRequest,
    state: BattleState,
    *,
    own_mega_slot: int,
    our_side: str,
    opp_side: str,
    book: SpreadBook,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle,
    species_meta: dict[str, SpeciesFormMeta],
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    variant_joints: list[JointAction],
) -> MegaEvaluationContext | None:
    """The "we Mega evolved ``own_mega_slot`` this turn" branch. Re-derives the
    ``MegaProjectionResult`` (already proven projectable by the caller's
    ``filter_projectable_variants`` pass) to get an independent projected-state
    copy plus the projected form's post-Mega speed, and feeds that speed
    straight into ``_plan_my_actions`` via ``planned_speed_overrides_by_slot``
    (spec Sec.5.2: move order after Mega uses POST-Mega speed)."""
    mon = _active_mon(req, own_mega_slot)
    if mon is None:
        return None
    species = parse_details(mon.details).species
    item = mon.item
    if not item:
        return None
    form = mega_form_for(species, item)
    if form is None:
        return None
    slot_letter = _ACTIVE_SLOTS[own_mega_slot]
    try:
        proj: MegaProjectionResult = project_mega(
            state, our_side, slot_letter, form,
            species_meta=species_meta, speed_oracle=speed_oracle,
            spread_lookup=our_spreads or {}, calc_profile=calc_profile,
        )
    except (UnsupportedMegaAbilityError, MissingMegaSpreadError, ValueError):
        return None

    projected_state = proj.projected_state
    overrides = {own_mega_slot: proj.effective_speed}
    plans = {
        ja: _plan_my_actions(
            req, ja, state=projected_state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
            planned_speed_overrides_by_slot=overrides,
        )
        for ja in variant_joints
    }
    model = DamageModel(
        projected_state, our_side, opp_side, book=book, oracle=oracle,
        field=projected_state.field, our_spreads=our_spreads, opp_sets=opp_sets,
        calc_profile=calc_profile,
    )
    return MegaEvaluationContext(
        context_id=f"own_mega:{own_mega_slot}",
        projected_state=projected_state,
        own_mega_slot=own_mega_slot,
        foe_mega_slot=None,
        branch_weight=1.0,
        activation_order=None,
        field=projected_state.field,
        plans=plans,
        damage_model=model,
    )


def build_own_mega_contexts(
    req: BattleRequest,
    state: BattleState,
    *,
    our_side: str,
    opp_side: str,
    book: SpreadBook,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle,
    species_meta: dict[str, SpeciesFormMeta],
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    my_actions: list[JointAction],
) -> list[MegaEvaluationContext]:
    """One context for ``own_mega_slot=None`` and one per surviving own Mega
    slot (design spec Sec.6.2-6.3). ``foe_mega_slot=None``/``branch_weight=1.0``
    always in I7a -- dual-Mega branch logic is out of scope here.

    Never mutates ``state``/``req``: every context owns an independent
    ``copy_battle_state``-derived ``projected_state``. Surviving Mega slots
    are exactly ``filter_projectable_variants``'s already-fail-closed output
    (Scovillain / any other unsupported-ability or missing-spread mon is
    excluded upstream; this function does not weaken that gate).

    Enqueues every context's plans into the SHARED ``oracle`` WITHOUT
    flushing -- batching multiple contexts into one Node round trip is a
    later caller's job (Task 3).
    """
    contexts = [
        _none_context(
            req, state, our_side=our_side, opp_side=opp_side, book=book,
            oracle=oracle, speed_oracle=speed_oracle, our_spreads=our_spreads,
            opp_sets=opp_sets, calc_profile=calc_profile, my_actions=my_actions,
        )
    ]

    variants = expand_mega_variants(list(my_actions), req, state, our_side)
    variants = filter_projectable_variants(
        variants, req, state, our_side, species_meta=species_meta,
        speed_oracle=speed_oracle, our_spreads=our_spreads or {},
        calc_profile=calc_profile,
    )
    surviving_slots = sorted(
        {v.own_mega_slot for v in variants if v.own_mega_slot is not None}
    )

    for slot_idx in surviving_slots:
        variant_joints = [v.joint for v in variants if v.own_mega_slot == slot_idx]
        ctx = _mega_context(
            req, state, own_mega_slot=slot_idx, our_side=our_side, opp_side=opp_side,
            book=book, oracle=oracle, speed_oracle=speed_oracle,
            species_meta=species_meta, our_spreads=our_spreads, opp_sets=opp_sets,
            calc_profile=calc_profile, variant_joints=variant_joints,
        )
        if ctx is not None:
            contexts.append(ctx)

    for ctx in contexts:
        ctx.damage_model.enqueue(list(ctx.plans.values()))

    return contexts

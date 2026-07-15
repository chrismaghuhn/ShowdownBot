from __future__ import annotations

import os
from dataclasses import dataclass

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.decision import _plan_my_actions
from showdown_bot.battle.evaluate import DamageModel, EvalWeights, LineEvaluation, _evaluate_line_details
from showdown_bot.battle.mega_variants import (
    ScoredMegaVariant,
    expand_mega_variants,
    filter_projectable_variants,
)
from showdown_bot.battle.opponent import SpeciesDex, predict_responses
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.policy import aggregate_scores
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.belief.world_sampler import (
    build_world_dist, sample_worlds, world_samples, world_seed,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc_profile import CalcProfile
from showdown_bot.engine.mega_projection import (
    MegaProjectionResult,
    copy_battle_state,
)
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.species_meta import SpeciesFormMeta
from showdown_bot.engine.state import BattleState, FieldState, to_id
from showdown_bot.models.request import BattleRequest


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
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    variant_joints: list[JointAction],
    proj: MegaProjectionResult,
) -> MegaEvaluationContext | None:
    """The "we Mega evolved ``own_mega_slot`` this turn" branch. Consumes the
    ``MegaProjectionResult`` the caller's ``filter_projectable_variants`` pass
    already computed while proving this slot projectable, instead of calling
    ``project_mega`` again (that call is a full ``copy_battle_state`` deepcopy
    plus species/spread lookups -- not worth doubling per slot). Builds an
    independent projected-state copy plus the projected form's post-Mega
    speed, and feeds that speed straight into ``_plan_my_actions`` via
    ``planned_speed_overrides_by_slot`` (spec Sec.5.2: move order after Mega
    uses POST-Mega speed)."""
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
    projections: dict[int, MegaProjectionResult] = {}
    variants = filter_projectable_variants(
        variants, req, state, our_side, species_meta=species_meta,
        speed_oracle=speed_oracle, our_spreads=our_spreads or {},
        calc_profile=calc_profile, projections=projections,
    )
    surviving_slots = sorted(
        {v.own_mega_slot for v in variants if v.own_mega_slot is not None}
    )

    for slot_idx in surviving_slots:
        proj = projections.get(slot_idx)
        if proj is None:
            # Should not happen: filter_projectable_variants only keeps a
            # slot in `variants` after successfully populating `projections`
            # for it. Guard defensively rather than assume the invariant.
            continue
        variant_joints = [v.joint for v in variants if v.own_mega_slot == slot_idx]
        ctx = _mega_context(
            req, state, own_mega_slot=slot_idx, our_side=our_side, opp_side=opp_side,
            book=book, oracle=oracle, speed_oracle=speed_oracle,
            our_spreads=our_spreads, opp_sets=opp_sets,
            calc_profile=calc_profile, variant_joints=variant_joints, proj=proj,
        )
        if ctx is not None:
            contexts.append(ctx)

    for ctx in contexts:
        ctx.damage_model.enqueue(list(ctx.plans.values()))

    return contexts


@dataclass
class MegaScoreRecord:
    """One scored Mega candidate (design spec Sec.6.4-6.5; I7a-B Task 3 binding
    score-record contract). ``score_vector``/``score_weights`` are POOLED across
    every sampled world (parallel arrays, same length); ``diagnostic_details``/
    ``diagnostic_weights`` are world-0-ONLY (parallel arrays, same length, always
    <= the pooled arrays' length). The two pairs must never be mixed: a
    denominator built from one pair must never divide values keyed by the
    other (see ``score_evaluated_variants`` / the I7a-B plan's binding
    contract -- a wrong-denominator bug would silently corrupt every displayed
    percentage-of-max diagnostic even though ranking, which only reads
    ``aggregate_score``, would stay correct)."""

    variant: ScoredMegaVariant
    score_vector: list[float]
    score_weights: list[float] | None
    diagnostic_details: list[LineEvaluation]
    diagnostic_weights: list[float] | None
    aggregate_score: float = 0.0


def _world_seed_board_key(state: BattleState, opp_side: str) -> str:
    """Local duplicate of ``decision._board_key`` (a stable per-decision string
    for seeding the world sampler: opponent species + hp buckets + field).
    Deliberately NOT imported from ``decision.py`` -- this module already
    imports ``decision._plan_my_actions``, and ``decision.py`` is expected to
    import from this module in a later integration slice (I7a-B Task 4); a
    mutual module-level import in both directions would be a circular import.
    Kept byte-identical to ``decision._board_key`` on purpose (same board ->
    same worlds, regardless of which module computes the seed)."""
    parts = []
    for slot, mon in sorted(state.side(opp_side).items()):
        parts.append(f"{slot}:{mon.species}:{int((mon.hp_fraction or 0) * 20)}")
    field_state = getattr(state, "field", None)
    return "|".join(parts) + "#" + str(field_state)


def score_evaluated_variants(
    evaluated_variants: list[ScoredMegaVariant],
    contexts: list[MegaEvaluationContext],
    *,
    req: BattleRequest,
    state: BattleState,
    book: SpreadBook,
    our_side: str,
    opp_side: str,
    calc: CalcClient,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle | None,
    dex: SpeciesDex | None,
    priors=None,
    weights: EvalWeights,
    mode: GameMode,
    risk_lambda: float,
    rollout_horizon: int,
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    accuracy_mode: bool,
    accuracy_branch_cap: int,
    endgame: bool,
    fast_board: bool,
) -> list[MegaScoreRecord]:
    """Expand no actions -- score exactly the supplied ``evaluated_variants``
    against the already-built ``contexts`` (I7a-B Task 3).

    ``contexts`` is the (single) prior ``build_own_mega_contexts(...)`` call's
    return value -- this function does NOT call ``expand_mega_variants`` /
    ``filter_projectable_variants`` again (that expansion+projectability-filter
    pass happens exactly once, upstream). ``req``/``calc`` are accepted for
    signature parity with the design-spec contract and future callers; this
    function does not itself need a live ``BattleRequest`` or a raw
    ``CalcClient`` (scoring goes through the already-built ``DamageModel``s /
    the shared ``oracle``).

    For every sampled opponent-set world (``engine.belief.world_sampler``,
    byte-identical to a single most-likely world when ``SHOWDOWN_WORLD_SAMPLES``
    <= 1 or there is no opponent-set uncertainty): for each context, predicts
    opponent responses against that context's OWN ``projected_state`` (so a
    Mega branch's opponent-response prediction sees the Mega'd typing/bulk,
    never the base mon), builds a fresh per-(context, world) ``DamageModel``
    keyed to that world's merged ``opp_sets``, and enqueues every context's
    plans plus that context's predicted responses into the SHARED ``oracle`` --
    all contexts for a given world enqueue before that world's single
    ``flush()`` (never per-context, never per-candidate).

    Every evaluated variant accumulates its (world, response) scores into a
    pooled ``score_vector``/``score_weights`` (all worlds). Only world index 0
    (always the most-likely world; ``sample_worlds`` guarantees this) also
    contributes its ``LineEvaluation`` objects and RAW (not world-weight-scaled)
    response weights to ``diagnostic_details``/``diagnostic_weights`` -- written
    exactly once per candidate, never accumulated across worlds.
    """
    ctx_by_slot: dict[int | None, MegaEvaluationContext] = {c.own_mega_slot: c for c in contexts}
    for v in evaluated_variants:
        if v.own_mega_slot not in ctx_by_slot:
            raise ValueError(
                f"score_evaluated_variants: no MegaEvaluationContext for "
                f"own_mega_slot={v.own_mega_slot!r}"
            )

    threatened = {
        slot
        for slot, mon in state.side(opp_side).items()
        if slot in ("a", "b") and 0.0 < mon.hp_fraction <= 0.6
    }

    world_dist = None
    if world_samples() > 1:
        opp_mons = [(to_id(mon.species), mon.species) for mon in state.side(opp_side).values()]
        world_dist = build_world_dist(opp_mons, book, opp_sets or {})

    if world_dist:
        seed = world_seed(
            os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "world"),
            getattr(state, "turn", 0) or 0,
            _world_seed_board_key(state, opp_side),
        )
        worlds = sample_worlds(world_dist, world_samples(), seed=seed)
    else:
        worlds = [({}, 1.0)]

    records = [
        MegaScoreRecord(
            variant=v, score_vector=[], score_weights=[],
            diagnostic_details=[], diagnostic_weights=[],
        )
        for v in evaluated_variants
    ]
    records_by_slot: dict[int | None, list[MegaScoreRecord]] = {}
    for rec in records:
        records_by_slot.setdefault(rec.variant.own_mega_slot, []).append(rec)

    for world_idx, (world_sets, world_w) in enumerate(worlds):
        merged_sets = {**(opp_sets or {}), **world_sets}
        world_resps_by_slot: dict[int | None, list] = {}
        world_model_by_slot: dict[int | None, DamageModel] = {}

        for slot, ctx in ctx_by_slot.items():
            resps = predict_responses(
                ctx.projected_state, our_side, opp_side, speed_oracle=speed_oracle,
                book=book, dex=dex, field=ctx.field, priors=priors,
                threatened_slots=threatened, opp_sets=merged_sets,
            )
            model = DamageModel(
                ctx.projected_state, our_side, opp_side, book=book, oracle=oracle,
                field=ctx.field, our_spreads=our_spreads, opp_sets=merged_sets,
                calc_profile=calc_profile,
            )
            model.enqueue(list(ctx.plans.values()) + [r.actions for r in resps])
            world_resps_by_slot[slot] = resps
            world_model_by_slot[slot] = model

        # All contexts for THIS world are enqueued above -- flush exactly once
        # per world, never per-context (I7a-B Task 3 batching invariant).
        oracle.flush()

        for slot, ctx in ctx_by_slot.items():
            resps = world_resps_by_slot[slot]
            model = world_model_by_slot[slot]
            targets = resps if resps else [None]
            for rec in records_by_slot.get(slot, []):
                plan = ctx.plans[rec.variant.joint]
                for r in targets:
                    opp_actions = r.actions if r is not None else []
                    detail = _evaluate_line_details(
                        ctx.projected_state, plan, opp_actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=ctx.field,
                        rollout_horizon=rollout_horizon, endgame=endgame,
                        fast_board=fast_board, accuracy_mode=accuracy_mode,
                        accuracy_branch_cap=accuracy_branch_cap,
                    )
                    raw_w = r.weight if (priors is not None and r is not None) else 1.0
                    rec.score_vector.append(detail.score)
                    rec.score_weights.append(world_w * raw_w)
                    if world_idx == 0:
                        rec.diagnostic_details.append(detail)
                        rec.diagnostic_weights.append(raw_w)

    for rec in records:
        rec.aggregate_score = aggregate_scores(
            rec.score_vector, mode, risk_lambda=risk_lambda, weights=rec.score_weights,
        )

    return records

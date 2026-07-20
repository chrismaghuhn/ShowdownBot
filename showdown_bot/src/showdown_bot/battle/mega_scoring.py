from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.decision import _plan_my_actions, _search_depth, _search_topm, _search_topn
from showdown_bot.battle.evaluate import DamageModel, EvalWeights, LineEvaluation, _evaluate_line_details
from showdown_bot.battle.mega_variants import (
    ScoredMegaVariant,
    expand_mega_variants,
    filter_projectable_variants,
)
from showdown_bot.battle.opponent import OppResponse, SpeciesDex, predict_responses
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.policy import aggregate_scores
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.battle.search import depth2_value_for_mega_context
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.belief.world_sampler import (
    build_world_dist, sample_worlds, world_samples, world_seed,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc_profile import CalcProfile
from showdown_bot.engine.mega_form import MegaForm, mega_form_for
from showdown_bot.engine.mega_projection import (
    MegaProjectionResult,
    copy_battle_state,
)
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.species_meta import SpeciesFormMeta
from showdown_bot.engine.state import BattleState, FieldState, to_id
from showdown_bot.models.request import BattleRequest


@dataclass
class MegaShapeCounts:
    """Optional at-origin work-set telemetry for ``score_evaluated_variants`` (I8, C3-fix).

    Every field is counted WHERE THE WORK HAPPENS, never estimated afterwards from the
    evidence sink: ``n_candidates`` is V, ``n_responses`` every scored response line,
    ``n_mega_twins`` the foe-Mega subset of those lines, ``n_branches`` every projection
    branch composed, ``n_worlds`` K, and ``depth2_frontier`` every (record, index) the
    depth-2 wrap actually refined (``0`` at depth 1 by construction).

    OFF by default: ``score_evaluated_variants(..., shape_sink=None)`` increments nothing and
    is byte-identical to the legacy path. A profile session passes one and reads it; nothing
    on the live decision path does. It is separate from ``opp_mega_evidence_sink`` on purpose
    -- that sink is per-response provenance for the opp-Mega trace, this one is a per-decision
    work-set count, and deriving the second from the first is exactly the after-the-fact
    estimation this addendum removes.
    """

    n_candidates: int = 0
    n_responses: int = 0
    n_mega_twins: int = 0
    n_branches: int = 0
    n_worlds: int = 0
    depth2_frontier: int = 0
    # v3 coverage telemetry (Task 1/2): the foe-Mega slot set actually scored ({0,1} subset) and
    # whether a full activation-order tie was scored. Filled at origin (Task 2); defaulted here so
    # a sink that predates the fill, or a non-foe-Mega decision, stays empty/False.
    foe_mega_slots: tuple[int, ...] = ()
    foe_mega_order_tie: bool = False


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
) -> tuple[list[MegaEvaluationContext], list[ScoredMegaVariant]]:
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

    Returns ``(contexts, evaluated_variants)``. ``evaluated_variants`` is
    exactly ``filter_projectable_variants(expand_mega_variants(my_actions,
    req, state, our_side), ...)``'s own return order -- interleaved per base
    joint (the base variant, then its own legal/projectable Mega variants),
    NOT grouped by ``own_mega_slot``. Callers computing ranking/tie-break/
    trace/max_damage order MUST iterate this list, never reconstruct an
    order from ``contexts`` (e.g. by grouping over each context's ``plans``
    dict) -- ``contexts`` is grouped by ``own_mega_slot`` (``[None, then
    sorted(surviving_slots)]``) and reconstructing from it silently
    reorders every non-Mega variant ahead of every Mega variant, which
    breaks first-wins tie-break semantics (Codex I7a-B merge-blocker: a tie
    between ``A+Mega`` and ``B`` must resolve to ``A+Mega`` because it is
    enumerated immediately after ``A``, before ``B``, in the true expand
    order -- not to whichever variant a grouped-by-slot reconstruction
    happens to place first).
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

    return contexts, variants


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
    diagnostic_contexts: list["MegaEvaluationContext"] = field(default_factory=list)
    # World-0-only, same length/cadence as diagnostic_details/diagnostic_weights
    # (never populated for pooled-world indices beyond world 0): records WHICH
    # MegaEvaluationContext each diagnostic index's detail/outcome was actually
    # computed against -- the pre-existing own-mega-only ctx for a no-mega
    # index, or that specific foe-mega branch's own branch_ctx for a foe-mega
    # index. Task 6 depends on this to bind depth-2 to the CORRECT context per
    # index, since a record's own top-M diagnostic indices may span both a
    # no-mega response and one or more foe-mega branch responses.


@dataclass(frozen=True)
class ScoredResponseEvidence:
    """One (candidate, opponent response, Mega branch) scored contribution --
    NOT persisted to decision-trace-v3 (battle_id/decision_index co-location
    does not prove which candidate was scored against which response). Raw
    components only -- NOT a pre-multiplied "contribution": aggregate_scores
    (policy.py) is non-linear under MUST_REACT (`mean - lambda*(mean-min)`) and
    NEUTRAL (`mean - lambda*variance`), so no single per-response product is the
    correct "contribution" under both operators; consumers multiply these
    components themselves per their own operator. Built inline during scoring;
    consumed directly by eval/opp_mega_trace.py (I7b-C), never reconstructed
    after the fact."""

    candidate_key: str
    response_id: str
    foe_mega_slot: int | None
    branch_index: int
    branch_weight: float
    world_index: int
    world_weight: float
    response_weight: float
    raw_score: float
    required_classes: tuple[str, ...]
    retained_classes: tuple[str, ...]


@dataclass(frozen=True)
class _BranchResponsePair:
    """Original hypothesis metadata plus actions replanned on the branch.

    ``original`` owns response_id/foe_mega_slot/weight after I7b-A's click-rate,
    cap, and renormalization pipeline. ``replanned`` owns only the actions that
    see the branch's projected state, weather, species, and speeds.
    """

    original: OppResponse
    replanned: OppResponse


class MissingBranchResponseError(ValueError):
    """A foe-Mega branch's re-generated predict_responses() call did not
    reproduce one of the original top-M response labels (e.g.
    revealed_support becoming newly available post-Mega). Fail closed rather
    than silently drop or mismatch a response."""


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


def _is_scored_order_tie(orderings: set) -> bool:
    """Task 2: True iff a foe-Mega interaction's SCORED branches are exactly the two
    mutually-reversed 0.5-weighted activation orderings (a full tie pair). A lone 0.5 branch, or a
    1.0 (strict-inequality) branch, is NOT a tie. ``orderings`` is a set of (branch_weight,
    activation_order) actually scored for that (own_slot, foe_mega_slot) interaction."""
    halves = [order for (weight, order) in orderings if weight == 0.5]
    if len(halves) != 2:
        return False
    a, b = halves
    return a == tuple(reversed(b))


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
    mode: GameMode | None = None,
    resolve_mode=None,
    risk_lambda: float,
    rollout_horizon: int,
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    accuracy_mode: bool,
    accuracy_branch_cap: int,
    endgame: bool,
    fast_board: bool,
    foe_mega_eligibility: dict[str, MegaForm] | None = None,
    species_meta: dict[str, SpeciesFormMeta] | None = None,
    opp_mega_evidence_sink: list[ScoredResponseEvidence] | None = None,
    shape_sink: MegaShapeCounts | None = None,
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

    if shape_sink is not None:
        # V and K, set once at origin. The remaining counts accumulate as the work is done.
        shape_sink.n_candidates = len(records)
        shape_sink.n_worlds = len(worlds)
    # Task 2 coverage telemetry: decision-level accumulators. The scored foe-Mega slots, and per
    # (world_idx, own_slot, foe_mega_slot) interaction the set of (branch_weight, activation_order)
    # actually scored -- world_idx keeps two different sampled worlds' branches from being pooled
    # into a false tie (a genuine tie is both reversed orderings scored within ONE world). Written
    # onto shape_sink ONLY at successful completion, so a mid-scoring abort leaves
    # foe_mega_slots/foe_mega_order_tie at their defaults.
    _cov_scored_slots: set[int] = set()
    _cov_tie_orderings: dict[tuple, set] = {}

    from showdown_bot.battle.candidate_identity import joint_action_key_v2
    from showdown_bot.battle.opponent import OpponentResponseCapError, opp_mega_click_rate
    from showdown_bot.engine.mega_projection import (
        UnsupportedMegaAbilityError,
        compose_mega_projection_branches,
    )
    from showdown_bot.engine.speed import MissingMegaSpreadError

    _click_rate = opp_mega_click_rate() if foe_mega_eligibility else None
    _i7b_active = bool(foe_mega_eligibility)
    # [REV.9 finding 3] Evidence is built inline during Phase C, but the depth-2 wrap
    # below OVERWRITES rec.score_vector[i] in place afterwards and aggregate_scores()
    # consumes THAT final vector. So an evidence row must not keep the 1-ply
    # detail.score it was built from -- that number is superseded and never entered
    # the decision. Each pending row therefore carries its (record, score_index)
    # binding, and raw_score is resolved from rec.score_vector at the very end. The
    # caller's sink is extended only then, so it can never be observed holding a
    # superseded value, and a mid-scoring exception leaves it untouched rather than
    # half-filled. Binding by index -- never by re-deriving from labels, which cannot
    # distinguish a no-mega response from its foe-Mega twin on a rebuilt board.
    _pending_evidence: list[tuple[ScoredResponseEvidence, MegaScoreRecord, int]] = []

    for world_idx, (world_sets, world_w) in enumerate(worlds):
        merged_sets = {**(opp_sets or {}), **world_sets}
        world_resps_by_slot: dict[int | None, list[OppResponse]] = {}
        world_model_by_slot: dict[int | None, DamageModel] = {}
        world_no_mega_resps_by_slot: dict[int | None, list[OppResponse]] = {}
        world_coverage_by_slot: dict[int | None, tuple[tuple[str, ...], tuple[str, ...]]] = {}

        # --- Phase A, part 1: existing no-mega responses/model (byte-identical) ---
        for slot, ctx in ctx_by_slot.items():
            resps = predict_responses(
                ctx.projected_state, our_side, opp_side, speed_oracle=speed_oracle,
                book=book, dex=dex, field=ctx.field, priors=priors,
                threatened_slots=threatened, opp_sets=merged_sets,
                foe_mega_eligibility=foe_mega_eligibility, opp_mega_click_rate=_click_rate,
            )
            model = DamageModel(
                ctx.projected_state, our_side, opp_side, book=book, oracle=oracle,
                field=ctx.field, our_spreads=our_spreads, opp_sets=merged_sets,
                calc_profile=calc_profile,
            )
            # [P1] A zero-weight response cannot move a weighted mean, but
            # aggregate_scores' MUST_REACT operator takes `min(scores)` WITHOUT
            # weights (policy.py) -- so a weight-0 sample DOES move the aggregate
            # ([10] w=[1] -> 10.0, but [10,-100] w=[1,0] -> -56.0). It must never be
            # enqueued, evaluated, or appended to score_vector. Only on the I7b-active
            # path: the legacy path's weights are untouched, so its behavior stays
            # byte-identical. I7b-A still EMITS the zero-weight twins upstream for
            # identity/cap coverage -- `resps` (not this filtered list) feeds
            # retained_classes below, so cap discipline is unaffected.
            no_mega_resps = [
                r for r in resps
                if r.foe_mega_slot is None and (not _i7b_active or r.weight > 0)
            ]
            required_classes = tuple(sorted(
                {"none"} | {str(0 if s == "a" else 1) for s in foe_mega_eligibility}
            )) if _i7b_active else ("none",)
            retained_classes = tuple(sorted({
                "none" if r.foe_mega_slot is None else str(r.foe_mega_slot)
                for r in resps
            }))
            if _i7b_active and not set(required_classes) <= set(retained_classes):
                raise OpponentResponseCapError(
                    f"required opponent response classes {required_classes} "
                    f"not retained by predict_responses: {retained_classes}"
                )
            model.enqueue(list(ctx.plans.values()) + [r.actions for r in no_mega_resps])
            world_resps_by_slot[slot] = resps
            world_model_by_slot[slot] = model
            world_no_mega_resps_by_slot[slot] = no_mega_resps
            world_coverage_by_slot[slot] = (required_classes, retained_classes)

        # --- Phase A, part 2: every foe-Mega branch, built ONCE per
        # (slot, foe_mega_slot, branch_idx), shared across every candidate ---
        branch_bundles: dict[tuple, dict] = {}
        for slot, ctx in ctx_by_slot.items():
            resps = world_resps_by_slot[slot]
            # sorted(), not raw set iteration: evidence rows and score_vector entries
            # are appended in this order, so an unordered iteration would make both
            # non-reproducible. [P1] weight > 0 filter: a zero-weight Mega class is
            # inert (see the no_mega filter above), so composing its branches would
            # only burn calc latency for samples that must not be scored anyway.
            foe_mega_slots = sorted({
                r.foe_mega_slot for r in resps
                if r.foe_mega_slot is not None and r.weight > 0
            })
            for foe_mega_slot in foe_mega_slots:
                own_form = None
                own_slot_key = "a" if slot == 0 else "b" if slot is not None else None
                if slot is not None:
                    own_mon = state.sides[our_side][own_slot_key]
                    own_form = mega_form_for(own_mon.species, own_mon.item) if own_mon.item else None
                activations = []
                if own_form is not None:
                    activations.append((our_side, own_slot_key, own_form))
                foe_slot_key = "a" if foe_mega_slot == 0 else "b"
                activations.append((opp_side, foe_slot_key, foe_mega_eligibility[foe_slot_key]))
                try:
                    branches = compose_mega_projection_branches(
                        state, activations, our_side=our_side, speed_oracle=speed_oracle,
                        our_spreads=our_spreads, opp_sets=merged_sets, book=book,
                        species_meta=species_meta, calc_profile=calc_profile,
                    )
                except (UnsupportedMegaAbilityError, MissingMegaSpreadError):
                    branches = []  # fail-closed: exclude, never crash the whole score

                if shape_sink is not None:
                    shape_sink.n_branches += len(branches)   # projection branches composed

                for branch_idx, branch in enumerate(branches):
                    # PokemonState carries NO effective_speed -- post-Mega speed lives
                    # on MegaProjectionResult, which compose_mega_projection_branches
                    # does not surface. Re-derive from the COMPLETE, FINAL branch state
                    # via the central resolver, so the override stays correct even if a
                    # weather-sensitive speed modifier is ever added (weather is not one
                    # today: speed_modifiers_from_state reads only boost/tailwind/
                    # paralysis/scarf/booster). Never hand-rolled stat math, never a
                    # private SpeedOracle method, never the pre-branch own-Mega context.
                    own_override = None
                    if ctx.own_mega_slot is not None:
                        own_slot_letter = "a" if ctx.own_mega_slot == 0 else "b"
                        own_projected = branch.projected_state.sides[our_side][own_slot_letter]
                        own_override = {
                            ctx.own_mega_slot: speed_oracle.speed_for_species(
                                species_name=own_projected.species,
                                base_species_id=own_projected.base_species_id or own_projected.species,
                                side=our_side,
                                mon=own_projected,
                                field=branch.projected_state.field,
                                our_spreads=our_spreads,
                                opp_sets=None,
                                book=book,
                                is_ours=True,
                            )
                        }
                    replanned_plans = {
                        joint: _plan_my_actions(
                            req, joint, state=branch.projected_state, our_side=our_side,
                            opp_side=opp_side, speed_oracle=speed_oracle,
                            planned_speed_overrides_by_slot=own_override,
                        )
                        for joint in ctx.plans
                    }
                    branch_resps = predict_responses(
                        branch.projected_state, our_side, opp_side, speed_oracle=speed_oracle,
                        book=book, dex=dex, field=branch.projected_state.field, priors=priors,
                        threatened_slots=threatened, opp_sets=merged_sets,
                    )
                    branch_resps_by_label = {r.label: r for r in branch_resps}
                    # [P1] weight > 0: same exclusion rule as the no-mega path.
                    matching_original = [
                        r for r in resps
                        if r.foe_mega_slot == foe_mega_slot and r.weight > 0
                    ]
                    for r in matching_original:
                        if r.label not in branch_resps_by_label:
                            raise MissingBranchResponseError(
                                f"branch-regenerated responses missing label {r.label!r}"
                            )
                    branch_model = DamageModel(
                        branch.projected_state, our_side, opp_side, book=book, oracle=oracle,
                        field=branch.projected_state.field, our_spreads=our_spreads,
                        opp_sets=merged_sets, calc_profile=calc_profile,
                    )
                    response_pairs = [
                        _BranchResponsePair(
                            original=original,
                            replanned=branch_resps_by_label[original.label],
                        )
                        for original in matching_original
                    ]
                    branch_model.enqueue(
                        list(replanned_plans.values())
                        + [pair.replanned.actions for pair in response_pairs]
                    )
                    # Task 6: a real MegaEvaluationContext bound to THIS branch, so
                    # depth-2's existing depth2_value_for_mega_context can be reused
                    # completely unmodified -- never a different branch's or the
                    # base own-mega-only context's projected_state/oracle.
                    branch_ctx = MegaEvaluationContext(
                        context_id=f"foe_mega:{foe_mega_slot}:{branch_idx}",
                        projected_state=branch.projected_state,
                        own_mega_slot=ctx.own_mega_slot, foe_mega_slot=foe_mega_slot,
                        branch_weight=branch.weight, activation_order=branch.activation_order,
                        field=branch.projected_state.field, plans=replanned_plans,
                        damage_model=branch_model,
                    )
                    branch_bundles[(slot, foe_mega_slot, branch_idx)] = {
                        "branch": branch, "model": branch_model,
                        "replanned_plans": replanned_plans,
                        "response_pairs": response_pairs,
                        "branch_ctx": branch_ctx,
                    }

        # --- Phase B: one shared flush for every enqueue in this world ---
        oracle.flush()
        if resolve_mode is not None and world_idx == 0:
            # Lever A: the game-mode incoming folded into THIS flush; resolve GameMode once,
            # after the first world's flush, and reuse it for every world (memoized resolver).
            # Direct callers pass a precomputed ``mode`` instead and skip this.
            mode = resolve_mode()

        # --- Phase C: evaluate weighted samples with full evidence ---
        for slot, ctx in ctx_by_slot.items():
            model = world_model_by_slot[slot]
            no_mega = world_no_mega_resps_by_slot[slot]
            if _i7b_active:
                # NO [None] fallback on the active path: at click rate 1.0 the no-mega
                # twin is zero-weight and excluded above, and this record's samples come
                # from the foe-Mega branches below. Falling back to [None] here would
                # inject a phantom no-opponent-action line at weight 1.0 -- the same
                # zero-weight distortion this filter exists to prevent, in reverse.
                targets = no_mega
            else:
                targets = no_mega if no_mega else [None]
            for rec in records_by_slot.get(slot, []):
                plan = ctx.plans[rec.variant.joint]
                candidate_key = joint_action_key_v2(rec.variant.joint)
                required_classes, retained_classes = world_coverage_by_slot[slot]

                for r in targets:
                    opp_actions = r.actions if r is not None else []
                    detail = _evaluate_line_details(
                        ctx.projected_state, plan, opp_actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=ctx.field,
                        rollout_horizon=rollout_horizon, endgame=endgame,
                        fast_board=fast_board, accuracy_mode=accuracy_mode,
                        accuracy_branch_cap=accuracy_branch_cap,
                    )
                    if shape_sink is not None:
                        shape_sink.n_responses += 1     # one scored response line (no-mega path)
                    if _i7b_active:
                        raw_w = r.weight if r is not None else 1.0  # consistent under the active path
                    else:
                        raw_w = r.weight if (priors is not None and r is not None) else 1.0  # legacy, unchanged
                    rec.score_vector.append(detail.score)
                    rec.score_weights.append(world_w * raw_w)
                    if world_idx == 0:
                        rec.diagnostic_details.append(detail)
                        rec.diagnostic_weights.append(raw_w)
                        if _i7b_active:
                            # Only on the active path. Task 6's depth-2 binding treats an
                            # EMPTY diagnostic_contexts as "pre-I7b-B, fall back to
                            # ctx_by_slot[own_mega_slot]"; populating it here on the legacy
                            # path would make that fallback dead and break the structural
                            # (not just numeric) parity claim.
                            rec.diagnostic_contexts.append(ctx)
                    if opp_mega_evidence_sink is not None:
                        _pending_evidence.append((ScoredResponseEvidence(
                            candidate_key=candidate_key,
                            response_id=(r.response_id if r is not None else "none"),
                            foe_mega_slot=None, branch_index=0, branch_weight=1.0,
                            world_index=world_idx, world_weight=world_w,
                            response_weight=raw_w, raw_score=detail.score,
                            required_classes=required_classes,
                            retained_classes=retained_classes,
                        ), rec, len(rec.score_vector) - 1))

                for (b_slot, foe_mega_slot, branch_idx), bundle in branch_bundles.items():
                    if b_slot != slot:
                        continue
                    replanned_plan = bundle["replanned_plans"][rec.variant.joint]
                    branch = bundle["branch"]
                    branch_model = bundle["model"]
                    for pair in bundle["response_pairs"]:
                        original = pair.original
                        replanned = pair.replanned
                        detail = _evaluate_line_details(
                            branch.projected_state, replanned_plan, replanned.actions,
                            branch_model.damage_fn,
                            our_side=our_side, weights=weights, field=branch.projected_state.field,
                            rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                            accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                        )
                        if shape_sink is not None:
                            shape_sink.n_responses += 1    # a scored response line...
                            shape_sink.n_mega_twins += 1   # ...on the foe-Mega branch path
                            # Task 2: this foe slot was positively scored; record it and this
                            # branch's (weight, activation_order) for the interaction's tie test.
                            # Keyed by world_idx too: a genuine tie is both reversed orderings scored
                            # WITHIN ONE world's own resolution of the ambiguity, never one world's
                            # lone half pooled with a different world's lone (coincidentally reversed)
                            # half -- each sampled world can imply a different speed/spread
                            # assumption, so two worlds each contributing one half never proves either
                            # world actually faced a tie (review finding, offline-reproduced).
                            _cov_scored_slots.add(foe_mega_slot)
                            _cov_tie_orderings.setdefault((world_idx, slot, foe_mega_slot), set()).add(
                                (branch.weight, branch.activation_order)
                            )
                        raw_w = original.weight
                        rec.score_vector.append(detail.score)
                        rec.score_weights.append(world_w * raw_w * branch.weight)
                        if world_idx == 0:
                            rec.diagnostic_details.append(detail)
                            rec.diagnostic_weights.append(raw_w * branch.weight)
                            rec.diagnostic_contexts.append(bundle["branch_ctx"])  # Task 6
                        if opp_mega_evidence_sink is not None:
                            _pending_evidence.append((ScoredResponseEvidence(
                                candidate_key=candidate_key, response_id=original.response_id,
                                foe_mega_slot=original.foe_mega_slot, branch_index=branch_idx,
                                branch_weight=branch.weight, world_index=world_idx,
                                world_weight=world_w, response_weight=raw_w,
                                raw_score=detail.score,
                                required_classes=required_classes,
                                retained_classes=retained_classes,
                            ), rec, len(rec.score_vector) - 1))

    # Lever A fail-closed: GameMode must be set -- either a precomputed ``mode`` was passed, or
    # ``resolve_mode`` resolved it on world 0 (there is always >= 1 world). A refactor that skipped
    # the resolve would otherwise score with an unset mode.
    assert mode is not None, "score_evaluated_variants needs mode= or resolve_mode()"

    if _search_depth() > 1 and world_samples() <= 1:
        # --- depth-2 wrap for the Mega grid (I7a-B Task 1 follow-up; mirrors
        # decision.py's single-world depth-2 wrap in spirit): base AND
        # own-Mega candidates are ranked together in the SAME grid for the
        # global top-N frontier (by their still-1-ply aggregate score); each
        # selected record's own top-M response slots (by ITS OWN
        # diagnostic_weights -- responses differ per context, since a Mega
        # branch's board differs) get overwritten with
        # search.depth2_value_for_mega_context, bound to THAT record's own
        # context (never another context's projected_state/oracle -- see
        # depth2_value_for_mega_context's own binding-rule docstring). Only
        # world 0 (always present) has ``diagnostic_details``/
        # ``diagnostic_weights`` populated; that is also the only world that
        # exists when this gate is true (``world_samples() <= 1``), so
        # ``score_vector``'s indices line up with them one-to-one here.
        top_n = _search_topn()
        top_m = _search_topm()
        ranked_pos = sorted(
            range(len(records)),
            key=lambda i: aggregate_scores(
                records[i].score_vector, mode, risk_lambda=risk_lambda,
                weights=records[i].score_weights,
            ),
            reverse=True,
        )
        d2_predict_kwargs = {"dex": dex, "speed_oracle": speed_oracle}
        d2_model_kwargs = {
            "our_spreads": our_spreads, "opp_sets": opp_sets, "calc_profile": calc_profile,
        }
        # [accuracy-slice parity] Deliberately excludes accuracy_mode/
        # accuracy_branch_cap -- same known, accepted gap as decision.py's
        # non-Mega depth-2 wrap (see its own comment there): depth-2
        # refinement is out of scope for the accuracy slice.
        d2_eval_kwargs = {
            "weights": weights, "rollout_horizon": rollout_horizon,
            "endgame": endgame, "fast_board": fast_board,
        }
        for pos in ranked_pos[:top_n]:
            rec = records[pos]
            resp_ws = rec.diagnostic_weights or [1.0] * len(rec.score_vector)
            top_m_idx = sorted(range(len(resp_ws)), key=lambda i: -resp_ws[i])[:top_m]

            for i in top_m_idx:
                if shape_sink is not None:
                    shape_sink.depth2_frontier += 1   # this (record, index) is actually refined
                outcome = rec.diagnostic_details[i].representative_outcome
                # Task 6: bind to THIS index's own context -- the own-only ctx_by_slot
                # entry for a no-mega index, or that specific foe-mega branch's own
                # branch_ctx for a foe-mega index. A record's top-M may legitimately
                # span both, since Task 4 interleaves foe-Mega branch responses into
                # the same score_vector/diagnostic_details arrays; binding one blanket
                # ctx_by_slot[rec.variant.own_mega_slot] to every index refined a
                # foe-Mega branch's diagnostic against the own-only board.
                # diagnostic_contexts is EMPTY on the legacy/I7a path (Task 4 populates
                # it only when _i7b_active), so the else-branch preserves pre-I7b-B
                # behavior byte-identically.
                bound_ctx = (
                    rec.diagnostic_contexts[i]
                    if rec.diagnostic_contexts
                    else ctx_by_slot[rec.variant.own_mega_slot]
                )
                rec.score_vector[i] = depth2_value_for_mega_context(
                    bound_ctx,
                    outcome,
                    our_side=our_side,
                    mode=mode,
                    risk_lambda=risk_lambda,
                    top_m=2,
                    book=book,
                    predict_kwargs=d2_predict_kwargs,
                    model_kwargs=d2_model_kwargs,
                    eval_kwargs=d2_eval_kwargs,
                )

    # [REV.9 finding 3] Finalise evidence AFTER the depth-2 wrap and BEFORE the
    # aggregate below, resolving each row's raw_score from the score_vector slot it
    # was bound to. Index-parallel by construction: within a record, Phase C appends
    # to rec.score_vector and to _pending_evidence in lockstep, so slot i of that
    # record's rows is slot i of its vector -- exactly the values aggregate_scores()
    # is about to consume. Rows whose index depth-2 never touched resolve back to
    # their own 1-ply value unchanged, so the depth-1/legacy path is untouched.
    if opp_mega_evidence_sink is not None:
        opp_mega_evidence_sink.extend(
            ev if ev.raw_score == rec.score_vector[i]
            else replace(ev, raw_score=rec.score_vector[i])
            for ev, rec, i in _pending_evidence
        )

    for rec in records:
        rec.aggregate_score = aggregate_scores(
            rec.score_vector, mode, risk_lambda=risk_lambda, weights=rec.score_weights,
        )

    # Task 2: finalize the coverage cell fields onto the sink -- reached ONLY on successful
    # completion, so a decision that aborted mid-scoring keeps them at their defaults.
    if shape_sink is not None:
        shape_sink.foe_mega_slots = tuple(sorted(_cov_scored_slots))
        shape_sink.foe_mega_order_tie = any(
            _is_scored_order_tie(orders) for orders in _cov_tie_orderings.values()
        )

    return records

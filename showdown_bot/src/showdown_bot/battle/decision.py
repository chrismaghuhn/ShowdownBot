from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.battle.evaluate import DamageModel, EvalWeights, evaluate_line
from showdown_bot.battle.opponent import SpeciesDex, predict_responses
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.policy import _risk_lambda, aggregate_scores, pick_best, tera_decision
from showdown_bot.battle.random_agent import pick_default_pair, pick_random_pair
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.battle.search import depth2_value
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.belief.game_mode import classify_game_mode
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.belief.world_sampler import (
    build_world_dist, sample_worlds, world_samples, world_seed,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, to_id
from showdown_bot.models.actions import SlotAction
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview

logger = logging.getLogger(__name__)

_SLOTS = ["a", "b"]

TOP_K_TRACE_CANDIDATES = 6


def _default_rollout_horizon() -> int:
    """Multi-turn rollout horizon, overridable via ``SHOWDOWN_ROLLOUT_HORIZON``
    (0 disables the rollout). Lets us A/B the rollout from the gauntlet."""
    try:
        return int(os.environ.get("SHOWDOWN_ROLLOUT_HORIZON", "2"))
    except ValueError:
        return 2


def _fast_board_protect_weight() -> float:
    """``SHOWDOWN_FAST_BOARD_PROTECT_PENALTY`` -> ``EvalWeights.fast_board_protect``
    (float; default ``0.0`` keeps it OFF -> byte-identical scores). Independently
    gated from ``SHOWDOWN_PROTECT_PENALTY``: this atlas-aimed penalty is a separate
    lever and stays off even when the historic Protect-stall penalty is on."""
    try:
        return float(os.environ.get("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", "0.0"))
    except ValueError:
        return 0.0


def _search_depth() -> int:
    """Search depth (SHOWDOWN_SEARCH_DEPTH), clamped to {1, 2}. Default/unparsable
    -> 1 (verbatim 1-ply = byte-identical). >=2 -> approximate depth-2."""
    try:
        return 2 if int(os.environ.get("SHOWDOWN_SEARCH_DEPTH", "1")) >= 2 else 1
    except ValueError:
        return 1


def _search_topn() -> int:
    """Depth-2 candidate frontier cap N (SHOWDOWN_SEARCH_TOPN): how many of our
    top-1-ply-ranked turn-1 candidates get expanded to depth-2. Default 2,
    clamped >=1. Unused unless SHOWDOWN_SEARCH_DEPTH>=2 (see ``_search_depth``)
    -- deliberately NOT BEHAVIOR_AFFECTING (see config_env), since it cannot
    affect output at depth=1."""
    try:
        v = int(os.environ.get("SHOWDOWN_SEARCH_TOPN", "2"))
    except ValueError:
        return 2
    return max(1, v)


def _search_topm() -> int:
    """Depth-2 response frontier cap M1 (SHOWDOWN_SEARCH_TOPM): how many of a
    selected candidate's opponent-response slots (the highest-weight ones) get
    expanded to depth-2. Default 2, clamped >=1. Same non-BEHAVIOR_AFFECTING
    rationale as ``_search_topn``."""
    try:
        v = int(os.environ.get("SHOWDOWN_SEARCH_TOPM", "2"))
    except ValueError:
        return 2
    return max(1, v)


def _accuracy_mode() -> bool:
    """``SHOWDOWN_ACCURACY_MODE``: on/off switch for hit/miss branching in evaluate_line.
    Default-on when the env key is absent. Explicit off via ``""``, ``"0"``, or ``"false"``
    (case-insensitive). Uses an EXPLICIT off-list, not ``bool(os.environ.get(...))`` --
    that shortcut treats the STRING ``"0"`` or ``"false"`` as truthy, which is wrong here."""
    if "SHOWDOWN_ACCURACY_MODE" not in os.environ:
        return True
    raw = os.environ["SHOWDOWN_ACCURACY_MODE"].strip().lower()
    return raw not in ("0", "false", "")


def _accuracy_branch_cap() -> int:
    """Max resolve_turn calls per resolve_turn_branches expansion
    (SHOWDOWN_ACCURACY_BRANCH_CAP). Default 6, clamped >=1. Only consulted when
    _accuracy_mode() is on."""
    try:
        v = int(os.environ.get("SHOWDOWN_ACCURACY_BRANCH_CAP", "6"))
    except ValueError:
        return 6
    return max(1, v)


def _applied_damage_from_outcome(outcome, state: BattleState) -> dict[tuple[str, str], float]:
    """Absolute-HP damage per (side, slot) from a turn-1 ``TurnOutcome``, for
    ``approx_turn2_state``. ``hp_delta`` is FRACTIONAL (new_frac - start_frac,
    <=0 for damage); convert to absolute HP via the CURRENT (turn-1) max_hp.
    Heals (delta>=0) contribute no subtraction."""
    dmg: dict[tuple[str, str], float] = {}
    for (side, slot), delta in outcome.hp_delta.items():
        if delta >= 0:
            continue
        mon = state.sides.get(side, {}).get(slot)
        if mon is not None:
            dmg[(side, slot)] = -delta * mon.max_hp
    return dmg


def choose_for_request(req: BattleRequest) -> str:
    """Legacy random agent (kept for smoke tests / hard fallback)."""
    if req.team_preview:
        slots = pick_team_preview_default(req)
        return encode_team_preview(slots, rqid=req.rqid)
    pair = pick_random_pair(req)
    return encode_choose(pair, rqid=req.rqid)


def choose_for_request_json(payload: str) -> str:
    req = BattleRequest.model_validate(json.loads(payload))
    return choose_for_request(req)


def _opp_side(our_side: str) -> str:
    return "p2" if our_side == "p1" else "p1"


def _board_key(state, opp_side: str) -> str:
    """A stable per-decision string for seeding the world sampler: opponent species
    + hp buckets + field. Same board -> same worlds (determinism)."""
    parts = []
    for slot, mon in sorted(state.side(opp_side).items()):
        parts.append(f"{slot}:{mon.species}:{int((mon.hp_fraction or 0) * 20)}")
    field = getattr(state, "field", None)
    return "|".join(parts) + "#" + str(field)


def _is_fast_board(field) -> bool:
    """True iff BOTH sides have Tailwind up (a "fast board" -- everyone acts
    sooner, so a wasted Protect turn is extra costly). Side-agnostic: reads both
    the ``p1`` and ``p2`` keys of ``field.tailwind`` directly, truthy on both."""
    tw = getattr(field, "tailwind", None) or {}
    return bool(tw.get("p1", False)) and bool(tw.get("p2", False))


def _active_pokemon(req: BattleRequest):
    return [p for p in req.side.pokemon if p.active]


def _map_target(slot_action: SlotAction, meta, our_side: str, opp_side: str, my_slot: str):
    """SlotAction target convention -> resolver (side, slot) key."""
    if meta is not None and not meta.is_damaging and not meta.hits_foe:
        return None
    if meta is not None and meta.is_spread:
        return (opp_side, "a")  # 2A models spread as one representative foe hit
    t = slot_action.target
    if t == 1:
        return (opp_side, "a")
    if t == 2:
        return (opp_side, "b")
    if t == -1:
        return (our_side, "b" if my_slot == "a" else "a")
    if t in (None, -2):
        return None
    return (opp_side, "a")


def _planned_speed_for_slot(
    *,
    active_index: int,
    actives: list,
    state: BattleState,
    our_side: str,
    speed_oracle: SpeedOracle | None,
    planned_speed_overrides_by_slot: dict[int, int] | None,
) -> int:
    """Speed to stamp on this slot's ``PlannedAction`` this turn.

    An explicit override (post-Mega ``speed_for_species`` result, keyed by
    active index) always wins -- that's how Mega evaluation contexts inject
    the projected form's speed (spec Sec.5.2: move order after Mega uses
    POST-Mega speed, not the request's pre-Mega ``stats["spe"]``). Absent an
    override, this is byte-identical to the inline logic ``_plan_my_actions``
    used before this helper existed.
    """
    overrides = planned_speed_overrides_by_slot or {}
    if active_index in overrides:
        return int(overrides[active_index])
    base_spe = (
        int(actives[active_index].stats.get("spe", 0))
        if active_index < len(actives)
        else 0
    )
    mon = state.side(our_side).get(_SLOTS[active_index])
    if speed_oracle is not None and mon is not None:
        return speed_oracle.our_speed(base_spe, mon, state.field, our_side)
    return base_spe


def _plan_my_actions(
    req: BattleRequest,
    ja: JointAction,
    *,
    state: BattleState,
    our_side: str,
    opp_side: str,
    speed_oracle: SpeedOracle | None,
    planned_speed_overrides_by_slot: dict[int, int] | None = None,
) -> list[PlannedAction]:
    actives = _active_pokemon(req)
    plans: list[PlannedAction] = []
    for i, sa in enumerate((ja.slot0, ja.slot1)):
        slot = _SLOTS[i]
        speed = _planned_speed_for_slot(
            active_index=i, actives=actives, state=state, our_side=our_side,
            speed_oracle=speed_oracle,
            planned_speed_overrides_by_slot=planned_speed_overrides_by_slot,
        )

        if sa.kind == "pass":
            plans.append(PlannedAction(our_side, slot, "pass", speed=speed, is_ours=True))
            continue
        if sa.kind == "switch":
            plans.append(
                PlannedAction(our_side, slot, "switch", speed=speed, is_ours=True)
            )
            continue

        move_name = None
        if i < len(req.active) and sa.move_index and sa.move_index - 1 < len(req.active[i].moves):
            move_name = req.active[i].moves[sa.move_index - 1].move
        meta = get_move_meta(move_name) if move_name else None
        kind = "protect" if (meta and meta.id in ("protect", "detect", "wideguard")) else "move"
        target = _map_target(sa, meta, our_side, opp_side, slot) if kind == "move" else None
        plans.append(
            PlannedAction(
                our_side, slot, kind, speed=speed, move=meta, target=target,
                is_ours=True, is_tera=sa.terastallize, is_mega=sa.mega_evolve,
            )
        )
    return plans


def _label_ja(req: BattleRequest, ja: JointAction) -> str:
    """Readable label for a JointAction (for decision diagnostics). Labels are
    diagnostic only -- structural resolution uses candidate-key-v2."""
    labels: list[str] = []
    for i, sa in enumerate((ja.slot0, ja.slot1)):
        active = req.active[i] if i < len(req.active) else None
        if sa.kind == "move" and sa.move_index and active is not None:
            moves = active.moves
            name = moves[sa.move_index - 1].move if sa.move_index - 1 < len(moves) else f"move{sa.move_index}"
            tgt = f"->{sa.target}" if sa.target else ""
            tera = " tera" if sa.terastallize else ""
            mega = " mega" if sa.mega_evolve else ""
            labels.append(f"{name}{tgt}{tera}{mega}")
        else:
            labels.append(sa.kind)
    return "(" + ", ".join(labels) + ")"


def _choose_best(
    req: BattleRequest,
    *,
    state: BattleState,
    book: SpreadBook,
    our_side: str | None = None,
    calc: CalcClient | None = None,
    oracle: DamageOracle | None = None,
    speed_oracle: SpeedOracle | None = None,
    dex: SpeciesDex | None = None,
    priors=None,
    weights: EvalWeights | None = None,
    risk_lambda: float | None = None,
    tera_margin: float = 1.0,
    rollout_horizon: int | None = None,
    report: list[str] | None = None,
    our_spreads: dict | None = None,
    opp_sets: dict | None = None,
    trace=None,
    format_config=None,
) -> tuple[JointAction, float]:
    """One-ply heuristic decision core. Returns ``(chosen_ja, best_val)``.

    Raises ``ValueError`` for team-preview requests (use the public wrapper
    ``heuristic_choose_for_request`` which handles team preview). Raises on any
    other inability so the caller's fallback chain can take over.

    ``rollout_horizon`` enables the multi-turn condition rollout (0 = off, exact
    legacy behavior; default resolves ``SHOWDOWN_ROLLOUT_HORIZON``, else 2).
    ``risk_lambda`` (NEUTRAL-mode variance penalty passed to pick_best/
    aggregate_scores) defaults to ``None``, which resolves ``SHOWDOWN_RISK_LAMBDA``
    via ``policy._risk_lambda()`` (else 0.5); pass an explicit float to override.
    Pass a ``report`` list to collect a readable decision block.
    """
    if req.team_preview:
        raise ValueError("_choose_best_ja does not handle team preview")
    if rollout_horizon is None:
        rollout_horizon = _default_rollout_horizon()
    if risk_lambda is None:
        risk_lambda = _risk_lambda()
    accuracy_mode = _accuracy_mode()
    accuracy_branch_cap = _accuracy_branch_cap()

    our_side = our_side or (req.side.id or "p1")
    opp_side = _opp_side(our_side)

    from showdown_bot.engine.calc_profile import calc_profile_from_config

    calc_profile = calc_profile_from_config(format_config)

    calc = calc or CalcClient()
    oracle = oracle or DamageOracle(calc)
    if speed_oracle is None:
        try:
            from showdown_bot.engine.calc_profile import build_speed_oracle

            speed_oracle = build_speed_oracle(calc.backend, calc_profile)
        except Exception:
            speed_oracle = None
    if dex is None:
        try:
            dex = SpeciesDex(calc.backend)
        except Exception:
            dex = None

    # Enrich our active mons' typing so the resolver can apply Grass / powder
    # immunity (e.g. our Grass-type ignoring an opponent's Rage Powder). Cached
    # per species in the dex, so this is effectively free after the first turn.
    if dex is not None:
        for slot, mon in state.side(our_side).items():
            if slot in ("a", "b") and mon is not None and not mon.types and mon.species:
                try:
                    mon.types = list(dex.types(mon.species))
                except Exception:
                    pass

    # Drop dead Fake Out / First Impression: a mon that already acted since
    # switching in can't use them (they auto-fail and waste the turn). Active
    # index 0/1 maps to our slots a/b.
    from showdown_bot.team.spreads import apply_own_team_knowledge

    apply_own_team_knowledge(state, req, our_spreads)

    side_mons = state.side(our_side)
    moved_since_switch = []
    for slot in ("a", "b"):
        m = side_mons.get(slot)
        moved_since_switch.append(bool(m is not None and getattr(m, "moved_since_switch", False)))

    # Endgame = our last mon (no bench to switch to): Protect then only defers the
    # loss, so the eval penalizes it (see score_outcome). Count non-fainted mons
    # from the authoritative request.
    our_remaining = sum(1 for p in req.side.pokemon if "fnt" not in (p.condition or ""))
    endgame = our_remaining <= 1

    # Fast board = both sides have Tailwind up (everyone acts sooner -> a wasted
    # Protect turn is extra costly). Computed once here, alongside endgame, and
    # threaded into the same evaluation calls (see evaluate.py::score_outcome).
    fast_board = _is_fast_board(state.field)

    # A/B knob for the Protect stall penalties (Fix 2). Default on.
    if weights is None:
        fast_board_protect = _fast_board_protect_weight()
        weights = EvalWeights(fast_board_protect=fast_board_protect)
        if os.environ.get("SHOWDOWN_PROTECT_PENALTY", "1") == "0":
            weights = EvalWeights(
                protect_stall=0.0, endgame_protect=0.0, partner_abandon=0.0,
                fast_board_protect=fast_board_protect,
            )

    my_actions = enumerate_my_actions(req, moved_since_switch=moved_since_switch)
    if not my_actions:
        raise ValueError("no legal joint actions")

    mode = classify_game_mode(
        state, our_side=our_side, calc=calc, book=book, calc_profile=calc_profile
    )

    plans = {
        ja: _plan_my_actions(
            req, ja, state=state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
        )
        for ja in my_actions
    }
    threatened = {
        slot
        for slot, mon in state.side(opp_side).items()
        if slot in ("a", "b") and 0.0 < mon.hp_fraction <= 0.6
    }
    world_dist = None
    if world_samples() > 1:
        opp_mons = [(to_id(mon.species), mon.species)
                    for mon in state.side(opp_side).values()]
        world_dist = build_world_dist(opp_mons, book, opp_sets or {})
    if world_dist:
        # --- K-world opponent-set sampling (2c +Sampling): only when there is actual
        # opponent-set uncertainty to sample; empty dist -> single-world = byte-identical ---
        seed = world_seed(os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "world"),
                          getattr(state, "turn", 0) or 0, _board_key(state, opp_side))
        worlds = sample_worlds(world_dist, world_samples(), seed=seed)
        shared_oracle = oracle or DamageOracle()
        world_ctx = []  # (world_weight, opp_resps_k, model_k)
        for world_sets, world_w in worlds:
            merged_sets = {**(opp_sets or {}), **world_sets}
            resps_k = predict_responses(
                state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
                dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
                opp_sets=merged_sets,
            )
            model_k = DamageModel(
                state, our_side, opp_side, book=book, oracle=shared_oracle,
                field=state.field, our_spreads=our_spreads, opp_sets=merged_sets,
                calc_profile=calc_profile,
            )
            model_k.enqueue(list(plans.values()) + [r.actions for r in resps_k])
            world_ctx.append((world_w, resps_k, model_k))
        shared_oracle.flush()
        # _maybe_tera + report/trace below reference a single opp_resps/model; bind them
        # to the most-likely world (world_ctx[0], always present). Full K-world Tera/trace
        # is a follow-up refinement (this machinery slice is off-by-default, no winrate claim).
        opp_resps = world_ctx[0][1]
        model = world_ctx[0][2]

        def score_plan(my_plan: list[PlannedAction]) -> list[float]:
            out: list[float] = []
            for _w, resps_k, model_k in world_ctx:
                targets = [r.actions for r in resps_k] if resps_k else [[]]
                for opp_actions in targets:
                    out.append(evaluate_line(
                        state, my_plan, opp_actions, model_k.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                    )[0])
            return out

        resp_weights = []
        for world_w, resps_k, _model_k in world_ctx:
            if resps_k:
                for r in resps_k:
                    resp_weights.append(world_w * (r.weight if priors is not None else 1.0))
            else:
                resp_weights.append(world_w)
        items = [(ja, score_plan(plan)) for ja, plan in plans.items()]
        best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)
    else:
        # --- single-world path (unchanged; byte-identical when world_samples()<=1) ---
        opp_resps = predict_responses(
            state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
            dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
            opp_sets=opp_sets,
        )
        resp_weights = [r.weight for r in opp_resps] if (priors is not None and opp_resps) else None

        model = DamageModel(
            state, our_side, opp_side, book=book, oracle=oracle, field=state.field,
            our_spreads=our_spreads, opp_sets=opp_sets, calc_profile=calc_profile,
        )
        groups = list(plans.values()) + [r.actions for r in opp_resps]
        model.prefetch(groups)

        def score_plan(my_plan: list[PlannedAction]) -> list[float]:
            if opp_resps:
                return [
                    evaluate_line(
                        state, my_plan, r.actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                    )[0]
                    for r in opp_resps
                ]
            return [
                evaluate_line(
                    state, my_plan, [], model.damage_fn,
                    our_side=our_side, weights=weights, field=state.field,
                    rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                    accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                )[0]
            ]

        if _search_depth() > 1 and world_samples() <= 1:
            # --- depth-2 wrap (guarded; the verbatim 1-ply branch below runs
            # unchanged whenever this condition is false -> byte-identical off) ---
            def score_plan_with_outcome(my_plan: list[PlannedAction]) -> list[tuple[float, object]]:
                targets = [r.actions for r in opp_resps] if opp_resps else [[]]
                return [
                    evaluate_line(
                        state, my_plan, opp_actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=state.field,
                        rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                    )
                    for opp_actions in targets
                ]

            full = {ja: score_plan_with_outcome(plan) for ja, plan in plans.items()}
            items = [(ja, [s for s, _o in vec]) for ja, vec in full.items()]

            # Frontier caps: N turn-1 candidates x M1 opponent-response slots.
            top_n = _search_topn()
            top_m = _search_topm()
            ranked_pos = sorted(
                range(len(items)),
                key=lambda i: aggregate_scores(
                    items[i][1], mode, risk_lambda=risk_lambda, weights=resp_weights
                ),
                reverse=True,
            )
            top_n_pos = ranked_pos[:top_n]

            n_resps = len(opp_resps) if opp_resps else 1
            if resp_weights is not None:
                top_m_idx = sorted(range(len(resp_weights)), key=lambda i: -resp_weights[i])[:top_m]
            else:
                top_m_idx = list(range(min(top_m, n_resps)))

            d2_predict_kwargs = {"dex": dex, "speed_oracle": speed_oracle}
            d2_model_kwargs = {
                "our_spreads": our_spreads,
                "opp_sets": opp_sets,
                "calc_profile": calc_profile,
            }
            # [accuracy-slice] Deliberately does NOT include accuracy_mode/accuracy_branch_cap.
            # depth2_value's turn-2 refinement (search.py) is out of scope for the accuracy slice
            # (spec Sec.12, Depth-2 Stage 3 is separate, later work) -- if SHOWDOWN_ACCURACY_MODE
            # and SHOWDOWN_SEARCH_DEPTH=2 are ever both on, the top-N/top-M candidates' scores get
            # overwritten by depth2_value with legacy always-hit values, mixing methodologies
            # inside one decision's comparison set. Not exercised by the accuracy-slice latency
            # bench (scratchpad/bench_accuracy_latency.py) or tests -- known, accepted gap until
            # Depth-2 Stage 3 threads these two kwargs through search.py.
            d2_eval_kwargs = {
                "weights": weights, "rollout_horizon": rollout_horizon,
                "endgame": endgame, "fast_board": fast_board,
            }

            for pos in top_n_pos:
                ja, scores_vec = items[pos]
                outcomes = full[ja]
                for i in top_m_idx:
                    _score1, outcome = outcomes[i]
                    applied_damage = _applied_damage_from_outcome(outcome, state)
                    v = depth2_value(
                        state, our_side=our_side, applied_damage=applied_damage, mode=mode,
                        risk_lambda=risk_lambda, top_m=2, book=book, oracle=model.oracle,
                        predict_kwargs=d2_predict_kwargs, model_kwargs=d2_model_kwargs,
                        eval_kwargs=d2_eval_kwargs,
                    )
                    scores_vec[i] = v
        else:
            items = [(ja, score_plan(plan)) for ja, plan in plans.items()]
        best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)
    if trace is not None:
        from showdown_bot.battle.policy import must_react_lambda as _mrl
        trace.aggregation_mode = mode.value if hasattr(mode, "value") else str(mode)
        trace.risk_lambda = float(risk_lambda)
        trace.must_react_lambda = float(_mrl())
    if best_ja is None:
        raise ValueError("no best action found")

    pre_tera_ja = best_ja
    best_ja = _maybe_tera(
        req, best_ja, best_val, mode, state, our_side, opp_side,
        speed_oracle, opp_resps, model, weights, risk_lambda, tera_margin, resp_weights,
        endgame=endgame, fast_board=fast_board,
        accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
        format_config=format_config,
    )

    if report is not None:
        from showdown_bot.battle.diagnostics import format_decision

        ranked = sorted(
            (
                (_label_ja(req, ja), aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights))
                for ja, scores in items
            ),
            key=lambda p: p[1],
            reverse=True,
        )
        report.append(format_decision(_label_ja(req, best_ja), ranked, getattr(mode, "name", str(mode))))

        # Metrics line: predicted incoming/outgoing for the chosen line + score gap.
        # Makes the gauntlet A/Bs interpretable beyond winrate (esp. for the bulk
        # proxy: does perceived incoming drop?). Cheap -- reuses prefetched calcs.
        chosen_plan = _plan_my_actions(
            req, best_ja, state=state, our_side=our_side, opp_side=opp_side, speed_oracle=speed_oracle
        )
        rep_resp = opp_resps[0].actions if opp_resps else []
        _, out = evaluate_line(
            state, chosen_plan, rep_resp, model.damage_fn,
            our_side=our_side, weights=weights, field=state.field, rollout_horizon=0,
            accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
        )
        incoming = sum(-d for k, d in out.hp_delta.items() if k[0] == our_side and d < 0)
        outgoing = sum(-d for k, d in out.hp_delta.items() if k[0] == opp_side and d < 0)
        gap = (ranked[0][1] - ranked[1][1]) if len(ranked) >= 2 else 0.0
        report.append(
            f"metrics mode={getattr(mode, 'name', mode)} in={incoming:.2f} out={outgoing:.2f} gap={gap:.2f}"
        )

        # "Why not max_damage" -- only when explicitly requested (it runs the
        # baseline, an extra calc). Read ~10 lost turns to see cowardice vs
        # false-threat vs worse damage line.
        if os.environ.get("SHOWDOWN_DECISION_DIFF") == "1":
            try:
                from showdown_bot.battle.baselines import max_damage_choice

                md = max_damage_choice(
                    req,
                    state=state,
                    book=book,
                    our_side=our_side,
                    format_config=format_config,
                )
                report.append(f"max_damage would: {md}")
            except Exception:  # noqa: BLE001
                pass

    if trace is not None:
        from showdown_bot.battle.candidate_identity import derive_tera_slot, joint_action_key_v2
        from showdown_bot.battle.decision_trace import (
            AccuracyEventTrace,
            AccuracyResponseDetail,
            AccuracyTieOrderTrace,
            CandidateModelFeatures,
            CandidateTrace,
            DecisionTrace as _DT,
        )
        from showdown_bot.battle.evaluate import (
            OutcomeBreakdown,
            _evaluate_line_details,
            score_outcome_with_breakdown,
        )
        from showdown_bot.engine.belief.game_mode import guaranteed_ohko, ko_threat_counts

        rep_resps = [r.actions for r in opp_resps] if opp_resps else [[]]

        def _breakdowns_for(plan):
            out = []
            acc_details = []
            for ri, ra in enumerate(rep_resps):
                d = _evaluate_line_details(
                    state, plan, ra, model.damage_fn, our_side=our_side,
                    weights=weights, field=state.field, rollout_horizon=0,
                    endgame=endgame, fast_board=fast_board,
                    accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                )
                out.append(
                    score_outcome_with_breakdown(
                        d.representative_outcome, our_side, weights, endgame=endgame, fast_board=fast_board
                    )[1]
                )
                acc_details.append(AccuracyResponseDetail(
                    accuracy_leaf_count=sum(t.accuracy_leaf_count for t in d.tie_order_details),
                    accuracy_event_count=len(d.accuracy_events),
                    accuracy_branch_cap_hits=d.fallback_leaves,
                    events_complete=(d.fallback_leaves == 0),
                    tie_orders=[
                        AccuracyTieOrderTrace(
                            t.tie_order, t.weight, t.accuracy_leaf_count,
                            t.accuracy_branch_cap_hits, t.events_complete,
                        )
                        for t in d.tie_order_details
                    ],
                    events=[
                        AccuracyEventTrace(
                            e.attacker, e.target, e.move_id, e.hit_probability,
                            response_index=ri, tie_order=e.tie_order,
                        )
                        for e in d.accuracy_events
                    ],
                ))
            return out, acc_details

        def _weighted_mean_breakdown(bds):
            ws = resp_weights or [1.0] * len(bds)
            tot = sum(ws) or 1.0
            agg = OutcomeBreakdown()
            for f in ("total_score", "predicted_outgoing_damage", "predicted_incoming_damage",
                      "my_kos", "my_faints", "protect_stall_penalty",
                      "endgame_protect_penalty", "partner_abandon_penalty",
                      "fast_board_protect_penalty"):
                setattr(agg, f, sum(getattr(b, f) * w for b, w in zip(bds, ws)) / tot)
            return agg

        # Decision-level threat counts: computed once, shared across all candidates.
        dec_threatened, dec_survives = ko_threat_counts(
            state, our_side, calc=calc, book=book, calc_profile=calc_profile
        )

        def _ko_secured_for(plan: list[PlannedAction]) -> int:
            """Distinct opponent active slots guaranteed-OHKO'd by this candidate's
            selected damaging moves (OFFENSE-vs-DEFENSE, same as game_mode)."""
            slots: set = set()
            for a in plan:
                if (
                    a.kind == "move"
                    and a.move is not None
                    and a.move.is_damaging
                    and a.is_ours
                    and a.target is not None
                ):
                    atk = state.side(a.side).get(a.slot)
                    tgt = state.side(a.target[0]).get(a.target[1])
                    if (
                        atk is not None
                        and tgt is not None
                        and not tgt.fainted
                        and guaranteed_ohko(
                            state, atk, a.move.name, tgt,
                            calc=calc, book=book, calc_profile=calc_profile,
                        )
                    ):
                        slots.add(a.target)
            return len(slots)

        scored = [
            (ja, scores, aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights))
            for ja, scores in items
        ]
        scored.sort(key=lambda t: (-t[2], _label_ja(req, t[0])))
        cands = []
        for rank, (ja, scores, agg) in enumerate(scored[:TOP_K_TRACE_CANDIDATES]):
            bds, acc_details = _breakdowns_for(plans[ja])
            cands.append(CandidateTrace(
                candidate_id=_label_ja(req, ja), joint_action=ja, rank=rank,
                aggregate_score=agg, score_vector=list(scores),
                outcome_breakdowns=bds, aggregate_breakdown=_weighted_mean_breakdown(bds),
                model_features=CandidateModelFeatures(
                    ko_secured_count=_ko_secured_for(plans[ja]),
                    ko_threatened_count=dec_threatened,
                    survives_for_sure_count=dec_survives,
                ),
                accuracy_details=acc_details,
                candidate_key=joint_action_key_v2(ja),
            ))
        trace.game_mode = getattr(mode, "name", str(mode))
        trace.chosen_candidate_key = joint_action_key_v2(pre_tera_ja)
        trace.chosen_candidate_id = _label_ja(req, best_ja)
        trace.chosen_tera_slot = derive_tera_slot(pre_tera_ja, best_ja)
        # Task 1 (I7a-B) is identity/schema-only -- no Mega candidates are
        # ranked yet, so this stays null until the Mega ranking slice (Task 2+).
        trace.chosen_mega_slot = None
        trace.opponent_responses = [r.actions for r in opp_resps]
        trace.opponent_response_weights = resp_weights or []
        trace.candidates = cands

        from showdown_bot.battle.opponent import _opponent_speed as _opp_speed
        from showdown_bot.battle.decision_trace import DecisionTempoFeatures

        _sp_actives = _active_pokemon(req)
        our_speeds = []
        for _i, _letter in enumerate(("a", "b")):
            _m = state.side(our_side).get(_letter)
            if _m is not None and not _m.fainted and speed_oracle is not None:
                _base = int(_sp_actives[_i].stats.get("spe", 0)) if _i < len(_sp_actives) else 0
                our_speeds.append(speed_oracle.our_speed(_base, _m, state.field, our_side))
        opp_speeds = []
        if speed_oracle is not None:
            for _letter in ("a", "b"):
                _m = state.side(opp_side).get(_letter)
                if _m is not None and not _m.fainted:
                    opp_speeds.append(_opp_speed(_m, state.field, opp_side, speed_oracle=speed_oracle, book=book, opp_sets=opp_sets))
        _our_fast = max(our_speeds, default=0)
        _opp_fast = max(opp_speeds, default=0)
        trace.tempo_features = DecisionTempoFeatures(
            we_outspeed_count=sum(1 for o in opp_speeds if _our_fast > o),
            they_outspeed_count=sum(1 for u in our_speeds if _opp_fast > u),
            speed_tie_count=sum(1 for u in our_speeds for o in opp_speeds if u == o),
            our_fastest_active_speed=_our_fast,
            opp_fastest_active_speed=_opp_fast,
        )

    return best_ja, best_val


def _choose_best_ja(
    req: BattleRequest,
    *,
    state: BattleState,
    book: SpreadBook,
    our_side: str | None = None,
    calc: CalcClient | None = None,
    oracle: DamageOracle | None = None,
    speed_oracle: SpeedOracle | None = None,
    dex: SpeciesDex | None = None,
    priors=None,
    weights: EvalWeights | None = None,
    risk_lambda: float | None = None,
    tera_margin: float = 1.0,
    rollout_horizon: int | None = None,
    report: list[str] | None = None,
    our_spreads: dict | None = None,
    opp_sets: dict | None = None,
    trace=None,
    format_config=None,
) -> JointAction:
    """Thin alias for ``_choose_best`` that returns only the chosen ``JointAction``.

    Kept for backwards compatibility — 1c-B equivalence tests and the public
    wrappers call this; they must continue to work unchanged.
    """
    return _choose_best(
        req,
        state=state,
        book=book,
        our_side=our_side,
        calc=calc,
        oracle=oracle,
        speed_oracle=speed_oracle,
        dex=dex,
        priors=priors,
        weights=weights,
        risk_lambda=risk_lambda,
        tera_margin=tera_margin,
        rollout_horizon=rollout_horizon,
        report=report,
        our_spreads=our_spreads,
        opp_sets=opp_sets,
        trace=trace,
        format_config=format_config,
    )[0]


def heuristic_choose_for_request(
    req: BattleRequest,
    *,
    state: BattleState,
    book: SpreadBook,
    our_side: str | None = None,
    calc: CalcClient | None = None,
    oracle: DamageOracle | None = None,
    speed_oracle: SpeedOracle | None = None,
    dex: SpeciesDex | None = None,
    priors=None,
    weights: EvalWeights | None = None,
    risk_lambda: float | None = None,
    tera_margin: float = 1.0,
    rollout_horizon: int | None = None,
    report: list[str] | None = None,
    our_spreads: dict | None = None,
    opp_sets: dict | None = None,
    trace=None,
    format_config=None,
) -> str:
    """One-ply heuristic decision. Raises on any inability so the caller's
    fallback chain can take over.

    ``rollout_horizon`` enables the multi-turn condition rollout (0 = off, exact
    legacy behavior; default resolves ``SHOWDOWN_ROLLOUT_HORIZON``, else 2).
    ``risk_lambda`` defaults to ``None``, which resolves ``SHOWDOWN_RISK_LAMBDA``
    (else 0.5) inside ``_choose_best``. Pass a ``report`` list to collect a
    readable decision block.
    """
    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)
    best_ja = _choose_best_ja(
        req,
        state=state,
        book=book,
        our_side=our_side,
        calc=calc,
        oracle=oracle,
        speed_oracle=speed_oracle,
        dex=dex,
        priors=priors,
        weights=weights,
        risk_lambda=risk_lambda,
        tera_margin=tera_margin,
        rollout_horizon=rollout_horizon,
        report=report,
        our_spreads=our_spreads,
        opp_sets=opp_sets,
        trace=trace,
        format_config=format_config,
    )
    return encode_choose(best_ja.as_pair(), rqid=req.rqid)


def _maybe_tera(
    req, best_ja, best_val, mode, state, our_side, opp_side,
    speed_oracle, opp_resps, model, weights, risk_lambda, tera_margin, resp_weights=None,
    *, endgame: bool = False, fast_board: bool = False,
    accuracy_mode: bool = False, accuracy_branch_cap: int = 4,
    format_config=None,
) -> JointAction:
    """Overlay: only spend Tera if it beats the non-Tera line by a margin."""
    from showdown_bot.battle.policy import aggregate_scores

    if format_config is not None and not format_config.tera:
        return best_ja

    best = best_ja
    best_overlay_val = best_val
    for i, sa in enumerate((best_ja.slot0, best_ja.slot1)):
        if sa.kind != "move":
            continue
        if i >= len(req.active) or not req.active[i].can_terastallize:
            continue
        tera_ja = best_ja.with_tera(i)
        plan = _plan_my_actions(
            req, tera_ja, state=state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
        )
        if opp_resps:
            scores = [
                evaluate_line(state, plan, r.actions, model.damage_fn,
                              our_side=our_side, weights=weights, field=state.field,
                              endgame=endgame, fast_board=fast_board,
                              accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap)[0]
                for r in opp_resps
            ]
        else:
            scores = [
                evaluate_line(state, plan, [], model.damage_fn,
                              our_side=our_side, weights=weights, field=state.field,
                              endgame=endgame, fast_board=fast_board,
                              accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap)[0]
            ]
        val = aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights)
        if val > best_overlay_val and tera_decision(best_val, val, margin=tera_margin):
            best = tera_ja
            best_overlay_val = val
    return best


def _mark_selection(trace, stage: str, reason: str | None = None) -> None:
    """Pure side-effect telemetry marker: records which stage produced the
    chosen ``/choose`` string (and, on a fallback, why) on the passed
    ``DecisionTrace``. No-op when ``trace`` is None -- never influences which
    branch ``choose_with_fallback`` takes or what it returns."""
    if trace is not None:
        trace.selection_stage = stage
        trace.fallback_reason = reason


def choose_with_fallback(
    req: BattleRequest,
    *,
    state: BattleState | None = None,
    book: SpreadBook | None = None,
    our_side: str | None = None,
    hard_timeout: float = 4.0,
    report: list[str] | None = None,
    trace=None,
    format_config=None,
    **deps,
) -> str:
    """Hard fallback chain: heuristic -> max_damage -> random -> first legal.

    Each layer catches exceptions/timeouts of the layer above so a turn is never
    skipped and the bot never crashes the battle loop.
    """
    if req.team_preview:
        _mark_selection(trace, "team_preview")
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)

    fallback_reason: str | None = None
    if state is not None and book is not None:
        # NOTE: a ThreadPoolExecutor context manager would block in __exit__
        # waiting for the worker, defeating the timeout. We shut it down with
        # wait=False so the fallback returns immediately. (Python threads cannot
        # be force-killed; a true time budget inside the evaluator/oracle is the
        # long-term fix -- the orphaned worker just finishes and is discarded.)
        ex = ThreadPoolExecutor(max_workers=1)
        try:
            fut = ex.submit(
                heuristic_choose_for_request,
                req, state=state, book=book, our_side=our_side, report=report, trace=trace,
                format_config=format_config, **deps,
            )
            choice = fut.result(timeout=hard_timeout)
            _mark_selection(trace, "heuristic")
            return choice
        except FutureTimeout:
            fallback_reason = "heuristic_timeout"
            logger.warning("heuristic timed out after %ss, falling back", hard_timeout)
        except Exception as exc:  # noqa: BLE001 - intentional catch-all for robustness
            fallback_reason = "heuristic_error"
            logger.warning("heuristic failed, falling back: %s", exc)
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    try:
        from showdown_bot.battle.baselines import max_damage_choice

        if state is not None and book is not None:
            choice = max_damage_choice(
                req,
                state=state,
                book=book,
                our_side=our_side,
                format_config=format_config,
                **deps,
            )
            _mark_selection(trace, "max_damage_fallback", fallback_reason)
            return choice
    except Exception as exc:  # noqa: BLE001
        fallback_reason = "max_damage_error"
        logger.warning("max_damage fallback failed: %s", exc)

    try:
        choice = encode_choose(pick_default_pair(req), rqid=req.rqid)
        _mark_selection(trace, "deterministic_default_pair", fallback_reason)
        return choice
    except Exception as exc:  # noqa: BLE001
        logger.warning("random fallback failed: %s", exc)

    _mark_selection(trace, "server_default", "default_pair_error")
    return f"/choose default|{req.rqid}"

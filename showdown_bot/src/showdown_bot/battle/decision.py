from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.battle.evaluate import DamageModel, EvalWeights, evaluate_line
from showdown_bot.battle.opponent import SpeciesDex, predict_responses
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.policy import pick_best, tera_decision
from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.belief.game_mode import classify_game_mode
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState
from showdown_bot.models.actions import SlotAction
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview

logger = logging.getLogger(__name__)

_SLOTS = ["a", "b"]


def _default_rollout_horizon() -> int:
    """Multi-turn rollout horizon, overridable via ``SHOWDOWN_ROLLOUT_HORIZON``
    (0 disables the rollout). Lets us A/B the rollout from the gauntlet."""
    try:
        return int(os.environ.get("SHOWDOWN_ROLLOUT_HORIZON", "2"))
    except ValueError:
        return 2


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


def _plan_my_actions(
    req: BattleRequest,
    ja: JointAction,
    *,
    state: BattleState,
    our_side: str,
    opp_side: str,
    speed_oracle: SpeedOracle | None,
) -> list[PlannedAction]:
    actives = _active_pokemon(req)
    plans: list[PlannedAction] = []
    for i, sa in enumerate((ja.slot0, ja.slot1)):
        slot = _SLOTS[i]
        base_spe = 0
        if i < len(actives):
            base_spe = int(actives[i].stats.get("spe", 0))
        mon = state.side(our_side).get(slot)
        if speed_oracle is not None and mon is not None:
            speed = speed_oracle.our_speed(base_spe, mon, state.field, our_side)
        else:
            speed = base_spe

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
                is_ours=True, is_tera=sa.terastallize,
            )
        )
    return plans


def _label_ja(req: BattleRequest, ja: JointAction) -> str:
    """Readable label for a JointAction (for decision diagnostics)."""
    labels: list[str] = []
    for i, sa in enumerate((ja.slot0, ja.slot1)):
        active = req.active[i] if i < len(req.active) else None
        if sa.kind == "move" and sa.move_index and active is not None:
            moves = active.moves
            name = moves[sa.move_index - 1].move if sa.move_index - 1 < len(moves) else f"move{sa.move_index}"
            tgt = f"->{sa.target}" if sa.target else ""
            tera = " tera" if sa.terastallize else ""
            labels.append(f"{name}{tgt}{tera}")
        else:
            labels.append(sa.kind)
    return "(" + ", ".join(labels) + ")"


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
    risk_lambda: float = 0.5,
    tera_margin: float = 1.0,
    rollout_horizon: int | None = None,
    report: list[str] | None = None,
) -> str:
    """One-ply heuristic decision. Raises on any inability so the caller's
    fallback chain can take over.

    ``rollout_horizon`` enables the multi-turn condition rollout (0 = off, exact
    legacy behavior; default resolves ``SHOWDOWN_ROLLOUT_HORIZON``, else 2). Pass
    a ``report`` list to collect a readable decision block.
    """
    if rollout_horizon is None:
        rollout_horizon = _default_rollout_horizon()
    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)

    our_side = our_side or (req.side.id or "p1")
    opp_side = _opp_side(our_side)

    calc = calc or CalcClient()
    oracle = oracle or DamageOracle(calc)
    if speed_oracle is None:
        try:
            speed_oracle = SpeedOracle(stats_backend=calc.backend)
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

    my_actions = enumerate_my_actions(req)
    if not my_actions:
        raise ValueError("no legal joint actions")

    mode = classify_game_mode(state, our_side=our_side, calc=calc, book=book)

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
    opp_resps = predict_responses(
        state, our_side, opp_side, speed_oracle=speed_oracle, book=book,
        dex=dex, field=state.field, priors=priors, threatened_slots=threatened,
    )
    resp_weights = [r.weight for r in opp_resps] if (priors is not None and opp_resps) else None

    model = DamageModel(state, our_side, opp_side, book=book, oracle=oracle, field=state.field)
    groups = list(plans.values()) + [r.actions for r in opp_resps]
    model.prefetch(groups)

    def score_plan(my_plan: list[PlannedAction]) -> list[float]:
        if opp_resps:
            return [
                evaluate_line(
                    state, my_plan, r.actions, model.damage_fn,
                    our_side=our_side, weights=weights, field=state.field,
                    rollout_horizon=rollout_horizon,
                )[0]
                for r in opp_resps
            ]
        return [
            evaluate_line(
                state, my_plan, [], model.damage_fn,
                our_side=our_side, weights=weights, field=state.field,
                rollout_horizon=rollout_horizon,
            )[0]
        ]

    items = [(ja, score_plan(plan)) for ja, plan in plans.items()]
    best_ja, best_val = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)
    if best_ja is None:
        raise ValueError("no best action found")

    best_ja = _maybe_tera(
        req, best_ja, best_val, mode, state, our_side, opp_side,
        speed_oracle, opp_resps, model, weights, risk_lambda, tera_margin, resp_weights,
    )

    if report is not None:
        from showdown_bot.battle.diagnostics import format_decision
        from showdown_bot.battle.policy import aggregate_scores

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

                md = max_damage_choice(req, state=state, book=book, our_side=our_side)
                report.append(f"max_damage would: {md}")
            except Exception:  # noqa: BLE001
                pass

    return encode_choose(best_ja.as_pair(), rqid=req.rqid)


def _maybe_tera(
    req, best_ja, best_val, mode, state, our_side, opp_side,
    speed_oracle, opp_resps, model, weights, risk_lambda, tera_margin, resp_weights=None,
) -> JointAction:
    """Overlay: only spend Tera if it beats the non-Tera line by a margin."""
    from showdown_bot.battle.policy import aggregate_scores

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
                              our_side=our_side, weights=weights, field=state.field)[0]
                for r in opp_resps
            ]
        else:
            scores = [
                evaluate_line(state, plan, [], model.damage_fn,
                              our_side=our_side, weights=weights, field=state.field)[0]
            ]
        val = aggregate_scores(scores, mode, risk_lambda=risk_lambda, weights=resp_weights)
        if val > best_overlay_val and tera_decision(best_val, val, margin=tera_margin):
            best = tera_ja
            best_overlay_val = val
    return best


def choose_with_fallback(
    req: BattleRequest,
    *,
    state: BattleState | None = None,
    book: SpreadBook | None = None,
    our_side: str | None = None,
    hard_timeout: float = 4.0,
    report: list[str] | None = None,
    **deps,
) -> str:
    """Hard fallback chain: heuristic -> max_damage -> random -> first legal.

    Each layer catches exceptions/timeouts of the layer above so a turn is never
    skipped and the bot never crashes the battle loop.
    """
    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)

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
                req, state=state, book=book, our_side=our_side, report=report, **deps,
            )
            return fut.result(timeout=hard_timeout)
        except FutureTimeout:
            logger.warning("heuristic timed out after %ss, falling back", hard_timeout)
        except Exception as exc:  # noqa: BLE001 - intentional catch-all for robustness
            logger.warning("heuristic failed, falling back: %s", exc)
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    try:
        from showdown_bot.battle.baselines import max_damage_choice

        if state is not None and book is not None:
            return max_damage_choice(req, state=state, book=book, our_side=our_side, **deps)
    except Exception as exc:  # noqa: BLE001
        logger.warning("max_damage fallback failed: %s", exc)

    try:
        return encode_choose(pick_random_pair(req), rqid=req.rqid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("random fallback failed: %s", exc)

    return f"/choose default|{req.rqid}"

from __future__ import annotations

import copy
from dataclasses import replace

from showdown_bot.battle.evaluate import DamageModel, evaluate_line
from showdown_bot.battle.opponent import OppResponse, predict_responses
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.policy import aggregate_scores, pick_best
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.state import BattleState


def approx_turn2_state(state: BattleState, *, our_side: str,
                       applied_damage: dict[tuple[str, str], float]) -> BattleState:
    """Coarse turn-2 successor: deep-copy `state`, subtract `applied_damage`
    (expected HP by (side, slot)) clamped >=0, mark 0-HP mons fainted, advance the
    turn. The FieldState (weather/trick_room/tailwind) has no turn counters, so it
    PERSISTS (a documented approximation). Does NOT model move secondary effects,
    switches beyond the applied damage, or item/ability triggers -- that is the
    'coarse' in coarse-depth-2 (see the design spec)."""
    nxt = copy.deepcopy(state)
    for (side, slot), dmg in applied_damage.items():
        mon = nxt.sides.get(side, {}).get(slot)
        if mon is None:
            continue
        mon.hp = max(0, int(mon.hp - dmg))
        if mon.hp == 0:
            mon.fainted = True
    nxt.turn = (nxt.turn or 0) + 1
    return nxt


def _opp_side(our_side: str) -> str:
    return "p2" if our_side == "p1" else "p1"


def _score_turn2_plans(
    state: BattleState,
    *,
    our_side: str,
    opp_side: str,
    opp_resps: list[OppResponse],
    book: SpreadBook | None,
    oracle: DamageOracle | None,
    predict_kwargs: dict,
    model_kwargs: dict,
    eval_kwargs: dict,
) -> list[tuple[str, list[float]]]:
    """Turn-2 analogue of ``_choose_best``'s single-world ``score_plan`` seam
    (decision.py ~360-390): for every plausible turn-2 action of ours, score it
    against every (already top-M-capped) opponent turn-2 response via a turn-2
    ``DamageModel``/``evaluate_line``, returning ``[(label, [score_per_opp_resp,
    ...]), ...]`` -- the same shape ``_choose_best`` feeds into ``pick_best``.

    Adaptation from the plan (no live ``BattleRequest`` exists for the
    hypothetical approximated turn-2 state, so ``enumerate_my_actions`` /
    ``_plan_my_actions`` -- which need one, for revealed movesets/PP/trapped/
    force-switch data -- cannot be reused verbatim): the state-only stand-in is
    ``predict_responses`` itself, called with ``our_side``/``opp_side``
    reversed. It is already a "plausible candidate joint-actions for a side,
    from ``BattleState`` alone" oracle (aggressive focus-fire, a Protect read,
    revealed support, a pivot) that today is only ever called for the
    opponent; reversed, it produces the same shape of candidates for OUR side,
    including its existing alive-slot filtering (so a fainted mon of ours
    correctly gets no turn-2 action). Its output defaults every
    ``PlannedAction.is_ours`` to ``False`` (it assumes it is always predicting
    the opponent), so those are corrected to ``True`` here -- otherwise
    ``DamageModel.damage_fn`` would score our own turn-2 attacks with the
    opponent's optimistic max-roll instead of our own worst-case-for-us roll
    convention (``_our_roll``).
    """
    my_resps = predict_responses(
        state, opp_side, our_side, book=book, field=state.field, **predict_kwargs
    )
    my_plans: list[tuple[str, list[PlannedAction]]] = [
        (r.label, [replace(a, is_ours=True) for a in r.actions]) for r in my_resps
    ]

    model = DamageModel(
        state, our_side, opp_side, book=book, oracle=oracle, field=state.field,
        **model_kwargs,
    )
    groups = [plan for _label, plan in my_plans] + [r.actions for r in opp_resps]
    # Enqueue only -- the shared oracle is flushed once across the whole depth-2
    # frontier by the caller (Task 4), not per turn-2 leaf.
    model.enqueue(groups)

    def score_plan(my_plan: list[PlannedAction]) -> list[float]:
        targets = [r.actions for r in opp_resps] if opp_resps else [[]]
        return [
            evaluate_line(
                state, my_plan, opp_actions, model.damage_fn,
                our_side=our_side, field=state.field, **eval_kwargs,
            )[0]
            for opp_actions in targets
        ]

    return [(label, score_plan(plan)) for label, plan in my_plans]


def depth2_value(
    state: BattleState,
    *,
    our_side: str,
    applied_damage: dict[tuple[str, str], float],
    mode: GameMode,
    risk_lambda: float,
    top_m: int,
    book: SpreadBook | None,
    oracle: DamageOracle | None,
    predict_kwargs: dict | None = None,
    model_kwargs: dict | None = None,
    eval_kwargs: dict | None = None,
) -> float:
    """The depth-2 leaf value for one turn-1 (my_plan, opp_response) line.

    Builds the coarse approximate turn-2 state from ``applied_damage`` (see
    ``approx_turn2_state``), then runs a fresh 1-ply decision on it: my best
    turn-2 action's response-weighted aggregate over the opponent's top-``m``
    turn-2 responses -- reusing the exact same ``predict_responses`` /
    ``DamageModel`` / ``evaluate_line`` / ``aggregate_scores`` / ``pick_best``
    machinery ``_choose_best``'s single-world path uses today (see
    ``_score_turn2_plans``).

    Dependency-injected on purpose: ``predict_responses``, ``_score_turn2_plans``,
    ``aggregate_scores`` and ``pick_best`` are called as bare module-level names
    (imported at module scope) so a caller/test can
    ``monkeypatch.setattr(search, "<name>", ...)`` to isolate this function's own
    orchestration from its collaborators.

    Does NOT flush ``oracle`` -- turn-2 calc requests are only enqueued into the
    passed-in shared ``DamageOracle``; Task 4's frontier wrapper flushes it once
    across the whole depth-2 frontier (one batched Node round trip).
    """
    predict_kwargs = predict_kwargs or {}
    model_kwargs = model_kwargs or {}
    eval_kwargs = eval_kwargs or {}
    opp_side = _opp_side(our_side)

    nxt = approx_turn2_state(state, our_side=our_side, applied_damage=applied_damage)

    opp_resps = predict_responses(
        nxt, our_side, opp_side, book=book, field=nxt.field, **predict_kwargs
    )
    opp_resps = sorted(opp_resps, key=lambda r: -r.weight)[:top_m]

    items = _score_turn2_plans(
        nxt, our_side=our_side, opp_side=opp_side, opp_resps=opp_resps,
        book=book, oracle=oracle, predict_kwargs=predict_kwargs,
        model_kwargs=model_kwargs, eval_kwargs=eval_kwargs,
    )

    resp_weights = [r.weight for r in opp_resps] if opp_resps else None
    best_ja, _ = pick_best(items, mode, risk_lambda=risk_lambda, weights=resp_weights)
    # Re-aggregate the winning candidate's own score vector explicitly (rather
    # than trust pick_best's second return) -- see Task 3 self-review: sound
    # either way (aggregate_scores is pure/deterministic, so this reproduces
    # exactly what pick_best already computed internally for that candidate),
    # and it is what makes this composable with a DI test that stubs pick_best
    # to only prove out the argmax-by-key half of its contract.
    best_scores = next((scores for key, scores in items if key == best_ja), [])
    return aggregate_scores(best_scores, mode, risk_lambda=risk_lambda, weights=resp_weights)

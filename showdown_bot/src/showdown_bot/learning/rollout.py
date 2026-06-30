"""H-loop teacher adapters (Phase 3 slice 1c-C).

Public API for this task (C1):
  make_resolve  — factory returning resolve(state, our_action, opp_action) -> (next_state, reward)

C2 (make_decide / make_leaf) and C3 (rollout_labels) are added in subsequent tasks.

Signature ground truth (all verified against source):
  DamageModel(state, our_side, opp_side, *, book, oracle, field, our_spreads, opp_sets)
    — positional: state / our_side / opp_side; keyword: book/oracle/field/our_spreads/opp_sets
    — NO 'calc' kwarg (oracle is the DamageOracle, already wraps calc internally)
  resolve_turn(state, actions, damage_fn, *, our_side, field, tie_break="ours_last")
  score_outcome(outcome, our_side, weights, *, endgame=False)
    — weights is 3rd positional arg
  apply_outcome_to_state(state, outcome, actions_by_side, *, roster_by_side)
    — actions_by_side: dict[str, JointAction] (only JointAction-shaped entries)
  _plan_my_actions(req, ja, *, state, our_side, opp_side, speed_oracle)
  synthesize_request(state, side, *, roster, movesets, stats, move_meta)
"""
from __future__ import annotations


def make_resolve(
    *,
    root_our_side: str,
    roster_by_side: dict,
    movesets_by_side: dict,
    stats_by_side: dict,
    move_meta: dict,
    deps: dict,
    weights=None,
):
    """Return a ``resolve(state, our_action, opp_action) -> (next_state, reward)``
    adapter for the 1a rollout teacher.

    Args:
        root_our_side:    The decision side whose perspective reward is scored from.
                          Fixed at factory time — ALWAYS used for score_outcome,
                          regardless of which side made the current sub-call.
        roster_by_side:   dict[side -> dict[ident -> PokemonState]] for both sides.
        movesets_by_side: dict[side -> dict[ident|species -> list[str]]].
        stats_by_side:    dict[side -> dict[ident|species -> dict[str, int]]].
        move_meta:        dict[move_id -> MoveMeta] from engine/moves._move_table().
        deps:             Decision deps dict carrying book, oracle, speed_oracle, etc.
        weights:          EvalWeights | None — passed to score_outcome.

    Returns:
        A callable ``resolve(state, our_action, opp_action) -> (next_state, float)``.
        The input ``state`` is NEVER mutated (clone-first semantics).
    """
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.battle.decision import _plan_my_actions, _opp_side
    from showdown_bot.battle.evaluate import DamageModel, score_outcome
    from showdown_bot.battle.resolve import resolve_turn
    from showdown_bot.learning.simulator import apply_outcome_to_state, clone_state
    from showdown_bot.learning.decide_adapter import synthesize_request

    opp = _opp_side(root_our_side)
    speed_oracle = deps.get("speed_oracle")

    def _to_plan(action, side, c):
        """Convert an action to a list[PlannedAction] on clone ``c``.

        JointAction (from decide / enumerate) -> synthesize a request then plan it.
        Anything else (already-PlannedActions, e.g. trace.opponent_responses) ->
        passthrough as list.
        """
        if isinstance(action, JointAction):
            req = synthesize_request(
                c, side,
                roster=roster_by_side,
                movesets=movesets_by_side,
                stats=stats_by_side,
                move_meta=move_meta,
            )
            opp_side_for_plan = opp if side == root_our_side else root_our_side
            return _plan_my_actions(
                req, action,
                state=c,
                our_side=side,
                opp_side=opp_side_for_plan,
                speed_oracle=speed_oracle,
            )
        return list(action)

    def resolve(state, our_action, opp_action):
        """Resolve one turn and return ``(next_state, reward)``.

        Clones ``state`` immediately — the input is never mutated.
        """
        c = clone_state(state)  # no mutation of the caller's state

        plan_us = _to_plan(our_action, root_our_side, c)
        plan_them = _to_plan(opp_action, opp, c)

        # Build a fresh DamageModel for this cloned state.
        # Real kwargs from battle/decision.py line 256-259:
        #   DamageModel(state, our_side, opp_side, book=book, oracle=oracle,
        #               field=state.field, our_spreads=our_spreads, opp_sets=opp_sets)
        # NOTE: no 'calc' kwarg — oracle already wraps calc.
        model = DamageModel(
            c,
            root_our_side,
            opp,
            book=deps["book"],
            oracle=deps.get("oracle"),
            field=c.field,
            our_spreads=deps.get("our_spreads"),
            opp_sets=deps.get("opp_sets"),
        )
        model.prefetch([plan_us, plan_them])

        outcome = resolve_turn(
            c,
            plan_us + plan_them,
            model.damage_fn,
            our_side=root_our_side,
            field=c.field,
        )

        # apply switches ONLY for JointAction-shaped actions.
        # PlannedActions passthrough (e.g. trace.opponent_responses) have no
        # switch-target info, so they are excluded here; their HP/field changes
        # still flow through the outcome.
        acts = {
            s: a
            for s, a in ((root_our_side, our_action), (opp, opp_action))
            if isinstance(a, JointAction)
        }
        nxt = apply_outcome_to_state(c, outcome, acts, roster_by_side=roster_by_side)

        # ALWAYS score from root_our_side perspective, never from the deciding side.
        # score_outcome(outcome, our_side, weights, *, endgame=False)
        reward = score_outcome(outcome, root_our_side, weights)

        return nxt, reward

    return resolve

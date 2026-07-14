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


class RolloutLabelError(Exception):
    """Raised when rollout_labels cannot produce labels for a decision due to a
    recoverable data issue (e.g. no opponent responses, all-switch responses,
    chosen candidate not among the rolled-out candidates).

    The runtime catches this and skips the decision (incrementing a skip counter)
    rather than hard-failing the export pipeline.  Integrity bugs in weights
    (length mismatch, sum <= 0) raise plain ValueError instead — those are
    programming errors that must hard-fail.
    """


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
        from showdown_bot.engine.calc_profile import calc_profile_from_config

        calc_profile = deps.get("calc_profile") or calc_profile_from_config(
            deps.get("format_config")
        )
        model = DamageModel(
            c,
            root_our_side,
            opp,
            book=deps["book"],
            oracle=deps.get("oracle"),
            field=c.field,
            our_spreads=deps.get("our_spreads"),
            opp_sets=deps.get("opp_sets"),
            calc_profile=calc_profile,
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


def make_decide(
    *,
    root_our_side: str,
    roster_by_side: dict,
    movesets_by_side: dict,
    stats_by_side: dict,
    move_meta: dict,
    deps: dict,
):
    """Return a ``decide(state, token) -> JointAction`` adapter for the 1a rollout teacher.

    ``token`` must be one of the ``US`` / ``THEM`` constants from ``learning.teacher``.
    The mapping from token to side is STATIC (built at factory time from ``root_our_side``),
    never derived from the state at call time.

    Raises:
        ValueError: if ``token`` is not US or THEM.
    """
    from showdown_bot.learning.teacher import US, THEM
    from showdown_bot.battle.decision import _opp_side
    from showdown_bot.learning.decide_adapter import decide as _decide

    side_for = {US: root_our_side, THEM: _opp_side(root_our_side)}

    def decide(state, token):
        if token not in side_for:
            raise ValueError(
                f"unknown rollout token {token!r} (expected US={US!r} or THEM={THEM!r})"
            )
        side = side_for[token]
        return _decide(
            state, side,
            roster=roster_by_side,
            movesets=movesets_by_side,
            stats=stats_by_side,
            move_meta=move_meta,
            deps=deps,
        )

    return decide


def make_leaf(
    *,
    root_our_side: str,
    roster_by_side: dict,
    movesets_by_side: dict,
    stats_by_side: dict,
    move_meta: dict,
    deps: dict,
):
    """Return a ``leaf(state) -> float`` adapter for the 1a rollout teacher.

    The leaf is ALWAYS evaluated from ``root_our_side``'s perspective — never
    from the side-to-move.  This is the root-perspective bootstrap value used
    at the end of the H-step rollout.
    """
    from showdown_bot.learning.decide_adapter import leaf_value as _leaf_value

    def leaf(state):
        return _leaf_value(
            state, root_our_side,
            roster=roster_by_side,
            movesets=movesets_by_side,
            stats=stats_by_side,
            move_meta=move_meta,
            deps=deps,
        )

    return leaf


# ---------------------------------------------------------------------------
# C3: driver — (trace, state) → counterfactual_value → label_decision
# ---------------------------------------------------------------------------

def _drop_switch_responses(responses, weights):
    """Filter out opponent responses that contain a bare switch PlannedAction.

    v1 (B-fallback): predict_responses' pivot/switch emits a bare
    PlannedAction(kind="switch") with NO switch-in target, so the next active
    mon cannot be reconstructed.  Rather than apply an inconsistent state
    (which poisons labels), we DROP switch responses from R and renormalize
    the remaining (move) responses.

    Documented v1 limitation: the opponent pivot line is not rolled out.

    Raises ValueError if all responses are switches (nothing left to roll out).
    """
    weights = weights or [1.0] * len(responses)
    kept = [
        (r, w)
        for r, w in zip(responses, weights)
        if not any(getattr(a, "kind", None) == "switch" for a in r)
    ]
    if not kept:
        raise RolloutLabelError(
            "all opponent responses are switches; cannot build a v1 rollout R"
        )
    return [r for r, _ in kept], [w for _, w in kept]


def _normalize_responses(responses, weights):
    """Normalize (response, weight) pairs so weights sum to 1.

    Raises ValueError on: empty responses, length mismatch, sum <= 0.
    Missing/empty weights -> uniform (1.0 each).
    """
    if not responses:
        raise RolloutLabelError("rollout_labels requires at least one opponent response")
    if not weights:
        weights = [1.0] * len(responses)
    if len(weights) != len(responses):
        raise ValueError(
            f"response weights length mismatch: {len(weights)} weights for "
            f"{len(responses)} responses"
        )
    total = sum(weights)
    if total <= 0:
        raise ValueError("response weights must sum > 0")
    return [(resp, w / total) for resp, w in zip(responses, weights)]


def rollout_labels(
    trace,
    state,
    *,
    root_our_side: str,
    roster_by_side: dict,
    movesets_by_side: dict,
    stats_by_side: dict,
    move_meta: dict,
    deps: dict,
    cfg,
) -> dict:
    """Consume a captured DecisionTrace + raw BattleState, run counterfactual_value
    per top-K candidate using the three adapters, and return real ``label_decision``
    labels — replacing the ``stub-h0`` placeholder.

    Args:
        trace:          A populated ``DecisionTrace`` from the 1b capture pipeline.
        state:          The ``BattleState`` at the time of the decision (NOT mutated).
        root_our_side:  EXPLICIT — which side is "us".  Never derived from the trace.
        roster_by_side: dict[side -> dict[ident -> PokemonState]] for both sides.
        movesets_by_side: dict[side -> dict[ident|species -> list[str]]].
        stats_by_side:  dict[side -> dict[ident|species -> dict[str, int]]].
        move_meta:      dict[move_id -> MoveMeta].
        deps:           Decision deps dict (book, oracle, etc.).
        cfg:            ``RolloutConfig`` (H, gamma, top_k, use_leaf).

    Returns:
        dict[candidate_id -> per-candidate label dict] as returned by
        ``label_decision`` from ``learning.teacher``.

    Raises:
        ValueError: if all opponent responses are switches, if chosen_candidate_id
                    is not among the rollout candidates, or on malformed weights.
    """
    from showdown_bot.battle.candidate_identity import (
        assert_unique_candidate_identities,
        candidate_identity,
        resolve_chosen_candidate,
    )
    from showdown_bot.learning.teacher import counterfactual_value, label_decision

    common = dict(
        root_our_side=root_our_side,
        roster_by_side=roster_by_side,
        movesets_by_side=movesets_by_side,
        stats_by_side=stats_by_side,
        move_meta=move_meta,
        deps=deps,
    )
    resolve = make_resolve(weights=deps.get("weights"), **common)
    decide = make_decide(**common)
    leaf = make_leaf(**common)

    # Filter switch responses (v1 B-fallback) and normalize to sum-1 weights.
    resps, weights = _drop_switch_responses(
        trace.opponent_responses,
        list(trace.opponent_response_weights) if trace.opponent_response_weights else [],
    )
    R = _normalize_responses(resps, weights)

    prefix = trace.candidates[: cfg.top_k]
    assert_unique_candidate_identities(prefix)
    chosen = resolve_chosen_candidate(trace)
    chosen_ident = candidate_identity(chosen)

    teacher_values: dict = {}
    heuristic_values: dict = {}
    for c in prefix:
        ident = candidate_identity(c)
        teacher_values[ident] = counterfactual_value(
            state,
            c.joint_action,
            R,
            decide=decide,
            resolve=resolve,
            leaf=leaf,
            cfg=cfg,
        )
        heuristic_values[ident] = c.aggregate_score

    if chosen_ident not in teacher_values:
        raise RolloutLabelError(
            f"chosen candidate identity {chosen_ident!r} is not among the "
            f"rollout candidates ({list(teacher_values)!r})"
        )

    return label_decision(teacher_values, heuristic_values, chosen_ident)

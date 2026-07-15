from __future__ import annotations

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.battle.decision import _opp_side, _plan_my_actions
from showdown_bot.battle.evaluate import DamageModel
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.random_agent import pick_default_pair
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview

# A guaranteed KO is worth more than any amount of chip; weight it above the
# maximum possible summed damage fraction (<= ~4.0 across both slots).
_KO_BONUS = 100.0


def max_damage_choice(
    req: BattleRequest,
    *,
    state: BattleState,
    book: SpreadBook,
    our_side: str | None = None,
    calc: CalcClient | None = None,
    oracle: DamageOracle | None = None,
    speed_oracle: SpeedOracle | None = None,
    format_config=None,
    fallback=None,
    our_spreads: dict | None = None,
    **_ignored,
) -> str:
    """max_damage baseline: pick the legal joint action with the most immediate
    damage, preferring guaranteed KOs, IGNORING incoming damage, NEVER Tera.

    Defender uses the standard (defense) preset -- a fair, fixed bulk assumption.

    ``fallback`` (T3c): a callable ``req -> choice_str`` used only on the no-legal-action
    paths. Default ``None`` (T4b) uses ``pick_default_pair`` -- the default fallback is
    deterministic since T4b; the eval dispatch may still pass its own.
    (The main equal-damage tie-break is already deterministic — enumeration order.)
    """
    def _default_fallback(r):
        return encode_choose(pick_default_pair(r), rqid=r.rqid)

    _fb = fallback if fallback is not None else _default_fallback

    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)

    our_side = our_side or (req.side.id or "p1")
    opp_side = _opp_side(our_side)
    calc = calc or CalcClient()
    oracle = oracle or DamageOracle(calc)
    from showdown_bot.engine.calc_profile import calc_profile_from_config

    calc_profile = calc_profile_from_config(format_config)
    if speed_oracle is None:
        try:
            from showdown_bot.engine.calc_profile import build_speed_oracle

            speed_oracle = build_speed_oracle(calc.backend, calc_profile)
        except Exception:
            speed_oracle = None

    my_actions = enumerate_my_actions(req)
    if not my_actions:
        return _fb(req)

    if format_config is not None and format_config.mega:
        # Mega-enabled branch (I7a-B Task 5): mirrors decision.py's
        # _choose_best_mega dispatch -- own-Mega variants are scored as
        # first-class candidates via the SAME shared expand/filter/context
        # path (mega_scoring.build_own_mega_contexts), never a second
        # expansion. This early return leaves everything below UNTOUCHED for
        # format_config.mega False/None -- the legacy body stays byte-for-
        # byte identical to before this task.
        return _max_damage_choice_mega(
            req, state=state, book=book, our_side=our_side, opp_side=opp_side,
            oracle=oracle, speed_oracle=speed_oracle, calc_profile=calc_profile,
            my_actions=my_actions, fallback=_fb, our_spreads=our_spreads,
        )

    plans = {
        ja: _plan_my_actions(
            req, ja, state=state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
        )
        for ja in my_actions
    }
    model = DamageModel(
        state, our_side, opp_side, book=book, oracle=oracle, field=state.field,
        calc_profile=calc_profile,
    )
    model.prefetch(list(plans.values()))

    best_ja = None
    best_score = float("-inf")
    for ja, plan in plans.items():
        score = 0.0
        for action in plan:
            if action.kind != "move" or action.move is None or not action.move.is_damaging:
                continue
            if action.target is None:
                continue
            frac = model.damage_fn(action, None)
            score += frac
            target_mon = state.sides.get(action.target[0], {}).get(action.target[1])
            if target_mon is not None and frac >= target_mon.hp_fraction > 0:
                score += _KO_BONUS
        if score > best_score:
            best_score = score
            best_ja = ja

    if best_ja is None:
        return _fb(req)
    return encode_choose(best_ja.as_pair(), rqid=req.rqid)


def _max_damage_choice_mega(
    req: BattleRequest,
    *,
    state: BattleState,
    book: SpreadBook,
    our_side: str,
    opp_side: str,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle | None,
    calc_profile,
    my_actions,
    fallback,
    our_spreads: dict | None = None,
) -> str:
    """Mega-aware max_damage (I7a-B Task 5): own-Mega variants are scored as
    first-class candidates in the SAME grid as base (non-Mega) actions, via
    the single shared expand+filter+context pass already built and locked by
    Task 2-4 (``mega_scoring.build_own_mega_contexts`` -- never a second
    ``expand_mega_variants``/``filter_projectable_variants`` call here).

    Scoring is IDENTICAL in spirit to the non-Mega loop above (summed outgoing
    damage fractions + ``_KO_BONUS`` for guaranteed KOs), just applied per
    context (``context.projected_state``/``context.damage_model`` instead of
    the single live ``state``/model) so a Mega'd mon's own post-Mega bulk and
    species are reflected. Still NEVER evaluates incoming damage, NEVER calls
    ``evaluate.evaluate_line`` or any opponent-response modeling, and NEVER
    applies Tera -- max_damage stays a pure outgoing-damage baseline.

    Iterates the ``evaluated_variants`` list ``build_own_mega_contexts``
    returns (the true ``expand_mega_variants``/``filter_projectable_variants``
    order, interleaved per base joint, NOT grouped by ``own_mega_slot``) --
    never a double loop over ``contexts``/``ctx.plans.items()`` (that order
    groups every non-Mega variant ahead of every Mega variant and breaks the
    strict first-wins ``score > best_score`` tie-break; Codex I7a-B
    merge-blocker).

    ``our_spreads`` is threaded straight through to ``build_own_mega_contexts``
    (never hardcoded to ``None``) -- without a real spread lookup,
    ``project_mega`` always raises ``MissingMegaSpreadError`` for every real
    species and ``filter_projectable_variants`` fail-closes every own-Mega
    variant before scoring ever happens, so a Mega candidate could never even
    exist in the evaluated set regardless of how much more damage it would
    deal (Codex I7a-B merge-blocker #2).
    """
    from showdown_bot.battle.mega_scoring import build_own_mega_contexts
    from showdown_bot.engine.species_meta import species_meta_table

    if speed_oracle is None:
        raise ValueError("Mega-enabled max_damage requires a speed_oracle")

    contexts, evaluated_variants = build_own_mega_contexts(
        req, state, our_side=our_side, opp_side=opp_side, book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=our_spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    # build_own_mega_contexts already enqueued every context's plans into the
    # shared oracle WITHOUT flushing (its own contract) -- one flush here
    # batches every context's calc requests into a single Node round trip,
    # matching the non-Mega loop's model.prefetch() (enqueue + one flush).
    oracle.flush()

    ctx_by_slot = {c.own_mega_slot: c for c in contexts}

    best_ja = None
    best_score = float("-inf")
    # Deterministic order: evaluated_variants' own expand order (interleaved
    # per base joint -- base, then its own Mega variants) -- so ties keep the
    # same strict first-wins semantics as the non-Mega loop.
    for variant in evaluated_variants:
        ctx = ctx_by_slot[variant.own_mega_slot]
        ja = variant.joint
        plan = ctx.plans[ja]
        score = 0.0
        for action in plan:
            if action.kind != "move" or action.move is None or not action.move.is_damaging:
                continue
            if action.target is None:
                continue
            frac = ctx.damage_model.damage_fn(action, None)
            score += frac
            target_mon = ctx.projected_state.sides.get(action.target[0], {}).get(action.target[1])
            if target_mon is not None and frac >= target_mon.hp_fraction > 0:
                score += _KO_BONUS
        if score > best_score:
            best_score = score
            best_ja = ja

    if best_ja is None:
        return fallback(req)
    return encode_choose(best_ja.as_pair(), rqid=req.rqid)

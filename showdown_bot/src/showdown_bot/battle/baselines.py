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
    fallback=None,
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
    if speed_oracle is None:
        try:
            speed_oracle = SpeedOracle(stats_backend=calc.backend)
        except Exception:
            speed_oracle = None

    my_actions = enumerate_my_actions(req)
    if not my_actions:
        return _fb(req)

    plans = {
        ja: _plan_my_actions(
            req, ja, state=state, our_side=our_side, opp_side=opp_side,
            speed_oracle=speed_oracle,
        )
        for ja in my_actions
    }
    model = DamageModel(state, our_side, opp_side, book=book, oracle=oracle, field=state.field)
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

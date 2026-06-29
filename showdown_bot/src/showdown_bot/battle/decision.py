from __future__ import annotations

import json

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview


def choose_for_request(req: BattleRequest) -> str:
    if req.team_preview:
        slots = pick_team_preview_default(req)
        return encode_team_preview(slots, rqid=req.rqid)
    pair = pick_random_pair(req)
    return encode_choose(pair, rqid=req.rqid)


def choose_for_request_json(payload: str) -> str:
    req = BattleRequest.model_validate(json.loads(payload))
    return choose_for_request(req)

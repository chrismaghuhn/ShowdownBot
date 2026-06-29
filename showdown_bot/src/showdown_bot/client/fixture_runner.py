from __future__ import annotations

import json
import random
from pathlib import Path

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose


def replay_request_fixture(path: str | Path, seed: int = 0) -> str:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    req = BattleRequest.model_validate(data)
    pair = pick_random_pair(req, rng=random.Random(seed))
    return encode_choose(pair, rqid=req.rqid)

from __future__ import annotations

import random

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.actions import SlotPair
from showdown_bot.models.request import BattleRequest


def pick_random_pair(req: BattleRequest, rng: random.Random | None = None) -> SlotPair:
    rng = rng or random.Random()
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        raise ValueError("No legal actions for request")
    return rng.choice(pairs)

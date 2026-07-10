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


def pick_default_pair(req: BattleRequest) -> SlotPair:
    """Deterministic last-resort: the FIRST legal pair (enumeration order). Used by the
    fallback chain (T4b) so an enumeration hole can never reintroduce nondeterminism;
    the `random` policy keeps using pick_random_pair."""
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        raise ValueError("No legal actions for request")
    return pairs[0]

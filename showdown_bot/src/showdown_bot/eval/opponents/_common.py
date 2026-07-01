"""Shared, deterministic slot-pair scoring for the eval-only opponent policies (T3c).

Reads only the request (legal actions + move metadata); no calc, no rollout. A policy is
a per-slot score function; ``pick_best_pair`` picks the highest-scoring legal joint action
(first on tie, by enumeration order — so it is deterministic).
"""
from __future__ import annotations

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview

PROTECT_IDS = frozenset({
    "protect", "detect", "spikyshield", "kingsshield", "banefulbunker",
    "burningbulwark", "silktrap", "obstruct", "maxguard",
})
SUPPORT_IDS = frozenset({"followme", "ragepowder", "tailwind", "helpinghand", "allyswitch"})


def move_meta_for(req, slot_index, action):
    """MoveMeta for a ``move`` SlotAction in ``slot_index``; None for switch/pass/invalid."""
    if action.kind != "move" or action.move_index is None:
        return None
    if not req.active or slot_index >= len(req.active) or req.active[slot_index] is None:
        return None
    moves = req.active[slot_index].moves
    idx = action.move_index - 1
    if 0 <= idx < len(moves):
        return get_move_meta(moves[idx].move)
    return None


def pick_best_pair(req, slot_score) -> str:
    """Deterministic policy driver: pick the max-scoring legal joint action, encode it."""
    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        return f"/choose default|{req.rqid}"
    best = pairs[0]
    best_score = float("-inf")
    for pair in pairs:
        s = (slot_score(move_meta_for(req, 0, pair.slot0), pair.slot0)
             + slot_score(move_meta_for(req, 1, pair.slot1), pair.slot1))
        if s > best_score:  # strict > -> first pair wins ties (deterministic)
            best_score = s
            best = pair
    return encode_choose(best, rqid=req.rqid)

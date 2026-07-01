"""Eval-only scripted_vgc opponent policy (T3c) — ISOLATED, tiny, table-driven.

Deliberately NOT strong: a fixed per-slot priority that EXERCISES VGC mechanics — turn-1
disrupt/setup (Fake Out, redirect/support), attack (attempting Tera), and Protect as a
last resort. Mechanic coverage, not a strength claim.
"""
from __future__ import annotations

from showdown_bot.eval.opponents._common import PROTECT_IDS, SUPPORT_IDS, pick_best_pair

# Priority table (higher = preferred). Fake Out > redirect/support > attack (tera'd) > Protect.
_FAKE_OUT = 4.0
_SUPPORT = 3.0
_PROTECT = 0.5


def _scripted_slot(meta, action) -> float:
    if meta is None:
        return -1.0
    mid = meta.id
    if mid == "fakeout":
        return _FAKE_OUT
    if mid in SUPPORT_IDS:
        return _SUPPORT
    if meta.is_damaging:
        score = 1.0 + meta.base_power / 1000.0
        if action.terastallize:
            score += 0.001  # attempt Tera on the chosen attack
        return score
    if mid in PROTECT_IDS:
        return _PROTECT
    return 0.0


def scripted_vgc_choice(req, **_ignored) -> str:
    return pick_best_pair(req, _scripted_slot)

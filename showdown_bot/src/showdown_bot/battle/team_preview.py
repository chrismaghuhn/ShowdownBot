from __future__ import annotations

import random

from showdown_bot.models.request import BattleRequest


def pick_team_preview(
    req: BattleRequest,
    rng: random.Random | None = None,
) -> list[int]:
    """Pick 4 team slots (1-indexed). First two are leads in doubles."""
    rng = rng or random.Random()
    team_size = len(req.side.pokemon)
    if team_size < 4:
        raise ValueError(f"team preview needs at least 4 pokemon, got {team_size}")
    slots = list(range(1, team_size + 1))
    rng.shuffle(slots)
    chosen = slots[:4]
    return chosen


def pick_team_preview_default(req: BattleRequest) -> list[int]:
    """Fixed order: first four on team sheet, leads 1+2."""
    team_size = len(req.side.pokemon)
    if team_size < 4:
        raise ValueError(f"team preview needs at least 4 pokemon, got {team_size}")
    return [1, 2, 3, 4]

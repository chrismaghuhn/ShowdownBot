from __future__ import annotations

import random

from showdown_bot.engine.moves import get_move_meta
from showdown_bot.models.request import BattleRequest, PokemonSlot


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


def _roles(mon: PokemonSlot) -> dict[str, bool]:
    """Detect a mon's preview-relevant roles from its moves (reuses move
    effect-class metadata)."""
    classes: set[str] = set()
    fake_out = False
    for mid in mon.moves:
        meta = get_move_meta(mid)
        classes.update(meta.effect_classes)
        if meta.id == "fakeout":
            fake_out = True
    return {
        "speed_control": "speed_control" in classes,
        "fake_out": fake_out,
        "redirect": "redirect" in classes,
    }


def _bring_score(r: dict[str, bool]) -> float:
    # Speed control is the single most important VGC tool -> weight it highest.
    return 1.0 + 3.0 * r["speed_control"] + 2.0 * r["fake_out"] + 1.5 * r["redirect"]


def _lead_score(r: dict[str, bool]) -> float:
    # Tempo openers belong in the lead slot: Fake Out, then speed control.
    return 3.0 * r["fake_out"] + 2.5 * r["speed_control"] + 2.0 * r["redirect"]


def pick_team_preview_default(req: BattleRequest) -> list[int]:
    """Role-aware Bring-4 + leads (1-indexed; first two are doubles leads).

    Brings the team's speed control and Fake Out users (the VGC tempo core) and
    leads with the strongest tempo openers, instead of the naive first-four. Falls
    back to ``[1,2,3,4]`` when the request carries no move info."""
    team = req.side.pokemon
    if len(team) < 4:
        raise ValueError(f"team preview needs at least 4 pokemon, got {len(team)}")
    if not any(m.moves for m in team):
        return [1, 2, 3, 4]

    roles = [_roles(m) for m in team]
    # Bring the 4 highest-value mons (stable: ties keep team-sheet order).
    chosen = sorted(range(len(team)), key=lambda i: (-_bring_score(roles[i]), i))[:4]
    # Order the chosen 4 so the two best tempo openers lead.
    chosen.sort(key=lambda i: (-_lead_score(roles[i]), i))
    return [i + 1 for i in chosen]

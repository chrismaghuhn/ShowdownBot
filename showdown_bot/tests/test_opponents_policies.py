"""T3c eval-only policies: greedy_protect + simple_heuristic (deterministic, request-only)."""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.eval.opponents.policies import (
    greedy_protect_choice,
    simple_heuristic_choice,
)
from showdown_bot.models.request import BattleRequest

_FIX = Path(__file__).parent / "fixtures" / "request_doubles_moves.json"


def _req():
    # Incineroar (slot0): FakeOut(1) / FlareBlitz(2,120bp) / Protect(3) / KnockOff(4,65bp).
    return BattleRequest.model_validate(json.loads(_FIX.read_text()))


def _slot0(out: str) -> str:
    return out[len("/choose "):].split("|")[0].split(", ")[0]


def test_greedy_protect_picks_protect_when_available():
    assert _slot0(greedy_protect_choice(_req())).startswith("move 3")  # Protect is move 3


def test_greedy_protect_deterministic():
    assert greedy_protect_choice(_req()) == greedy_protect_choice(_req())


def test_simple_heuristic_picks_highest_base_power():
    assert _slot0(simple_heuristic_choice(_req())).startswith("move 2")  # Flare Blitz (120)


def test_simple_heuristic_deterministic():
    assert simple_heuristic_choice(_req()) == simple_heuristic_choice(_req())


def test_choices_are_legal_choose_strings():
    for out in (greedy_protect_choice(_req()), simple_heuristic_choice(_req())):
        assert out.startswith("/choose ") and out.endswith("|2")  # fixture rqid = 2

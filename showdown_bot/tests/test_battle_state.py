from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.engine.log_parser import parse_log
from showdown_bot.engine.state import BattleState, merge_request, parse_details
from showdown_bot.models.request import BattleRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
LOG = FIXTURE_DIR / "logs" / "sample_damage_turn.log"
REQUEST = FIXTURE_DIR / "request_doubles_moves.json"


def test_parse_details():
    d = parse_details("Landorus-Therian, L50, M")
    assert d.species == "Landorus-Therian"
    assert d.level == 50
    assert d.gender == "M"


def test_two_active_per_side_after_turn1():
    events = [e for e in parse_log(LOG.read_text(encoding="utf-8"))]
    # Only feed up to first turn marker to check the opening switch-ins.
    turn1 = []
    for e in events:
        turn1.append(e)
        if e.type == "turn" and e.amount == 1:
            break
    state = BattleState.from_log(turn1)
    assert set(state.side("p1")) == {"a", "b"}
    assert set(state.side("p2")) == {"a", "b"}
    assert state.active("p1", "a").species == "Incineroar"
    assert state.active("p2", "b").species == "Delibird"


def test_damage_and_faint_tracked():
    state = BattleState.from_log_text(LOG.read_text(encoding="utf-8"))
    flutter = state.active("p2", "a")
    assert flutter.fainted is True
    assert flutter.hp == 0
    incineroar = state.active("p1", "a")
    assert incineroar.hp == 96 and incineroar.max_hp == 150
    # Intimidate dropped both opposing attackers by one stage.
    assert incineroar.moves >= {"fakeout", "knockoff"}
    assert state.turn == 3


def test_intimidate_unboost_applied():
    state = BattleState.from_log_text(LOG.read_text(encoding="utf-8"))
    # Flutter Mane fainted but its boost was applied while alive.
    assert state.active("p2", "a").boosts.get("atk") == -1


def test_enditem_marks_item_known():
    state = BattleState.from_log_text(LOG.read_text(encoding="utf-8"))
    flutter = state.active("p2", "a")
    assert flutter.item_known is True
    assert flutter.item is None


def test_merge_request_adds_moves():
    state = BattleState.from_log_text(LOG.read_text(encoding="utf-8"))
    req = BattleRequest.model_validate(json.loads(REQUEST.read_text(encoding="utf-8")))
    merge_request(req, state)
    incineroar = state.active("p1", "a")
    # Moves from the private request are merged into our own active mon.
    assert {"fakeout", "flareblitz", "protect", "knockoff"} <= incineroar.moves

import json
from pathlib import Path

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_pick_random_is_legal():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    legal = set(enumerate_slot_pairs(req))
    pair = pick_random_pair(req, rng=__import__("random").Random(42))
    assert pair in legal

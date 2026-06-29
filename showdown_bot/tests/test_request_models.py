import json
from pathlib import Path

from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_doubles_move_request():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    assert req.rqid == 2
    assert len(req.active) == 2
    assert req.active[0].moves[0].id == "fakeout"
    assert req.active[0].can_terastallize == "Fire"
    assert len(req.side.pokemon) == 4

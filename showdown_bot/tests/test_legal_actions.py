import json
from pathlib import Path

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_enumerate_move_pairs_for_doubles():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    pairs = enumerate_slot_pairs(req)
    assert len(pairs) > 0
    assert all(p.slot0 is not None and p.slot1 is not None for p in pairs)
    ids = {(p.slot0.kind, p.slot1.kind) for p in pairs}
    assert ("move", "move") in ids


def test_no_double_switch_to_same_bench():
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    req = BattleRequest.model_validate(data)
    pairs = enumerate_slot_pairs(req)
    for p in pairs:
        if p.slot0.kind == "switch" and p.slot1.kind == "switch":
            assert p.slot0.target_ident != p.slot1.target_ident

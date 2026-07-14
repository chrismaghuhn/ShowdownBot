import json
from pathlib import Path

from showdown_bot.battle.legal_actions import _slot_move_actions
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.models.actions import SlotAction
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


def test_parse_struggle_only_request():
    """T6 held-out finding (seed t6heldout2026, idx 23): Showdown sends a
    Struggle-only move slot -- {'move': 'Struggle', 'id': 'struggle',
    'target': 'normal'/'randomNormal', 'disabled': False} -- with NO pp/maxpp
    keys when the active mon is out of PP on every real move. The request must
    still parse, with pp/maxpp coming back as None on that slot.
    """
    data = json.loads((FIXTURES / "request_struggle_only.json").read_text())
    req = BattleRequest.model_validate(data)
    assert len(req.active) == 2

    struggle_slot = req.active[0].moves[0]
    assert struggle_slot.id == "struggle"
    assert struggle_slot.pp is None
    assert struggle_slot.maxpp is None

    normal_slot = req.active[1].moves[0]
    assert normal_slot.id == "heatwave"
    assert normal_slot.pp == 16
    assert normal_slot.maxpp == 16


def test_parse_force_switch_request_still_populates_pp():
    """Regression: an ordinary request (moves with real PP left) must keep
    parsing pp/maxpp as ints, not silently drift to None for everyone."""
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    req = BattleRequest.model_validate(data)
    for active_slot in req.active:
        for move in active_slot.moves:
            assert move.pp == 16
            assert move.maxpp == 16


def test_struggle_only_slot_is_a_selectable_move_action():
    """Choice-path smoke: the legal-actions layer must be able to CHOOSE
    Struggle, not just tolerate it in parsing. get_move_meta("Struggle") must
    resolve from the generated move table (it does -- config/moves/movedata.json
    has a "struggle" entry with target "randomNormal", so it is not routed
    through the unknown-move fallback in engine/moves.py).
    """
    meta = get_move_meta("Struggle")
    assert meta.id == "struggle"
    assert meta.is_damaging

    data = json.loads((FIXTURES / "request_struggle_only.json").read_text())
    req = BattleRequest.model_validate(data)
    actions = _slot_move_actions(0, req)
    assert any(a.kind == "move" and a.move_index == 1 for a in actions)


def test_parse_champions_solarbeam_without_target():
    """Champions payloads may omit target; keep None (no MoveMeta backfill)."""
    data = json.loads((FIXTURES / "request_champions_solarbeam_no_target.json").read_text())
    req = BattleRequest.model_validate(data)
    solar = req.active[1].moves[3]
    assert solar.id == "solarbeam"
    assert solar.target is None


def test_champions_solarbeam_without_target_is_selectable():
    data = json.loads((FIXTURES / "request_champions_solarbeam_no_target.json").read_text())
    req = BattleRequest.model_validate(data)
    actions = _slot_move_actions(1, req)
    solar = [a for a in actions if a.kind == "move" and a.move_index == 4]
    assert solar
    assert all(a.target is None for a in solar)


def test_parse_champions_solarbeam_release_minimal_slot():
    """Turn-6 rain held-out: charge-release Solar Beam is move+id only."""
    data = json.loads((FIXTURES / "request_champions_solarbeam_release.json").read_text())
    req = BattleRequest.model_validate(data)
    solar = req.active[0].moves[0]
    assert solar.id == "solarbeam"
    assert solar.target is None
    assert solar.pp is None
    assert solar.maxpp is None


def test_champions_solarbeam_release_slot_actions_are_targetless():
    data = json.loads((FIXTURES / "request_champions_solarbeam_release.json").read_text())
    req = BattleRequest.model_validate(data)
    actions = _slot_move_actions(0, req)
    solar = [a for a in actions if a.kind == "move" and a.move_index == 1]
    assert solar == [SlotAction(kind="move", move_index=1, target=None)]


def test_champions_solarbeam_with_normal_target_stays_targeted():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    solar = req.active[1].moves[3]
    assert solar.target == "normal"
    actions = _slot_move_actions(1, req)
    solar_actions = [a for a in actions if a.kind == "move" and a.move_index == 4]
    assert {a.target for a in solar_actions} == {1, 2}

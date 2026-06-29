from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.models.actions import SlotAction
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def _req(name="request_doubles_moves.json") -> BattleRequest:
    return BattleRequest.model_validate(json.loads((FIXTURES / name).read_text()))


def test_enumerate_strips_tera():
    acts = enumerate_my_actions(_req())
    assert acts
    for ja in acts:
        assert not ja.slot0.terastallize
        assert not ja.slot1.terastallize


def test_enumerate_has_move_move():
    acts = enumerate_my_actions(_req())
    kinds = {(ja.slot0.kind, ja.slot1.kind) for ja in acts}
    assert ("move", "move") in kinds


def test_double_switch_dropped_by_default():
    acts = enumerate_my_actions(_req(), allow_double_switch=False)
    assert not any(
        ja.slot0.kind == "switch" and ja.slot1.kind == "switch" for ja in acts
    )


def test_double_switch_allowed_when_requested():
    acts = enumerate_my_actions(_req(), allow_double_switch=True)
    assert any(
        ja.slot0.kind == "switch" and ja.slot1.kind == "switch" for ja in acts
    )


def test_with_tera_applies_to_move_slot():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="switch", target_ident="Flutter Mane"),
    )
    t0 = ja.with_tera(0)
    assert t0.slot0.terastallize is True
    assert t0.slot1.terastallize is False
    # cannot tera while switching -> no-op
    t1 = ja.with_tera(1)
    assert t1.slot1.terastallize is False
    assert t1 is ja or t1.slot1.terastallize is False


def test_as_pair_roundtrip():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=2, target=1),
        slot1=SlotAction(kind="move", move_index=1, target=2),
    )
    pair = ja.as_pair()
    assert pair.slot0 is ja.slot0
    assert pair.slot1 is ja.slot1

import json
from pathlib import Path

from showdown_bot.battle.legal_actions import _move_targets, enumerate_slot_pairs
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_side_field_moves_take_no_target():
    """Regression: allySide (Tailwind/screens), foeSide, randomNormal etc. take
    NO target. The old default [1,2] gave them a foe target -> 'move N 1' ->
    server rejects 'You can't choose a target for Tailwind' and the game stalls."""
    assert _move_targets("allySide") == [None]
    assert _move_targets("allyTeam") == [None]
    assert _move_targets("foeSide") == [None]
    assert _move_targets("randomNormal") == [None]
    assert _move_targets("normal") == [1, 2]
    assert _move_targets("adjacentFoe") == [1, 2]
    # Tailwind really is an allySide move in the data -> must be targetless.
    assert get_move_meta("Tailwind").target == "allySide"


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


def test_force_switch_with_null_active_yields_switches():
    # Mid-turn faint: Showdown sends forceSwitch with NO `active` block.
    req = BattleRequest.model_validate(
        {
            "forceSwitch": [True, False],
            "side": {
                "pokemon": [
                    {"ident": "p1: A", "details": "A", "condition": "0 fnt", "active": True, "moves": []},
                    {"ident": "p1: B", "details": "B", "condition": "100/100", "active": True, "moves": []},
                    {"ident": "p1: C", "details": "C", "condition": "100/100", "active": False, "moves": []},
                    {"ident": "p1: D", "details": "D", "condition": "100/100", "active": False, "moves": []},
                ]
            },
            "rqid": 9,
        }
    )
    pairs = enumerate_slot_pairs(req)
    assert pairs, "force-switch with null active must still yield legal choices"
    # forced slot switches to a bench mon; non-forced slot passes
    assert all(p.slot0.kind == "switch" for p in pairs)
    assert all(p.slot1.kind == "pass" for p in pairs)
    assert {p.slot0.target_ident for p in pairs} == {"C", "D"}


def _choice_request(item: str):
    return BattleRequest.model_validate(
        {
            "active": [
                {
                    "moves": [
                        {"move": "Moonblast", "id": "moonblast", "pp": 16, "maxpp": 16, "target": "normal", "disabled": False},
                        {"move": "Shadow Ball", "id": "shadowball", "pp": 16, "maxpp": 16, "target": "normal", "disabled": False},
                        {"move": "Protect", "id": "protect", "pp": 16, "maxpp": 16, "target": "self", "disabled": False},
                    ]
                },
                None,
            ],
            "side": {
                "pokemon": [
                    {"ident": "p1: Flutter Mane", "details": "Flutter Mane", "condition": "100/100", "active": True, "item": item, "moves": []},
                    {"ident": "p1: Inc", "details": "Incineroar", "condition": "0 fnt", "active": True, "item": "", "moves": []},
                ]
            },
            "rqid": 5,
        }
    )


def test_choice_item_holder_cannot_select_protect():
    """Clicking a non-damaging move (Protect) with a Choice item locks the mon
    into it forever -> infinite stall. Such moves must be filtered out."""
    req = _choice_request("choicespecs")
    pairs = enumerate_slot_pairs(req)
    move_indices = {p.slot0.move_index for p in pairs if p.slot0.kind == "move"}
    assert 3 not in move_indices, "Protect (index 3) must not be offered to a Choice holder"
    assert move_indices == {1, 2}  # only the damaging moves


def test_non_choice_holder_keeps_protect():
    req = _choice_request("")  # no item -> Protect stays legal
    pairs = enumerate_slot_pairs(req)
    move_indices = {p.slot0.move_index for p in pairs if p.slot0.kind == "move"}
    assert 3 in move_indices


def test_one_mon_left_doubles_null_active_slot():
    # A doubles side with one mon left: the empty slot serializes as null.
    # Must parse (not raise) and yield "move ..., pass" choices.
    from showdown_bot.battle.actions import enumerate_my_actions

    req = BattleRequest.model_validate(
        {
            "active": [
                {"moves": [{"move": "Earth Power", "id": "earthpower", "pp": 16, "maxpp": 16, "target": "normal", "disabled": False}]},
                None,
            ],
            "side": {
                "pokemon": [
                    {"ident": "p1: Lando", "details": "Landorus-Therian", "condition": "100/100", "active": True, "moves": []},
                    {"ident": "p1: Inc", "details": "Incineroar", "condition": "0 fnt", "active": True, "moves": []},
                ]
            },
            "rqid": 20,
        }
    )
    pairs = enumerate_slot_pairs(req)
    assert pairs
    assert all(p.slot1.kind == "pass" for p in pairs)
    assert any(p.slot0.kind == "move" for p in pairs)
    # the heuristic enumerator must also handle the null slot
    assert enumerate_my_actions(req)

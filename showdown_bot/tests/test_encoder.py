from showdown_bot.models.actions import SlotAction, SlotPair
from showdown_bot.protocol.encoder import encode_choose, format_slot_action


def test_format_move_with_target():
    a = SlotAction(kind="move", move_index=1, target=2)
    assert format_slot_action(a) == "move 1 2"


def test_format_protect():
    a = SlotAction(kind="move", move_index=3)
    assert format_slot_action(a) == "move 3"


def test_format_switch():
    a = SlotAction(kind="switch", target_ident="Rillaboom")
    assert format_slot_action(a) == "switch Rillaboom"


def test_encode_choose_with_rqid():
    pair = SlotPair(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="move", move_index=3),
    )
    assert encode_choose(pair, rqid=2) == "/choose move 1 1, move 3"

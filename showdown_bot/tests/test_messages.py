from showdown_bot.protocol.messages import parse_message, ParsedMessage


def test_parse_request_message():
    raw = '|request|{"rqid":1,"active":[{"moves":[]}]}'
    msg = parse_message(raw)
    assert msg.prefix == "request"
    assert msg.payload.startswith('{"rqid"')


def test_parse_battle_init():
    raw = "|init|battle"
    msg = parse_message(raw)
    assert msg.prefix == "init"
    assert msg.args == ["battle"]


def test_parse_with_room_prefix():
    raw = ">battle-gen9vgc2024regf-123|request|{}"
    msg = parse_message(raw)
    assert msg.room == "battle-gen9vgc2024regf-123"
    assert msg.prefix == "request"

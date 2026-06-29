import json
from pathlib import Path

import pytest

from showdown_bot.client.auth import (
    AuthError,
    fetch_guest_assertion,
    parse_auth_response,
)
from showdown_bot.battle.decision import choose_for_request
from showdown_bot.battle.team_preview import pick_team_preview, pick_team_preview_default
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_team_preview

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_login_json_response():
    body = ']{ "assertion": "abc123", "curuser": { "loggedin": true } }'
    assert parse_auth_response(body) == "abc123"


def test_parse_raw_assertion():
    assert parse_auth_response("someguestassertion") == "someguestassertion"


def test_parse_rejects_semicolon_error():
    with pytest.raises(AuthError, match="username is no longer available"):
        parse_auth_response(";;Your username is no longer available.")


def test_to_showdown_id():
    from showdown_bot.client.auth import to_showdown_id

    assert to_showdown_id("VGCRegBot107763") == "vgcregbot107763"


def test_encode_team_preview_with_rqid():
    assert encode_team_preview([1, 2, 3, 4], rqid=1) == "/choose team 1234 #1"


def test_pick_team_preview_default_four_slots():
    data = json.loads((FIXTURES / "request_team_preview.json").read_text())
    req = BattleRequest.model_validate(data)
    assert pick_team_preview_default(req) == [1, 2, 3, 4]


def test_pick_team_preview_random_is_four_unique():
    data = json.loads((FIXTURES / "request_team_preview.json").read_text())
    req = BattleRequest.model_validate(data)
    slots = pick_team_preview(req, __import__("random").Random(0))
    assert len(slots) == 4
    assert len(set(slots)) == 4
    assert all(1 <= s <= 6 for s in slots)


def test_choose_for_team_preview_request():
    data = json.loads((FIXTURES / "request_team_preview.json").read_text())
    req = BattleRequest.model_validate(data)
    cmd = choose_for_request(req)
    assert cmd == "/choose team 1234 #1"


@pytest.mark.integration
def test_fetch_guest_assertion_live():
    assertion = fetch_guest_assertion(
        "vgcbottestguest",
        "4|testchallstr",
    )
    assert assertion

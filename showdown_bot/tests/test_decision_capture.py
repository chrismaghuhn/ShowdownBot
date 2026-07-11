from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from showdown_bot.eval.decision_capture import (
    DecisionCaptureError,
    normalize_choose,
    observable_state_payload,
    prepare_capture,
)
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def capture_fixture(decision_fixture):
    req, kw = decision_fixture
    return req, copy.deepcopy(kw["state"])


def test_observable_hash_is_order_independent(capture_fixture):
    request, state = capture_fixture
    left = prepare_capture(state, request)
    state.sides["p1"]["a"].boosts = {"spe": 1, "atk": -1}
    right = prepare_capture(state, request)
    state.sides["p1"]["a"].boosts = {"atk": -1, "spe": 1}
    again = prepare_capture(state, request)
    assert right.observable_state_hash == again.observable_state_hash
    assert left.request_hash == right.request_hash


def test_payload_has_explicit_allowlist(capture_fixture):
    _request, state = capture_fixture
    payload = observable_state_payload(state)
    rendered = json.dumps(payload, sort_keys=True)
    assert "game_outcome" not in rendered
    assert "winner" not in rendered
    assert "teacher" not in rendered


def test_prepare_capture_regular_turn_phase(capture_fixture):
    request, state = capture_fixture
    capture = prepare_capture(state, request)
    assert capture.decision_phase == "regular_turn"


def test_prepare_capture_team_preview_phase():
    data = json.loads((FIXTURES / "request_team_preview.json").read_text())
    request = BattleRequest.model_validate(data)
    capture = prepare_capture(None, request)
    assert capture.decision_phase == "team_preview"
    assert capture.state_summary == {"turn": 0, "field": {}, "sides": {}}


def test_prepare_capture_forced_replacement_phase():
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    request = BattleRequest.model_validate(data)
    capture = prepare_capture(None, request)
    assert capture.decision_phase == "forced_replacement"


@pytest.mark.parametrize(
    ("choose", "kind", "move_id", "target", "tera"),
    [
        ("/choose move 1 1, move 2 2|7", "joint", "fakeout", 1, False),
        ("/choose move 1 1 terastallize, pass|7", "joint", "fakeout", 1, True),
        ("/choose team 1234|7", "team_preview", None, None, False),
        ("/choose default|7", "default", None, None, False),
    ],
)
def test_normalize_choose(choose, kind, move_id, target, tera, capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose(choose, request)
    assert action["kind"] == kind
    if kind == "joint":
        assert action["slots"][0]["move_id"] == move_id
        assert action["slots"][0]["target"] == target
        assert action["slots"][0]["tera"] is tera


def test_normalize_choose_team_preview_order(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose team 1234|7", request)
    assert action["order"] == [1, 2, 3, 4]


def test_normalize_choose_switch(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose switch 3, move 1 1|7", request)
    assert action["kind"] == "joint"
    assert action["slots"][0] == {"kind": "switch", "switch_target": "3"}
    assert action["slots"][1]["kind"] == "move"
    assert action["slots"][1]["move_id"] == "heatwave"


def test_normalize_choose_protect_flags_is_protect(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose move 3 1, move 3 1|7", request)
    assert action["slots"][0]["move_id"] == "protect"
    assert action["slots"][0]["is_protect"] is True
    assert action["slots"][1]["move_id"] == "protect"
    assert action["slots"][1]["is_protect"] is True


def test_normalize_choose_negative_ally_target(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose move 4 -1, pass|7", request)
    assert action["slots"][0]["move_id"] == "knockoff"
    assert action["slots"][0]["target"] == -1
    assert action["slots"][1] == {"kind": "pass"}


def test_normalize_choose_forced_replacement():
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    request = BattleRequest.model_validate(data)
    action = normalize_choose("/choose switch 3, pass|5", request)
    assert action["kind"] == "joint"
    assert action["slots"][0] == {"kind": "switch", "switch_target": "3"}
    assert action["slots"][1] == {"kind": "pass"}


def test_normalize_choose_invalid_move_index_raises(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/choose move 9 1, pass|7", request)


def test_normalize_choose_unsupported_slot_token_raises(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/choose shift, pass|7", request)


def test_normalize_choose_unknown_command_raises(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/forfeit|7", request)

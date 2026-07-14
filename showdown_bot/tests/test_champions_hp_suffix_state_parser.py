"""Champions HP suffix (100y / 100g / 100r) state-parser regression (I5 slice)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.client.gauntlet import _Client
from showdown_bot.engine.log_parser import HpStatus, parse_log
from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.models.request import BattleRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REQUEST = FIXTURE_DIR / "request_doubles_moves.json"

CHAMPIONS_DAMAGE_Y = (
    "|switch|p1a: Garchomp|Garchomp, L50|215/215\n"
    "|switch|p2b: Basculegion|Basculegion, L50|197/197\n"
    "|turn|1\n"
    "|-damage|p2b: Basculegion|20/100y\n"
)

CHAMPIONS_DAMAGE_G = (
    "|switch|p1a: Garchomp|Garchomp, L50|215/215\n"
    "|switch|p2b: Basculegion|Basculegion, L50|197/197\n"
    "|turn|1\n"
    "|-damage|p2b: Basculegion|50/100g\n"
)

CHAMPIONS_DAMAGE_R = (
    "|switch|p1a: Garchomp|Garchomp, L50|215/215\n"
    "|switch|p2b: Basculegion|Basculegion, L50|197/197\n"
    "|turn|1\n"
    "|-damage|p2b: Basculegion|20/100r\n"
)


def test_hp_status_champions_suffix_y():
    # Showdown emits y/r at the 20% HP color threshold.
    assert HpStatus.parse("20/100y") == HpStatus(current=20, maximum=100)


def test_hp_status_champions_suffix_g():
    # Showdown emits g/y at the 50% HP color threshold.
    assert HpStatus.parse("50/100g") == HpStatus(current=50, maximum=100)


def test_hp_status_champions_suffix_r():
    # Showdown emits y/r at the 20% HP color threshold.
    assert HpStatus.parse("20/100r") == HpStatus(current=20, maximum=100)


def test_hp_status_normal_fraction_unchanged():
    assert HpStatus.parse("20/100") == HpStatus(current=20, maximum=100)


def test_hp_status_fnt_and_status_suffix_unchanged():
    assert HpStatus.parse("0 fnt") == HpStatus(current=0, maximum=None, fainted=True)
    assert HpStatus.parse("71/100 par") == HpStatus(current=71, maximum=100, status="par")


def test_malformed_hp_not_silently_coerced():
    with pytest.raises(ValueError):
        HpStatus.parse("20/100%")
    with pytest.raises(ValueError):
        HpStatus.parse("abc/100")
    with pytest.raises(ValueError):
        HpStatus.parse("20/abc")
    with pytest.raises(ValueError):
        HpStatus.parse("20/100garbage")
    with pytest.raises(ValueError):
        HpStatus.parse("20y/100")


def test_damage_log_with_suffix_y_parses_without_exception():
    events = parse_log(CHAMPIONS_DAMAGE_Y)
    dmg = [e for e in events if e.type == "damage"][0]
    assert dmg.hp == HpStatus(current=20, maximum=100)


def test_damage_log_with_suffix_g_parses_without_exception():
    events = parse_log(CHAMPIONS_DAMAGE_G)
    dmg = [e for e in events if e.type == "damage"][0]
    assert dmg.hp == HpStatus(current=50, maximum=100)


def test_damage_log_with_suffix_r_parses_without_exception():
    events = parse_log(CHAMPIONS_DAMAGE_R)
    dmg = [e for e in events if e.type == "damage"][0]
    assert dmg.hp == HpStatus(current=20, maximum=100)


def test_battle_state_from_log_text_champions_suffix():
    state = BattleState.from_log_text(CHAMPIONS_DAMAGE_Y)
    basc = state.active("p2", "b")
    assert basc.hp == 20
    assert basc.max_hp == 100


def test_merge_request_champions_condition_suffix():
    state = BattleState.from_log_text(CHAMPIONS_DAMAGE_Y)
    req_data = json.loads(REQUEST.read_text(encoding="utf-8"))
    req_data["side"]["pokemon"][0]["condition"] = "96/150y"
    req_data["side"]["pokemon"][1]["condition"] = "140/155g"
    req = BattleRequest.model_validate(req_data)
    merge_request(req, state)
    assert state.active("p1", "a").hp == 96
    assert state.active("p1", "a").max_hp == 150
    assert state.active("p1", "b").hp == 140
    assert state.active("p1", "b").max_hp == 155


def test_client_state_for_returns_state_not_none_on_suffix():
    req = BattleRequest.model_validate(json.loads(REQUEST.read_text(encoding="utf-8")))
    client = _Client(
        conn=object(),
        name="Hero",
        agent="heuristic",
        book=object(),
        priors=None,
        format_id="gen9championsvgc2026regma",
        packed_team="",
        opp_sets={},
    )
    room = "battle-gen9championsvgc2026regma-1"
    client.room_raw[room] = CHAMPIONS_DAMAGE_Y.splitlines()
    state = client._state_for(room, req)
    assert state is not None
    assert state.active("p2", "b").hp == 20
    assert state.active("p2", "b").max_hp == 100

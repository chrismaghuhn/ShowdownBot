from __future__ import annotations

from pathlib import Path

from showdown_bot.engine.log_parser import HpStatus, LogEvent, PokemonId, parse_log

FIXTURE = Path(__file__).parent / "fixtures" / "logs" / "sample_damage_turn.log"


def _events() -> list[LogEvent]:
    return parse_log(FIXTURE.read_text(encoding="utf-8"))


def test_pokemon_id_parse():
    pid = PokemonId.parse("p2a: Flutter Mane")
    assert pid.side == "p2"
    assert pid.slot == "a"
    assert pid.name == "Flutter Mane"


def test_hp_status_variants():
    assert HpStatus.parse("52/100") == HpStatus(current=52, maximum=100)
    assert HpStatus.parse("0 fnt") == HpStatus(current=0, maximum=None, fainted=True)
    assert HpStatus.parse("71/100 par") == HpStatus(current=71, maximum=100, status="par")


def test_delibird_damage_parsed():
    events = _events()
    dmg = [
        e
        for e in events
        if e.type == "damage" and e.pokemon and e.pokemon.name == "Delibird"
    ]
    first = dmg[0]
    assert first.hp == HpStatus(current=52, maximum=100)


def test_turns_increment():
    turns = [e.amount for e in _events() if e.type == "turn"]
    assert turns == [1, 2, 3]


def test_switch_and_faint_and_boost():
    events = _events()
    switches = [e for e in events if e.type == "switch"]
    assert any(e.pokemon and e.pokemon.name == "Incineroar" for e in switches)

    unboost = [e for e in events if e.type == "boost" and e.amount == -1]
    assert len(unboost) == 2  # Intimidate hits both opposing mons

    faints = [e.pokemon.name for e in events if e.type == "faint" and e.pokemon]
    assert "Flutter Mane" in faints and "Delibird" in faints


def test_enditem_and_move_target():
    events = _events()
    enditem = [e for e in events if e.type == "enditem"]
    assert enditem and enditem[0].value == "Booster Energy"

    moves = [e for e in events if e.type == "move"]
    fake_out = next(e for e in moves if e.details == "Fake Out")
    assert fake_out.target and fake_out.target.name == "Delibird"


def test_malformed_protocol_lines_do_not_abort_following_valid_events():
    raw = "\n".join(
        [
            "|switch|",
            "|-damage|p1a: Incineroar|not-hp",
            "|-boost|p1a: Incineroar|atk|not-an-int",
            "|turn|not-a-turn",
            "|move|p1a: Incineroar",
            "|faint|",
            "|turn|7",
        ]
    )
    events = parse_log(raw)
    # "-damage" with a present-but-unparseable HP token and "move" with no move name are now
    # DROPPED entirely (like an unparseable pokemon token already was), not kept with a
    # fabricated None/"" field -- see test_validate_log.py's fabrication-prevention tests for
    # why: a kept-but-nulled HP/move silently becomes "no damage happened" / an empty move name
    # once paired into a DamageInstance downstream.
    assert [(event.type, event.amount) for event in events] == [
        ("boost", None),
        ("turn", None),
        ("turn", 7),
    ]

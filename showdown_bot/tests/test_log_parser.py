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

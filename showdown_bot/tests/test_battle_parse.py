"""T2 side-agnostic battle-result parser (winner/turns/players/hp_by_slot from room_raw).

The parser knows nothing about hero/villain; it returns raw slot data + the |player| name
map so the row assembler (Task 3) can resolve sides explicitly. HP is best-effort: null
hp_by_slot on any surprise, never a crash.
"""
from __future__ import annotations

from showdown_bot.eval.battle_parse import parse_battle_result

_FULL = [
    ">battle-gen9vgc2025regi-1",
    "|player|p1|HeroBot|170|",
    "|player|p2|VillainBot|2|",
    "|switch|p1a: Incineroar|Incineroar, L50, F|200/200",
    "|switch|p2a: Rillaboom|Rillaboom, L50, M|100/100",
    "|turn|1",
    "|-damage|p2a: Rillaboom|50/100",
    "|turn|2",
    "|-damage|p2a: Rillaboom|0 fnt",
    "|faint|p2a: Rillaboom",
    "|turn|3",
    "|win|HeroBot",
]


def test_parse_full_battle():
    r = parse_battle_result([("\n".join(_FULL))])
    assert r["winner_name"] == "HeroBot"
    assert r["is_tie"] is False
    assert r["turns"] == 3
    assert r["players"] == {"p1": "HeroBot", "p2": "VillainBot"}
    assert abs(r["hp_by_slot"]["p1"] - 1.0) < 1e-9   # Incineroar full
    assert abs(r["hp_by_slot"]["p2"] - 0.0) < 1e-9   # Rillaboom fainted


def test_parse_tie():
    frames = ["|player|p1|A|1|", "|player|p2|B|1|", "|turn|1", "|tie"]
    r = parse_battle_result(frames)
    assert r["is_tie"] is True
    assert r["winner_name"] is None
    assert r["turns"] == 1


def test_parse_malformed_is_tolerated():
    r = parse_battle_result(["garbage", "|-damage|not a valid line", "|switch|weird"])
    assert r["winner_name"] is None
    assert r["hp_by_slot"] is None
    assert r["turns"] == 0


def test_hp_by_slot_sums_multiple_mons_per_side():
    frames = [
        "|switch|p1a: Incineroar|Incineroar, L50, F|100/100",
        "|switch|p1b: Rillaboom|Rillaboom, L50, M|50/100",   # 0.5
        "|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100",
        "|-damage|p1a: Incineroar|50/100",                    # 0.5
        "|win|X",
    ]
    r = parse_battle_result(frames)
    assert abs(r["hp_by_slot"]["p1"] - 1.0) < 1e-9   # 0.5 + 0.5
    assert abs(r["hp_by_slot"]["p2"] - 1.0) < 1e-9   # 1.0


# --- T3f Task 5: end_reason detection from room_raw ------------------------------------

def test_end_reason_normal_win():
    assert parse_battle_result([("\n".join(_FULL))])["end_reason"] == "normal"


def test_end_reason_normal_tie():
    frames = ["|player|p1|A|1|", "|player|p2|B|1|", "|turn|1", "|tie"]
    assert parse_battle_result(frames)["end_reason"] == "normal"


def test_end_reason_timeout_inactivity():
    frames = [
        "|player|p1|HeroBot|1|", "|player|p2|VillainBot|1|", "|turn|1",
        "|inactive|VillainBot has 30 seconds left.",
        "|-message|VillainBot lost due to inactivity.",
        "|win|HeroBot",
    ]
    assert parse_battle_result(frames)["end_reason"] == "timeout"


def test_end_reason_forfeit():
    frames = [
        "|player|p1|HeroBot|1|", "|player|p2|VillainBot|1|", "|turn|1",
        "|-message|VillainBot forfeited.",
        "|win|HeroBot",
    ]
    assert parse_battle_result(frames)["end_reason"] == "forfeit"


def test_end_reason_crash():
    frames = [
        "|player|p1|HeroBot|1|", "|player|p2|VillainBot|1|", "|turn|1",
        "|error|The battle crashed",
        "|win|HeroBot",
    ]
    assert parse_battle_result(frames)["end_reason"] == "crash"


def test_end_reason_crash_takes_priority_over_timeout():
    frames = [
        "|-message|VillainBot lost due to inactivity.",
        "|error|The battle crashed",
        "|win|HeroBot",
    ]
    assert parse_battle_result(frames)["end_reason"] == "crash"

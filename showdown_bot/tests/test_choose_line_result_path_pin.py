"""Pin: `>choose rqid=<N> <choice>` diagnostic lines (added to dump_frames() by the
choose-dispatch-log slice) are invisible to the result path.

Three independent filters currently make this true by coincidence rather than by
contract: `normalize_battle_log` drops every `>`-prefixed line outright,
`parse_battle_result`'s main loop skips lines without a `|` prefix, and
`_detect_end_reason` substring-matches over ALL lines (not guarded against `>`-prefixed
diagnostic content). This file pins the two visible properties. The third gap
(`_detect_end_reason`) is closed and pinned separately in
test_detect_end_reason_ignores_choose_lines.py.
"""
from __future__ import annotations

from showdown_bot.eval.battle_parse import parse_battle_result
from showdown_bot.eval.room_dump import normalized_room_log_sha256

_BASE_FRAMES = [
    "|player|p1|HeuristicBot1234|blue|1000",
    "|player|p2|BaselineBot5678|red|1000",
    "|turn|1",
    "|move|p1a: Aerodactyl|Rock Slide|p2a: Incineroar",
    "|-damage|p2a: Incineroar|50/100",
    "|turn|2",
    "|win|HeuristicBot1234",
]

_CHOOSE_LINES = [
    ">choose rqid=4 move rockslide 1, move protect",
    ">choose rqid=6 switch 3",
]

_FORFEIT_FRAMES = [
    "|player|p1|HeuristicBot1234|blue|1000",
    "|player|p2|BaselineBot5678|red|1000",
    "|turn|1",
    "|move|p1a: Aerodactyl|Rock Slide|p2a: Incineroar",
    "BaselineBot5678 forfeited.",
    "|win|HeuristicBot1234",
]


def test_hash_is_identical_with_and_without_choose_lines():
    # This is the guard for normalize_battle_log's ">"-line drop, not a style pin: the
    # 360 normalized_room_log_sha256 values frozen in the Gate B evidence on main
    # (data/eval/.../gate-b-safety-fail-bc2d6df/{arm-a-heuristic,arm-b-max-damage}/rows.jsonl,
    # 180 rows each) were all computed before dump_frames() started appending >choose
    # lines. If this test ever goes red, something started letting >choose content
    # into the hash -- the fix is in normalize_battle_log, never re-pinning this
    # expectation or the frozen values.
    without = list(_BASE_FRAMES)
    with_choose = list(_BASE_FRAMES) + list(_CHOOSE_LINES)
    assert normalized_room_log_sha256(without) == normalized_room_log_sha256(with_choose)


def test_parse_battle_result_is_identical_with_and_without_choose_lines():
    without = list(_BASE_FRAMES)
    with_choose = list(_BASE_FRAMES) + list(_CHOOSE_LINES)
    assert parse_battle_result(without) == parse_battle_result(with_choose)


def test_hash_is_identical_with_and_without_choose_lines_on_a_forfeit():
    without = list(_FORFEIT_FRAMES)
    with_choose = list(_FORFEIT_FRAMES) + list(_CHOOSE_LINES)
    assert normalized_room_log_sha256(without) == normalized_room_log_sha256(with_choose)


def test_parse_battle_result_is_identical_with_and_without_choose_lines_on_a_forfeit():
    without = list(_FORFEIT_FRAMES)
    with_choose = list(_FORFEIT_FRAMES) + list(_CHOOSE_LINES)
    result_without = parse_battle_result(without)
    result_with = parse_battle_result(with_choose)
    assert result_without["end_reason"] == "forfeit"
    assert result_without == result_with

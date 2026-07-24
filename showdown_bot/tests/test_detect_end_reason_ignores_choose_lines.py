"""Adversarial pin: `_detect_end_reason` must never classify a battle from text that
appears only inside a `>`-prefixed client/session line -- `>choose` diagnostic lines
(client/gauntlet.py's dump_frames()) included. Room-header lines (`>battle-<format>-<n>`)
are the existing case `normalize_battle_log` already treats as session metadata;
`_detect_end_reason` runs over the same frames but, before this guard, had no such
skip and substring-matched every line regardless of a `>` prefix.

This is intentionally adversarial: the synthetic choice string itself contains the word
"forfeited" so it would flip a naive case-insensitive substring scan even though nothing
in the actual battle ended that way.
"""
from __future__ import annotations

from showdown_bot.eval.battle_parse import parse_battle_result

_FRAMES_NO_REAL_FORFEIT = [
    "|player|p1|HeuristicBot1234|blue|1000",
    "|player|p2|BaselineBot5678|red|1000",
    "|turn|1",
    "|move|p1a: Aerodactyl|Rock Slide|p2a: Incineroar",
    "|-damage|p2a: Incineroar|50/100",
    "|turn|2",
    "|win|HeuristicBot1234",
    ">choose rqid=9 team forfeited squad 1, 2",
]


def test_a_choose_line_containing_forfeited_text_does_not_flip_end_reason():
    result = parse_battle_result(_FRAMES_NO_REAL_FORFEIT)
    assert result["end_reason"] == "normal", result["end_reason"]

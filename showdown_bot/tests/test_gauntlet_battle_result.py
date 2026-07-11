"""T2 pure battle-record assembler: explicit hero/villain/tie mapping + hero-side end_hp_diff.

Tested without a live server. Unknown winner -> ResultRowError (never guessed); end_hp_diff
is hero-side minus villain-side via the |player| slot map, or null if that mapping is unreliable.
"""
from __future__ import annotations

import hashlib

import pytest

from showdown_bot.client.gauntlet import _battle_result_record
from showdown_bot.eval.result_jsonl import ResultRowError
from showdown_bot.eval.room_dump import GAUNTLET_NAME_SUBS, normalize_battle_log

_BASE = [
    "|player|p1|HeroBot|1|",
    "|player|p2|VillBot|1|",
    "|switch|p1a: Incineroar|Incineroar, L50|100/100",
    "|switch|p2a: Rillaboom|Rillaboom, L50|50/100",
    "|turn|1",
    "|turn|2",
    "|win|HeroBot",
]


def _frames(win="HeroBot"):
    lines = [ln if not ln.startswith("|win|") else f"|win|{win}" for ln in _BASE]
    return ["\n".join(lines)]


def test_hero_win_and_end_hp_diff():
    r = _battle_result_record("HeroBot", "VillBot", _frames(), invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=100, room_raw_path=None)
    assert r["winner"] == "hero"
    assert r["turns"] == 2
    assert abs(r["end_hp_diff"] - (1.0 - 0.5)) < 1e-9  # hero p1=1.0 minus villain p2=0.5


def test_villain_win_carries_stats():
    r = _battle_result_record("HeroBot", "VillBot", _frames(win="VillBot"), invalid_choices=1,
                              crashes=2, decision_latency_p95_ms=50, room_raw_path="x.log")
    assert r["winner"] == "villain"
    assert r["invalid_choices"] == 1 and r["crashes"] == 2 and r["room_raw_path"] == "x.log"


def test_tie():
    frames = ["\n".join(["|player|p1|A|1|", "|player|p2|B|1|", "|turn|1", "|tie"])]
    r = _battle_result_record("A", "B", frames, invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=0, room_raw_path=None)
    assert r["winner"] == "tie"


def test_unknown_winner_raises():
    with pytest.raises(ResultRowError):
        _battle_result_record("HeroBot", "VillBot", _frames(win="SomebodyElse"),
                              invalid_choices=0, crashes=0, decision_latency_p95_ms=0, room_raw_path=None)


def test_end_hp_diff_null_when_side_mapping_unreliable():
    # No |player| lines -> can't map hero/villain to slots -> end_hp_diff null (not guessed).
    frames = ["\n".join(["|switch|p1a: X|X, L50|100/100", "|win|HeroBot"])]
    r = _battle_result_record("HeroBot", "VillBot", frames, invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=0, room_raw_path=None)
    assert r["winner"] == "hero"
    assert r["end_hp_diff"] is None


def test_record_carries_end_reason_normal():
    # T3f Task 5: an ordinary |win| battle -> end_reason "normal".
    r = _battle_result_record("HeroBot", "VillBot", _frames(), invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=100, room_raw_path=None)
    assert r["end_reason"] == "normal"


def test_record_carries_end_reason_forfeit():
    frames = ["\n".join([
        "|player|p1|HeroBot|1|", "|player|p2|VillBot|1|", "|turn|1",
        "|-message|VillBot forfeited.", "|win|HeroBot",
    ])]
    r = _battle_result_record("HeroBot", "VillBot", frames, invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=0, room_raw_path=None)
    assert r["winner"] == "hero" and r["end_reason"] == "forfeit"


def test_normalized_room_log_sha256_matches_canonical_normalization():
    # T4c R1: the row's sha must equal hashlib.sha256 over normalize_battle_log's output,
    # using the SAME name_subs convention (GAUNTLET_NAME_SUBS) as the T4 identity check
    # (validate_prefix_reproduction), joined + encoded the way dump_room_raw writes the
    # room_raw file itself ("\n".join(...).encode("utf-8")).
    frames = _frames()
    r = _battle_result_record("HeroBot", "VillBot", frames, invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=100, room_raw_path=None)
    expected = hashlib.sha256(
        "\n".join(normalize_battle_log(frames, name_subs=GAUNTLET_NAME_SUBS)).encode("utf-8")
    ).hexdigest()
    assert r["normalized_room_log_sha256"] == expected


def test_normalized_room_log_sha256_differs_on_a_real_divergence():
    # Sanity: not a constant -- a genuine battle difference changes the sha.
    r_a = _battle_result_record("HeroBot", "VillBot", _frames(), invalid_choices=0, crashes=0,
                                decision_latency_p95_ms=0, room_raw_path=None)
    frames_b = ["\n".join([
        "|player|p1|HeroBot|1|", "|player|p2|VillBot|1|",
        "|switch|p1a: Incineroar|Incineroar, L50|100/100",
        "|switch|p2a: Rillaboom|Rillaboom, L50|10/100",  # different HP roll
        "|turn|1", "|turn|2", "|win|HeroBot",
    ])]
    r_b = _battle_result_record("HeroBot", "VillBot", frames_b, invalid_choices=0, crashes=0,
                                decision_latency_p95_ms=0, room_raw_path=None)
    assert r_a["normalized_room_log_sha256"] != r_b["normalized_room_log_sha256"]


def test_normalized_room_log_sha256_null_on_hashing_failure(monkeypatch):
    # T4c: any exception during sha computation -> field None, battle record still assembled.
    import showdown_bot.client.gauntlet as gauntlet_mod

    def _boom(frames, *, name_subs=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(gauntlet_mod, "normalize_battle_log", _boom)
    r = _battle_result_record("HeroBot", "VillBot", _frames(), invalid_choices=0, crashes=0,
                              decision_latency_p95_ms=0, room_raw_path=None)
    assert r["normalized_room_log_sha256"] is None
    assert r["winner"] == "hero"  # the rest of the record is unaffected

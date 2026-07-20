"""Task 6: the hero-specific, foe-Mega-bound safety seam -- ON the in-memory GauntletStats, OFF the
closed T2 result row. Each hero invalid choice is attributed to the SENT choice's decision_index
(recorded per room at send time), never the since-advanced counter; an unattributable |error|
records a fail-closed -1 sentinel; the closed T2 writer (eval/result_jsonl.py) is untouched.
"""
from __future__ import annotations

from showdown_bot.client.gauntlet import GauntletStats, _Client
from showdown_bot.eval.result_jsonl import NULLABLE_FIELDS, REQUIRED_FIELDS


def _client() -> _Client:
    # A bare client with only the invalid-attribution state the seam touches (the real __init__ is
    # heavy -- a live connection, agent, book, ...; the seam under test needs none of it).
    c = _Client.__new__(_Client)
    c.invalid = 0
    c._invalid_decision_indices = []
    c._last_choice_decision_index = {}
    c._request_seq = 0
    return c


def test_gauntlet_stats_records_the_decision_index_of_each_hero_invalid_choice():
    c = _client()
    c._last_choice_decision_index["battle-x"] = 7   # the choice sent for decision 7
    c._note_invalid_choice("battle-x")
    assert c._invalid_decision_indices == [7]


def test_the_recorded_index_is_the_rejected_choice_not_the_advanced_counter():
    c = _client()
    c._last_choice_decision_index["battle-x"] = 7   # sent at decision 7
    c._request_seq = 8                               # the shared counter has since advanced (retry)
    c._note_invalid_choice("battle-x")
    assert c._invalid_decision_indices == [7]        # the SENT index, not the advanced 8


def test_an_opponent_invalid_choice_is_not_recorded_for_the_hero():
    hero, villain = _client(), _client()
    villain._last_choice_decision_index["battle-x"] = 3
    villain._note_invalid_choice("battle-x")         # only the OPPONENT erred
    stats = GauntletStats()
    stats.invalid_choices = hero.invalid + villain.invalid           # the summed count
    stats.hero_invalid_decision_indices = tuple(hero._invalid_decision_indices)
    assert stats.invalid_choices == 1
    assert stats.hero_invalid_decision_indices == ()                 # hero seat recorded nothing


def test_an_unattributable_error_records_a_fail_closed_sentinel():
    c = _client()
    c._note_invalid_choice("battle-unknown")         # no send-time index for this room
    assert c._invalid_decision_indices == [-1]


def test_the_closed_t2_result_row_and_writer_are_untouched():
    # The seam rides GauntletStats, never the closed T2 row: the writer allowlist has no such key.
    assert "hero_invalid_decision_indices" not in (REQUIRED_FIELDS | NULLABLE_FIELDS)
    # And GauntletStats DOES carry the new in-memory field (defaulted).
    assert GauntletStats().hero_invalid_decision_indices == ()

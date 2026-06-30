from __future__ import annotations

from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.belief.tracker import BeliefTracker
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.log_parser import parse_log
from showdown_bot.engine.state import BattleState, to_id

LOG = """\
|switch|p1a: Incineroar|Incineroar, L50, F|150/150
|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|move|p2a: Flutter Mane|Moonblast|p1a: Incineroar
|-damage|p1a: Incineroar|96/150
|-enditem|p2a: Flutter Mane|Booster Energy
"""


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def test_tracker_learns_move_and_item():
    book = _book()
    tracker = BeliefTracker.from_state(BattleState(), book)
    tracker.feed(parse_log(LOG))

    opp = tracker.hypotheses_for("p2")["a"]
    assert to_id("Moonblast") in opp.known_moves
    # Item revealed via |-enditem| -> fixed and candidate list collapses.
    assert opp.item_known is True
    assert opp.item_candidates("offense") == []


def test_tracker_records_move_order_for_speed():
    book = _book()
    tracker = BeliefTracker.from_state(BattleState(), book)
    tracker.feed(parse_log(LOG))
    assert ("p2", "a") in tracker.speed_observations


def test_tracker_resyncs_on_switch():
    book = _book()
    tracker = BeliefTracker.from_state(BattleState(), book)
    tracker.feed(parse_log(LOG))
    # A switch into the same slot replaces the hypothesis species.
    tracker.feed(parse_log("|switch|p2a: Amoonguss|Amoonguss, L50, F|100/100"))
    assert tracker.hypotheses_for("p2")["a"].species == "Amoonguss"

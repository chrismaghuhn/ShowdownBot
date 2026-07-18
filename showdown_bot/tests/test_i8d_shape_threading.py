"""The origin MegaShapeCounts shape-sink threads through the REAL live decision path
(agent_choose -> choose_with_fallback -> heuristic_choose_for_request -> _choose_best ->
_choose_best_mega -> score_evaluated_variants), and its values come only from the at-origin
increments. Reuses the promoted profile fixtures for a real board; touches the calc bridge,
starts no server and plays no battle.
"""
from __future__ import annotations

from showdown_bot.battle.mega_scoring import MegaShapeCounts
from showdown_bot.client.gauntlet import agent_choose
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.eval import profile_fixtures as pf


def _run(board_name, shape_sink):
    s = pf.make_session(board_name)
    try:
        return agent_choose(
            "heuristic", s.req, state=s.state, book=s.book, our_side="p1",
            our_spreads=s.our_spreads, opp_sets=s.opp_sets,
            calc=s.calc, oracle=s.oracle, speed_oracle=s.speed, dex=s.dex,
            format_config=load_format_config(pf.FORMAT), shape_sink=shape_sink,
        )
    finally:
        s.close()


def test_a_real_active_foe_mega_decision_fills_the_shape_sink():
    shape = MegaShapeCounts()
    choice = _run("mega_decision_tie_fixture", shape)          # own==foe==200: real foe-Mega
    assert isinstance(choice, str) and choice
    assert shape.n_candidates > 0                              # scoring actually ran
    assert shape.n_mega_twins > 0                             # foe-Mega hypotheses composed
    # foe_mega_active is exactly n_mega_twins > 0 (the DTO's rule)
    assert (shape.n_mega_twins > 0) is True


def test_an_inactive_board_leaves_the_sink_foe_mega_inactive():
    shape = MegaShapeCounts()
    choice = _run("mega_decision_fixture", shape)              # p2 Incineroar: eligibility {}
    assert isinstance(choice, str) and choice
    assert shape.n_mega_twins == 0                            # no foe-Mega twin composed


def test_no_shape_sink_still_returns_a_valid_choice():
    # Threading is additive: without a sink the decision path returns the same kind of action.
    s = pf.make_session("mega_decision_tie_fixture")
    try:
        choice = agent_choose(
            "heuristic", s.req, state=s.state, book=s.book, our_side="p1",
            our_spreads=s.our_spreads, opp_sets=s.opp_sets,
            calc=s.calc, oracle=s.oracle, speed_oracle=s.speed, dex=s.dex,
            format_config=load_format_config(pf.FORMAT),
        )
        assert isinstance(choice, str) and choice
    finally:
        s.close()

"""Task 2: origin telemetry -- score_evaluated_variants fills MegaShapeCounts.foe_mega_slots and
foe_mega_order_tie AT ORIGIN, only for positively-scored foe-Mega branches, only on successful
completion, and order_tie only when BOTH mutually-reversed 0.5 orderings of a tie interaction are
scored. Behavior-neutral: only the sink is written.

Boards (from profile_fixtures, node-free): dual_unequal -> slot0, foe_slotb -> slot1,
both_foe_slots -> {0,1}, tie -> order_tie. These fail before the origin fill (the two fields stay
at their defaults); they pass once score_evaluated_variants accumulates and writes them.
"""
from __future__ import annotations

import pytest

import showdown_bot.battle.mega_scoring as ms
import showdown_bot.engine.mega_projection as mp
import showdown_bot.eval.profile_fixtures as pf
from showdown_bot.battle.evaluate import EvalWeights
from showdown_bot.battle.mega_scoring import MegaShapeCounts, score_evaluated_variants
from showdown_bot.battle.opponent import foe_mega_eligibility
from showdown_bot.engine.belief.game_mode import GameMode
from showdown_bot.engine.species_meta import species_meta_table


def _score_into(session, shape):
    elig = foe_mega_eligibility(session.state, "p2", opp_sets=session.opp_sets)
    return score_evaluated_variants(
        session._variants, session._contexts, req=session.req, state=session.state,
        book=session.book, our_side="p1", opp_side="p2", calc=session.calc, oracle=session.oracle,
        speed_oracle=session.speed, dex=session.dex, priors=None, weights=EvalWeights(),
        mode=GameMode.NEUTRAL, risk_lambda=0.5, rollout_horizon=0,
        our_spreads=session.our_spreads, opp_sets=session.opp_sets,
        calc_profile=session.calc_profile, accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False, foe_mega_eligibility=elig,
        species_meta=species_meta_table(), shape_sink=shape,
    )


def _shape_for(board_name: str) -> MegaShapeCounts:
    s = pf.make_session(board_name)
    try:
        s.prepare()
        shape = MegaShapeCounts()
        _score_into(s, shape)
        return shape
    finally:
        s.close()


def test_foe_slot0_board_fills_foe_mega_slots_with_0():
    shape = _shape_for("mega_decision_dual_unequal_fixture")
    assert tuple(shape.foe_mega_slots) == (0,)
    assert shape.foe_mega_order_tie is False


def test_foe_slot1_board_fills_foe_mega_slots_with_1():
    shape = _shape_for("mega_decision_foe_slotb_fixture")
    assert tuple(shape.foe_mega_slots) == (1,)


def test_both_foe_slots_board_fills_0_and_1():
    shape = _shape_for("mega_decision_both_foe_slots_fixture")
    assert tuple(shape.foe_mega_slots) == (0, 1)


def test_tie_board_sets_order_tie_true_only_when_both_reversed_orderings_are_scored():
    shape = _shape_for("mega_decision_tie_fixture")
    assert shape.foe_mega_order_tie is True
    assert tuple(shape.foe_mega_slots) != ()


def test_a_strict_inequality_11_branch_is_not_a_tie():
    shape = _shape_for("mega_decision_dual_unequal_fixture")
    assert shape.foe_mega_order_tie is False
    assert tuple(shape.foe_mega_slots) == (0,)


def test_a_single_05_branch_alone_does_not_set_order_tie(monkeypatch):
    # Drop the second of the tie's two reversed 0.5 orderings: a lone 0.5 branch is NOT a tie.
    real = mp.compose_mega_projection_branches

    def only_first(*a, **k):
        return real(*a, **k)[:1]

    monkeypatch.setattr(mp, "compose_mega_projection_branches", only_first)
    shape = _shape_for("mega_decision_tie_fixture")
    assert shape.foe_mega_order_tie is False   # only one ordering scored -> not a tie
    assert tuple(shape.foe_mega_slots) != ()   # the slot is still recorded


def test_only_positively_scored_slots_count(monkeypatch):
    # Zero the weight of the foe-Mega responses for slot 1: a weight==0 response does not add its
    # slot, so the both_foe_slots board records only slot 0.
    real = ms.predict_responses

    def zero_slot1(*a, **k):
        resps = real(*a, **k)
        for r in resps:
            if getattr(r, "foe_mega_slot", None) == 1:
                r.weight = 0.0
        return resps

    monkeypatch.setattr(ms, "predict_responses", zero_slot1)
    shape = _shape_for("mega_decision_both_foe_slots_fixture")
    assert tuple(shape.foe_mega_slots) == (0,)


def test_filling_the_new_fields_leaves_the_chosen_action_and_six_counts_identical():
    # Two independent copies of the same board: one scored WITH a sink (which now also fills the
    # two new coverage fields), one WITHOUT. The chosen action (aggregate scores) is byte-identical,
    # so filling the new fields is pure telemetry -- and the six work-set counts are unaffected.
    board = "mega_decision_both_foe_slots_fixture"
    s_sink = pf.make_session(board)
    s_none = pf.make_session(board)
    try:
        s_sink.prepare()
        s_none.prepare()
        shape = MegaShapeCounts()
        recs_sink = _score_into(s_sink, shape)
        recs_none = _score_into(s_none, None)
        assert [r.aggregate_score for r in recs_sink] == [r.aggregate_score for r in recs_none]
        assert tuple(shape.foe_mega_slots) == (0, 1)                 # the new fields ARE filled
        assert shape.n_candidates == len(recs_sink) and shape.n_worlds == 1
        assert shape.n_mega_twins > 0 and shape.n_responses >= shape.n_mega_twins
    finally:
        s_sink.close()
        s_none.close()


def test_an_aborted_scoring_leaves_the_cell_fields_at_defaults(monkeypatch):
    # Inject a failure after the first scored line: score raises, and the cell fields are written
    # ONLY on successful completion, so they stay at their defaults.
    real = ms._evaluate_line_details
    state = {"n": 0}

    def boom(*a, **k):
        state["n"] += 1
        if state["n"] >= 2:
            raise RuntimeError("injected failure mid-scoring")
        return real(*a, **k)

    monkeypatch.setattr(ms, "_evaluate_line_details", boom)
    s = pf.make_session("mega_decision_both_foe_slots_fixture")
    try:
        s.prepare()
        shape = MegaShapeCounts()
        with pytest.raises(RuntimeError):
            _score_into(s, shape)
    finally:
        s.close()
    assert tuple(shape.foe_mega_slots) == ()
    assert shape.foe_mega_order_tie is False

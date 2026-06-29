from __future__ import annotations

from showdown_bot.battle.evaluate import (
    EvalWeights,
    score_outcome,
    score_outcome_with_breakdown,
)
from showdown_bot.battle.resolve import (
    ProtectedHit,
    TurnOutcome,
)


def test_total_score_equals_scalar_score_outcome():
    oc = TurnOutcome(
        hp_delta={("p2", "a"): -40, ("p1", "a"): -20},
        my_kos=0,
        my_faints=0,
    )
    w = EvalWeights()
    score, bd = score_outcome_with_breakdown(oc, "p1", w)
    assert bd.total_score == score
    assert score == score_outcome(oc, "p1", w)


def test_breakdown_damage_split():
    oc = TurnOutcome(
        hp_delta={("p2", "a"): -40, ("p1", "a"): -20},
        my_kos=0,
        my_faints=0,
    )
    _, bd = score_outcome_with_breakdown(oc, "p1", EvalWeights())
    assert bd.predicted_outgoing_damage == 40
    assert bd.predicted_incoming_damage == 20


def test_breakdown_protect_stall_penalty():
    oc = TurnOutcome(
        hp_delta={},
        my_kos=0,
        my_faints=0,
        flags={"protect:p1a"},
    )
    w = EvalWeights()
    _, bd = score_outcome_with_breakdown(oc, "p1", w)
    assert bd.protect_stall_penalty == w.protect_stall
    assert bd.partner_abandon_penalty == 0.0

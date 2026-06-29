from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown


def test_dtos_construct_with_defaults():
    dt = DecisionTrace()
    assert dt.candidates == [] and dt.opponent_responses == []
    ct = CandidateTrace(candidate_id="x", joint_action=None, rank=0,
                        aggregate_score=1.0, score_vector=[1.0],
                        outcome_breakdowns=[OutcomeBreakdown()],
                        aggregate_breakdown=OutcomeBreakdown())
    assert ct.candidate_id == "x" and ct.rank == 0

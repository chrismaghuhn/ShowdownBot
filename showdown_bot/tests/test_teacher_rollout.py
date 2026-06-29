import pytest

from showdown_bot.learning.teacher import RolloutConfig, counterfactual_value


def _fakes(rewards_by_turn, leaf_value):
    """resolve/decide/leaf fakes. State is just an int turn counter; each turn's
    transition_reward is rewards_by_turn[turn]. decide returns a dummy action."""
    def decide(state, side):
        return ("dummy", side)

    def resolve(state, our_action, opp_action):
        turn = state
        return turn + 1, rewards_by_turn[turn]

    def leaf(state):
        return leaf_value

    return decide, resolve, leaf


def test_h0_no_leaf_equals_one_ply_aggregate():
    decide, resolve, leaf = _fakes({0: 2.0}, leaf_value=99.0)
    cfg = RolloutConfig(H=0, gamma=0.75, use_leaf=False)
    v = counterfactual_value(
        start_state=0, candidate="c", responses=[("r1", 0.25), ("r2", 0.75)],
        decide=decide, resolve=resolve, leaf=leaf, cfg=cfg,
    )
    assert v == 2.0  # one-ply aggregate, no leaf, no follow-ups


def test_return_formula_no_double_count():
    # H=2 follow-ups; rewards r0=1, r1=2, r2=3; leaf=10; gamma=0.5
    # v = 1 + 0.5*2 + 0.25*3 + 0.5^3 * 10 = 1 + 1 + 0.75 + 1.25 = 4.0
    decide, resolve, leaf = _fakes({0: 1.0, 1: 2.0, 2: 3.0}, leaf_value=10.0)
    cfg = RolloutConfig(H=2, gamma=0.5, use_leaf=True)
    v = counterfactual_value(
        start_state=0, candidate="c", responses=[("r", 1.0)],
        decide=decide, resolve=resolve, leaf=leaf, cfg=cfg,
    )
    assert abs(v - 4.0) < 1e-9


def test_response_weights_are_applied():
    # responses give DIFFERENT rewards, so a teacher that ignored weights would fail
    def decide(state, side):
        return ("dummy", side)

    def resolve(state, our_action, opp_action):
        return state + 1, (2.0 if opp_action == "r1" else 6.0)

    def leaf(state):
        return 0.0

    cfg = RolloutConfig(H=0, gamma=0.75, use_leaf=False)
    v = counterfactual_value(
        start_state=0, candidate="c", responses=[("r1", 0.25), ("r2", 0.75)],
        decide=decide, resolve=resolve, leaf=leaf, cfg=cfg,
    )
    assert abs(v - 5.0) < 1e-9  # 0.25*2 + 0.75*6


def test_rejects_empty_responses():
    decide, resolve, leaf = _fakes({0: 1.0}, leaf_value=0.0)
    cfg = RolloutConfig(H=0, use_leaf=False)
    with pytest.raises(ValueError, match="empty"):
        counterfactual_value(start_state=0, candidate="c", responses=[],
                             decide=decide, resolve=resolve, leaf=leaf, cfg=cfg)


def test_rejects_weights_not_summing_to_one():
    decide, resolve, leaf = _fakes({0: 1.0}, leaf_value=0.0)
    cfg = RolloutConfig(H=0, use_leaf=False)
    with pytest.raises(ValueError, match="sum to 1"):
        counterfactual_value(start_state=0, candidate="c", responses=[("r1", 0.3), ("r2", 0.3)],
                             decide=decide, resolve=resolve, leaf=leaf, cfg=cfg)


def test_rejects_negative_weight():
    decide, resolve, leaf = _fakes({0: 1.0}, leaf_value=0.0)
    cfg = RolloutConfig(H=0, use_leaf=False)
    with pytest.raises(ValueError, match="non-negative"):
        counterfactual_value(start_state=0, candidate="c", responses=[("r1", 1.3), ("r2", -0.3)],
                             decide=decide, resolve=resolve, leaf=leaf, cfg=cfg)


def test_rollout_config_rejects_invalid_values():
    with pytest.raises(ValueError, match="H must be"):
        RolloutConfig(H=-1)
    with pytest.raises(ValueError, match="gamma must be"):
        RolloutConfig(gamma=0)
    with pytest.raises(ValueError, match="top_k must be"):
        RolloutConfig(top_k=0)


def test_label_decision_normalizes_and_flags_disagreement():
    from showdown_bot.learning.teacher import label_decision
    teacher_values = {"A": 1.0, "B": 3.0, "C": 2.0}   # teacher prefers B
    heuristic_values = {"A": 5.0, "B": 1.0, "C": 2.0}  # heuristic prefers A
    out = label_decision(teacher_values, heuristic_values, heuristic_choice_id="A")

    assert out["B"]["teacher_best"] is True
    assert out["A"]["teacher_best"] is False
    assert out["A"]["chosen_by_current_heuristic"] is True
    assert out["B"]["chosen_by_current_heuristic"] is False
    # within-decision normalization: value - mean(2.0)
    assert abs(out["B"]["counterfactual_value_normalized_within_decision"] - 1.0) < 1e-9
    assert abs(out["A"]["value_gap_to_best"] - (1.0 - 3.0)) < 1e-9
    # ranks (0 = best) differ: teacher ranks B first, heuristic ranks A first
    assert out["B"]["teacher_rank"] == 0
    assert out["A"]["heuristic_rank"] == 0
    assert out["A"]["teacher_rank"] != 0


def test_label_decision_tie_break_is_consistent():
    # tied teacher values: teacher_rank==0 and teacher_best MUST point at the same id
    from showdown_bot.learning.teacher import label_decision
    out = label_decision({"A": 1.0, "B": 1.0}, {"A": 0.0, "B": 0.0}, "A")
    assert out["A"]["teacher_rank"] == 0
    assert out["A"]["teacher_best"] is True
    assert out["B"]["teacher_best"] is False


def test_label_decision_requires_same_candidate_sets():
    from showdown_bot.learning.teacher import label_decision
    with pytest.raises(ValueError, match="same candidates"):
        label_decision({"A": 1.0}, {"A": 1.0, "B": 2.0}, "A")


def test_label_decision_requires_choice_in_candidates():
    from showdown_bot.learning.teacher import label_decision
    with pytest.raises(ValueError, match="must be one of"):
        label_decision({"A": 1.0, "B": 2.0}, {"A": 1.0, "B": 2.0}, "Z")


def test_label_decision_rejects_empty_values():
    from showdown_bot.learning.teacher import label_decision
    with pytest.raises(ValueError, match="empty"):
        label_decision({}, {}, "A")

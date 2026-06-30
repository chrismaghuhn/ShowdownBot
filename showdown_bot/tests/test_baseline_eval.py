# tests/test_baseline_eval.py
from showdown_bot.learning.dataset import group_decisions
from showdown_bot.learning.baseline_eval import evaluate_baseline, BaselineMetrics


def _r(game, dec, idx, **lbl):
    base = {"teacher_best": False, "chosen_by_current_heuristic": False,
            "value_gap_to_best": -1.0}
    base.update(lbl)
    return {"features": {"slot1_move_id": "tackle", "slot1_action_type": "move"},
            "metadata": {"game_id": game, "decision_id": dec, "candidate_index": idx},
            "label": base}


def test_agreement_counts_topset_and_strict():
    # A: heuristic-chosen IS teacher_best (agree)
    A = [_r("g", "A", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "A", 1, value_gap_to_best=-2.0)]
    # B: heuristic-chosen is NOT teacher_best, gap -0.3 -> near-equal-safe miss
    B = [_r("g", "B", 0, teacher_best=True, value_gap_to_best=0.0),
         _r("g", "B", 1, chosen_by_current_heuristic=True, value_gap_to_best=-0.3)]
    m = evaluate_baseline(group_decisions(A + B))
    assert m.multi_decisions == 2
    assert m.agree_topset == 1 and m.agree_topset_total == 2          # 50%
    assert m.wrong_but_near_equal == 1                               # B is a cheap miss
    assert m.mean_regret == 0.15                                     # (0.0 + 0.3)/2
    assert m.override_opportunity == 1                               # B: chosen != best


def test_tie_decision_excluded_from_strict_but_in_topset():
    T = [_r("g", "T", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "T", 1, teacher_best=True, value_gap_to_best=0.0),
         _r("g", "T", 2, value_gap_to_best=-1.0)]
    m = evaluate_baseline(group_decisions(T))
    assert m.ties == 1
    assert m.agree_topset == 1                  # chosen in teacher-best set
    assert m.strict_total == 0                  # tie excluded from unique-strict


def test_zero_gap_nonbest_flagged():
    Z = [_r("g", "Z", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "Z", 1, value_gap_to_best=0.0),   # equal value, not marked best
         _r("g", "Z", 2, value_gap_to_best=-5.0)]
    m = evaluate_baseline(group_decisions(Z))
    assert m.zero_gap_nonbest_decisions == 1


def test_format_report_runs():
    A = [_r("g", "A", 0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g", "A", 1, value_gap_to_best=-2.0)]
    from showdown_bot.learning.baseline_eval import format_report
    text = format_report(evaluate_baseline(group_decisions(A)))
    assert "Baseline Evaluation Report" in text and "joint-action class" in text

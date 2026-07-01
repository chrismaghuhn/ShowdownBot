# tests/test_reranker_eval.py
from showdown_bot.learning.dataset import group_decisions
from showdown_bot.learning.reranker_eval import regret_metrics, format_report, RerankerMetrics

def _dec(gaps, chosen_idx, scores, attack=True):
    move = "moonblast" if attack else "protect"
    rows = []
    for i, gap in enumerate(gaps):
        rows.append({
            "features": {"slot1_move_id": move, "slot1_action_type": "move",
                         "slot1_is_switch": False, "slot2_action_type": "pass",
                         "slot2_move_id": "__none__"},
            "metadata": {"game_id": "g", "decision_id": "g-d", "candidate_index": i},
            "label": {"teacher_best": gap == 0.0, "chosen_by_current_heuristic": i == chosen_idx,
                      "value_gap_to_best": gap},
        })
    return group_decisions(rows)[0], scores

def test_regret_model_beats_heuristic():
    # heuristic chose idx1 (gap -0.3); model scores rank idx0 (gap 0) top
    d, scores = _dec([0.0, -0.3, -2.0], chosen_idx=1, scores=[9.0, 1.0, 0.0])
    m = regret_metrics([(d, scores)])
    assert m.heuristic_regret == 0.3
    assert m.model_regret == 0.0          # model picked the best
    assert m.model_regret < m.heuristic_regret

def test_format_report_has_mandatory_lower_bound_and_nowin_lines():
    d, scores = _dec([0.0, -0.3], chosen_idx=0, scores=[0.0, 9.0])  # model WORSE than heuristic
    m = regret_metrics([(d, scores)])
    text = format_report(m)
    assert "lower-bound experiment, not a final judgment" in text
    assert "NOT NO-GO for the reranker architecture" in text

# tests/test_dataset.py
import pytest
from showdown_bot.learning.dataset import (
    load_rows, group_decisions, action_class, Decision,
)

def _row(game, dec, idx, *, move_id="tackle", action_type="move",
         teacher_best=False, chosen=False, gap=-1.0):
    # minimal row; only the fields the loader/grouping/classifier read need values.
    return {
        "features": {"slot1_move_id": move_id, "slot1_action_type": action_type},
        "metadata": {"game_id": game, "decision_id": dec, "candidate_index": idx},
        "label": {"teacher_best": teacher_best,
                  "chosen_by_current_heuristic": chosen,
                  "value_gap_to_best": gap},
    }

def test_group_by_game_then_decision_sorts_by_candidate_index():
    rows = [_row("g1", "d1", 2), _row("g1", "d1", 0), _row("g1", "d1", 1)]
    decs = group_decisions(rows)
    assert len(decs) == 1
    assert [r["metadata"]["candidate_index"] for r in decs[0].rows] == [0, 1, 2]

def test_same_decision_id_in_two_games_stays_separate():
    rows = [_row("g1", "dX", 0), _row("g2", "dX", 0)]
    decs = group_decisions(rows)
    assert len(decs) == 2  # keyed by (game_id, decision_id), no collision

def test_decision_helpers_chosen_and_teacher_best_and_ties():
    # idx1 is a real teacher TIE (teacher_best, gap 0); idx2 is a real
    # zero-gap-NONbest (not teacher_best, gap 0). The two must be distinguished.
    rows = [_row("g", "d", 0, teacher_best=True, chosen=True, gap=0.0),
            _row("g", "d", 1, teacher_best=True, gap=0.0),    # teacher tie at best
            _row("g", "d", 2, teacher_best=False, gap=0.0),   # zero-gap but NOT best
            _row("g", "d", 3, gap=-3.0)]
    d = group_decisions(rows)[0]
    assert d.is_multi_candidate
    assert d.chosen_row()["metadata"]["candidate_index"] == 0
    assert len(d.teacher_best_rows()) == 2          # tie counted, not collapsed
    assert d.is_tie                                  # >1 teacher_best
    assert d.zero_gap_nonbest_count() == 1           # only idx2 (best rows excluded)

def test_action_class_single_slot():
    assert action_class(_row("g","d",0, move_id="protect")) == "protect"
    assert action_class(_row("g","d",0, move_id="tackle")) == "attack"
    assert action_class(_row("g","d",0, action_type="switch", move_id="")) == "switch"
    assert action_class(_row("g","d",0, move_id="tailwind")) == "status"

def _joint(slot1_move, slot2_move):
    row = _row("g", "d", 0, move_id=slot1_move)
    row["features"]["slot2_action_type"] = "move"
    row["features"]["slot2_move_id"] = slot2_move
    return row

def test_joint_action_class_double_protect_is_protect():
    assert action_class(_joint("protect", "protect")) == "protect"

def test_joint_action_class_protect_plus_attack_is_attack():
    assert action_class(_joint("protect", "moonblast")) == "attack"

def test_joint_action_class_attack_plus_protect_is_attack():
    assert action_class(_joint("flareblitz", "protect")) == "attack"

def test_action_class_strict_raises_on_unknown_move():
    with pytest.raises(ValueError):
        action_class(_row("g","d",0, move_id="not_a_real_move_xyz"), strict=True)

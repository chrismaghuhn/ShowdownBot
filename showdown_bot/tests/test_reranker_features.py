# tests/test_reranker_features.py
import pytest
from showdown_bot.learning.dataset import group_decisions
from showdown_bot.learning.reranker_features import (
    build_feature_matrix, relevance_from_gap, active_feature_names,
    feature_schema_hash, LABEL_DENYLIST, METADATA_DENYLIST,
)

def _row(game, dec, idx, *, move="tackle", atype="move", mode="NORMAL",
         best=False, chosen=False, gap=-1.0, score=0.0):
    return {
        "features": {"slot1_move_id": move, "slot1_action_type": atype,
                     "game_mode": mode, "heuristic_aggregate_score": score,
                     "turn_number": 1, "endgame_flag": False},
        "metadata": {"game_id": game, "decision_id": dec, "candidate_index": idx},
        "label": {"teacher_best": best, "chosen_by_current_heuristic": chosen,
                  "value_gap_to_best": gap},
    }

def test_relevance_bucketing():
    assert relevance_from_gap(0.0) == 4
    assert relevance_from_gap(-0.5) == 3
    assert relevance_from_gap(-0.4) == 3
    assert relevance_from_gap(-2.0) == 2
    assert relevance_from_gap(-5.0) == 1
    assert relevance_from_gap(-5.0001) == 0

def test_active_features_drops_constant_and_denied():
    rows = [_row("g", "d", 0, score=1.0), _row("g", "d", 1, score=2.0)]
    decs = group_decisions(rows)
    active = active_feature_names(decs)
    assert "heuristic_aggregate_score" in active   # varies -> kept
    assert "turn_number" not in active             # constant here -> dropped
    assert "endgame_flag" not in active            # constant here -> dropped
    assert not (set(active) & (LABEL_DENYLIST | METADATA_DENYLIST))

def test_build_matrix_groups_relevance_and_decision_keys():
    rows = [_row("g1", "d1", 0, best=True, chosen=True, gap=0.0, score=5.0),
            _row("g1", "d1", 1, gap=-3.0, score=2.0),
            _row("g2", "d2", 0, best=True, chosen=True, gap=0.0, score=4.0),
            _row("g2", "d2", 1, gap=-0.3, score=3.0)]
    m = build_feature_matrix(group_decisions(rows))
    assert m.group_sizes == [2, 2]
    assert sum(m.group_sizes) == len(m.X)
    assert m.relevance == [4, 1, 4, 3]
    assert m.decision_keys == [("g1", "d1"), ("g2", "d2")]

def test_categorical_detection_includes_strings():
    rows = [_row("g", "d", 0, move="tackle", mode="NORMAL"),
            _row("g", "d", 1, move="protect", mode="MUST_REACT")]
    m = build_feature_matrix(group_decisions(rows))
    assert "slot1_move_id" in m.categorical_feature_names
    assert "game_mode" in m.categorical_feature_names
    assert "heuristic_aggregate_score" not in m.categorical_feature_names
    assert all(isinstance(v, float) for row in m.X for v in row)

def test_reranker_features_rejects_label_leakage():
    rows = [_row("g", "d", 0, chosen=True, best=True, gap=0.0), _row("g", "d", 1, gap=-2.0)]
    decs = group_decisions(rows)
    for bad in ["teacher_best", "teacher_rank", "heuristic_rank", "value_gap_to_best",
                "counterfactual_value_raw", "game_id", "decision_id"]:
        with pytest.raises(ValueError):
            build_feature_matrix(decs, feature_names=["heuristic_aggregate_score", bad])

def test_rejects_non_schema_feature_column():
    rows = [_row("g", "d", 0, chosen=True, best=True, gap=0.0), _row("g", "d", 1, gap=-2.0)]
    with pytest.raises(ValueError):
        build_feature_matrix(group_decisions(rows),
                             feature_names=["heuristic_aggregate_score", "not_in_schema"])

def test_provided_encodings_force_categorical_on_val_even_if_autodetect_differs():
    train = group_decisions([_row("g", "d", 0, mode="NORMAL"), _row("g", "d", 1, mode="MUST_REACT")])
    feat = ["game_mode", "heuristic_aggregate_score"]
    tm = build_feature_matrix(train, feature_names=feat)
    assert "game_mode" in tm.categorical_feature_names
    val = group_decisions([_row("v", "d", 0, mode="NORMAL"), _row("v", "d", 1, mode="NORMAL")])
    vm = build_feature_matrix(val, feature_names=feat, encodings=tm.categorical_encodings)
    assert "game_mode" in vm.categorical_feature_names
    unseen = group_decisions([_row("v", "d", 0, mode="ENDGAME"), _row("v", "d", 1, mode="ENDGAME")])
    um = build_feature_matrix(unseen, feature_names=feat, encodings=tm.categorical_encodings)
    gm_col = um.feature_names.index("game_mode")
    assert um.X[0][gm_col] == 0.0

def test_feature_schema_hash_stable_and_order_sensitive():
    a = feature_schema_hash(["x", "y"], ["x"])
    assert a == feature_schema_hash(["x", "y"], ["x"])
    assert a != feature_schema_hash(["y", "x"], ["x"])

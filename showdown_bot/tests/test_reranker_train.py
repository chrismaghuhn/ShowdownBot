# tests/test_reranker_train.py
import json
import numpy as np
import pytest
lgb = pytest.importorskip("lightgbm")
from showdown_bot.learning.dataset import group_decisions
from showdown_bot.learning.reranker_features import build_feature_matrix
from showdown_bot.learning.reranker_train import train_lambdarank, build_manifest, DEFAULT_CONFIG

def _decs(n=40):
    rows = []
    for g in range(n):
        best_gap = [0.0, -0.3, -3.0, -8.0]
        for i, gap in enumerate(best_gap):
            rows.append({
                "features": {"slot1_move_id": "tackle" if i % 2 else "moonblast",
                             "game_mode": "NORMAL", "heuristic_aggregate_score": 5.0 - i,
                             "predicted_outgoing_damage": 50.0 - 5 * i},
                "metadata": {"game_id": f"g{g}", "decision_id": f"g{g}-d", "candidate_index": i},
                "label": {"teacher_best": i == 0, "chosen_by_current_heuristic": i == 0,
                          "value_gap_to_best": gap},
            })
    return group_decisions(rows)

def test_train_returns_booster_and_predicts_per_candidate():
    m = build_feature_matrix(_decs())
    booster = train_lambdarank(m, config=DEFAULT_CONFIG)
    preds = booster.predict(np.array(m.X, dtype=float))
    assert len(preds) == len(m.X)

def test_manifest_has_all_required_fields():
    m = build_feature_matrix(_decs())
    booster = train_lambdarank(m, config=DEFAULT_CONFIG)
    man = build_manifest(matrix=m, config=DEFAULT_CONFIG, dataset_sha256="deadbeef",
                         dropped_constant_columns=["turn_number"],
                         training_decision_filter="test", metrics_summary={"model_regret": 1.0},
                         eval_report_path="reports/x.md", model_type="lightgbm-lambdarank",
                         split_seed=42)
    for k in ["dataset_sha256", "feature_schema_hash", "training_config_hash", "model_type",
              "split_seed", "metrics_summary", "git_sha", "eval_report_path", "feature_names",
              "categorical_feature_names", "categorical_encodings", "dropped_constant_columns",
              "denied_columns_checked", "training_decision_filter"]:
        assert k in man, f"manifest missing {k}"
    assert man["feature_names"] == m.feature_names
    assert man["model_type"] == "lightgbm-lambdarank"

def test_strict_and_attack_filters():
    from showdown_bot.learning.reranker_train import strict_decisions, attack_strict_decisions
    decs = _decs(3)          # each group: 1 teacher_best, 1 chosen, 4 candidates, chosen is moonblast (attack)
    s = strict_decisions(decs)
    assert len(s) == 3       # all are strict-unique multi
    a = attack_strict_decisions(decs)
    assert len(a) == 3       # chosen (idx0) move is moonblast -> attack

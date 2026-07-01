"""Slice 2b-2a: train a groupwise LightGBM LambdaRank reranker + write the
INV-7 model manifest. Offline only. Imports lightgbm/numpy (the [learning] extra).
The main() CLI + _scores_per_decision wiring are added in Task 4."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import lightgbm as lgb
import numpy as np

from showdown_bot.learning.dataset import action_class, group_decisions, load_rows, split_by_game
from showdown_bot.learning.reranker_features import (
    LABEL_DENYLIST, METADATA_DENYLIST, FeatureMatrix, active_feature_names,
    build_feature_matrix, feature_schema_hash,
)

EXPECTED_2B0_SHA256 = "62f156b1ed7ab406a5838761a0985909737a738f2cd621d383e3ec9dbc73e849"

DEFAULT_CONFIG = {
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "learning_rate": 0.05,
    "n_estimators": 300,
    "early_stopping_rounds": 30,
    "ndcg_eval_at": [1, 2],
}


def _cat_indices(matrix: FeatureMatrix) -> list[int]:
    return [matrix.feature_names.index(c) for c in matrix.categorical_feature_names]


def train_lambdarank(matrix: FeatureMatrix, *, config: dict, val_matrix: FeatureMatrix | None = None):
    """Train LightGBM lambdarank. Categorical columns are passed as categorical_feature
    (NOT ordinals). Relevance 0..4 uses LightGBM's default label_gain (2^r - 1)."""
    cat = _cat_indices(matrix)
    train_set = lgb.Dataset(np.array(matrix.X, dtype=float), label=np.array(matrix.relevance, dtype=int),
                            group=matrix.group_sizes, feature_name=matrix.feature_names,
                            categorical_feature=cat, free_raw_data=False)
    valid_sets, callbacks = [], []
    if val_matrix is not None:
        valid_sets = [lgb.Dataset(np.array(val_matrix.X, dtype=float),
                                  label=np.array(val_matrix.relevance, dtype=int),
                                  group=val_matrix.group_sizes, feature_name=val_matrix.feature_names,
                                  categorical_feature=cat, reference=train_set, free_raw_data=False)]
        callbacks = [lgb.early_stopping(config["early_stopping_rounds"], verbose=False)]
    params = {"objective": "lambdarank", "metric": "ndcg", "ndcg_eval_at": config["ndcg_eval_at"],
              "num_leaves": config["num_leaves"], "min_data_in_leaf": config["min_data_in_leaf"],
              "learning_rate": config["learning_rate"], "verbosity": -1}
    return lgb.train(params, train_set, num_boost_round=config["n_estimators"],
                     valid_sets=valid_sets, callbacks=callbacks)


def sha256_of_file(path: str) -> str:
    import gzip
    p = Path(path)
    data = gzip.open(p, "rb").read() if p.suffix == ".gz" else p.open("rb").read()
    return hashlib.sha256(data).hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def build_manifest(*, matrix, config, dataset_sha256, dropped_constant_columns,
                   training_decision_filter, metrics_summary, eval_report_path,
                   model_type, split_seed, split_counts=None) -> dict:
    cfg_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
    return {
        "dataset_sha256": dataset_sha256,
        "feature_schema_hash": feature_schema_hash(matrix.feature_names, matrix.categorical_feature_names),
        "training_config_hash": cfg_hash,
        "model_type": model_type,
        "split_seed": split_seed,
        "split_counts": split_counts or {},
        "metrics_summary": metrics_summary,
        "git_sha": _git_sha(),
        "eval_report_path": eval_report_path,
        "feature_names": matrix.feature_names,
        "categorical_feature_names": matrix.categorical_feature_names,
        "categorical_encodings": matrix.categorical_encodings,
        "dropped_constant_columns": dropped_constant_columns,
        "denied_columns_checked": sorted(LABEL_DENYLIST | METADATA_DENYLIST),
        "training_decision_filter": training_decision_filter,
    }


def strict_decisions(decisions) -> list:
    """Strict-unique set: multi-candidate AND exactly-1 teacher_best AND exactly-1
    chosen_by_current_heuristic. Explicit counts. ALL candidates of a qualifying
    decision are kept."""
    out = []
    for d in decisions:
        if len(d.rows) <= 1:
            continue
        if len(d.teacher_best_rows()) != 1:
            continue
        if len(d.chosen_rows()) != 1:
            continue
        out.append(d)
    return out


def attack_strict_decisions(decisions) -> list:
    """strict_decisions whose chosen heuristic joint-action class == 'attack'. We
    filter DECISIONS by the chosen class; we NEVER drop candidates inside a decision."""
    return [d for d in strict_decisions(decisions) if action_class(d.chosen_rows()[0]) == "attack"]

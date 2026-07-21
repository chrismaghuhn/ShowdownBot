import math

import pytest

from showdown_bot.learning.audit.contracts import AuditConfig, AuditCorpus, AuditError, Severity
from showdown_bot.learning.audit.model import (
    audit_model_artifacts, audit_optional_model, calibration_metrics, decision_nll,
    fit_temperature, softmax,
)
from showdown_bot.learning.dataset import Decision
from showdown_bot.learning.reranker_features import LABEL_DENYLIST, METADATA_DENYLIST, feature_schema_hash
from showdown_bot.learning.schema import FEATURE_COLUMNS


class StubModel:
    def __init__(self, feature_names, predictions):
        self._feature_names = list(feature_names)
        self.predictions = list(predictions)

    def feature_name(self):
        return list(self._feature_names)

    def predict(self, matrix):
        return list(self.predictions)


def _model_fixture():
    rows = []
    for index, score in enumerate((1.0, 0.0)):
        features = {key: 0.0 for key in FEATURE_COLUMNS}
        features["heuristic_aggregate_score"] = score
        rows.append({
            "features": features,
            "metadata": {"game_id": "g", "decision_id": "d", "candidate_index": index},
            "label": {"teacher_best": index == 0, "value_gap_to_best": -float(index),
                      "chosen_by_current_heuristic": index == 0},
        })
    decision = Decision("g", "d", rows)
    corpus = AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(decision.rows), decisions=(decision,),
        split_by_game={"g": "test"},
        decisions_by_split={"train": (decision,), "validation": (decision,), "test": (decision,)},
        split_manifest={})
    features = ["heuristic_aggregate_score"]
    model = StubModel(features, [1.0, 0.0])
    manifest = {
        "dataset_sha256": corpus.dataset_sha256,
        "feature_schema_hash": feature_schema_hash(features, []),
        "training_config_hash": "a" * 16, "model_type": "lightgbm-lambdarank",
        "split_seed": 42, "metrics_summary": {}, "git_sha": "a" * 40,
        "eval_report_path": "reports/test.md", "feature_names": features,
        "categorical_feature_names": [], "categorical_encodings": {},
        "dropped_constant_columns": sorted(
            feature for feature in FEATURE_COLUMNS
            if feature not in features and feature not in (LABEL_DENYLIST | METADATA_DENYLIST)),
        "denied_columns_checked": sorted(LABEL_DENYLIST | METADATA_DENYLIST),
        "training_decision_filter": "fixture",
    }
    return corpus, model, manifest


def test_manifest_mismatches_are_fail():
    corpus, model, manifest = _model_fixture()
    manifest["dataset_sha256"] = "0" * 64
    findings, _metrics = audit_model_artifacts(corpus, model, manifest, AuditConfig())
    assert any(f.code == "MODEL_DATASET_HASH_MISMATCH" and f.severity == Severity.FAIL
               for f in findings)


def test_predictions_must_be_deterministic_and_finite():
    corpus, model, manifest = _model_fixture()
    model.predictions = [float("nan"), 0.0]
    findings, _metrics = audit_model_artifacts(corpus, model, manifest, AuditConfig())
    assert any(f.code == "MODEL_NONFINITE_PREDICTION" for f in findings)


@pytest.mark.parametrize(("mutation", "code"), [
    (lambda _model, manifest: manifest.update(feature_schema_hash="bad"),
     "MODEL_FEATURE_SCHEMA_MISMATCH"),
    (lambda model, _manifest: setattr(model, "_feature_names", ["different"]),
     "MODEL_FEATURE_ORDER_MISMATCH"),
    (lambda _model, manifest: manifest.update(categorical_encodings={"x": {"seen": 1}}),
     "MODEL_ENCODING_INVALID"),
    (lambda _model, manifest: manifest.update(dropped_constant_columns=[]),
     "MODEL_DROPPED_CONSTANT_MISMATCH"),
])
def test_manifest_contract_failures(mutation, code):
    corpus, model, manifest = _model_fixture()
    mutation(model, manifest)
    findings, _metrics = audit_model_artifacts(corpus, model, manifest, AuditConfig())
    assert any(f.code == code and f.severity == Severity.FAIL for f in findings)


def test_only_one_model_artifact_is_fail(tmp_path):
    corpus, _model, _manifest = _model_fixture()
    findings, metrics = audit_optional_model(
        corpus, AuditConfig(), tmp_path / "model.txt", None, {})
    assert metrics["status"] == "unavailable"
    assert findings[0].code == "MODEL_ARTIFACT_PAIR_MISSING"


def test_temperature_uses_validation_only():
    validation = [{"scores": [2.0, 0.0], "teacher_best": [True, False],
                   "game_id": "g", "decision_id": "d"}]
    seen = []
    temperature = fit_temperature(validation, observer=seen.append)
    assert temperature > 0
    assert seen and all(item["split"] == "validation" for item in seen)


def test_calibration_metrics_handle_teacher_ties():
    scored = [{"scores": [2.0, 2.0, 0.0], "teacher_best": [True, True, False],
               "game_id": "g", "decision_id": "d"}]
    metrics = calibration_metrics(scored, temperature=1.0)
    assert metrics["n"] == 1
    assert math.isfinite(metrics["nll"])
    assert math.isfinite(metrics["brier"])


def test_empty_calibration_inputs_fail_closed():
    with pytest.raises(AuditError, match="at least one score"):
        softmax([], 1.0)
    with pytest.raises(AuditError, match="teacher_best"):
        decision_nll({"scores": [1.0], "teacher_best": [False]}, 1.0)
    with pytest.raises(AuditError, match="validation decisions"):
        fit_temperature([])
    with pytest.raises(AuditError, match="requires decisions"):
        calibration_metrics([], 1.0)

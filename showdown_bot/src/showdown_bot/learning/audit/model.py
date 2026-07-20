"""Model manifest, prediction and calibration auditing (Phase 3,
dataset-reranker-audit slice, Task 7). Validates a trained reranker's manifest
against the audited dataset and the frozen feature schema, checks that
predictions are deterministic and finite, fits a softmax temperature on the
validation split ONLY, and reports test-only calibration metrics (topset
accuracy, mean regret, NDCG@1/@2, NLL, multiclass Brier, ECE), including a
stratified ID/OOD breakdown. Offline/pure except for the optional lightgbm
Booster load in audit_optional_model. No network, no live battle imports.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from showdown_bot.learning.audit.contracts import (
    AuditConfig, AuditError, Finding, Severity, make_finding,
)
from showdown_bot.learning.reranker_features import (
    LABEL_DENYLIST, METADATA_DENYLIST, active_feature_names, build_feature_matrix,
    feature_schema_hash,
)
from showdown_bot.learning.schema import FEATURE_COLUMNS

REQUIRED_MANIFEST_KEYS = frozenset({
    "dataset_sha256", "feature_schema_hash", "training_config_hash", "model_type",
    "split_seed", "metrics_summary", "git_sha", "eval_report_path", "feature_names",
    "categorical_feature_names", "categorical_encodings", "dropped_constant_columns",
    "denied_columns_checked", "training_decision_filter",
})


def model_fail(code: str, examples) -> Finding:
    return make_finding(
        code=code, severity=Severity.FAIL, scope="model", message=code,
        count=max(1, len(examples)), examples=examples,
        remediation="rebuild model and manifest from the audited dataset",
    )


def model_warn(code: str, examples, evidence=None) -> Finding:
    return make_finding(
        code=code, severity=Severity.WARN, scope="model", message=code,
        count=max(1, len(examples)), examples=examples, evidence=evidence or {},
        remediation="inspect the historical evaluation provenance",
    )


def validate_manifest(corpus, model, manifest, train_decisions, manifest_base=None) -> list[Finding]:
    findings = []
    missing = REQUIRED_MANIFEST_KEYS - set(manifest)
    if missing:
        findings.append(model_fail("MODEL_MANIFEST_MISSING_KEYS", sorted(missing)))
        return findings
    if manifest["dataset_sha256"] != corpus.dataset_sha256:
        findings.append(model_fail("MODEL_DATASET_HASH_MISMATCH", []))
    if manifest["model_type"] != "lightgbm-lambdarank":
        findings.append(model_fail("MODEL_TYPE_MISMATCH", [manifest["model_type"]]))
    config_hash = str(manifest["training_config_hash"])
    if len(config_hash) < 16 or any(char not in "0123456789abcdef" for char in config_hash.lower()):
        findings.append(model_fail("MODEL_TRAINING_CONFIG_HASH_INVALID", [config_hash]))
    if not isinstance(manifest["metrics_summary"], dict):
        findings.append(model_fail("MODEL_METRICS_SUMMARY_INVALID", []))
    features = list(manifest["feature_names"])
    denied = set(features) & (LABEL_DENYLIST | METADATA_DENYLIST)
    if denied or not set(features) <= set(FEATURE_COLUMNS):
        findings.append(model_fail("MODEL_FEATURE_ALLOWLIST_MISMATCH", sorted(denied)))
    expected_hash = feature_schema_hash(features, manifest["categorical_feature_names"])
    if expected_hash != manifest["feature_schema_hash"]:
        findings.append(model_fail("MODEL_FEATURE_SCHEMA_MISMATCH", []))
    if list(model.feature_name()) != features:
        findings.append(model_fail("MODEL_FEATURE_ORDER_MISMATCH", []))
    encodings = manifest["categorical_encodings"]
    categoricals = list(manifest["categorical_feature_names"])
    train_feature_names = {name for decision in train_decisions
                           for row in decision.rows for name in row["features"]}
    if not set(features) <= train_feature_names:
        findings.append(model_fail("MODEL_FEATURE_MISSING_FROM_TRAIN",
                                   sorted(set(features) - train_feature_names)))
    encoding_invalid = set(encodings) != set(categoricals)
    for mapping in encodings.values():
        codes = list(mapping.values()) if isinstance(mapping, dict) else []
        encoding_invalid |= (
            not isinstance(mapping, dict) or mapping.get("__unk__") != 0
            or any(not isinstance(code, int) or code < 0 for code in codes)
            or len(codes) != len(set(codes))
        )
    if encoding_invalid or not set(categoricals) <= set(features):
        findings.append(model_fail("MODEL_ENCODING_INVALID", []))
    expected_denied = sorted(LABEL_DENYLIST | METADATA_DENYLIST)
    if sorted(manifest["denied_columns_checked"]) != expected_denied:
        findings.append(model_fail("MODEL_DENYLIST_ATTESTATION_MISMATCH", []))
    active = set(active_feature_names(train_decisions))
    actual_dropped = sorted(
        feature for feature in FEATURE_COLUMNS
        if feature not in active and feature not in (LABEL_DENYLIST | METADATA_DENYLIST))
    if sorted(manifest["dropped_constant_columns"]) != actual_dropped:
        findings.append(model_fail("MODEL_DROPPED_CONSTANT_MISMATCH", actual_dropped))
    if manifest_base is not None:
        report_path = Path(manifest_base) / manifest["eval_report_path"]
        if not report_path.exists():
            finding = (model_fail("MODEL_EVAL_REPORT_MISSING_WITH_HASH", [str(report_path)])
                       if "eval_report_sha256" in manifest
                       else model_warn("MODEL_EVAL_REPORT_MISSING", [str(report_path)]))
            findings.append(finding)
        elif "eval_report_sha256" in manifest:
            actual_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
            if actual_hash != manifest["eval_report_sha256"]:
                findings.append(model_fail("MODEL_EVAL_REPORT_HASH_MISMATCH", [str(report_path)]))
    return findings


def audit_model_artifacts(corpus, model, manifest, config: AuditConfig, manifest_base=None):
    findings = validate_manifest(
        corpus, model, manifest, corpus.decisions_by_split["train"], manifest_base)
    if any(f.severity == Severity.FAIL for f in findings):
        return findings, {"status": "not_scored_due_to_manifest_failure"}
    matrix = build_feature_matrix(
        corpus.decisions, feature_names=manifest["feature_names"],
        encodings=manifest["categorical_encodings"])
    first = list(model.predict(np.asarray(matrix.X, dtype=float)))
    second = list(model.predict(np.asarray(matrix.X, dtype=float)))
    if first != second:
        findings.append(model_fail("MODEL_NONDETERMINISTIC_PREDICTION", []))
    if len(first) != len(matrix.X):
        findings.append(model_fail("MODEL_PREDICTION_COUNT_MISMATCH", []))
    if any(not math.isfinite(float(value)) for value in first):
        findings.append(model_fail("MODEL_NONFINITE_PREDICTION", []))
    return findings, {"prediction_count": len(first), "deterministic": first == second}


def softmax(scores: list[float], temperature: float) -> list[float]:
    if temperature <= 0 or not math.isfinite(temperature):
        raise AuditError("temperature must be finite and positive")
    if not scores:
        raise AuditError("softmax requires at least one score")
    scaled = [score / temperature for score in scores]
    maximum = max(scaled)
    exp = [math.exp(value - maximum) for value in scaled]
    total = sum(exp)
    return [value / total for value in exp]


def decision_nll(item, temperature: float) -> float:
    probs = softmax(item["scores"], temperature)
    best = [i for i, flag in enumerate(item["teacher_best"]) if flag]
    if not best:
        raise AuditError("decision_nll requires at least one teacher_best candidate")
    target = 1.0 / len(best)
    return -sum(target * math.log(max(probs[i], 1e-15)) for i in best)


def fit_temperature(validation_items, observer=None) -> float:
    if not validation_items:
        raise AuditError("fit_temperature requires validation decisions")
    left, right = -5.0, 5.0
    phi = (1 + math.sqrt(5)) / 2
    objective = lambda log_t: sum(decision_nll(item, math.exp(log_t))
                                  for item in validation_items) / len(validation_items)
    for _ in range(80):
        c = right - (right - left) / phi
        d = left + (right - left) / phi
        if observer is not None:
            observer({"split": "validation", "c": c, "d": d})
        if objective(c) <= objective(d):
            right = d
        else:
            left = c
    return math.exp((left + right) / 2)


def calibration_metrics(items, temperature: float) -> dict:
    if not items:
        raise AuditError("calibration_metrics requires decisions")
    records, nlls, briers, regrets, ndcg1, ndcg2 = [], [], [], [], [], []
    for item in items:
        probs = softmax(item["scores"], temperature)
        best = [i for i, flag in enumerate(item["teacher_best"]) if flag]
        if not best:
            raise AuditError("calibration_metrics requires at least one teacher_best candidate")
        target = [1.0 / len(best) if i in best else 0.0 for i in range(len(probs))]
        prediction = max(range(len(probs)), key=lambda i: (probs[i], -i))
        correct = float(prediction in best)
        confidence = probs[prediction]
        gaps = [float(value) for value in item.get(
            "value_gap_to_best", [0.0 if flag else -1.0 for flag in item["teacher_best"]])]
        regrets.append(-gaps[prediction])
        relevance = [math.exp(value) for value in gaps]
        ideal = sorted(relevance, reverse=True)
        order = sorted(range(len(probs)), key=lambda i: (-probs[i], i))

        def ndcg_at(k):
            dcg = sum(relevance[index] / math.log2(position + 2)
                      for position, index in enumerate(order[:k]))
            idcg = sum(value / math.log2(position + 2)
                       for position, value in enumerate(ideal[:k]))
            return dcg / idcg if idcg else 1.0

        ndcg1.append(ndcg_at(1))
        ndcg2.append(ndcg_at(2))
        nlls.append(-sum(t * math.log(max(p, 1e-15)) for p, t in zip(probs, target)))
        briers.append(sum((p - t) ** 2 for p, t in zip(probs, target)) / len(probs))
        ordered_probs = sorted(probs, reverse=True)
        margin = ordered_probs[0] - ordered_probs[1] if len(ordered_probs) > 1 else 1.0
        records.append((confidence, item["game_id"], item["decision_id"], correct,
                        -gaps[prediction], margin))
    records.sort(key=lambda row: (row[0], row[1], row[2]))
    bins = [list(chunk) for chunk in np.array_split(np.array(records, dtype=object), min(10, len(records)))
            if len(chunk)]
    ece = 0.0
    bin_rows = []
    for bucket in bins:
        confidence = sum(float(row[0]) for row in bucket) / len(bucket)
        accuracy = sum(float(row[3]) for row in bucket) / len(bucket)
        mean_regret = sum(float(row[4]) for row in bucket) / len(bucket)
        mean_top_margin = sum(float(row[5]) for row in bucket) / len(bucket)
        ece += len(bucket) / len(records) * abs(confidence - accuracy)
        bin_rows.append({"n": len(bucket), "confidence": confidence, "accuracy": accuracy,
                         "mean_regret": mean_regret, "mean_top_margin": mean_top_margin})
    return {
        "n": len(records),
        "topset_accuracy": sum(row[3] for row in records) / len(records),
        "mean_regret": sum(regrets) / len(regrets),
        "ndcg_at_1": sum(ndcg1) / len(ndcg1),
        "ndcg_at_2": sum(ndcg2) / len(ndcg2),
        "nll": sum(nlls) / len(nlls), "brier": sum(briers) / len(briers),
        "ece": ece, "bins": bin_rows,
    }


def score_split(model, manifest, decisions, split: str) -> list[dict]:
    items = []
    for decision in decisions:
        matrix = build_feature_matrix(
            (decision,), feature_names=manifest["feature_names"],
            encodings=manifest["categorical_encodings"])
        scores = [float(value) for value in model.predict(np.asarray(matrix.X, dtype=float))]
        items.append({
            "split": split, "game_id": decision.game_id, "decision_id": decision.decision_id,
            "scores": scores,
            "teacher_best": [bool(row["label"]["teacher_best"]) for row in decision.rows],
            "value_gap_to_best": [float(row["label"]["value_gap_to_best"])
                                  for row in decision.rows],
        })
    return items


def audit_optional_model(corpus, config, model_path, manifest_path, ood_scores):
    if model_path is None and manifest_path is None:
        return [], {"status": "not_requested"}
    if model_path is None or manifest_path is None:
        return [model_fail("MODEL_ARTIFACT_PAIR_MISSING", [])], {"status": "unavailable"}
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    import lightgbm as lgb
    model = lgb.Booster(model_file=str(model_path))
    findings, artifact_metrics = audit_model_artifacts(
        corpus, model, manifest, config, Path(manifest_path).parent)
    if any(f.severity == Severity.FAIL for f in findings):
        return findings, {"artifacts": artifact_metrics, "calibration": "not_run"}
    validation = score_split(model, manifest, corpus.decisions_by_split["validation"], "validation")
    test = score_split(model, manifest, corpus.decisions_by_split["test"], "test")
    if not validation or not test:
        findings.append(model_fail("CALIBRATION_SPLIT_EMPTY", []))
        return findings, {"artifacts": artifact_metrics, "calibration": "not_run"}
    temperature = fit_temperature(validation)
    test_metrics = calibration_metrics(test, temperature)
    if test_metrics["ece"] > config.ece_warn:
        findings.append(make_finding(
            code="ECE_HIGH", severity=Severity.WARN, scope="calibration",
            message="test ECE exceeds the configured threshold", count=len(test),
            evidence={"ece": test_metrics["ece"], "threshold": config.ece_warn},
            remediation="inspect calibration; fit temperature on validation only",
        ))
    if len(test) < config.calibration_small_n:
        findings.append(make_finding(
            code="CALIBRATION_SMALL_N", severity=Severity.WARN, scope="calibration",
            message="test calibration sample is underpowered", count=len(test),
            evidence={"minimum": config.calibration_small_n},
            remediation="collect more independent test decisions",
        ))
    strata = {}
    for name, keep_ood in (("id", False), ("ood", True)):
        subset = [item for item in test
                  if (ood_scores.get("test", {}).get(item["decision_id"], 0.0)
                      >= config.ood_threshold) == keep_ood]
        strata[name] = (calibration_metrics(subset, temperature) if subset
                        else {"n": 0, "underpowered": True})
        if 0 < len(subset) < config.small_bucket_games:
            strata[name]["underpowered"] = True
    performance_effect = None
    if strata["id"].get("n", 0) >= config.small_bucket_games and \
            strata["ood"].get("n", 0) >= config.small_bucket_games:
        performance_effect = {
            "topset_accuracy_delta_ood_minus_id": (
                strata["ood"]["topset_accuracy"] - strata["id"]["topset_accuracy"]),
            "mean_regret_delta_ood_minus_id": (
                strata["ood"]["mean_regret"] - strata["id"]["mean_regret"]),
        }
    return findings, {
        "artifacts": artifact_metrics, "temperature": temperature,
        "test": test_metrics, "test_by_ood": strata,
        "ood_performance_effect": performance_effect,
    }

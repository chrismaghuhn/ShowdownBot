import pytest

from showdown_bot.learning.audit.contracts import AuditConfig, AuditCorpus
from showdown_bot.learning.audit.features import audit_features, spearman, train_quantile_edges
from showdown_bot.learning.dataset import Decision


def _feature_corpus(train_rows, test_rows=()):
    def decisions(rows, prefix):
        return tuple(Decision(prefix, f"{prefix}-{i}", [{
            "features": row, "metadata": {"candidate_index": 0}, "label": {}}])
            for i, row in enumerate(rows))
    train, test = decisions(train_rows, "tr"), decisions(test_rows, "te")
    return AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(row for d in train + test for row in d.rows), decisions=train + test,
        split_by_game={d.game_id: ("train" if d in train else "test") for d in train + test},
        decisions_by_split={"train": train, "validation": (), "test": test}, split_manifest={})


def test_constant_near_constant_and_nonfinite_findings():
    corpus = _feature_corpus([
        {"constant": 1, "near": 0 if i < 199 else 1,
         "bad": 0.0 if i < 199 else float("inf")}
        for i in range(200)
    ])
    findings, metrics = audit_features(corpus, AuditConfig())
    codes = {f.code for f in findings}
    assert {"CONSTANT_FEATURE", "NEAR_CONSTANT_FEATURE", "NONFINITE_FEATURE"} <= codes
    assert metrics["train"]["constant"]["unique"] == 1


def test_psi_and_js_use_train_reference():
    corpus = _feature_corpus(
        [{"numeric": i, "category": "a"} for i in range(100)],
        [{"numeric": i, "category": "b"} for i in range(100, 200)],
    )
    findings, metrics = audit_features(corpus, AuditConfig())
    assert metrics["drift"]["test"]["numeric"]["psi"] >= 0.25
    assert metrics["drift"]["test"]["category"]["js"] >= 0.10
    assert {f.code for f in findings} >= {"PSI_DRIFT", "JS_DRIFT", "UNSEEN_CATEGORY"}


def test_feature_threshold_boundaries_are_inclusive():
    rows = [{"near": 0 if i < 199 else 1,
             "sentinel": None if i < 190 else "value"} for i in range(200)]
    findings, _metrics = audit_features(_feature_corpus(rows), AuditConfig())
    assert any(f.code == "NEAR_CONSTANT_FEATURE" and f.feature == "near" for f in findings)
    assert any(f.code == "SENTINEL_DOMINATED_FEATURE" and f.feature == "sentinel"
               for f in findings)


def test_spearman_ties_and_quantile_edges_are_deterministic():
    assert spearman([1, 1, 2, 2], [4, 4, 8, 8]) == pytest.approx(1.0)
    values = list(range(100))
    assert train_quantile_edges(values) == train_quantile_edges(list(reversed(values)))

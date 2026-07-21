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


def test_spearman_empty_pair_is_neutral_but_length_mismatch_is_rejected():
    assert spearman([], []) == 0.0
    with pytest.raises(ValueError, match="equal-length"):
        spearman([], [1.0])
    with pytest.raises(ValueError, match="equal-length"):
        spearman([1.0], [])


def test_format_id_feature_metadata_overlap_is_not_a_denylist_violation():
    # format_id intentionally appears in BOTH FEATURE_COLUMNS and METADATA_KEYS (schema: the only
    # allowed overlap). A real dataset carrying it as a feature must NOT trip the allowlist FAIL.
    corpus = _feature_corpus(
        [{"format_id": "gen9vgc2025regi", "mirror_flag": 0} for _ in range(20)]
    )
    findings, _metrics = audit_features(corpus, AuditConfig())
    assert not any(f.code == "FEATURE_ALLOWLIST_VIOLATION" for f in findings)


def test_denylisted_non_feature_column_still_flags_violation():
    # A genuine leak (a denylisted metadata/label key that is NOT a canonical feature column)
    # must still FAIL — the fix only exempts the documented format_id overlap, not real leaks.
    corpus = _feature_corpus([{"game_outcome": "win"} for _ in range(20)])
    findings, _metrics = audit_features(corpus, AuditConfig())
    assert any(f.code == "FEATURE_ALLOWLIST_VIOLATION" for f in findings)

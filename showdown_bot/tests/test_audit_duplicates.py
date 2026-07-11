from dataclasses import replace

from showdown_bot.learning.audit.contracts import AuditConfig, AuditCorpus, Severity
from showdown_bot.learning.audit.duplicates import (
    audit_duplicates, full_decision_hash, mixed_decision_distance,
    robust_numeric_reference, semantic_decision_hash,
)
from showdown_bot.learning.dataset import group_decisions


def _decision(game_id, *, numeric=0.0, label_gap=-1.0):
    rows = []
    for index in (0, 1):
        best = index == 0
        rows.append({
            "features": {"format_id": "f", "game_mode": "NEUTRAL",
                         "slot1_action_type": "move", "slot2_action_type": "move",
                         "numeric": numeric, "candidate": index},
            "metadata": {"game_id": game_id, "decision_id": f"{game_id}-d",
                         "candidate_index": index, "format_id": "f",
                         "schema_version": "v1", "feature_extractor_version": "v1",
                         "teacher_version": "t", "config_hash": "c"},
            "label": {"teacher_best": best, "value_gap_to_best": 0.0 if best else label_gap},
        })
    return group_decisions(rows)[0]


def _corpus(train, test):
    decisions = tuple(train + test)
    return AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(row for decision in decisions for row in decision.rows), decisions=decisions,
        split_by_game={d.game_id: ("train" if d in train else "test") for d in decisions},
        decisions_by_split={"train": tuple(train), "validation": (), "test": tuple(test)},
        split_manifest={},
    )


def test_semantic_duplicate_across_splits_is_fail():
    corpus = _corpus([_decision("train-g")], [_decision("test-g")])
    findings, metrics = audit_duplicates(corpus, AuditConfig())
    finding = next(f for f in findings if f.code == "SEMANTIC_CROSS_SPLIT_DUPLICATE")
    assert finding.severity == Severity.FAIL
    assert metrics["semantic_cross_split_pairs"] == 1


def test_label_only_change_keeps_semantic_hash():
    left = _decision("left", label_gap=-1.0)
    right = _decision("right", label_gap=-2.0)
    assert semantic_decision_hash(left) == semantic_decision_hash(right)
    assert full_decision_hash(left) != full_decision_hash(right)


def test_near_duplicate_threshold_is_inclusive():
    left, right = _decision("left", numeric=0.0), _decision("right", numeric=0.5)
    reference = {"numeric": (0.0, 1.0)}
    distance = mixed_decision_distance(left, right, reference, AuditConfig())
    corpus = _corpus([left], [right])
    findings, _metrics = audit_duplicates(
        corpus, replace(AuditConfig(), near_duplicate_threshold=distance))
    assert any(f.code == "NEAR_CROSS_SPLIT_DUPLICATE" for f in findings)


def test_same_split_duplicate_is_not_fail():
    left, right = _decision("a"), _decision("b")
    findings, _metrics = audit_duplicates(_corpus([left, right], []), AuditConfig())
    duplicate_findings = [f for f in findings if "DUPLICATE" in f.code]
    assert duplicate_findings
    assert all(f.severity != Severity.FAIL for f in duplicate_findings)


def test_near_distance_above_threshold_and_different_blocks_do_not_warn():
    left, right = _decision("left", numeric=0.0), _decision("right", numeric=1.0)
    right.rows[0]["features"]["game_mode"] = "TRICK_ROOM"
    right.rows[1]["features"]["game_mode"] = "TRICK_ROOM"
    corpus = _corpus([left], [right])
    findings, _metrics = audit_duplicates(corpus, AuditConfig(near_duplicate_threshold=0.05))
    assert not any(f.code == "NEAR_CROSS_SPLIT_DUPLICATE" for f in findings)


def test_zero_iqr_reference_has_positive_scale():
    reference = robust_numeric_reference([_decision("a", numeric=0.0)])
    assert reference["numeric"][1] > 0

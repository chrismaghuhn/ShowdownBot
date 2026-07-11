import json

import pytest

from showdown_bot.learning.audit.contracts import AuditConfig, AuditCorpus, AuditError, Severity
from showdown_bot.learning.audit.distribution import (
    audit_distribution, audit_ood, audit_team_coverage, load_team_catalog,
)
from showdown_bot.learning.dataset import Decision


def _write_catalog(tmp_path, rows):
    path = tmp_path / "teams.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _distribution_corpus(train_features, test_features=(), team_hashes=None):
    team_hashes = team_hashes or ["known"] * (len(train_features) + len(test_features))
    decisions = []
    for index, features in enumerate(list(train_features) + list(test_features)):
        split = "train" if index < len(train_features) else "test"
        row = {"features": features,
               "metadata": {"candidate_index": 0, "team_hash": team_hashes[index],
                            "game_id": f"g{index}", "decision_id": f"d{index}",
                            "teacher_config": {"trainable_label": True}},
               "label": {"teacher_best": True, "chosen_by_current_heuristic": True}}
        decisions.append((split, Decision(f"g{index}", f"d{index}", [row])))
    return AuditCorpus(
        dataset_name="fixture", dataset_sha256="a" * 64,
        rows=tuple(row for _s, d in decisions for row in d.rows),
        decisions=tuple(d for _s, d in decisions),
        split_by_game={d.game_id: split for split, d in decisions},
        decisions_by_split={
            name: tuple(d for split, d in decisions if split == name)
            for name in ("train", "validation", "test")}, split_manifest={})


def test_team_catalog_is_strict_and_partial_coverage_warns(tmp_path):
    catalog = _write_catalog(tmp_path, [{
        "team_hash": "known", "team_id": "rain-1", "archetype": "rain", "declared_split": "train",
    }])
    corpus = _distribution_corpus([{"x": 0.0}, {"x": 1.0}], team_hashes=["known", "unknown"])
    teams, findings = load_team_catalog(catalog), audit_team_coverage(corpus, load_team_catalog(catalog))
    assert teams["known"].archetype == "rain"
    assert any(f.code == "UNKNOWN_TEAM_HASH" and f.severity == Severity.WARN for f in findings)


def test_ood_score_components_and_threshold():
    corpus = _distribution_corpus(
        [{"numeric": 0.0, "category": "seen", "maybe": 1.0}],
        [{"numeric": 100.0, "category": "unseen", "maybe": None}],
    )
    scores, findings, metrics = audit_ood(corpus, AuditConfig(ood_threshold=0.5))
    assert any(score >= 0.5 for score in scores["test"].values())
    assert any(f.code == "OOD_DECISIONS" for f in findings)
    assert metrics["test"]["ood_rate"] > 0


def test_catalog_rejects_unknown_fields_and_conflicting_hash(tmp_path):
    unknown = _write_catalog(tmp_path, [{
        "team_hash": "h", "team_id": "id", "archetype": "rain",
        "declared_split": "train", "extra": True,
    }])
    with pytest.raises(AuditError, match="fields mismatch"):
        load_team_catalog(unknown)
    conflicting = _write_catalog(tmp_path, [
        {"team_hash": "h", "team_id": "a", "archetype": "rain", "declared_split": "train"},
        {"team_hash": "h", "team_id": "b", "archetype": "sun", "declared_split": "train"},
    ])
    with pytest.raises(AuditError, match="conflicting team hash"):
        load_team_catalog(conflicting)


def test_missing_catalog_and_small_action_bucket_are_reported():
    corpus = _distribution_corpus([{"slot1_action_type": "move",
                                    "slot2_action_type": "move"}])
    findings, metrics, _scores = audit_distribution(corpus, AuditConfig(), team_catalog=None)
    assert metrics["coverage"]["train"]["teams"] == "unavailable"
    assert {f.code for f in findings} >= {"TEAM_CATALOG_UNAVAILABLE", "SINGLE_ACTION_CLASS",
                                          "SMALL_ACTION_BUCKET"}

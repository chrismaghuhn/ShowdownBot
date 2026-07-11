import pytest

from showdown_bot.learning.audit.contracts import AuditConfig, AuditError, Severity
from showdown_bot.learning.audit.integrity import build_split_manifest, dataset_sha256, load_and_audit_integrity
from showdown_bot.learning.schema import FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS, Row, to_jsonl_line


def _schema_row(game_id, decision_id, candidate_index, *, format_id="gen9vgc2025regi"):
    features = {key: 0.0 for key in FEATURE_COLUMNS}
    features.update({
        "format_id": format_id, "game_mode": "NEUTRAL",
        "slot1_action_type": "move", "slot2_action_type": "move",
        "slot1_move_id": "tackle", "slot2_move_id": "protect",
    })
    best = candidate_index == 0
    raw = 1.0 if best else 0.0
    metadata = {key: None for key in METADATA_KEYS}
    metadata.update({
        "game_id": game_id, "decision_id": decision_id,
        "candidate_index": candidate_index, "format_id": format_id,
        "game_outcome": "win", "final_turn": 5, "winner": "p1", "teacher_trace": {},
        "schema_version": "v1", "feature_extractor_version": "v1",
        "teacher_version": "rollout-h1-v1", "git_sha": "a" * 40,
        "team_hash": "team-a", "config_hash": "config-a",
        "teacher_config": {"teacher_version": "rollout-h1-v1", "trainable_label": True},
    })
    label = {key: 0 for key in LABEL_KEYS}
    label.update({
        "counterfactual_value_raw": raw,
        "counterfactual_value_normalized_within_decision": 0.5 if best else -0.5,
        "value_gap_to_best": 0.0 if best else -1.0,
        "counterfactual_rank": candidate_index, "teacher_rank": candidate_index,
        "teacher_best": best, "chosen_by_current_heuristic": best,
        "heuristic_rank": candidate_index,
    })
    return Row(features=features, metadata=metadata, label=label)


@pytest.fixture
def audit_dataset():
    def write(tmp_path, *, games=3, candidate_indices=(0, 1), mixed_format=False,
              mixed_provenance=False):
        path = tmp_path / "dataset.jsonl"
        lines = []
        for game_index in range(games):
            for candidate_index in candidate_indices:
                if mixed_provenance:
                    format_id = "gen9vgc2025regi" if game_index % 2 == 0 else "other-format"
                elif mixed_format and candidate_index == candidate_indices[-1]:
                    format_id = "other-format"
                else:
                    format_id = "gen9vgc2025regi"
                lines.append(to_jsonl_line(_schema_row(
                    f"g{game_index}", f"g{game_index}-d0", candidate_index,
                    format_id=format_id,
                )))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    return write


def split_manifest_for(path, assignments):
    return build_split_manifest(dataset_sha256(path), assignments)


def test_generated_split_is_complete_disjoint_and_hashed(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, games=20)
    corpus, findings = load_and_audit_integrity(path, AuditConfig())
    assert findings == []
    assert set(corpus.split_by_game) == {f"g{i}" for i in range(20)}
    assert set(corpus.split_by_game.values()) <= {"train", "validation", "test"}
    assert len(corpus.split_manifest["split_sha256"]) == 64


def test_split_manifest_refuses_missing_game(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, games=3)
    manifest = split_manifest_for(path, {"g0": "train", "g1": "test"})
    with pytest.raises(AuditError, match="missing games"):
        load_and_audit_integrity(path, AuditConfig(), split_manifest=manifest)


def test_candidate_indices_and_decision_metadata_fail(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, candidate_indices=[0, 2], mixed_format=True)
    _corpus, findings = load_and_audit_integrity(path, AuditConfig())
    assert {f.code for f in findings} >= {"NONCONTIGUOUS_CANDIDATES", "DECISION_METADATA_MISMATCH"}
    assert all(f.severity == Severity.FAIL for f in findings)


def test_empty_dataset_and_wrong_manifest_hash_are_rejected(tmp_path, audit_dataset):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(AuditError, match="empty"):
        load_and_audit_integrity(empty, AuditConfig())
    path = audit_dataset(tmp_path, games=3)
    manifest = split_manifest_for(path, {"g0": "train", "g1": "validation", "g2": "test"})
    manifest["dataset_sha256"] = "0" * 64
    with pytest.raises(AuditError, match="dataset hash"):
        load_and_audit_integrity(path, AuditConfig(), split_manifest=manifest)


def test_effective_feature_denylist_is_fail(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path)
    _corpus, findings = load_and_audit_integrity(
        path, AuditConfig(), effective_model_features=["teacher_best"])
    assert any(f.code == "MODEL_FEATURE_DENYLIST_VIOLATION"
               and f.severity == Severity.FAIL for f in findings)


def test_mixed_provenance_is_reported(tmp_path, audit_dataset):
    path = audit_dataset(tmp_path, mixed_provenance=True)
    _corpus, findings = load_and_audit_integrity(path, AuditConfig())
    assert any(f.code == "MIXED_PROVENANCE" for f in findings)

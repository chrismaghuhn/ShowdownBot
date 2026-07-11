import json

from showdown_bot.learning.audit.runner import AuditRunConfig, run_audit
from showdown_bot.learning.schema import FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS, Row, to_jsonl_line


def _runner_row(game, decision, index):
    features = {key: 0.0 for key in FEATURE_COLUMNS}
    features.update({"format_id": "f", "game_mode": "NEUTRAL",
                     "slot1_action_type": "move", "slot2_action_type": "move",
                     "slot1_move_id": "tackle", "slot2_move_id": "protect"})
    best = index == 0
    metadata = {key: None for key in METADATA_KEYS}
    metadata.update({
        "game_id": game, "decision_id": decision, "candidate_index": index,
        "format_id": "f", "game_outcome": "win", "final_turn": 4, "winner": "p1",
        "teacher_trace": {}, "schema_version": "v1", "feature_extractor_version": "v1",
        "teacher_version": "t", "git_sha": "a" * 40, "team_hash": "team",
        "config_hash": "config", "teacher_config": {"teacher_version": "t",
                                                       "trainable_label": True},
    })
    label = {key: 0 for key in LABEL_KEYS}
    label.update({
        "counterfactual_value_raw": 1.0 if best else 0.0,
        "counterfactual_value_normalized_within_decision": 0.5 if best else -0.5,
        "value_gap_to_best": 0.0 if best else -1.0,
        "counterfactual_rank": index, "teacher_rank": index,
        "teacher_best": best, "chosen_by_current_heuristic": best, "heuristic_rank": index,
    })
    return Row(features=features, metadata=metadata, label=label)


def _runner_dataset(tmp_path):
    path = tmp_path / "valid.jsonl"
    rows = [_runner_row("g0", "d0", 0), _runner_row("g0", "d0", 1),
            _runner_row("g1", "d1", 0), _runner_row("g1", "d1", 1)]
    path.write_text("\n".join(to_jsonl_line(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_runner_writes_report_on_findings(tmp_path):
    dataset = _runner_dataset(tmp_path)
    code = run_audit(AuditRunConfig(
        dataset=dataset, out_dir=tmp_path / "out", model_path=tmp_path / "model.txt"))
    assert code == 1
    assert (tmp_path / "out" / "audit.json").exists()
    assert (tmp_path / "out" / "audit.md").exists()
    assert (tmp_path / "out" / "split-manifest.json").exists()


def test_fatal_input_writes_minimal_report(tmp_path):
    code = run_audit(AuditRunConfig(dataset=tmp_path / "missing.jsonl", out_dir=tmp_path))
    obj = json.loads((tmp_path / "audit.json").read_text())
    assert code == 1
    assert obj["status"] == "AUDIT FAIL"
    assert obj["findings"][0]["code"] == "FATAL_INPUT"
    assert obj["metrics"] == {"not_run": True}

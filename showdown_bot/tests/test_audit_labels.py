import pytest

from showdown_bot.learning.audit.contracts import Severity
from showdown_bot.learning.audit.labels import audit_labels
from showdown_bot.learning.dataset import group_decisions


def _label_decision(*, raw_values=(1.0, 0.0), teacher_best=(True, False),
                    chosen=(True, False), teacher_rank=(0, 1)):
    mean = sum(raw_values) / len(raw_values)
    maximum = max(raw_values)
    rows = []
    for index, raw in enumerate(raw_values):
        rows.append({
            "features": {"candidate": index},
            "metadata": {"game_id": "g", "decision_id": "d", "candidate_index": index,
                         "teacher_version": "t", "feature_extractor_version": "v1",
                         "config_hash": "c",
                         "teacher_config": {"teacher_version": "t", "trainable_label": True}},
            "label": {
                "counterfactual_value_raw": raw,
                "counterfactual_value_normalized_within_decision": raw - mean,
                "value_gap_to_best": raw - maximum,
                "counterfactual_rank": teacher_rank[index], "teacher_rank": teacher_rank[index],
                "teacher_best": teacher_best[index],
                "chosen_by_current_heuristic": chosen[index], "heuristic_rank": index,
            },
        })
    return group_decisions(rows)[0]


def test_valid_tie_and_multiple_equivalent_choices_pass():
    decision = _label_decision(
        raw_values=[2.0, 2.0, 1.0], teacher_best=[True, True, False],
        chosen=[True, True, False], teacher_rank=[0, 0, 2],
    )
    findings, _metrics = audit_labels([decision])
    assert not [f for f in findings if f.severity == Severity.FAIL]


@pytest.mark.parametrize(("mutation", "code"), [
    (lambda row: row["label"].update(value_gap_to_best=0.1), "POSITIVE_VALUE_GAP"),
    (lambda row: row["label"].update(teacher_best=True, value_gap_to_best=-1.0), "BEST_NONZERO_GAP"),
    (lambda row: row["label"].update(counterfactual_value_normalized_within_decision=5.0), "NORMALIZED_MEAN_MISMATCH"),
])
def test_label_failures(mutation, code):
    decision = _label_decision()
    mutation(decision.rows[0])
    findings, _metrics = audit_labels([decision])
    assert any(f.code == code and f.severity == Severity.FAIL for f in findings)


@pytest.mark.parametrize(("decision", "code"), [
    (_label_decision(teacher_best=(False, False)), "NO_TEACHER_BEST"),
    (_label_decision(chosen=(False, False)), "NO_HEURISTIC_CHOICE"),
    (_label_decision(teacher_rank=(1, 0)), "TEACHER_RANK_MISMATCH"),
])
def test_structural_label_failures(decision, code):
    findings, _metrics = audit_labels([decision])
    assert any(f.code == code and f.severity == Severity.FAIL for f in findings)


def test_nonfinite_and_trainable_mismatch_fail():
    nonfinite = _label_decision()
    nonfinite.rows[0]["label"]["counterfactual_value_raw"] = float("nan")
    mismatch = _label_decision()
    mismatch.rows[1]["metadata"]["teacher_config"]["trainable_label"] = False
    first, _metrics = audit_labels([nonfinite])
    second, _metrics = audit_labels([mismatch])
    assert any(f.code == "NONFINITE_LABEL" for f in first)
    assert any(f.code == "TRAINABLE_LABEL_MISMATCH" for f in second)

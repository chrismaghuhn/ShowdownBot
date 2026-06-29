import pytest

from showdown_bot.learning.schema import (
    FEATURE_COLUMNS, METADATA_KEYS, LABEL_KEYS, Row,
    validate_row, to_jsonl_line, from_jsonl_line,
)


def _row():
    features = {c: 0 for c in FEATURE_COLUMNS}
    metadata = {k: "x" for k in METADATA_KEYS}
    label = {k: 0 for k in LABEL_KEYS}
    return Row(features=features, metadata=metadata, label=label)


def test_outcome_fields_are_metadata_not_features():
    for forbidden in ("game_outcome", "winner", "final_turn", "teacher_trace"):
        assert forbidden not in FEATURE_COLUMNS
        assert forbidden in METADATA_KEYS


def test_jsonl_roundtrip_is_identity():
    row = _row()
    back = from_jsonl_line(to_jsonl_line(row))
    assert back.features == row.features
    assert back.metadata == row.metadata
    assert back.label == row.label


def test_validate_row_rejects_unknown_feature_key():
    row = _row()
    row.features["not_a_real_feature"] = 1
    with pytest.raises(ValueError, match="unknown feature"):
        validate_row(row)


def test_validate_row_requires_versioning_metadata():
    row = _row()
    del row.metadata["schema_version"]
    with pytest.raises(ValueError, match="missing metadata"):
        validate_row(row)

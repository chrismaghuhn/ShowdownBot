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


def test_feature_columns_are_unique():
    assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS))
    assert len(METADATA_KEYS) == len(set(METADATA_KEYS))
    assert len(LABEL_KEYS) == len(set(LABEL_KEYS))


def test_sections_do_not_accidentally_overlap_except_allowed():
    allowed = {"format_id"}
    assert (set(FEATURE_COLUMNS) & set(METADATA_KEYS)) <= allowed
    assert not (set(FEATURE_COLUMNS) & set(LABEL_KEYS))
    assert not (set(METADATA_KEYS) & set(LABEL_KEYS))


def test_validate_row_rejects_missing_feature_key():
    row = _row()
    del row.features[FEATURE_COLUMNS[0]]
    with pytest.raises(ValueError, match="missing feature"):
        validate_row(row)


def test_validate_row_rejects_missing_label_key():
    row = _row()
    del row.label[LABEL_KEYS[0]]
    with pytest.raises(ValueError, match="missing label"):
        validate_row(row)


def test_validate_row_rejects_unknown_metadata_key():
    row = _row()
    row.metadata["bogus_meta"] = 1
    with pytest.raises(ValueError, match="unknown metadata"):
        validate_row(row)


def test_to_jsonl_validates_before_serializing():
    row = _row()
    row.features["bad"] = 1
    with pytest.raises(ValueError):
        to_jsonl_line(row)

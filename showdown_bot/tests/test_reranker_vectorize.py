# tests/test_reranker_vectorize.py
from showdown_bot.learning.reranker_features import vectorize


def test_vectorize_uses_only_named_features_in_order():
    feats = [{"a": 1.0, "b": "x", "c_extra": 99}, {"a": 2.0, "b": "y", "c_extra": 88}]
    enc = {"b": {"__unk__": 0, "x": 1, "y": 2}}
    X, missing = vectorize(feats, feature_names=["a", "b"], encodings=enc)
    assert missing == []
    assert X == [[1.0, 1.0], [2.0, 2.0]]        # b:x->1, b:y->2; c_extra ignored


def test_vectorize_unseen_categorical_maps_to_unk_zero():
    enc = {"b": {"__unk__": 0, "x": 1}}
    X, missing = vectorize([{"a": 1.0, "b": "zzz"}], feature_names=["a", "b"], encodings=enc)
    assert X == [[1.0, 0.0]] and missing == []   # unseen -> UNK code 0


def test_vectorize_reports_missing_feature_names():
    X, missing = vectorize([{"a": 1.0}], feature_names=["a", "b"], encodings={})
    assert "b" in missing                        # 'b' absent from the row

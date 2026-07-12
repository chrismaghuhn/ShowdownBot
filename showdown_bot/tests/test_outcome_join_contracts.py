import gzip
import pytest
from showdown_bot.learning.outcome_join.contracts import (
    OutcomeJoinError, OutcomeLabel, encode_game_outcome, canonical_json,
    content_sha256, read_jsonl, SIDECAR_SCHEMA_VERSION,
)

def test_encode_game_outcome_is_signed_hero_relative():
    assert encode_game_outcome("hero") == 1.0
    assert encode_game_outcome("villain") == -1.0
    assert encode_game_outcome("tie") == 0.0
    with pytest.raises(OutcomeJoinError, match="winner"):
        encode_game_outcome("p1")

def test_outcome_label_roundtrips_and_validates():
    label = OutcomeLabel(game_id="g", battle_id="b", team_hash="t", seed_index=0,
                         winner="hero", game_outcome=1.0, final_turn=16)
    row = label.to_row()
    assert row["schema_version"] == SIDECAR_SCHEMA_VERSION
    assert OutcomeLabel.from_row(row) == label
    with pytest.raises(OutcomeJoinError, match="final_turn"):
        OutcomeLabel(game_id="g", battle_id="b", team_hash="t", seed_index=0,
                     winner="hero", game_outcome=1.0, final_turn=-1).validate()

def test_canonical_hash_is_order_independent():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
    assert content_sha256({"a": 1, "b": 2}) == content_sha256({"b": 2, "a": 1})

def test_read_jsonl_is_gzip_aware(tmp_path):
    p = tmp_path / "x.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write('{"a":1}\n{"a":2}\n')
    assert [r["a"] for r in read_jsonl(p)] == [1, 2]

import gzip, json
from showdown_bot.learning.outcome_join.bridge import DatasetGroup, BridgeMapping
from showdown_bot.learning.outcome_join.join import build_labels, apply_labels

KEY = ("g", "t", "c")

def test_build_labels_encodes_and_fills_three_fields():
    group = DatasetGroup(KEY, "g", "t", "c", frozenset({"a"}), {"a": 3})
    mapping = BridgeMapping(KEY, (True, 0), {"a": 0})
    results = {0: {"battle_id": "b0", "winner": "villain", "turns": 9}}
    labels = build_labels(group, mapping, results)
    assert len(labels) == 1
    lab = labels[0]
    assert (lab.winner, lab.game_outcome, lab.final_turn) == ("villain", -1.0, 9)
    assert lab.battle_id == "b0" and lab.seed_index == 0

def test_apply_fills_every_row_of_a_battle_and_leaves_others_pending(tmp_path):
    rows = [{"metadata": {"game_id": "a", "game_outcome": "__pending__",
                          "winner": "__pending__", "final_turn": -1}, "features": {}},
            {"metadata": {"game_id": "a", "game_outcome": "__pending__",
                          "winner": "__pending__", "final_turn": -1}, "features": {}},
            {"metadata": {"game_id": "z", "game_outcome": "__pending__",
                          "winner": "__pending__", "final_turn": -1}, "features": {}}]
    from showdown_bot.learning.outcome_join.contracts import OutcomeLabel
    labels = [OutcomeLabel("a", "b0", "t", 0, "hero", 1.0, 16)]
    out = tmp_path / "filled.jsonl.gz"
    n = apply_labels(rows, labels, out)
    assert n == 2
    written = [json.loads(l) for l in gzip.open(out, "rt", encoding="utf-8")]
    a_rows = [r for r in written if r["metadata"]["game_id"] == "a"]
    assert all(r["metadata"]["game_outcome"] == 1.0 for r in a_rows)
    assert all(r["metadata"]["winner"] == "hero" for r in a_rows)
    z = [r for r in written if r["metadata"]["game_id"] == "z"][0]
    assert z["metadata"]["winner"] == "__pending__"   # untouched

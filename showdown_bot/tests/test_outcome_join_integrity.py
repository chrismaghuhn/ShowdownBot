from showdown_bot.learning.outcome_join.bridge import DatasetGroup, BridgeMapping
from showdown_bot.learning.outcome_join.integrity import check_group

KEY = ("g", "t", "c")

def _group(max_turns):  # game_id -> max turn
    return DatasetGroup(KEY, "g", "t", "c", frozenset(max_turns), dict(max_turns))

def _mapping(game_to_seed):
    return BridgeMapping(KEY, (True, 0), dict(game_to_seed))

def _results(turns_by_seed):
    return {s: {"turns": t} for s, t in turns_by_seed.items()}

def test_gate_passes_when_bijective_and_turns_fit():
    g = _group({"a": 3, "b": 5})
    r = check_group(g, _mapping({"a": 0, "b": 1}), _results({0: 9, 1: 9}))
    assert r.passed and r.turn_violations == 0

def test_gate_fails_on_turn_overshoot():
    g = _group({"a": 12})
    r = check_group(g, _mapping({"a": 0}), _results({0: 9}))
    assert not r.passed and r.turn_violations == 1

def test_gate_fails_when_mapping_not_bijective_over_group():
    g = _group({"a": 3, "b": 3})
    r = check_group(g, _mapping({"a": 0}), _results({0: 9, 1: 9}))  # 'b' unmapped
    assert not r.passed and r.coverage_ok is False

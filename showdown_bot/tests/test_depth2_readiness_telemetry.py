"""Depth2ReadinessCounts sink tests (spec §6.5, §10.3)."""
from __future__ import annotations

from showdown_bot.eval.depth2_readiness import Depth2ReadinessCounts


def test_initial_state():
    """All counters start at zero."""
    c = Depth2ReadinessCounts()
    assert c.search_depth == 1
    assert c.search_topn_requested == 0
    assert c.search_topm_requested == 0
    assert c.depth2_candidates_selected == 0
    assert c.depth2_response_slots_eligible == 0
    assert c.accuracy_mode is False
    assert c.accuracy_branch_cap == 0
    assert c.turn1_accuracy_leaf_count == 0
    assert c.turn1_accuracy_cap_hits == 0
    assert c.turn2_accuracy_leaf_count == 0
    assert c.turn2_accuracy_cap_hits == 0


def test_increment_turn1():
    """Turn-1 leaf/cap counters increment additively."""
    c = Depth2ReadinessCounts()
    c.add_turn1_accuracy(leaf_count=3, cap_hits=1)
    c.add_turn1_accuracy(leaf_count=2, cap_hits=0)
    assert c.turn1_accuracy_leaf_count == 5
    assert c.turn1_accuracy_cap_hits == 1


def test_increment_turn2():
    """Turn-2 leaf/cap counters increment additively."""
    c = Depth2ReadinessCounts()
    c.add_turn2_accuracy(leaf_count=4, cap_hits=2)
    c.add_turn2_accuracy(leaf_count=1, cap_hits=0)
    assert c.turn2_accuracy_leaf_count == 5
    assert c.turn2_accuracy_cap_hits == 2


def test_cap_fallback_derived():
    """Cap-fallback booleans are derived, not stored."""
    c = Depth2ReadinessCounts()
    assert c.turn1_accuracy_cap_fallback is False
    assert c.turn2_accuracy_cap_fallback is False
    c.add_turn1_accuracy(leaf_count=6, cap_hits=1)
    assert c.turn1_accuracy_cap_fallback is True
    assert c.turn2_accuracy_cap_fallback is False
    c.add_turn2_accuracy(leaf_count=6, cap_hits=3)
    assert c.turn2_accuracy_cap_fallback is True


def test_to_dict():
    """to_dict produces the exact field set expected by profile v4."""
    c = Depth2ReadinessCounts()
    c.search_depth = 2
    c.search_topn_requested = 3
    c.search_topm_requested = 3
    c.depth2_candidates_selected = 2
    c.depth2_response_slots_eligible = 5
    c.accuracy_mode = True
    c.accuracy_branch_cap = 6
    c.add_turn1_accuracy(leaf_count=10, cap_hits=2)
    c.add_turn2_accuracy(leaf_count=8, cap_hits=0)

    d = c.to_dict()
    assert d == {
        "search_depth": 2,
        "search_topn_requested": 3,
        "search_topm_requested": 3,
        "depth2_candidates_selected": 2,
        "depth2_response_slots_eligible": 5,
        "accuracy_mode": True,
        "accuracy_branch_cap": 6,
        "turn1_accuracy_leaf_count": 10,
        "turn1_accuracy_cap_hits": 2,
        "turn1_accuracy_cap_fallback": True,
        "turn2_accuracy_leaf_count": 8,
        "turn2_accuracy_cap_hits": 0,
        "turn2_accuracy_cap_fallback": False,
    }

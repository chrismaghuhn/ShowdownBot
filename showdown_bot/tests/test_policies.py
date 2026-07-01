"""T3a central policy registry (decouples the known-policy set from T3c implementations).

Declares the full planned policy set with metadata now; T3c flips implemented=True as each
is wired. Panel + schedule validation both source this registry.
"""
from __future__ import annotations

from showdown_bot.eval.policies import (
    POLICIES,
    is_known,
    is_reproducible,
    reproducible_names,
)


def test_full_planned_set_declared():
    assert set(POLICIES) == {
        "heuristic", "max_damage", "random",
        "greedy_protect", "simple_heuristic", "scripted_vgc",
    }


def test_implemented_flags():
    assert POLICIES["heuristic"].implemented is True
    assert POLICIES["max_damage"].implemented is True
    assert POLICIES["random"].implemented is True
    # the 3 new policies are wired in T3c
    for name in ("greedy_protect", "simple_heuristic", "scripted_vgc"):
        assert POLICIES[name].implemented is True


def test_random_is_non_reproducible():
    assert POLICIES["random"].reproducible is False
    assert is_reproducible("random") is False
    assert "random" not in reproducible_names()


def test_reproducible_names_excludes_random_only():
    assert reproducible_names() == {
        "heuristic", "max_damage", "greedy_protect", "simple_heuristic", "scripted_vgc",
    }


def test_is_known():
    assert is_known("heuristic") is True
    assert is_known("mystery_bot") is False

"""Regression tests for the build_known_side ident-suffix key bug.

Root cause: build_known_side keyed roster/movesets/stats/quality by the FULL
slot.ident (e.g. "p1: Flutter Mane"), but simulator._apply_switches looked up
roster[sa.target_ident] where target_ident is the SUFFIX (e.g. "Flutter Mane"),
as emitted by actions.py:52 via mon.ident.split(": ", 1)[-1].

Fix: build_known_side must key all four maps by the ident suffix.

These tests are HERMETIC — no Node, no live CalcClient.
"""
from __future__ import annotations

import pytest

from showdown_bot.models.actions import SlotAction
from showdown_bot.battle.actions import JointAction
from showdown_bot.learning.belief_builder import BeliefSide, build_known_side
from showdown_bot.engine.state import BattleState, PokemonState


# ---------------------------------------------------------------------------
# Minimal fake PokemonSlot (avoids pydantic / fixture-file dep for hermeticity)
# ---------------------------------------------------------------------------

class _Slot:
    """Minimal duck-typed PokemonSlot for build_known_side unit tests."""

    def __init__(self, ident, details, condition, active, stats, moves):
        self.ident = ident
        self.details = details
        self.condition = condition
        self.active = active
        self.stats = stats
        self.moves = moves


def _make_team_slots():
    """Two active + one bench slot.  Bench slot has ident 'p1: Flutter Mane'."""
    return [
        _Slot(
            ident="p1: Incineroar",
            details="Incineroar, L50, F",
            condition="150/150",
            active=True,
            stats={"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
            moves=["fakeout", "flareblitz", "protect", "knockoff"],
        ),
        _Slot(
            ident="p1: Rillaboom",
            details="Rillaboom, L50, M",
            condition="155/155",
            active=True,
            stats={"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 95},
            moves=["heatwave", "earthpower", "protect", "solarbeam"],
        ),
        _Slot(
            ident="p1: Flutter Mane",
            details="Flutter Mane, L50",
            condition="131/131",
            active=False,
            stats={"atk": 50, "def": 60, "spa": 140, "spd": 120, "spe": 151},
            moves=["moonblast", "shadowball", "dazzlinggleam", "protect"],
        ),
    ]


# ---------------------------------------------------------------------------
# 1. Unit test: build_known_side must key by SUFFIX, not full ident
# ---------------------------------------------------------------------------

def test_build_known_side_keys_by_ident_suffix():
    """build_known_side must use the ident SUFFIX as the key for all four maps.

    Before the fix: roster["p1: Flutter Mane"] existed, roster["Flutter Mane"] did not.
    After the fix:  roster["Flutter Mane"] exists, roster["p1: Flutter Mane"] does not.
    """
    slots = _make_team_slots()
    bs = build_known_side(slots)

    # Bench slot suffix must be present in all four maps
    assert "Flutter Mane" in bs.roster, (
        "roster must be keyed by ident suffix 'Flutter Mane', not full ident"
    )
    assert "p1: Flutter Mane" not in bs.roster, (
        "roster must NOT be keyed by full ident 'p1: Flutter Mane'"
    )

    assert "Flutter Mane" in bs.movesets, "movesets must use suffix key"
    assert "p1: Flutter Mane" not in bs.movesets, "movesets must NOT use full-ident key"

    assert "Flutter Mane" in bs.stats, "stats must use suffix key"
    assert "p1: Flutter Mane" not in bs.stats, "stats must NOT use full-ident key"

    assert "Flutter Mane" in bs.quality, "quality must use suffix key"
    assert "p1: Flutter Mane" not in bs.quality, "quality must NOT use full-ident key"


def test_build_known_side_all_maps_share_suffix_keyspace():
    """movesets, stats, quality must all have the same key set (all suffix-based)."""
    slots = _make_team_slots()
    bs = build_known_side(slots)

    expected_suffixes = {s.ident.split(": ", 1)[-1] for s in slots}

    assert set(bs.movesets) == expected_suffixes, (
        f"movesets keys {set(bs.movesets)} != expected suffixes {expected_suffixes}"
    )
    assert set(bs.stats) == expected_suffixes, (
        f"stats keys {set(bs.stats)} != expected suffixes {expected_suffixes}"
    )
    assert set(bs.quality) == expected_suffixes, (
        f"quality keys {set(bs.quality)} != expected suffixes {expected_suffixes}"
    )

    # Bench suffix must be among them
    assert "Flutter Mane" in set(bs.movesets)


# ---------------------------------------------------------------------------
# 2. Path-level regression: switch via build_known_side roster must NOT raise ValueError
#
# This is the real crash path: apply_outcome_to_state -> _apply_switches ->
# roster[sa.target_ident] where target_ident == "Flutter Mane" (suffix).
# Before the fix: roster has "p1: Flutter Mane" -> KeyError -> ValueError.
# After the fix:  roster has "Flutter Mane"     -> lookup succeeds.
# ---------------------------------------------------------------------------

def test_apply_outcome_switch_uses_known_side_roster():
    """A switch JointAction whose target_ident is an ident suffix MUST resolve
    without ValueError when the roster was produced by build_known_side.

    This reproduces the exact crash from the rollout-export probe:
      ValueError: switch target 'Flutter Mane' not in roster for side 'p1'

    The test is hermetic: no Node, no live calc, no fixture files.
    """
    from showdown_bot.learning.simulator import apply_outcome_to_state
    from showdown_bot.battle.resolve import TurnOutcome

    # Build a BattleState with Flutter Mane on the bench (it's not in sides)
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    state.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    state.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=120, max_hp=120)
    state.sides["p2"]["b"] = PokemonState(species="Tornadus", hp=140, max_hp=140)

    # Build the known-side roster from team slots (the same code path the
    # rollout export probe uses)
    slots = _make_team_slots()
    bs = build_known_side(slots)

    # Construct a switch JointAction exactly as actions.py does:
    #   target_ident = mon.ident.split(": ", 1)[-1]  -> "Flutter Mane"
    switch_action = JointAction(
        slot0=SlotAction(kind="switch", target_ident="Flutter Mane"),
        slot1=SlotAction(kind="pass"),
    )

    # A minimal outcome (no HP delta, no field changes, just a switch flag)
    outcome = TurnOutcome()
    outcome.flags.add("switch:p1a")

    # This is the call that crashed before the fix:
    #   _apply_switches sees roster_by_side["p1"]["Flutter Mane"]
    #   -> KeyError -> ValueError: switch target 'Flutter Mane' not in roster
    # After the fix it must succeed without raising.
    try:
        nxt = apply_outcome_to_state(
            state,
            outcome,
            actions_by_side={"p1": switch_action},
            roster_by_side={"p1": bs.roster, "p2": {}},
        )
    except ValueError as e:
        pytest.fail(
            f"apply_outcome_to_state raised ValueError (the switch-roster crash): {e}\n"
            f"  roster keys: {list(bs.roster)}\n"
            f"  target_ident: 'Flutter Mane'"
        )

    # Confirm the switch actually took effect (Flutter Mane moved to slot "a")
    assert nxt.sides["p1"]["a"].species == "Flutter Mane", (
        f"Expected slot 'a' to become Flutter Mane after switch, "
        f"got {nxt.sides['p1']['a'].species!r}"
    )
    # Input state must be unchanged (clone semantics)
    assert state.sides["p1"]["a"].species == "Incineroar", (
        "apply_outcome_to_state must not mutate the input state"
    )

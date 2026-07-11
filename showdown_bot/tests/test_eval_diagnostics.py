"""Tests for eval/diagnostics.py -- diagnostics v0 schema + 3 detectors (Task 1).

Naming note: ``tests/test_diagnostics.py`` already exists for the unrelated live-battle
formatting module ``showdown_bot.battle.diagnostics``. This file follows the repo's existing
``test_eval_<module>.py`` convention (see ``test_eval_pairing.py``, ``test_eval_report.py``,
``test_eval_stats.py``) to avoid colliding with it.

Fixtures are hand-authored, already-normalized ``list[str]`` protocol-line logs, shaped like
the real fixture in ``data/eval/t4/rerun/room_raw`` (verified by gunzipping one during Task 1).
"""
from __future__ import annotations

from showdown_bot.eval.diagnostics import (
    DiagnosticEvent,
    _iter_turns,
    detect_attack_into_protect,
    detect_immunity_punished,
    detect_panic_switching,
    diagnose_battle,
)

# --- ATTACK_INTO_PROTECT fixtures ------------------------------------------------------------

_ATTACK_INTO_PROTECT_POSITIVE = [
    "|turn|3",
    "|move|p1a: Incineroar|Knock Off|p2b: Torkoal",
    "|-activate|p2b: Torkoal|move: Protect",
    "|turn|4",
]

_ATTACK_NOT_PROTECTED = [
    "|turn|3",
    "|move|p1a: Incineroar|Knock Off|p2b: Torkoal",
    "|-damage|p2b: Torkoal|50/100",
    "|turn|4",
]

_STATUS_SELF_PROTECT_NOT_COUNTED = [
    "|turn|2",
    "|move|p1a: Incineroar|Protect|p1a: Incineroar",
    "|-singleturn|p1a: Incineroar|Protect",
    "|turn|3",
]

# --- IMMUNITY_PUNISHED fixtures ---------------------------------------------------------------

_IMMUNE_POSITIVE = [
    "|turn|5",
    "|move|p1a: Landorus|Earth Power|p2a: Tornadus",
    "|-immune|p2a: Tornadus",
    "|turn|6",
]

_SUPEREFFECTIVE_NOT_IMMUNE = [
    "|turn|5",
    "|move|p1a: Landorus|Earth Power|p2a: Torkoal",
    "|-supereffective|p2a: Torkoal",
    "|-damage|p2a: Torkoal|10/100",
    "|turn|6",
]

# --- PANIC_SWITCHING fixtures ------------------------------------------------------------------

_PANIC_POSITIVE = [
    "|turn|1",
    "|switch|p1a: Incineroar|Incineroar, L50, M|100/100",
    "|turn|2",
    "|switch|p1a: Rillaboom|Rillaboom, L50, M|100/100",
    "|turn|3",
    "|switch|p1a: Incineroar|Incineroar, L50, M|80/100",
    "|turn|4",
]

_PANIC_NEGATIVE_FAINT_BETWEEN = [
    "|turn|1",
    "|switch|p1a: Incineroar|Incineroar, L50, M|100/100",
    "|turn|2",
    "|switch|p1a: Rillaboom|Rillaboom, L50, M|100/100",
    "|turn|3",
    "|faint|p1b: Tornadus",
    "|switch|p1a: Incineroar|Incineroar, L50, M|80/100",
    "|turn|4",
]


# --- ATTACK_INTO_PROTECT tests -----------------------------------------------------------------

def test_attack_into_protect_fires():
    events = detect_attack_into_protect(_ATTACK_INTO_PROTECT_POSITIVE, battle_id="b1")
    assert len(events) == 1
    e = events[0]
    assert isinstance(e, DiagnosticEvent)
    assert e.battle_id == "b1"
    assert e.turn == 3
    assert e.side == "p1"
    assert e.bucket == "ATTACK_INTO_PROTECT"
    assert e.severity == "warn"
    assert e.action == "Knock Off"
    assert e.target == "p2b: Torkoal"
    assert list(e.evidence.keys()) == sorted(e.evidence.keys())


def test_attack_into_non_protected_target_does_not_fire():
    events = detect_attack_into_protect(_ATTACK_NOT_PROTECTED, battle_id="b1")
    assert events == []


def test_status_move_self_protect_does_not_fire():
    events = detect_attack_into_protect(_STATUS_SELF_PROTECT_NOT_COUNTED, battle_id="b1")
    assert events == []


# --- IMMUNITY_PUNISHED tests -------------------------------------------------------------------

def test_immunity_punished_fires():
    events = detect_immunity_punished(_IMMUNE_POSITIVE, battle_id="b1")
    assert len(events) == 1
    e = events[0]
    assert e.turn == 5
    assert e.side == "p1"
    assert e.bucket == "IMMUNITY_PUNISHED"
    assert e.severity == "warn"
    assert e.action == "Earth Power"
    assert e.target == "p2a: Tornadus"
    assert list(e.evidence.keys()) == sorted(e.evidence.keys())


def test_supereffective_does_not_fire_immunity():
    events = detect_immunity_punished(_SUPEREFFECTIVE_NOT_IMMUNE, battle_id="b1")
    assert events == []


# --- PANIC_SWITCHING tests ----------------------------------------------------------------------

def test_panic_switching_oscillation_fires():
    events = detect_panic_switching(_PANIC_POSITIVE, battle_id="b1")
    assert len(events) == 1
    e = events[0]
    assert e.turn == 3
    assert e.side == "p1"
    assert e.bucket == "PANIC_SWITCHING"
    assert e.severity == "warn"
    assert e.action == "p1a"
    assert e.target == "Incineroar"
    assert e.evidence["species_a"] == "Incineroar"
    assert e.evidence["species_b"] == "Rillaboom"
    assert e.evidence["turns"] == [1, 2, 3]
    assert list(e.evidence.keys()) == sorted(e.evidence.keys())


def test_panic_switching_with_faint_between_does_not_fire():
    events = detect_panic_switching(_PANIC_NEGATIVE_FAINT_BETWEEN, battle_id="b1")
    assert events == []


# --- determinism + malformed-line tolerance -----------------------------------------------------

def test_diagnose_battle_is_deterministic():
    a = diagnose_battle(_ATTACK_INTO_PROTECT_POSITIVE, battle_id="b1")
    b = diagnose_battle(_ATTACK_INTO_PROTECT_POSITIVE, battle_id="b1")
    assert a == b
    assert len(a) == 1


def test_malformed_line_is_skipped_others_still_detected():
    frames = [
        "|turn|3",
        "garbage line without pipes",
        "|move|p1a: Incineroar|Knock Off|p2b: Torkoal",
        "|-activate|p2b: Torkoal|move: Protect",
        "|turn|banana",  # malformed turn marker -- tolerated, turn counter just increments
        "|move|p1a: Incineroar|Knock Off|p2b: Torkoal",
        "|-activate|p2b: Torkoal|move: Protect",
        "|turn|5",
    ]
    events = detect_attack_into_protect(frames, battle_id="bmal")
    assert len(events) == 2


def test_diagnose_battle_runs_all_detectors_and_sorts():
    frames = _ATTACK_INTO_PROTECT_POSITIVE + _IMMUNE_POSITIVE
    events = diagnose_battle(frames, battle_id="bmix")
    assert [e.bucket for e in events] == ["ATTACK_INTO_PROTECT", "IMMUNITY_PUNISHED"]
    assert [e.turn for e in events] == [3, 5]


# --- _iter_turns sanity ---------------------------------------------------------------------------

def test_iter_turns_buckets_by_turn_marker_turn_zero_is_pre_first_turn():
    frames = [
        "|switch|p1a: Incineroar|Incineroar, L50, M|100/100",
        "|turn|1",
        "|move|p1a: Incineroar|Tackle|p2a: X",
        "|turn|2",
        "|move|p1a: Incineroar|Tackle|p2a: X",
    ]
    turns = list(_iter_turns(frames))
    assert turns[0] == (0, ["|switch|p1a: Incineroar|Incineroar, L50, M|100/100"])
    assert turns[1] == (1, ["|move|p1a: Incineroar|Tackle|p2a: X"])
    assert turns[2] == (2, ["|move|p1a: Incineroar|Tackle|p2a: X"])

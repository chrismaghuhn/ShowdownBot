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
    aggregate,
    bucket_delta,
    detect_attack_into_protect,
    detect_immunity_punished,
    detect_panic_switching,
    diagnose_battle,
    diagnose_run,
    format_diagnostics_md,
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


# ================================================================================================
# Task 2: aggregation + candidate-vs-baseline bucket delta
# ================================================================================================

def _ev(battle_id, turn, side, bucket, severity="warn", action="mv", target="tgt"):
    """Fabricate a DiagnosticEvent for aggregate()/bucket_delta() tests (no real detection)."""
    return DiagnosticEvent(
        battle_id=battle_id,
        turn=turn,
        side=side,
        bucket=bucket,
        severity=severity,
        action=action,
        target=target,
        evidence={},
    )


_NOT_A_GATE_SNIPPET = "NOT a gate; strength gate stays paired McNemar/winrate"


# --- aggregate() ---------------------------------------------------------------------------------

def test_aggregate_counts_and_severity_correct():
    events = [
        _ev("b1", 1, "p1", "ATTACK_INTO_PROTECT", severity="warn"),
        _ev("b1", 2, "p1", "ATTACK_INTO_PROTECT", severity="fail"),
        _ev("b2", 1, "p2", "IMMUNITY_PUNISHED", severity="warn"),
        _ev("b2", 3, "p1", "IMMUNITY_PUNISHED", severity="info"),
    ]
    agg = aggregate(events)

    assert agg["ATTACK_INTO_PROTECT"]["count"] == 2
    assert agg["ATTACK_INTO_PROTECT"]["by_severity"] == {"info": 0, "warn": 1, "fail": 1}
    assert agg["IMMUNITY_PUNISHED"]["count"] == 2
    assert agg["IMMUNITY_PUNISHED"]["by_severity"] == {"info": 1, "warn": 1, "fail": 0}
    # PANIC_SWITCHING is unobserved but must still be present, zero-filled.
    assert agg["PANIC_SWITCHING"]["count"] == 0
    assert agg["PANIC_SWITCHING"]["by_severity"] == {"info": 0, "warn": 0, "fail": 0}
    assert agg["total"] == 4
    assert agg["n_battles"] == 2  # distinct battle_id: b1, b2


def test_aggregate_empty_events_is_all_zero():
    agg = aggregate([])
    assert agg["total"] == 0
    assert agg["n_battles"] == 0
    for bucket in ("ATTACK_INTO_PROTECT", "IMMUNITY_PUNISHED", "PANIC_SWITCHING"):
        assert agg[bucket] == {"count": 0, "by_severity": {"info": 0, "warn": 0, "fail": 0}}


def test_aggregate_bucket_keys_sorted_and_deterministic():
    events = [_ev("b1", 1, "p1", "PANIC_SWITCHING")]
    agg = aggregate(events)
    bucket_keys = [k for k in agg if k in ("ATTACK_INTO_PROTECT", "IMMUNITY_PUNISHED", "PANIC_SWITCHING")]
    assert bucket_keys == sorted(bucket_keys)
    assert aggregate(events) == aggregate(events)


# --- diagnose_run() --------------------------------------------------------------------------

def test_diagnose_run_skips_unparseable_battle_and_tallies_parse_skipped():
    battles = [
        ("good1", _ATTACK_INTO_PROTECT_POSITIVE),
        ("bad1", None),  # not iterable -> raises deep inside diagnose_battle
        ("good2", _IMMUNE_POSITIVE),
    ]
    events, agg = diagnose_run(battles)

    assert [e.battle_id for e in events] == ["good1", "good2"]
    assert agg["parse_skipped"] == 1
    assert agg["battles_total"] == 3
    assert agg["n_battles"] == 2
    assert agg["total"] == 2


def test_diagnose_run_all_battles_parse_ok_zero_skipped():
    battles = [("good1", _ATTACK_INTO_PROTECT_POSITIVE), ("good2", _IMMUNE_POSITIVE)]
    events, agg = diagnose_run(battles)

    assert len(events) == 2
    assert agg["parse_skipped"] == 0
    assert agg["battles_total"] == 2


def test_diagnose_run_all_unparseable_still_surfaces_tally_not_silent():
    battles = [("bad1", None), ("bad2", 12345)]
    events, agg = diagnose_run(battles)

    assert events == []
    assert agg["parse_skipped"] == 2
    assert agg["battles_total"] == 2
    assert agg["total"] == 0


# --- bucket_delta() --------------------------------------------------------------------------

def test_bucket_delta_candidate_improves_when_fewer_events():
    events_a = [
        _ev("a1", 1, "p1", "ATTACK_INTO_PROTECT"),
        _ev("a1", 2, "p1", "ATTACK_INTO_PROTECT"),
    ]
    events_b: list = []
    delta = bucket_delta(events_a, events_b, hero_side_a="p1", hero_side_b="p1")

    assert delta["per_bucket"]["ATTACK_INTO_PROTECT"] == {"a_count": 2, "b_count": 0, "delta": -2}
    assert delta["verdict_per_bucket"]["ATTACK_INTO_PROTECT"] == "candidate_improves"


def test_bucket_delta_candidate_regresses_when_more_events():
    events_a: list = []
    events_b = [
        _ev("b1", 1, "p1", "IMMUNITY_PUNISHED"),
        _ev("b1", 2, "p1", "IMMUNITY_PUNISHED"),
        _ev("b1", 3, "p1", "IMMUNITY_PUNISHED"),
    ]
    delta = bucket_delta(events_a, events_b, hero_side_a="p1", hero_side_b="p1")

    assert delta["per_bucket"]["IMMUNITY_PUNISHED"] == {"a_count": 0, "b_count": 3, "delta": 3}
    assert delta["verdict_per_bucket"]["IMMUNITY_PUNISHED"] == "candidate_regresses"


def test_bucket_delta_flat_when_equal():
    events_a = [_ev("a1", 1, "p1", "PANIC_SWITCHING")]
    events_b = [_ev("b1", 1, "p1", "PANIC_SWITCHING")]
    delta = bucket_delta(events_a, events_b, hero_side_a="p1", hero_side_b="p1")

    assert delta["per_bucket"]["PANIC_SWITCHING"] == {"a_count": 1, "b_count": 1, "delta": 0}
    assert delta["verdict_per_bucket"]["PANIC_SWITCHING"] == "flat"


def test_bucket_delta_filters_by_hero_side_and_allows_different_sides():
    # baseline hero is p1: the p2-side event must NOT be counted.
    events_a = [
        _ev("a1", 1, "p1", "ATTACK_INTO_PROTECT"),
        _ev("a1", 1, "p2", "ATTACK_INTO_PROTECT"),
    ]
    # candidate hero is p2 (deliberately different side than the baseline hero).
    events_b = [_ev("b1", 1, "p2", "ATTACK_INTO_PROTECT")]
    delta = bucket_delta(events_a, events_b, hero_side_a="p1", hero_side_b="p2")

    assert delta["per_bucket"]["ATTACK_INTO_PROTECT"] == {"a_count": 1, "b_count": 1, "delta": 0}
    assert delta["verdict_per_bucket"]["ATTACK_INTO_PROTECT"] == "flat"
    assert delta["hero_side_a"] == "p1"
    assert delta["hero_side_b"] == "p2"


def test_bucket_delta_every_bucket_present_even_if_unobserved():
    delta = bucket_delta([], [], hero_side_a="p1", hero_side_b="p1")
    all_buckets = {"ATTACK_INTO_PROTECT", "IMMUNITY_PUNISHED", "PANIC_SWITCHING"}

    assert set(delta["per_bucket"]) == all_buckets
    assert set(delta["verdict_per_bucket"]) == all_buckets
    for bucket in all_buckets:
        assert delta["per_bucket"][bucket] == {"a_count": 0, "b_count": 0, "delta": 0}
        assert delta["verdict_per_bucket"][bucket] == "flat"


def test_bucket_delta_note_embeds_not_a_gate_invariant():
    delta = bucket_delta([], [], hero_side_a="p1", hero_side_b="p1")
    assert delta["note"] == (
        "diagnostic signal only — NOT a gate; strength gate stays paired McNemar/winrate"
    )


# --- format_diagnostics_md() -------------------------------------------------------------------

def test_format_diagnostics_md_has_bucket_table_and_not_a_gate_note():
    agg = aggregate([_ev("b1", 1, "p1", "ATTACK_INTO_PROTECT")])
    md = format_diagnostics_md(agg)

    assert "ATTACK_INTO_PROTECT" in md
    assert "IMMUNITY_PUNISHED" in md
    assert "PANIC_SWITCHING" in md
    assert "parse_skipped" in md
    assert _NOT_A_GATE_SNIPPET in md


def test_format_diagnostics_md_with_delta_includes_delta_table():
    agg = aggregate([])
    delta = bucket_delta(
        [_ev("a1", 1, "p1", "ATTACK_INTO_PROTECT")], [], hero_side_a="p1", hero_side_b="p1"
    )
    md = format_diagnostics_md(agg, delta=delta)

    assert "Candidate vs baseline" in md
    assert "candidate_improves" in md
    assert _NOT_A_GATE_SNIPPET in md


def test_format_diagnostics_md_without_delta_omits_delta_section():
    agg = aggregate([])
    md = format_diagnostics_md(agg)
    assert "Candidate vs baseline" not in md


def test_format_diagnostics_md_surfaces_parse_skipped_from_diagnose_run():
    battles = [("good", _ATTACK_INTO_PROTECT_POSITIVE), ("bad", None)]
    _events, agg = diagnose_run(battles)
    md = format_diagnostics_md(agg)
    assert "parse_skipped: 1" in md


def test_format_diagnostics_md_is_deterministic():
    agg = aggregate([_ev("b1", 1, "p1", "ATTACK_INTO_PROTECT"), _ev("b2", 2, "p2", "PANIC_SWITCHING")])
    assert format_diagnostics_md(agg) == format_diagnostics_md(agg)

"""Split `invalid_choices` per seat (Gate B finding 5).

Established defect, recorded on `main` in
`docs/projects/champions/audits/2026-07-24-b1-live-verification-and-gate-integrity-findings.md`:
`stats.invalid_choices = hero.invalid + villain.invalid` -- one number that cannot be attributed.
A BASELINE-side illegal action fails the CANDIDATE and consumes a held-out ledger slot, with
nothing on the row able to show it.

Mirrors PR #68's fix for finding 4 EXACTLY (same shape: per-seat deltas in
`_PerBattleCounters.emit`, threaded through `_battle_result_record`, declared nullable on the
closed T2 schema, gated separately in `compute_safety_pass`). Reuses its helpers rather than
duplicating them.

`invalid_choices` itself is UNCHANGED and NOT removed: it stays "sum, historical" so the frozen
Gate B evidence and any existing consumer keeps reading it. The gate stops depending on it.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------------------------
# Per-battle deltas: hero and villain invalid counts, mirroring hero_degraded/villain_degraded.
# ---------------------------------------------------------------------------------------------

def test_per_battle_counters_emit_per_seat_invalid_deltas():
    from showdown_bot.client.gauntlet import _PerBattleCounters

    c = _PerBattleCounters()
    first = c.emit(invalid=3, crashes=0, latencies=[], hero_invalid=2, villain_invalid=1)
    assert first["hero_invalid_choices"] == 2
    assert first["villain_invalid_choices"] == 1
    # invalid_choices (the existing summed field) is UNCHANGED behaviour.
    assert first["invalid_choices"] == 3
    # Cumulative client counters -> the SECOND battle carries its own delta, not the total.
    second = c.emit(invalid=5, crashes=0, latencies=[], hero_invalid=3, villain_invalid=3)
    assert second["hero_invalid_choices"] == 1
    assert second["villain_invalid_choices"] == 2
    assert second["invalid_choices"] == 2


def test_per_battle_counters_default_seat_invalid_to_zero():
    """A caller that does not pass hero_invalid/villain_invalid (none currently exists, but the
    default must be safe) gets zero deltas, mirroring hero_degraded/villain_degraded's defaults."""
    from showdown_bot.client.gauntlet import _PerBattleCounters

    c = _PerBattleCounters()
    d = c.emit(invalid=0, crashes=0, latencies=[])
    assert d["hero_invalid_choices"] == 0
    assert d["villain_invalid_choices"] == 0


def test_battle_result_record_carries_both_seats_invalid_separately():
    from showdown_bot.client.gauntlet import _battle_result_record

    frames = ["|player|p1|hero|", "|player|p2|villain|", "|turn|1", "|win|hero"]
    record = _battle_result_record(
        "hero", "villain", frames,
        invalid_choices=4, crashes=0, decision_latency_p95_ms=1, room_raw_path=None,
        hero_invalid_choices=3, villain_invalid_choices=1,
    )
    assert record["invalid_choices"] == 4          # unchanged, still the sum
    assert record["hero_invalid_choices"] == 3
    assert record["villain_invalid_choices"] == 1


def test_battle_result_record_defaults_seat_invalid_to_zero():
    from showdown_bot.client.gauntlet import _battle_result_record

    frames = ["|player|p1|hero|", "|player|p2|villain|", "|turn|1", "|win|hero"]
    record = _battle_result_record(
        "hero", "villain", frames,
        invalid_choices=0, crashes=0, decision_latency_p95_ms=1, room_raw_path=None,
    )
    assert record["hero_invalid_choices"] == 0
    assert record["villain_invalid_choices"] == 0


# ---------------------------------------------------------------------------------------------
# The closed T2 row schema: new fields nullable, type-checked exactly like the degraded counters.
# ---------------------------------------------------------------------------------------------

def _valid_row() -> dict:
    return {
        "battle_id": "b0", "run_id": "r", "config_id": "heuristic",
        "format_id": "gen9championsvgc2026regma", "config_hash": "cfg", "schedule_hash": "s",
        "seed_index": 0, "opp_policy": "heuristic", "hero_team_path": "h.txt",
        "opp_team_path": "o.txt", "seed": "0", "seed_base": "b", "winner": "hero", "turns": 5,
        "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10,
        "git_sha": "deadbeef", "dirty": False, "end_reason": "normal",
    }


def test_the_closed_row_schema_accepts_the_new_seat_fields():
    from showdown_bot.eval.result_jsonl import validate_battle_row

    row = _valid_row()
    row["hero_invalid_choices"] = 1
    row["villain_invalid_choices"] = 0
    validate_battle_row(row)          # must not raise


def test_the_closed_row_schema_still_accepts_a_legacy_row_without_them():
    """Rows written before this field existed -- including every frozen Gate B row on `main` --
    must still validate. `invalid_choices` (unchanged) is what those rows carry."""
    from showdown_bot.eval.result_jsonl import validate_battle_row

    validate_battle_row(_valid_row())


@pytest.mark.parametrize("bad", [-1, True, 1.0, "3"])
@pytest.mark.parametrize("field", ["hero_invalid_choices", "villain_invalid_choices"])
def test_the_row_schema_rejects_a_type_wrong_seat_invalid_count(field, bad):
    from showdown_bot.eval.result_jsonl import ResultRowError, validate_battle_row

    row = _valid_row()
    row[field] = bad
    with pytest.raises(ResultRowError):
        validate_battle_row(row)


# ---------------------------------------------------------------------------------------------
# The Gate B arm's closed callback whitelist must admit the new fields.
# ---------------------------------------------------------------------------------------------

def test_the_gate_b_callback_whitelist_admits_the_new_seat_fields():
    from showdown_bot.eval.strength_holdout_runner import _CALLBACK_RECORD_FIELDS

    assert {"hero_invalid_choices", "villain_invalid_choices"} <= _CALLBACK_RECORD_FIELDS
    # invalid_choices (the existing summed field) is STILL required -- unchanged, not removed.
    assert "invalid_choices" in _CALLBACK_RECORD_FIELDS


# ---------------------------------------------------------------------------------------------
# compute_safety_pass: each seat gated SEPARATELY, with its own rationale, mirroring the
# degraded-decision gating exactly. The three RED scenarios the order asks for by name.
# ---------------------------------------------------------------------------------------------

def _gate_row(*, hero_invalid=0, villain_invalid=0, hero_degraded=0, villain_degraded=0) -> dict:
    row = _valid_row()
    row["hero_invalid_choices"] = hero_invalid
    row["villain_invalid_choices"] = villain_invalid
    row["hero_degraded_decisions"] = hero_degraded
    row["villain_degraded_decisions"] = villain_degraded
    return row


def test_safety_pass_still_passes_a_clean_row():
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    assert compute_safety_pass([_gate_row()], [_gate_row()])


def test_safety_pass_refuses_a_hero_side_invalid_choice():
    """(b) from the order: a hero-side invalid choice still fails."""
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    assert not compute_safety_pass([_gate_row(hero_invalid=1)], [_gate_row()])
    assert not compute_safety_pass([_gate_row()], [_gate_row(hero_invalid=1)])


def test_safety_pass_refuses_a_villain_side_invalid_choice_attributably():
    """(a) from the order: a row where ONLY the villain has an invalid choice must still fail --
    but the failure must be attributable to that seat, not misread as the candidate's fault. The
    row itself carries the attribution: hero_invalid_choices stays 0."""
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    row = _gate_row(villain_invalid=1)
    assert row["hero_invalid_choices"] == 0
    assert row["villain_invalid_choices"] == 1
    assert not compute_safety_pass([row], [_gate_row()])


def test_safety_pass_fails_CLOSED_when_a_seat_invalid_counter_is_absent():
    """(c) from the order: a missing counter fails closed, consistent with the degraded
    counters -- absent must never read as zero."""
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    row = _gate_row()
    del row["hero_invalid_choices"]
    assert not compute_safety_pass([row], [_gate_row()])

    row2 = _gate_row()
    del row2["villain_invalid_choices"]
    assert not compute_safety_pass([row2], [_gate_row()])


@pytest.mark.parametrize("bad", [True, 1.0, "0", None, -1])
def test_safety_pass_rejects_a_type_wrong_seat_invalid_counter(bad):
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    row = _gate_row()
    row["hero_invalid_choices"] = bad
    assert not compute_safety_pass([row], [_gate_row()])


def test_the_two_invalid_seats_are_never_summed_by_a_producer():
    """The non-conflation guard PR #68 established for the degraded counters, mirrored for the
    invalid counters: no producer collapses hero_invalid_choices + villain_invalid_choices into
    one field (that would recreate finding 5 in a new field)."""
    import inspect

    from showdown_bot.client.gauntlet import _battle_result_record, _PerBattleCounters

    for fn in (_battle_result_record, _PerBattleCounters.emit):
        src = inspect.getsource(fn)
        assert "hero_invalid" in src and "villain_invalid" in src
        for summed in ("hero_invalid + villain_invalid",
                       "hero.invalid_choices + villain.invalid_choices",
                       "invalid_choices\": hero_invalid + "):
            assert summed not in src, (fn.__name__, summed)


def test_existing_invalid_choices_field_is_unchanged_not_repurposed():
    """The order is explicit: keep invalid_choices as-is, sum/historical. This is a behavioural
    pin, not just a schema check -- the summed value from the two seats must still equal what the
    OLD code would have produced."""
    from showdown_bot.client.gauntlet import _PerBattleCounters

    c = _PerBattleCounters()
    d = c.emit(invalid=7, crashes=0, latencies=[], hero_invalid=4, villain_invalid=3)
    assert d["invalid_choices"] == 7 == d["hero_invalid_choices"] + d["villain_invalid_choices"]

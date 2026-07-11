"""2b-4 Task 3: unit tests for eval.identity.compare_identity (the pure double-run identity
check). Fabricated result-row fixtures only -- no battles, no file I/O (see the module
docstring's rationale for why this is a new, small module rather than an extension of an
existing one)."""
from __future__ import annotations

from showdown_bot.eval.identity import IdentityReport, compare_identity


def _row(seed_index, *, winner="hero", turns=12, log_sha="deadbeef", battle_id=None):
    return {
        "seed_index": seed_index,
        "battle_id": battle_id or f"b{seed_index}",
        "winner": winner,
        "turns": turns,
        "normalized_room_log_sha256": log_sha,
    }


def _identical_pair(n=3):
    rows_a = [_row(i) for i in range(n)]
    rows_b = [_row(i) for i in range(n)]
    return rows_a, rows_b


# --- identical fixtures --------------------------------------------------------------------

def test_identical_two_tiny_runs_report_identical():
    rows_a, rows_b = _identical_pair(3)

    report = compare_identity(rows_a, rows_b)

    assert report == IdentityReport(identical=True, n_compared=3, diffs=())


def test_identical_runs_out_of_order_still_identical():
    # seed_index pairing, not list-position pairing.
    rows_a = [_row(0), _row(1), _row(2)]
    rows_b = [_row(2), _row(0), _row(1)]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is True
    assert report.n_compared == 3
    assert report.diffs == ()


def test_identical_single_battle():
    rows_a = [_row(0, winner="villain", turns=7, log_sha="abc123")]
    rows_b = [_row(0, winner="villain", turns=7, log_sha="abc123")]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is True
    assert report.n_compared == 1


# --- one-diff fixtures ----------------------------------------------------------------------

def test_one_diff_winner_mismatch_detected():
    rows_a = [_row(0), _row(1, winner="villain"), _row(2)]
    rows_b = [_row(0), _row(1, winner="hero"), _row(2)]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert report.n_compared == 3
    assert report.diffs == (
        {"seed_index": 1, "field": "winner", "a": "villain", "b": "hero"},
    )


def test_one_diff_turns_mismatch_detected():
    rows_a = [_row(0, turns=10)]
    rows_b = [_row(0, turns=11)]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert report.diffs == ({"seed_index": 0, "field": "turns", "a": 10, "b": 11},)


def test_one_diff_log_sha_mismatch_detected():
    rows_a = [_row(0, log_sha="hash-a")]
    rows_b = [_row(0, log_sha="hash-b")]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert report.diffs == (
        {"seed_index": 0, "field": "normalized_room_log_sha256", "a": "hash-a", "b": "hash-b"},
    )


def test_multiple_fields_differ_on_one_battle_yields_multiple_diff_entries():
    rows_a = [_row(0, winner="hero", turns=10, log_sha="hash-a")]
    rows_b = [_row(0, winner="villain", turns=11, log_sha="hash-b")]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert len(report.diffs) == 3
    fields = {d["field"] for d in report.diffs}
    assert fields == {"winner", "turns", "normalized_room_log_sha256"}


def test_diff_in_one_battle_does_not_affect_others():
    rows_a = [_row(0), _row(1, winner="villain"), _row(2)]
    rows_b = [_row(0), _row(1, winner="hero"), _row(2)]

    report = compare_identity(rows_a, rows_b)

    assert report.n_compared == 3
    assert len(report.diffs) == 1
    assert report.diffs[0]["seed_index"] == 1


# --- structural (missing-row) mismatches -----------------------------------------------------

def test_missing_seed_index_in_b_becomes_missing_diff_not_a_raise():
    rows_a = [_row(0), _row(1)]
    rows_b = [_row(0)]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert report.n_compared == 1  # only seed_index 0 is comparable on both sides
    assert report.diffs == (
        {"seed_index": 1, "field": "_missing", "a": "b1", "b": None},
    )


def test_missing_seed_index_in_a_becomes_missing_diff():
    rows_a = [_row(0)]
    rows_b = [_row(0), _row(1)]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert report.diffs == (
        {"seed_index": 1, "field": "_missing", "a": None, "b": "b1"},
    )


def test_empty_both_runs_is_identical_with_zero_compared():
    report = compare_identity([], [])

    assert report == IdentityReport(identical=True, n_compared=0, diffs=())


# --- normalized_room_log_sha256 can be legitimately null (T4c: hashing failure never fails
# the battle record) -- None == None must not be flagged as a diff. ------------------------

def test_both_null_log_sha_is_not_a_diff():
    rows_a = [_row(0, log_sha=None)]
    rows_b = [_row(0, log_sha=None)]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is True


def test_null_vs_present_log_sha_is_a_diff():
    rows_a = [_row(0, log_sha=None)]
    rows_b = [_row(0, log_sha="hash-b")]

    report = compare_identity(rows_a, rows_b)

    assert report.identical is False
    assert report.diffs == (
        {"seed_index": 0, "field": "normalized_room_log_sha256", "a": None, "b": "hash-b"},
    )

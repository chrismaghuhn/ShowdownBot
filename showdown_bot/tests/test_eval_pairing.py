"""Tests for eval/pairing.py — the pairing validator (T5 Task 2).

Fail-fast: every violation gets its own exception subclass of PairingError, never a
warn-and-continue path. Spec: docs/superpowers/specs/2026-07-10-t5-report-generator-design.md
§1.2. Rationale: docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-architecture-review.md §2.
"""
from __future__ import annotations

import pytest

from showdown_bot.eval.pairing import (
    DuplicateRowError,
    MissingPairError,
    Pair,
    PairingError,
    PairSeedMismatchError,
    RowCountError,
    RunMismatchError,
    SelfComparisonError,
    pair_runs,
)
from showdown_bot.eval.stats import mcnemar_counts


def _row(seed_index, *, config_hash="cfgA", winner="hero", schedule_hash="sched1",
         seed_base="base1", panel_hash="pan1", format_id="gen9vgc2025regi",
         opp_policy="heuristic", opp_team_hash="team1", seed=None, battle_id=None):
    return {
        "battle_id": battle_id or f"b{seed_index}", "config_hash": config_hash,
        "schedule_hash": schedule_hash, "seed_base": seed_base, "panel_hash": panel_hash,
        "format_id": format_id, "seed_index": seed_index, "opp_policy": opp_policy,
        "opp_team_hash": opp_team_hash, "seed": seed or f"sodium,{seed_index:032x}",
        "winner": winner,
    }


# --- exception hierarchy -----------------------------------------------------------

def test_exception_hierarchy():
    assert issubclass(PairingError, ValueError)
    for exc in (
        SelfComparisonError, RunMismatchError, PairSeedMismatchError,
        DuplicateRowError, MissingPairError, RowCountError,
    ):
        assert issubclass(exc, PairingError)


# --- happy path + tie semantics (from the plan, verbatim) --------------------------

def test_pair_runs_happy_path_and_tie_semantics():
    a = [_row(0, winner="hero"), _row(1, winner="villain"), _row(2, winner="tie")]
    b = [_row(0, winner="villain", config_hash="cfgB"),
         _row(1, winner="hero", config_hash="cfgB"),
         _row(2, winner="hero", config_hash="cfgB")]
    pairs = pair_runs(a, b)
    assert [(p.hero_win_a, p.hero_win_b) for p in pairs] == [
        (True, False), (False, True), (False, True)]          # tie = not-a-win
    assert pairs[0].cell == ("heuristic", "team1")
    counts = mcnemar_counts([(p.hero_win_a, p.hero_win_b) for p in pairs])
    assert (counts.n10, counts.n01) == (1, 2)


def test_pair_runs_sorted_by_seed_index():
    a = [_row(2), _row(0), _row(1)]
    b = [_row(2, config_hash="cfgB"), _row(0, config_hash="cfgB"), _row(1, config_hash="cfgB")]
    pairs = pair_runs(a, b)
    assert [p.seed_index for p in pairs] == [0, 1, 2]
    assert [p.battle_id for p in pairs] == ["b0", "b1", "b2"]


def test_pair_is_frozen_dataclass_with_expected_fields():
    a = [_row(0)]
    b = [_row(0, config_hash="cfgB")]
    pair = pair_runs(a, b)[0]
    assert isinstance(pair, Pair)
    assert pair.battle_id == "b0"
    assert pair.seed_index == 0
    assert pair.cell == ("heuristic", "team1")
    assert pair.row_a["config_hash"] == "cfgA"
    assert pair.row_b["config_hash"] == "cfgB"
    with pytest.raises(Exception):
        pair.battle_id = "mutated"  # frozen


# --- SelfComparisonError ------------------------------------------------------------

def test_self_comparison_error_on_equal_config_hash():
    a = [_row(0), _row(1)]
    b = [_row(0), _row(1)]  # identical config_hash "cfgA" -> refuse self-comparison
    with pytest.raises(SelfComparisonError):
        pair_runs(a, b)


# --- RunMismatchError: cross-run, parametrized over the four pairability fields ----

@pytest.mark.parametrize("field", ["schedule_hash", "seed_base", "panel_hash", "format_id"])
def test_run_mismatch_error_cross_run(field):
    a = [_row(0), _row(1)]
    b = [_row(0, config_hash="cfgB", **{field: "different"}),
         _row(1, config_hash="cfgB", **{field: "different"})]
    with pytest.raises(RunMismatchError):
        pair_runs(a, b)


# --- RunMismatchError: non-constant within a single run -----------------------------

@pytest.mark.parametrize(
    "field", ["schedule_hash", "seed_base", "panel_hash", "format_id", "config_hash"]
)
def test_run_mismatch_error_non_constant_within_run(field):
    a = [_row(0), _row(1, **{field: "different"})]
    b = [_row(0, config_hash="cfgB"), _row(1, config_hash="cfgB")]
    with pytest.raises(RunMismatchError):
        pair_runs(a, b)


# --- PairSeedMismatchError -----------------------------------------------------------

def test_pair_seed_mismatch_error():
    a = [_row(0), _row(1)]
    b = [_row(0, config_hash="cfgB", seed="not-the-same-seed"), _row(1, config_hash="cfgB")]
    with pytest.raises(PairSeedMismatchError):
        pair_runs(a, b)


# --- DuplicateRowError ----------------------------------------------------------------

def test_duplicate_row_error_within_run():
    a = [_row(0), _row(0)]  # same (battle_id, config_hash) twice
    b = [_row(0, config_hash="cfgB")]
    with pytest.raises(DuplicateRowError):
        pair_runs(a, b)


# --- MissingPairError -------------------------------------------------------------------

def test_missing_pair_error_row_count_differs():
    a = [_row(0), _row(1)]
    b = [_row(0, config_hash="cfgB")]
    with pytest.raises(MissingPairError):
        pair_runs(a, b)


def test_missing_pair_error_battle_id_only_on_one_side():
    a = [_row(0), _row(1)]
    b = [_row(0, config_hash="cfgB"), _row(1, config_hash="cfgB", battle_id="different")]
    with pytest.raises(MissingPairError):
        pair_runs(a, b)


# --- RowCountError (expected_rows kwarg) --------------------------------------------------

def test_row_count_error_expected_rows_mismatch():
    a = [_row(0), _row(1)]
    b = [_row(0, config_hash="cfgB"), _row(1, config_hash="cfgB")]
    with pytest.raises(RowCountError):
        pair_runs(a, b, expected_rows=3)


def test_expected_rows_ok_when_matching():
    a = [_row(0), _row(1)]
    b = [_row(0, config_hash="cfgB"), _row(1, config_hash="cfgB")]
    pairs = pair_runs(a, b, expected_rows=2)
    assert len(pairs) == 2

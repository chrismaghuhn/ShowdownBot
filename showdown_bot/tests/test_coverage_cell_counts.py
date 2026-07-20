"""Task 3: validated per-cell counts over the v3 live dataset.

``coverage_cell_counts(path)`` validates the live dataset FIRST (malformed/mixed-version data is
rejected, never counted), then tallies the four coverage cells over ``is_active_valid_live_row``
rows only:
  slot0          <=> 0 in foe_mega_slots
  slot1          <=> 1 in foe_mega_slots
  both_foe_slots <=> {0,1} subset of foe_mega_slots
  order_tie      <=> foe_mega_order_tie is True
Each cell reports {"decisions", "distinct_battles"}. The safety signal is NOT in this dataset.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from showdown_bot.eval.coverage import coverage_cell_counts
from showdown_bot.eval.decision_profile import DecisionProfileError, build_live_profile_row

_CTR = ("damage_batch_calls", "planned_damage_batches", "implicit_damage_batches",
        "stats_batch_calls", "types_batch_calls", "mixed_batch_calls",
        "requests_total", "requests_unique", "cache_hits", "transport_attempts", "spawn_count")


def _before():
    return {k: 0 for k in _CTR}


def _after():
    return {"damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
            "stats_batch_calls": 1, "types_batch_calls": 1, "mixed_batch_calls": 0,
            "requests_total": 4, "requests_unique": 4, "cache_hits": 0,
            "transport_attempts": 3, "spawn_count": 3}


def _row(*, battle_id, decision_index, slots=(0,), tie=False, outcome="ok", twins=2):
    shape = SimpleNamespace(
        n_candidates=8, n_responses=40, n_mega_twins=twins, n_branches=2, n_worlds=1,
        depth2_frontier=0, foe_mega_slots=tuple(slots), foe_mega_order_tie=tie,
    )
    return build_live_profile_row(
        battle_id=battle_id, decision_index=decision_index, schedule_hash="s" * 16,
        config_id="cfg", format_id="gen9championsvgc2026regma", git_sha="deadbeef",
        config_hash="0" * 16, calc_backend="oneshot", outcome=outcome, latency_ms=12.0,
        counters_before=_before(), counters_after=_after(), shape=shape,
    )


def _write(tmp_path, rows) -> str:
    import json
    p = tmp_path / "profile.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(p)


def test_coverage_cell_counts_returns_decisions_and_distinct_battles_per_cell(tmp_path):
    rows = [
        _row(battle_id="b0", decision_index=0, slots=(0,)),
        _row(battle_id="b1", decision_index=0, slots=(1,)),
        _row(battle_id="b2", decision_index=0, slots=(0, 1)),
        _row(battle_id="b3", decision_index=0, slots=(0, 1), tie=True),
    ]
    counts = coverage_cell_counts(_write(tmp_path, rows))
    assert set(counts) == {"slot0", "slot1", "both_foe_slots", "order_tie"}
    for cell in counts:
        assert set(counts[cell]) == {"decisions", "distinct_battles"}
    assert counts["slot0"]["decisions"] == 3          # b0 (0,), b2 (0,1), b3 (0,1) all contain 0
    assert counts["slot1"]["decisions"] == 3          # b1 (1,), b2 (0,1), b3 (0,1) all contain 1
    assert counts["both_foe_slots"]["decisions"] == 2  # b2 and b3 have {0,1}
    assert counts["order_tie"]["decisions"] == 1       # only b3 is a tie


def test_malformed_jsonl_is_rejected_not_counted(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"schema_version": "decision-profile-v3"\n', encoding="utf-8")  # truncated JSON
    with pytest.raises(DecisionProfileError):
        coverage_cell_counts(str(p))


def test_only_active_valid_rows_count(tmp_path):
    rows = [
        _row(battle_id="b0", decision_index=0, slots=(0,), outcome="ok"),      # active-valid
        _row(battle_id="b1", decision_index=0, slots=(), twins=0),             # inactive (no twin)
    ]
    counts = coverage_cell_counts(_write(tmp_path, rows))
    assert counts["slot0"]["decisions"] == 1          # only the active-valid ok row


def test_a_non_ok_decision_credits_no_cell(tmp_path):
    rows = [
        _row(battle_id="b0", decision_index=0, slots=(0,), outcome="crash"),   # non-ok
        _row(battle_id="b1", decision_index=0, slots=(1,), outcome="fallback"),
    ]
    counts = coverage_cell_counts(_write(tmp_path, rows))
    assert counts["slot0"]["decisions"] == 0 and counts["slot1"]["decisions"] == 0


def test_both_foe_slots_also_credits_slot0_and_slot1(tmp_path):
    counts = coverage_cell_counts(_write(tmp_path, [_row(battle_id="b0", decision_index=0, slots=(0, 1))]))
    assert counts["slot0"]["decisions"] == 1
    assert counts["slot1"]["decisions"] == 1
    assert counts["both_foe_slots"]["decisions"] == 1
    assert counts["order_tie"]["decisions"] == 0


def test_distinct_battles_dedupes_by_battle_id(tmp_path):
    rows = [
        _row(battle_id="b0", decision_index=0, slots=(0,)),
        _row(battle_id="b0", decision_index=1, slots=(0,)),   # same battle, another decision
        _row(battle_id="b1", decision_index=0, slots=(0,)),
    ]
    counts = coverage_cell_counts(_write(tmp_path, rows))
    assert counts["slot0"]["decisions"] == 3
    assert counts["slot0"]["distinct_battles"] == 2

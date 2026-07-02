"""T3e-P0: per-battle counter deltas (not run-lifetime cumulative).

`_Client.invalid`/`.crashes` are lifetime-cumulative and `.latencies` is append-only, so a
T2 result row built from the raw totals makes row N carry battles 0..N. `_PerBattleCounters`
tracks a watermark advanced after each battle so `emit` returns only the finishing battle's
counts, and latency p95 is taken over ONLY the latencies appended since the last emit.

Tested without a live server — this is a pure counter helper.
"""
from __future__ import annotations

from showdown_bot.client.gauntlet import _PerBattleCounters, _latency_p95


def test_two_battles_are_per_battle_not_cumulative():
    c = _PerBattleCounters()
    # Battle 0: 1 invalid, 0 crashes, 3 decisions.
    d0 = c.emit(invalid=1, crashes=0, latencies=[0.10, 0.20, 0.30])
    assert d0 == {"invalid_choices": 1, "crashes": 0, "decision_latency_p95_ms": 300}

    # Battle 1: NO new invalids (cumulative still 1), 2 NEW crashes (cumulative 2), and two
    # more decisions appended. Row 1 must show THIS battle's counts, not the run totals.
    d1 = c.emit(invalid=1, crashes=2, latencies=[0.10, 0.20, 0.30, 0.05, 0.07])
    assert d1["invalid_choices"] == 0          # per-battle, NOT the cumulative 1
    assert d1["crashes"] == 2                   # the two NEW crashes only
    # p95 over only the NEW latencies [0.05, 0.07] -> 0.07 -> 70 ms, not the run p95 (~300 ms).
    assert d1["decision_latency_p95_ms"] == 70


def test_single_battle_matches_cumulative_behavior_unchanged():
    # One battle: the delta from the zero watermark equals the raw cumulative values, so the
    # existing single-battle-per-row schedule behavior is bit-for-bit preserved.
    c = _PerBattleCounters()
    lat = [0.10, 0.20, 0.30]
    d = c.emit(invalid=2, crashes=1, latencies=lat)
    assert d == {
        "invalid_choices": 2,
        "crashes": 1,
        "decision_latency_p95_ms": round(_latency_p95(lat) * 1000),
    }


def test_battle_with_no_new_decisions_yields_zero_p95():
    c = _PerBattleCounters()
    c.emit(invalid=0, crashes=0, latencies=[0.10, 0.20])
    # Next battle finished with no new latencies appended (edge case) -> p95 over empty -> 0.
    d = c.emit(invalid=0, crashes=0, latencies=[0.10, 0.20])
    assert d["decision_latency_p95_ms"] == 0

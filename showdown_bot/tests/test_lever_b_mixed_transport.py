"""Lever B, T1: mixed stats+types one-shot transport primitive + mixed_batch_calls.

Unit-level: a scripted ``_run`` (no Node) records payloads and counts one transport per
call. Pins one-spawn, prefix split, empty/one-sided, per-kind error domains (stats raises,
types -> []), and a transport-level error (counted, propagated).
"""
from __future__ import annotations

import pytest

from showdown_bot.engine.calc.client import CalcClient, CalcError, SubprocessCalcBackend


class _Mon:
    def __init__(self, spe: int) -> None:
        self._spe = spe

    def to_payload(self) -> dict:
        return {"species": "X", "spe": self._spe}


class _Script(SubprocessCalcBackend):
    """Overrides ``_run`` with a scripted response, mimicking the real spawn/transport counters."""

    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)
        self.payloads: list = []

    def _run(self, payload):
        self.payloads.append(payload)
        self.spawn_count += 1
        self.transport_attempts += 1
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _s(i, spe):
    return {"id": f"s{i}", "stats": {"spe": spe}}


def _t(j, ts):
    return {"id": f"t{j}", "types": ts}


def test_mixed_batch_one_spawn_and_prefix_split():
    b = _Script([[_s(0, 100), _s(1, 120), _t(0, ["Fire"]), _t(1, ["Water"])]])
    stats, types = b.mixed_batch([_Mon(100), _Mon(120)], ["Charizard", "Blastoise"])
    assert len(b.payloads) == 1                       # ONE transport
    assert b.mixed_batch_calls == 1
    assert b.transport_attempts == 1 and b.spawn_count == 1
    assert [s["spe"] for s in stats] == [100, 120]
    assert types == [["Fire"], ["Water"]]
    assert [it["id"] for it in b.payloads[0]] == ["s0", "s1", "t0", "t1"]
    assert [it["kind"] for it in b.payloads[0]] == ["stats", "stats", "types", "types"]


def test_mixed_batch_empty_no_transport():
    b = _Script([])
    assert b.mixed_batch([], []) == ([], [])
    assert b.payloads == [] and b.mixed_batch_calls == 0 and b.transport_attempts == 0


def test_mixed_batch_stats_only_one_spawn():
    b = _Script([[_s(0, 100)]])
    stats, types = b.mixed_batch([_Mon(100)], [])
    assert len(b.payloads) == 1 and b.mixed_batch_calls == 1
    assert [s["spe"] for s in stats] == [100] and types == []


def test_mixed_batch_types_only_one_spawn():
    b = _Script([[_t(0, ["Grass"])]])
    stats, types = b.mixed_batch([], ["Venusaur"])
    assert len(b.payloads) == 1 and b.mixed_batch_calls == 1
    assert stats == [] and types == [["Grass"]]


def test_mixed_batch_per_item_error_is_per_kind():
    # stats-item error -> raises (mirrors stats_batch's item["stats"]); types-item error -> []
    b = _Script([[{"id": "s0", "error": "boom"}, _t(0, ["Fire"])]])
    with pytest.raises(KeyError):
        b.mixed_batch([_Mon(1)], ["Charizard"])
    b2 = _Script([[_s(0, 100), {"id": "t0", "error": "boom"}]])
    stats, types = b2.mixed_batch([_Mon(100)], ["Charizard"])
    assert [s["spe"] for s in stats] == [100] and types == [[]]


def test_mixed_batch_transport_error_raises_calcerror():
    b = _Script([CalcError("timeout")])
    with pytest.raises(CalcError):
        b.mixed_batch([_Mon(1)], ["Charizard"])
    assert b.mixed_batch_calls == 1                   # failed attempt still counts one transport


def test_calcclient_mixed_batch_passthrough():
    b = _Script([[_s(0, 100), _t(0, ["Fire"])]])
    calc = CalcClient(backend=b)
    stats, types = calc.mixed_batch([_Mon(100)], ["Charizard"])
    assert [s["spe"] for s in stats] == [100] and types == [["Fire"]]
    assert b.mixed_batch_calls == 1                   # counter lives on the backend

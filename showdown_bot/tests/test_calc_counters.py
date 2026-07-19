"""I8-A Task A1 — transport/spawn counters on both calc backends.

These counters are the raw facts the I8 profile row is built from (design
`docs/projects/champions/specs/2026-07-16-champions-i8-latency-design.md`, Rev. 11, §2.4/§5.5):
`backend_class` is a *predicate* over `(spawn_count_before, spawn_calls, transport_retried)`,
and the validator requires `calc_backend == "oneshot" => spawn_calls == transport_attempts`.

CUMULATIVE, NOT PER-DECISION -- and that is deliberate. The design's ROW fields are
per-decision deltas, but a backend has no concept of a "decision" and must not acquire one.
More decisively: the row's `spawn_count_before` is *defined* as "the backend's cumulative spawn
count before this decision", so it is computable ONLY from a cumulative counter. Every counter
here therefore counts since construction -- matching the semantics `PersistentCalcBackend.spawn_count`
already had (client.py:171) -- and the profile writer derives the per-decision deltas by
snapshotting before/after (I8-B). Naming a backend attribute `spawn_calls` would have quietly
conflated the two.

Nothing reads these counters yet. They are additive attributes on the backend objects; no
decision path touches them.
"""

from __future__ import annotations

import pytest

from showdown_bot.engine.calc.client import (
    PersistentCalcBackend,
    SubprocessCalcBackend,
    _TransportError,
)
from showdown_bot.engine.calc.models import CalcMon, DamageRequest


def _req(move: str = "Moonblast") -> DamageRequest:
    return DamageRequest(
        attacker=CalcMon(species="Flutter Mane", nature="Timid", evs={"spa": 252}),
        defender=CalcMon(species="Incineroar", nature="Careful", evs={"hp": 252}),
        move=move,
    )


def _spec() -> CalcMon:
    return CalcMon(species="Incineroar", level=50, nature="Careful", evs={"hp": 252})


# --------------------------------------------------------------------------
# oneshot: every batch spawns a Node process, at TWO distinct sites
# --------------------------------------------------------------------------


def test_oneshot_spawn_count_counts_every_process_including_the_run_helper():
    # SubprocessCalcBackend spawns at two sites: calc_batch's own subprocess.run
    # (client.py:58) and the shared _run helper (client.py:88) that serves BOTH
    # stats_batch and types_batch. Counting only the first would under-report exactly
    # the spawn-dominated cost this slice exists to measure.
    backend = SubprocessCalcBackend()

    backend.calc_batch([_req()])              # site 1: client.py:58
    backend.stats_batch([_spec()], gen=9)     # site 2: client.py:88 via _run
    backend.types_batch(["Incineroar"])       # site 2 again

    assert backend.spawn_count == 3
    # The design's oneshot invariant: one process per physical attempt.
    assert backend.spawn_count == backend.transport_attempts


def test_oneshot_counts_each_logical_method_separately():
    backend = SubprocessCalcBackend()

    backend.calc_batch([_req()])
    backend.stats_batch([_spec()], gen=9)
    backend.types_batch(["Incineroar"])

    assert backend.damage_batch_calls == 1
    assert backend.stats_batch_calls == 1
    assert backend.types_batch_calls == 1


def test_oneshot_empty_list_spawns_nothing_and_counts_nothing():
    # All three public methods early-return on an empty list without touching transport
    # (client.py:54-55, :114-115, :124-125). The counters must sit BELOW those guards.
    backend = SubprocessCalcBackend()

    assert backend.calc_batch([]) == []
    assert backend.stats_batch([], gen=9) == []
    assert backend.types_batch([]) == []

    assert backend.spawn_count == 0
    assert backend.transport_attempts == 0
    assert backend.damage_batch_calls == 0
    assert backend.stats_batch_calls == 0
    assert backend.types_batch_calls == 0


def test_oneshot_counters_start_at_zero():
    backend = SubprocessCalcBackend()
    assert backend.spawn_count == 0
    assert backend.transport_attempts == 0
    assert backend.damage_batch_calls == 0
    assert backend.stats_batch_calls == 0
    assert backend.types_batch_calls == 0


# --------------------------------------------------------------------------
# persistent: one logical call can be two physical attempts
# --------------------------------------------------------------------------


def test_persistent_counters_start_at_zero_and_do_not_spawn_on_construction():
    # _proc is None at construction (client.py:167); the spawn is lazy via _ensure.
    backend = PersistentCalcBackend()
    assert backend.spawn_count == 0
    assert backend.transport_attempts == 0
    assert backend.damage_batch_calls == 0


def test_persistent_one_logical_call_can_be_two_physical_attempts(monkeypatch):
    # _run runs _run_once, and on _TransportError re-spawns and retries ONCE
    # (client.py:242-243). That is ONE logical call and TWO physical attempts, both
    # paying latency. transport_attempts is the physical count; damage_batch_calls is
    # the logical one; neither substitutes for the other.
    backend = PersistentCalcBackend()

    calls: list[int] = []

    def fake_spawn() -> None:
        backend.spawn_count += 1

    def fake_run_once(payload):
        calls.append(1)
        backend.transport_attempts += 1
        if len(calls) == 1:
            raise _TransportError("first attempt dies")
        return [{"rolls": [1], "minDamage": 1, "maxDamage": 1, "maxHP": 100}]

    monkeypatch.setattr(backend, "_spawn", fake_spawn)
    monkeypatch.setattr(backend, "_run_once", fake_run_once)

    backend.calc_batch([_req()])

    assert backend.damage_batch_calls == 1        # logical
    assert backend.transport_attempts == 2        # physical
    assert backend.transport_attempts > backend.damage_batch_calls


def test_persistent_empty_list_touches_no_counter():
    # client.py:278-279, :287-288, :297-298
    backend = PersistentCalcBackend()

    assert backend.calc_batch([]) == []
    assert backend.stats_batch([], gen=9) == []
    assert backend.types_batch([]) == []

    assert backend.spawn_count == 0
    assert backend.transport_attempts == 0
    assert backend.damage_batch_calls == 0
    assert backend.stats_batch_calls == 0
    assert backend.types_batch_calls == 0


# --------------------------------------------------------------------------
# the counters are a contract shared by both backends
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attr",
    [
        "spawn_count",
        "transport_attempts",
        "damage_batch_calls",
        "stats_batch_calls",
        "types_batch_calls",
        "mixed_batch_calls",
    ],
)
@pytest.mark.parametrize("make", [SubprocessCalcBackend, PersistentCalcBackend])
def test_both_backends_expose_the_same_counter_surface(make, attr):
    # The profile writer reads one surface regardless of which backend is configured.
    assert isinstance(getattr(make(), attr), int)

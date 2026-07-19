"""I8-A Task A2 — planned vs implicit damage batches, counted AT ORIGIN.

Design `docs/projects/champions/specs/2026-07-16-champions-i8-latency-design.md` (Rev. 11) §2.4:
a damage batch has exactly two origins, and telling them apart is the one genuinely new
counter the design needs (P-7):

  planned  -- a caller deliberately resolving its enqueued batch via the public flush()
              (the sole explicit call site is mega_scoring.py:625-626)
  implicit -- DamageOracle.get() auto-flushing because the key was still pending
              (oracle.py:55-58). That is a PREFETCH MISS: a hidden mid-evaluation round
              trip the three-phase scoring contract is supposed to avoid.

MEASURED AT ORIGIN, NEVER BY SUBTRACTION. The design records why `implicit = delta - planned`
is invalid: flush() early-returns on an empty pending map BEFORE incrementing anything
(oracle.py:42-43), so an empty flush would make the arithmetic yield -1.
"""

from __future__ import annotations

import pytest

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.calc.client import CalcClient, CalcError
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult


class _FakeClient:
    """Records batches; never touches Node."""

    def __init__(self) -> None:
        self.batches: list[list[DamageRequest]] = []

    def damage_batch(self, reqs: list[DamageRequest]) -> list[DamageResult]:
        self.batches.append(list(reqs))
        return [
            DamageResult(rolls=[10], min_damage=10, max_damage=10, max_hp=100)
            for _ in reqs
        ]


class _FailingClient:
    """A round trip that is made and then fails -- Node spawned, latency paid, no result."""

    def __init__(self) -> None:
        self.calls = 0

    def damage_batch(self, reqs: list[DamageRequest]) -> list[DamageResult]:
        self.calls += 1
        raise CalcError("calc subprocess failed (rc=1): node died mid-batch")


def _req(move: str) -> DamageRequest:
    return DamageRequest(
        attacker=CalcMon(species="Flutter Mane", nature="Timid", evs={"spa": 252}),
        defender=CalcMon(species="Incineroar", nature="Careful", evs={"hp": 252}),
        move=move,
    )


def test_counters_start_at_zero():
    oracle = DamageOracle(_FakeClient())
    assert oracle.batch_calls == 0
    assert oracle.planned_damage_batches == 0
    assert oracle.implicit_damage_batches == 0


def test_public_flush_is_planned():
    oracle = DamageOracle(_FakeClient())
    oracle.request(_req("Moonblast"))
    oracle.flush()

    assert oracle.planned_damage_batches == 1
    assert oracle.implicit_damage_batches == 0
    assert oracle.batch_calls == 1


def test_get_on_a_pending_key_is_an_implicit_batch():
    # oracle.get auto-flushes when the key is still pending (oracle.py:55-58).
    # This is the prefetch miss the profile exists to surface.
    oracle = DamageOracle(_FakeClient())
    key = oracle.request(_req("Moonblast"))
    oracle.get(key)

    assert oracle.implicit_damage_batches == 1
    assert oracle.planned_damage_batches == 0
    assert oracle.batch_calls == 1


def test_planned_and_implicit_are_counted_at_origin_not_by_subtraction():
    oracle = DamageOracle(_FakeClient())

    oracle.request(_req("Moonblast"))
    oracle.flush()                       # planned

    key2 = oracle.request(_req("Dazzling Gleam"))
    oracle.get(key2)                     # implicit: get() triggers the flush

    assert (oracle.planned_damage_batches, oracle.implicit_damage_batches) == (1, 1)
    assert oracle.batch_calls == oracle.planned_damage_batches + oracle.implicit_damage_batches


def test_an_empty_flush_moves_no_counter():
    # flush() early-returns on an empty pending map BEFORE incrementing (oracle.py:42-43).
    # This is exactly why the design forbids implicit = batch_calls_delta - planned:
    # that arithmetic would yield -1 here.
    oracle = DamageOracle(_FakeClient())
    oracle.flush()
    oracle.flush()

    assert oracle.batch_calls == 0
    assert oracle.planned_damage_batches == 0
    assert oracle.implicit_damage_batches == 0


def test_get_on_an_already_resolved_key_flushes_nothing():
    oracle = DamageOracle(_FakeClient())
    key = oracle.request(_req("Moonblast"))
    oracle.flush()                       # planned == 1, key now cached

    oracle.get(key)                      # cache hit: no pending, no batch

    assert oracle.planned_damage_batches == 1
    assert oracle.implicit_damage_batches == 0
    assert oracle.batch_calls == 1


def test_damage_convenience_resolves_on_demand_and_counts_implicit():
    # damage() is request + get, so its round trip comes from get()'s auto-flush.
    # Counting it implicit is not a quirk: damage() prefetched nothing, it resolved
    # on demand, which is precisely what the implicit counter means.
    oracle = DamageOracle(_FakeClient())
    oracle.damage(_req("Moonblast"))

    assert oracle.implicit_damage_batches == 1
    assert oracle.planned_damage_batches == 0


def test_a_planned_batch_that_raises_is_still_counted():
    """A batch that fails still HAPPENED: the round trip was made and paid latency.

    Counting only successes would break the invariant the profile validator asserts --
    the backend counts the attempt (client.py's damage_batch_calls increments before the
    call), so a failed batch would leave backend.damage_batch_calls == 1 against
    planned + implicit == 0. Design §2.6 also requires a non-ok row's counters to
    describe the transport that really happened.
    """
    client = _FailingClient()
    oracle = DamageOracle(client)
    oracle.request(_req("Moonblast"))

    with pytest.raises(CalcError):
        oracle.flush()

    assert client.calls == 1                       # the round trip was really made
    assert oracle.batch_calls == 1                 # a logical ATTEMPT, not a success
    assert oracle.planned_damage_batches == 1
    assert oracle.implicit_damage_batches == 0
    assert oracle.batch_calls == oracle.planned_damage_batches + oracle.implicit_damage_batches


def test_an_implicit_batch_that_raises_is_still_counted():
    """Same, for the prefetch-miss origin: a failed miss is still a miss that cost a
    round trip, and losing it would under-report the very cost this counter exists for."""
    client = _FailingClient()
    oracle = DamageOracle(client)
    key = oracle.request(_req("Moonblast"))

    with pytest.raises(CalcError):
        oracle.get(key)

    assert client.calls == 1
    assert oracle.batch_calls == 1
    assert oracle.implicit_damage_batches == 1
    assert oracle.planned_damage_batches == 0
    assert oracle.batch_calls == oracle.planned_damage_batches + oracle.implicit_damage_batches


def test_a_failed_implicit_batch_does_not_leak_the_origin_flag():
    """The on-demand flag must be cleared even when the batch raises.

    A leaked flag would silently misattribute every LATER planned batch as implicit --
    i.e. one transport error would turn the prefetch-miss counter into noise for the
    rest of the decision.
    """
    oracle = DamageOracle(_FailingClient())
    key = oracle.request(_req("Moonblast"))
    with pytest.raises(CalcError):
        oracle.get(key)

    oracle.client = _FakeClient()          # transport recovers
    oracle.request(_req("Icy Wind"))
    oracle.flush()                         # a PLANNED batch

    assert oracle.planned_damage_batches == 1, "origin flag leaked past the failed get()"
    assert oracle.implicit_damage_batches == 1


def test_oracle_and_backend_agree_on_the_error_path():
    """The profile invariant spans two layers, so the counter-proof must too.

    The row asserts `damage_batch_calls == planned + implicit`, where the left side comes
    from the BACKEND and the right from the ORACLE. A failed batch is exactly where those
    two layers can silently disagree: the backend counts the attempt (client.py:64), so
    if the oracle counted only successes the invariant would break on every transport
    error -- the case the row is most likely to be read for (design §2.6 keeps a non-ok
    row's counters precisely because they describe transport that really happened).
    """

    class _DyingBackend:
        def __init__(self) -> None:
            self.damage_batch_calls = 0

        def calc_batch(self, requests):
            self.damage_batch_calls += 1  # mirrors client.py:64 -- counted before the raise
            raise CalcError("node died mid-batch")

        def close(self) -> None:
            pass

    backend = _DyingBackend()
    oracle = DamageOracle(CalcClient(backend=backend))
    oracle.request(_req("Moonblast"))

    with pytest.raises(CalcError):
        oracle.flush()

    assert backend.damage_batch_calls == 1
    assert oracle.batch_calls == backend.damage_batch_calls
    assert (
        backend.damage_batch_calls
        == oracle.planned_damage_batches + oracle.implicit_damage_batches
    ), "backend and oracle disagree on a failed batch; the row's invariant would break"


def test_get_still_calls_the_PUBLIC_flush_so_prefetch_spies_stay_alive():
    """A prefetch miss must remain visible to code that patches `flush` on the instance.

    This is a regression guard on a real near-miss in I8-A. The first cut of the
    planned/implicit split routed `get` to a private `_flush`, which silently blinded
    the two existing guards that spy on prefetch misses this exact way:
    tests/i7b/test_i7b_scoring.py:352 ("exactly one flush") and
    tests/test_baselines.py:314. Both kept PASSING -- they simply stopped being able to
    see the miss they exist to forbid, which no full-suite run would ever reveal.

    So the call graph is part of the contract: `get` calls the PUBLIC `flush`.
    """
    oracle = DamageOracle(_FakeClient())
    seen = {"n": 0}
    real_flush = oracle.flush

    def spy_flush():
        seen["n"] += 1
        return real_flush()

    oracle.flush = spy_flush  # exactly how the existing guards do it

    key = oracle.request(_req("Moonblast"))
    oracle.get(key)  # prefetch miss -> MUST go through the patched public flush

    assert seen["n"] == 1, "get()'s auto-flush bypassed the public flush; spies are blind"
    assert oracle.implicit_damage_batches == 1  # and it is still attributed correctly


def test_the_split_always_accounts_for_every_batch():
    # The invariant the per-row validator asserts:
    #   damage_batch_calls == planned_damage_batches + implicit_damage_batches
    client = _FakeClient()
    oracle = DamageOracle(client)

    oracle.request(_req("Moonblast"))
    oracle.request(_req("Dazzling Gleam"))
    oracle.flush()                       # one batch, two deduped requests -> planned 1
    k = oracle.request(_req("Icy Wind"))
    oracle.get(k)                        # implicit 1
    oracle.flush()                       # nothing pending -> counts nothing

    assert oracle.batch_calls == 2
    assert oracle.planned_damage_batches == 1
    assert oracle.implicit_damage_batches == 1
    assert oracle.batch_calls == oracle.planned_damage_batches + oracle.implicit_damage_batches
    assert len(client.batches) == oracle.batch_calls   # counters match real round trips

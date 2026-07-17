"""I8-A addendum — request-level accounting on ``DamageOracle`` (P-7 / §2.4).

Three counters the design's row contract (§2.4) names but I8-A did not build, and whose
absence blocked C3: a real microprofile/live session must read them off the production
oracle, and a test-only re-implementation would be a second definition free to disagree
with the real cache/pending logic.

  requests_total  -- every ``request()`` call, raw
  requests_unique -- calls whose key newly reached ``_pending`` (dedup survivors)
  cache_hits      -- calls whose key was already resolved in ``_cache``

A key already **pending** is neither: it is a duplicate within the current batch, counted
only in ``requests_total``. Counted at origin, cumulative since construction, exactly like
I8-A's ``batch_calls`` split. The point of the file is falsifiability: each test pins exact
values, so an implementation that miscounts a pending duplicate as unique, or a cache hit as
unique, fails here rather than skewing a profile column downstream.
"""

from __future__ import annotations

import pytest

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.calc.client import CalcError
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult


class _FakeClient:
    """Records batches; never touches Node. Resolves every request so ``flush`` moves
    the batch's keys from ``_pending`` into ``_cache`` -- which is what lets a later
    ``request()`` of the same key be a genuine cache hit."""

    def __init__(self) -> None:
        self.batches: list[list[DamageRequest]] = []

    def damage_batch(self, reqs: list[DamageRequest]) -> list[DamageResult]:
        self.batches.append(list(reqs))
        return [DamageResult(rolls=[10], min_damage=10, max_damage=10, max_hp=100) for _ in reqs]


class _FailingClient:
    """A round trip that is made and then fails: the batch raises, so ``flush`` never
    reaches its cache write. The request counters must be untouched by that failure --
    they describe ``request()`` calls, which happened before any transport."""

    def __init__(self) -> None:
        self.calls = 0

    def damage_batch(self, reqs: list[DamageRequest]) -> list[DamageResult]:
        self.calls += 1
        raise CalcError("calc subprocess failed (rc=1): node died mid-batch")


def _req(move: str) -> DamageRequest:
    """Distinct ``move`` -> distinct semantic key; identical ``move`` -> identical key
    (``_key`` dumps the whole payload minus id)."""
    return DamageRequest(
        attacker=CalcMon(species="Flutter Mane", nature="Timid", evs={"spa": 252}),
        defender=CalcMon(species="Incineroar", nature="Careful", evs={"hp": 252}),
        move=move,
    )


def test_counters_start_at_zero():
    oracle = DamageOracle(_FakeClient())
    assert (oracle.requests_total, oracle.requests_unique, oracle.cache_hits) == (0, 0, 0)


def test_first_request_is_total_and_unique_not_a_hit():
    oracle = DamageOracle(_FakeClient())
    oracle.request(_req("Moonblast"))
    assert (oracle.requests_total, oracle.requests_unique, oracle.cache_hits) == (1, 1, 0)


def test_a_pending_duplicate_is_neither_unique_nor_a_hit():
    """The same key requested twice BEFORE any flush. The second call is a duplicate of a
    still-pending key: it adds nothing to ``_pending`` and nothing is cached yet, so it is
    counted only in ``requests_total``. This is the case an unconditional ``unique += 1``
    (or a ``cache_hits += 1`` that fires on 'not new') would get wrong."""
    oracle = DamageOracle(_FakeClient())
    oracle.request(_req("Moonblast"))
    oracle.request(_req("Moonblast"))
    assert (oracle.requests_total, oracle.requests_unique, oracle.cache_hits) == (2, 1, 0)
    assert len(oracle._pending) == 1  # dedup semantics unchanged: one enqueued key


def test_a_repeat_after_flush_is_a_cache_hit_not_a_new_unique():
    oracle = DamageOracle(_FakeClient())
    oracle.request(_req("Moonblast"))
    oracle.flush()                       # key moves _pending -> _cache
    oracle.request(_req("Moonblast"))    # now resolved: a cache hit
    assert (oracle.requests_total, oracle.requests_unique, oracle.cache_hits) == (2, 1, 1)
    assert len(oracle._pending) == 0     # a hit enqueues nothing


def test_multiple_distinct_keys_are_all_unique():
    oracle = DamageOracle(_FakeClient())
    for move in ("Moonblast", "Dazzling Gleam", "Icy Wind", "Moonblast"):  # last is a pending dup
        oracle.request(_req(move))
    assert (oracle.requests_total, oracle.requests_unique, oracle.cache_hits) == (4, 3, 0)
    assert len(oracle._pending) == 3


def test_the_full_lifecycle_total_equals_unique_plus_hits_plus_pending_dupes():
    """total is exactly partitioned: every request() is a unique, a cache hit, or a
    pending duplicate, and nothing is double-counted."""
    oracle = DamageOracle(_FakeClient())
    oracle.request(_req("Moonblast"))       # unique
    oracle.request(_req("Moonblast"))       # pending dup
    oracle.request(_req("Dazzling Gleam"))  # unique
    oracle.flush()
    oracle.request(_req("Moonblast"))       # cache hit
    oracle.request(_req("Icy Wind"))        # unique
    total, unique, hits = oracle.requests_total, oracle.requests_unique, oracle.cache_hits
    pending_dupes = total - unique - hits
    assert (total, unique, hits, pending_dupes) == (5, 3, 1, 1)


def test_dedup_and_resolution_behaviour_is_unchanged():
    """The counters are pure telemetry: which keys are enqueued, batched and resolved must
    be byte-identical to before. Request A twice (dup) and B once; the backend sees exactly
    [A, B] in one batch, and get() returns the cached result -- unchanged scoring behaviour."""
    client = _FakeClient()
    oracle = DamageOracle(client)
    ka = oracle.request(_req("Moonblast"))
    kb = oracle.request(_req("Dazzling Gleam"))
    oracle.request(_req("Moonblast"))        # duplicate of ka, still pending
    assert ka != kb and len(oracle._pending) == 2
    oracle.flush()
    assert len(client.batches) == 1 and len(client.batches[0]) == 2   # exactly the 2 uniques
    assert oracle.get(ka).max_damage == 10   # resolves from cache, no second batch
    assert len(client.batches) == 1


def test_the_error_path_leaves_request_counters_intact():
    """A flush that raises describes transport, not ``request()``. The three request
    counters were fixed at request time and a failed batch must not perturb them."""
    client = _FailingClient()
    oracle = DamageOracle(client)
    oracle.request(_req("Moonblast"))
    oracle.request(_req("Moonblast"))        # pending dup
    before = (oracle.requests_total, oracle.requests_unique, oracle.cache_hits)
    assert before == (2, 1, 0)
    with pytest.raises(CalcError):
        oracle.flush()
    assert client.calls == 1                 # the round trip really happened
    after = (oracle.requests_total, oracle.requests_unique, oracle.cache_hits)
    assert after == before                   # untouched by the failure


def test_a_real_oracle_exposes_all_three_without_reimplementation():
    """The blocker C3 hit head-on: a real session must read these off the production oracle.

    A real ``DamageOracle()`` (real ``CalcClient`` / real backend) exposes all three as plain
    int attributes, and ``request()`` populates them without any Node round trip -- so the
    harness's ``session.counters()`` can read them directly. The harness's own ``_DELTA_FIELDS``
    is the authority on which names it reads; the three must be there, and be real here."""
    from showdown_bot.eval.profile_harness import _DELTA_FIELDS

    for name in ("requests_total", "requests_unique", "cache_hits"):
        assert name in _DELTA_FIELDS, f"harness does not read {name!r}"

    oracle = DamageOracle()                  # real CalcClient; construction spawns no Node
    oracle.request(_req("Moonblast"))
    oracle.request(_req("Moonblast"))        # pending dup
    oracle.request(_req("Icy Wind"))
    snapshot = {name: getattr(oracle, name) for name in
                ("requests_total", "requests_unique", "cache_hits")}
    assert snapshot == {"requests_total": 3, "requests_unique": 2, "cache_hits": 0}
    assert all(isinstance(v, int) for v in snapshot.values())

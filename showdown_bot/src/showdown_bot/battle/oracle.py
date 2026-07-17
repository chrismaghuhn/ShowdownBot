from __future__ import annotations

import json

from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc.models import DamageRequest, DamageResult


class DamageOracle:
    """Memoized damage front-end over CalcClient.

    Goals:
    - **One batch per turn.** Callers enqueue all calcs via ``request`` during
      evaluation, then everything resolves in a single ``flush`` (one Node round
      trip) instead of N subprocess launches.
    - **Full cache key.** The key is the entire semantic payload (both mon
      specs incl. item/nature/evs/ivs/boosts/status/tera/ability, move, and the
      field: weather/terrain/screens/gameType). Two calcs collide only if they
      are genuinely identical, so dedupe is safe.
    """

    def __init__(self, client: CalcClient | None = None) -> None:
        self.client = client or CalcClient()
        self._cache: dict[str, DamageResult] = {}
        self._pending: dict[str, DamageRequest] = {}
        # Logical batch ATTEMPTS, not successes: a round trip that raises still happened
        # and still paid latency (I8-A). No production code reads this; it is telemetry.
        self.batch_calls = 0
        # I8-A: the same attempts as `batch_calls`, split by ORIGIN and counted where they
        # happen -- never derived as `batch_calls - planned`, which an empty flush would
        # make negative (see `flush`). Invariant, asserted by the profile validator:
        # batch_calls == planned_damage_batches + implicit_damage_batches. It holds on the
        # error path too, which is the whole reason all three increment together.
        self.planned_damage_batches = 0
        self.implicit_damage_batches = 0
        # I8-A addendum (§2.4, P-7): request-level accounting, counted at origin in
        # `request` and cumulative since construction like the batch counters above.
        # requests_total is every call; a call is then EITHER a cache hit (key already in
        # `_cache`), a pending duplicate (key already enqueued this batch -- counted in
        # neither of the two below), or a new unique key that reaches `_pending`. These are
        # pure telemetry: they change no cache or decision semantics. The row contract names
        # all three (they were the one gap that blocked a real session from reading its own
        # counters), and the invariant `requests_unique <= requests_total` is enforced by
        # the profile validator.
        self.requests_total = 0
        self.requests_unique = 0
        self.cache_hits = 0
        # True only while `get` is resolving a pending key. It exists so `get` can keep
        # calling the PUBLIC `flush` while `flush` still attributes the batch correctly.
        # That is not a style choice: existing guards spy on prefetch misses by patching
        # `flush` on the instance (tests/i7b/test_i7b_scoring.py:352,
        # tests/test_baselines.py:314). Routing `get` to a private helper instead would
        # leave those guards passing but blind -- they would no longer see the very
        # miss they exist to forbid.
        self._resolving_on_demand = False

    @staticmethod
    def _key(req: DamageRequest) -> str:
        payload = req.to_payload()
        payload.pop("id", None)
        return json.dumps(payload, sort_keys=True, default=str)

    def request(self, req: DamageRequest) -> str:
        """Enqueue a calc; returns its cache key. Identical calcs dedupe."""
        key = self._key(req)
        # I8-A accounting, counted at origin. The `_pending` mutation below is byte-identical
        # to the original `if key not in _cache and key not in _pending`: the assignment
        # still fires only for a key that is in neither map, so dedup and resolution are
        # unchanged -- only the three counters are added.
        self.requests_total += 1
        if key in self._cache:
            self.cache_hits += 1
        elif key not in self._pending:
            self.requests_unique += 1
            self._pending[key] = req
        # else: a key already pending -- a duplicate within this batch, counted in neither.
        return key

    def flush(self) -> None:
        if not self._pending:
            # No batch happened, so NO counter moves -- not batch_calls, not either half
            # of the split. This early return is exactly why the planned/implicit split
            # must be counted at origin: `implicit = batch_calls_delta - planned` would
            # score an empty flush as -1.
            return
        items = list(self._pending.items())
        reqs = []
        for idx, (_, req) in enumerate(items):
            req.id = f"o{idx}"
            reqs.append(req)
        # I8-A: count the ATTEMPT, immediately before the round trip, and attribute it to
        # its ORIGIN in the same breath -- a caller deliberately resolving its enqueue
        # phase is PLANNED; a flush `get` had to trigger to answer a still-pending key is
        # a prefetch miss and is IMPLICIT.
        #
        # Before the call, not after, because a batch that RAISES still happened: the
        # round trip was made and paid latency. Counting only successes would (a) contradict
        # the backend, which counts the attempt (`client.py`'s damage_batch_calls and
        # transport_attempts both increment before their call), breaking the profile
        # invariant `damage_batch_calls == planned + implicit` on any failed batch, and
        # (b) contradict the design's crash semantics, which require a non-ok row's
        # counters to describe the transport that really happened.
        self.batch_calls += 1
        if self._resolving_on_demand:
            self.implicit_damage_batches += 1
        else:
            self.planned_damage_batches += 1
        results = self.client.damage_batch(reqs)
        for (key, _), res in zip(items, results):
            self._cache[key] = res
        self._pending.clear()

    def get(self, key: str) -> DamageResult:
        if key in self._pending:
            # A PREFETCH MISS: this key was enqueued but never flushed, so answering it
            # costs a hidden mid-evaluation round trip. Note this calls the PUBLIC
            # `flush` -- unchanged from before I8-A -- so anything spying on `flush` to
            # forbid prefetch misses still sees it. The flag only tells `flush` how to
            # attribute the batch; it never reroutes the call.
            self._resolving_on_demand = True
            try:
                self.flush()
            finally:
                self._resolving_on_demand = False
        return self._cache[key]

    def damage(self, req: DamageRequest) -> DamageResult:
        """Convenience single calc (request + flush + get)."""
        key = self.request(req)
        return self.get(key)

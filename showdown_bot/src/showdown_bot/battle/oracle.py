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
        self.batch_calls = 0

    @staticmethod
    def _key(req: DamageRequest) -> str:
        payload = req.to_payload()
        payload.pop("id", None)
        return json.dumps(payload, sort_keys=True, default=str)

    def request(self, req: DamageRequest) -> str:
        """Enqueue a calc; returns its cache key. Identical calcs dedupe."""
        key = self._key(req)
        if key not in self._cache and key not in self._pending:
            self._pending[key] = req
        return key

    def flush(self) -> None:
        if not self._pending:
            return
        items = list(self._pending.items())
        reqs = []
        for idx, (_, req) in enumerate(items):
            req.id = f"o{idx}"
            reqs.append(req)
        results = self.client.damage_batch(reqs)
        self.batch_calls += 1
        for (key, _), res in zip(items, results):
            self._cache[key] = res
        self._pending.clear()

    def get(self, key: str) -> DamageResult:
        if key in self._pending:
            self.flush()
        return self._cache[key]

    def damage(self, req: DamageRequest) -> DamageResult:
        """Convenience single calc (request + flush + get)."""
        key = self.request(req)
        return self.get(key)

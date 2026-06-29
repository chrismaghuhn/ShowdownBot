from __future__ import annotations

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult


class FakeClient:
    """Stand-in CalcClient that counts batch calls and returns deterministic
    results keyed by request order."""

    def __init__(self):
        self.batch_calls = 0
        self.total_requests = 0

    def damage_batch(self, requests):
        self.batch_calls += 1
        self.total_requests += len(requests)
        out = []
        for r in requests:
            out.append(
                DamageResult(
                    rolls=[100] * 16, min_damage=100, max_damage=100, max_hp=200, id=r.id
                )
            )
        return out


def _req(move="Moonblast", defender_item=None):
    return DamageRequest(
        attacker=CalcMon(species="Flutter Mane", move=move),
        defender=CalcMon(species="Incineroar", item=defender_item),
        move=move,
    )


def test_dedupes_identical_requests():
    oracle = DamageOracle(client=FakeClient())
    k1 = oracle.request(_req())
    k2 = oracle.request(_req())
    assert k1 == k2
    assert len(oracle._pending) == 1


def test_single_batch_per_turn():
    fake = FakeClient()
    oracle = DamageOracle(client=fake)
    keys = [
        oracle.request(_req("Moonblast")),
        oracle.request(_req("Shadow Ball")),
        oracle.request(_req("Moonblast")),  # dup
    ]
    oracle.flush()
    assert fake.batch_calls == 1
    assert fake.total_requests == 2  # dup collapsed
    for k in keys:
        assert oracle.get(k).max_hp == 200


def test_get_autoflushes():
    fake = FakeClient()
    oracle = DamageOracle(client=fake)
    k = oracle.request(_req())
    res = oracle.get(k)  # triggers flush
    assert res.min_damage == 100
    assert fake.batch_calls == 1


def test_distinct_field_makes_distinct_key():
    oracle = DamageOracle(client=FakeClient())
    a = _req()
    b = _req(defender_item="Assault Vest")  # changes defender payload
    assert oracle._key(a) != oracle._key(b)


def test_cached_results_no_extra_batch():
    fake = FakeClient()
    oracle = DamageOracle(client=fake)
    k = oracle.request(_req())
    oracle.flush()
    # second request of same calc should hit cache, not re-enqueue
    k2 = oracle.request(_req())
    assert k == k2
    assert len(oracle._pending) == 0
    oracle.get(k2)
    assert fake.batch_calls == 1

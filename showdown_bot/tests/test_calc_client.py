from __future__ import annotations

import pytest

from showdown_bot.engine.calc.client import CalcClient, CalcError, SubprocessCalcBackend
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult


class FakeBackend:
    def __init__(self, results: list[DamageResult]):
        self._results = results
        self.calls: list[list[DamageRequest]] = []

    def calc_batch(self, requests):
        self.calls.append(list(requests))
        # Echo ids onto canned results in order.
        out = []
        for req, res in zip(requests, self._results):
            res.id = req.id
            out.append(res)
        return out


def _req(move: str = "Moonblast") -> DamageRequest:
    return DamageRequest(
        attacker=CalcMon(species="Flutter Mane", nature="Timid", evs={"spa": 252}),
        defender=CalcMon(species="Incineroar", nature="Careful", evs={"hp": 252}),
        move=move,
    )


def test_damage_single_maps_result():
    canned = DamageResult(rolls=[84, 99], min_damage=84, max_damage=99, max_hp=202)
    client = CalcClient(backend=FakeBackend([canned]))
    res = client.damage(_req())
    assert res.rolls == [84, 99]
    assert res.is_guaranteed_ohko is False
    assert res.can_ohko is False


def test_damage_batch_assigns_ids_and_orders():
    backend = FakeBackend(
        [
            DamageResult(rolls=[10], min_damage=10, max_damage=10, max_hp=100),
            DamageResult(rolls=[200], min_damage=200, max_damage=200, max_hp=131),
        ]
    )
    client = CalcClient(backend=backend)
    results = client.damage_batch([_req("Moonblast"), _req("Shadow Ball")])
    assert len(results) == 2
    assert backend.calls[0][0].id == "req0"
    assert backend.calls[0][1].id == "req1"
    assert results[1].is_guaranteed_ohko is True  # 200 >= 131


def test_error_result_raises():
    client = CalcClient(backend=FakeBackend([DamageResult(error="bad species")]))
    with pytest.raises(CalcError):
        client.damage(_req())


def test_payload_uses_camelcase_tera_and_field_default():
    req = DamageRequest(
        attacker=CalcMon(species="Ogerpon-Hearthflame", tera_type="Fire", move="Ivy Cudgel"),
        defender=CalcMon(species="Incineroar"),
        move="Ivy Cudgel",
    )
    payload = req.to_payload()
    assert payload["attacker"]["teraType"] == "Fire"
    assert payload["field"] == {"gameType": "Doubles"}


@pytest.mark.integration
def test_real_subprocess_flare_blitz_ohko():
    client = CalcClient(backend=SubprocessCalcBackend())
    req = DamageRequest(
        attacker=CalcMon(
            species="Incineroar", nature="Adamant", evs={"atk": 252}, move="Flare Blitz"
        ),
        defender=CalcMon(species="Flutter Mane", nature="Timid", evs={"hp": 4}),
        move="Flare Blitz",
    )
    res = client.damage(req)
    assert res.rolls and all(r > 0 for r in res.rolls)
    assert len(res.rolls) == 16
    assert res.is_guaranteed_ohko is True

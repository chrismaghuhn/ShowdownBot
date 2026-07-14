"""T0 Reg-I parity and T2 gen-0 damage smoke on vendored @smogon/calc (I4 commit 3+5)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from showdown_bot.engine.calc.client import (
    CalcClient,
    PersistentCalcBackend,
    SubprocessCalcBackend,
)
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
BASELINE_FIXTURE = FIXTURES_DIR / "calc_regi_parity_baseline.json"
GEN0_FIXTURE = FIXTURES_DIR / "calc_gen0_damage_upstream.json"
CALC_DIR = TESTS_DIR.parent / "tools" / "calc"

# Direct package API probe (T2 package-level smoke; bridge path tested separately below).
_GEN0_PROBE = r"""
import { readFileSync } from "node:fs";
import { calculate, Generations, Move, Pokemon } from "@smogon/calc";

function toRolls(damage) {
  if (typeof damage === "number") return [damage];
  if (Array.isArray(damage) && damage.length > 0 && Array.isArray(damage[0])) {
    const hits = damage;
    return hits[0].map((_, i) => hits.reduce((sum, h) => sum + h[i], 0));
  }
  return Array.from(damage);
}

const fixture = JSON.parse(readFileSync(process.argv[1], "utf8"));
const req = fixture.case.request_payload;
const gen = Generations.get(req.gen);
const attacker = new Pokemon(gen, req.attacker.species, {
  ability: req.attacker.ability,
  item: req.attacker.item,
});
const defender = new Pokemon(gen, req.defender.species, {
  ability: req.defender.ability,
});
const move = new Move(gen, req.move);
const result = calculate(gen, attacker, defender, move);
const rolls = toRolls(result.damage);
const minDamage = Math.min(...rolls);
const maxDamage = Math.max(...rolls);
const maxHP = defender.maxHP();
process.stdout.write(
  JSON.stringify({
    id: req.id,
    damage: rolls,
    minDamage,
    maxDamage,
    maxHP,
    minPercent: (minDamage / maxHP) * 100,
    maxPercent: (maxDamage / maxHP) * 100,
    desc: result.desc(),
  }),
);
"""


def _load_gen0_fixture() -> dict:
    return json.loads(GEN0_FIXTURE.read_text(encoding="utf-8"))


def _gen0_damage_request(fixture: dict | None = None) -> DamageRequest:
    payload = (fixture or _load_gen0_fixture())["case"]["request_payload"]
    attacker = payload["attacker"]
    defender = payload["defender"]
    return DamageRequest(
        id=payload["id"],
        gen=payload["gen"],
        attacker=CalcMon(
            species=attacker["species"],
            ability=attacker.get("ability"),
            item=attacker.get("item"),
        ),
        defender=CalcMon(
            species=defender["species"],
            ability=defender.get("ability"),
        ),
        move=payload["move"],
    )


def _damage_result_to_probe_dict(result: DamageResult) -> dict:
    return {
        "id": result.id,
        "damage": result.rolls,
        "minDamage": result.min_damage,
        "maxDamage": result.max_damage,
        "maxHP": result.max_hp,
        "minPercent": result.min_percent,
        "maxPercent": result.max_percent,
        "desc": result.desc,
    }


def _run_calc_mjs(payloads: list[dict]) -> list[dict]:
    proc = subprocess.run(
        ["node", "calc.mjs"],
        input=json.dumps(payloads),
        capture_output=True,
        text=True,
        cwd=str(CALC_DIR),
        timeout=60.0,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"calc.mjs failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"calc.mjs returned invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise AssertionError(f"expected JSON array from calc.mjs, got {type(data).__name__}")
    return data


def _assert_case_matches(case: dict, actual: dict) -> None:
    if actual.get("error"):
        pytest.fail(f"probe {case['id']!r} error: {actual['error']}")
    expected = case["expected_response"]
    assert actual["id"] == expected["id"]
    kind = case["kind"]
    if kind == "stats":
        assert actual["stats"] == expected["stats"]
    elif kind == "types":
        assert actual["types"] == expected["types"]
    elif kind == "damage":
        assert actual["damage"] == expected["damage"]
        assert actual["minDamage"] == expected["minDamage"]
        assert actual["maxDamage"] == expected["maxDamage"]
        assert actual["maxHP"] == expected["maxHP"]
        assert actual["minPercent"] == expected["minPercent"]
        assert actual["maxPercent"] == expected["maxPercent"]
        assert actual["desc"] == expected["desc"]
    else:
        pytest.fail(f"unknown probe kind: {kind!r}")


@pytest.mark.integration
def test_regi_parity_matches_baseline_fixture():
    """T0: vendored calc gen-9 stats/types/damage match Reg-I @0.10.0 baseline."""
    baseline = json.loads(BASELINE_FIXTURE.read_text(encoding="utf-8"))
    cases = baseline["cases"]
    payloads = [case["request_payload"] for case in cases]
    results = _run_calc_mjs(payloads)
    by_id = {item["id"]: item for item in results}
    assert len(by_id) == len(cases)
    for case in cases:
        assert case["id"] in by_id, f"missing result for {case['id']!r}"
        _assert_case_matches(case, by_id[case["id"]])


@pytest.mark.integration
def test_gen0_damage_smoke_matches_upstream_fixture():
    """T2: vendored @smogon/calc gen-0 Body Slam pin (39-46) via package API."""
    fixture = _load_gen0_fixture()
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", _GEN0_PROBE, str(GEN0_FIXTURE)],
        capture_output=True,
        text=True,
        cwd=str(CALC_DIR),
        timeout=30.0,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(f"gen-0 probe failed (rc={proc.returncode}): {proc.stderr.strip()}")
    actual = json.loads(proc.stdout)
    _assert_case_matches(fixture["case"], actual)


@pytest.mark.integration
def test_gen0_body_slam_via_calc_mjs():
    """T2 bridge: gen-0 Body Slam through calc.mjs (req.gen ?? 9)."""
    fixture = _load_gen0_fixture()
    payload = fixture["case"]["request_payload"]
    results = _run_calc_mjs([payload])
    _assert_case_matches(fixture["case"], results[0])


@pytest.mark.integration
@pytest.mark.parametrize("backend_factory", [SubprocessCalcBackend, PersistentCalcBackend])
def test_gen0_body_slam_via_python_backend(backend_factory):
    """T2 bridge: gen-0 Body Slam through Python calc backend."""
    fixture = _load_gen0_fixture()
    backend = backend_factory()
    try:
        result = backend.calc_batch([_gen0_damage_request(fixture)])[0]
    finally:
        backend.close()
    _assert_case_matches(fixture["case"], _damage_result_to_probe_dict(result))


@pytest.mark.integration
def test_gen0_body_slam_via_calc_client():
    """T2 bridge: gen-0 Body Slam through CalcClient."""
    fixture = _load_gen0_fixture()
    client = CalcClient(backend=SubprocessCalcBackend())
    try:
        result = client.damage(_gen0_damage_request(fixture))
    finally:
        client.close()
    _assert_case_matches(fixture["case"], _damage_result_to_probe_dict(result))


@pytest.mark.integration
def test_stats_batch_defaults_to_gen_nine():
    backend = SubprocessCalcBackend()
    spec = CalcMon(species="Flutter Mane", level=50, nature="Timid", evs={"spe": 252})
    assert backend.stats_batch([spec]) == backend.stats_batch([spec], gen=9)


@pytest.mark.integration
def test_stats_batch_gen_zero_uses_champions_formula():
    backend = SubprocessCalcBackend()
    spec = CalcMon(species="Abomasnow", level=50, nature="Hardy", evs={"spe": 32})
    gen0 = backend.stats_batch([spec], gen=0)[0]
    gen9 = backend.stats_batch([spec], gen=9)[0]
    assert gen0["spe"] == 112
    assert gen9["spe"] != gen0["spe"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "evs,nature,expected",
    [
        ({}, "Hardy", {"hp": 165, "spe": 80}),
        ({"spe": 1}, "Hardy", {"spe": 81}),
        ({"spe": 2}, "Hardy", {"spe": 82}),
        ({"spe": 32}, "Hardy", {"spe": 112}),
        ({"atk": 32}, "Adamant", {"atk": 158}),
    ],
    ids=["hp-sp0-spe0", "spe-sp1", "spe-sp2", "spe-sp32", "atk-sp32-adamant"],
)
def test_gen0_champions_stat_vectors(evs, nature, expected):
    """T1: pinned gen-0 stat vectors for Stat Points 0/1/2/32."""
    backend = SubprocessCalcBackend()
    spec = CalcMon(species="Abomasnow", level=50, nature=nature, evs=evs)
    stats = backend.stats_batch([spec], gen=0)[0]
    for stat, value in expected.items():
        assert stats[stat] == value, f"{stat} expected {value}, got {stats[stat]}"

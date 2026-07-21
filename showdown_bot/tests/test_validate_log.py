from __future__ import annotations

from pathlib import Path

import pytest

from showdown_bot.engine.calc.client import CalcClient, SubprocessCalcBackend
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.validate import (
    _collect_instances,
    load_known_sets,
    validate_log,
)
from showdown_bot.engine.log_parser import parse_log

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "logs"
VALIDATE_LOG = FIXTURE_DIR / "validate_sample.log"
VALIDATE_SETS = FIXTURE_DIR / "validate_sets.json"
SAMPLE_LOG = FIXTURE_DIR / "sample_damage_turn.log"


def test_collect_instances_pairs_moves_and_skips_recoil():
    events = parse_log(VALIDATE_LOG.read_text(encoding="utf-8"))
    instances = _collect_instances(events)
    moves = {(i.attacker_species, i.move, i.defender_species) for i in instances}
    assert ("Incineroar", "Knock Off", "Amoonguss") in moves
    assert ("Rillaboom", "Wood Hammer", "Urshifu-Rapid-Strike") in moves
    assert ("Flutter Mane", "Moonblast", "Incineroar") in moves
    # Recoil self-damage on Rillaboom must NOT be a validation instance.
    assert all(i.defender_species != "Rillaboom" for i in instances)


def test_malformed_hp_token_does_not_fabricate_a_no_damage_instance():
    # A real hit whose HP token is garbled must NOT be recorded as "no damage happened" --
    # the parser previously let a present-but-unparseable HP token through as hp=None, and
    # _collect_instances silently defaulted post_hp to the stale pre_hp, fabricating a
    # 100->100 "Thunderbolt did nothing" record for a hit that actually landed.
    raw = "\n".join([
        "|switch|p1a: Incineroar|Incineroar, M|100/100",
        "|switch|p2a: Delibird|Delibird, F|100/100",
        "|move|p1a: Incineroar|Thunderbolt|p2a: Delibird",
        "|-damage|p2a: Delibird|garbled-hp-token",
        "|turn|2",
    ])
    events = parse_log(raw)
    instances = _collect_instances(events)
    assert not any(i.move == "Thunderbolt" for i in instances)


def test_missing_move_name_does_not_fabricate_an_empty_move_instance():
    # A move event with no move name must NOT be paired with its damage under a fabricated
    # move="" -- that would feed an empty move name into the damage calculator and compare
    # its output against a real HP delta as if the comparison meant something.
    raw = "\n".join([
        "|switch|p1a: Incineroar|Incineroar, M|100/100",
        "|switch|p2a: Delibird|Delibird, F|100/100",
        "|move|p1a: Incineroar",
        "|-damage|p2a: Delibird|60/100",
        "|turn|2",
    ])
    events = parse_log(raw)
    instances = _collect_instances(events)
    assert not instances


@pytest.mark.integration
def test_strict_validation_all_match():
    cfg = load_format_config("gen9vgc2025regi")
    known = load_known_sets(VALIDATE_SETS)
    report = validate_log(
        VALIDATE_LOG.read_text(encoding="utf-8"),
        calc=CalcClient(backend=SubprocessCalcBackend()),
        format_config=cfg,
        known_sets=known,
    )
    assert report.total("strict") == 3
    assert report.matched("strict") >= 1
    # Exit criterion: strict match rate >= 95%.
    assert report.ratio("strict") >= 0.95


@pytest.mark.integration
def test_union_validation_runs_without_sets():
    cfg = load_format_config("gen9vgc2025regi")
    report = validate_log(
        SAMPLE_LOG.read_text(encoding="utf-8"),
        calc=CalcClient(backend=SubprocessCalcBackend()),
        format_config=cfg,
        known_sets={},
    )
    # All damage instances fall into the union bucket when no sets are known.
    assert report.total("union") >= 1
    assert report.total("strict") == 0
    # Should produce a human-readable summary.
    assert "union" in report.summary()

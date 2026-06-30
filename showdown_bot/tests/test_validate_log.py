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

"""Tests for VGC-Bench external-replay ingestion foundation (2b-5a Part A Task 1).

Fixtures live inside the package itself
(`research/vgc_bench_ingest/fixtures/`), not `tests/fixtures/`, mirroring the
isolation of the package they belong to (external-replay ingestion, never
imported by the live path -- see the package docstring / README invariant).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import showdown_bot.research.vgc_bench_ingest as vgc_bench_ingest
from showdown_bot.eval.battle_parse import parse_battle_result
from showdown_bot.research.vgc_bench_ingest.load_raw import load_raw
from showdown_bot.research.vgc_bench_ingest.parse_log import parse_battle
from showdown_bot.research.vgc_bench_ingest.schema import (
    VgcBenchParseError,
    VgcBenchRawBattle,
)
from showdown_bot.research.vgc_bench_ingest.snapshot import (
    build_sample_manifest,
    sha256_file,
)

FIXTURES = Path(vgc_bench_ingest.__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _regi_entry():
    return load_raw(_read("valid_sample.json"))["battle-vgcbench-regi-001"]


def _regma_entry():
    return load_raw(_read("valid_sample.json"))["battle-vgcbench-regma-002"]


# --- load_raw ----------------------------------------------------------------


def test_load_raw_parses_valid_sample_into_epoch_log_pairs():
    entries = load_raw(_read("valid_sample.json"))
    assert set(entries) == {"battle-vgcbench-regi-001", "battle-vgcbench-regma-002"}
    epoch, log = entries["battle-vgcbench-regi-001"]
    assert epoch == 1700000001
    assert isinstance(epoch, int)
    assert isinstance(log, str)
    assert "|tier|[Gen 9] VGC 2025 Reg I" in log


def test_load_raw_rejects_malformed_entry_naming_the_bad_battle_id():
    with pytest.raises(VgcBenchParseError) as exc_info:
        load_raw(_read("malformed_sample.json"))
    assert "battle-vgcbench-bad-003" in str(exc_info.value)


def test_load_raw_does_not_silently_skip_the_valid_entries_it_never_reaches():
    # The malformed entry must raise, not be dropped while the rest load fine.
    with pytest.raises(VgcBenchParseError):
        load_raw(_read("malformed_sample.json"))


def test_load_raw_rejects_non_object_top_level():
    with pytest.raises(VgcBenchParseError):
        load_raw("[1, 2, 3]")


def test_load_raw_rejects_invalid_json():
    with pytest.raises(VgcBenchParseError):
        load_raw("{not valid json")


# --- parse_battle: valid fixtures --------------------------------------------


def test_parse_battle_valid_regi_fixture_header_fields():
    epoch, log = _regi_entry()
    battle = parse_battle("battle-vgcbench-regi-001", epoch, log)
    assert isinstance(battle, VgcBenchRawBattle)
    assert battle.battle_id == "battle-vgcbench-regi-001"
    assert battle.epoch_seconds == 1700000001
    assert battle.gametype == "doubles"
    assert battle.format_name == "[Gen 9] VGC 2025 Reg I"
    assert battle.players == (("p1", "HeroBot"), ("p2", "VillainBot"))
    assert battle.rules == (
        "Species Clause: Only one of each Pokémon is allowed",
        "Open Team Sheets: Rosters and teams are revealed before battle",
    )
    assert battle.log_lines[0] == ">battle-gen9vgc2025regi-1"
    assert battle.log_lines[-1] == "|win|HeroBot"


def test_parse_battle_valid_regma_fixture_header_fields():
    epoch, log = _regma_entry()
    battle = parse_battle("battle-vgcbench-regma-002", epoch, log)
    assert battle.gametype == "doubles"
    assert battle.format_name == "[Gen 9] VGC 2025 Reg M-A"
    assert battle.players == (("p1", "AshBot"), ("p2", "MistyBot"))
    assert battle.rules == ("Species Clause: Only one of each Pokémon is allowed",)


# --- parse_battle: malformed entry --------------------------------------------


def test_parse_battle_malformed_entry_raises_naming_the_battle_id():
    with pytest.raises(VgcBenchParseError) as exc_info:
        parse_battle("battle-x-missing-header", 1700000000, "|move|p1a: X|Tackle|p2a: Y\n|win|X")
    assert "battle-x-missing-header" in str(exc_info.value)


# --- winner/turns re-derivation -----------------------------------------------


def test_parse_battle_winner_and_turns_match_the_regi_fixtures_actual_outcome():
    epoch, log = _regi_entry()
    battle = parse_battle("battle-vgcbench-regi-001", epoch, log)
    expected = parse_battle_result([log])
    assert battle.winner == expected["winner_name"] == "HeroBot"
    assert battle.turns == expected["turns"] == 3
    assert battle.is_tie is expected["is_tie"] is False
    assert battle.end_reason == expected["end_reason"] == "normal"


def test_parse_battle_winner_and_turns_match_the_regma_fixtures_actual_outcome():
    epoch, log = _regma_entry()
    battle = parse_battle("battle-vgcbench-regma-002", epoch, log)
    expected = parse_battle_result([log])
    assert battle.winner == expected["winner_name"] == "AshBot"
    assert battle.turns == expected["turns"] == 2
    assert battle.is_tie is False
    assert battle.end_reason == "normal"


# --- hash stability ------------------------------------------------------------


def test_parse_battle_hashes_are_stable_across_two_independent_parses():
    epoch, log = _regi_entry()
    a = parse_battle("battle-vgcbench-regi-001", epoch, log)
    b = parse_battle("battle-vgcbench-regi-001", epoch, log)
    assert a.raw_log_sha256 == b.raw_log_sha256
    assert a.normalized_log_sha256 == b.normalized_log_sha256
    # Session metadata (room id, |player| names, |j| joins) is stripped by
    # normalization but present in the raw log, so the two hashes must differ.
    assert a.raw_log_sha256 != a.normalized_log_sha256


def test_parse_battle_raw_sha256_matches_direct_hash_of_the_log_bytes():
    epoch, log = _regi_entry()
    battle = parse_battle("battle-vgcbench-regi-001", epoch, log)
    assert battle.raw_log_sha256 == hashlib.sha256(log.encode("utf-8")).hexdigest()


def test_parse_battle_different_battles_have_different_hashes():
    regi_epoch, regi_log = _regi_entry()
    regma_epoch, regma_log = _regma_entry()
    a = parse_battle("battle-vgcbench-regi-001", regi_epoch, regi_log)
    b = parse_battle("battle-vgcbench-regma-002", regma_epoch, regma_log)
    assert a.raw_log_sha256 != b.raw_log_sha256
    assert a.normalized_log_sha256 != b.normalized_log_sha256


# --- snapshot: sha256_file -----------------------------------------------------


def test_sha256_file_matches_hashlib_over_the_same_bytes(tmp_path):
    p = tmp_path / "sample.json"
    p.write_bytes(b'{"a": [1, "x"]}')
    assert sha256_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_sha256_file_over_the_real_valid_fixture():
    path = FIXTURES / "valid_sample.json"
    assert sha256_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()


# --- snapshot: build_sample_manifest --------------------------------------------


def test_build_sample_manifest_keys_are_sorted_and_purpose_defaults():
    manifest = build_sample_manifest(
        source="cameronangliss/vgc-battle-logs-sv",
        source_revision="abc123",
        dataset_file="valid_sample.json",
        dataset_file_sha256="deadbeef",
        format_filter="gen9vgc2025regi",
        sample_size=2,
        license="MIT",
        created_at="2026-07-11T00:00:00Z",
    )
    assert list(manifest.keys()) == sorted(manifest.keys())
    assert manifest["purpose"] == "ingestion_prototype_only"
    assert manifest["created_at"] == "2026-07-11T00:00:00Z"
    assert manifest["sample_size"] == 2
    assert manifest["license"] == "MIT"


def test_build_sample_manifest_purpose_can_be_overridden():
    manifest = build_sample_manifest(
        source="x",
        source_revision=None,
        dataset_file="f.json",
        dataset_file_sha256="00",
        format_filter=None,
        sample_size=1,
        license="MIT",
        created_at="t",
        purpose="custom_purpose",
    )
    assert manifest["purpose"] == "custom_purpose"
    assert list(manifest.keys()) == sorted(manifest.keys())


def test_build_sample_manifest_is_pure_same_inputs_same_output():
    kwargs = dict(
        source="x",
        source_revision="r1",
        dataset_file="f.json",
        dataset_file_sha256="00",
        format_filter="gen9vgc2025regi",
        sample_size=5,
        license="MIT",
        created_at="2026-07-11T00:00:00Z",
    )
    assert build_sample_manifest(**kwargs) == build_sample_manifest(**kwargs)


# --- package isolation docstring (full guard test lands in Task 2) --------------


def test_package_docstring_states_the_live_path_isolation_invariant():
    doc = vgc_bench_ingest.__doc__ or ""
    assert "MUST NOT be imported" in doc
    assert "live" in doc.lower()

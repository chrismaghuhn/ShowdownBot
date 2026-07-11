"""Tests for VGC-Bench external-replay ingestion foundation (2b-5a Part A Task 1).

Fixtures live inside the package itself
(`research/vgc_bench_ingest/fixtures/`), not `tests/fixtures/`, mirroring the
isolation of the package they belong to (external-replay ingestion, never
imported by the live path -- see the package docstring / README invariant).
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import showdown_bot.research.vgc_bench_ingest as vgc_bench_ingest
from showdown_bot.eval.battle_parse import parse_battle_result
from showdown_bot.research.vgc_bench_ingest.format_gate import (
    FormatGateResult,
    gate_format,
)
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


# --- package isolation docstring ----------------------------------------------


def test_package_docstring_states_the_live_path_isolation_invariant():
    doc = vgc_bench_ingest.__doc__ or ""
    assert "MUST NOT be imported" in doc
    assert "live" in doc.lower()


# --- format_gate: gate_format (2b-5a Part A Task 2) -----------------------------


def test_gate_format_reg_i_machine_id_is_target_compatible():
    result = gate_format("gen9vgc2025regi")
    assert isinstance(result, FormatGateResult)
    assert result.compatibility == "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "I"
    assert result.is_bo3 is False
    assert result.source_format == "gen9vgc2025regi"


def test_gate_format_reg_i_raw_human_tier_string_is_target_compatible():
    # Both accepted input forms: the raw human tier string parse_log.parse_battle
    # captures on VgcBenchRawBattle.format_name, and the machine format id.
    result = gate_format("[Gen 9] VGC 2025 Reg I")
    assert result.compatibility == "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "I"
    assert result.is_bo3 is False


def test_gate_format_reg_i_2026_is_also_target_compatible():
    result = gate_format("gen9vgc2026regi")
    assert result.compatibility == "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "I"


def test_gate_format_reg_i_end_to_end_from_the_task1_fixture():
    # Ties Task 1's parser output directly into the Task 2 gate.
    epoch, log = _regi_entry()
    battle = parse_battle("battle-vgcbench-regi-001", epoch, log)
    result = gate_format(battle.format_name)
    assert result.compatibility == "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "I"


def test_gate_format_reg_i_bo3_is_target_compatible_and_tagged_bo3():
    result = gate_format("gen9vgc2025regibo3")
    assert result.compatibility == "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "I"
    assert result.is_bo3 is True


def test_gate_format_reg_i_bo3_raw_human_tier_string_variant():
    result = gate_format("[Gen 9] VGC 2025 Reg I (Bo3)")
    assert result.compatibility == "TARGET_COMPATIBLE"
    assert result.is_bo3 is True


def test_gate_format_regma_is_mechanically_similar_never_target_compatible():
    result = gate_format("gen9vgc2025regma")
    assert result.compatibility == "MECHANICALLY_SIMILAR_BUT_NOT_TARGET"
    assert result.compatibility != "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "M-A"
    # Explicit hard-rule assertion: MA must never be classified as Reg I.
    assert result.inferred_regulation != "I"


def test_gate_format_regmb_is_mechanically_similar_never_target_compatible():
    result = gate_format("gen9vgc2025regmb")
    assert result.compatibility == "MECHANICALLY_SIMILAR_BUT_NOT_TARGET"
    assert result.compatibility != "TARGET_COMPATIBLE"
    assert result.inferred_regulation == "M-B"
    assert result.inferred_regulation != "I"


def test_gate_format_regma_raw_human_tier_string_end_to_end_from_fixture():
    # Ties Task 1's MA fixture directly into the Task 2 hard rule: MA/MB has
    # zero Reg I data and must never be laundered into TARGET_COMPATIBLE.
    epoch, log = _regma_entry()
    battle = parse_battle("battle-vgcbench-regma-002", epoch, log)
    result = gate_format(battle.format_name)
    assert result.compatibility == "MECHANICALLY_SIMILAR_BUT_NOT_TARGET"
    assert result.inferred_regulation == "M-A"
    assert "not" in result.reason.lower()


def test_gate_format_other_gen9_vgc_regulation_is_mechanically_similar():
    result = gate_format("gen9vgc2025regh")
    assert result.compatibility == "MECHANICALLY_SIMILAR_BUT_NOT_TARGET"
    assert result.inferred_regulation == "H"


def test_gate_format_gen9ou_is_rejected_as_format_mismatch():
    result = gate_format("gen9ou")
    assert result.compatibility == "REJECT_FORMAT_MISMATCH"
    assert result.inferred_regulation is None


def test_gate_format_gen8vgc_is_rejected_as_format_mismatch():
    result = gate_format("[Gen 8] VGC 2023 Reg E")
    assert result.compatibility == "REJECT_FORMAT_MISMATCH"


def test_gate_format_garbage_string_is_rejected_as_unknown():
    result = gate_format("not a pokemon format at all")
    assert result.compatibility == "REJECT_UNKNOWN_FORMAT"
    assert result.inferred_regulation is None
    assert result.is_bo3 is None


def test_gate_format_empty_string_is_rejected_as_unknown():
    result = gate_format("")
    assert result.compatibility == "REJECT_UNKNOWN_FORMAT"
    assert result.is_bo3 is None


def test_gate_format_source_format_preserves_original_input_string():
    original = "[Gen 9] VGC 2025 Reg I"
    result = gate_format(original)
    assert result.source_format == original


def test_gate_format_reason_is_a_nonempty_human_string():
    for fmt in ("gen9vgc2025regi", "gen9vgc2025regma", "gen9ou", "garbage"):
        result = gate_format(fmt)
        assert isinstance(result.reason, str)
        assert result.reason


# --- format_gate: live-path isolation guard -------------------------------------


def test_live_path_modules_do_not_transitively_import_vgc_bench_ingest():
    """Runtime isolation check (INV-1), run in a fresh subprocess so no other
    test's import of vgc_bench_ingest can contaminate ``sys.modules`` first.
    """
    probe = (
        "import sys\n"
        "import showdown_bot.battle.decision\n"
        "import showdown_bot.client.gauntlet\n"
        "import showdown_bot.learning.reranker_shadow\n"
        "import showdown_bot.learning.export_runtime\n"
        "leaked = [m for m in sys.modules if 'vgc_bench_ingest' in m]\n"
        "assert not leaked, f'live path leaked vgc_bench_ingest import: {leaked}'\n"
        "print('ISOLATION_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ISOLATION_OK" in result.stdout


def test_live_path_source_files_do_not_reference_vgc_bench_ingest_by_name():
    """Belt-and-suspenders static check alongside the runtime probe above:
    no live-path source file should even mention the package by name.
    """
    src_root = Path(vgc_bench_ingest.__file__).parent.parent.parent
    live_path_dirs = ["battle", "learning", "client"]
    offenders = []
    for dir_name in live_path_dirs:
        for path in (src_root / dir_name).rglob("*.py"):
            if "vgc_bench_ingest" in path.read_text(encoding="utf-8"):
                offenders.append(str(path))
    assert offenders == []

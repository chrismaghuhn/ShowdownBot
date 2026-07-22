"""Gate B holdout team artifacts — Task 13 step 1.

Binds the six sealed team files to the frozen VGCPastes source evidence: same bytes, closed
source-ID -> team-ID -> file mapping, deterministic `.packed`, real `validate-team` legality, and
`seal_team` hashes that agree with the canonical panel hash. Nothing here starts a server or plays
a battle.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC_DIR = REPO / "docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence"
TEAM_DIR = REPO / "showdown_bot/teams/panel_champions_strength_holdout_v0"
FORMAT_ID = "gen9championsvgc2026regma"
PINNED_SHOWDOWN = Path.home() / ".cache/showdownbot/pokemon-showdown/pokemon-showdown"

HOLDOUT_MANIFEST = REPO / "config/eval/holdout/champions_strength_holdout_v0_manifest.json"


def _manifest() -> dict:
    return json.loads(HOLDOUT_MANIFEST.read_text(encoding="utf-8"))


def _mapping() -> list[tuple[str, str]]:
    """(public source id, opaque internal id) pairs, in frozen selection order.

    Read from the holdout manifest and never restated here. Spec Amendment A1.1 makes that manifest
    the only artifact carrying the public-id-to-internal-id MAPPING; the internal ids themselves
    legitimately appear in the allowlisted operational artifacts (team filenames, panel, baseline,
    evidence). A test is not one of those, so spelling either here would make this file a leakage
    hit -- exactly the property the amendment exists to protect.
    """
    teams = sorted(_manifest()["teams"], key=lambda t: t["selection_index"])
    return [(t["source_team_id"], t["team_id"]) for t in teams]


SOURCE_TO_TEAM_ID = _mapping()


def _sources() -> dict:
    return json.loads((SRC_DIR / "sources.json").read_text(encoding="utf-8"))


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_repo_packer():
    """Load `showdown_bot/tools/generate_packed_team.py` by path and return its `pack_team`.

    This is deliberately the repo's existing packer -- the same one every committed `.packed`
    file was produced with -- rather than a second implementation written for the test.
    """
    import importlib.util

    tool = REPO / "showdown_bot/tools/generate_packed_team.py"
    spec = importlib.util.spec_from_file_location("_gpt_tool", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.pack_team


# --- mapping is closed in both directions ----------------------------------------------------


def test_source_id_to_team_id_mapping_is_closed_and_matches_the_frozen_selection():
    entries = _sources()["entries"]
    assert [e["team_id"] for e in entries] == [s for s, _ in SOURCE_TO_TEAM_ID]
    # the manifest is the single source of the mapping, and it is complete
    assert len(_mapping()) == 6
    assert len({t for _, t in _mapping()}) == 6
    assert [e["selection_index"] for e in entries] == [1, 2, 3, 4, 5, 6]
    # every mapped team has both artifacts, and the directory holds nothing else
    expected_files = set()
    for _, tid in SOURCE_TO_TEAM_ID:
        expected_files |= {f"{tid}.txt", f"{tid}.packed"}
    assert set(os.listdir(TEAM_DIR)) == expected_files


@pytest.mark.parametrize("team_id", [t for _, t in SOURCE_TO_TEAM_ID])
def test_team_id_is_safe_for_the_schedule_and_for_a_windows_filename(team_id):
    # Task 9 builds an on-disk path from the team_id, so it must satisfy that pattern exactly.
    assert re.fullmatch(r"[A-Za-z0-9_-]+", team_id)
    assert team_id == team_id.lower()
    # And it must be OPAQUE: no digit of any public source id may appear in it, or the identifier
    # leg would flag every document that legitimately describes the source (Amendment A1.1).
    for source_id, _ in _mapping():
        assert source_id.lower() not in team_id
        assert source_id.lower().lstrip("pc") not in team_id


# --- the final .txt IS the frozen source ------------------------------------------------------


@pytest.mark.parametrize("source_id,team_id", SOURCE_TO_TEAM_ID)
def test_final_txt_is_byte_identical_to_the_frozen_source_paste(source_id, team_id):
    frozen = SRC_DIR / f"{source_id.lower()}-paste.txt"
    final = TEAM_DIR / f"{team_id}.txt"
    assert final.read_bytes() == frozen.read_bytes()


@pytest.mark.parametrize("source_id,team_id", SOURCE_TO_TEAM_ID)
def test_final_txt_matches_the_digest_registered_in_the_source_manifest(source_id, team_id):
    entry = next(e for e in _sources()["entries"] if e["team_id"] == source_id)
    assert _sha256(TEAM_DIR / f"{team_id}.txt") == entry["sha256"]


@pytest.mark.parametrize("source_id,team_id", SOURCE_TO_TEAM_ID)
def test_every_team_has_exactly_six_pokemon_with_complete_published_fields(source_id, team_id):
    blocks = [b for b in (TEAM_DIR / f"{team_id}.txt").read_text(encoding="utf-8").strip().split("\n\n") if b.strip()]
    assert len(blocks) == 6
    for block in blocks:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        assert " @ " in lines[0], lines[0]                       # species + held item
        assert any(l.startswith("Ability:") for l in lines)
        assert any(l == "Level: 50" for l in lines)
        assert any(l.startswith("EVs:") for l in lines)
        assert any(l.endswith(" Nature") for l in lines)
        assert len([l for l in lines if l.startswith("- ")]) == 4


# --- .packed is deterministic and comes from the repo's own packer -----------------------------


@pytest.mark.parametrize("team_id", [t for _, t in SOURCE_TO_TEAM_ID])
def test_packed_is_reproducible_byte_for_byte_from_the_txt(tmp_path, team_id):
    pytest.importorskip("poke_env")
    # `showdown_bot/tools/` is a scripts directory, not an importable package (it is outside
    # `src/`), so the repo's own packer is loaded by path rather than by import name.
    pack_team = _load_repo_packer()

    committed = (TEAM_DIR / f"{team_id}.packed").read_bytes()
    scratch_txt = tmp_path / f"{team_id}.txt"
    shutil.copyfile(TEAM_DIR / f"{team_id}.txt", scratch_txt)
    repacked = pack_team(scratch_txt)
    assert repacked.read_bytes() == committed
    # and a second pack of the same input is byte-identical again
    assert pack_team(scratch_txt).read_bytes() == committed


@pytest.mark.parametrize("team_id", [t for _, t in SOURCE_TO_TEAM_ID])
def test_packed_is_a_single_line_with_six_pokemon(team_id):
    packed = (TEAM_DIR / f"{team_id}.packed").read_text(encoding="utf-8")
    assert "\n" not in packed.strip()
    assert len(packed.split("]")) == 6


# --- real legality, from the pinned Showdown -------------------------------------------------


@pytest.mark.parametrize("team_id", [t for _, t in SOURCE_TO_TEAM_ID])
def test_validate_team_passes_against_the_pinned_showdown(team_id):
    if not PINNED_SHOWDOWN.exists():  # pragma: no cover - environment dependent
        pytest.skip(f"pinned pokemon-showdown checkout not present at {PINNED_SHOWDOWN}")
    if shutil.which("node") is None:  # pragma: no cover
        pytest.skip("node is not available")
    with open(TEAM_DIR / f"{team_id}.txt", "rb") as team_file:
        result = subprocess.run(
            ["node", str(PINNED_SHOWDOWN), "validate-team", FORMAT_ID],
            stdin=team_file, capture_output=True, text=True,
        )
    assert result.returncode == 0, f"{team_id}: {result.stdout} {result.stderr}"


# --- sealing agrees with the canonical panel hash ---------------------------------------------


@pytest.mark.parametrize("source_id,team_id", SOURCE_TO_TEAM_ID)
def test_seal_team_content_hash_equals_the_canonical_panel_team_content_hash(source_id, team_id):
    from showdown_bot.eval.panel import team_content_hash
    from showdown_bot.eval.team_sealing import seal_team

    rel = f"teams/panel_champions_strength_holdout_v0/{team_id}.txt"
    record = seal_team(
        team_id=team_id, teams_root=str(REPO / "showdown_bot"), team_path=rel,
        archetype="published-tournament-team",
        source_description=f"VGCPastes {source_id}",
        source_date="2026-07-22",
        blind_attestation=_sources()["blindness_attestation"]["statement"],
    )
    assert record.content_hash == team_content_hash(str(REPO / "showdown_bot"), rel)
    assert record.team_path == rel
    assert record.team_id == team_id


def test_sealing_uses_the_specific_frozen_blindness_attestation_not_a_generic_one():
    statement = _sources()["blindness_attestation"]["statement"]
    # Must be the real recorded rationale, not a placeholder: long, and naming what it rules out.
    assert len(statement) > 200
    assert "blind to this bot's results" in statement
    assert "BEFORE any paste was read" in statement
    assert "no bot result" in statement          # names what was ruled out, not just that it was


# --- the source evidence is never touched ------------------------------------------------------


def test_creating_the_team_artifacts_left_every_frozen_source_file_unchanged():
    manifest = _sources()
    checks = [(e["filename"], e["sha256"], e["size_bytes"]) for e in manifest["entries"]]
    for key in ("selection_proof", "format_declaration_proof"):
        checks.append((manifest[key]["file"], manifest[key]["sha256"], manifest[key]["size_bytes"]))
    for filename, sha, size in checks:
        p = SRC_DIR / filename
        assert _sha256(p) == sha, filename
        assert p.stat().st_size == size, filename

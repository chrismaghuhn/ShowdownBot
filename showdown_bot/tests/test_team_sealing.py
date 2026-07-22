"""Gate B holdout team sealing — Task 12, plan §15, DESIGN sec 3.4.

`seal_team` RECORDS a seal for team files that already exist on disk. It never selects,
generates, downloads, legalises, modifies, or plays a team, and it deliberately makes no legality
claim: Task 13 must prove legality separately, before sealing. Every fixture here is synthetic;
no real holdout team is involved.
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
from pathlib import Path

import pytest

from showdown_bot.eval.panel import team_content_hash
from showdown_bot.eval.team_sealing import SealedTeamRecord, SealingError, seal_team

_META = dict(
    archetype="fixture-archetype",
    source_description="synthetic fixture, not a real team",
    source_date="2026-07-21",
    blind_attestation="fixture attestation, recorded before the bot ever saw this team",
)


def _write_fixture_team(tmp_path, txt_content="Fixture Mon @ Focus Sash\n", packed_content="|packed-fixture|", stem="fixture_team"):
    txt = tmp_path / f"{stem}.txt"
    packed = tmp_path / f"{stem}.packed"
    txt.write_text(txt_content, encoding="utf-8")
    packed.write_text(packed_content, encoding="utf-8")
    return txt, packed


def _seal(tmp_path, **overrides):
    kwargs = dict(
        team_id="holdout_0", teams_root=str(tmp_path), team_path="fixture_team.txt", **_META,
    )
    kwargs.update(overrides)
    return seal_team(**kwargs)


# --- 1/2/3: the hash is the REAL canonical .txt + .packed digest ------------------------------


def test_seal_team_records_the_real_txt_plus_packed_content_hash(tmp_path):
    _write_fixture_team(tmp_path)
    record = _seal(tmp_path)
    assert record.content_hash == team_content_hash(str(tmp_path), "fixture_team.txt")


def test_seal_team_changes_hash_if_only_the_packed_file_changes(tmp_path):
    # The exact bug Rev. 1 had: a .txt-only hash cannot see packed-only drift.
    _write_fixture_team(tmp_path, packed_content="|packed-version-1|")
    first = _seal(tmp_path)
    (tmp_path / "fixture_team.packed").write_text("|packed-version-2|", encoding="utf-8")
    assert _seal(tmp_path).content_hash != first.content_hash


def test_seal_team_changes_hash_if_only_the_txt_file_changes(tmp_path):
    _write_fixture_team(tmp_path, txt_content="Fixture Mon @ Focus Sash\n")
    first = _seal(tmp_path)
    (tmp_path / "fixture_team.txt").write_text("Fixture Mon @ Leftovers\n", encoding="utf-8")
    assert _seal(tmp_path).content_hash != first.content_hash


# --- 4/5: both halves of the pair are required ------------------------------------------------


def test_seal_team_rejects_a_missing_txt_file(tmp_path):
    (tmp_path / "fixture_team.packed").write_text("|packed-fixture|", encoding="utf-8")
    with pytest.raises(SealingError, match="fixture_team"):
        _seal(tmp_path)


def test_seal_team_rejects_a_missing_packed_file(tmp_path):
    (tmp_path / "fixture_team.txt").write_text("Fixture Mon @ Focus Sash\n", encoding="utf-8")
    with pytest.raises(SealingError, match="packed"):
        _seal(tmp_path)


# --- 6/7: fail-closed metadata validation -----------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", " \n\t "])
def test_seal_team_rejects_an_empty_or_whitespace_only_blind_attestation(tmp_path, blank):
    _write_fixture_team(tmp_path)
    with pytest.raises(SealingError, match="blind_attestation"):
        _seal(tmp_path, blind_attestation=blank)


_METADATA_FIELDS = ("team_id", "teams_root", "team_path", "archetype",
                    "source_description", "source_date", "blind_attestation")


@pytest.mark.parametrize("field", _METADATA_FIELDS)
@pytest.mark.parametrize("bad", ["", "   ", None, 123, b"bytes", ["a"]])
def test_seal_team_rejects_every_metadata_field_when_blank_or_not_a_string(tmp_path, field, bad):
    _write_fixture_team(tmp_path)
    with pytest.raises(SealingError, match=field):
        _seal(tmp_path, **{field: bad})


# --- 8: the record carries the real relative path that was sealed -----------------------------


def test_record_carries_the_relative_team_path_that_was_actually_sealed(tmp_path):
    nested = tmp_path / "teams" / "champions"
    nested.mkdir(parents=True)
    _write_fixture_team(nested, stem="holdout_a")
    record = _seal(tmp_path, team_path="teams/champions/holdout_a.txt", team_id="holdout_a")
    assert record.team_path == "teams/champions/holdout_a.txt"
    assert record.team_id == "holdout_a"
    assert record.content_hash == team_content_hash(str(tmp_path), "teams/champions/holdout_a.txt")


def test_record_carries_every_provenance_field_verbatim(tmp_path):
    _write_fixture_team(tmp_path)
    record = _seal(tmp_path)
    assert record.archetype == _META["archetype"]
    assert record.source_description == _META["source_description"]
    assert record.source_date == _META["source_date"]
    assert record.blind_attestation == _META["blind_attestation"]


# --- 9/10: path shape and containment ---------------------------------------------------------


def test_seal_team_rejects_an_absolute_team_path(tmp_path):
    # panel._team_content_hash does `Path(teams_root) / team_path`, and `/` DISCARDS teams_root
    # entirely when the right-hand side is absolute -- so an absolute team_path would silently
    # seal a file from anywhere on the filesystem. Refused here, before that call.
    txt, _ = _write_fixture_team(tmp_path)
    with pytest.raises(SealingError, match="relative"):
        _seal(tmp_path, team_path=str(txt))


def test_seal_team_rejects_dotdot_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _write_fixture_team(tmp_path, stem="outside")
    with pytest.raises(SealingError, match=r"traversal|outside|relative"):
        _seal(tmp_path, teams_root=str(root), team_path="../outside.txt")


def test_seal_team_rejects_dotdot_even_when_it_resolves_back_inside_teams_root(tmp_path):
    # Isolates the LEXICAL '..' check from the resolved-containment check: this path resolves to
    # a file genuinely inside teams_root, so containment alone would accept it. A team_path is
    # recorded verbatim in the sealed record and is later used to rebuild paths elsewhere, so a
    # non-canonical spelling of the same file must not be sealable in the first place.
    # (Found by mutation-testing the guard: disabling the '..' check left the test above green,
    # because containment caught that case too.)
    sub = tmp_path / "sub"
    sub.mkdir()
    _write_fixture_team(tmp_path, stem="fixture_team")
    with pytest.raises(SealingError, match="traversal"):
        _seal(tmp_path, team_path="sub/../fixture_team.txt")


def _make_windows_junction(link_path: Path, target_path: Path) -> None:
    """Create a Windows directory junction via `mklink /J` -- unlike a symlink this needs no admin
    privilege or Developer Mode, so the escape test really runs here instead of skipping (verified:
    plain os.symlink fails with WinError 1314, "a required privilege is not held by the client").
    Same helper as Task 10's own link-escape test. Raises OSError on failure."""
    import subprocess
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise OSError(f"mklink /J failed (rc={result.returncode}): {result.stdout} {result.stderr}")


def test_seal_team_rejects_a_team_path_that_escapes_teams_root_via_link(tmp_path):
    # A purely lexical ".." check cannot see this: every component is a normal name, and the
    # escape only exists once the path is really resolved.
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_fixture_team(outside, stem="secret")
    link_path = root / "link"
    try:
        os.symlink(str(outside), str(link_path), target_is_directory=True)
    except (OSError, NotImplementedError):
        try:
            _make_windows_junction(link_path, outside)
        except OSError as exc:  # pragma: no cover - platform dependent
            pytest.skip(
                "neither os.symlink nor mklink /J is available in this environment "
                f"(insufficient privilege) -- cannot exercise a real link escape: {exc}"
            )
    with pytest.raises(SealingError, match=r"outside|traversal"):
        _seal(tmp_path, teams_root=str(root), team_path="link/secret.txt")


def test_seal_team_rejects_a_non_txt_team_path(tmp_path):
    _write_fixture_team(tmp_path)
    with pytest.raises(SealingError, match=r"\.txt"):
        _seal(tmp_path, team_path="fixture_team.packed")


# --- 11: read/encoding/permission failures never escape raw -----------------------------------


def test_seal_team_wraps_a_permission_error_as_sealing_error(tmp_path, monkeypatch):
    _write_fixture_team(tmp_path)
    real_read_text = Path.read_text

    def _boom(self, *args, **kwargs):
        if self.suffix in (".txt", ".packed"):
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)
    with pytest.raises(SealingError, match=r"read|permission|Permission"):
        _seal(tmp_path)


def test_seal_team_wraps_a_decoding_error_as_sealing_error(tmp_path):
    # Real non-UTF-8 bytes on disk: panel's read_text(encoding="utf-8") raises UnicodeDecodeError,
    # which _team_content_hash does NOT convert to PanelError.
    #
    # Matching the SPECIFIC wording on purpose: UnicodeDecodeError is a ValueError subclass, so a
    # generic `except ValueError` would also produce a SealingError here and a loose regex would
    # pass either way (confirmed by mutation-testing: removing the dedicated clause left a looser
    # version of this test green). The dedicated clause exists for the operator-legible message,
    # so that is what is asserted.
    (tmp_path / "fixture_team.txt").write_bytes(b"\xff\xfe\x00binary not utf-8")
    (tmp_path / "fixture_team.packed").write_text("|packed-fixture|", encoding="utf-8")
    with pytest.raises(SealingError, match="not valid utf-8"):
        _seal(tmp_path)


def test_seal_team_wraps_a_directory_in_place_of_a_team_file_as_sealing_error(tmp_path):
    (tmp_path / "fixture_team.txt").mkdir()
    (tmp_path / "fixture_team.packed").write_text("|packed-fixture|", encoding="utf-8")
    with pytest.raises(SealingError):
        _seal(tmp_path)


# --- 12: the record is genuinely frozen -------------------------------------------------------


def test_sealed_record_is_frozen_and_cannot_be_edited_after_sealing(tmp_path):
    _write_fixture_team(tmp_path)
    record = _seal(tmp_path)
    assert dataclasses.is_dataclass(record) and isinstance(record, SealedTeamRecord)
    for field in ("team_id", "team_path", "content_hash", "archetype",
                  "source_description", "source_date", "blind_attestation"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, field, "tampered")


# --- 13: sealing is strictly read-only --------------------------------------------------------


def test_seal_team_does_not_modify_either_team_file(tmp_path):
    txt, packed = _write_fixture_team(tmp_path)
    before = {p: (p.read_bytes(), hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size)
              for p in (txt, packed)}
    listing_before = sorted(os.listdir(tmp_path))

    _seal(tmp_path)

    for p in (txt, packed):
        raw = p.read_bytes()
        assert raw == before[p][0]
        assert hashlib.sha256(raw).hexdigest() == before[p][1]
        assert p.stat().st_size == before[p][2]
    # and it wrote nothing new next to them either
    assert sorted(os.listdir(tmp_path)) == listing_before


def test_seal_team_makes_no_legality_claim(tmp_path):
    # DESIGN sec 3.4 / Task 13 item 2: legality is proven SEPARATELY, before sealing. A record
    # that carried a legality field would invite treating a seal as a legality certificate.
    _write_fixture_team(tmp_path)
    record = _seal(tmp_path)
    field_names = {f.name for f in dataclasses.fields(record)}
    assert not any("legal" in name or "valid" in name for name in field_names), field_names

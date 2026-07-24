"""Guard: every fixture manifest.json's declared sha256 must match its file's actual bytes.

Verify-only -- never recomputes or rewrites a mismatch (that would delete the check it
exists to be; see python/reseal_manifest_hashes.py for the deliberate, hand-run tool that
does the healing). Two known exceptions exist, both asserted positively below (their own
tests prove the expected condition still holds), never just excluded from the sweep:

- fixtures/viewer-v0/sources/fixture-06/bundle is DELIBERATELY hash-mismatched -- it is
  what test_fixture06_hash_mismatch in godot/tests/bundle/test_bundle_validator.gd and
  test_app_shell_smoke.gd's test_fixture06_refuse_reason exist to exercise.
- fixtures/viewer-v0/sources/fixture-08/bundle DELIBERATELY declares decision_trace
  present:true while the file is absent from disk (bundle contract §14 fixture 8 / §11.1.1
  invariant 5) -- it is what test_fixture08_missing_mandatory_file_refuses in
  test_bundle_validator.gd exercises. This is a distinct condition from a hash mismatch (the
  file doesn't exist to hash at all), so it gets its own label, "missing_on_disk", rather
  than being folded into "hash_mismatch" -- collapsing the two would make a future "file
  deleted by accident" indistinguishable from "file's bytes drifted" in this guard's output.
"""

# ruff: noqa: S101 -- pytest assertion rewriting needs bare `assert`, matches every
# sibling file under tests/python/.
from __future__ import annotations

import json
from pathlib import Path

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

from showdownbot_studio_exporter.hashutil import sha256_file  # type: ignore[import-not-found]

# Manifests live at different depths -- fixtures/viewer-v0/bundles/*/manifest.json is one
# level deep, fixtures/viewer-v0/sources/fixture-06/bundle/manifest.json is two -- so scan
# recursively rather than with a fixed-depth glob (a `*/manifest.json` glob against the
# sources/ root silently returns nothing).
_ROOTS = (
    STUDIO_ROOT / "godot" / "tests" / "fixtures" / "unit",
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles",
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources",
)
# measured: 11 unit + 6 bundles + 7 sources-bundle dirs (fixture-06 plus Plan F's
# fixtures 7, 8, 12, 22a, 22b, 23)
_MIN_MANIFEST_COUNT = 24

_FIXTURE06_MANIFEST = (
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-06" / "bundle" / "manifest.json"
)
_FIXTURE08_MANIFEST = (
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-08" / "bundle" / "manifest.json"
)
_EXPECTED_BAD = {
    _FIXTURE06_MANIFEST: {"decision_trace": "hash_mismatch"},
    _FIXTURE08_MANIFEST: {"decision_trace": "missing_on_disk"},
}


def _manifests() -> list[Path]:
    found: list[Path] = []
    for root in _ROOTS:
        found.extend(root.rglob("manifest.json"))
    return found


def _bad_keys(manifest_path: Path) -> dict[str, str]:
    """Map each present:true logical key to its problem, if any.

    A file that's absent on disk ("missing_on_disk") is a distinct, legitimate fixture
    state (fixture-08's own condition, contract §14 fixture 8) from a byte-level hash
    drift ("hash_mismatch", fixture-06's condition) -- they get different labels rather
    than being folded into one, so real drift can never be masked as an expected miss.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad: dict[str, str] = {}
    for key, entry in manifest.get("files", {}).items():
        if not entry.get("present"):
            continue
        file_path = manifest_path.parent / entry["path"]
        if not file_path.is_file():
            bad[key] = "missing_on_disk"
            continue
        actual = sha256_file(file_path)
        if actual != entry.get("sha256"):
            bad[key] = "hash_mismatch"
    return bad


def test_manifest_scan_finds_expected_fixtures():
    # A scan that silently under-matches (wrong depth, wrong root) is worse than no guard
    # at all -- it reports green while checking nothing. Fail loudly instead.
    found = _manifests()
    assert len(found) >= _MIN_MANIFEST_COUNT, f"only found {len(found)}: {found}"


def test_all_fixture_manifest_hashes_match_except_known_exception():
    mismatches: dict[str, dict[str, str]] = {}
    for manifest_path in _manifests():
        bad = _bad_keys(manifest_path)
        expected = _EXPECTED_BAD.get(manifest_path, {})
        if bad != expected:
            mismatches[str(manifest_path)] = bad
    assert not mismatches, f"unexpected hash drift or missing file (or a healed known exception): {mismatches}"


def test_fixture06_bundle_is_still_deliberately_mismatched():
    assert _FIXTURE06_MANIFEST.is_file(), _FIXTURE06_MANIFEST
    assert _bad_keys(_FIXTURE06_MANIFEST) == {"decision_trace": "hash_mismatch"}


def test_fixture08_bundle_still_declares_missing_required_file():
    assert _FIXTURE08_MANIFEST.is_file(), _FIXTURE08_MANIFEST
    assert _bad_keys(_FIXTURE08_MANIFEST) == {"decision_trace": "missing_on_disk"}

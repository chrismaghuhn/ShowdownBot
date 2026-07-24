"""Guard: every fixture manifest.json's declared sha256 must match its file's actual bytes.

Verify-only -- never recomputes or rewrites a mismatch (that would delete the check it
exists to be; see python/reseal_manifest_hashes.py for the deliberate, hand-run tool that
does the healing). The one known exception is fixtures/viewer-v0/sources/fixture-06/bundle,
which is DELIBERATELY mismatched -- it is what test_fixture06_hash_mismatch in
godot/tests/bundle/test_bundle_validator.gd and test_app_shell_smoke.gd's
test_fixture06_refuse_reason exist to exercise. That exception is asserted positively
below (its own test proves it still mismatches), not just excluded from the sweep.
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
_MIN_MANIFEST_COUNT = 18  # measured: 11 unit + 6 bundles + 1 sources/fixture-06/bundle

_FIXTURE06_MANIFEST = (
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-06" / "bundle" / "manifest.json"
)
_EXPECTED_MISMATCH = {_FIXTURE06_MANIFEST: {"decision_trace"}}


def _manifests() -> list[Path]:
    found: list[Path] = []
    for root in _ROOTS:
        found.extend(root.rglob("manifest.json"))
    return found


def _mismatched_keys(manifest_path: Path) -> set[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = set()
    for key, entry in manifest.get("files", {}).items():
        if not entry.get("present"):
            continue
        actual = sha256_file(manifest_path.parent / entry["path"])
        if actual != entry.get("sha256"):
            bad.add(key)
    return bad


def test_manifest_scan_finds_expected_fixtures():
    # A scan that silently under-matches (wrong depth, wrong root) is worse than no guard
    # at all -- it reports green while checking nothing. Fail loudly instead.
    found = _manifests()
    assert len(found) >= _MIN_MANIFEST_COUNT, f"only found {len(found)}: {found}"


def test_all_fixture_manifest_hashes_match_except_known_exception():
    mismatches: dict[str, set[str]] = {}
    for manifest_path in _manifests():
        bad = _mismatched_keys(manifest_path)
        expected = _EXPECTED_MISMATCH.get(manifest_path, set())
        if bad != expected:
            mismatches[str(manifest_path)] = bad
    assert not mismatches, f"unexpected hash drift (or a healed fixture-06): {mismatches}"


def test_fixture06_bundle_is_still_deliberately_mismatched():
    assert _FIXTURE06_MANIFEST.is_file(), _FIXTURE06_MANIFEST
    assert _mismatched_keys(_FIXTURE06_MANIFEST) == {"decision_trace"}

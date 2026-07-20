from __future__ import annotations

import hashlib
import re
from pathlib import Path

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.cli import main

_HASH_LINE = re.compile(
    r"- `(fixtures/viewer-v0/[^`]+)` sha256 `([0-9a-f]{64})`"
)
_INVENTORY_ROOTS = (
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources",
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles",
)


def _sources_md_entries() -> list[tuple[Path, str]]:
    md = STUDIO_ROOT / "fixtures" / "viewer-v0" / "SOURCES.md"
    entries: list[tuple[Path, str]] = []
    for line in md.read_text(encoding="utf-8").splitlines():
        match = _HASH_LINE.search(line)
        if not match:
            continue
        rel, digest = match.group(1), match.group(2)
        entries.append((STUDIO_ROOT / rel, digest))
    return entries


def _inventory_files() -> set[Path]:
    files: set[Path] = set()
    for root in _INVENTORY_ROOTS:
        for path in root.rglob("*"):
            if path.is_file():
                files.add(path.resolve())
    return files


def test_sources_md_hashes_match_committed_files():
    entries = _sources_md_entries()
    listed = {path.resolve() for path, _ in entries}
    on_disk = _inventory_files()
    missing_from_md = sorted(p.relative_to(STUDIO_ROOT).as_posix() for p in on_disk - listed)
    extra_in_md = sorted(p.relative_to(STUDIO_ROOT).as_posix() for p in listed - on_disk)
    assert not missing_from_md, f"files missing from SOURCES.md: {missing_from_md}"
    assert not extra_in_md, f"SOURCES.md paths not on disk: {extra_in_md}"
    mismatches = []
    for path, want in entries:
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != want:
            mismatches.append(f"{path.relative_to(STUDIO_ROOT).as_posix()}: {got} != {want}")
    assert not mismatches, "SOURCES.md hash mismatches:\n" + "\n".join(mismatches)


def test_all_plan_a_sources_unchanged_after_export(tmp_path):
    entries = [
        (path, digest)
        for path, digest in _sources_md_entries()
        if "fixtures/viewer-v0/sources/" in path.as_posix().replace("\\", "/")
    ]
    assert entries, "SOURCES.md must list source files under fixtures/viewer-v0/sources/"
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path, _ in entries}
    for path, want in entries:
        assert before[path] == want

    out = tmp_path / "out"
    fix01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"
    main(
        [
            "--out",
            str(out),
            "--battle-log",
            str(fix01 / "battle.log"),
            "--decision-trace",
            str(fix01 / "decision_trace.jsonl"),
            "--results",
            str(fix01 / "results.jsonl"),
        ]
    )
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path, _ in entries}
    assert before == after

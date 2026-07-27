"""Every Gate B freeze must stay verifiable, not merely have been correct once.

A freeze is a claim about bytes. ``inventory.json`` declares a ``sha256`` and a ``bytes`` count for
every file in the run directory, and the run directory is supposed to contain exactly those files
plus the inventory itself (which cannot list its own hash). Nothing enforced either half until this
test: the ``gate-b-safety-fail-bc2d6df`` freeze has carried an unchecked inventory since it landed.

The two checks are deliberately separate. Re-hashing catches a file whose CONTENT drifted -- a
re-encoded line ending, a "harmless" reformat, a partial restore. The closed-set check catches a
file that APPEARED or VANISHED, which no per-file hash can see: an extra artifact copied in later
looks fine to every declared hash, and a deleted one simply stops being checked.

Parametrised over every freeze whose inventory has the shared shape, so a new freeze is covered by
adding a directory rather than by editing this file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATUM_ROOT = REPO_ROOT / "data" / "eval" / "champions-panel-v0" / "strength-holdout-v0" / "windows"

FREEZE_DIRS = ["gate-b-5ab1083", "gate-b-safety-fail-bc2d6df"]


def _load(freeze: str) -> tuple[Path, dict]:
    run_dir = STRATUM_ROOT / freeze
    inventory = run_dir / "inventory.json"
    if not inventory.is_file():
        pytest.skip(f"freeze {freeze!r} is not present in this checkout")
    return run_dir, json.loads(inventory.read_text(encoding="utf-8"))


@pytest.mark.parametrize("freeze", FREEZE_DIRS)
def test_every_declared_file_matches_its_declared_bytes_and_sha256(freeze: str) -> None:
    run_dir, inv = _load(freeze)
    declared = inv["files"]
    assert declared, f"{freeze}: inventory declares no files at all"

    mismatches = []
    for relpath, entry in sorted(declared.items()):
        path = run_dir / relpath
        if not path.is_file():
            mismatches.append(f"{relpath}: declared but missing from disk")
            continue
        blob = path.read_bytes()
        if len(blob) != entry["bytes"]:
            mismatches.append(f"{relpath}: {len(blob)} bytes on disk != {entry['bytes']} declared")
        actual = hashlib.sha256(blob).hexdigest()
        if actual != entry["sha256"]:
            mismatches.append(f"{relpath}: sha256 {actual} != {entry['sha256']} declared")

    assert not mismatches, f"{freeze}: frozen bytes no longer match the inventory:\n  " + "\n  ".join(mismatches)


@pytest.mark.parametrize("freeze", FREEZE_DIRS)
def test_run_directory_is_a_closed_set(freeze: str) -> None:
    """{on-disk} == {declared} + {inventory.json}, both directions.

    A per-file hash loop can never notice a file that was added after the freeze, nor one that was
    removed -- it only ever looks at what the inventory already names.
    """
    run_dir, inv = _load(freeze)
    on_disk = {p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()}
    expected = set(inv["files"]) | {"inventory.json"}

    assert on_disk == expected, (
        f"{freeze}: run directory is not a closed set\n"
        f"  on disk but undeclared: {sorted(on_disk - expected)}\n"
        f"  declared but absent:    {sorted(expected - on_disk)}"
    )


@pytest.mark.parametrize("freeze", FREEZE_DIRS)
def test_inventory_never_declares_itself(freeze: str) -> None:
    """The self-exception is what makes the closed-set check's ``+ {inventory.json}`` term correct;
    if an inventory ever declared its own hash that hash could not be satisfiable."""
    _, inv = _load(freeze)
    assert "inventory.json" not in inv["files"]


@pytest.mark.parametrize("freeze", FREEZE_DIRS)
def test_freeze_carries_no_strength_claim(freeze: str) -> None:
    _, inv = _load(freeze)
    assert inv["no_strength_claim"] is True

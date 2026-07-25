"""No live DTO type (protocol/dto/, session/dto/, battle/dto/) may be referenced from a
*bundle_writer*.gd file (spec section 4.1.2). None of those directories or files exist yet
in F0 -- see this task's fail-check steps for how this is proven meaningful today.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_GODOT_SRC = STUDIO_ROOT / "godot" / "src"
_LIVE_DTO_DIRS = (
    _GODOT_SRC / "protocol" / "dto",
    _GODOT_SRC / "session" / "dto",
    _GODOT_SRC / "battle" / "dto",
)
_BUNDLE_WRITER_GLOB = "*bundle_writer*.gd"
_ALLOWLIST_FILE = (
    Path(__file__).parent / "architecture_allowlists" / "live_dto_bundle_path_allowlist.txt"
)
_CLASS_NAME_RE = re.compile(r"^class_name\s+(\w+)", re.MULTILINE)


def _bundle_writer_files() -> list[Path]:
    return sorted(_GODOT_SRC.rglob(_BUNDLE_WRITER_GLOB))


def _live_dto_class_names() -> set[str]:
    names: set[str] = set()
    for live_dir in _LIVE_DTO_DIRS:
        if not live_dir.is_dir():
            continue
        for path in live_dir.rglob("*.gd"):
            match = _CLASS_NAME_RE.search(path.read_text(encoding="utf-8"))
            if match:
                names.add(match.group(1))
    return names


def _load_allowlist() -> list[str]:
    entries = []
    for line in _ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


@pytest.mark.architecture
def test_godot_src_root_exists_for_bundle_writer_scan():
    assert _GODOT_SRC.is_dir()


@pytest.mark.architecture
def test_no_live_dto_type_referenced_from_a_bundle_writer_file():
    live_dto_names = _live_dto_class_names()
    allowlist = _load_allowlist()
    violations: list[str] = []
    for path in _bundle_writer_files():
        rel = path.relative_to(_GODOT_SRC).as_posix()
        if rel in allowlist:
            continue
        text = path.read_text(encoding="utf-8")
        for name in live_dto_names:
            if re.search(rf"\b{re.escape(name)}\b", text):
                violations.append(f"{rel} references live DTO {name}")
    assert not violations, violations

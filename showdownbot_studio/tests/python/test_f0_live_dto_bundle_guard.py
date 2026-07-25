"""No file under godot/src/replay/ may reference a live DTO type (protocol/dto/, session/dto/,
battle/dto/ -- spec section 4.1.2), except the one sanctioned M3a conversion boundary,
`replay/live_recording_sink.gd`. Scoping this to the whole replay/ directory rather than only
files matching a `*bundle_writer*.gd` naming convention closes the gap where a differently
named file (the actual Phase-0 bundle writer, `ReplayExportGateway`, or any future replay file)
could reference a live DTO type without tripping a filename-pattern-based guard. None of the
live-DTO directories exist yet in F0 -- see this task's fail-check steps for how this is proven
meaningful today.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_GODOT_SRC = STUDIO_ROOT / "godot" / "src"
_REPLAY_DIR = _GODOT_SRC / "replay"
_LIVE_DTO_DIRS = (
    _GODOT_SRC / "protocol" / "dto",
    _GODOT_SRC / "session" / "dto",
    _GODOT_SRC / "battle" / "dto",
)
_ALLOWLIST_FILE = (
    Path(__file__).parent / "architecture_allowlists" / "live_dto_bundle_path_allowlist.txt"
)
_CLASS_NAME_RE = re.compile(r"^class_name\s+(\w+)", re.MULTILINE)


def _replay_files() -> list[Path]:
    return sorted(_REPLAY_DIR.rglob("*.gd"))


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
def test_replay_dir_exists_for_live_dto_scan():
    # A scan root that silently doesn't exist would make the rest of this file vacuously
    # green for the wrong reason -- replay/ is pre-existing Phase-0 code, so it must exist.
    assert _REPLAY_DIR.is_dir()


@pytest.mark.architecture
def test_no_live_dto_type_referenced_from_a_replay_file():
    # This assertion stays meaningful even before protocol/dto/, session/dto/, and battle/dto/
    # exist: _live_dto_class_names() returns an empty set until M1b/M2a/M1c create those
    # directories, at which point every replay/ file (except the allowlisted sink) is
    # immediately covered without any further test change. The scratch fail-check (see the
    # F0 gate-evidence for this slice) proves the mechanism catches a real violation today by
    # temporarily creating a fixture DTO directory and a referencing replay/ file.
    live_dto_names = _live_dto_class_names()
    allowlist = _load_allowlist()
    violations: list[str] = []
    for path in _replay_files():
        rel = path.relative_to(_GODOT_SRC).as_posix()
        if rel in allowlist:
            continue
        text = path.read_text(encoding="utf-8")
        for name in live_dto_names:
            if re.search(rf"\b{re.escape(name)}\b", text):
                violations.append(f"{rel} references live DTO {name}")
    assert not violations, violations

"""Forbidden-dependency guard: HumanBattleCommandGateway (spec section 4.2.3) may only be
referenced from godot/src/ui/panels/ -- the human battle controller's home from M2d onward.
Today (F0) the gateway does not exist yet and zero references exist anywhere; this test is
still meaningful because it is fail-checked with a synthetic violation (see this task's
fail-check steps) before being trusted as a real guard.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_GODOT_SRC = STUDIO_ROOT / "godot" / "src"
_GATEWAY_IDENTIFIER = "HumanBattleCommandGateway"
_ALLOWED_HOLDER_DIR = _GODOT_SRC / "ui" / "panels"


def _all_gd_files() -> list[Path]:
    return sorted(_GODOT_SRC.rglob("*.gd"))


@pytest.mark.architecture
def test_gateway_scan_root_finds_expected_file_count():
    # A scan that silently under-matches its root is worse than no guard at all -- it
    # reports green while checking nothing. 45 .gd files exist under godot/src/ as of F0;
    # this floor stays comfortably below that and below every file F0 itself adds.
    found = _all_gd_files()
    assert len(found) >= 40, f"only found {len(found)} .gd files under godot/src -- scan root is wrong"


@pytest.mark.architecture
def test_no_module_outside_ui_panels_imports_the_human_battle_command_gateway():
    violations: list[str] = []
    pattern = re.compile(rf"\b{_GATEWAY_IDENTIFIER}\b")
    for path in _all_gd_files():
        if _ALLOWED_HOLDER_DIR in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            violations.append(path.relative_to(STUDIO_ROOT).as_posix())
    assert not violations, (
        f"{_GATEWAY_IDENTIFIER} referenced outside "
        f"{_ALLOWED_HOLDER_DIR.relative_to(STUDIO_ROOT).as_posix()}: {violations}"
    )

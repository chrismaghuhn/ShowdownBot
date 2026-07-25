"""Forbidden-dependency guard: HumanBattleCommandGateway (spec section 4.2.3) may only be
referenced from an exact-path allowlist, not from an entire directory tree -- allowlisting
the whole godot/src/ui/panels/ directory would let any future panel file quietly acquire a
gateway reference without a review defect being flagged. The allowlist is EMPTY today (F0):
the gateway does not exist yet and zero references exist anywhere. M2d may add ONLY
godot/src/ui/panels/human_battle_controller.gd and
godot/src/ui/panels/human_battle_command_gateway.gd to the allowlist, via an owner-approved
diff; any broader entry (a directory, a wildcard, or a file outside that pair) is a review
defect. This test is still meaningful before the gateway exists because it is fail-checked
with a synthetic violation (see this task's fail-check steps) before being trusted as a real
guard.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_GODOT_SRC = STUDIO_ROOT / "godot" / "src"
_GATEWAY_IDENTIFIER = "HumanBattleCommandGateway"
# Exact-path allowlist, empty before M2d. Do not widen this to a directory -- see the
# module docstring for why a directory allowlist is the defect this guard replaced.
_ALLOWED_HOLDER_FILES: frozenset[str] = frozenset()


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
def test_no_module_outside_the_exact_file_allowlist_imports_the_human_battle_command_gateway():
    violations: list[str] = []
    pattern = re.compile(rf"\b{_GATEWAY_IDENTIFIER}\b")
    for path in _all_gd_files():
        relative_posix = path.relative_to(STUDIO_ROOT).as_posix()
        if relative_posix in _ALLOWED_HOLDER_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            violations.append(relative_posix)
    assert not violations, (
        f"{_GATEWAY_IDENTIFIER} referenced outside the exact-file allowlist "
        f"{sorted(_ALLOWED_HOLDER_FILES)}: {violations}"
    )

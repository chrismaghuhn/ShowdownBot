"""Guards against double-encoded UTF-8 ("mojibake") creeping back into Studio docs.

Root cause this guard exists for: a checkbox-ticking rewrite of
docs/plans/2026-07-25-phase3-f0-foundation.md used a PowerShell `Get-Content -Raw` read
without `-Encoding`, which decoded the file's UTF-8 bytes as the system ANSI codepage and then
re-encoded that mis-decoded text back to UTF-8 -- turning every multi-byte character (mostly
em dashes) into a several-character garbled sequence. Any tool that reads a UTF-8 file without
declaring UTF-8 explicitly (PowerShell's `Get-Content`/`Set-Content` default to the system
codepage, not UTF-8) can reintroduce this. This test walks the Studio docs tree and fails on
the literal mis-decoded marker sequences that pattern produces, read back as UTF-8.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_DOCS_ROOT = STUDIO_ROOT / "docs"
_TOP_LEVEL_DOCS = (STUDIO_ROOT / "AGENTS.md", STUDIO_ROOT / "README.md")

# Each of these is a literal double-encoded-UTF-8 marker: the mis-decoded byte sequence a
# correctly-encoded em dash / en dash / section sign / arrow / curly quote turns into when
# read as UTF-8 after being round-tripped through the wrong codepage once.
_MOJIBAKE_MARKERS = (
    "â€”",  # "â€”" -- mis-decoded em dash (E2 80 94)
    "â€“",  # "â€“" -- mis-decoded en dash (E2 80 93)
    "Â§",  # "Â§" -- mis-decoded section sign (C2 A7)
    "â†’",  # "â†’" -- mis-decoded rightwards arrow (E2 86 92)
    "â€œ",  # "â€œ" -- mis-decoded left double quote (E2 80 9C)
    "â€",  # "â€\x9d" -- mis-decoded right double quote (E2 80 9D)
)


def _doc_files() -> list[Path]:
    files = sorted(_DOCS_ROOT.rglob("*.md"))
    files.extend(p for p in _TOP_LEVEL_DOCS if p.is_file())
    return files


@pytest.mark.architecture
def test_docs_scan_root_finds_files():
    # A scan root that silently finds nothing would make this guard vacuously green.
    found = _doc_files()
    assert len(found) >= 10, f"only found {len(found)} doc files -- scan root is wrong"


@pytest.mark.architecture
def test_no_double_encoded_utf8_marker_in_studio_docs():
    violations: list[str] = []
    for path in _doc_files():
        text = path.read_text(encoding="utf-8")
        for marker in _MOJIBAKE_MARKERS:
            if marker in text:
                violations.append(f"{path.relative_to(STUDIO_ROOT).as_posix()}: {marker!r}")
    assert not violations, f"double-encoded UTF-8 marker found: {violations}"

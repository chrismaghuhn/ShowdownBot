"""No cross-module public interface may expose an untyped Variant/Array/Dictionary
(AGENTS.md rule 9, spec section 10). See this file's header comment in the allowlist for the
concrete scope of "cross-module," "public," and the audited-boundary exceptions.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_GODOT_SRC = STUDIO_ROOT / "godot" / "src"
_ALLOWLIST_FILE = (
    Path(__file__).parent / "architecture_allowlists" / "untyped_boundary_allowlist.txt"
)
_CLASS_NAME_RE = re.compile(r"^class_name\s+(\w+)", re.MULTILINE)
_FUNC_SIG_RE = re.compile(r"^func\s+([a-zA-Z_]\w*)\s*\((.*?)\)\s*(?:->\s*([^:]+))?:", re.MULTILINE | re.DOTALL)
_BARE_UNTYPED_RE = re.compile(r"\b(Variant|Array|Dictionary)\b(?!\[)")


def _module_dir(path: Path) -> str:
    return path.relative_to(_GODOT_SRC).parts[0]


def _all_gd_files() -> list[Path]:
    return sorted(_GODOT_SRC.rglob("*.gd"))


def _load_allowlist() -> list[str]:
    entries = []
    for line in _ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _is_allowlisted(path: Path, allowlist: list[str]) -> bool:
    rel = path.relative_to(_GODOT_SRC).as_posix()
    for entry in allowlist:
        if entry.endswith("/"):
            if rel.startswith(entry):
                return True
        elif rel == entry:
            return True
    return False


def _class_names_by_file() -> dict[Path, str]:
    mapping: dict[Path, str] = {}
    for path in _all_gd_files():
        match = _CLASS_NAME_RE.search(path.read_text(encoding="utf-8"))
        if match:
            mapping[path] = match.group(1)
    return mapping


def _cross_module_classes() -> set[str]:
    by_file = _class_names_by_file()
    file_texts = {path: path.read_text(encoding="utf-8") for path in _all_gd_files()}
    cross_module: set[str] = set()
    for decl_path, class_name in by_file.items():
        decl_module = _module_dir(decl_path)
        pattern = re.compile(rf"\b{re.escape(class_name)}\b")
        for other_path, text in file_texts.items():
            if other_path == decl_path or _module_dir(other_path) == decl_module:
                continue
            if pattern.search(text):
                cross_module.add(class_name)
                break
    return cross_module


def _public_signature_violations(path: Path) -> list[str]:
    violations = []
    text = path.read_text(encoding="utf-8")
    for match in _FUNC_SIG_RE.finditer(text):
        name, params, ret = match.group(1), match.group(2), match.group(3) or ""
        if name.startswith("_"):
            continue
        if _BARE_UNTYPED_RE.search(params) or _BARE_UNTYPED_RE.search(ret):
            violations.append(f"{path.relative_to(STUDIO_ROOT).as_posix()}::{name}")
    return violations


@pytest.mark.architecture
def test_cross_module_class_scan_finds_at_least_one_cross_module_class():
    # A scan that finds zero cross-module classes has a broken module-dir/identifier match,
    # not a codebase with no shared types -- BundleDTO alone is already used from replay/,
    # decision/, diagnostics/, and workspace/ today.
    found = _cross_module_classes()
    assert "BundleDTO" in found, found


@pytest.mark.architecture
def test_no_untyped_container_in_cross_module_public_interface():
    allowlist = _load_allowlist()
    by_file = _class_names_by_file()
    cross_module = _cross_module_classes()
    violations: list[str] = []
    for path, class_name in by_file.items():
        if class_name not in cross_module or _is_allowlisted(path, allowlist):
            continue
        violations.extend(_public_signature_violations(path))
    assert not violations, f"untyped container in cross-module public interface: {violations}"

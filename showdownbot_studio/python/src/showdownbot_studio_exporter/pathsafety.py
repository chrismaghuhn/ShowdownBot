"""Output path safety guards."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .errors import ExportRefuse

PROTECTED_ROOT_NAMES = ("data/eval", "config/eval", "reports", "showdownbot_studio/fixtures/viewer-v0/sources")


def _normalize_parts(path: Path) -> tuple[str, ...]:
    return tuple(p.lower() for p in path.resolve().parts)


def _is_under(resolved: Path, root: Path) -> bool:
    try:
        resolved.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _protected_roots(repo_root: Path) -> list[Path]:
    roots = []
    for rel in PROTECTED_ROOT_NAMES:
        roots.append((repo_root / rel).resolve())
    return roots


def check_output_path(
    out: Path,
    *,
    input_paths: list[Path],
    repo_root: Path | None = None,
) -> None:
    out = out.resolve()
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[4]

    for protected in _protected_roots(repo_root):
        if _is_under(out, protected):
            raise ExportRefuse("output_inside_protected_tree", f"output under protected root {protected}")

    for inp in input_paths:
        if inp is None:
            continue
        parent = inp.resolve().parent
        if _is_under(out, parent):
            raise ExportRefuse("output_inside_protected_tree", f"output under input parent {parent}")

    if out.exists():
        raise ExportRefuse("output_exists", f"output already exists: {out}")


def refuse_if_symlink_escapes(out: Path, protected: Path) -> None:
    """Refuse when out resolves inside protected via symlink/junction."""
    if sys.platform == "win32":
        # resolve() follows symlinks/junctions on Windows
        if _is_under(out.resolve(), protected.resolve()):
            raise ExportRefuse("output_inside_protected_tree", "output resolves into protected tree via link")

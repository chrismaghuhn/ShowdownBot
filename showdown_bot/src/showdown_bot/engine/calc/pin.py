"""Pinned @smogon/calc manifest load + fail-closed artifact verification (I4 §5.4)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

DEFAULT_CALC_DIR = Path(__file__).resolve().parents[4] / "tools" / "calc"
PINNED_CALC_FILENAME = "PINNED_CALC.json"


class PinnedCalcError(RuntimeError):
    """Pinned calc manifest or artifact verification failed."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned_calc_manifest(*, calc_dir: Path | None = None) -> dict:
    """Load ``PINNED_CALC.json`` and verify ``artifact_sha256`` against vendor ``.tgz``."""
    base = calc_dir or DEFAULT_CALC_DIR
    manifest_path = base / PINNED_CALC_FILENAME
    if not manifest_path.is_file():
        raise PinnedCalcError(f"missing pinned calc manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filename = manifest.get("artifact_filename")
    expected = manifest.get("artifact_sha256")
    if not filename or not expected:
        raise PinnedCalcError(
            f"{manifest_path}: missing artifact_filename or artifact_sha256"
        )

    artifact_path = base / "vendor" / filename
    if not artifact_path.is_file():
        raise PinnedCalcError(f"missing pinned calc artifact: {artifact_path}")

    actual = _sha256_file(artifact_path)
    if actual != expected:
        raise PinnedCalcError(
            f"artifact SHA-256 mismatch for {filename}\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}"
        )
    return manifest


def calc_pin_hash(*, calc_dir: Path | None = None) -> str:
    """SHA-256[:16] of committed ``PINNED_CALC.json`` UTF-8 bytes (after artifact verify)."""
    base = calc_dir or DEFAULT_CALC_DIR
    manifest_path = base / PINNED_CALC_FILENAME
    load_pinned_calc_manifest(calc_dir=base)
    return _sha256_file(manifest_path)[:16]


def format_config_hash(source_path: Path) -> str:
    """SHA-1[:16] of resolved format yaml bytes."""
    return hashlib.sha1(source_path.read_bytes()).hexdigest()[:16]

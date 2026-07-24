"""Reseal a bundle manifest.json's sha256 fields to match its files' actual bytes.

Developer tool, run by hand when a fixture's committed bytes and its manifest's
declared sha256 have drifted (e.g. the file was hand-edited after the manifest was
generated). Verify-only guards (pytest / gdUnit) must never call this -- it is the
opposite of a check, it heals the very drift the guards exist to catch.

Usage:
    python reseal_manifest_hashes.py <bundle_dir> [<bundle_dir> ...]

For each declared-present file in <bundle_dir>/manifest.json whose sha256 does not
match the file's actual bytes, updates that entry and rewrites manifest.json via the
same RFC 8785 canonicalizer the exporter uses (showdownbot_studio_exporter.canonicalize),
so the resealed file stays byte-for-byte canonical. Prints each changed hash.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ponytail: prepend this worktree's src/ so the script is correct regardless of what
# showdownbot_studio_exporter is installed (editable installs bind to whichever tree ran
# `pip install -e`, which may not be this checkout).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from showdownbot_studio_exporter.canonicalize import dumps  # type: ignore[import-not-found]  # noqa: E402
from showdownbot_studio_exporter.hashutil import sha256_file  # type: ignore[import-not-found]  # noqa: E402


def reseal(bundle_dir: Path) -> list[tuple[str, str, str]]:
    """Rewrite drifted sha256 entries in bundle_dir/manifest.json. Returns (key, old, new)."""
    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changes: list[tuple[str, str, str]] = []
    for key, entry in manifest.get("files", {}).items():
        if not entry.get("present"):
            continue
        actual = sha256_file(bundle_dir / entry["path"])
        declared = entry.get("sha256")
        if actual != declared:
            entry["sha256"] = actual
            changes.append((key, declared, actual))
    if changes:
        manifest_path.write_bytes(dumps(manifest))
    return changes


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)  # noqa: T201 -- CLI report output, this script's entire purpose
        return 2
    for arg in argv:
        bundle_dir = Path(arg)
        for key, old, new in reseal(bundle_dir):
            print(f"{bundle_dir}: {key} {old} -> {new}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

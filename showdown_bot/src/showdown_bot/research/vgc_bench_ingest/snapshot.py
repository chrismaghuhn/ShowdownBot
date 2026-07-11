"""Source-file snapshot manifest for VGC-Bench sample ingestion (2b-5a Part A Task 1).

Pure + deterministic: no wall-clock reads (``created_at`` is always injected by
the caller) and no filesystem side effects beyond hashing the given file.
"""
from __future__ import annotations

import hashlib
import os

_CHUNK_SIZE = 1 << 20  # 1 MiB


def sha256_file(path: str | os.PathLike) -> str:
    """sha256 hex digest of a file's bytes, streamed in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_sample_manifest(
    *,
    source: str,
    source_revision: str | None,
    dataset_file: str,
    dataset_file_sha256: str,
    format_filter: str | None,
    sample_size: int,
    license: str,
    created_at: str,
    purpose: str = "ingestion_prototype_only",
) -> dict:
    """Build a manifest dict describing a local VGC-Bench sample snapshot.

    Pure: no I/O, no clock reads. ``created_at`` must be injected by the
    caller. Returned dict's keys are sorted alphabetically so serialization
    (e.g. ``json.dumps``) is stable regardless of dict insertion order.
    """
    manifest = {
        "created_at": created_at,
        "dataset_file": dataset_file,
        "dataset_file_sha256": dataset_file_sha256,
        "format_filter": format_filter,
        "license": license,
        "purpose": purpose,
        "sample_size": sample_size,
        "source": source,
        "source_revision": source_revision,
    }
    return dict(sorted(manifest.items()))

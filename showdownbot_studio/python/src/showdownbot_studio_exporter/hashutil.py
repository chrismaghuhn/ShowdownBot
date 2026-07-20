"""Hash helpers — request_hash uses bot recipe (sort_keys json.dumps + sha256)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_hash_from_payload(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def request_hash_from_request_dump(dump: dict[str, Any]) -> str:
    """Offline/live recipe: model_dump(mode='json', by_alias=True, exclude_none=False)."""
    return request_hash_from_payload(dump)

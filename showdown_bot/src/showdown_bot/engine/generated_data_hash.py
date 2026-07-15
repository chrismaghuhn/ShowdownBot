from __future__ import annotations

import hashlib
import json
import re

_DATA_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


def embedded_table_hash(raw: dict, table_key: str) -> str:
    payload = json.dumps(
        raw[table_key],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def verify_embedded_data_hash(
    raw: dict,
    table_key: str,
    *,
    label: str,
    stale_error: type[Exception],
) -> str:
    """Return the embedded 16-hex data_hash only when present, well-formed, and fresh."""
    expected = raw.get("data_hash")
    if expected is None or not _DATA_HASH_RE.fullmatch(str(expected)):
        raise stale_error(f"{label}: missing or malformed data_hash: {expected!r}")
    actual = embedded_table_hash(raw, table_key)
    if actual != expected:
        raise stale_error(f"{label} stale: embedded {expected!r} != computed {actual!r}")
    return str(expected)

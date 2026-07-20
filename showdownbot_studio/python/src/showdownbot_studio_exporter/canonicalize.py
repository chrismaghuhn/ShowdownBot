"""RFC 8785 JCS wrapper — never use json.dumps for bundle bytes."""

from __future__ import annotations

from typing import Any

import rfc8785


class CanonicalizeError(ValueError):
    """Non-finite floats or other inputs refused by the exporter JCS policy."""


def _refuse_nonfinite(value: Any) -> None:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise CanonicalizeError("non-finite float refused")
        return
    if isinstance(value, dict):
        for item in value.values():
            _refuse_nonfinite(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _refuse_nonfinite(item)


def dumps(value: Any) -> bytes:
    """Canonicalize ``value`` with rfc8785; refuse NaN/Inf before library call."""
    _refuse_nonfinite(value)
    return rfc8785.dumps(value)

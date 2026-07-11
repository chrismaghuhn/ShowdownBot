"""Strict JSON loader for the VGC-Bench outer wrapper (2b-5a Part A Task 1).

The dataset card documents the wrapper as a JSON object mapping
``battle-id -> [epoch_seconds, battle_log_string]``. This loader trusts
nothing: any entry that doesn't fit that shape raises ``VgcBenchParseError``
naming the offending battle_id. Malformed entries are never silently skipped
(fail-closed, per the package's ingestion-prototype invariant).
"""
from __future__ import annotations

import json

from .schema import VgcBenchParseError


def load_raw(json_text: str) -> dict[str, tuple[int, str]]:
    """Parse the VGC-Bench JSON wrapper into ``{battle_id: (epoch, log)}``.

    Raises ``VgcBenchParseError`` (naming the battle_id) if any value isn't a
    2-element ``[epoch, log]`` list with an int-coercible epoch and a string
    log, or if the top-level JSON isn't an object.
    """
    try:
        raw = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise VgcBenchParseError(f"invalid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise VgcBenchParseError(
            f"top-level JSON must be an object mapping battle_id -> [epoch, log], "
            f"got {type(raw).__name__}"
        )

    entries: dict[str, tuple[int, str]] = {}
    for battle_id, value in raw.items():
        if not isinstance(value, list) or len(value) != 2:
            raise VgcBenchParseError(
                f"{battle_id}: expected a 2-element [epoch, log] list, got {value!r}"
            )
        epoch_raw, log_raw = value
        if isinstance(epoch_raw, bool):
            raise VgcBenchParseError(f"{battle_id}: epoch must be int-coercible, got {epoch_raw!r}")
        try:
            epoch = int(epoch_raw)
        except (TypeError, ValueError) as exc:
            raise VgcBenchParseError(
                f"{battle_id}: epoch must be int-coercible, got {epoch_raw!r}"
            ) from exc
        if not isinstance(log_raw, str):
            raise VgcBenchParseError(
                f"{battle_id}: log must be a string, got {type(log_raw).__name__}"
            )
        entries[battle_id] = (epoch, log_raw)
    return entries

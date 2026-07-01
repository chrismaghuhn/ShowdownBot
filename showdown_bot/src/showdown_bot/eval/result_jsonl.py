"""Per-battle result JSONL (T2): the pairing substrate for later reporting (T5).

One validated row per battle; validate-on-write + append-only (parent plan T2-CC-1/2).
No stats, no McNemar/Wilson, no report — those are T5.

Config provenance (T2 review Fix 1): ``config_id`` = the evaluated bot config/version
(e.g. ``heuristic``/``shadow``/``override``/``prev_version``) — NOT the format;
``format_id`` = the Showdown format; ``config_hash`` = a stable hash of the effective
eval config (simple in T2, but present so later slices don't break the row schema).
"""
from __future__ import annotations

import hashlib
import json

REQUIRED_FIELDS = frozenset({
    "battle_id", "config_id", "format_id", "config_hash", "schedule_hash", "seed_index",
    "opp_policy", "hero_team_path", "opp_team_path", "seed", "winner", "turns",
    "invalid_choices", "crashes", "decision_latency_p95_ms", "git_sha",
})
NULLABLE_FIELDS = frozenset({"end_hp_diff", "timeouts", "room_raw_path", "panel_hash"})
_WINNERS = frozenset({"hero", "villain", "tie"})


class ResultRowError(ValueError):
    """A battle-result row is missing a required field or has an invalid value."""


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def make_battle_id(schedule_hash: str, seed_index: int, seed: str) -> str:
    return hashlib.sha1(_canonical([schedule_hash, seed_index, seed]).encode("utf-8")).hexdigest()[:16]


def make_config_hash(config_id: str, format_id: str) -> str:
    """Stable hash of the effective eval config (simple in T2; the field must exist)."""
    return hashlib.sha1(
        _canonical({"config_id": config_id, "format_id": format_id}).encode("utf-8")
    ).hexdigest()[:16]


def validate_battle_row(row: dict) -> None:
    for f in REQUIRED_FIELDS:
        if f not in row:
            raise ResultRowError(f"missing required field: {f}")
        if row[f] is None:
            raise ResultRowError(f"required field is None: {f}")
    if row["winner"] not in _WINNERS:
        raise ResultRowError(f"winner must be one of {sorted(_WINNERS)}, got {row['winner']!r}")
    unknown = set(row) - REQUIRED_FIELDS - NULLABLE_FIELDS
    if unknown:
        raise ResultRowError(f"unknown fields: {sorted(unknown)}")


def to_jsonl_line(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


class BattleResultWriter:
    """Append-only writer: validate-on-write, one JSON row per line (T2-CC-1/2)."""

    def __init__(self, path: str):
        self.path = path

    def write(self, row: dict) -> None:
        validate_battle_row(row)  # fail fast before appending — never a half-written row
        with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(to_jsonl_line(row) + "\n")

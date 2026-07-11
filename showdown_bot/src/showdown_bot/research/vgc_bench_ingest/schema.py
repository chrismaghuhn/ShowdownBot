"""Frozen data shapes for VGC-Bench raw-battle ingestion (2b-5a Part A Task 1).

External-replay ingestion only -- see the package docstring / README invariant
(INV-1): never imported by the live decision path, teacher, or reranker.
"""
from __future__ import annotations

from dataclasses import dataclass


class VgcBenchParseError(Exception):
    """Raised when a VGC-Bench dataset entry or battle log fails strict parsing.

    Fail-closed by design: malformed input is never silently skipped. The
    message always names the offending battle_id.
    """


@dataclass(frozen=True)
class VgcBenchRawBattle:
    """One parsed VGC-Bench battle.

    ``winner``, ``is_tie``, ``turns``, and ``end_reason`` are RE-DERIVED from
    the raw log via ``eval.battle_parse.parse_battle_result`` -- never trusted
    from any external field. ``raw_log_sha256``/``normalized_log_sha256`` are
    deterministic hashes of the raw log bytes and the normalized (session-
    metadata-stripped) protocol respectively, so two parses of the same log
    are byte-for-byte comparable.
    """

    battle_id: str
    epoch_seconds: int
    raw_log_sha256: str
    normalized_log_sha256: str
    format_name: str
    gametype: str
    players: tuple[tuple[str, str], ...]
    rules: tuple[str, ...]
    log_lines: tuple[str, ...]
    winner: str | None
    is_tie: bool
    turns: int
    end_reason: str

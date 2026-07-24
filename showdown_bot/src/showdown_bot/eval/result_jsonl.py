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
import re

REQUIRED_FIELDS = frozenset({
    "battle_id", "run_id", "config_id", "format_id", "config_hash", "schedule_hash", "seed_index",
    "opp_policy", "hero_team_path", "opp_team_path", "seed", "seed_base", "winner", "turns",
    "invalid_choices", "crashes", "decision_latency_p95_ms", "git_sha", "dirty", "end_reason",
})
# hero_team_hash/opp_team_hash are team-content provenance (T3e P4): present for
# panel-generated schedules, null for legacy schedules that carry no team hashes.
NULLABLE_FIELDS = frozenset({
    "end_hp_diff", "timeouts", "room_raw_path", "panel_hash", "hero_team_hash", "opp_team_hash",
    "panel_split",  # T3f Task 4: "dev"/"heldout" from the schedule row; null for legacy schedules
    # T4c R1: sha256 over the normalized room log, binding the row to its log. Null when
    # hashing failed (never fails the battle record) or absent for legacy rows written
    # before this field existed -- every consumer must tolerate both.
    "normalized_room_log_sha256",
    # Task 3 (decision sidecar binding): count + sha256 of the per-battle decision trace
    # sidecar file. Both null/absent when decision capture is off (the default) or for
    # legacy rows written before this field existed -- every consumer must tolerate both.
    "decision_trace_count", "decision_trace_sha256",
    # Gate B finding 4: per-SEAT counts of decisions that did not complete on the agent's
    # intended path. Nullable because rows written before this field existed must still
    # validate -- but see compute_safety_pass: for a GATE run, absent is refused, never read
    # as zero.
    "hero_degraded_decisions", "villain_degraded_decisions",
    # Gate B finding 5: per-SEAT invalid-choice counts. `invalid_choices` (REQUIRED, above) is
    # the historical SUM and is kept unchanged -- these are ADDITIVE, so a baseline-side illegal
    # action is attributable to that seat rather than failing the candidate with nothing on the
    # row able to show it. Nullable for the same reason as the degraded counters: legacy rows,
    # including every frozen Gate B row, carry no such field and must still validate.
    "hero_invalid_choices", "villain_invalid_choices",
})
_DEGRADED_COUNTERS = ("hero_degraded_decisions", "villain_degraded_decisions")
_SEAT_INVALID_COUNTERS = ("hero_invalid_choices", "villain_invalid_choices")
_WINNERS = frozenset({"hero", "villain", "tie"})
# T3f Task 5: how the battle ended. "normal" = ordinary |win|/|tie|; the others are
# detected from room_raw markers (see eval.battle_parse._detect_end_reason).
_END_REASONS = frozenset({"normal", "timeout", "forfeit", "crash"})


class ResultRowError(ValueError):
    """A battle-result row is missing a required field or has an invalid value."""


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def make_battle_id(schedule_hash: str, seed_index: int, seed: str) -> str:
    """Deterministic **pairing key** for a battle: sha1(schedule_hash, seed_index, seed)[:16].

    battle_id identifies the *battle slot* (same schedule + seed_index + seed), so it MAY
    repeat across paired config runs — that is exactly how two runs are paired for later
    analysis. It is NOT a globally-unique row id: row identity for paired analysis is the
    battle_id together with the config being evaluated (e.g. config_hash), not battle_id alone.
    """
    return hashlib.sha1(_canonical([schedule_hash, seed_index, seed]).encode("utf-8")).hexdigest()[:16]


def make_config_hash(manifest: dict) -> str:
    """Stable, order-independent hash of the effective-config manifest (T3f Task 1).

    Two behaviorally-different bots MUST get different hashes; changes to denylisted or
    captured-by-reason env vars MUST NOT change it (they are simply absent from
    ``manifest['env']`` — see ``eval.config_env``). Build the manifest with
    ``config_env.build_config_manifest``.
    """
    return hashlib.sha1(_canonical(manifest).encode("utf-8")).hexdigest()[:16]


def validate_battle_row(row: dict) -> None:
    for f in REQUIRED_FIELDS:
        if f not in row:
            raise ResultRowError(f"missing required field: {f}")
        if row[f] is None:
            raise ResultRowError(f"required field is None: {f}")
    if row["winner"] not in _WINNERS:
        raise ResultRowError(f"winner must be one of {sorted(_WINNERS)}, got {row['winner']!r}")
    if row["end_reason"] not in _END_REASONS:
        raise ResultRowError(
            f"end_reason must be one of {sorted(_END_REASONS)}, got {row['end_reason']!r}"
        )
    unknown = set(row) - REQUIRED_FIELDS - NULLABLE_FIELDS
    if unknown:
        raise ResultRowError(f"unknown fields: {sorted(unknown)}")
    count = row.get("decision_trace_count")
    digest = row.get("decision_trace_sha256")
    if (count is None) != (digest is None):
        raise ResultRowError("decision trace count and sha256 must be present together")
    if count is not None and (not isinstance(count, int) or count <= 0):
        raise ResultRowError("decision_trace_count must be a positive int")
    if digest is not None and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
        raise ResultRowError("decision_trace_sha256 must be lowercase sha256 hex")
    # Same non-negative-int check for both counter families -- reused, not duplicated, because
    # the type-safety requirement is identical: bool is an int in Python and 0.0 == 0, so both
    # must be refused explicitly or a type-wrong counter reads as a clean zero.
    for name in (*_DEGRADED_COUNTERS, *_SEAT_INVALID_COUNTERS):
        value = row.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ResultRowError(f"{name} must be a non-negative int, got {value!r}")


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

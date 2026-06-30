"""Deterministic JSONL export for the reranker dataset (Phase 3 slice 1b-B2).

Takes finished schema Rows -> validated, stably-sorted, byte-identical JSONL. No
Trace/State, no client wiring (that is 1b-B3). No wall-clock, no UUIDs, no unseeded
randomness — IDs are content/seed-derived sha1.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from showdown_bot.learning.schema import Row, validate_row, to_jsonl_line


def _sha16(*parts) -> str:
    # canonical JSON (not ":".join) so delimiters cannot collide:
    # ("a:b", "c") and ("a", "b:c") must hash differently.
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def make_run_id(git_sha, dirty_flag, team_hash, config_hash, run_seed) -> str:
    return _sha16(git_sha, dirty_flag, team_hash, config_hash, run_seed)


def make_game_id(run_id, game_index) -> str:
    return _sha16(run_id, game_index)


def make_decision_id(game_id, decision_local_index, turn_number, our_side) -> str:
    return _sha16(game_id, decision_local_index, turn_number, our_side)

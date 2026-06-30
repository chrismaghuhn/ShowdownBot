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


@dataclass
class SamplingPolicy:
    policy: str = "all"      # "all" | "every_nth"
    rate: int = 1            # used by every_nth
    seed: int = 0            # reserved for future seeded sampling; deterministic

    def should_sample(self, decision_index: int) -> bool:
        if self.policy == "all":
            return True
        if self.policy == "every_nth":
            if self.rate <= 0:                       # fail-fast, never silently normalize
                raise ValueError("every_nth sampling rate must be > 0")
            return decision_index % self.rate == 0
        raise ValueError(f"unknown sampling policy: {self.policy}")


class DatasetExporter:
    """Buffers finished, validated Rows; writes stably-sorted byte-identical JSONL.
    Takes Row objects only — never Trace/State. Sampling is applied upstream (1b-B3);
    this holds a SamplingPolicy for that caller to consult."""

    def __init__(self, sampling_policy: SamplingPolicy | None = None) -> None:
        self.sampling_policy = sampling_policy or SamplingPolicy()
        self._rows: list[Row] = []

    def add(self, row: Row) -> None:
        validate_row(row)        # gate 2: never buffer an invalid row
        self._rows.append(row)

    def _sorted(self) -> list[Row]:
        return sorted(
            self._rows,
            key=lambda r: (
                str(r.metadata.get("game_id", "")),
                str(r.metadata.get("decision_id", "")),
                int(r.metadata.get("candidate_index", 0)),
            ),
        )

    def rows_for_test(self) -> list[Row]:
        return self._sorted()

    def to_jsonl(self) -> str:
        return "".join(to_jsonl_line(r) + "\n" for r in self._sorted())

    def flush_sorted(self, file_or_path) -> None:
        text = self.to_jsonl()
        if hasattr(file_or_path, "write"):
            file_or_path.write(text)
        else:
            # newline="\n" => byte-identical across OSes (no CRLF translation)
            with open(file_or_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)

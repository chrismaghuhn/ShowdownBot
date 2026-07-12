from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

SIDECAR_SCHEMA_VERSION = "outcome-join-sidecar-v1"
REPORT_SCHEMA_VERSION = "outcome-join-report-v1"
_WINNER_TO_OUTCOME = {"hero": 1.0, "villain": -1.0, "tie": 0.0}


class OutcomeJoinError(ValueError):
    pass


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def content_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_jsonl(path) -> list[dict]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    rows = []
    with opener(path, "rt", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise OutcomeJoinError(f"{path}:{line_no}: {exc}") from exc
    return rows


def encode_game_outcome(winner: str) -> float:
    if winner not in _WINNER_TO_OUTCOME:
        raise OutcomeJoinError(f"unknown winner {winner!r}; expected hero/villain/tie")
    return _WINNER_TO_OUTCOME[winner]


@dataclass(frozen=True)
class AuditConfig:
    schema_version: str = SIDECAR_SCHEMA_VERSION
    dirty_candidates: tuple[bool, ...] = (True, False)
    run_seed_candidates: tuple[int, ...] = (0,)

    def validate(self) -> None:
        if not self.dirty_candidates or not self.run_seed_candidates:
            raise OutcomeJoinError("candidate sweeps must be non-empty")


@dataclass(frozen=True)
class OutcomeLabel:
    game_id: str
    battle_id: str
    team_hash: str
    seed_index: int
    winner: str
    game_outcome: float
    final_turn: int

    def validate(self) -> "OutcomeLabel":
        if self.winner not in _WINNER_TO_OUTCOME:
            raise OutcomeJoinError(f"unknown winner {self.winner!r}")
        if self.game_outcome != _WINNER_TO_OUTCOME[self.winner]:
            raise OutcomeJoinError("game_outcome inconsistent with winner")
        if not isinstance(self.final_turn, int) or self.final_turn < 0:
            raise OutcomeJoinError("final_turn must be a non-negative int")
        if not isinstance(self.seed_index, int) or self.seed_index < 0:
            raise OutcomeJoinError("seed_index must be a non-negative int")
        return self

    def to_row(self) -> dict:
        self.validate()
        return {
            "schema_version": SIDECAR_SCHEMA_VERSION,
            "game_id": self.game_id, "battle_id": self.battle_id,
            "team_hash": self.team_hash, "seed_index": self.seed_index,
            "winner": self.winner, "game_outcome": self.game_outcome,
            "final_turn": self.final_turn,
        }

    @classmethod
    def from_row(cls, row: dict) -> "OutcomeLabel":
        if row.get("schema_version") != SIDECAR_SCHEMA_VERSION:
            raise OutcomeJoinError("unknown sidecar schema version")
        return cls(
            game_id=str(row["game_id"]), battle_id=str(row["battle_id"]),
            team_hash=str(row["team_hash"]), seed_index=int(row["seed_index"]),
            winner=str(row["winner"]), game_outcome=float(row["game_outcome"]),
            final_turn=int(row["final_turn"]),
        ).validate()

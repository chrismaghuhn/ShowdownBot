from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.learning.export import make_run_id, make_game_id
from showdown_bot.learning.outcome_join.contracts import OutcomeJoinError


@dataclass(frozen=True)
class DatasetGroup:
    key: tuple[str, str, str]           # (git_sha, team_hash, config_hash)
    git_sha: str
    team_hash: str
    config_hash: str
    game_ids: frozenset[str]
    max_turn_by_game: dict[str, int]    # game_id -> max features.turn_number


@dataclass(frozen=True)
class BridgeMapping:
    key: tuple[str, str, str]
    constants: tuple[bool, int]         # (dirty, run_seed)
    game_to_seed: dict[str, int]        # game_id -> seed_index (bijective)


def group_dataset_rows(rows: list[dict]) -> list[DatasetGroup]:
    acc: dict[tuple, dict] = {}
    for row in rows:
        md = row["metadata"]
        key = (str(md["git_sha"]), str(md["team_hash"]), str(md["config_hash"]))
        gid = str(md["game_id"])
        turn = int(row["features"]["turn_number"])
        bucket = acc.setdefault(key, {"games": {}})
        prev = bucket["games"].get(gid)
        bucket["games"][gid] = turn if prev is None else max(prev, turn)
    groups = []
    for key, bucket in sorted(acc.items()):
        games = bucket["games"]
        groups.append(DatasetGroup(
            key=key, git_sha=key[0], team_hash=key[1], config_hash=key[2],
            game_ids=frozenset(games), max_turn_by_game=dict(games)))
    return groups


def reconstruct_mapping(group: DatasetGroup, results: list[dict], *,
                        dirty_candidates, run_seed_candidates) -> BridgeMapping | None:
    """Return the UNIQUE (dirty, run_seed) whose replayed game_ids bijectively
    cover the group's game_ids, else None (fail-closed: ambiguous or no match)."""
    seed_indices = sorted(int(r["seed_index"]) for r in results)
    if seed_indices != list(range(len(results))):
        raise OutcomeJoinError("results seed_index must be contiguous from 0")
    solutions = []
    for dirty in dirty_candidates:
        for run_seed in run_seed_candidates:
            run_id = make_run_id(group.git_sha, dirty, group.team_hash,
                                 group.config_hash, run_seed)
            expected = {make_game_id(run_id, s): s for s in seed_indices}
            if len(expected) == len(seed_indices) and \
                    frozenset(expected) == group.game_ids:
                solutions.append(BridgeMapping(group.key, (dirty, run_seed), expected))
    if len(solutions) != 1:
        return None       # 0 = no cover, >1 = ambiguous -> fail-closed
    return solutions[0]

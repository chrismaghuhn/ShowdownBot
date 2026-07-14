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
    """Return the UNIQUE (dirty, run_seed) whose replayed game_ids cover the
    group's game_ids, else None (fail-closed: ambiguous or no match).

    Coverage is a SUBSET check (group.game_ids <= replayed game_ids), not exact
    set equality: a results file can legitimately record MORE battles than the
    dataset has games for -- e.g. a battle whose sampling gate selected zero
    decisions never produces a dataset row, so its game_id never appears in any
    group.game_ids even though the battle was played and has a results row
    (real-world instance: phase3-slice2b25a's trickroom hero played 75 battles
    but only 74 produced dataset rows -- see that dataset's manifest.json
    "trickroom_zero_sample_game" note). The returned mapping is trimmed to
    exactly the group's own game_ids (the extra, dataset-absent battles are
    dropped), so it stays bijective **over the group** for downstream
    consumers (`integrity.check_group`'s exact-equality coverage check,
    `join.build_labels`).
    """
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
                    group.game_ids <= frozenset(expected):
                covering = {gid: seed for gid, seed in expected.items()
                           if gid in group.game_ids}
                solutions.append(BridgeMapping(group.key, (dirty, run_seed), covering))
    if len(solutions) != 1:
        return None       # 0 = no cover, >1 = ambiguous -> fail-closed
    return solutions[0]

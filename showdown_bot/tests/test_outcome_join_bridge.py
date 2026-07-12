import pytest
from showdown_bot.learning.export import make_run_id, make_game_id
from showdown_bot.learning.outcome_join.bridge import (
    DatasetGroup, group_dataset_rows, reconstruct_mapping,
)

GIT, TEAM, CFG = "gitsha", "teamA", "cfgA"

def _dataset_rows(n, dirty=True, run_seed=0):
    run_id = make_run_id(GIT, dirty, TEAM, CFG, run_seed)
    rows = []
    for gi in range(n):
        gid = make_game_id(run_id, gi)
        # two candidate-rows per game, turn_number below the true 'turns'
        for turn in (1, 3):
            rows.append({"metadata": {"game_id": gid, "git_sha": GIT,
                                      "team_hash": TEAM, "config_hash": CFG},
                         "features": {"turn_number": turn}})
    return rows

def _results(n, turns=9):
    return [{"battle_id": f"b{gi}", "seed_index": gi, "winner": "hero",
             "turns": turns, "hero_team_hash": TEAM} for gi in range(n)]

def test_group_key_is_git_team_config():
    groups = group_dataset_rows(_dataset_rows(2))
    assert len(groups) == 1
    g = groups[0]
    assert g.key == (GIT, TEAM, CFG)
    assert sorted(g.max_turn_by_game.values()) == [3, 3]  # max(1,3) per game

def test_reconstruct_finds_unique_constants_and_maps_game_to_seed():
    g = group_dataset_rows(_dataset_rows(3))[0]
    m = reconstruct_mapping(g, _results(3), dirty_candidates=(True, False),
                            run_seed_candidates=(0,))
    assert m.constants == (True, 0)
    assert set(m.game_to_seed.values()) == {0, 1, 2}
    assert len(m.game_to_seed) == 3  # bijective

def test_reconstruct_returns_none_when_no_constant_covers():
    g = group_dataset_rows(_dataset_rows(3, dirty=True))[0]
    # sweep excludes the true constant -> no bijective cover
    m = reconstruct_mapping(g, _results(3), dirty_candidates=(False,),
                            run_seed_candidates=(0,))
    assert m is None

def test_reconstruct_rejects_ambiguous_multiple_matches():
    g = group_dataset_rows(_dataset_rows(1))[0]
    # a single game can be covered by >1 constant if results has 1 seed;
    # ambiguity must yield None (fail-closed), never a guess.
    m = reconstruct_mapping(g, _results(1), dirty_candidates=(True, False),
                            run_seed_candidates=(0, 1))
    assert m is None or m.constants == (True, 0)

def test_reconstruct_covers_dataset_that_is_a_strict_subset_of_results_battles():
    # Real-world edge case (phase3-slice2b25a's trickroom hero): a results file
    # can record MORE played battles than the dataset has games for, because a
    # battle whose sampling gate selected zero decisions never produces a
    # dataset row/game_id at all. reconstruct_mapping must still find the
    # unique (dirty, run_seed) and return a mapping trimmed to exactly the
    # dataset's own games -- never guessing at the missing one.
    run_id = make_run_id(GIT, True, TEAM, CFG, 0)
    all_game_ids = [make_game_id(run_id, gi) for gi in range(4)]
    rows = []
    for gi in (0, 1, 3):  # game 2's battle produced zero dataset rows
        for turn in (1, 3):
            rows.append({"metadata": {"game_id": all_game_ids[gi], "git_sha": GIT,
                                      "team_hash": TEAM, "config_hash": CFG},
                         "features": {"turn_number": turn}})
    g = group_dataset_rows(rows)[0]
    m = reconstruct_mapping(g, _results(4), dirty_candidates=(True, False),
                            run_seed_candidates=(0,))
    assert m is not None
    assert m.constants == (True, 0)
    assert set(m.game_to_seed) == {all_game_ids[0], all_game_ids[1], all_game_ids[3]}
    assert m.game_to_seed[all_game_ids[0]] == 0
    assert m.game_to_seed[all_game_ids[3]] == 3

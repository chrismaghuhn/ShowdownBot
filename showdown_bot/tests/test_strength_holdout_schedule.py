import pytest

from showdown_bot.eval.strength_holdout_schedule import (
    build_strength_holdout_schedule, STRENGTH_HOLDOUT_N_SEEDS,
    STRENGTH_HOLDOUT_OPPONENT_POLICIES, STRENGTH_HOLDOUT_FORMAT_ID,
)


def _six_teams():
    return sorted(f"holdout_{i}" for i in range(6))


def test_schedule_has_exactly_180_battle_keys():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    assert len(schedule.battle_keys) == 180


def test_seed_index_is_globally_contiguous_0_to_179_with_no_duplicates():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    indices = sorted(k.seed_index for k in schedule.battle_keys)
    assert indices == list(range(180))


def test_local_seed_repeats_across_the_12_team_policy_cells_but_seed_index_never_does():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    # local `seed` (0-14) legitimately repeats once per (team, policy) cell -- 12 cells x 15 = 180
    local_seed_counts = {}
    for k in schedule.battle_keys:
        local_seed_counts[k.seed] = local_seed_counts.get(k.seed, 0) + 1
    assert local_seed_counts == {s: 12 for s in range(15)}
    # but the pair (team, policy, seed) is unique, and seed_index is unique per key
    triples = {(k.holdout_team_id, k.opponent_policy, k.seed) for k in schedule.battle_keys}
    assert len(triples) == 180
    seed_indices = {k.seed_index for k in schedule.battle_keys}
    assert len(seed_indices) == 180


def test_schedule_rejects_wrong_team_count():
    with pytest.raises(ValueError, match="exactly 6 teams"):
        build_strength_holdout_schedule(holdout_team_ids=_six_teams()[:5], panel_hash="a" * 16)


def test_schedule_rejects_duplicate_teams():
    with pytest.raises(ValueError, match="unique"):
        build_strength_holdout_schedule(holdout_team_ids=["holdout_0"] * 6, panel_hash="a" * 16)


def test_schedule_rejects_unsorted_teams():
    unsorted = ["holdout_5", "holdout_0", "holdout_1", "holdout_2", "holdout_3", "holdout_4"]
    with pytest.raises(ValueError, match="sorted"):
        build_strength_holdout_schedule(holdout_team_ids=unsorted, panel_hash="a" * 16)


def test_schedule_is_deterministic():
    a = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    b = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    assert a.schedule_hash == b.schedule_hash


def test_schedule_hash_changes_if_a_team_changes():
    a = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    other = sorted(list(_six_teams())[:5] + ["holdout_other"])
    b = build_strength_holdout_schedule(holdout_team_ids=other, panel_hash="a" * 16)
    assert a.schedule_hash != b.schedule_hash


def test_format_id_is_the_current_champions_regulation():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    assert schedule.format_id == "gen9championsvgc2026regma" == STRENGTH_HOLDOUT_FORMAT_ID

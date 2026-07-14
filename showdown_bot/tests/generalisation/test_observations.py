# tests/generalisation/test_observations.py
from types import SimpleNamespace
import pytest

from showdown_bot.analysis.generalisation.observations import ObservationError, build_observation_bundle


def test_observation_joins_cell_and_novelty(monkeypatch):
    row = {"run_id": "run", "battle_id": "battle", "schedule_hash": "schedule",
           "seed_base": "base", "seed_index": 0, "seed": "seed", "config_id": "candidate",
           "config_hash": "cfg", "git_sha": "git", "dirty": False,
           "format_id": "gen9vgc2025regi", "panel_hash": "panel", "panel_split": "dev",
           "hero_team_hash": "hero", "opp_team_hash": "opp", "opp_policy": "heuristic",
           "winner": "hero", "turns": 7, "end_reason": "normal", "end_hp_diff": 1.0,
           "room_raw_path": "battle.log", "normalized_room_log_sha256": "loghash"}
    context = SimpleNamespace(row=row, hero_archetype="balance", opponent_archetype="rain",
                              hero_novelty="known_team", opponent_novelty="unseen_archetype",
                              static_hero="none", static_opponent="tailwind_only",
                              log_features=SimpleNamespace(hero_side="p1", hero_lead=("a", "b"),
                                  opponent_lead=("c", "d"), hero_speed_control=(),
                                  opponent_speed_control=("tailwind",)),
                              cell_id="cell", protected=True)
    bundle = build_observation_bundle.from_contexts([context], policy_hash="p", manifest_hash="m",
                                                     exposure_hash="e", taxonomy_hash="t")
    assert bundle.observations[0].hero_win is True
    assert bundle.observations[0].cell_id == "cell"
    assert bundle.observations[0].opponent_novelty == "unseen_archetype"


def test_duplicate_seed_in_same_cell_is_rejected():
    with pytest.raises(ObservationError, match="duplicate seed"):
        build_observation_bundle.ensure_unique_seeds([("cell", "seed"), ("cell", "seed")])

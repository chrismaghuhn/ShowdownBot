from types import SimpleNamespace
import pytest

from showdown_bot.analysis.generalisation.contracts import sha256_id
from showdown_bot.analysis.generalisation.planner import PlannerError, build_plan


def _manifest(split="dev"):
    cell_id = sha256_id({"hero_team_hash": "hero", "opponent_team_hash": "opp",
                         "opponent_policy": "heuristic", "format_id": "gen9vgc2025regi"}, 20)
    cell = SimpleNamespace(cell_id=cell_id, protected=True, required_unique_seeds=3)
    return SimpleNamespace(manifest_id="m", manifest_hash="mh", splits=(split,),
        format_ids=("gen9vgc2025regi",), hero_team_hashes=("hero",),
        opponent_team_hashes=("opp",), opponent_policies=("heuristic",),
        required_axes=("hero_team_hash", "opponent_team_hash", "opponent_policy", "format_id"),
        required_unique_seeds_per_cell=3, side_control="observed_only", cells=(cell,))


def _catalog(split="dev"):
    hero = SimpleNamespace(team_hash="hero", team_id="hero", team_path="hero.txt",
                           archetype="balance", declared_split="train")
    opponent = SimpleNamespace(team_hash="opp", team_id="opp", team_path="opp.txt",
                               archetype="rain", declared_split=split)
    return SimpleNamespace(by_hash={"hero": hero, "opp": opponent})


def _exposure():
    return SimpleNamespace(exposed_team_hashes=frozenset({"hero"}),
                           exposed_archetypes=frozenset({"balance"}))


def test_fresh_plan_is_deterministic_and_contiguous():
    first = build_plan(_manifest(), _catalog(), _exposure(), planner_seed=7, mode="fresh",
                       panel_hash="panel", panel_team_hashes={"opp"},
                       panel_policies={"heuristic"}, policy_hash="policy")
    second = build_plan(_manifest(), _catalog(), _exposure(), planner_seed=7, mode="fresh",
                        panel_hash="panel", panel_team_hashes={"opp"},
                        panel_policies={"heuristic"}, policy_hash="policy")
    assert first == second
    assert [row.seed_index for row in first.rows] == [0, 1, 2]
    assert [row.replicate_index for row in first.rows] == [0, 1, 2]
    assert first.schedule.schedule_hash == second.schedule.schedule_hash


def test_heldout_requires_confirmation_and_never_supplements():
    with pytest.raises(PlannerError, match="confirm"):
        build_plan(_manifest("heldout"), _catalog("heldout"), _exposure(), planner_seed=7,
                   mode="heldout-fresh", confirm_heldout=False, panel_hash="panel",
                   panel_team_hashes={"opp"}, panel_policies={"heuristic"}, policy_hash="policy")
    with pytest.raises(PlannerError, match="mode"):
        build_plan(_manifest("heldout"), _catalog("heldout"), _exposure(), planner_seed=7,
                   mode="heldout-supplement", confirm_heldout=True, panel_hash="panel",
                   panel_team_hashes={"opp"}, panel_policies={"heuristic"}, policy_hash="policy")

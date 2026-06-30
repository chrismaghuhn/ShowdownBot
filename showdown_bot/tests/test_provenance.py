from showdown_bot.learning.provenance import team_hash, config_hash, build_feature_context
from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id


def test_hashes_are_deterministic_16hex():
    assert team_hash("packed|team|str") == team_hash("packed|team|str")
    assert team_hash("a") != team_hash("b")
    assert len(team_hash("x")) == 16
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})   # order-independent
    assert config_hash({"a": 1}) != config_hash({"a": 2})


def test_build_feature_context_mints_chained_ids():
    ctx = build_feature_context(
        git_sha="sha", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=7,
        game_index=0, decision_local_index=2, turn_number=3, our_side="p1",
        format_id="fmt", mirror_flag=True,
        teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
    )
    run_id = make_run_id("sha", False, "t", "c", 7)
    assert ctx.run_id == run_id
    assert ctx.game_id == make_game_id(run_id, 0)
    assert ctx.decision_id == make_decision_id(ctx.game_id, 2, 3, "p1")
    assert ctx.format_id == "fmt" and ctx.mirror_flag is True
    # rebuild with same inputs -> identical ids (deterministic)
    ctx2 = build_feature_context(
        git_sha="sha", dirty_flag=False, team_hash_="t", config_hash_="c", run_seed=7,
        game_index=0, decision_local_index=2, turn_number=3, our_side="p1",
        format_id="fmt", mirror_flag=True,
        teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
    )
    assert (ctx2.run_id, ctx2.game_id, ctx2.decision_id) == (ctx.run_id, ctx.game_id, ctx.decision_id)

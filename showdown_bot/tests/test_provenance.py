import hashlib
import json

from showdown_bot.learning.provenance import team_hash, config_hash, build_feature_context
from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id


def test_hashes_are_deterministic_16hex():
    assert team_hash("packed|team|str") == team_hash("packed|team|str")
    assert team_hash("a") != team_hash("b")
    assert len(team_hash("x")) == 16
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})   # order-independent
    assert config_hash({"a": 1}) != config_hash({"a": 2})


def test_make_candidate_identity_matches_the_sha1_formula():
    from showdown_bot.learning.provenance import make_candidate_identity

    got = make_candidate_identity(hero_agent="h", git_sha="g", config_hash="c")
    expected = hashlib.sha1(
        json.dumps({"hero_agent": "h", "git_sha": "g", "config_hash": "c"},
                   sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    assert got == expected
    assert len(got) == 16
    # order of kwargs at the call site must not matter -- it's the canonical sorted-key JSON that's hashed.
    assert make_candidate_identity(git_sha="g", config_hash="c", hero_agent="h") == got


def test_i8d_and_coverage_produce_the_same_identity_for_the_same_inputs(monkeypatch):
    """Both resolvers must go through the ONE shared formula, not two copies that could silently
    drift -- proven two ways: (1) equal output for equal inputs, (2) a spy showing both actually
    call make_candidate_identity, not just happen to agree today."""
    import showdown_bot.eval.config_env as cenv
    import showdown_bot.eval.coverage_runner as cr
    import showdown_bot.eval.i8d_runner as ir
    import showdown_bot.eval.result_jsonl as rj
    import showdown_bot.learning.provenance as prov

    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("samesha", False))
    monkeypatch.setattr(cenv, "behavior_env", lambda: {})
    # SAME manifest regardless of caller's format_id, so config_hash matches for both gates too --
    # this test isolates "same formula" from the (expected, unrelated) fact that I8-D and coverage
    # use different real format_ids and would naturally get different config_hash values live.
    monkeypatch.setattr(cenv, "effective_config_manifest", lambda **kw: {"fixed": "manifest"})
    monkeypatch.setattr(rj, "make_config_hash", lambda m: "same-cfg")
    monkeypatch.delenv("SHOWDOWN_CALC_BACKEND", raising=False)

    calls = []
    real = prov.make_candidate_identity

    def spy(**kw):
        calls.append(kw)
        return real(**kw)

    monkeypatch.setattr(prov, "make_candidate_identity", spy)

    i8d_prov = ir.resolve_i8d_provenance()
    cov_prov = cr.resolve_coverage_provenance()

    assert i8d_prov["candidate_identity"] == cov_prov["candidate_identity"]
    assert len(calls) == 2, "expected exactly one make_candidate_identity call per resolver"
    assert calls[0] == calls[1] == {
        "hero_agent": "heuristic", "git_sha": "samesha", "config_hash": "same-cfg"}


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

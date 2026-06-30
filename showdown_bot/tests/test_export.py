# tests/test_export.py
from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id


def test_ids_are_deterministic():
    a = make_run_id("sha", False, "team", "cfg", 7)
    b = make_run_id("sha", False, "team", "cfg", 7)
    assert a == b and isinstance(a, str) and len(a) == 16

def test_ids_differ_on_any_input():
    base = make_run_id("sha", False, "team", "cfg", 7)
    assert base != make_run_id("sha2", False, "team", "cfg", 7)
    assert base != make_run_id("sha", True, "team", "cfg", 7)
    assert base != make_run_id("sha", False, "team", "cfg", 8)

def test_game_and_decision_ids_chain():
    run = make_run_id("sha", False, "team", "cfg", 7)
    g0, g1 = make_game_id(run, 0), make_game_id(run, 1)
    assert g0 != g1
    assert make_decision_id(g0, 0, 1, "p1") != make_decision_id(g0, 1, 1, "p1")
    assert make_decision_id(g0, 0, 1, "p1") == make_decision_id(g0, 0, 1, "p1")

def test_ids_avoid_delimiter_collision():
    # canonical JSON, not ":".join -> these must NOT collide
    assert make_run_id("a:b", False, "c", "cfg", 0) != make_run_id("a", False, "b:c", "cfg", 0)

def test_export_module_has_no_nondeterministic_imports():
    # gate 7: no wall-clock / uuid / unseeded randomness in the module
    import inspect
    import showdown_bot.learning.export as export
    src = inspect.getsource(export)
    assert "import uuid" not in src
    assert "import time" not in src
    assert "import random" not in src
    assert "datetime.now" not in src


def test_sampling_policy_default_is_all():
    from showdown_bot.learning.export import SamplingPolicy
    p = SamplingPolicy()
    assert p.policy == "all"
    assert all(p.should_sample(i) for i in range(10))

def test_sampling_policy_every_nth():
    from showdown_bot.learning.export import SamplingPolicy
    p = SamplingPolicy(policy="every_nth", rate=3)
    assert [i for i in range(9) if p.should_sample(i)] == [0, 3, 6]

def test_sampling_policy_rejects_unknown():
    import pytest
    from showdown_bot.learning.export import SamplingPolicy
    with pytest.raises(ValueError, match="unknown sampling"):
        SamplingPolicy(policy="bogus").should_sample(0)

def test_sampling_policy_rejects_nonpositive_rate():
    import pytest
    from showdown_bot.learning.export import SamplingPolicy
    with pytest.raises(ValueError, match="rate"):
        SamplingPolicy(policy="every_nth", rate=0).should_sample(0)

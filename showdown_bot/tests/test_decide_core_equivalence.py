"""Equivalence gate: _choose_best_ja + encode == heuristic_choose_for_request (Task 1)."""
from __future__ import annotations

import pytest

from showdown_bot.battle.decision import _choose_best_ja, heuristic_choose_for_request
from showdown_bot.protocol.encoder import encode_choose


def test_core_encode_equals_public_choice(decision_fixture):
    req, kw = decision_fixture
    public = heuristic_choose_for_request(req, **kw)          # the wire string
    best_ja = _choose_best_ja(req, **kw)                      # the JointAction
    assert encode_choose(best_ja.as_pair(), rqid=req.rqid) == public


def test_core_is_deterministic(decision_fixture):
    req, kw = decision_fixture
    assert _choose_best_ja(req, **kw).as_pair() == _choose_best_ja(req, **kw).as_pair()


def test_core_rejects_team_preview_request(decision_fixture):
    req, kw = decision_fixture
    req.team_preview = True
    with pytest.raises(ValueError, match="team preview"):
        _choose_best_ja(req, **kw)


def test_trace_preserved_via_public_and_core(decision_fixture):
    """The refactor must NOT break 1b capture: trace= still fills via the public
    wrapper AND the core."""
    from showdown_bot.battle.decision_trace import DecisionTrace

    req, kw = decision_fixture
    kw2 = {k: v for k, v in kw.items() if k != "trace"}
    tr_pub = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr_pub, **kw2)
    tr_core = DecisionTrace()
    _choose_best_ja(req, trace=tr_core, **kw2)
    assert tr_pub.chosen_candidate_id is not None and len(tr_pub.candidates) >= 1
    assert tr_core.chosen_candidate_id == tr_pub.chosen_candidate_id  # same population


def test_report_preserved_if_fixture_supports_it(decision_fixture):
    """report= must still be populated through the wrapper -> core path."""
    req, kw = decision_fixture
    kw2 = {k: v for k, v in kw.items() if k != "report"}
    rep: list[str] = []
    heuristic_choose_for_request(req, report=rep, **kw2)
    assert rep  # report= still populated through the wrapper -> core

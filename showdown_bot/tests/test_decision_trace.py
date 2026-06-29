from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedRange
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_dtos_construct_with_defaults():
    dt = DecisionTrace()
    assert dt.candidates == [] and dt.opponent_responses == []
    ct = CandidateTrace(candidate_id="x", joint_action=None, rank=0,
                        aggregate_score=1.0, score_vector=[1.0],
                        outcome_breakdowns=[OutcomeBreakdown()],
                        aggregate_breakdown=OutcomeBreakdown())
    assert ct.candidate_id == "x" and ct.rank == 0


# ---------------------------------------------------------------------------
# Fakes — mirrors of test_decision_replay.py fakes (no live server needed)
# ---------------------------------------------------------------------------

class _FakeCalc:
    """Returns non-KO damage (keeps game mode NEUTRAL)."""

    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracle:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)

    def get(self, key):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def damage(self, req):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def _book():
    cfg = load_format_config("gen9vgc2026regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _req():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    return BattleRequest.model_validate(data)


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


@pytest.fixture
def decision_fixture():
    req = _req()
    kw = dict(
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=_FakeCalc(),
        oracle=_FakeOracle(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
    )
    return req, kw


# ---------------------------------------------------------------------------
# Trace tests
# ---------------------------------------------------------------------------

def test_trace_off_equivalence(decision_fixture):
    req, kw = decision_fixture
    from showdown_bot.battle.decision import heuristic_choose_for_request
    choice_a = heuristic_choose_for_request(req, trace=None, **kw)
    choice_b = heuristic_choose_for_request(req, trace=DecisionTrace(), **kw)
    assert choice_a == choice_b


def test_trace_is_populated(decision_fixture):
    req, kw = decision_fixture
    from showdown_bot.battle.decision import heuristic_choose_for_request
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    assert tr.game_mode is not None
    assert tr.chosen_candidate_id is not None
    assert len(tr.candidates) >= 1
    assert [c.rank for c in tr.candidates] == sorted(c.rank for c in tr.candidates)
    top = tr.candidates[0]
    assert len(top.score_vector) == len(top.outcome_breakdowns)


def test_aggregate_breakdown_is_weighted_mean(decision_fixture):
    # weighted MEAN over responses (not response[0]). Pin rollout_horizon=0 so the
    # per-response base scores == score_vector, then the equality holds exactly.
    req, kw = decision_fixture
    kw = {k: v for k, v in kw.items() if k != "rollout_horizon"}
    from showdown_bot.battle.decision import heuristic_choose_for_request
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, rollout_horizon=0, **kw)
    top = tr.candidates[0]
    ws = tr.opponent_response_weights or [1.0] * len(top.score_vector)
    wmean = sum(s * w for s, w in zip(top.score_vector, ws)) / (sum(ws) or 1.0)
    assert abs(top.aggregate_breakdown.total_score - wmean) < 1e-9

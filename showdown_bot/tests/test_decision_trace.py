from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.battle.decision_trace import (
    AccuracyEventTrace,
    AccuracyResponseDetail,
    AccuracyTieOrderTrace,
    CandidateTrace,
    DecisionTrace,
)
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


def test_selection_telemetry_defaults_to_none():
    trace = DecisionTrace()
    assert trace.selection_stage is None
    assert trace.fallback_reason is None


def test_aggregation_params_default_to_none():
    t = DecisionTrace()
    assert t.aggregation_mode is None
    assert t.risk_lambda is None
    assert t.must_react_lambda is None


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
    cfg = load_format_config("gen9vgc2025regi")
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


# ---------------------------------------------------------------------------
# New: CandidateModelFeatures tests
# ---------------------------------------------------------------------------

class _FakeCalcAlwaysOhko:
    """Returns guaranteed-OHKO for every request (min_damage >= max_hp)."""

    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=999, max_damage=999, max_hp=150) for _ in requests]


def test_model_features_present_on_candidates(decision_fixture):
    """Every CandidateTrace.model_features has the 3 int counts (>=0)."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import CandidateModelFeatures
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    assert len(tr.candidates) >= 1
    for c in tr.candidates:
        mf = c.model_features
        assert isinstance(mf, CandidateModelFeatures)
        assert isinstance(mf.ko_secured_count, int) and mf.ko_secured_count >= 0
        assert isinstance(mf.ko_threatened_count, int) and mf.ko_threatened_count >= 0
        assert isinstance(mf.survives_for_sure_count, int) and mf.survives_for_sure_count >= 0


def test_model_features_decision_level_same_across_candidates(decision_fixture):
    """ko_threatened_count and survives_for_sure_count are decision-level
    and therefore identical across all candidates."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    assert len(tr.candidates) >= 2
    threatened_vals = [c.model_features.ko_threatened_count for c in tr.candidates]
    survives_vals = [c.model_features.survives_for_sure_count for c in tr.candidates]
    assert len(set(threatened_vals)) == 1, "ko_threatened_count must be identical across candidates"
    assert len(set(survives_vals)) == 1, "survives_for_sure_count must be identical across candidates"


def test_ko_threat_counts_when_ohko_guaranteed(decision_fixture):
    """With a fake calc that guarantees OHKO on every request, threatened > 0."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    req, kw = decision_fixture
    # Swap in a calc that always returns guaranteed OHKO
    ohko_kw = {**kw, "calc": _FakeCalcAlwaysOhko()}
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **ohko_kw)
    # With guaranteed OHKO on all incoming, every candidate should see threatened > 0
    for c in tr.candidates:
        assert c.model_features.ko_threatened_count > 0, (
            f"Expected ko_threatened_count > 0 with all-OHKO calc, got {c.model_features}"
        )


def test_ko_secured_count_non_negative_with_normal_calc(decision_fixture):
    """ko_secured_count is >= 0 for all candidates with normal (no-OHKO) calc.
    With a non-OHKO calc, ko_secured_count == 0 for all candidates.
    """
    from showdown_bot.battle.decision import heuristic_choose_for_request
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    for c in tr.candidates:
        # Normal fake calc never guarantees OHKO => 0 secured KOs
        assert c.model_features.ko_secured_count == 0, (
            f"Expected 0 with no-OHKO calc, got {c.model_features.ko_secured_count}"
        )


def test_ko_secured_count_positive_with_ohko_calc(decision_fixture):
    """With a fake calc that guarantees OHKO, at least some candidates see ko_secured_count > 0
    (the ones that actually select a damaging move targeting an active opp slot)."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    req, kw = decision_fixture
    ohko_kw = {**kw, "calc": _FakeCalcAlwaysOhko()}
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **ohko_kw)
    # At least one candidate among top-K should secure a KO (there are damaging moves)
    secured_vals = [c.model_features.ko_secured_count for c in tr.candidates]
    assert any(v > 0 for v in secured_vals), (
        f"Expected at least one candidate with ko_secured_count>0, got {secured_vals}"
    )


def test_ko_secured_counts_distinct_target_slots(decision_fixture):
    """ko_secured_count counts distinct opponent slots, not number of moves.
    We verify this by checking that with an all-OHKO calc, secured <= 2 (at most 2 opp slots).
    """
    from showdown_bot.battle.decision import heuristic_choose_for_request
    req, kw = decision_fixture
    ohko_kw = {**kw, "calc": _FakeCalcAlwaysOhko()}
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **ohko_kw)
    for c in tr.candidates:
        # Can't secure more unique opp slots than there are active opp mons (2)
        assert c.model_features.ko_secured_count <= 2, (
            f"ko_secured_count={c.model_features.ko_secured_count} exceeds max active opp slots"
        )


def test_tempo_features_populated(decision_fixture):
    """trace.tempo_features is a DecisionTempoFeatures with all int fields >= 0 after a real decision."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTempoFeatures
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    tf = tr.tempo_features
    assert isinstance(tf, DecisionTempoFeatures)
    assert isinstance(tf.we_outspeed_count, int) and tf.we_outspeed_count >= 0
    assert isinstance(tf.they_outspeed_count, int) and tf.they_outspeed_count >= 0
    assert isinstance(tf.speed_tie_count, int) and tf.speed_tie_count >= 0
    assert isinstance(tf.our_fastest_active_speed, int) and tf.our_fastest_active_speed >= 0
    assert isinstance(tf.opp_fastest_active_speed, int) and tf.opp_fastest_active_speed >= 0


def test_ko_secured_ignores_nondamaging_and_unselected(decision_fixture):
    """Non-damaging moves and unselected slots contribute 0 to ko_secured_count.
    With a normal no-OHKO calc, secured == 0 regardless of move selection."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    # _FakeCalc never OHKOs, so secured must be 0 even for all-damaging plans
    for c in tr.candidates:
        assert c.model_features.ko_secured_count == 0


# ---------------------------------------------------------------------------
# New: accuracy telemetry (CandidateTrace.accuracy_details) -- Task 6
# ---------------------------------------------------------------------------

def test_accuracy_response_detail_fields_exist():
    detail = AccuracyResponseDetail(
        accuracy_leaf_count=4, accuracy_event_count=2, accuracy_branch_cap_hits=0,
        events_complete=True, tie_orders=[], events=[],
    )
    assert detail.accuracy_leaf_count == 4
    assert detail.events_complete is True


def test_candidate_trace_accuracy_details_defaults_empty():
    ct = CandidateTrace(
        candidate_id="x", joint_action=None, rank=0, aggregate_score=0.0,
        score_vector=[], outcome_breakdowns=[], aggregate_breakdown=OutcomeBreakdown(),
    )
    assert ct.accuracy_details == []


def test_decision_with_accuracy_mode_populates_accuracy_details(decision_fixture, monkeypatch):
    """Integration test through the real decision.py entry point with a DecisionTrace
    passed and SHOWDOWN_ACCURACY_MODE forced on -- mirrors test_accuracy_mode_wiring.py's
    "force accuracy on via env var, pass a trace, inspect it" pattern using this file's
    own decision_fixture (same underlying fixture data as conftest.py's)."""
    from showdown_bot.battle.decision import heuristic_choose_for_request

    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    req, kw = decision_fixture
    trace = DecisionTrace()
    heuristic_choose_for_request(req, trace=trace, **kw)

    assert trace.candidates, "expected at least one candidate in the trace"
    saw_event = False
    for candidate in trace.candidates:
        assert isinstance(candidate.accuracy_details, list)
        assert len(candidate.accuracy_details) == len(candidate.score_vector)
        for detail in candidate.accuracy_details:
            assert isinstance(detail, AccuracyResponseDetail)
            assert detail.accuracy_branch_cap_hits >= 0
            assert isinstance(detail.events_complete, bool)
            assert detail.accuracy_event_count == len(detail.events)
            for tie_order in detail.tie_orders:
                assert isinstance(tie_order, AccuracyTieOrderTrace)
            for event in detail.events:
                assert isinstance(event, AccuracyEventTrace)
                assert event.tie_order in ("ours_first", "ours_last")
                saw_event = True
    # request_doubles_moves.json includes Heat Wave (90% accuracy), so with
    # accuracy mode on at least one candidate/response should surface a real
    # accuracy event -- proves the wiring actually threads live data through,
    # not just that the lists exist and are empty.
    assert saw_event, "expected at least one AccuracyEventTrace across all candidates"


def test_decision_trace_candidates_rank_sorted(decision_fixture, monkeypatch):
    """Spec Sec.5 point-8 fix: candidates must be provably rank-sorted, not just
    observed to be by accident of the current construction code."""
    from showdown_bot.battle.decision import heuristic_choose_for_request

    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "0")
    req, kw = decision_fixture
    trace = DecisionTrace()
    heuristic_choose_for_request(req, trace=trace, **kw)
    assert [c.rank for c in trace.candidates] == list(range(len(trace.candidates)))

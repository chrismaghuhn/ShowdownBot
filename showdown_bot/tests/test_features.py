"""Gate tests for learning/features.py scaffold (Phase 3 slice 1b-B1, Task 1).

All 7 hard gates must pass even with sentinel stubs; later tasks replace stubs
with real values without breaking these gates.
"""
from __future__ import annotations

import pytest

from showdown_bot.learning.schema import FEATURE_COLUMNS, METADATA_KEYS, LABEL_KEYS, validate_row
from showdown_bot.learning.features import FeatureContext, extract_features, CONTEXT_COLUMNS


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def features_fixture(decision_fixture):
    """Run heuristic_choose_for_request to populate a DecisionTrace, then
    return (trace, state, request, ctx) ready for extract_features."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace

    req, kw = decision_fixture
    tr = DecisionTrace()
    heuristic_choose_for_request(req, trace=tr, **kw)
    state = kw["state"]
    our_side = kw.get("our_side", "p1")
    ctx = FeatureContext(
        run_id="r",
        game_id="g",
        decision_id="d",
        decision_local_index=0,
        turn_number=getattr(state, "turn", 0),
        our_side=our_side,
        format_id="fmt",
        team_hash="t",
        config_hash="c",
        git_sha="s",
        dirty_flag=False,
        teacher_config={"teacher_version": "stub-h0", "trainable_label": False},
        sampling_policy="all",
        mirror_flag=True,
        # dex/move_meta/speed_oracle/protect_priors_by_opp_slot default None;
        # not used by the stub implementation.
    )
    return tr, state, req, ctx


# ---------------------------------------------------------------------------
# Hard gates (7)
# ---------------------------------------------------------------------------

def test_gate_one_row_per_candidate(features_fixture):
    """Gate 3: extract_features returns exactly one Row per CandidateTrace."""
    trace, state, req, ctx = features_fixture
    rows = extract_features(trace, state, req, ctx)
    assert len(rows) == len(trace.candidates)


def test_gate_every_feature_column_present_and_non_null(features_fixture):
    """Gate 1 + Gate 7: every FEATURE_COLUMNS key present, no None values."""
    trace, state, req, ctx = features_fixture
    for row in extract_features(trace, state, req, ctx):
        assert set(row.features) == set(FEATURE_COLUMNS)
        assert all(v is not None for v in row.features.values())


def test_gate_no_metadata_or_outcome_field_in_features(features_fixture):
    """Gate 6: no metadata/outcome/future field bleeds into features.
    format_id is the sole allowed overlap between features and metadata."""
    trace, state, req, ctx = features_fixture
    forbidden = (set(METADATA_KEYS) | set(LABEL_KEYS) | {"game_outcome", "winner"}) - {"format_id"}
    for row in extract_features(trace, state, req, ctx):
        assert not (set(row.features) & forbidden)


def test_gate_rows_validate(features_fixture):
    """Gate 1 (full): validate_row passes for every row (exact key sets)."""
    trace, state, req, ctx = features_fixture
    for row in extract_features(trace, state, req, ctx):
        validate_row(row)


def test_gate_group1_identical_across_candidates(features_fixture):
    """Gate 4: Group-1 context columns have the same value across all candidates."""
    trace, state, req, ctx = features_fixture
    rows = extract_features(trace, state, req, ctx)
    if len(rows) < 2:
        pytest.skip("Need at least 2 candidates to test cross-candidate identity")
    for col in CONTEXT_COLUMNS:
        vals = {row.features[col] for row in rows}
        assert len(vals) == 1, f"CONTEXT_COLUMN '{col}' differs across candidates: {vals}"


# ---------------------------------------------------------------------------
# Group-1 real-value tests (Task 2)
# ---------------------------------------------------------------------------

def _g1(features_fixture):
    trace, state, req, ctx = features_fixture
    from showdown_bot.learning.features import extract_features
    return extract_features(trace, state, req, ctx)[0].features


def test_g1_weather_terrain_sentinel_when_none(features_fixture):
    trace, state, req, ctx = features_fixture
    state.field.weather = None
    state.field.terrain = None
    f = _g1(features_fixture)
    assert f["field_weather"] == "__none__"
    assert f["field_terrain"] == "__none__"


def test_g1_weather_terrain_values(features_fixture):
    trace, state, req, ctx = features_fixture
    state.field.weather = "sun"
    state.field.terrain = "grassyterrain"
    f = _g1(features_fixture)
    assert f["field_weather"] == "sun" and f["field_terrain"] == "grassyterrain"


def test_g1_tailwind_trickroom(features_fixture):
    trace, state, req, ctx = features_fixture
    state.field.tailwind = {"p1": True, "p2": False}
    state.field.trick_room = True
    f = _g1(features_fixture)  # our_side defaults p1 in the fixture
    assert f["tailwind_ours"] is True and f["tailwind_opp"] is False and f["trick_room_active"] is True


def test_g1_speed_control_state(features_fixture):
    trace, state, req, ctx = features_fixture
    state.field.trick_room = False
    state.field.tailwind = {"p1": True, "p2": True}
    assert _g1(features_fixture)["speed_control_state"] == "tailwind_both"
    state.field.tailwind = {"p1": True, "p2": False}
    assert _g1(features_fixture)["speed_control_state"] == "tailwind_ours"
    state.field.tailwind = {"p1": False, "p2": False}
    assert _g1(features_fixture)["speed_control_state"] == "none"
    state.field.trick_room = True
    assert _g1(features_fixture)["speed_control_state"] == "trick_room"  # pure TR, no tailwind active
    state.field.tailwind = {"p1": True, "p2": False}
    assert _g1(features_fixture)["speed_control_state"] == "mixed"  # TR + our tailwind active


def test_g1_screens_untracked(features_fixture):
    f = _g1(features_fixture)
    assert f["screens_ours"] == "__untracked__" and f["screens_opp"] == "__untracked__"


def test_g1_format_and_mirror_from_context(features_fixture):
    trace, state, req, ctx = features_fixture
    f = _g1(features_fixture)
    assert f["format_id"] == ctx.format_id and f["mirror_flag"] == ctx.mirror_flag


def test_g1_alive_counts_and_endgame(features_fixture):
    # our_alive_count authoritative from request; opp_alive_count = max(0, 4 - observed opp faints)
    f = _g1(features_fixture)
    assert isinstance(f["our_alive_count"], int) and f["our_alive_count"] >= 0
    assert isinstance(f["opp_alive_count"], int) and 0 <= f["opp_alive_count"] <= 4
    assert f["endgame_flag"] == (f["our_alive_count"] <= 1)

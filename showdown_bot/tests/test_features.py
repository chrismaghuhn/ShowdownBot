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

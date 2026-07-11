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


# ---------------------------------------------------------------------------
# Group-2 candidate-action tests (Task 3)
# ---------------------------------------------------------------------------
#
# Strategy:
#   - g2_features_fixture extends features_fixture with real move_meta
#     (_move_table() from engine.moves, already cached) and a simple dex wrapper.
#   - For move slots: the decision_fixture candidates are all (move, move).
#     We pick the first candidate and assert on the exact move resolved from the
#     request.  The fixture's slot0 = Incineroar: moves[0]=fakeout, [2]=protect.
#     Slot1 = Rillaboom: moves[0]=heatwave.
#   - For switch/pass slots: we build a minimal CandidateTrace with a hand-crafted
#     JointAction and call _group2_action directly.
# ---------------------------------------------------------------------------

class _SimpleDex:
    """Minimal dex for testing: to_id delegates to engine.moves.to_id."""
    def to_id(self, species: str) -> str:
        from showdown_bot.engine.moves import to_id as _to_id
        return _to_id(species)


@pytest.fixture
def g2_features_fixture(decision_fixture):
    """Like features_fixture but with real move_meta + dex in ctx."""
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.engine.moves import _move_table  # type: ignore[attr-defined]

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
        dex=_SimpleDex(),
        move_meta=_move_table(),
    )
    return tr, state, req, ctx


def _g2_first(g2_features_fixture):
    """Return features dict of the first candidate (via extract_features)."""
    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)
    return rows[0].features


# --- helpers for hand-built CandidateTrace ---

def _make_candidate(slot0_kind, slot1_kind,
                    slot0_move_index=None, slot1_move_index=None,
                    slot0_target=None, slot1_target=None,
                    slot0_tera=False, slot1_tera=False,
                    slot0_target_ident=None, slot1_target_ident=None):
    """Build a minimal CandidateTrace for group-2 unit testing."""
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.battle.decision_trace import CandidateTrace
    from showdown_bot.battle.evaluate import OutcomeBreakdown
    from showdown_bot.models.actions import SlotAction

    sa0 = SlotAction(kind=slot0_kind, move_index=slot0_move_index, target=slot0_target,
                     terastallize=slot0_tera, target_ident=slot0_target_ident)
    sa1 = SlotAction(kind=slot1_kind, move_index=slot1_move_index, target=slot1_target,
                     terastallize=slot1_tera, target_ident=slot1_target_ident)
    ja = JointAction(slot0=sa0, slot1=sa1)
    bd = OutcomeBreakdown()
    return CandidateTrace(
        candidate_id="test",
        joint_action=ja,
        rank=0,
        aggregate_score=0.0,
        score_vector=[0.0],
        outcome_breakdowns=[bd],
        aggregate_breakdown=bd,
    )


def _g2_direct(g2_features_fixture, cand):
    """Call _group2_action directly on a hand-built candidate."""
    from showdown_bot.learning.features import _group2_action  # type: ignore[attr-defined]
    _, state, req, ctx = g2_features_fixture
    return _group2_action(cand, req, state, ctx)


# --- move slot tests ---

def test_g2_move_slot_resolves_id_type_category_priority_damaging(g2_features_fixture):
    """A move SlotAction resolves to real move id/type/category/priority/is_damaging.

    Schema mapping: slot1_* = JointAction.slot0 = active_index 0 = Incineroar (slot 'a')
                    slot2_* = JointAction.slot1 = active_index 1 = Rillaboom  (slot 'b')

    We test Rillaboom's Earth Power (slot2_) and Incineroar's Fake Out (slot1_).
    """
    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)

    # Find a row where Rillaboom (slot2_) used Earth Power
    earth_row = next(
        (r for r in rows if r.features.get("slot2_move_id") == "earthpower"), None
    )
    assert earth_row is not None, "Expected a candidate with Rillaboom earthpower at slot2"
    f = earth_row.features

    # slot2_: Earth Power — Ground-type special, priority 0, damaging, not protect
    assert f["slot2_action_type"] == "move"
    assert f["slot2_move_id"] == "earthpower"
    assert f["slot2_move_type"] == "Ground"
    assert f["slot2_move_category"] == "special"
    assert f["slot2_priority"] == 0
    assert f["slot2_is_damaging"] is True
    assert f["slot2_is_protect"] is False

    # Also check slot1_: Incineroar used Fake Out in this same candidate
    assert f["slot1_action_type"] == "move"
    assert f["slot1_move_id"] == "fakeout"
    assert f["slot1_move_type"] == "Normal"
    assert f["slot1_move_category"] == "physical"
    assert f["slot1_priority"] == 3  # Fake Out has priority +3
    assert f["slot1_is_damaging"] is True
    assert f["slot1_is_protect"] is False


def test_g2_protect_move_detected(g2_features_fixture):
    """A Protect move -> is_protect is True; a non-protect status move -> False."""
    # slot0 protect: move_index=3 on Incineroar -> protect
    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)
    protect_row = next(
        (r for r in rows if r.features.get("slot1_move_id") == "protect"), None
    )
    assert protect_row is not None, "Expected a candidate with protect at slot1"
    assert protect_row.features["slot1_is_protect"] is True
    assert protect_row.features["slot1_is_damaging"] is False

    # Non-protect status: use hand-built candidate with slot0=heatwave (damaging, not protect)
    from showdown_bot.engine.moves import get_move_meta
    heatwave_meta = get_move_meta("heatwave")
    assert heatwave_meta.is_damaging is True

    # Also test is_protect helper directly
    from showdown_bot.learning.features import _is_protect_move  # type: ignore[attr-defined]
    protect_meta = get_move_meta("protect")
    spore_meta = get_move_meta("spore")
    assert _is_protect_move("protect", protect_meta) is True
    assert _is_protect_move("wideguard", get_move_meta("wideguard")) is True
    assert _is_protect_move("silktrap", get_move_meta("silktrap")) is True
    assert _is_protect_move("burningbulwark", get_move_meta("burningbulwark")) is True
    # spore: has 'protect' in flags (blockable), but is NOT a protect move
    assert _is_protect_move("spore", spore_meta) is False
    # flareblitz: has 'protect' in flags (blockable), but not a protect move
    assert _is_protect_move("flareblitz", get_move_meta("flareblitz")) is False


def test_g2_target_kind_and_slot_foe(g2_features_fixture):
    """target=2 (foe slot 2) -> target_kind='foe', target_slot=2."""
    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)
    # Find candidate where slot0 targets foe slot 2
    row = next(
        (r for r in rows if r.features.get("slot1_target_slot") == 2), None
    )
    assert row is not None, "Expected a candidate where slot1 targets foe slot 2"
    f = row.features
    assert f["slot1_target_kind"] == "foe"
    assert f["slot1_target_slot"] == 2


def test_g2_target_none_yields_sentinels(g2_features_fixture):
    """target=None (spread/self move) -> target_kind=SENTINEL_CAT_NONE, target_slot=SENTINEL_NUM."""
    from showdown_bot.learning.features import SENTINEL_CAT_NONE, SENTINEL_NUM
    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)
    # Protect has target=None (self-targeting, no explicit slot)
    row = next(
        (r for r in rows if r.features.get("slot1_move_id") == "protect"), None
    )
    assert row is not None
    assert row.features["slot1_target_kind"] == SENTINEL_CAT_NONE
    assert row.features["slot1_target_slot"] == SENTINEL_NUM


def test_g2_tera_used(g2_features_fixture):
    """tera_used reflects terastallize on either slot."""
    from showdown_bot.learning.features import _group2_action  # type: ignore[attr-defined]
    _, state, req, ctx = g2_features_fixture

    # No tera: both slots move, no terastallize
    cand_no_tera = _make_candidate("move", "move",
                                   slot0_move_index=2, slot1_move_index=2,
                                   slot0_target=2, slot1_target=2)
    f_no = _group2_action(cand_no_tera, req, state, ctx)
    assert f_no["tera_used"] is False

    # Tera on slot0
    cand_tera0 = _make_candidate("move", "move",
                                  slot0_move_index=2, slot1_move_index=2,
                                  slot0_target=2, slot1_target=2, slot0_tera=True)
    f_t0 = _group2_action(cand_tera0, req, state, ctx)
    assert f_t0["tera_used"] is True

    # Tera on slot1
    cand_tera1 = _make_candidate("move", "move",
                                  slot0_move_index=2, slot1_move_index=2,
                                  slot0_target=2, slot1_target=2, slot1_tera=True)
    f_t1 = _group2_action(cand_tera1, req, state, ctx)
    assert f_t1["tera_used"] is True


def test_g2_switch_slot(g2_features_fixture):
    """switch SlotAction: move fields are __none__, is_switch True, species resolved via dex."""
    from showdown_bot.learning.features import SENTINEL_CAT_NONE
    # slot0 switches to "Flutter Mane" (bench mon in fixture)
    # target_ident = "Flutter Mane" (ident suffix from request: "p1: Flutter Mane" -> "Flutter Mane")
    cand = _make_candidate("switch", "move",
                            slot0_target_ident="Flutter Mane",
                            slot1_move_index=2, slot1_target=2)
    f = _g2_direct(g2_features_fixture, cand)

    assert f["slot1_action_type"] == "switch"
    assert f["slot1_move_id"] == SENTINEL_CAT_NONE
    assert f["slot1_move_type"] == SENTINEL_CAT_NONE
    assert f["slot1_move_category"] == SENTINEL_CAT_NONE
    assert f["slot1_priority"] == 0
    assert f["slot1_is_damaging"] is False
    assert f["slot1_is_protect"] is False
    assert f["slot1_is_switch"] is True
    # Flutter Mane -> dex.to_id -> "fluttermane"
    assert f["slot1_switch_target_species_id"] == "fluttermane"


def test_g2_pass_slot(g2_features_fixture):
    """pass SlotAction: all move/switch fields are sentinels."""
    from showdown_bot.learning.features import SENTINEL_CAT_NONE, SENTINEL_NUM
    cand = _make_candidate("pass", "move",
                            slot1_move_index=2, slot1_target=2)
    f = _g2_direct(g2_features_fixture, cand)

    assert f["slot1_action_type"] == "pass"
    assert f["slot1_move_id"] == SENTINEL_CAT_NONE
    assert f["slot1_is_switch"] is False
    assert f["slot1_target_kind"] == SENTINEL_CAT_NONE
    assert f["slot1_target_slot"] == SENTINEL_NUM
    assert f["slot1_switch_target_species_id"] == SENTINEL_CAT_NONE


def test_g2_actor_species_id(g2_features_fixture):
    """slot1_actor_species_id is the actor in active slot 'a' (Incineroar);
    slot2_actor_species_id is the actor in active slot 'b' (Rillaboom)."""
    f = _g2_first(g2_features_fixture)
    # slot1_ prefix = JointAction.slot0 = active index 0 = slot letter 'a' = Incineroar
    assert f["slot1_actor_species_id"] == "incineroar"
    # slot2_ prefix = JointAction.slot1 = active index 1 = slot letter 'b' = Rillaboom
    assert f["slot2_actor_species_id"] == "rillaboom"


# ---------------------------------------------------------------------------
# 2b-2.5a wiring-gap regression (reports/2026-07-11-2b25a-offline-eval.md root cause (A)):
# client/gauntlet.py hardcoded dex=None, move_meta=None at BOTH DatasetExportRuntime
# construction sites, so _slot_action_features always took its "no meta"/"no dex" sentinel
# branch regardless of how many distinct moves/species actually appeared across a dataset --
# 16 feature columns were constant sentinels in every exported row. The extractor itself
# (this file) was always correct; these tests pin the exact non-sentinel values it produces
# once real deps are present, contrasted against the sentinel it produces without them, so a
# future regression at either the extractor OR the gauntlet wiring seam is caught here.
# ---------------------------------------------------------------------------

def test_g2_regression_protect_move_type_category_priority_match_move_table(g2_features_fixture):
    """With move_meta present (as gauntlet.py now always threads via engine.moves._move_table()),
    slot1_move_type/category/priority for a known move ('protect') resolve to REAL values that
    agree exactly with _move_table()['protect'] -- the same table object gauntlet.py passes into
    DatasetExportRuntime.from_env(move_meta=...). Before the fix this was unconditionally
    '__none__'/0 (SENTINEL_CAT_NONE / SENTINEL_NUM) for every row in every exported dataset."""
    from showdown_bot.engine.moves import _move_table
    from showdown_bot.learning.features import SENTINEL_CAT_NONE

    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)
    protect_row = next((r for r in rows if r.features.get("slot1_move_id") == "protect"), None)
    assert protect_row is not None, "Expected a candidate with protect at slot1"
    f = protect_row.features

    protect_meta = _move_table()["protect"]
    assert f["slot1_move_type"] == protect_meta.move_type
    assert f["slot1_move_category"] == protect_meta.category
    assert f["slot1_priority"] == protect_meta.priority
    assert f["slot1_is_damaging"] == protect_meta.is_damaging
    # Pin the concrete real value too (not just "matches the table"), and prove it is NOT the
    # sentinel a dead/None move_meta would have produced.
    assert f["slot1_move_type"] != SENTINEL_CAT_NONE
    assert f["slot1_priority"] == 4  # Protect is priority +4


def test_g2_regression_move_slot_sentinels_when_move_meta_is_none(features_fixture):
    """Contrast case: features_fixture's ctx has move_meta=None (the plain/no-deps fixture,
    mirroring the pre-fix gauntlet.py wiring) -- move_type/category/priority/is_damaging/
    is_protect fall back to their sentinels EVEN THOUGH slot1_move_id resolves a real move id
    (move id resolution reads the request directly, not ctx.move_meta -- exactly the asymmetry
    the offline-eval report used to prove this was a wiring gap, not a data-diversity problem)."""
    from showdown_bot.learning.features import SENTINEL_BOOL, SENTINEL_CAT_NONE

    trace, state, req, ctx = features_fixture
    assert ctx.move_meta is None and ctx.dex is None
    rows = extract_features(trace, state, req, ctx)
    move_row = next((r for r in rows if r.features.get("slot1_action_type") == "move"), None)
    assert move_row is not None
    f = move_row.features
    assert f["slot1_move_id"] != SENTINEL_CAT_NONE  # resolved straight from the request
    assert f["slot1_move_type"] == SENTINEL_CAT_NONE
    assert f["slot1_move_category"] == SENTINEL_CAT_NONE
    assert f["slot1_priority"] == 0
    assert f["slot1_is_damaging"] == SENTINEL_BOOL
    assert f["slot1_is_protect"] == SENTINEL_BOOL
    assert f["slot1_actor_species_id"] == SENTINEL_CAT_NONE  # dex=None -> sentinel too


def test_g2_target_species_unknown_for_unrevealed_opp(g2_features_fixture):
    """Opponent species not revealed -> target_species_id_if_known = __unknown__."""
    from showdown_bot.learning.features import SENTINEL_CAT_UNKNOWN
    # The fixture state has Flutter Mane and Tornadus on p2, but we are targeting
    # them with move candidates.  Any foe target should resolve to the known species or __unknown__.
    trace, state, req, ctx = g2_features_fixture
    rows = extract_features(trace, state, req, ctx)
    # Candidates target foe slots 1 or 2; state.sides["p2"]["a"] = Flutter Mane (known)
    # so slot1_target=1 -> "fluttermane"; slot1_target=2 -> "tornadus"
    # Both are actually known in this fixture.  Test the __unknown__ branch with empty state slot.
    from showdown_bot.engine.state import BattleState
    empty_state = BattleState()
    # No p2 mons in state — target should be __unknown__
    cand = _make_candidate("move", "move",
                            slot0_move_index=2, slot1_move_index=2,
                            slot0_target=1, slot1_target=1)
    from showdown_bot.learning.features import _group2_action  # type: ignore[attr-defined]
    f = _group2_action(cand, req, empty_state, ctx)
    assert f["slot1_target_species_id_if_known"] == SENTINEL_CAT_UNKNOWN
    assert f["slot2_target_species_id_if_known"] == SENTINEL_CAT_UNKNOWN


# ---------------------------------------------------------------------------
# Group-3 eval (trace-only) + Group-4 tempo/risk tests (Task 4)
# ---------------------------------------------------------------------------

import math
from statistics import pvariance


def _feat0(features_fixture):
    trace, state, req, ctx = features_fixture
    from showdown_bot.learning.features import extract_features
    return trace, extract_features(trace, state, req, ctx)


def test_g3_reads_from_trace_exactly(features_fixture):
    trace, rows = _feat0(features_fixture)
    for cand, row in zip(trace.candidates, rows):
        f = row.features
        assert f["heuristic_aggregate_score"] == cand.aggregate_score
        assert f["predicted_outgoing_damage"] == cand.aggregate_breakdown.predicted_outgoing_damage
        assert f["predicted_incoming_damage"] == cand.aggregate_breakdown.predicted_incoming_damage
        assert f["ko_secured_count"] == cand.model_features.ko_secured_count
        assert f["ko_threatened_count"] == cand.model_features.ko_threatened_count
        assert f["survives_for_sure_count"] == cand.model_features.survives_for_sure_count
        assert f["protect_stall_penalty"] == cand.aggregate_breakdown.protect_stall_penalty
        assert f["predicted_kos_for"] == cand.aggregate_breakdown.my_kos
        assert f["predicted_kos_against"] == cand.aggregate_breakdown.my_faints
        if cand.score_vector:
            assert f["score_min_vs_opp"] == min(cand.score_vector)
            assert f["score_worst_response"] == min(cand.score_vector)
            assert f["value_range_across_opp_responses"] == max(cand.score_vector) - min(cand.score_vector)


def test_g3_sentinels_fakeout_action_economy_zero(features_fixture):
    _, rows = _feat0(features_fixture)
    for row in rows:
        assert row.features["fakeout_invalid_penalty"] == 0.0
        assert row.features["action_economy_score"] == 0.0


def test_g3_score_gap_top_is_zero_for_rank0(features_fixture):
    trace, rows = _feat0(features_fixture)
    assert rows[0].features["score_gap_to_top"] == 0.0   # candidates rank-sorted


def test_g3_no_calc_import_in_features():
    # the no-recompute guard: features.py must not import calc/oracle/DamageModel
    import showdown_bot.learning.features as feat, inspect
    src = inspect.getsource(feat)
    assert "DamageModel" not in src and "damage_batch" not in src and "CalcClient" not in src


def test_g4_response_count_and_value_range(features_fixture):
    trace, rows = _feat0(features_fixture)
    for cand, row in zip(trace.candidates, rows):
        assert row.features["response_count"] == len(trace.opponent_responses)


def test_g4_entropy_uniform(features_fixture):
    # uniform weights -> entropy ~ log2(n); degenerate/empty -> 0
    from showdown_bot.learning.features import _entropy
    assert abs(_entropy([0.5, 0.5]) - 1.0) < 1e-9
    assert _entropy([1.0]) == 0.0
    assert _entropy([]) == 0.0


def test_g4_must_react_flag(features_fixture):
    trace, rows = _feat0(features_fixture)
    expected = 1 if trace.game_mode == "MUST_REACT" else 0
    assert rows[0].features["must_react_reason_flags"] == expected


def test_g4_speed_from_trace(features_fixture):
    """G4 speed columns read directly from trace.tempo_features (no recompute)."""
    from showdown_bot.battle.decision_trace import DecisionTempoFeatures
    from showdown_bot.learning.features import extract_features
    trace, state, req, ctx = features_fixture
    # Inject known values into tempo_features
    trace.tempo_features = DecisionTempoFeatures(
        we_outspeed_count=2,
        they_outspeed_count=1,
        speed_tie_count=1,
        our_fastest_active_speed=120,
        opp_fastest_active_speed=95,
    )
    rows = extract_features(trace, state, req, ctx)
    assert len(rows) >= 1
    for row in rows:
        f = row.features
        assert f["we_outspeed_count"] == 2
        assert f["they_outspeed_count"] == 1
        assert f["speed_tie_count"] == 1
        assert f["our_fastest_active_speed"] == 120
        assert f["opp_fastest_active_speed"] == 95


def test_g4_protect_priors(features_fixture):
    trace, state, req, ctx = features_fixture
    from showdown_bot.learning.features import extract_features
    ctx.protect_priors_by_opp_slot = None
    f = extract_features(trace, state, req, ctx)[0].features
    assert f["protect_prior_target1"] == 0.0 and f["protect_prior_target2"] == 0.0
    ctx.protect_priors_by_opp_slot = {"a": 0.7, "b": 0.2}
    f = extract_features(trace, state, req, ctx)[0].features
    assert f["protect_prior_target1"] == 0.7 and f["protect_prior_target2"] == 0.2

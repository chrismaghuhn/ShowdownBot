from __future__ import annotations

import copy

import pytest

from showdown_bot.eval.decision_capture import (
    BattleTraceContext,
    DecisionTraceWriter,
    build_trace_row,
    load_decision_trace,
    prepare_capture,
)
from showdown_bot.eval.decision_diff import (
    DecisionDiffError,
    classify_action_diff,
    compare_battle_decisions,
    validate_trace_run,
)


@pytest.fixture
def bound_trace_fixture(tmp_path, decision_fixture):
    req, kw = decision_fixture
    writer = DecisionTraceWriter(tmp_path / "trace.jsonl")
    results = []
    for seed_index, battle_id in enumerate(("battle-a", "battle-b")):
        context = BattleTraceContext(
            battle_id=battle_id, seed_index=seed_index, config_id="heuristic",
            config_hash="config-a", schedule_hash="schedule-a",
            format_id="gen9vgc2025regi", git_sha="a" * 40,
        )
        for decision_index in (0, 1):
            writer.write(build_trace_row(
                context=context, prepared=prepare_capture(kw["state"], req), request=req,
                choose=f"/choose move 1 1, move 2 2|{req.rqid}", trace=None,
                decision_index=decision_index, decision_latency_ms=1.0,
            ))
        results.append({
            "battle_id": battle_id, "seed_index": seed_index,
            "config_hash": "config-a", "schedule_hash": "schedule-a",
            "format_id": "gen9vgc2025regi", "git_sha": "a" * 40,
            **writer.finish_battle(battle_id),
        })
    return results, load_decision_trace(tmp_path / "trace.jsonl")


def test_validate_trace_run_accepts_bound_rows(bound_trace_fixture):
    result_rows, trace_rows = bound_trace_fixture
    run = validate_trace_run(result_rows, trace_rows)
    assert sorted(run.rows_by_battle) == ["battle-a", "battle-b"]


@pytest.mark.parametrize("mutation, message", [
    (lambda results, traces: results[0].update(decision_trace_count=99), "count mismatch"),
    (lambda results, traces: results[0].update(decision_trace_sha256="0" * 64), "sha mismatch"),
    (lambda results, traces: traces[0].update(config_hash="wrong"), "config_hash mismatch"),
    (lambda results, traces: traces[1].update(decision_index=0), "duplicate decision key"),
])
def test_validate_trace_run_refuses_corruption(bound_trace_fixture, mutation, message):
    result_rows, trace_rows = copy.deepcopy(bound_trace_fixture)
    mutation(result_rows, trace_rows)
    with pytest.raises(DecisionDiffError, match=message):
        validate_trace_run(result_rows, trace_rows)


def test_validate_trace_run_rejects_legacy_result_rows(bound_trace_fixture):
    result_rows, trace_rows = bound_trace_fixture
    for row in result_rows:
        row.pop("decision_trace_count", None)
        row.pop("decision_trace_sha256", None)
    with pytest.raises(DecisionDiffError, match="missing decision trace binding"):
        validate_trace_run(result_rows, trace_rows)


# ---------------------------------------------------------------------------
# Task 6: classify action diffs and align decision streams.
# ---------------------------------------------------------------------------

def action(kind, *, move_id=None, target=None, protect=False, switch_target=None, tera=False):
    if kind == "move":
        slot0 = {
            "kind": "move", "move_index": 1, "move_id": move_id,
            "target": target, "tera": tera, "is_protect": protect,
        }
    elif kind == "switch":
        slot0 = {"kind": "switch", "switch_target": switch_target}
    else:
        slot0 = {"kind": kind}
    return {"kind": "joint", "slots": [slot0, {"kind": "pass"}]}


@pytest.mark.parametrize(("baseline", "candidate", "expected"), [
    (action("move", move_id="fakeout", target=1), action("move", move_id="fakeout", target=2), "ATTACK_TARGET"),
    (action("move", move_id="fakeout", target=1), action("move", move_id="flareblitz", target=1), "ATTACK_MOVE"),
    (action("move", move_id="protect", protect=True), action("move", move_id="fakeout", target=1), "PROTECT"),
    (action("move", move_id="fakeout", target=1), action("switch", switch_target="rillaboom"), "SWITCH"),
    (action("move", move_id="fakeout", target=1), action("move", move_id="fakeout", target=1, tera=True), "TERA"),
])
def test_classify_action_diff(baseline, candidate, expected):
    assert classify_action_diff(baseline, candidate).primary == expected


def test_classify_fallback_beats_all_other_classes():
    # Both a SWITCH and a TERA difference are present, but a fallback selection
    # stage change must win over every action-level class.
    baseline = action("move", move_id="fakeout", target=1)
    candidate = action("switch", switch_target="rillaboom")
    diff = classify_action_diff(
        baseline, candidate, baseline_stage="primary", candidate_stage="fallback_default")
    assert diff.primary == "FALLBACK"
    assert diff.markers == ("selection_stage_changed",)


def _decision_row(index, state_hash, normalized_action, *, turn=1,
                  phase="regular_turn", chosen_rank=0, selection_stage="primary"):
    return {
        "decision_index": index,
        "observable_state_hash": state_hash,
        "normalized_action": normalized_action,
        "turn_number": turn,
        "decision_phase": phase,
        "chosen_rank": chosen_rank,
        "selection_stage": selection_stage,
    }


def test_compare_same_action_different_rank_is_agreement():
    # Identical normalized action but a different chosen rank stays an
    # agreement (score_rank_changed marker), never a divergence.
    act = action("move", move_id="fakeout", target=1)
    baseline = (_decision_row(0, "s0", act, chosen_rank=0),)
    candidate = (_decision_row(0, "s0", act, chosen_rank=3),)
    diff = compare_battle_decisions("battle-x", baseline, candidate)
    assert diff.comparable == 1
    assert diff.agreements == 1
    assert diff.direct_divergences == ()
    assert diff.first_divergence is None
    assert diff.state_divergence_index is None
    assert diff.baseline_suffix_count == 0
    assert diff.candidate_suffix_count == 0


def test_compare_records_first_action_divergence():
    same = action("move", move_id="fakeout", target=1)
    baseline = (
        _decision_row(0, "s0", same),
        _decision_row(1, "s1", action("move", move_id="fakeout", target=1), turn=2),
    )
    candidate = (
        _decision_row(0, "s0", same),
        _decision_row(1, "s1", action("move", move_id="fakeout", target=2), turn=2),
    )
    diff = compare_battle_decisions("battle-y", baseline, candidate)
    assert diff.comparable == 2
    assert diff.agreements == 1
    assert len(diff.direct_divergences) == 1
    assert diff.first_divergence["decision_index"] == 1
    assert diff.first_divergence["turn_number"] == 2
    assert diff.first_divergence["primary"] == "ATTACK_TARGET"
    assert diff.first_divergence["markers"] == ["target_changed"]
    assert diff.state_divergence_index is None


def test_compare_stops_at_state_divergence():
    same = action("move", move_id="fakeout", target=1)
    baseline = (
        _decision_row(0, "s0", same),
        _decision_row(1, "base-state", action("move", move_id="fakeout", target=1), turn=2),
    )
    candidate = (
        _decision_row(0, "s0", same),
        _decision_row(1, "cand-state", action("move", move_id="flareblitz", target=1), turn=2),
    )
    diff = compare_battle_decisions("battle-z", baseline, candidate)
    assert diff.state_divergence_index == 1
    assert diff.comparable == 1
    assert diff.agreements == 1
    assert diff.direct_divergences == ()
    assert diff.first_divergence is None
    # State diverged at index 1: one row remains uncompared on each side.
    assert diff.baseline_suffix_count == 1
    assert diff.candidate_suffix_count == 1


def test_compare_allows_unequal_suffix_after_divergence():
    diverge_base = action("move", move_id="fakeout", target=1)
    diverge_cand = action("switch", switch_target="rillaboom")
    agree = action("move", move_id="protect", protect=True)
    baseline = (
        _decision_row(0, "s0", diverge_base),
        _decision_row(1, "s1", agree, turn=2),
    )
    candidate = (
        _decision_row(0, "s0", diverge_cand),
        _decision_row(1, "s1", agree, turn=2),
        _decision_row(2, "s2", action("move", move_id="fakeout", target=1), turn=3),
        _decision_row(3, "s3", action("move", move_id="fakeout", target=1), turn=4),
    )
    diff = compare_battle_decisions("battle-w", baseline, candidate)
    assert diff.comparable == 2
    assert diff.agreements == 1
    assert len(diff.direct_divergences) == 1
    assert diff.first_divergence["decision_index"] == 0
    assert diff.first_divergence["primary"] == "SWITCH"
    # Baseline ended at index 2; candidate still had two decisions to make.
    assert diff.baseline_suffix_count == 0
    assert diff.candidate_suffix_count == 2
    assert diff.state_divergence_index is None


def test_compare_missing_key_before_divergence_is_error():
    same = action("move", move_id="fakeout", target=1)
    baseline = (
        _decision_row(0, "s0", same),
        _decision_row(1, "s1", action("move", move_id="fakeout", target=1), turn=2),
    )
    candidate = (_decision_row(0, "s0", same),)
    with pytest.raises(DecisionDiffError, match="decision key missing before divergence"):
        compare_battle_decisions("battle-err", baseline, candidate)

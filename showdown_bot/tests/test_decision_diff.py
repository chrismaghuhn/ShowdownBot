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
from showdown_bot.eval.decision_diff import DecisionDiffError, validate_trace_run


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

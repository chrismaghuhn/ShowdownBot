"""Tests for the 2c-Slice-0b Task 5 offline teacher-label join
(showdown_bot.research.agg_teacher_join).

Builds tiny, self-consistent agg-trace / dataset / results file triples on disk
(using the REAL make_run_id/make_game_id provenance functions, so the
game_id -> seed_index reconstruction step is genuinely exercised, not hand-waved)
and drives join_teacher_labels() end to end. A final real-data test runs the join
against the actual Kaggle full-fidelity shard on disk (gitignored, local-only --
skipped when absent) and feeds the result through run_full_fidelity_probe.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from showdown_bot.learning.export import make_game_id, make_run_id
from showdown_bot.learning.schema import (
    FEATURE_COLUMNS, LABEL_KEYS, METADATA_KEYS, Row, to_jsonl_line,
)
from showdown_bot.research.agg_teacher_join import (
    JoinConfig,
    TeacherJoinError,
    join_teacher_labels,
)
from showdown_bot.research.aggregation_probe import run_full_fidelity_probe
from showdown_bot.research.aggregation_trace import (
    AGG_TRACE_SCHEMA_VERSION,
    validate_agg_row,
)

GIT_SHA = "b" * 40
TEAM_HASH = "team-hash-fixture"
CONFIG_HASH = "config-hash-fixture"


# ---------------------------------------------------------------------------
# Fixture builders. join_teacher_labels reads FILE PATHS, not in-memory rows,
# so every test writes tiny real files to tmp_path.
# ---------------------------------------------------------------------------

def _game_id(*, run_seed: int, dirty: bool, game_index: int) -> str:
    run_id = make_run_id(GIT_SHA, dirty, TEAM_HASH, CONFIG_HASH, run_seed)
    return make_game_id(run_id, game_index)


def _dataset_row(*, game_id, decision_id, candidate_index, turn_number, teacher_best) -> Row:
    features = {c: 0 for c in FEATURE_COLUMNS}
    features["turn_number"] = turn_number
    metadata = {k: "x" for k in METADATA_KEYS}
    metadata.update(
        game_id=game_id, decision_id=decision_id, candidate_index=candidate_index,
        git_sha=GIT_SHA, team_hash=TEAM_HASH, config_hash=CONFIG_HASH,
    )
    label = {k: 0 for k in LABEL_KEYS}
    label["teacher_best"] = teacher_best
    return Row(features=features, metadata=metadata, label=label)


def _write_dataset(path, rows: list[Row]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(to_jsonl_line(row) + "\n")


def _results_row(*, seed_index, turns, dirty=False) -> dict:
    return {"battle_id": f"b{seed_index}", "seed_index": seed_index, "turns": turns, "dirty": dirty}


def _write_results(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _cand(action_key: str, score: float = 1.0) -> dict:
    return {"action_key": action_key, "exported_aggregate_score": score, "response_scores": [score]}


def _agg_row(*, seed_index, decision_index, turn_number, mode="neutral", candidates=(),
             teacher_best=()) -> dict:
    has_cands = bool(candidates)
    return {
        "agg_trace_schema_version": AGG_TRACE_SCHEMA_VERSION,
        "battle_id": f"b{seed_index}",
        "seed_index": seed_index,
        "decision_index": decision_index,
        "turn_number": turn_number,
        "our_side": "p1",
        "config_id": "heuristic",
        "config_hash": "agg-cfg-hash",
        "schedule_hash": "sched-hash",
        "format_id": "gen9vgc2025regi",
        "git_sha": GIT_SHA,
        "game_mode": mode.upper() if mode else None,
        "aggregation_mode": mode,
        "risk_lambda": 0.5 if mode else None,
        "must_react_lambda": 0.6 if mode else None,
        "selected_action_key": None,
        "response_keys": ["r0"] if has_cands else [],
        "response_weights": [],
        "teacher_best_action_keys": list(teacher_best),
        "candidates": list(candidates),
    }


def _write_agg_trace(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            validate_agg_row(row)  # fixtures must themselves be valid rows
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# Group 1: provenance reconstruction (game_id -> seed_index)
# ---------------------------------------------------------------------------

def test_join_reconstructs_bijectively_with_default_config(tmp_path):
    gid = _game_id(run_seed=0, dirty=False, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=1, turn_number=1, teacher_best=False),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [
        _agg_row(seed_index=0, decision_index=0, turn_number=1, candidates=[_cand("A"), _cand("B")]),
    ])

    enriched, report = join_teacher_labels(
        tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
    )
    assert report["joined_count"] == 1
    assert report["reconstruction"] == {"dirty": False, "run_seed": 0, "games_total": 1}
    assert enriched[0]["teacher_best_action_keys"] == ["A"]


def test_join_sweeps_run_seed_candidates_to_find_bijection(tmp_path):
    gid = _game_id(run_seed=3, dirty=False, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [
        _agg_row(seed_index=0, decision_index=0, turn_number=1, candidates=[_cand("A")]),
    ])

    enriched, report = join_teacher_labels(
        tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
        config=JoinConfig(run_seed_candidates=(0, 1, 2, 3)),
    )
    assert report["joined_count"] == 1
    assert report["reconstruction"]["run_seed"] == 3


def test_join_falls_back_to_flipped_dirty_when_results_dirty_disagrees(tmp_path):
    # The TRUE provenance used dirty=True, but results.jsonl's own dirty field says
    # False -- the fallback sweep must flip it and still find the bijection.
    gid = _game_id(run_seed=0, dirty=True, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [
        _agg_row(seed_index=0, decision_index=0, turn_number=1, candidates=[_cand("A")]),
    ])

    enriched, report = join_teacher_labels(
        tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
    )
    assert report["joined_count"] == 1
    assert report["reconstruction"]["dirty"] is True


def test_join_maps_game_index_to_seed_index_via_results_file_order(tmp_path):
    # 2 games; results.jsonl lists them OUT of seed_index order and not starting at
    # 0, proving the mapping is driven by results FILE POSITION (game_index), not by
    # seed_index identity or sort order (the sharded-run case).
    gid0 = _game_id(run_seed=0, dirty=False, game_index=0)  # exported FIRST
    gid1 = _game_id(run_seed=0, dirty=False, game_index=1)  # exported SECOND
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid0, decision_id="d0", candidate_index=0, turn_number=1, teacher_best=True),
        _dataset_row(game_id=gid1, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [
        _results_row(seed_index=7, turns=1, dirty=False),  # results row 0 -> game_index 0
        _results_row(seed_index=3, turns=1, dirty=False),  # results row 1 -> game_index 1
    ])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [
        _agg_row(seed_index=7, decision_index=0, turn_number=1, candidates=[_cand("A0")]),
        _agg_row(seed_index=3, decision_index=0, turn_number=1, candidates=[_cand("A1")]),
    ])

    enriched, report = join_teacher_labels(
        tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
    )
    assert report["joined_count"] == 2
    by_seed = {r["seed_index"]: r for r in enriched}
    assert by_seed[7]["teacher_best_action_keys"] == ["A0"]
    assert by_seed[3]["teacher_best_action_keys"] == ["A1"]


def test_join_raises_when_no_bijection_found(tmp_path):
    gid = _game_id(run_seed=99, dirty=False, game_index=0)  # 99 outside the swept space
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [])

    with pytest.raises(TeacherJoinError):
        join_teacher_labels(
            tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
            config=JoinConfig(run_seed_candidates=(0, 1, 2)),
        )


def test_join_raises_when_dataset_turn_exceeds_battle_turns(tmp_path):
    gid = _game_id(run_seed=0, dirty=False, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=50, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=5, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [])

    with pytest.raises(TeacherJoinError, match="turn"):
        join_teacher_labels(
            tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
        )


# ---------------------------------------------------------------------------
# Group 2: intersection join, ambiguity/skip reasons, positional teacher keys.
#
# One shared "world": a single game (seed_index=0) with 6 decisions at turns
# 1-6, one per join-outcome category. Built once per test via _build_world so
# each test stays focused on ONE assertion, matching the pattern of a single
# ground-truth fixture already used in test_aggregation_probe.py.
# ---------------------------------------------------------------------------

def _build_world(tmp_path):
    gid = _game_id(run_seed=0, dirty=False, game_index=0)

    ds_rows = [
        # turn 1: successful join, 2 candidates -- the SECOND is teacher_best (proves
        # a real positional pick, not an accidental index-0 default).
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=False),
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=1, turn_number=1, teacher_best=True),
        # turn 2: dataset_only -- no agg row exists at turn 2 at all.
        _dataset_row(game_id=gid, decision_id="d2", candidate_index=0, turn_number=2, teacher_best=True),
        # turn 3: agg_only -- deliberately NO dataset rows at turn 3.
        # turn 4: ambiguous_agg -- exactly 1 dataset decision, 2 agg rows.
        _dataset_row(game_id=gid, decision_id="d4", candidate_index=0, turn_number=4, teacher_best=True),
        # turn 5: ambiguous_dataset -- 2 dataset decisions, exactly 1 agg row.
        _dataset_row(game_id=gid, decision_id="d5a", candidate_index=0, turn_number=5, teacher_best=True),
        _dataset_row(game_id=gid, decision_id="d5b", candidate_index=0, turn_number=5, teacher_best=True),
        # turn 6: candidate_count_mismatch -- dataset has 2 candidates, agg row has 1.
        _dataset_row(game_id=gid, decision_id="d6", candidate_index=0, turn_number=6, teacher_best=True),
        _dataset_row(game_id=gid, decision_id="d6", candidate_index=1, turn_number=6, teacher_best=False),
    ]
    _write_dataset(tmp_path / "dataset.jsonl.gz", ds_rows)
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=6, dirty=False)])

    agg_rows = [
        _agg_row(seed_index=0, decision_index=0, turn_number=1, candidates=[_cand("t1-A"), _cand("t1-B")]),
        _agg_row(seed_index=0, decision_index=1, turn_number=3, candidates=[_cand("t3-A")]),
        _agg_row(seed_index=0, decision_index=2, turn_number=4, candidates=[_cand("t4-A")]),
        _agg_row(seed_index=0, decision_index=3, turn_number=4, candidates=[_cand("t4-B")]),
        _agg_row(seed_index=0, decision_index=4, turn_number=5, candidates=[_cand("t5-A")]),
        _agg_row(seed_index=0, decision_index=5, turn_number=6, candidates=[_cand("t6-A")]),
    ]
    _write_agg_trace(tmp_path / "agg_trace.jsonl", agg_rows)
    return tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl"


def test_world_report_counts_and_reasons(tmp_path):
    agg_p, ds_p, res_p = _build_world(tmp_path)
    _enriched, report = join_teacher_labels(agg_p, ds_p, res_p)
    assert report["agg_non_degenerate_count"] == 6
    assert report["dataset_decisions_count"] == 6  # d1, d2, d4, d5a, d5b, d6
    assert report["joined_count"] == 1
    assert report["teacher_labeled_count"] == 1
    assert report["skipped_by_reason"] == {
        "dataset_only": 1, "agg_only": 1, "ambiguous_agg": 1,
        "ambiguous_dataset": 1, "candidate_count_mismatch": 1,
    }


def test_world_positional_teacher_best_action_keys(tmp_path):
    agg_p, ds_p, res_p = _build_world(tmp_path)
    enriched, _report = join_teacher_labels(agg_p, ds_p, res_p)
    row = next(r for r in enriched if r["turn_number"] == 1)
    assert row["teacher_best_action_keys"] == ["t1-B"]


def test_world_unjoined_rows_keep_empty_teacher_keys(tmp_path):
    agg_p, ds_p, res_p = _build_world(tmp_path)
    enriched, _report = join_teacher_labels(agg_p, ds_p, res_p)
    for row in enriched:
        if row["turn_number"] != 1:
            assert row["teacher_best_action_keys"] == []


def test_world_emits_the_full_agg_row_list(tmp_path):
    agg_p, ds_p, res_p = _build_world(tmp_path)
    enriched, _report = join_teacher_labels(agg_p, ds_p, res_p)
    assert len(enriched) == 6  # every agg-trace row is emitted, joined or not
    assert sorted(r["turn_number"] for r in enriched) == [1, 3, 4, 4, 5, 6]  # turn 4 appears twice


def test_world_every_emitted_row_still_validates(tmp_path):
    agg_p, ds_p, res_p = _build_world(tmp_path)
    enriched, _report = join_teacher_labels(agg_p, ds_p, res_p)
    for row in enriched:
        validate_agg_row(row)  # must not raise


def test_join_includes_all_teacher_best_ties_in_candidate_order(tmp_path):
    gid = _game_id(run_seed=0, dirty=False, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=1, turn_number=1, teacher_best=False),
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=2, turn_number=1, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [
        _agg_row(seed_index=0, decision_index=0, turn_number=1,
                 candidates=[_cand("A"), _cand("B"), _cand("C")]),
    ])

    enriched, _report = join_teacher_labels(
        tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
    )
    assert enriched[0]["teacher_best_action_keys"] == ["A", "C"]


def test_join_raises_on_non_contiguous_candidate_index_within_a_decision(tmp_path):
    gid = _game_id(run_seed=0, dirty=False, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=2, turn_number=1, teacher_best=False),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [
        _agg_row(seed_index=0, decision_index=0, turn_number=1, candidates=[_cand("A"), _cand("B")]),
    ])

    with pytest.raises(TeacherJoinError):
        join_teacher_labels(
            tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
        )


def test_join_leaves_degenerate_rows_untouched(tmp_path):
    gid = _game_id(run_seed=0, dirty=False, game_index=0)
    _write_dataset(tmp_path / "dataset.jsonl.gz", [
        _dataset_row(game_id=gid, decision_id="d1", candidate_index=0, turn_number=1, teacher_best=True),
    ])
    _write_results(tmp_path / "results.jsonl", [_results_row(seed_index=0, turns=1, dirty=False)])
    degenerate = _agg_row(seed_index=0, decision_index=0, turn_number=None, mode=None, candidates=())
    _write_agg_trace(tmp_path / "agg_trace.jsonl", [degenerate])

    enriched, report = join_teacher_labels(
        tmp_path / "agg_trace.jsonl", tmp_path / "dataset.jsonl.gz", tmp_path / "results.jsonl",
    )
    assert report["agg_non_degenerate_count"] == 0
    assert len(enriched) == 1
    assert enriched[0]["teacher_best_action_keys"] == []
    validate_agg_row(enriched[0])


# ---------------------------------------------------------------------------
# Group 3: real-data integration (local-only, gitignored Kaggle shard).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARD_DIR = REPO_ROOT / "kaggle_out" / "rain-aggtrace-shard-v2"


@pytest.mark.skipif(not SHARD_DIR.exists(), reason="local-only Kaggle shard not present (gitignored)")
def test_real_shard_join_and_full_fidelity_probe_teacher_agreement():
    enriched, report = join_teacher_labels(
        SHARD_DIR / "agg_trace.jsonl", SHARD_DIR / "dataset.jsonl.gz", SHARD_DIR / "results.jsonl",
    )
    print("agg_teacher_join report:", json.dumps(report, indent=2, sort_keys=True))

    assert report["reconstruction"]["games_total"] == 10
    assert report["joined_count"] > 0
    assert report["teacher_labeled_count"] > 0
    # the real shard genuinely exercises the ambiguity-skip paths (not a vacuous 1:1 join)
    assert sum(report["skipped_by_reason"].values()) > 0
    assert len(enriched) == report["agg_non_degenerate_count"] + sum(
        1 for r in enriched if r["turn_number"] is None
    )

    probe = run_full_fidelity_probe(enriched)
    for name in ("risk_lambda_0.0", "must_react_lambda_0.0"):
        v = probe["variants"][name]["global"]
        print(f"{name}: teacher_eligible_count={v['teacher_eligible_count']} "
              f"teacher_agreement_delta={v['teacher_agreement_delta']}")
        assert v["teacher_eligible_count"] > 0
        assert v["teacher_agreement_delta"] is not None

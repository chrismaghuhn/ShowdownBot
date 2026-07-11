"""End-to-end regression test for the candidate-vs-baseline decision-diff pipeline
(candidate-vs-baseline-diff Task 10, PRIORITY 1).

Every existing `decision-diff` CLI test (`tests/test_cli_decision_diff.py`) monkeypatches
`analyze_decision_diff` away, so the core orchestrator -- which had a `pair.battle_id`
crash bug fixed in Task 7 -- has never been exercised end-to-end by a committed test. This
test builds a REAL baseline run and a REAL candidate run: real `DecisionTraceWriter` +
`build_trace_row` sidecars (`eval.decision_capture`), real T2 result rows (validated via
the real `validate_battle_row`) carrying the `decision_trace_count`/`decision_trace_sha256`
binding, and real `RunBundle`s built via the same direct-construction seam
`tests/test_eval_report_paired.py` documents and uses for the paired eval-report flow
("these tests build RunBundle objects DIRECTLY with synthetic row dicts -- the exact seam
... run_safety_gates + the paired builders read only the row/manifest fields"). The same
reasoning applies here: `analyze_decision_diff` only reads `bundle.rows`/`.manifest`/
`.schedule_row_count`/`.latency_budget_ms`, never touches the filesystem-auditing half of
`RunBundle.load`, so a direct `RunBundle(...)` is a real, unmocked bundle for this seam.

The panel is loaded for real (`load_panel` against the committed `panel_v001.yaml` and its
real team `.txt`/`.packed` files), so matchup-bucket archetypes are real panel data too.

The chain driven here has NO mocks anywhere: `validate_trace_run` (both runs) -> `pair_runs`
(inside `analyze_decision_diff`) -> `analyze_decision_diff(outcome_only=False)` ->
`build_report_object` -> `render_markdown`. This locks in the Task 7 `pair.battle_id` fix.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from showdown_bot.eval.decision_capture import (
    BattleTraceContext,
    DecisionTraceWriter,
    build_trace_row,
    load_decision_trace,
    prepare_capture,
)
from showdown_bot.eval.decision_diff import analyze_decision_diff, validate_trace_run
from showdown_bot.eval.decision_diff_report import build_report_object, render_markdown
from showdown_bot.eval.panel import load_panel, team_content_hash
from showdown_bot.eval.report import RunBundle
from showdown_bot.eval.result_jsonl import make_battle_id, validate_battle_row
from showdown_bot.eval.seeding import derive_battle_seed

_SB = Path(__file__).resolve().parents[1]              # <repo>/showdown_bot/
_REPO_ROOT = _SB.parent                                  # <repo>/
_PANEL_PATH = _REPO_ROOT / "config" / "eval" / "panels" / "panel_v001.yaml"

_FORMAT_ID = "gen9vgc2025regi"
_SCHEDULE_HASH = "e2e-decision-diff-schedule"
_SEED_BASE = "e2e-decision-diff-seed-base"
_GIT_SHA = "e" * 40
_BASELINE_CFG = "cfg-e2e-baseline"
_CANDIDATE_CFG = "cfg-e2e-candidate"

# Fixed decision-fixture request (tests/conftest.py::decision_fixture): slot0 (Incineroar) has
# fakeout(1)/flareblitz(2)/protect(3)/knockoff(4); slot1 (Rillaboom) has heatwave(1)/
# earthpower(2)/protect(3)/solarbeam(4).
_ACTION_A = "/choose move 1 1, move 1|{rqid}"     # fakeout @ target 1, heatwave
_ACTION_B = "/choose move 2 1, move 1|{rqid}"     # flareblitz @ target 1, heatwave -> ATTACK_MOVE


def _seed_and_id(seed_index: int) -> tuple[str, str]:
    seed = derive_battle_seed(_SEED_BASE, seed_index)
    battle_id = make_battle_id(_SCHEDULE_HASH, seed_index, seed)
    return seed, battle_id


def _write_decisions(writer, context, req, entries):
    """entries: iterable of (decision_index, choose, state, latency_ms)."""
    for decision_index, choose, state, latency in entries:
        prepared = prepare_capture(state, req)
        writer.write(build_trace_row(
            context=context, prepared=prepared, request=req, choose=choose, trace=None,
            decision_index=decision_index, decision_latency_ms=latency,
        ))


def _row(*, battle_id, seed_index, seed, config_hash, winner, opp_policy, opp_team_hash,
         opp_team_path, panel_split, hero_team_hash, panel_hash, trace_binding):
    row = {
        "battle_id": battle_id, "run_id": f"run-{config_hash}", "config_id": config_hash,
        "format_id": _FORMAT_ID, "config_hash": config_hash, "schedule_hash": _SCHEDULE_HASH,
        "seed_index": seed_index, "opp_policy": opp_policy,
        "hero_team_path": "teams/fixed_team.txt", "opp_team_path": opp_team_path,
        "seed": seed, "seed_base": _SEED_BASE, "winner": winner, "turns": 6 + seed_index,
        "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 120,
        "git_sha": _GIT_SHA, "dirty": False, "end_reason": "normal",
        "hero_team_hash": hero_team_hash, "opp_team_hash": opp_team_hash,
        "panel_split": panel_split, "panel_hash": panel_hash,
        "decision_trace_count": trace_binding["decision_trace_count"],
        "decision_trace_sha256": trace_binding["decision_trace_sha256"],
    }
    validate_battle_row(row)  # prove this is a schema-valid real T2 result row, not an ad hoc dict
    return row


def _bundle(rows, *, config_hash):
    manifest = {
        "run_id": f"run-{config_hash}", "config_hash": config_hash,
        "schedule_hash": _SCHEDULE_HASH, "seed_base": _SEED_BASE,
        "panel_hash": rows[0]["panel_hash"], "git_sha": _GIT_SHA, "dirty": False,
        "start_ts": "2026-07-11T00:00:00+00:00",
    }
    return RunBundle(
        rows=rows, manifest=manifest, recomputed_panel_hash=rows[0]["panel_hash"],
        panel_dev_hashes=frozenset(), panel_held_hashes=frozenset(), team_path_by_hash={},
        schedule_row_count=len(rows), schedule_reproducible=True,
        alignment_ok=True, alignment_detail=f"{len(rows)} contiguous, derived",
        latency_budget_ms=1000, git_sha=_GIT_SHA,
        input_sha256={r: "0" * 64 for r in ("results", "seedlog", "schedule", "panel", "manifest")},
        input_basenames={r: f"{r}.x" for r in ("results", "seedlog", "schedule", "panel", "manifest")},
    )


@pytest.fixture
def _e2e_fixture(tmp_path, decision_fixture):
    """Builds a REAL baseline+candidate pair: 4 battles, real sidecars, real RunBundles.

    Battle 0 (rain): outcome-only positive flip (baseline loses, candidate wins), decisions
    agree -- no divergence needed for an outcome flip.
    Battle 1 (sun): outcome-only negative flip (baseline wins, candidate loses).
    Battle 2 (trickroom): both win; decisions agree at index 0-1, then the observable state
    diverges at index 2 (a *later* state divergence, not at the first decision) -> a suffix
    on both sides.
    Battle 3 (balance, held-out): both lose; decisions agree at index 0, then a direct policy
    divergence (ATTACK_MOVE) at index 1.
    """
    req, kw = decision_fixture
    state = kw["state"]
    mutated_state = copy.deepcopy(state)
    mutated_state.sides["p1"]["a"].boosts = {"atk": 1}   # forces a differing observable hash

    panel = load_panel(str(_PANEL_PATH), teams_root=str(_SB))
    hero_hash = team_content_hash(str(_SB), "teams/fixed_team.txt")
    trickroom, sun, rain = panel.dev_teams  # yaml order: trickroom, sun, rain
    balance, _tailwind = panel.heldout_teams

    action_a = _ACTION_A.format(rqid=req.rqid)
    action_b = _ACTION_B.format(rqid=req.rqid)

    baseline_writer = DecisionTraceWriter(tmp_path / "baseline-trace.jsonl")
    candidate_writer = DecisionTraceWriter(tmp_path / "candidate-trace.jsonl")

    battle_specs = [
        (0, rain, "max_damage", "dev", "villain", "hero",
         [(0, action_a, state, 90.0)], [(0, action_a, state, 90.0)]),           # positive flip
        (1, sun, "max_damage", "dev", "hero", "villain",
         [(0, action_a, state, 90.0)], [(0, action_a, state, 90.0)]),           # negative flip
        (2, trickroom, "max_damage", "dev", "hero", "hero",
         [(0, action_a, state, 80.0), (1, action_a, state, 80.0), (2, action_a, state, 80.0)],
         [(0, action_a, state, 80.0), (1, action_a, state, 80.0),
          (2, action_a, mutated_state, 80.0)]),                                 # later state suffix
        (3, balance, "max_damage", "heldout", "villain", "villain",
         [(0, action_a, state, 70.0), (1, action_a, state, 70.0)],
         [(0, action_a, state, 70.0), (1, action_b, state, 70.0)]),             # direct divergence
    ]

    baseline_rows, candidate_rows = [], []
    for (seed_index, opp_team, opp_policy, panel_split, base_winner, cand_winner,
         base_entries, cand_entries) in battle_specs:
        seed, battle_id = _seed_and_id(seed_index)
        base_ctx = BattleTraceContext(
            battle_id=battle_id, seed_index=seed_index, config_id=_BASELINE_CFG,
            config_hash=_BASELINE_CFG, schedule_hash=_SCHEDULE_HASH, format_id=_FORMAT_ID,
            git_sha=_GIT_SHA,
        )
        cand_ctx = BattleTraceContext(
            battle_id=battle_id, seed_index=seed_index, config_id=_CANDIDATE_CFG,
            config_hash=_CANDIDATE_CFG, schedule_hash=_SCHEDULE_HASH, format_id=_FORMAT_ID,
            git_sha=_GIT_SHA,
        )
        _write_decisions(baseline_writer, base_ctx, req, base_entries)
        _write_decisions(candidate_writer, cand_ctx, req, cand_entries)
        base_binding = baseline_writer.finish_battle(battle_id)
        cand_binding = candidate_writer.finish_battle(battle_id)

        baseline_rows.append(_row(
            battle_id=battle_id, seed_index=seed_index, seed=seed, config_hash=_BASELINE_CFG,
            winner=base_winner, opp_policy=opp_policy, opp_team_hash=opp_team.team_hash,
            opp_team_path=opp_team.team_path, panel_split=panel_split, hero_team_hash=hero_hash,
            panel_hash=panel.panel_hash, trace_binding=base_binding,
        ))
        candidate_rows.append(_row(
            battle_id=battle_id, seed_index=seed_index, seed=seed, config_hash=_CANDIDATE_CFG,
            winner=cand_winner, opp_policy=opp_policy, opp_team_hash=opp_team.team_hash,
            opp_team_path=opp_team.team_path, panel_split=panel_split, hero_team_hash=hero_hash,
            panel_hash=panel.panel_hash, trace_binding=cand_binding,
        ))

    baseline_bundle = _bundle(baseline_rows, config_hash=_BASELINE_CFG)
    candidate_bundle = _bundle(candidate_rows, config_hash=_CANDIDATE_CFG)

    baseline_trace = validate_trace_run(
        baseline_rows, load_decision_trace(tmp_path / "baseline-trace.jsonl"))
    candidate_trace = validate_trace_run(
        candidate_rows, load_decision_trace(tmp_path / "candidate-trace.jsonl"))

    return baseline_bundle, candidate_bundle, baseline_trace, candidate_trace, panel


def test_decision_diff_end_to_end_real_pipeline(_e2e_fixture):
    """Locks in the Task 7 `pair.battle_id` fix: drives validate_trace_run -> pair_runs
    (inside analyze_decision_diff) -> analyze_decision_diff -> build_report_object ->
    render_markdown with NO mocks anywhere in the chain."""
    baseline_bundle, candidate_bundle, baseline_trace, candidate_trace, panel = _e2e_fixture

    analysis = analyze_decision_diff(
        baseline_bundle, candidate_bundle, panel=panel,
        baseline_trace=baseline_trace, candidate_trace=candidate_trace, outcome_only=False,
    )

    assert analysis["capability_mode"] == "full"

    integrity = analysis["integrity"]
    assert integrity["paired_battles"] == 4
    assert integrity["battles_with_decision_comparison"] == 4
    assert integrity["directly_comparable_decisions"] == 6
    assert integrity["direct_agreements"] == 5
    assert integrity["direct_divergences"] == 1
    assert integrity["battles_with_state_divergence"] == 1

    outcomes = analysis["outcomes"]
    assert outcomes["CANDIDATE_FLIP_TO_WIN"] == 1
    assert outcomes["CANDIDATE_REGRESSION_TO_LOSS"] == 1
    assert outcomes["BOTH_WIN"] == 1
    assert outcomes["BOTH_LOSS"] == 1
    assert outcomes["NON_BINARY"] == 0

    diffs = analysis["decision_differences"]
    assert diffs["comparable"] == 6
    assert diffs["agreements"] == 5
    assert diffs["divergences"] == 1
    assert diffs["by_primary_class"] == {"ATTACK_MOVE": 1}

    buckets = analysis["matchup_buckets"]
    assert len(buckets) == 4
    assert all(bucket["underpowered"] for bucket in buckets)
    assert {b["opponent_archetype"] for b in buckets} == {"rain", "sun", "trick_room", "balance"}

    # stability: no repeat traces were supplied -> real "not_provided" status, not fabricated.
    assert analysis["stability"] == {
        "baseline": {"status": "not_provided"}, "candidate": {"status": "not_provided"},
    }

    obj = build_report_object(analysis)
    assert obj["capability_mode"] == "full"
    assert obj["integrity"]["paired_battles"] == 4
    assert obj["decision_differences"]["by_primary_class"] == {"ATTACK_MOVE": 1}

    md = render_markdown(obj)
    assert md.startswith("# Candidate-vs-Baseline Differential Report")
    assert "CANDIDATE_FLIP_TO_WIN: 1" in md
    assert "CANDIDATE_REGRESSION_TO_LOSS: 1" in md
    assert "ATTACK_MOVE" in md
    assert len(md) > 0

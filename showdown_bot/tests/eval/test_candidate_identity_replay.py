"""Integration checks for candidate-identity slice."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from showdown_bot.battle.candidate_identity import resolve_chosen_candidate
from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.battle.opponent import SpeciesDex
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.speed import SpeedOracle

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_REPORT = REPO_ROOT / "data" / "eval" / "accuracy-gate" / "gate-b-report.json"
MANIFEST = REPO_ROOT / "data" / "eval" / "accuracy-cap-derisk" / "decision-id-manifest.jsonl"


@pytest.fixture
def decision_kw(decision_fixture):
    req, kw = decision_fixture
    return req, copy.deepcopy(kw)


def test_choose_byte_identical_with_and_without_trace(decision_kw):
    req, kw = decision_kw
    without = heuristic_choose_for_request(req, **kw)
    trace = DecisionTrace()
    with_trace = heuristic_choose_for_request(req, trace=trace, **kw)
    assert with_trace == without
    assert trace.chosen_candidate_key is not None
    resolve_chosen_candidate(trace)


def test_historical_ambiguous_exceptions_resolve_with_structural_keys():
    if not GATE_REPORT.exists() or not MANIFEST.exists():
        pytest.skip("historical gate artifacts not available in this checkout")

    report = json.loads(GATE_REPORT.read_text(encoding="utf-8"))
    exceptions = report.get("acceptance", {}).get("exceptions", [])
    ambiguous_request_hashes = {
        row["request_hash"]
        for row in exceptions
        if "ambiguous chosen_candidate" in row.get("exception", "")
    }
    if not ambiguous_request_hashes:
        pytest.skip("no historical ambiguous exceptions in gate report")

    manifest_rows = [
        json.loads(line)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    from showdown_bot.eval.accuracy_cap_derisk import build_request_hash_index

    manifest_by_request_hash = build_request_hash_index(manifest_rows)
    ambiguous_decision_ids = {
        manifest_by_request_hash[request_hash]["decision_id"]
        for request_hash in ambiguous_request_hashes
        if request_hash in manifest_by_request_hash
    }
    if not ambiguous_decision_ids:
        pytest.skip("no manifest decision_ids for historical ambiguous request_hashes")

    from showdown_bot.eval.accuracy_cap_derisk import DecisionIdComponents, compute_decision_id
    from showdown_bot.eval.room_raw_replay import RequestKind, deduplicate_battle_logs, extract_decisions_from_log

    glob_dirs = [
        REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "room_raw",
        REPO_ROOT / "data" / "eval" / "t4" / "room_raw_divergent",
        REPO_ROOT / "data" / "eval" / "t6" / "room_raw",
        REPO_ROOT / "data" / "eval" / "kaggle-validation" / "room_raw",
    ]
    import glob

    log_files = []
    for d in glob_dirs:
        if d.exists():
            log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    manifest_files = [
        REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "t4rerun-run1.jsonl",
        REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "t4rerun-run2.jsonl",
        REPO_ROOT / "data" / "eval" / "t4" / "rerun" / "t4rerun-prefix.jsonl",
        REPO_ROOT / "data" / "eval" / "t6" / "t6-run1.jsonl",
        REPO_ROOT / "data" / "eval" / "t6" / "t6-run2.jsonl",
        REPO_ROOT / "data" / "eval" / "kaggle-validation" / "results.jsonl",
    ]
    dedup = deduplicate_battle_logs(
        log_files=sorted(set(log_files), key=str),
        manifest_files=[p for p in manifest_files if p.exists()],
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )

    decisions_by_id: dict[str, object] = {}
    for path in sorted(dedup.kept, key=str):
        identity = dedup.kept_identities.get(path)
        if identity is None:
            continue
        for d in extract_decisions_from_log(path):
            if d.kind != RequestKind.MOVE:
                continue
            decision_id = compute_decision_id(DecisionIdComponents(
                seed_base=identity.seed_base,
                seed_index=identity.seed_index,
                request_hash=d.request_hash,
                log_prefix_hash=d.log_prefix_hash,
                side=d.side,
                rqid=d.request.rqid,
                turn=d.turn,
            ))
            if decision_id in decisions_by_id:
                continue
            decisions_by_id[decision_id] = d

    book = load_spread_book(load_format_config("gen9vgc2025regi").meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    resolved = 0
    for decision_id in ambiguous_decision_ids:
        if decision_id not in decisions_by_id:
            continue
        decision = decisions_by_id[decision_id]
        trace = DecisionTrace()
        import os
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
        try:
            heuristic_choose_for_request(
                decision.request,
                state=copy.deepcopy(decision.state),
                book=book,
                our_side=decision.side,
                calc=calc,
                oracle=DamageOracle(calc),
                speed_oracle=speed_oracle,
                dex=dex,
                trace=trace,
            )
            chosen = resolve_chosen_candidate(trace)
            assert trace.chosen_candidate_key is not None
            assert chosen.candidate_key == trace.chosen_candidate_key
            resolved += 1
        finally:
            os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)

    assert resolved == len(ambiguous_decision_ids), (
        f"resolved {resolved}/{len(ambiguous_decision_ids)} historical ambiguous decisions "
        f"(keyed by decision_id)"
    )

"""Task 6: the coverage runner. Fully exercised WITHOUT a server or a battle -- run_local_gauntlet is
monkeypatched at the module seam (a stub that writes controlled v3 profile rows through the real
staging writer, simulates the Channel-A seed log, and returns a GauntletStats carrying
hero_invalid_decision_indices). Provenance is derived internally; the panel + out-dir are locked;
safety is per-seat + foe-Mega-bound with three fail-closed guards.
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from showdown_bot.eval.decision_profile import build_live_profile_row
from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.eval.coverage_schedule import (
    COVERAGE_PANEL_PATH,
    COVERAGE_SEED_BASE,
    build_coverage_schedule,
    load_coverage_manifest,
)
from showdown_bot.eval.coverage_verdict import COVERAGE_MAX_SCORED_DECISIONS
from showdown_bot.eval import coverage_runner as cr
from showdown_bot.eval.coverage_runner import (
    CoverageRunError,
    resolve_coverage_provenance,
    run_coverage_gate,
)
from showdown_bot.eval.coverage_schedule import COVERAGE_MAX_BATTLES

_REPO = Path(__file__).resolve().parents[2]
_TEAMS_ROOT = str(_REPO / "showdown_bot")

_BEFORE = {k: 0 for k in ("damage_batch_calls", "planned_damage_batches", "implicit_damage_batches",
                          "stats_batch_calls", "types_batch_calls", "mixed_batch_calls",
                          "transport_attempts", "spawn_count", "requests_total", "requests_unique", "cache_hits")}
_AFTER = {"damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
          "stats_batch_calls": 1, "types_batch_calls": 1, "mixed_batch_calls": 0,
          "transport_attempts": 3, "spawn_count": 3, "requests_total": 4, "requests_unique": 4, "cache_hits": 0}

_PROV = {"git_sha": "deadbeef", "config_hash": "cfg01", "calc_backend": "oneshot",
         "hero_agent": "heuristic", "candidate_identity": "cand0123456789ab"}


def _row(battle_id, decision_index, *, twins=2, slots=(0,), tie=False, outcome="ok"):
    shape = SimpleNamespace(n_candidates=8, n_responses=40, n_mega_twins=twins, n_branches=2,
                            n_worlds=1, depth2_frontier=0, foe_mega_slots=tuple(slots), foe_mega_order_tie=tie)
    return build_live_profile_row(
        battle_id=battle_id, decision_index=decision_index, schedule_hash="sched-cov-test",
        config_id="heuristic", format_id="gen9championsvgc2026regma", git_sha="deadbeef",
        config_hash="cfg01", calc_backend="oneshot", outcome=outcome, latency_ms=12.0,
        counters_before=dict(_BEFORE), counters_after=dict(_AFTER), shape=shape)


def _schedule(n=8):
    panel = load_panel(str(_REPO / COVERAGE_PANEL_PATH), teams_root=_TEAMS_ROOT)
    return build_coverage_schedule(panel, load_coverage_manifest(), n_battles=n, teams_root=_TEAMS_ROOT)


def _install(monkeypatch, *, rows_for, seed_log_path, games=1, indices_for=None, capture=None):
    import showdown_bot.client.gauntlet as g
    counter = {"i": 0}

    async def _fake(**kw):
        if capture is not None:
            capture.append(kw.get("games"))
        writer, ctx = kw["decision_profile_writer"], kw["decision_profile_context"]
        for row in rows_for(ctx.battle_id, counter["i"]):
            writer.write(row)
        i = counter["i"]; counter["i"] += 1
        with open(seed_log_path, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps({"battle_index": i, "seed_base": COVERAGE_SEED_BASE,
                                 "seed": derive_battle_seed(COVERAGE_SEED_BASE, i)}) + "\n")
        st = g.GauntletStats(games=games, hero_wins=1 if games == 1 else 0)
        st.hero_invalid_decision_indices = indices_for(i) if indices_for else ()
        return st

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    monkeypatch.setattr(cr, "resolve_coverage_provenance", lambda **k: dict(_PROV))


def _run(tmp_path, monkeypatch, *, rows_for, n=8, games=1, indices_for=None, capture=None, out="out"):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    seed_log = str(tmp_path / "seed.log")
    _install(monkeypatch, rows_for=rows_for, seed_log_path=seed_log, games=games,
             indices_for=indices_for, capture=capture)
    return run_coverage_gate(schedule=_schedule(n), out_dir=str(tmp_path / out), seed_log_path=seed_log,
                             expected_battles=n, teams_root=_TEAMS_ROOT)


# ---- pure / signature ------------------------------------------------------

def test_caps_are_200_and_2000():
    assert COVERAGE_MAX_BATTLES == 200 and COVERAGE_MAX_SCORED_DECISIONS == 2000


def test_the_runner_does_not_accept_caller_supplied_git_sha_or_config_hash():
    params = set(inspect.signature(run_coverage_gate).parameters)
    assert not (params & {"git_sha", "config_hash", "candidate_identity", "calc_backend"})


def test_the_runner_uses_the_derived_calc_backend_not_a_default(tmp_path, monkeypatch):
    # resolve_coverage_provenance is the ONLY legitimate source of calc_backend; a run under
    # SHOWDOWN_CALC_BACKEND=persistent must report "persistent" even though nothing ever passes
    # calc_backend as an argument (there is no such parameter -- see the signature test above).
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    seed_log = str(tmp_path / "seed.log")
    _install(monkeypatch, rows_for=lambda b, i: [_row(b, 0, slots=(0,))], seed_log_path=seed_log)
    monkeypatch.setattr(cr, "resolve_coverage_provenance",
                        lambda **k: {**_PROV, "calc_backend": "persistent"})
    report = run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                               seed_log_path=seed_log, expected_battles=8, teams_root=_TEAMS_ROOT)
    assert report["calc_backend"] == "persistent"


def test_resolve_coverage_provenance_derives_from_repo_and_env_and_refuses_dirty(monkeypatch):
    import showdown_bot.learning.provenance as prov
    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("cafef00d", False))
    monkeypatch.delenv("SHOWDOWN_CALC_BACKEND", raising=False)
    d = resolve_coverage_provenance()
    assert set(d) == {"git_sha", "config_hash", "calc_backend", "hero_agent", "candidate_identity"}
    assert d["git_sha"] == "cafef00d" and d["calc_backend"] == "oneshot" and len(d["candidate_identity"]) == 16
    # a dirty tree fails closed
    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("cafef00d", True))
    with pytest.raises(CoverageRunError):
        resolve_coverage_provenance()
    # an unknown calc backend fails closed
    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("cafef00d", False))
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "banana")
    with pytest.raises(CoverageRunError):
        resolve_coverage_provenance()


# ---- locks + atomic publish ------------------------------------------------

def test_the_out_dir_may_not_be_under_data_eval(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError, match="data/eval"):
        run_coverage_gate(schedule=_schedule(8), out_dir="data/eval/champions-panel-v0/coverage-v0",
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT)


def test_the_runner_refuses_a_leftover_staging_or_out_dir(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError, match="already exists"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(out), seed_log_path=str(tmp_path / "s.log"),
                          expected_battles=8, teams_root=_TEAMS_ROOT)


def test_the_panel_is_locked_to_the_coverage_panel(tmp_path, monkeypatch):
    # a schedule whose panel_hash is not the coverage panel's is refused before any battle.
    sched = _schedule(8)
    forged = type(sched)(version=sched.version, rows=sched.rows,
                         schedule_hash=sched.schedule_hash, panel_hash="0" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError):
        run_coverage_gate(schedule=forged, out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT)


def test_output_dir_is_published_atomically_and_verdict_equals_return(tmp_path, monkeypatch):
    # every foe-Mega slot present each battle, no safety issue: schedule exhausts (floor unmet at 8
    # battles) -> FAIL/schedule_exhausted, verdict.json on disk equals the returned dict.
    report = _run(tmp_path, monkeypatch,
                  rows_for=lambda b, i: [_row(b, 0, slots=(0, 1)), _row(b, 1, slots=(0, 1), tie=True)])
    out = tmp_path / "out"
    assert out.is_dir() and not (tmp_path / "out.staging").exists()
    on_disk = json.loads((out / "verdict.json").read_text("utf-8"))
    assert on_disk == report
    assert report["candidate_identity"] == "cand0123456789ab"
    assert report["stop_reason"] == "schedule_exhausted" and report["verdict"] == "FAIL"
    assert report["safety_violations"] == 0


def test_reaching_the_battle_cap_at_the_schedules_natural_end_is_FAIL_not_INCONCLUSIVE(tmp_path, monkeypatch):
    # In production, COVERAGE_MAX_BATTLES (200) always equals the schedule's own row count (the CLI
    # locks expected_battles=COVERAGE_MAX_BATTLES) -- so hitting the max_battles cap on the LAST row
    # is the schedule's natural end, not a truncation. A for/else that only sets
    # stop_reason="schedule_exhausted" when the loop was never `break`-ed misses this: the cap always
    # fires (and breaks) first, so a genuinely-exhausted schedule with an unmet floor was reported
    # INCONCLUSIVE/max_battles instead of FAIL/schedule_exhausted. Mirror that coincidence at n=8 by
    # patching the cap down to the schedule's own length.
    import showdown_bot.eval.coverage_verdict as cv
    monkeypatch.setattr(cv, "COVERAGE_MAX_BATTLES", 8)
    report = _run(tmp_path, monkeypatch, n=8,
                  rows_for=lambda b, i: [_row(b, 0, twins=0, slots=())])  # never meets the floor
    assert report["battles_played"] == 8
    assert report["verdict"] == "FAIL"
    assert report["stop_reason"] == "schedule_exhausted"


def test_the_runner_invokes_run_local_gauntlet_with_games_1(tmp_path, monkeypatch):
    seen = []
    _run(tmp_path, monkeypatch, rows_for=lambda b, i: [_row(b, 0, slots=(0, 1))], capture=seen)
    assert seen and set(seen) == {1}


# ---- safety: per-seat + foe-Mega-bound + guards ----------------------------

def test_a_hero_illegal_choice_on_a_foe_mega_decision_is_a_safety_violation(tmp_path, monkeypatch):
    # battle 0: decision 0 is a foe-Mega decision; the hero's invalid index (0,) joins to it.
    report = _run(tmp_path, monkeypatch,
                  rows_for=lambda b, i: [_row(b, 0, twins=2, slots=(0,))],
                  indices_for=lambda i: (0,) if i == 0 else ())
    assert report["safety_violations"] >= 1
    assert report["verdict"] == "FAIL" and report["stop_reason"] == "safety_violation"


def test_a_hero_illegal_choice_on_a_non_foe_mega_decision_is_not_a_coverage_safety_violation(tmp_path, monkeypatch):
    # decision 1 has foe_mega_active False (twins=0); the hero invalid index (1,) is out of scope.
    report = _run(tmp_path, monkeypatch,
                  rows_for=lambda b, i: [_row(b, 0, twins=2, slots=(0,)),
                                         _row(b, 1, twins=0, slots=())],
                  indices_for=lambda i: (1,) if i == 0 else ())
    assert report["safety_violations"] == 0
    assert report["verdict"] != "FAIL" or report["stop_reason"] != "safety_violation"


def test_an_opponent_invalid_choice_is_never_a_candidate_safety_violation(tmp_path, monkeypatch):
    # the opponent erred: the HERO's hero_invalid_decision_indices is empty -> no violation.
    report = _run(tmp_path, monkeypatch,
                  rows_for=lambda b, i: [_row(b, 0, slots=(0, 1))],
                  indices_for=lambda i: ())
    assert report["safety_violations"] == 0


def test_a_battle_that_did_not_complete_exactly_one_game_is_discarded_fail_closed(tmp_path, monkeypatch):
    with pytest.raises(CoverageRunError, match="did not complete exactly one game"):
        _run(tmp_path, monkeypatch, rows_for=lambda b, i: [_row(b, 0, slots=(0,))], games=0)
    assert not (tmp_path / "out").exists()


def test_an_unjoinable_hero_invalid_index_aborts_fail_closed(tmp_path, monkeypatch):
    # the hero invalid index 99 has NO matching decision row present -> technical abort (no out_dir).
    with pytest.raises(CoverageRunError, match="no present decision row"):
        _run(tmp_path, monkeypatch, rows_for=lambda b, i: [_row(b, 0, slots=(0,))],
             indices_for=lambda i: (99,) if i == 0 else ())
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "out" / "verdict.json").exists()


def test_a_technical_abort_publishes_no_out_dir_and_records_no_verdict(tmp_path, monkeypatch):
    # the -1 sentinel (unattributable |error|) aborts fail-closed: no out_dir, no verdict.
    with pytest.raises(CoverageRunError):
        _run(tmp_path, monkeypatch, rows_for=lambda b, i: [_row(b, 0, slots=(0,))],
             indices_for=lambda i: (-1,) if i == 0 else ())
    assert not (tmp_path / "out").exists()


def test_seed_alignment_is_verified(tmp_path, monkeypatch):
    # a seed log missing records for the battles that ran fails the alignment check.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    import showdown_bot.client.gauntlet as g

    async def _fake(**kw):
        for row in [_row(kw["decision_profile_context"].battle_id, 0, slots=(0, 1))]:
            kw["decision_profile_writer"].write(row)
        return g.GauntletStats(games=1, hero_wins=1)   # NOTE: writes NO seed-log record

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    monkeypatch.setattr(cr, "resolve_coverage_provenance", lambda **k: dict(_PROV))
    empty_log = tmp_path / "empty.log"
    empty_log.write_text("", encoding="utf-8")
    with pytest.raises(CoverageRunError, match="seed-log"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(empty_log), expected_battles=8, teams_root=_TEAMS_ROOT)

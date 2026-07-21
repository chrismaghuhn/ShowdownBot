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
import subprocess
import sys
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
    _is_under_data_eval,
    resolve_coverage_provenance,
    run_coverage_gate,
)
from showdown_bot.eval.coverage_schedule import COVERAGE_MAX_BATTLES
from showdown_bot.eval.gates import load_latency_budget_ms
from showdown_bot.eval.i8d_runner import (
    I8D_MAX_SCORED_DECISIONS,
    I8D_MIN_ACTIVE_DECISIONS,
    I8D_MIN_DISTINCT_BATTLES,
)
from showdown_bot.eval.i8d_schedule import I8D_EXPECTED_PANEL_HASH, I8D_SEED_BASE

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


_I8D_SCHED_HASH_TEST = "i8d-sched-test"     # matches the build_i8d_canonical_schedule stub below
_I8D_HERO_HASH_TEST = "i8d-hero-test-hash"  # matches the SAME stub's fake row
_I8D_OPP_HASH_TEST = "i8d-opp-test-hash"    # matches the SAME stub's fake row


def _i8d_canonical_stub():
    """The build_i8d_canonical_schedule() stub shared by _install() and the one test
    (test_seed_alignment_is_verified) that duplicates its setup manually. A single fake row is
    enough: the guard only ever reads .schedule_hash and .rows[*].hero_team_hash/.opp_team_hash."""
    return SimpleNamespace(
        schedule_hash=_I8D_SCHED_HASH_TEST,
        rows=(SimpleNamespace(hero_team_hash=_I8D_HERO_HASH_TEST, opp_team_hash=_I8D_OPP_HASH_TEST),))


def _write_i8d_verdict(tmp_path, *, omit_fields=(), name="i8d_verdict.json", **overrides):
    """A fully-shaped I8-D verdict artifact for the T3 identity+PASS+contract guard. Defaults to a
    valid, matching, PASSing artifact carrying the REAL field set a genuine I8-D verdict.json always
    has (review round 7: the guard now requires -- and where a canonical value is knowable, checks
    -- the full 25-field report i8d_runner.run_i8d_live_gate writes, not just the 11 fields it
    originally happened to read values from) so every OTHER test in this file (not testing the guard
    itself) sails through unchanged. A test targeting the guard overrides exactly the field(s) it
    wants wrong via **overrides (e.g. _write_i8d_verdict(tmp_path, git_sha="wrong")), or lists a
    field in omit_fields to make the artifact incomplete."""
    data = {
        "candidate_identity": _PROV["candidate_identity"], "verdict": "PASS",
        "calc_backend": _PROV["calc_backend"], "git_sha": _PROV["git_sha"],
        "config_hash": _PROV["config_hash"], "hero_agent": _PROV["hero_agent"],
        "panel_hash": I8D_EXPECTED_PANEL_HASH, "schedule_hash": _I8D_SCHED_HASH_TEST,
        "seed_base": I8D_SEED_BASE, "seed_log_verified": True, "p95_is_gate_value": True,
        "hero_team_hash": _I8D_HERO_HASH_TEST, "opp_team_hashes": [_I8D_OPP_HASH_TEST],
        "battles_played": 25, "scored_decisions": 65,
        "max_scored_decisions": I8D_MAX_SCORED_DECISIONS, "scored_overshoot": 0,
        "active_valid_decisions": 61, "distinct_active_battles": 21,
        "stop_reason": "exposure_floor_met", "exposure_floor_met": True,
        "min_active_decisions": I8D_MIN_ACTIVE_DECISIONS,
        "min_distinct_battles": I8D_MIN_DISTINCT_BATTLES,
        "budget_ms": load_latency_budget_ms(), "p95_ms": 1.0,
    }
    data.update(overrides)
    for field in omit_fields:
        data.pop(field, None)
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


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
    monkeypatch.setattr(cr, "build_i8d_canonical_schedule", lambda **k: _i8d_canonical_stub())


def _run(tmp_path, monkeypatch, *, rows_for, n=8, games=1, indices_for=None, capture=None, out="out"):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    seed_log = str(tmp_path / "seed.log")
    _install(monkeypatch, rows_for=rows_for, seed_log_path=seed_log, games=games,
             indices_for=indices_for, capture=capture)
    return run_coverage_gate(schedule=_schedule(n), out_dir=str(tmp_path / out), seed_log_path=seed_log,
                             expected_battles=n, teams_root=_TEAMS_ROOT,
                             i8d_verdict_path=_write_i8d_verdict(tmp_path))


# ---- pure / signature ------------------------------------------------------

def test_caps_are_200_and_2000():
    assert COVERAGE_MAX_BATTLES == 200 and COVERAGE_MAX_SCORED_DECISIONS == 2000


def test_the_runner_does_not_accept_caller_supplied_git_sha_or_config_hash():
    params = set(inspect.signature(run_coverage_gate).parameters)
    assert not (params & {"git_sha", "config_hash", "candidate_identity", "calc_backend",
                          "expected_panel_hash"})


def test_a_forged_panel_hash_on_otherwise_legitimate_rows_is_rejected(tmp_path, monkeypatch):
    # Review finding (F3, follow-up): expected_panel_hash was itself a caller-suppliable
    # parameter -- a forged schedule.panel_hash paired with a MATCHING caller-supplied
    # expected_panel_hash sailed through unnoticed (the rows were otherwise legitimate, so
    # schedule_hash matched canonical too). Now that the parameter is gone entirely, panel_hash
    # can only be checked against a canonical value derived internally from the locked
    # panel/manifest -- never anything the caller can supply or match.
    sched = _schedule(8)
    forged = type(sched)(version=sched.version, rows=sched.rows,
                         schedule_hash=sched.schedule_hash, panel_hash="f" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError, match="canonical panel_hash"):
        run_coverage_gate(schedule=forged, out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


def test_the_runner_uses_the_derived_calc_backend_not_a_default(tmp_path, monkeypatch):
    # resolve_coverage_provenance is the ONLY legitimate source of calc_backend; a run under
    # SHOWDOWN_CALC_BACKEND=persistent must report "persistent" even though nothing ever passes
    # calc_backend as an argument (there is no such parameter -- see the signature test above).
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    seed_log = str(tmp_path / "seed.log")
    _install(monkeypatch, rows_for=lambda b, i: [_row(b, 0, slots=(0,))], seed_log_path=seed_log)
    monkeypatch.setattr(cr, "resolve_coverage_provenance",
                        lambda **k: {**_PROV, "calc_backend": "persistent"})
    # the I8-D artifact's calc_backend must match THIS run's (overridden) calc_backend, or the new
    # calc_backend guard (review round 5) would refuse it before ever reaching the assertion below.
    report = run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                               seed_log_path=seed_log, expected_battles=8, teams_root=_TEAMS_ROOT,
                               i8d_verdict_path=_write_i8d_verdict(tmp_path, calc_backend="persistent"))
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
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


def test_the_data_eval_guard_is_case_insensitive_on_windows():
    # NTFS (this repo's actual platform) is case-insensitive: DATA\EVAL\... and data/eval/... are
    # the SAME directory on disk. A case-sensitive guard would silently let a run publish into the
    # protected frozen-evidence tree via a differently-cased path.
    assert _is_under_data_eval(r"data\eval\coverage-v0") is True
    assert _is_under_data_eval(r"DATA\EVAL\coverage-v0") is True
    assert _is_under_data_eval(r"Data\Eval\coverage-v0") is True
    assert _is_under_data_eval("DATA/EVAL/coverage-v0") is True
    assert _is_under_data_eval("data/notdata/coverage-v0") is False


def test_a_junction_pointing_at_data_eval_is_still_blocked(tmp_path):
    # Review finding (F6, follow-up): a pure string/segment match (even case-insensitive) never
    # resolves the path -- a junction/symlink under a totally different name that points AT the
    # repo's real data/eval would silently bypass it, since the STRING never contains "data/eval".
    # The write would still land in the protected tree regardless of what the caller's path string
    # says, so the guard must resolve the real target, not pattern-match the string.
    if sys.platform != "win32":
        pytest.skip("junction creation via mklink is Windows-specific")
    alias = tmp_path / "alias_dir"
    target = _REPO / "data" / "eval"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)],
                   check=True, capture_output=True)
    assert _is_under_data_eval(str(alias / "some-coverage-run")) is True


def test_an_unrelated_directory_sharing_the_data_eval_name_stays_allowed(tmp_path):
    # Review finding (F6, follow-up): a pure segment-pair search anywhere in the string flags ANY
    # path with a "data" segment immediately followed by an "eval" segment, even one that has
    # nothing to do with this repo (e.g. an unrelated project's own data/eval directory reached via
    # a completely different root). The guard protects THIS repo's tree specifically -- it must
    # compare against the repo's own canonical data/eval, not search for the substring anywhere.
    other = tmp_path / "other" / "data" / "eval"
    other.mkdir(parents=True)
    assert _is_under_data_eval(str(other / "coverage-v0")) is False


def test_the_runner_refuses_a_leftover_staging_or_out_dir(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError, match="already exists"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(out), seed_log_path=str(tmp_path / "s.log"),
                          expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


def test_a_reordered_matchup_cycle_is_rejected_even_with_a_valid_panel_hash(tmp_path, monkeypatch):
    # panel_hash covers team CONTENT only (schedule composition is a separate concern): reverse the
    # manifest's matchup order before building, so panel_hash is unchanged (still the approved teams)
    # and the forged schedule is fully SELF-consistent (verify_coverage_schedule's own checks only
    # compare a schedule against itself) -- only a rebuild-and-compare against the canonical
    # panel/manifest catches the reordering.
    from dataclasses import replace
    manifest = load_coverage_manifest()
    reordered = replace(manifest, matchups=tuple(reversed(manifest.matchups)))
    panel = load_panel(str(_REPO / COVERAGE_PANEL_PATH), teams_root=_TEAMS_ROOT)
    forged = build_coverage_schedule(panel, reordered, n_battles=8, teams_root=_TEAMS_ROOT)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError, match="schedule_hash"):
        run_coverage_gate(schedule=forged, out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


def test_a_teams_hash_record_that_no_longer_matches_disk_is_caught_by_the_runner_itself(tmp_path, monkeypatch):
    # opp_team_hash/hero_team_hash are explicitly EXCLUDED from schedule_hash (eval/schedule.py) --
    # so a stale/tampered recorded hash is invisible to the canonical-rebuild-and-compare check
    # above. Only re-hashing every team file from disk (verify_coverage_panel_and_teams) catches it,
    # and that guard must run INSIDE run_coverage_gate itself -- not only from the CLI wrapper --
    # so any direct caller of the runner gets the same TOCTOU protection immediately before battle 1.
    from dataclasses import replace
    sched = _schedule(8)
    tampered = replace(sched.rows[0], opp_team_hash="0" * 16)
    forged = type(sched)(version=sched.version, rows=(tampered,) + sched.rows[1:],
                         schedule_hash=sched.schedule_hash, panel_hash=sched.panel_hash)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError, match="content hash"):
        run_coverage_gate(schedule=forged, out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


def test_the_panel_is_locked_to_the_coverage_panel(tmp_path, monkeypatch):
    # a schedule whose panel_hash is not the coverage panel's is refused before any battle.
    sched = _schedule(8)
    forged = type(sched)(version=sched.version, rows=sched.rows,
                         schedule_hash=sched.schedule_hash, panel_hash="0" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    with pytest.raises(CoverageRunError):
        run_coverage_gate(schedule=forged, out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


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
    monkeypatch.setattr(cr, "build_i8d_canonical_schedule", lambda **k: _i8d_canonical_stub())
    empty_log = tmp_path / "empty.log"
    empty_log.write_text("", encoding="utf-8")
    with pytest.raises(CoverageRunError, match="seed-log"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(empty_log), expected_battles=8, teams_root=_TEAMS_ROOT,
                          i8d_verdict_path=_write_i8d_verdict(tmp_path))


# ---- T3: fail closed unless the SAME I8-D candidate PASSed ----------------------------------

def _no_schedule_build(monkeypatch):
    """Poison-pill build_coverage_live_schedule: if the identity/PASS guard actually runs before
    the canonical schedule is built (the T3 requirement), this never fires and the test's
    CoverageRunError comes from the guard itself, not from this pill."""
    def _boom(*a, **k):
        raise AssertionError("build_coverage_live_schedule was called -- the I8-D guard did not "
                             "run before the canonical schedule build")
    monkeypatch.setattr(cr, "build_coverage_live_schedule", _boom)


def test_a_missing_i8d_verdict_path_is_refused_before_the_schedule_build(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    with pytest.raises(CoverageRunError, match="i8d.verdict.path"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path="")
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "out.staging").exists()


def test_an_unreadable_or_malformed_i8d_verdict_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    missing_path = str(tmp_path / "does_not_exist.json")
    with pytest.raises(CoverageRunError, match="cannot read"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=missing_path)
    assert not (tmp_path / "out").exists()

    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CoverageRunError, match="cannot read"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out2"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=str(malformed_path))
    assert not (tmp_path / "out2").exists()


@pytest.mark.parametrize("bad_json", ["[]", "null", '"just a string"'])
def test_an_i8d_verdict_that_is_not_a_json_object_is_refused(tmp_path, monkeypatch, bad_json):
    # (P2, review round 5) json.load succeeds on any valid JSON, not just objects; .get() on a
    # list/None/str raises AttributeError, not CoverageRunError, unless guarded explicitly.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = tmp_path / "not_an_object.json"
    path.write_text(bad_json, encoding="utf-8")
    with pytest.raises(CoverageRunError, match="not a JSON object"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=str(path))
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("missing_field", [
    "candidate_identity", "verdict", "calc_backend", "git_sha", "config_hash", "hero_agent",
    "panel_hash", "schedule_hash", "seed_base", "seed_log_verified", "p95_is_gate_value",
    "hero_team_hash", "opp_team_hashes", "battles_played", "scored_decisions",
    "max_scored_decisions", "scored_overshoot", "active_valid_decisions",
    "distinct_active_battles", "stop_reason", "exposure_floor_met", "min_active_decisions",
    "min_distinct_battles", "budget_ms", "p95_ms",
])
def test_an_i8d_verdict_missing_a_required_field_is_refused(tmp_path, monkeypatch, missing_field):
    # (P1, review round 5) a hand-crafted JSON carrying only SOME fields must not pass -- the
    # check is general (any of the real I8-D verdict's fields, not hardcoded to the two this
    # guard happens to compare values from).
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, omit_fields=(missing_field,))
    with pytest.raises(CoverageRunError, match=r"missing required field\(s\)"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_panel_hash_is_refused(tmp_path, monkeypatch):
    # (P1, review round 5) binds the artifact to the REAL I8-D panel, not just any panel_hash string.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, panel_hash="0" * 16)
    with pytest.raises(CoverageRunError, match="panel_hash"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_seed_base_is_refused(tmp_path, monkeypatch):
    # (P1, review round 5) binds the artifact to the REAL I8-D seed namespace.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, seed_base="not-the-i8d-namespace")
    with pytest.raises(CoverageRunError, match="seed_base"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_seed_log_not_verified_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, seed_log_verified=False)
    with pytest.raises(CoverageRunError, match="seed_log_verified"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_a_mismatched_i8d_candidate_identity_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    wrong_path = _write_i8d_verdict(tmp_path, candidate_identity="wrongidentity01")
    with pytest.raises(CoverageRunError, match="candidate_identity"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=wrong_path)
    assert not (tmp_path / "out").exists()


def test_a_mismatched_calc_backend_is_refused(tmp_path, monkeypatch):
    # (P1, review round 5) candidate_identity does NOT capture calc_backend by design -- confirmed
    # empirically that switching SHOWDOWN_CALC_BACKEND between oneshot/persistent leaves
    # config_hash and candidate_identity byte-identical (both "594295543f13a55d" /
    # "a68acfef984b91f1" in the reproduction). Same candidate_identity as _PROV (oneshot), but the
    # I8-D artifact claims a different backend -- must still be refused.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, calc_backend="persistent")
    with pytest.raises(CoverageRunError, match="calc_backend"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_git_sha_is_refused(tmp_path, monkeypatch):
    # (P1, review round 6) candidate_identity alone does not bind git_sha: it is a PUBLIC,
    # locally-computable hash (nothing secret in the formula or its inputs), so a hand-crafted
    # artifact can carry the CORRECT candidate_identity (trivially reproducible) alongside a
    # completely unrelated git_sha. Kept equal to _PROV's candidate_identity here on purpose --
    # only git_sha itself is wrong -- to prove the raw field is checked, not just its hash.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, git_sha="some-other-commit")
    with pytest.raises(CoverageRunError, match="git_sha"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_config_hash_is_refused(tmp_path, monkeypatch):
    # (P1, review round 6) same gap as git_sha, for config_hash.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, config_hash="some-other-config")
    with pytest.raises(CoverageRunError, match="config_hash"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_hero_agent_is_refused(tmp_path, monkeypatch):
    # (P1, review round 6) same gap as git_sha, for hero_agent.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, hero_agent="some-other-agent")
    with pytest.raises(CoverageRunError, match="hero_agent"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_schedule_hash_is_refused(tmp_path, monkeypatch):
    # (P1, review round 6) schedule_hash was required PRESENT but never checked against anything --
    # the test helper's own former hardcoded "i8d-sched-test" default (never tied to any real I8-D
    # schedule) proved the gap. Now bound against a freshly rebuilt canonical I8-D schedule
    # (build_i8d_canonical_schedule, stubbed in _install() to keep this test hermetic).
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, schedule_hash="not-the-canonical-i8d-schedule")
    with pytest.raises(CoverageRunError, match="schedule_hash"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_p95_is_gate_value_false_but_verdict_pass_is_refused(tmp_path, monkeypatch):
    # (P1, review round 6) the real i8d_verdict() can never produce verdict="PASS" together with
    # p95_is_gate_value=False (its PASS/FAIL branch always pairs with True; only the untested
    # INCONCLUSIVE branch sets it False) -- but a hand-crafted JSON is not bound by that invariant
    # unless the guard checks it explicitly.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, p95_is_gate_value=False)
    with pytest.raises(CoverageRunError, match="p95_is_gate_value"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_min_active_decisions_is_refused(tmp_path, monkeypatch):
    # (P1, review round 7) required PRESENT (round 6) but never checked against the pinned floor --
    # a forged artifact could claim a LOWERED floor and still look complete.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, min_active_decisions=1)
    with pytest.raises(CoverageRunError, match="min_active_decisions"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_min_distinct_battles_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, min_distinct_battles=1)
    with pytest.raises(CoverageRunError, match="min_distinct_battles"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_max_scored_decisions_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, max_scored_decisions=1)
    with pytest.raises(CoverageRunError, match="max_scored_decisions"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_budget_ms_is_refused(tmp_path, monkeypatch):
    # a forged artifact could claim an INFLATED budget and still look complete.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, budget_ms=999999)
    with pytest.raises(CoverageRunError, match="budget_ms"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_hero_team_hash_is_refused(tmp_path, monkeypatch):
    # (P1, review round 7) hero_team_hash/opp_team_hashes required PRESENT (round 6) but never
    # checked -- both are free given the already-rebuilt canonical I8-D schedule.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, hero_team_hash="not-the-canonical-hero-hash")
    with pytest.raises(CoverageRunError, match="hero_team_hash"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_opp_team_hashes_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, opp_team_hashes=["not-the-canonical-opp-hash"])
    with pytest.raises(CoverageRunError, match="opp_team_hashes"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_exposure_floor_met_false_but_verdict_pass_is_refused(tmp_path, monkeypatch):
    # (P1, review round 7) a genuine verdict="PASS" can only ever pair with
    # exposure_floor_met=True (i8d_verdict()'s PASS/FAIL branch requires the floor met) -- a
    # hand-crafted JSON is not bound by that invariant unless checked explicitly.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, exposure_floor_met=False)
    with pytest.raises(CoverageRunError, match="exposure_floor_met"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_wrong_stop_reason_is_refused(tmp_path, monkeypatch):
    # (P1, review round 7) a genuine verdict="PASS" can only ever pair with
    # stop_reason="exposure_floor_met" (i8d_runner.should_stop checks the floor FIRST, before
    # max_battles/max_scored_decisions) -- checked explicitly since a hand-crafted JSON is not bound
    # by that invariant otherwise.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, stop_reason="max_battles")
    with pytest.raises(CoverageRunError, match="stop_reason"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_p95_ms_above_budget_is_refused(tmp_path, monkeypatch):
    # (P1, review round 7) p95_is_gate_value=True (checked since round 6) does not by itself prove
    # p95_ms is a sane number -- a hand-crafted JSON could pair verdict="PASS" with any p95_ms.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, p95_ms=999999.0)
    with pytest.raises(CoverageRunError, match="p95_ms"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_a_non_numeric_p95_ms_is_refused(tmp_path, monkeypatch):
    # type-safety companion to the check above (generalises review round 5 P2's non-object-JSON
    # lesson): a non-numeric p95_ms must fail closed with CoverageRunError, not crash with an
    # unhandled TypeError from the "<=" comparison.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, p95_ms=None)
    with pytest.raises(CoverageRunError, match="p95_ms"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("counter_field,bad_value", [
    ("battles_played", "25"),
    ("battles_played", True),
    ("scored_decisions", -1),
    ("scored_overshoot", 3.5),
    ("active_valid_decisions", -5),
    ("active_valid_decisions", False),
    ("distinct_active_battles", "21"),
])
def test_an_i8d_verdict_with_a_bad_counter_type_or_sign_is_refused(tmp_path, monkeypatch,
                                                                    counter_field, bad_value):
    # (P1, review round 8) the five per-run counters were required PRESENT (round 7) but never
    # type/sign-checked -- a string, bool, float, or negative value was accepted.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, **{counter_field: bad_value})
    with pytest.raises(CoverageRunError, match=counter_field):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_a_wrong_scored_overshoot_is_refused(tmp_path, monkeypatch):
    # (P1, review round 8) scored_overshoot is a DETERMINISTIC function of scored_decisions
    # (i8d_runner's own literal "max(0, scored_decisions - max_scored_decisions)") but was only
    # presence-checked (round 7) -- an internally-inconsistent value sailed through.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, scored_overshoot=999)
    with pytest.raises(CoverageRunError, match="scored_overshoot"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_more_active_valid_decisions_than_scored_is_refused(tmp_path, monkeypatch):
    # (P1, review round 8) active-valid rows are a SUBSET of all scored rows by construction --
    # claiming more active-valid than total scored is internally impossible.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, scored_decisions=10, active_valid_decisions=61)  # 61 > 10
    with pytest.raises(CoverageRunError, match="active_valid_decisions"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_more_distinct_active_battles_than_battles_played_is_refused(tmp_path, monkeypatch):
    # (P1, review round 8) distinct active battle_ids cannot outnumber battles actually played.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, battles_played=5, distinct_active_battles=21)  # 21 > 5
    with pytest.raises(CoverageRunError, match="distinct_active_battles"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_active_valid_decisions_below_the_floor_is_refused(tmp_path, monkeypatch):
    # (P1, review round 8) exposure_floor_met=True (checked since round 7) is, by itself, just a
    # bare claim -- re-derive i8d_runner.exposure_floor_met()'s own comparison against the
    # artifact's own counters instead of trusting the boolean alone.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, active_valid_decisions=0)
    with pytest.raises(CoverageRunError, match="active_valid_decisions"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_distinct_active_battles_below_the_floor_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, distinct_active_battles=0)
    with pytest.raises(CoverageRunError, match="distinct_active_battles"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_nan_p95_ms_is_refused(tmp_path, monkeypatch):
    # (P1, review round 8) json.loads parses the bare token NaN into float('nan'), and EVERY
    # comparison with NaN -- including the round-7 guard's "> budget_ms" -- returns False under
    # IEEE 754. Empirically reproduced before fixing: the round-7 guard silently accepted this.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, p95_ms=float("nan"))
    with pytest.raises(CoverageRunError, match="p95_ms"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_a_negative_p95_ms_is_refused(tmp_path, monkeypatch):
    # (P1, review round 8) a negative p95_ms is physically nonsensical; the round-7 "> budget_ms"
    # check never excluded it (a negative number is trivially "not greater than the budget").
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, p95_ms=-1.0)
    with pytest.raises(CoverageRunError, match="p95_ms"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_an_unexpected_extra_field_is_refused(tmp_path, monkeypatch):
    # (P2, review round 8) the comment claimed "the EXACT field set" but the check only rejected
    # MISSING fields -- an artifact with every required field plus an arbitrary extra still passed.
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    path = _write_i8d_verdict(tmp_path, totally_unexpected_field="anything")
    with pytest.raises(CoverageRunError, match="unexpected extra field"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=path)
    assert not (tmp_path / "out").exists()


def test_an_i8d_verdict_with_the_right_identity_but_verdict_fail_is_refused(tmp_path, monkeypatch):
    # Same candidate, but I8-D itself did not PASS -- the binding execution order is "I8-D must
    # PASS -> coverage runs on the same candidate", not merely "same candidate" (P1, review round 5).
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", COVERAGE_SEED_BASE)
    _install(monkeypatch, rows_for=lambda b, i: [], seed_log_path=str(tmp_path / "s.log"))
    _no_schedule_build(monkeypatch)
    fail_path = _write_i8d_verdict(tmp_path, verdict="FAIL")   # candidate_identity matches _PROV
    with pytest.raises(CoverageRunError, match="'FAIL'"):
        run_coverage_gate(schedule=_schedule(8), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "s.log"), expected_battles=8,
                          teams_root=_TEAMS_ROOT, i8d_verdict_path=fail_path)
    assert not (tmp_path / "out").exists()

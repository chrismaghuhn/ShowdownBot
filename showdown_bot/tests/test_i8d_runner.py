"""I8-D §4: the exposure/cap runner and the verdict.

Two tiers, both fully exercised WITHOUT a server or a battle:

- Pure decision core -- ``exposure_floor_met`` / ``should_stop`` / ``i8d_active_p95_ms`` /
  ``i8d_verdict`` -- the load-bearing logic. The stop rule is plan §5.1 verbatim (D-1 floor,
  then the two caps; ``measured_ms`` is never an input); the verdict is §5.2's three-way table;
  the floor (≥ 60 active decisions from ≥ 20 distinct battles) and the 1000 ms budget are the
  CLOSED D-1/gates numbers, not test-chosen; the p95 is the same nearest-rank statistic the
  per-battle gate uses (reused, not re-derived).

- The driver ``run_i8d_live_gate`` -- monkeypatches ``run_local_gauntlet`` at the module seam
  (a stub that writes controlled profile rows through the real writer and returns stats), so the
  loop, the whole-battle stop (§5.4.4: a battle is adopted only once complete; the scored cap is
  a THRESHOLD the last battle may overshoot by exactly its own rows), the recount, the verdict,
  the atomic LF verdict staging, and the restart-from-seed-0-no-merge gate are all real.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.battle.mega_scoring import MegaShapeCounts
from showdown_bot.eval.decision_profile import build_live_profile_row
from showdown_bot.eval.schedule import Schedule, ScheduleRow
from showdown_bot.eval.i8d_runner import (
    I8D_MIN_ACTIVE_DECISIONS,
    I8D_MIN_DISTINCT_BATTLES,
    I8D_MAX_SCORED_DECISIONS,
    I8DRunError,
    exposure_floor_met,
    i8d_active_p95_ms,
    i8d_verdict,
    run_i8d_live_gate,
    should_stop,
)

# ---- pure decision core ----------------------------------------------------


def test_the_closed_floor_numbers_are_the_pinned_ones():
    assert (I8D_MIN_ACTIVE_DECISIONS, I8D_MIN_DISTINCT_BATTLES, I8D_MAX_SCORED_DECISIONS) == (60, 20, 2000)


@pytest.mark.parametrize("active,distinct,expected", [
    (60, 20, True),
    (60, 19, False),      # spread minimum unmet
    (59, 20, False),      # decision minimum unmet
    (200, 200, True),
    (0, 0, False),
])
def test_exposure_floor_met(active, distinct, expected):
    assert exposure_floor_met(active, distinct) is expected


def test_should_stop_fires_on_d1_before_the_caps_and_names_it():
    stop, reason = should_stop(battles_played=5, scored_decisions=100, active_valid=60, distinct_battles=20)
    assert stop is True and reason == "exposure_floor_met"


def test_should_stop_d1_wins_the_reason_even_when_a_cap_also_holds():
    # A battle can cross D-1 and a cap at once; the good stop is reported.
    stop, reason = should_stop(battles_played=200, scored_decisions=2000, active_valid=60, distinct_battles=20)
    assert stop is True and reason == "exposure_floor_met"


def test_should_stop_on_max_battles():
    stop, reason = should_stop(battles_played=200, scored_decisions=100, active_valid=5, distinct_battles=3)
    assert stop is True and reason == "max_battles"


def test_should_stop_on_max_scored_decisions_including_overshoot():
    stop, reason = should_stop(battles_played=14, scored_decisions=2100, active_valid=0, distinct_battles=0)
    assert stop is True and reason == "max_scored_decisions"


def test_should_not_stop_below_every_threshold():
    stop, reason = should_stop(battles_played=10, scored_decisions=500, active_valid=59, distinct_battles=25)
    assert stop is False and reason is None


def test_measured_ms_is_never_a_stop_input():
    # There is no latency argument to the stop rule at all -- it cannot be a stop input.
    import inspect
    params = set(inspect.signature(should_stop).parameters)
    assert not (params & {"measured_ms", "p95", "p95_ms", "latency", "latencies"})


def test_active_p95_is_nearest_rank_and_reuses_the_gate_statistic():
    from showdown_bot.client.gauntlet import _latency_p95
    values = [float(i) for i in range(1, 21)]           # 1..20
    # idx = round(0.95*(20-1)) = round(18.05) = 18 -> the 19th smallest.
    assert i8d_active_p95_ms(values) == 19.0
    assert i8d_active_p95_ms(values) == _latency_p95(values)
    scattered = [12.0, 3.0, 900.0, 45.0, 45.0, 7.0, 1001.0]
    assert i8d_active_p95_ms(scattered) == _latency_p95(scattered)


def test_verdict_pass_at_the_budget_boundary():
    v = i8d_verdict(active_valid=60, distinct_battles=20, active_measured_ms=[1000.0] * 60, budget_ms=1000)
    assert v["verdict"] == "PASS"
    assert v["p95_ms"] == 1000.0 and v["p95_is_gate_value"] is True and v["exposure_floor_met"] is True


def test_verdict_fail_just_over_the_budget():
    v = i8d_verdict(active_valid=60, distinct_battles=20, active_measured_ms=[1000.5] * 60, budget_ms=1000)
    assert v["verdict"] == "FAIL"
    assert v["p95_ms"] == 1000.5 and v["p95_is_gate_value"] is True


@pytest.mark.parametrize("active,distinct", [(59, 20), (60, 19), (0, 0)])
def test_verdict_inconclusive_when_floor_unmet_even_if_fast(active, distinct):
    # A blazing-fast p95 cannot rescue a run that misses the floor: the floor is a precondition
    # evaluated BEFORE the p95, and an INCONCLUSIVE run reports no gate p95.
    v = i8d_verdict(active_valid=active, distinct_battles=distinct, active_measured_ms=[1.0] * active, budget_ms=1000)
    assert v["verdict"] == "INCONCLUSIVE — exposure floor not met"
    assert v["p95_ms"] is None and v["p95_is_gate_value"] is False and v["exposure_floor_met"] is False


# ---- the driver ------------------------------------------------------------

_BEFORE = {"damage_batch_calls": 0, "planned_damage_batches": 0, "implicit_damage_batches": 0,
           "stats_batch_calls": 0, "types_batch_calls": 0, "transport_attempts": 0,
           "spawn_count": 0, "requests_total": 0, "requests_unique": 0, "cache_hits": 0}
_AFTER = {"damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
          "stats_batch_calls": 16, "types_batch_calls": 2, "transport_attempts": 19,
          "spawn_count": 1, "requests_total": 140, "requests_unique": 9, "cache_hits": 80}


def _shape(twins):
    s = MegaShapeCounts()
    s.n_candidates, s.n_responses, s.n_mega_twins = 8, 48, twins
    s.n_branches, s.n_worlds, s.depth2_frontier = 3, 1, 0
    return s


def _mk(*, battle_id, decision_index, outcome="ok", twins=24, latency_ms=100.0):
    return build_live_profile_row(
        battle_id=battle_id, decision_index=decision_index, schedule_hash="sched-i8d-test",
        config_id="heuristic", format_id="gen9championsvgc2026regma", git_sha="deadbeef",
        config_hash="cfg01", calc_backend="persistent", outcome=outcome, latency_ms=latency_ms,
        counters_before=dict(_BEFORE), counters_after=dict(_AFTER), shape=_shape(twins))


def _sched(n):
    rows = tuple(
        ScheduleRow(
            format_id="gen9championsvgc2026regma", hero_team_path="teams/hero.txt",
            opp_policy="heuristic" if i % 2 == 0 else "max_damage",
            opp_team_path="teams/opp.txt", seed_index=i)
        for i in range(n)
    )
    return Schedule(version="1", rows=rows, schedule_hash="sched-i8d-test", panel_hash=None)


def _install_stub(monkeypatch, *, rows_for):
    """A battle-free run_local_gauntlet: it writes this battle's rows through the REAL writer
    the driver passed (so they are per-row validated and land in the frozen dataset), stamping
    each with the context's battle_id so distinct-battle accounting is exercised, then returns
    stats. If the driver reused one context across battles, every row would share one battle_id
    and the spread floor could never be met -- so this doubles as a distinct-context counterproof.
    """
    import showdown_bot.client.gauntlet as g

    async def _fake(**kw):
        writer = kw["decision_profile_writer"]
        ctx = kw["decision_profile_context"]
        for row in rows_for(ctx.battle_id):
            writer.write(row)
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)


def _run(tmp_path, schedule, monkeypatch, *, rows_for):
    _install_stub(monkeypatch, rows_for=rows_for)
    return run_i8d_live_gate(
        schedule=schedule, profile_out=str(tmp_path / "profile.jsonl"),
        verdict_out=str(tmp_path / "verdict.json"), config_hash="cfg01", git_sha="deadbeef")


def test_driver_stops_on_the_exposure_floor_and_passes(tmp_path, monkeypatch):
    # 3 active decisions per battle, one distinct battle_id each, fast measured_ms: the floor is
    # met at exactly battle 20 (60 active from 20 distinct), before the 24-row schedule is spent.
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=k, outcome="ok", twins=24, latency_ms=100.0)
                for k in range(3)]

    report = _run(tmp_path, _sched(24), monkeypatch, rows_for=rows_for)
    assert report["stop_reason"] == "exposure_floor_met"
    assert report["battles_played"] == 20
    assert report["active_valid_decisions"] == 60
    assert report["distinct_active_battles"] == 20
    assert report["verdict"] == "PASS"
    assert report["p95_ms"] == 100.0 and report["p95_is_gate_value"] is True
    assert report["scored_overshoot"] == 0


def test_driver_whole_battle_overshoot_is_bounded_and_reported(tmp_path, monkeypatch):
    # 150 INACTIVE ok decisions per battle: scored accrues, active never does. Before battle 14
    # scored = 1950 < 2000 (no premature stop); battle 14 completes and carries it to 2100. The
    # cap is a stop THRESHOLD, overshot by exactly one battle's rows -- never truncated.
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=k, outcome="ok", twins=0, latency_ms=5.0)
                for k in range(150)]

    report = _run(tmp_path, _sched(20), monkeypatch, rows_for=rows_for)
    assert report["stop_reason"] == "max_scored_decisions"
    assert report["battles_played"] == 14
    assert report["scored_decisions"] == 2100
    assert report["scored_overshoot"] == 100
    assert report["active_valid_decisions"] == 0
    assert report["verdict"] == "INCONCLUSIVE — exposure floor not met"
    assert report["p95_ms"] is None


def test_driver_exhausts_the_schedule_when_neither_floor_nor_cap_binds(tmp_path, monkeypatch):
    # 6 battles, 1 active decision each: 6 active from 6 distinct battles -- floor unmet, no cap.
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=0, outcome="ok", twins=24, latency_ms=100.0)]

    report = _run(tmp_path, _sched(6), monkeypatch, rows_for=rows_for)
    assert report["stop_reason"] == "schedule_exhausted"
    assert report["battles_played"] == 6
    assert report["active_valid_decisions"] == 6
    assert report["verdict"] == "INCONCLUSIVE — exposure floor not met"


def test_verdict_report_is_atomic_lf_and_equals_the_return_value(tmp_path, monkeypatch):
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=0, outcome="ok", twins=24, latency_ms=100.0)]

    report = _run(tmp_path, _sched(6), monkeypatch, rows_for=rows_for)
    vpath = tmp_path / "verdict.json"
    raw = vpath.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")          # LF-stable
    assert json.loads(raw.decode("utf-8")) == report          # what we staged == what we returned
    assert not (tmp_path / "verdict.json.tmp").exists()        # atomic replace left no temp behind


def test_driver_refuses_to_merge_into_an_existing_profile(tmp_path, monkeypatch):
    p = tmp_path / "profile.jsonl"
    p.write_text('{"from":"an earlier partial run"}\n', encoding="utf-8")
    _install_stub(monkeypatch, rows_for=lambda bid: [])
    with pytest.raises(I8DRunError, match="already has content"):
        run_i8d_live_gate(schedule=_sched(6), profile_out=str(p),
                          verdict_out=str(tmp_path / "verdict.json"), config_hash="c", git_sha="d")


def test_driver_refuses_to_overwrite_an_existing_verdict(tmp_path, monkeypatch):
    v = tmp_path / "verdict.json"
    v.write_text("{}\n", encoding="utf-8")
    _install_stub(monkeypatch, rows_for=lambda bid: [])
    with pytest.raises(I8DRunError, match="already has content"):
        run_i8d_live_gate(schedule=_sched(6), profile_out=str(tmp_path / "profile.jsonl"),
                          verdict_out=str(v), config_hash="c", git_sha="d")


def test_driver_builds_a_distinct_battle_id_per_row(tmp_path, monkeypatch):
    # Capture the battle_ids the driver actually stamps: they must all differ (seed_index varies),
    # else the spread floor is unreachable no matter how many decisions are scored.
    seen: list = []

    import showdown_bot.client.gauntlet as g

    async def _fake(**kw):
        seen.append(kw["decision_profile_context"].battle_id)
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    run_i8d_live_gate(schedule=_sched(6), profile_out=str(tmp_path / "profile.jsonl"),
                      verdict_out=str(tmp_path / "verdict.json"), config_hash="c", git_sha="d")
    assert len(seen) == 6 and len(set(seen)) == 6

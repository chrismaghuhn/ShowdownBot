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
from showdown_bot.eval.panel import Panel, PanelTeam
from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.eval.i8d_schedule import I8D_SEED_BASE, I8DScheduleError, build_i8d_schedule
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
           "stats_batch_calls": 0, "types_batch_calls": 0, "mixed_batch_calls": 0,
           "transport_attempts": 0,
           "spawn_count": 0, "requests_total": 0, "requests_unique": 0, "cache_hits": 0}
_AFTER = {"damage_batch_calls": 1, "planned_damage_batches": 1, "implicit_damage_batches": 0,
          "stats_batch_calls": 16, "types_batch_calls": 2, "mixed_batch_calls": 0,
          "transport_attempts": 19,
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


def _panel() -> Panel:
    def t(tid, arch):
        return PanelTeam(team_id=tid, team_path=f"teams/panel_champions_v0/{tid}.txt",
                         archetype=arch, team_hash=f"hash_{tid}")
    return Panel(
        version="champions_v0", policies=("heuristic", "max_damage"),
        dev_teams=(t("goodstuff", "balance_goodstuff"),
                   t("tailwind_offense", "tailwind_offense"),
                   t("trick_room", "trick_room")),
        heldout_teams=(t("rain_offense", "weather_rain"), t("disruption", "bulky_disruption")),
        panel_hash="aac1ea30446fde88")


def _canon(n):
    """A CANONICAL I8-D schedule of n rows -- passes verify_i8d_schedule(expected_battles=n). The
    runner re-locks the schedule, so a hand-built stand-in would now be rejected (finding 3)."""
    return build_i8d_schedule(_panel(), n_battles=n, teams_root=".")


def _install_stub(monkeypatch, *, rows_for, seed_log_path, games=1):
    """A battle-free run_local_gauntlet that (a) writes this battle's rows through the STAGING
    writer the driver passed, stamping each with the context's battle_id (so distinct-battle
    accounting and per-battle staging are exercised), and (b) simulates the Channel-A server
    appending a seed-log record for the created battle. ``games`` lets a test drive the
    incomplete-battle (games != 1) discard path. Battles play in seed_index order, so the record's
    battle_index is a simple counter.
    """
    import showdown_bot.client.gauntlet as g
    counter = {"i": 0}

    async def _fake(**kw):
        writer = kw["decision_profile_writer"]
        ctx = kw["decision_profile_context"]
        for row in rows_for(ctx.battle_id):
            writer.write(row)
        i = counter["i"]
        counter["i"] += 1
        with open(seed_log_path, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps({"battle_index": i, "seed_base": I8D_SEED_BASE,
                                 "seed": derive_battle_seed(I8D_SEED_BASE, i)}) + "\n")
        return g.GauntletStats(games=games, hero_wins=1 if games == 1 else 0)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)


def _fixture_teams(tmp_path):
    """Create the champions team files the canonical schedule references, under a teams_root, so the
    runner's per-battle team resolution + non-empty-packed check pass. .packed is one non-empty line."""
    from showdown_bot.eval.i8d_schedule import I8D_HERO_TEAM
    root = tmp_path / "teamsroot"
    for rel in (I8D_HERO_TEAM, "teams/panel_champions_v0/goodstuff.txt",
                "teams/panel_champions_v0/tailwind_offense.txt",
                "teams/panel_champions_v0/trick_room.txt"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("paste\n", encoding="utf-8")
        p.with_suffix(".packed").write_text("stub-packed-team", encoding="utf-8")
    return str(root)


def _run(tmp_path, schedule, monkeypatch, *, rows_for, games=1):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)   # the server's approved namespace
    seed_log = str(tmp_path / "seed.log")
    _install_stub(monkeypatch, rows_for=rows_for, seed_log_path=seed_log, games=games)
    return run_i8d_live_gate(
        schedule=schedule, out_dir=str(tmp_path / "out"), seed_log_path=seed_log,
        config_hash="cfg01", git_sha="deadbeef", expected_battles=len(schedule.rows),
        teams_root=_fixture_teams(tmp_path))


def test_driver_stops_on_the_exposure_floor_and_passes(tmp_path, monkeypatch):
    # 3 active decisions per battle, one distinct battle_id each, fast measured_ms: the floor is
    # met at exactly battle 20 (60 active from 20 distinct), before the 24-row schedule is spent.
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=k, outcome="ok", twins=24, latency_ms=100.0)
                for k in range(3)]

    report = _run(tmp_path, _canon(24), monkeypatch, rows_for=rows_for)
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

    report = _run(tmp_path, _canon(20), monkeypatch, rows_for=rows_for)
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

    report = _run(tmp_path, _canon(6), monkeypatch, rows_for=rows_for)
    assert report["stop_reason"] == "schedule_exhausted"
    assert report["battles_played"] == 6
    assert report["active_valid_decisions"] == 6
    assert report["verdict"] == "INCONCLUSIVE — exposure floor not met"


def test_output_dir_is_published_atomically_and_verdict_equals_return(tmp_path, monkeypatch):
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=0, outcome="ok", twins=24, latency_ms=100.0)]

    report = _run(tmp_path, _canon(6), monkeypatch, rows_for=rows_for)
    out = tmp_path / "out"
    raw = (out / "verdict.json").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")            # LF-stable
    assert json.loads(raw.decode("utf-8")) == report          # what we staged == what we returned
    assert (out / "profile.jsonl").exists()                   # profile + verdict published together
    assert not (tmp_path / "out.staging").exists()            # the staging dir was consumed by the rename

    # candidate_identity + its ingredients must reach the published artifact, not just be
    # computable in isolation -- _run() calls run_i8d_live_gate with git_sha="deadbeef",
    # config_hash="cfg01", hero_agent defaulting to "heuristic".
    from showdown_bot.learning.provenance import make_candidate_identity
    expected_identity = make_candidate_identity(
        hero_agent="heuristic", git_sha="deadbeef", config_hash="cfg01")
    for field, expected in (("candidate_identity", expected_identity), ("git_sha", "deadbeef"),
                            ("config_hash", "cfg01"), ("calc_backend", "oneshot"),
                            ("hero_agent", "heuristic")):
        assert report[field] == expected, f"report[{field!r}] == {report.get(field)!r}"
        parsed = json.loads(raw.decode("utf-8"))
        assert parsed[field] == expected, f"published verdict.json[{field!r}] == {parsed.get(field)!r}"


def _gate(tmp_path, schedule, monkeypatch, *, seed_log=None, base=I8D_SEED_BASE):
    """Call the runner with the env set but WITHOUT a stub -- for the fail-closed preflight gates
    that must fire before any battle is dispatched."""
    if base is not None:
        monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", base)
    else:
        monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    return run_i8d_live_gate(
        schedule=schedule, out_dir=str(tmp_path / "out"),
        seed_log_path=str(tmp_path / "seed.log") if seed_log is None else seed_log,
        config_hash="c", git_sha="d", expected_battles=len(schedule.rows))


def test_driver_refuses_to_merge_into_an_existing_output_dir(tmp_path, monkeypatch):
    (tmp_path / "out").mkdir()
    with pytest.raises(I8DRunError, match="already exists"):
        _gate(tmp_path, _canon(6), monkeypatch)


def test_driver_refuses_a_leftover_staging_dir(tmp_path, monkeypatch):
    (tmp_path / "out.staging").mkdir()   # a crashed run's staging dir
    with pytest.raises(I8DRunError, match="already exists"):
        _gate(tmp_path, _canon(6), monkeypatch)


def test_driver_builds_a_distinct_battle_id_per_row(tmp_path, monkeypatch):
    # The battle_ids the driver stamps must all differ (seed_index varies), else the spread floor
    # is unreachable no matter how many decisions are scored. rows_for(bid) records them.
    seen: list = []
    _run(tmp_path, _canon(6), monkeypatch, rows_for=lambda bid: seen.append(bid) or [])
    assert len(seen) == 6 and len(set(seen)) == 6


# ---- finding 1: a battle that does not complete one game is discarded, never adopted ----------

def test_an_incomplete_battle_is_discarded_and_the_run_fails_closed(tmp_path, monkeypatch):
    # The stub stages 5 rows THEN reports games == 0 (a timeout). Those partial rows must never
    # reach the frozen dataset, the staging file must be gone, and no verdict is written -- a run
    # restarted for an infrastructure fault restarts from seed 0 (§5.1), not from a half battle.
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=k, outcome="ok", twins=24, latency_ms=100.0)
                for k in range(5)]

    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)
    seed_log = str(tmp_path / "seed.log")
    _install_stub(monkeypatch, rows_for=rows_for, seed_log_path=seed_log, games=0)
    with pytest.raises(I8DRunError, match="did not complete exactly one game"):
        run_i8d_live_gate(
            schedule=_canon(6), out_dir=str(tmp_path / "out"), seed_log_path=seed_log,
            config_hash="c", git_sha="d", expected_battles=6, teams_root=_fixture_teams(tmp_path))
    assert not (tmp_path / "out").exists()                        # never published
    # the staging dir remains (crashed run) but holds NO adopted battle rows and no staged battle
    assert (tmp_path / "out.staging" / "profile.jsonl").read_text(encoding="utf-8").strip() == ""
    assert not (tmp_path / "out.staging" / "battle.jsonl").exists()


# ---- finding 2: the seeds are PROVEN, not merely labelled -------------------------------------

def test_run_refuses_a_missing_seed_base(tmp_path, monkeypatch):
    with pytest.raises(I8DRunError, match="SHOWDOWN_BATTLE_SEED_BASE must be"):
        _gate(tmp_path, _canon(6), monkeypatch, base=None)


def test_run_refuses_a_wrong_seed_base(tmp_path, monkeypatch):
    with pytest.raises(I8DRunError, match="SHOWDOWN_BATTLE_SEED_BASE must be"):
        _gate(tmp_path, _canon(6), monkeypatch, base="some-other-namespace")


def test_run_requires_a_seed_log(tmp_path, monkeypatch):
    with pytest.raises(I8DRunError, match="requires the server's seed log"):
        _gate(tmp_path, _canon(6), monkeypatch, seed_log="")


def test_run_fails_closed_on_a_misaligned_seed_log(tmp_path, monkeypatch):
    # The server logs a WRONG seed for each created battle (namespace intact): a run whose seeds
    # cannot be proven against derive_battle_seed yields no verdict.
    import showdown_bot.client.gauntlet as g
    seed_log = str(tmp_path / "seed.log")
    counter = {"i": 0}

    async def _fake(**kw):
        for r in [_mk(battle_id=kw["decision_profile_context"].battle_id, decision_index=0)]:
            kw["decision_profile_writer"].write(r)
        i = counter["i"]
        counter["i"] += 1
        with open(seed_log, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps({"battle_index": i, "seed_base": I8D_SEED_BASE, "seed": "WRONG"}) + "\n")
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)
    with pytest.raises(I8DRunError, match="seed-log verification failed"):
        run_i8d_live_gate(
            schedule=_canon(6), out_dir=str(tmp_path / "out"), seed_log_path=seed_log,
            config_hash="c", git_sha="d", expected_battles=6, teams_root=_fixture_teams(tmp_path))
    assert not (tmp_path / "out").exists()   # seeds unproven -> no verdict, nothing published


# ---- finding 3 (integration): the runner re-locks the schedule at the execution point ---------

def test_run_rejects_a_non_canonical_schedule_at_the_execution_point(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)
    # a canonical 24-row schedule, but the gate is locked to 200: count mismatch is refused BEFORE
    # any battle, and no output files are created.
    with pytest.raises(I8DScheduleError, match="exactly 200 rows"):
        run_i8d_live_gate(
            schedule=_canon(24), out_dir=str(tmp_path / "out"),
            seed_log_path=str(tmp_path / "seed.log"), config_hash="c", git_sha="d")   # default 200
    assert not (tmp_path / "out").exists() and not (tmp_path / "out.staging").exists()


# ---- blocker 2 (integration): the panel + team content identity is bound at the runner ---------

def test_run_rejects_a_schedule_whose_panel_hash_is_not_the_approved_one(tmp_path, monkeypatch):
    import dataclasses
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)
    # panel_hash is content-derived; a value != the frozen champions panel means the team CONTENTS
    # are not the approved ones (schedule_hash alone would not catch it -- rows are unchanged).
    bad = dataclasses.replace(_canon(6), panel_hash="not-the-champions-panel")
    with pytest.raises(I8DRunError, match="panel_hash .* != expected champions panel"):
        run_i8d_live_gate(
            schedule=bad, out_dir=str(tmp_path / "out"), seed_log_path=str(tmp_path / "seed.log"),
            config_hash="c", git_sha="d", expected_battles=6)
    assert not (tmp_path / "out").exists()


def test_verdict_records_the_panel_and_team_hashes(tmp_path, monkeypatch):
    def rows_for(bid):
        return [_mk(battle_id=bid, decision_index=0, outcome="ok", twins=24, latency_ms=100.0)]

    report = _run(tmp_path, _canon(6), monkeypatch, rows_for=rows_for)
    assert report["panel_hash"] == "aac1ea30446fde88"          # the content-bound panel identity
    assert report["opp_team_hashes"] == ["hash_goodstuff", "hash_tailwind_offense", "hash_trick_room"]
    assert "hero_team_hash" in report                          # recorded (None here: hero file absent)

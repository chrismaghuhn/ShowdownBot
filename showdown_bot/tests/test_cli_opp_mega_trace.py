"""I7b-C Rev. 9 finding 1: the opponent-Mega sidecar must be REACHABLE from the
real schedule CLI.

Before this slice `_Client` accepted an `opp_mega_trace_writer` that no caller
could supply: `run_local_gauntlet` had no such parameter and nothing anywhere
constructed an `OppMegaTraceWriter`. Every off-by-default test passed and a live
smoke would have written zero rows -- the same dead end the original I7b-C root
cause had one layer down (`opp_mega_evidence_sink` on `_choose_best_mega` with no
caller passing one).

No live server/battles: `run_local_gauntlet` is monkeypatched at the
`showdown_bot.client.gauntlet` module seam that `cli.run_schedule` re-imports
from on every call (its `from ... import ...` is a LOCAL import inside the
function body, so it re-reads the current module attribute at call time).
"""
from __future__ import annotations

import argparse

import pytest

_SCHEDULE_YAML = """\
version: "1"
rows:
  - format_id: gen9vgc2025regi
    hero_team_path: teams/fixed_team.txt
    opp_policy: max_damage
    opp_team_path: teams/fixed_team.txt
    seed_index: 0
  - format_id: gen9vgc2025regi
    hero_team_path: teams/fixed_team.txt
    opp_policy: max_damage
    opp_team_path: teams/fixed_team.txt
    seed_index: 1
"""


@pytest.fixture
def _sched_path(tmp_path):
    p = tmp_path / "sched.yaml"
    p.write_text(_SCHEDULE_YAML, encoding="utf-8")
    return p


def _fake_battle_record():
    """The battle-derived half of a T2 result row (see gauntlet._battle_result_record).
    Supplied so the --result-out path's own completeness check ("wrote 0 rows but
    schedule has N") does not fire ahead of the assertion under test."""
    return {
        "winner": "hero", "turns": 5, "end_reason": "normal", "end_hp_diff": 10,
        "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 42,
        "room_raw_path": None, "normalized_room_log_sha256": None,
    }


def _capture_runner(monkeypatch, received):
    import showdown_bot.client.gauntlet as gauntlet_mod

    async def _fake(**kwargs):
        received.append(kwargs)
        on_br = kwargs.get("on_battle_result")
        if on_br is not None:
            on_br(_fake_battle_record())
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake)


def test_run_schedule_without_env_passes_no_writer_or_context(_sched_path, monkeypatch):
    """Off by default: env unset -> the runner gets an explicit None for both, and
    no OppMegaTraceWriter is ever constructed."""
    import showdown_bot.eval.opp_mega_trace as opp_mod
    from showdown_bot import cli

    monkeypatch.delenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", raising=False)
    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)
    monkeypatch.setattr(
        opp_mod, "OppMegaTraceWriter",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("env-off path constructed an OppMegaTraceWriter")),
    )

    received: list = []
    _capture_runner(monkeypatch, received)
    cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))

    assert len(received) == 2
    for kw in received:
        assert kw["opp_mega_trace_writer"] is None
        assert kw["opp_mega_trace_context"] is None


def test_run_schedule_with_env_reaches_runner_with_real_writer_and_per_battle_contexts(
    _sched_path, tmp_path, monkeypatch
):
    """UPPER-BOUNDARY COUNTERPROOF for finding 1.

    Not "some object arrived": the runner must receive a REAL OppMegaTraceWriter
    pointed at the env's path, ONE run-scoped instance shared by both rows, and a
    DISTINCT OppMegaTraceContext per row carrying that row's own real battle_id /
    config_hash / schedule_hash / git_sha. Two battles sharing a context would
    stamp every row with the first battle's battle_id."""
    from showdown_bot import cli
    from showdown_bot.eval.opp_mega_trace import OppMegaTraceContext, OppMegaTraceWriter
    from showdown_bot.eval.schedule import load_schedule

    out = tmp_path / "opp_mega_trace.jsonl"
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", str(out))
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "i7b-c-test-base")
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)

    received: list = []
    _capture_runner(monkeypatch, received)
    cli.run_schedule(argparse.Namespace(
        schedule=str(_sched_path), result_out=str(tmp_path / "results.jsonl"),
    ))

    assert len(received) == 2
    writers = [kw["opp_mega_trace_writer"] for kw in received]
    contexts = [kw["opp_mega_trace_context"] for kw in received]

    # A real writer, on the env's path, built once and shared run-scoped.
    assert all(isinstance(w, OppMegaTraceWriter) for w in writers)
    assert writers[0] is writers[1]
    assert writers[0].path == str(out)

    # A real, DISTINCT context per battle -- never the same object, never the same id.
    assert all(isinstance(c, OppMegaTraceContext) for c in contexts)
    assert contexts[0] is not contexts[1]
    assert contexts[0].battle_id != contexts[1].battle_id
    assert all(c.battle_id for c in contexts)

    # Real provenance, not placeholders: schedule_hash matches the loaded schedule,
    # and format_id matches the row.
    sched = load_schedule(str(_sched_path))
    assert all(c.schedule_hash == sched.schedule_hash for c in contexts)
    assert all(c.format_id == "gen9vgc2025regi" for c in contexts)
    assert all(c.config_id == "heuristic" for c in contexts)
    assert all(c.config_hash for c in contexts)
    assert all(c.git_sha for c in contexts)


def test_run_schedule_env_without_result_out_fails_closed(_sched_path, tmp_path, monkeypatch):
    """Evidence with no result row to join against is unusable provenance -- and
    battle_id/config_hash are only computed on the --result-out path at all."""
    from showdown_bot import cli

    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", str(tmp_path / "t.jsonl"))
    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)

    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="SHOWDOWN_OPP_MEGA_TRACE_OUT requires --result-out"):
        cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))
    assert received == []  # fails BEFORE any battle is dispatched


def test_run_schedule_refuses_an_existing_non_empty_sidecar(_sched_path, tmp_path, monkeypatch):
    """Appending onto a previous run's file would interleave two runs into one
    file that later reads as a single run -- mirrors --result-out's own T2-CC-2
    gate."""
    from showdown_bot import cli

    out = tmp_path / "opp_mega_trace.jsonl"
    out.write_text('{"battle_id":"from-an-earlier-run"}\n', encoding="utf-8")
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", str(out))
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "i7b-c-test-base")

    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="already has rows"):
        cli.run_schedule(argparse.Namespace(
            schedule=str(_sched_path), result_out=str(tmp_path / "results.jsonl"),
        ))
    assert received == []


def test_plain_gauntlet_with_env_set_fails_closed_instead_of_silently_ignoring(tmp_path, monkeypatch):
    """The no-schedule gauntlet path cannot build a battle_id/config_hash, so it
    can never honour the env. Silently ignoring it would hand back an empty file
    that reads as 'the bot generated no foe-Mega hypotheses' -- a false claim.
    Fail closed and name the supported path instead."""
    from showdown_bot import cli

    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", str(tmp_path / "t.jsonl"))
    # Monkeypatched so a MISSING guard surfaces as "no SystemExit" rather than as a
    # ConnectionRefusedError from a real socket -- and so a regression here can never
    # be mistaken for an unrelated environment problem.
    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="SHOWDOWN_OPP_MEGA_TRACE_OUT.*--schedule.*--result-out"):
        cli.run_gauntlet(argparse.Namespace(
            schedule="", games=1, villain="max_damage",
            format_id="gen9vgc2025regi", strict=False,
        ))
    assert received == []  # fails BEFORE any battle is dispatched

"""I8-D: the live decision-profile sidecar must be REACHABLE from the real schedule CLI.

The gauntlet ``_Client`` already accepts a ``decision_profile_writer``/``decision_profile_context``
(proven by ``test_i8d_live_profile_wiring.py``), but before this slice no caller could supply
either: ``run_local_gauntlet`` had no such parameter and nothing constructed a
``DecisionProfileWriter``. Every off-by-default test passed and a live gate run would have
written zero rows -- the same dead-end shape the I7b-C opp-mega sidecar had to close one layer up.

This mirrors ``test_cli_opp_mega_trace.py`` exactly, because the wiring is deliberately the same
env-only, --result-out-gated, run-scoped-writer / per-battle-context shape.

No live server/battles: ``run_local_gauntlet`` is monkeypatched at the
``showdown_bot.client.gauntlet`` module seam that ``cli.run_schedule`` re-imports from on every
call (its ``from ... import ...`` is a LOCAL import inside the function body).
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


def _clear_backend_env(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_CALC_BACKEND", raising=False)


def test_run_schedule_without_env_passes_no_writer_or_context(_sched_path, monkeypatch):
    """Off by default: env unset -> the runner gets an explicit None for both, and no
    DecisionProfileWriter is ever constructed."""
    import showdown_bot.eval.decision_profile as dp_mod
    from showdown_bot import cli

    monkeypatch.delenv("SHOWDOWN_DECISION_PROFILE_OUT", raising=False)
    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)
    monkeypatch.setattr(
        dp_mod, "DecisionProfileWriter",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("env-off path constructed a DecisionProfileWriter")),
    )

    received: list = []
    _capture_runner(monkeypatch, received)
    cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))

    assert len(received) == 2
    for kw in received:
        assert kw["decision_profile_writer"] is None
        assert kw["decision_profile_context"] is None


def test_run_schedule_with_env_reaches_runner_with_real_writer_and_per_battle_contexts(
    _sched_path, tmp_path, monkeypatch
):
    """UPPER-BOUNDARY COUNTERPROOF: the runner must receive a REAL DecisionProfileWriter
    pointed at the env's path, ONE run-scoped instance shared by both rows, and a DISTINCT
    LiveProfileContext per row carrying that row's own real battle_id / config_hash /
    schedule_hash / git_sha. Two battles sharing a context would stamp every row with the
    first battle's battle_id."""
    from showdown_bot import cli
    from showdown_bot.eval.decision_profile import DecisionProfileWriter, LiveProfileContext
    from showdown_bot.eval.schedule import load_schedule

    out = tmp_path / "decision_profile.jsonl"
    monkeypatch.setenv("SHOWDOWN_DECISION_PROFILE_OUT", str(out))
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "i8d-test-base")
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)
    _clear_backend_env(monkeypatch)  # unset -> the "oneshot" default label

    received: list = []
    _capture_runner(monkeypatch, received)
    cli.run_schedule(argparse.Namespace(
        schedule=str(_sched_path), result_out=str(tmp_path / "results.jsonl"),
    ))

    assert len(received) == 2
    writers = [kw["decision_profile_writer"] for kw in received]
    contexts = [kw["decision_profile_context"] for kw in received]

    # A real writer, on the env's path, built once and shared run-scoped.
    assert all(isinstance(w, DecisionProfileWriter) for w in writers)
    assert writers[0] is writers[1]
    assert writers[0].path == str(out)

    # A real, DISTINCT context per battle -- never the same object, never the same id.
    assert all(isinstance(c, LiveProfileContext) for c in contexts)
    assert contexts[0] is not contexts[1]
    assert contexts[0].battle_id != contexts[1].battle_id
    assert all(c.battle_id for c in contexts)

    # Real provenance, not placeholders: schedule_hash matches the loaded schedule, format_id
    # matches the row, config_id is the hero policy, and the calc_backend label defaults to
    # "oneshot" (matching make_calc_backend with SHOWDOWN_CALC_BACKEND unset).
    sched = load_schedule(str(_sched_path))
    assert all(c.schedule_hash == sched.schedule_hash for c in contexts)
    assert all(c.format_id == "gen9vgc2025regi" for c in contexts)
    assert all(c.config_id == "heuristic" for c in contexts)
    assert all(c.config_hash for c in contexts)
    assert all(c.git_sha for c in contexts)
    assert all(c.calc_backend == "oneshot" for c in contexts)


def test_run_schedule_calc_backend_label_follows_env(_sched_path, tmp_path, monkeypatch):
    """The row's provenance label must record the backend the client will actually build:
    SHOWDOWN_CALC_BACKEND=persistent -> "persistent" (normalised exactly as make_calc_backend
    selects it), not the default."""
    from showdown_bot import cli

    monkeypatch.setenv("SHOWDOWN_DECISION_PROFILE_OUT", str(tmp_path / "dp.jsonl"))
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "i8d-test-base")
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "persistent")

    received: list = []
    _capture_runner(monkeypatch, received)
    cli.run_schedule(argparse.Namespace(
        schedule=str(_sched_path), result_out=str(tmp_path / "results.jsonl"),
    ))

    contexts = [kw["decision_profile_context"] for kw in received]
    assert contexts and all(c.calc_backend == "persistent" for c in contexts)


def test_run_schedule_unknown_calc_backend_fails_closed(_sched_path, tmp_path, monkeypatch):
    """An unknown SHOWDOWN_CALC_BACKEND would make the client's make_calc_backend() raise at
    run time; the profile path fails closed up front with the same vocabulary instead of
    stamping a bogus label."""
    from showdown_bot import cli

    monkeypatch.setenv("SHOWDOWN_DECISION_PROFILE_OUT", str(tmp_path / "dp.jsonl"))
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "i8d-test-base")
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "quantum")

    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="unknown SHOWDOWN_CALC_BACKEND"):
        cli.run_schedule(argparse.Namespace(
            schedule=str(_sched_path), result_out=str(tmp_path / "results.jsonl"),
        ))
    assert received == []  # fails BEFORE any battle is dispatched


def test_run_schedule_env_without_result_out_fails_closed(_sched_path, tmp_path, monkeypatch):
    """A live profile with no result row to join against is unusable provenance -- and
    battle_id/config_hash are only computed on the --result-out path at all."""
    from showdown_bot import cli

    monkeypatch.setenv("SHOWDOWN_DECISION_PROFILE_OUT", str(tmp_path / "dp.jsonl"))
    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    _clear_backend_env(monkeypatch)

    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="SHOWDOWN_DECISION_PROFILE_OUT requires --result-out"):
        cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))
    assert received == []  # fails BEFORE any battle is dispatched


def test_run_schedule_refuses_an_existing_non_empty_sidecar(_sched_path, tmp_path, monkeypatch):
    """Appending onto a previous run's file would interleave two runs into one file that
    later reads as a single run -- mirrors --result-out's own T2-CC-2 gate."""
    from showdown_bot import cli

    out = tmp_path / "decision_profile.jsonl"
    out.write_text('{"battle_id":"from-an-earlier-run"}\n', encoding="utf-8")
    monkeypatch.setenv("SHOWDOWN_DECISION_PROFILE_OUT", str(out))
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "i8d-test-base")
    _clear_backend_env(monkeypatch)

    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="already has rows"):
        cli.run_schedule(argparse.Namespace(
            schedule=str(_sched_path), result_out=str(tmp_path / "results.jsonl"),
        ))
    assert received == []


def test_plain_gauntlet_with_env_set_fails_closed_instead_of_silently_ignoring(tmp_path, monkeypatch):
    """The no-schedule gauntlet path cannot build a battle_id/config_hash, so it can never
    honour the env. Silently ignoring it would hand back an empty file that reads as 'the bot
    made no scored decisions' -- a false claim. Fail closed and name the supported path."""
    from showdown_bot import cli

    monkeypatch.setenv("SHOWDOWN_DECISION_PROFILE_OUT", str(tmp_path / "dp.jsonl"))
    _clear_backend_env(monkeypatch)
    received: list = []
    _capture_runner(monkeypatch, received)
    with pytest.raises(SystemExit, match="SHOWDOWN_DECISION_PROFILE_OUT.*--schedule.*--result-out"):
        cli.run_gauntlet(argparse.Namespace(
            schedule="", games=1, villain="max_damage",
            format_id="gen9vgc2025regi", strict=False,
        ))
    assert received == []  # fails BEFORE any battle is dispatched

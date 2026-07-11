"""2b-4 Task 3: `cli.run_schedule` reads SHOWDOWN_HERO_AGENT to select the hero agent for a
schedule run (the ONLY seam that lets a Kaggle kernel select "heuristic_reranker" -- the gated
override agent, 2b-4 Task 2 -- for a schedule battle; ScheduleRow itself has no per-row
hero-agent field). Absent -> "heuristic", byte-identical to every prior run_schedule call.

Same no-live-server technique as test_cli_run_schedule_export.py: `run_local_gauntlet` is
monkeypatched at the `showdown_bot.client.gauntlet` module seam `cli.run_schedule` re-imports
from on every call, so no battle/server is ever started.
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


def _clean_seed_env(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)


def _patch_run_local_gauntlet(monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet_mod

    calls = []

    async def _fake(**kwargs):
        calls.append(kwargs)
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake)
    return calls


def test_hero_agent_defaults_to_heuristic_when_env_unset(_sched_path, monkeypatch):
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_HERO_AGENT", raising=False)
    calls = _patch_run_local_gauntlet(monkeypatch)

    cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))

    assert len(calls) == 2
    assert all(c["hero_agent"] == "heuristic" for c in calls)


def test_hero_agent_reads_env_override(_sched_path, monkeypatch):
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_HERO_AGENT", "heuristic_reranker")
    calls = _patch_run_local_gauntlet(monkeypatch)

    cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))

    assert len(calls) == 2
    assert all(c["hero_agent"] == "heuristic_reranker" for c in calls)


def test_hero_agent_is_the_same_for_every_row(_sched_path, monkeypatch):
    # Not per-row -- one run-time choice for the whole schedule run.
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_HERO_AGENT", "max_damage")
    calls = _patch_run_local_gauntlet(monkeypatch)

    cli.run_schedule(argparse.Namespace(schedule=str(_sched_path), result_out=""))

    assert {c["hero_agent"] for c in calls} == {"max_damage"}

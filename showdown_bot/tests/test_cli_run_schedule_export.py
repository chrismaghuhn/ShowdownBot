"""2b-2.5a run-scoped dataset export fix: `cli.run_schedule` must build ONE export runtime
(when the SHOWDOWN_DATASET_EXPORT gate is active) and thread the SAME instance through every
`run_local_gauntlet` call, closing it exactly once after the row loop -- not build+close a
fresh runtime inside each of the N per-row calls (the old behavior, which meant every battle's
flush overwrote the file and only the last battle in the schedule ever survived to disk).

No live server/battles: `run_local_gauntlet` and `build_schedule_export_runtime` are both
monkeypatched at the `showdown_bot.client.gauntlet` module seam that `cli.run_schedule`
re-imports from on every call (`from showdown_bot.client.gauntlet import ...` is a LOCAL
import inside the function body, so it re-reads the current module attribute at call time).
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
  - format_id: gen9vgc2025regi
    hero_team_path: teams/fixed_team.txt
    opp_policy: max_damage
    opp_team_path: teams/fixed_team.txt
    seed_index: 2
"""


class _FakeRuntime:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


@pytest.fixture
def _sched_path(tmp_path):
    p = tmp_path / "sched.yaml"
    p.write_text(_SCHEDULE_YAML, encoding="utf-8")
    return p


def _clean_seed_env(monkeypatch):
    # Keep the --result-out / seed-log branches out of scope for these tests.
    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)


def test_run_schedule_builds_export_runtime_once_and_threads_same_instance(
    _sched_path, tmp_path, monkeypatch
):
    import showdown_bot.client.gauntlet as gauntlet_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "dataset.jsonl"))

    fake_runtime = _FakeRuntime()
    build_calls = []

    def _fake_build(format_id, hero_team_path, villain_team_path=None):
        build_calls.append((format_id, hero_team_path, villain_team_path))
        return fake_runtime

    received_runtimes = []

    async def _fake_run_local_gauntlet(**kwargs):
        received_runtimes.append(kwargs.get("export_runtime"))
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "build_schedule_export_runtime", _fake_build)
    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="")
    cli.run_schedule(args)

    assert len(build_calls) == 1  # built exactly ONCE for the whole schedule, not per row
    # representative row 0 -- 2b-2.5a wiring fix: villain_team_path is now threaded too, so the
    # run-scoped runtime's INITIAL mirror_flag reflects row 0's real hero/villain pairing.
    assert build_calls[0] == ("gen9vgc2025regi", "teams/fixed_team.txt", "teams/fixed_team.txt")
    assert received_runtimes == [fake_runtime, fake_runtime, fake_runtime]  # SAME object, all 3 rows
    assert fake_runtime.closed == 1  # closed exactly once, after the loop


def test_run_schedule_skips_export_runtime_when_env_gate_unset(_sched_path, tmp_path, monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)

    build_calls = []

    def _fake_build(*a, **kw):
        build_calls.append((a, kw))
        return _FakeRuntime()

    received_runtimes = []

    async def _fake_run_local_gauntlet(**kwargs):
        received_runtimes.append(kwargs.get("export_runtime"))
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "build_schedule_export_runtime", _fake_build)
    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="")
    cli.run_schedule(args)

    assert build_calls == []  # gate off -> never even attempted
    assert received_runtimes == [None, None, None]  # every row runs with export disabled


def test_run_schedule_closes_export_runtime_even_if_a_battle_raises(_sched_path, tmp_path, monkeypatch):
    """The finally-close must fire on the failure path too, not just the happy path --
    otherwise a mid-schedule crash leaks the rollout-mode CalcClient (2b-2.5a Kaggle-OOM
    concern) for the run-scoped runtime exactly as it would for a per-battle one."""
    import showdown_bot.client.gauntlet as gauntlet_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_DATASET_EXPORT", str(tmp_path / "dataset.jsonl"))

    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(gauntlet_mod, "build_schedule_export_runtime", lambda *a, **kw: fake_runtime)

    async def _boom(**kwargs):
        raise RuntimeError("simulated battle crash")

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _boom)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="")
    with pytest.raises(RuntimeError, match="simulated battle crash"):
        cli.run_schedule(args)

    assert fake_runtime.closed == 1  # still closed despite the mid-loop exception

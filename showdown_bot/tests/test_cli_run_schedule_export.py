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
import json
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# candidate-vs-baseline-diff Task 4: `--decision-trace-out` requires `--result-out`
# (the trace sidecar binds into the per-battle result row, so a result row must
# exist to bind into). This must raise BEFORE any battle is played.
# ---------------------------------------------------------------------------


def test_schedule_trace_requires_result_out(_sched_path, monkeypatch):
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)

    args = argparse.Namespace(
        schedule=str(_sched_path), result_out="", decision_trace_out="trace.jsonl",
    )
    with pytest.raises(SystemExit, match="--decision-trace-out requires --result-out"):
        cli.run_schedule(args)


# ---------------------------------------------------------------------------
# 2c-Slice-0b Task 3: `--agg-trace-out` -- a SECOND, INDEPENDENT optional sidecar
# from `--decision-trace-out` above. Same off-by-default discipline (unset ->
# byte-identical `run_schedule` behavior, AggTraceWriter never even
# constructed) and the same "requires --result-out" gate.
# ---------------------------------------------------------------------------


def test_parser_accepts_agg_trace_out(monkeypatch):
    from showdown_bot import cli

    captured = {}
    monkeypatch.setattr(
        sys, "argv",
        ["showdown-bot", "gauntlet", "--schedule", "s.yaml", "--result-out", "r.jsonl",
         "--agg-trace-out", "agg.jsonl.gz"],
    )
    monkeypatch.setattr(cli, "run_gauntlet", lambda args: captured.update(vars(args)))
    cli.main()
    assert captured["agg_trace_out"] == "agg.jsonl.gz"


def test_parser_defaults_agg_trace_out_to_empty(monkeypatch):
    from showdown_bot import cli

    captured = {}
    monkeypatch.setattr(sys, "argv", ["showdown-bot", "gauntlet", "--schedule", "s.yaml"])
    monkeypatch.setattr(cli, "run_gauntlet", lambda args: captured.update(vars(args)))
    cli.main()
    assert captured["agg_trace_out"] == ""


def test_schedule_agg_trace_requires_result_out(_sched_path, monkeypatch):
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)

    args = argparse.Namespace(
        schedule=str(_sched_path), result_out="", agg_trace_out="agg.jsonl",
    )
    with pytest.raises(SystemExit, match="--agg-trace-out requires --result-out"):
        cli.run_schedule(args)


def test_schedule_without_agg_trace_out_passes_none_to_run_local_gauntlet(_sched_path, monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    monkeypatch.delenv("SHOWDOWN_AGG_TRACE_OUT", raising=False)  # "off" must not depend on ambient env

    received = []

    async def _fake_run_local_gauntlet(**kwargs):
        received.append(kwargs)
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="", agg_trace_out="")
    cli.run_schedule(args)

    assert len(received) == 3  # one call per schedule row
    assert all(kw["agg_trace_writer"] is None for kw in received)
    assert all(kw["agg_trace_context"] is None for kw in received)
    # Independent of decision-trace-out, which is ALSO off here (not passed -> getattr default).
    assert all(kw["decision_trace_writer"] is None for kw in received)


def test_schedule_without_agg_trace_out_never_imports_agg_trace_writer(_sched_path, monkeypatch):
    """Extra belt-and-braces guard on the same golden: the agg-trace-off path must never even
    construct an `AggTraceWriter` (mirrors the decision-trace-level off golden). The
    SHOWDOWN_AGG_TRACE_OUT env alias is explicitly cleared so "off" is deterministic regardless
    of ambient env -- otherwise this gate could be only accidentally green."""
    import showdown_bot.client.gauntlet as gauntlet_mod
    import showdown_bot.research.aggregation_trace as agg_trace_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    monkeypatch.delenv("SHOWDOWN_AGG_TRACE_OUT", raising=False)

    def _boom(path):
        raise AssertionError("agg-trace-off path constructed an AggTraceWriter")

    monkeypatch.setattr(agg_trace_mod, "AggTraceWriter", _boom)

    async def _fake_run_local_gauntlet(**kwargs):
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="", agg_trace_out="")
    cli.run_schedule(args)  # must not raise


class _FakeAggWriter:
    def __init__(self, path):
        self.path = path
        self.finish_calls: list[str] = []

    def write(self, row):  # not exercised here -- no real battle/handle_request runs
        raise AssertionError("write() should not be called without a real battle")

    def finish_battle(self, battle_id):
        self.finish_calls.append(battle_id)
        return {"agg_trace_count": 3, "agg_trace_sha256": "b" * 64}


def test_schedule_with_agg_trace_out_threads_writer_and_context_per_row(_sched_path, tmp_path, monkeypatch):
    """On: ONE AggTraceWriter for the whole run, a distinct per-battle AggTraceContext, and
    finish_battle validated per battle. Deliberate scope boundary (Task 3, see cli.py's own
    comment at the call site): eval/result_jsonl.py's closed row schema is NOT extended in this
    slice, so -- unlike decision-trace's count/sha256 -- the agg-trace binding is validated but
    NOT merged into the --result-out row; the sidecar FILE is the source of truth for the
    Task 4/5 probe instead."""
    import showdown_bot.client.gauntlet as gauntlet_mod
    import showdown_bot.research.aggregation_trace as agg_trace_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "run2026")

    fake_writer = _FakeAggWriter(None)

    def _fake_writer_ctor(path):
        fake_writer.path = path
        return fake_writer

    monkeypatch.setattr(agg_trace_mod, "AggTraceWriter", _fake_writer_ctor)

    received = []

    async def _fake_run_local_gauntlet(**kwargs):
        received.append(kwargs)
        record = {
            "winner": "hero", "turns": 5, "end_reason": "normal",
            "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 100,
        }
        kwargs["on_battle_result"](record)
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    result_out = str(tmp_path / "results.jsonl")
    agg_out = str(tmp_path / "agg.jsonl")
    args = argparse.Namespace(
        schedule=str(_sched_path), result_out=result_out, agg_trace_out=agg_out,
    )
    cli.run_schedule(args)

    assert fake_writer.path == agg_out  # AggTraceWriter built exactly ONCE for the run

    assert len(received) == 3  # one call per schedule row
    assert all(kw["agg_trace_writer"] is fake_writer for kw in received)
    contexts = [kw["agg_trace_context"] for kw in received]
    assert all(c is not None for c in contexts)
    assert len({c.battle_id for c in contexts}) == 3
    assert {c.seed_index for c in contexts} == {0, 1, 2}
    assert all(c.our_side == "p1" for c in contexts)
    assert all(c.config_id == "heuristic" for c in contexts)
    assert all(c.format_id == "gen9vgc2025regi" for c in contexts)
    assert all(len(c.git_sha) for c in contexts)

    assert len(fake_writer.finish_calls) == 3
    assert set(fake_writer.finish_calls) == {c.battle_id for c in contexts}

    lines = [json.loads(line) for line in Path(result_out).read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3
    assert all("agg_trace_count" not in row and "agg_trace_sha256" not in row for row in lines)


def test_schedule_agg_trace_turns_on_via_env_var_alone(_sched_path, tmp_path, monkeypatch):
    """Kaggle reachability pin (2c-Slice-0b Task 5): the datagen kernel builds a HARDCODED argv
    (--schedule + --result-out only) and can inject per-run config ONLY via the EXTRA_ENV
    passthrough (tools/kaggle/kernel_payload.py), so a CLI-only --agg-trace-out flag would
    silently no-op there. This pins that SHOWDOWN_AGG_TRACE_OUT ALONE (no --agg-trace-out flag,
    agg_trace_out="") turns the AggTraceWriter ON in run_schedule and threads it into the hero
    exactly like the flag path."""
    import showdown_bot.client.gauntlet as gauntlet_mod
    import showdown_bot.research.aggregation_trace as agg_trace_mod
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "run2026")

    agg_out = str(tmp_path / "agg.jsonl")
    monkeypatch.setenv("SHOWDOWN_AGG_TRACE_OUT", agg_out)  # env alias, NOT the CLI flag

    fake_writer = _FakeAggWriter(None)

    def _fake_writer_ctor(path):
        fake_writer.path = path
        return fake_writer

    monkeypatch.setattr(agg_trace_mod, "AggTraceWriter", _fake_writer_ctor)

    received = []

    async def _fake_run_local_gauntlet(**kwargs):
        received.append(kwargs)
        record = {
            "winner": "hero", "turns": 5, "end_reason": "normal",
            "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 100,
        }
        kwargs["on_battle_result"](record)
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    result_out = str(tmp_path / "results.jsonl")
    args = argparse.Namespace(
        schedule=str(_sched_path), result_out=result_out, agg_trace_out="",  # flag EMPTY
    )
    cli.run_schedule(args)

    assert fake_writer.path == agg_out  # env alias drove the AggTraceWriter path
    assert len(received) == 3
    assert all(kw["agg_trace_writer"] is fake_writer for kw in received)  # threaded to every hero
    contexts = [kw["agg_trace_context"] for kw in received]
    assert all(c is not None for c in contexts)
    assert {c.seed_index for c in contexts} == {0, 1, 2}
    assert len(fake_writer.finish_calls) == 3


def test_schedule_agg_trace_env_var_still_requires_result_out(_sched_path, monkeypatch):
    """The env alias does NOT bypass the --result-out gate: the sidecar binds per battle, so a
    result row must exist. SHOWDOWN_AGG_TRACE_OUT set but --result-out empty -> same SystemExit
    as the flag path, raised before any battle."""
    from showdown_bot import cli

    _clean_seed_env(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    monkeypatch.setenv("SHOWDOWN_AGG_TRACE_OUT", "agg.jsonl")

    args = argparse.Namespace(
        schedule=str(_sched_path), result_out="", agg_trace_out="",
    )
    with pytest.raises(SystemExit, match="--agg-trace-out requires --result-out"):
        cli.run_schedule(args)

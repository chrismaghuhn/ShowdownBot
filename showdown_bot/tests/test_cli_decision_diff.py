"""candidate-vs-baseline-diff Task 4: `--decision-trace-out` CLI contract.

The flag threads an optional per-battle hero decision-capture sidecar through
`cli.run_schedule` -> `client.gauntlet.run_local_gauntlet` (hero-only, games=1),
binding a `decision_trace_count`/`decision_trace_sha256` pair into the matching
`--result-out` row. Off (the default, unset) must be byte-identical to every
prior `run_schedule` call: `decision_trace_writer`/`decision_trace_context`
reach `run_local_gauntlet` as `None`, and `DecisionTraceWriter` is never
constructed.

Same no-live-server technique as test_cli_run_schedule_export.py:
`run_local_gauntlet` is monkeypatched at the `showdown_bot.client.gauntlet`
module seam `cli.run_schedule` re-imports from on every call, so no
battle/server is ever started. `DecisionTraceWriter` is likewise monkeypatched
at the `showdown_bot.eval.decision_capture` module seam `cli.run_schedule`
locally imports from.
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
"""


@pytest.fixture
def _sched_path(tmp_path):
    p = tmp_path / "sched.yaml"
    p.write_text(_SCHEDULE_YAML, encoding="utf-8")
    return p


def _clean_env(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_DATASET_EXPORT", raising=False)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)


# ---------------------------------------------------------------------------
# Parser contract
# ---------------------------------------------------------------------------


def test_parser_accepts_decision_trace_out(monkeypatch):
    from showdown_bot import cli

    captured = {}
    monkeypatch.setattr(
        sys, "argv",
        ["showdown-bot", "gauntlet", "--schedule", "s.yaml", "--result-out", "r.jsonl",
         "--decision-trace-out", "trace.jsonl.gz"],
    )
    monkeypatch.setattr(cli, "run_gauntlet", lambda args: captured.update(vars(args)))
    cli.main()
    assert captured["decision_trace_out"] == "trace.jsonl.gz"


def test_parser_defaults_decision_trace_out_to_empty(monkeypatch):
    from showdown_bot import cli

    captured = {}
    monkeypatch.setattr(sys, "argv", ["showdown-bot", "gauntlet", "--schedule", "s.yaml"])
    monkeypatch.setattr(cli, "run_gauntlet", lambda args: captured.update(vars(args)))
    cli.main()
    assert captured["decision_trace_out"] == ""


# ---------------------------------------------------------------------------
# run_schedule wiring: off (default) -> None/None to every row, byte-identical.
# ---------------------------------------------------------------------------


def test_schedule_without_trace_out_passes_none_to_run_local_gauntlet(_sched_path, monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet_mod
    from showdown_bot import cli

    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    _clean_env(monkeypatch)

    received = []

    async def _fake_run_local_gauntlet(**kwargs):
        received.append(kwargs)
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="", decision_trace_out="")
    cli.run_schedule(args)

    assert len(received) == 2  # one call per schedule row
    assert all(kw["decision_trace_writer"] is None for kw in received)
    assert all(kw["decision_trace_context"] is None for kw in received)


def test_schedule_without_trace_out_never_imports_decision_trace_writer(_sched_path, monkeypatch):
    """Extra belt-and-braces guard on the same golden: the trace-off path must never even
    construct a `DecisionTraceWriter` (mirrors the gauntlet-level capture-off golden)."""
    import showdown_bot.client.gauntlet as gauntlet_mod
    import showdown_bot.eval.decision_capture as capture_mod
    from showdown_bot import cli

    monkeypatch.delenv("SHOWDOWN_BATTLE_SEED_BASE", raising=False)
    _clean_env(monkeypatch)

    def _boom(path):
        raise AssertionError("trace-off path constructed a DecisionTraceWriter")

    monkeypatch.setattr(capture_mod, "DecisionTraceWriter", _boom)

    async def _fake_run_local_gauntlet(**kwargs):
        return gauntlet_mod.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    args = argparse.Namespace(schedule=str(_sched_path), result_out="", decision_trace_out="")
    cli.run_schedule(args)  # must not raise


# ---------------------------------------------------------------------------
# run_schedule wiring: on -> one writer for the whole run, a distinct
# per-battle context, and the binding lands in the --result-out row.
# ---------------------------------------------------------------------------


class _FakeTraceWriter:
    def __init__(self, path):
        self.path = path
        self.finish_calls: list[str] = []

    def write(self, row):  # not exercised here -- no real battle/handle_request runs
        raise AssertionError("write() should not be called without a real battle")

    def finish_battle(self, battle_id):
        self.finish_calls.append(battle_id)
        return {"decision_trace_count": 3, "decision_trace_sha256": "a" * 64}


def test_schedule_with_trace_out_threads_writer_and_context_per_row(_sched_path, tmp_path, monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet_mod
    import showdown_bot.eval.decision_capture as capture_mod
    from showdown_bot import cli

    _clean_env(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "run2026")

    fake_writer = _FakeTraceWriter(None)
    build_calls = []

    def _fake_writer_ctor(path):
        build_calls.append(path)
        fake_writer.path = path
        return fake_writer

    monkeypatch.setattr(capture_mod, "DecisionTraceWriter", _fake_writer_ctor)

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
    trace_out = str(tmp_path / "trace.jsonl")
    args = argparse.Namespace(
        schedule=str(_sched_path), result_out=result_out, decision_trace_out=trace_out,
    )
    cli.run_schedule(args)

    assert build_calls == [trace_out]  # DecisionTraceWriter built exactly ONCE for the run
    assert len(received) == 2  # one call per schedule row

    # Every row's hero client borrows the SAME writer instance...
    assert all(kw["decision_trace_writer"] is fake_writer for kw in received)
    # ...but a battle-specific context (distinct battle_id per seed_index).
    contexts = [kw["decision_trace_context"] for kw in received]
    assert all(c is not None for c in contexts)
    assert len({c.battle_id for c in contexts}) == 2
    assert {c.seed_index for c in contexts} == {0, 1}
    assert all(c.config_id == "heuristic" for c in contexts)
    assert all(c.format_id == "gen9vgc2025regi" for c in contexts)
    assert all(c.schedule_hash for c in contexts)
    assert all(len(c.git_sha) for c in contexts)

    assert len(fake_writer.finish_calls) == 2
    assert set(fake_writer.finish_calls) == {c.battle_id for c in contexts}

    lines = [json.loads(line) for line in Path(result_out).read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert all(row["decision_trace_count"] == 3 for row in lines)
    assert all(row["decision_trace_sha256"] == "a" * 64 for row in lines)


def test_schedule_with_trace_out_omits_binding_when_no_battle_ran(_sched_path, tmp_path, monkeypatch):
    """games==0 (no on_battle_result fired -- e.g. a battle that never completed) writes no
    row at all, so there's nothing to bind; T2-CC-4's row-count check catches this."""
    import showdown_bot.client.gauntlet as gauntlet_mod
    import showdown_bot.eval.decision_capture as capture_mod
    from showdown_bot import cli

    _clean_env(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "run2026")

    monkeypatch.setattr(capture_mod, "DecisionTraceWriter", lambda path: _FakeTraceWriter(path))

    async def _fake_run_local_gauntlet(**kwargs):
        return gauntlet_mod.GauntletStats(games=0)  # on_battle_result never fired

    monkeypatch.setattr(gauntlet_mod, "run_local_gauntlet", _fake_run_local_gauntlet)

    result_out = str(tmp_path / "results.jsonl")
    trace_out = str(tmp_path / "trace.jsonl")
    args = argparse.Namespace(
        schedule=str(_sched_path), result_out=result_out, decision_trace_out=trace_out,
    )
    with pytest.raises(SystemExit, match="T2: wrote 0 rows"):
        cli.run_schedule(args)

"""Code-review findings 4 & 5: an executable, provenance-locked I8-D entry point.

Before this the I8-D runner was a library function with no CLI, and its provenance
(``git_sha``/``config_hash``/``calc_backend``/agent) was caller-supplied. The ``i8d-live-gate``
command DERIVES provenance from the real repo/env fail-closed (``resolve_i8d_provenance``), builds
the schedule from the panel, and drives the hardened runner -- so a run is authorizable through one
locked command rather than an unverified library call.

No server/battles: ``resolve_i8d_provenance``'s repo/env sources, ``build_i8d_live_schedule`` and
``run_i8d_live_gate`` are stubbed at the module seam.
"""
from __future__ import annotations

import argparse

import pytest


# ---- finding 5: provenance is DERIVED from the real repo/env and fail-closed ------------------

def test_resolve_provenance_derives_from_repo_and_env(monkeypatch):
    import showdown_bot.eval.config_env as cenv
    import showdown_bot.eval.i8d_runner as r
    import showdown_bot.eval.result_jsonl as rj
    import showdown_bot.learning.provenance as prov

    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("a1b2c3", False))
    monkeypatch.setattr(cenv, "behavior_env", lambda: {"X": "1"})
    monkeypatch.setattr(cenv, "effective_config_manifest", lambda **kw: {"agent": kw["agent"]})
    monkeypatch.setattr(rj, "make_config_hash", lambda m: "cfg-derived")
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "persistent")

    assert r.resolve_i8d_provenance() == {
        "git_sha": "a1b2c3", "config_hash": "cfg-derived",
        "calc_backend": "persistent", "hero_agent": "heuristic"}


def test_resolve_provenance_refuses_a_dirty_tree(monkeypatch):
    import showdown_bot.eval.i8d_runner as r
    import showdown_bot.learning.provenance as prov
    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("a1b2c3", True))
    with pytest.raises(r.I8DRunError, match="working tree is dirty"):
        r.resolve_i8d_provenance()


def test_resolve_provenance_refuses_an_unknown_git_sha(monkeypatch):
    import showdown_bot.eval.i8d_runner as r
    import showdown_bot.learning.provenance as prov
    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("unknown", False))
    with pytest.raises(r.I8DRunError, match="cannot resolve a git sha"):
        r.resolve_i8d_provenance()


def test_resolve_provenance_refuses_an_unknown_calc_backend(monkeypatch):
    import showdown_bot.eval.config_env as cenv
    import showdown_bot.eval.i8d_runner as r
    import showdown_bot.eval.result_jsonl as rj
    import showdown_bot.learning.provenance as prov
    monkeypatch.setattr(prov, "git_sha_and_dirty", lambda: ("a1b2c3", False))
    monkeypatch.setattr(cenv, "behavior_env", lambda: {})
    monkeypatch.setattr(cenv, "effective_config_manifest", lambda **kw: {})
    monkeypatch.setattr(rj, "make_config_hash", lambda m: "c")
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "quantum")
    with pytest.raises(r.I8DRunError, match="unknown SHOWDOWN_CALC_BACKEND"):
        r.resolve_i8d_provenance()


# ---- finding 4: the command wires derived provenance into the hardened runner -----------------

class _Sched:
    schedule_hash = "sched-xyz"
    rows = ()


def _install_cli_stubs(monkeypatch, captured):
    import showdown_bot.eval.i8d_runner as r

    def _fake_build(panel, *, n_battles, teams_root):
        captured["panel"] = panel
        captured["n_battles"] = n_battles
        captured["teams_root"] = teams_root
        return _Sched()

    def _fake_run(**kw):
        captured["run_kwargs"] = kw
        return {"verdict": "INCONCLUSIVE — exposure floor not met", "active_valid_decisions": 0,
                "distinct_active_battles": 0, "battles_played": 0, "p95_ms": None,
                "stop_reason": "schedule_exhausted"}

    monkeypatch.setattr(r, "resolve_i8d_provenance",
                        lambda **kw: {"git_sha": "sha9", "config_hash": "cfg9",
                                      "calc_backend": "oneshot", "hero_agent": "heuristic"})
    monkeypatch.setattr(r, "build_i8d_live_schedule", _fake_build)
    monkeypatch.setattr(r, "run_i8d_live_gate", _fake_run)


def test_command_derives_provenance_and_reaches_the_runner(tmp_path, monkeypatch):
    from showdown_bot import cli
    captured: dict = {}
    _install_cli_stubs(monkeypatch, captured)
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(tmp_path / "seed.log"))
    cli.run_i8d_gate(argparse.Namespace(
        panel="config/eval/panels/panel_champions_v0.yaml",
        out_dir=str(tmp_path / "out"), teams_root="."))
    kw = captured["run_kwargs"]
    # DERIVED provenance, not caller labels
    assert (kw["git_sha"], kw["config_hash"], kw["calc_backend"], kw["hero_agent"]) == (
        "sha9", "cfg9", "oneshot", "heuristic")
    assert kw["expected_battles"] == 200                        # locked to the D-2 cap, not caller-set
    assert kw["seed_log_path"] == str(tmp_path / "seed.log")    # from the server's env
    assert kw["out_dir"] == str(tmp_path / "out")              # the atomic-publish output directory
    assert kw["schedule"].schedule_hash == "sched-xyz"          # BUILT from the panel, not passed in
    assert captured["panel"] == "config/eval/panels/panel_champions_v0.yaml"
    assert captured["n_battles"] == 200


def test_command_requires_panel_and_out_dir(tmp_path, monkeypatch):
    from showdown_bot import cli
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(tmp_path / "seed.log"))
    with pytest.raises(SystemExit, match="requires --panel and --out-dir"):
        cli.run_i8d_gate(argparse.Namespace(panel="", out_dir="", teams_root="."))


def test_command_requires_the_server_seed_log(tmp_path, monkeypatch):
    from showdown_bot import cli
    captured: dict = {}
    _install_cli_stubs(monkeypatch, captured)
    monkeypatch.delenv("SHOWDOWN_EVAL_SEED_LOG", raising=False)
    with pytest.raises(SystemExit, match="requires SHOWDOWN_EVAL_SEED_LOG"):
        cli.run_i8d_gate(argparse.Namespace(
            panel="p.yaml", out_dir=str(tmp_path / "out"), teams_root="."))
    assert "run_kwargs" not in captured   # fails before building or driving anything

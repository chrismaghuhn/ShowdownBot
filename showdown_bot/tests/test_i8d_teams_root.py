"""The I8-D team-path wiring fix (post-restart-abort root cause).

`run_local_gauntlet` loads battle team files relative to the process CWD, but the i8d-live-gate
command runs from the repo root (so the repo-root-relative panel path resolves) while the team files
live under `showdown_bot/teams/`. `--teams-root` was only used to HASH the teams
(`verify_i8d_panel_and_teams`), not to LOAD them at battle time — so the gauntlet got missing files,
`_resolve_side_teams` silently degraded them to EMPTY packed teams, the server rejected the
empty-team challenge, no battle was ever created, and the gate only timed out (both aborts).

The fix threads `teams_root` into `run_i8d_live_gate` and, immediately before `run_local_gauntlet`,
resolves the hero/opponent paths to ABSOLUTE against that root and proves each loads a NON-EMPTY
packed team — failing closed before any server/battle otherwise. The schedule's stored relative
paths and `schedule_hash` are untouched, and `run_local_gauntlet` is not changed (other callers,
e.g. `run_schedule`, are unaffected). No server, no battle.
"""
from __future__ import annotations

import inspect
import os

import pytest

from showdown_bot.eval.panel import Panel, PanelTeam
from showdown_bot.eval.i8d_schedule import I8D_HERO_TEAM, I8D_SEED_BASE, build_i8d_schedule
from showdown_bot.eval.i8d_runner import I8DRunError, run_i8d_live_gate
from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.team.pack import load_packed_team


def _panel() -> Panel:
    def t(tid, arch):
        return PanelTeam(team_id=tid, team_path=f"teams/panel_champions_v0/{tid}.txt",
                         archetype=arch, team_hash=f"hash_{tid}")
    return Panel(version="champions_v0", policies=("heuristic", "max_damage"),
                 dev_teams=(t("goodstuff", "balance_goodstuff"),
                            t("tailwind_offense", "tailwind_offense"), t("trick_room", "trick_room")),
                 heldout_teams=(t("rain_offense", "weather_rain"), t("disruption", "bulky_disruption")),
                 panel_hash="aac1ea30446fde88")


def _canon(n):
    return build_i8d_schedule(_panel(), n_battles=n, teams_root=".")


def _make_team(txt_path, packed="stub-packed-team"):
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("paste\n", encoding="utf-8")
    txt_path.with_suffix(".packed").write_text(packed, encoding="utf-8")


def _fixture_teams(tmp_path):
    root = tmp_path / "teamsroot"
    for rel in (I8D_HERO_TEAM, "teams/panel_champions_v0/goodstuff.txt",
                "teams/panel_champions_v0/tailwind_offense.txt",
                "teams/panel_champions_v0/trick_room.txt"):
        _make_team(root / rel)
    return str(root)


def _capture_stub(monkeypatch, captured, seed_log):
    """Capture the team paths run_local_gauntlet receives + write the Channel-A seed line (so the
    post-run seed verification passes) + report one completed game."""
    import showdown_bot.client.gauntlet as g
    counter = {"i": 0}

    async def _fake(**kw):
        captured["team_path"] = kw["team_path"]
        captured["opp_team_path"] = kw["opp_team_path"]
        i = counter["i"]; counter["i"] += 1
        with open(seed_log, "a", encoding="utf-8", newline="") as fh:
            import json
            fh.write(json.dumps({"battle_index": i, "seed_base": I8D_SEED_BASE,
                                 "seed": derive_battle_seed(I8D_SEED_BASE, i)}) + "\n")
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)


def test_gate_passes_absolute_nonempty_team_paths_to_the_gauntlet(tmp_path, monkeypatch):
    # GREEN after the fix; RED before it (the old code passed the RELATIVE row path straight through).
    teams_root = _fixture_teams(tmp_path)
    seed_log = str(tmp_path / "seed.log")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)
    captured: dict = {}
    _capture_stub(monkeypatch, captured, seed_log)
    run_i8d_live_gate(schedule=_canon(6), out_dir=str(tmp_path / "out"), seed_log_path=seed_log,
                      config_hash="c", git_sha="d", expected_battles=6, teams_root=teams_root)
    hp, op = captured["team_path"], captured["opp_team_path"]
    assert os.path.isabs(hp) and os.path.isabs(op)                     # ABSOLUTE, not the relative row path
    assert load_packed_team(hp) and load_packed_team(op)              # both packed teams NON-EMPTY
    assert os.path.realpath(hp).startswith(os.path.realpath(teams_root))   # resolved under teams_root


def test_wrong_or_missing_teams_root_fails_closed_before_any_battle(tmp_path, monkeypatch):
    called = {"n": 0}
    import showdown_bot.client.gauntlet as g

    async def _fake(**kw):
        called["n"] += 1
        return g.GauntletStats(games=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", I8D_SEED_BASE)
    empty_root = str(tmp_path / "empty"); os.makedirs(empty_root)     # no team files under it
    with pytest.raises(I8DRunError, match="not found under teams_root"):
        run_i8d_live_gate(schedule=_canon(6), out_dir=str(tmp_path / "out"),
                          seed_log_path=str(tmp_path / "seed.log"), config_hash="c", git_sha="d",
                          expected_battles=6, teams_root=empty_root)
    assert called["n"] == 0                                            # failed BEFORE the server/battle
    assert not (tmp_path / "out").exists()                            # nothing published


def test_schedule_identity_and_relative_paths_are_untouched(tmp_path):
    s = _canon(6)
    assert s.schedule_hash == build_i8d_schedule(_panel(), n_battles=6, teams_root=".").schedule_hash
    for r in s.rows:
        assert r.hero_team_path == "teams/fixed_champions_v0.txt"
        assert not os.path.isabs(r.hero_team_path) and not os.path.isabs(r.opp_team_path)


def test_run_local_gauntlet_is_not_changed_by_the_fix():
    # The fix lives entirely in run_i8d_live_gate; run_local_gauntlet (and run_schedule, which calls
    # it with raw relative paths + its own CWD contract) is untouched.
    from showdown_bot.client.gauntlet import run_local_gauntlet
    params = inspect.signature(run_local_gauntlet).parameters
    assert "team_path" in params and "opp_team_path" in params
    assert "teams_root" not in params


def test_root_cause_geometry_repo_root_misses_teams_root_resolves(tmp_path):
    # The exact geometry: panel at <root>/config/…, teams at <root>/showdown_bot/teams/…. A team
    # path resolved from the panel/repo root MISSES; only teams_root=showdown_bot resolves it —
    # which is what --teams-root now bridges at battle time.
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)                             # panel root; no teams/ here
    _make_team(repo / "showdown_bot" / I8D_HERO_TEAM)                 # teams live under showdown_bot/
    with pytest.raises(FileNotFoundError):
        load_packed_team(str(repo / I8D_HERO_TEAM))                   # repo-root-relative: MISS
    assert load_packed_team(str(repo / "showdown_bot" / I8D_HERO_TEAM))   # teams_root-relative: non-empty

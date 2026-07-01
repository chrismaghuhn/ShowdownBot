"""T3d panel-driven schedule generator (dev/held-out gated, reproducible-only default)."""
from __future__ import annotations

import pytest

from showdown_bot.eval.panel import Panel, PanelTeam
from showdown_bot.eval.panel_schedule import (
    PanelScheduleError,
    generate_dev_schedule,
    generate_heldout_schedule,
    write_schedule_yaml,
)
from showdown_bot.eval.schedule import load_schedule


def _panel():
    dev = (
        PanelTeam("d1", "teams/panel_v001/trickroom_dev.txt", "trick_room", "h1"),
        PanelTeam("d2", "teams/panel_v001/sun_dev.txt", "sun", "h2"),
    )
    held = (PanelTeam("hd1", "teams/panel_v001/balance_held.txt", "balance", "h3"),)
    return Panel(
        version="v001",
        policies=("heuristic", "max_damage", "random"),
        dev_teams=dev, heldout_teams=held, panel_hash="pan999",
    )


def test_dev_default_reproducible_only():
    sched = generate_dev_schedule(_panel())
    # 2 dev teams x 2 reproducible policies (random excluded) = 4 rows
    assert len(sched.rows) == 4
    assert {r.opp_policy for r in sched.rows} == {"heuristic", "max_damage"}
    assert [r.seed_index for r in sched.rows] == [0, 1, 2, 3]  # contiguous from 0
    assert all(r.format_id == "gen9vgc2025regi" for r in sched.rows)
    assert sched.panel_hash == "pan999"
    assert sched.reproducible is True


def test_dev_uses_only_dev_teams():
    sched = generate_dev_schedule(_panel())
    assert {r.opp_team_path for r in sched.rows} == {
        "teams/panel_v001/trickroom_dev.txt", "teams/panel_v001/sun_dev.txt",
    }


def test_dev_never_contains_heldout_team():
    sched = generate_dev_schedule(_panel())
    assert "teams/panel_v001/balance_held.txt" not in {r.opp_team_path for r in sched.rows}


def test_random_excluded_by_default_and_gated():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["random"])  # needs allow_nonreproducible
    sched = generate_dev_schedule(_panel(), policies=["random"], allow_nonreproducible=True)
    assert {r.opp_policy for r in sched.rows} == {"random"}
    assert sched.reproducible is False  # marked non-reproducible


def test_heldout_requires_confirm():
    with pytest.raises(PanelScheduleError):
        generate_heldout_schedule(_panel())  # confirm_heldout defaults False
    sched = generate_heldout_schedule(_panel(), confirm_heldout=True)
    assert {r.opp_team_path for r in sched.rows} == {"teams/panel_v001/balance_held.txt"}


def test_seeds_per_cell():
    sched = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=3)
    assert len(sched.rows) == 2 * 1 * 3  # 2 teams x 1 policy x 3 seeds
    assert [r.seed_index for r in sched.rows] == [0, 1, 2, 3, 4, 5]


def test_write_yaml_round_trips(tmp_path):
    sched = generate_dev_schedule(_panel())
    out = tmp_path / "dev.yaml"
    write_schedule_yaml(sched, str(out))
    reloaded = load_schedule(str(out))
    assert reloaded.schedule_hash == sched.schedule_hash  # stable
    assert reloaded.panel_hash == sched.panel_hash        # preserved
    assert [r.format_id for r in reloaded.rows] == [r.format_id for r in sched.rows]

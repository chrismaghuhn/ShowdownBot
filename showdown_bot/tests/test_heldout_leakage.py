"""T6 Task 2: leakage drift test (spec sec 1 R4).

Held-out identifiers (team_id, team_path, team_hash of every panel v001 held-out team --
read via `load_panel`, never hardcoded) must never appear in a committed schedule row that
is dev-labeled or unlabeled (`panel_split in ("dev", None)`). A schedule whose rows are
ALL heldout-labeled is exempt (that's the point of a held-out schedule, e.g. T6's own
`t6_heldout_v001.yaml` arriving in a later task).

The check itself is factored into `assert_schedule_file_has_no_heldout_leakage` so both
the repo-wide scan (real committed files) and a synthetic negative case (a constructed
leaky dev schedule) exercise the identical logic -- proving the test is dynamic: a future
leaky schedule fails it, a future all-heldout schedule passes it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.panel_schedule import write_schedule_yaml
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash, load_schedule

_REPO = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_PANEL = _REPO / "config" / "eval" / "panels" / "panel_v001.yaml"
_SCHEDULES_DIR = _REPO / "config" / "eval" / "schedules"
_TEAMS_ROOT = str(_REPO / "showdown_bot")


def _heldout_identifiers(panel) -> set[str]:
    """team_id, team_path, and content team_hash of every held-out team -- read from the
    panel, never hardcoded (a v002 panel with different held-out teams must not require
    editing this test)."""
    ids: set[str] = set()
    for t in panel.heldout_teams:
        ids.add(t.team_id)
        ids.add(t.team_path)
        ids.add(t.team_hash)
    return ids


def assert_schedule_file_has_no_heldout_leakage(schedule_path, heldout_ids: set[str]) -> None:
    """Assert no row of the schedule at `schedule_path` leaks a held-out identifier,
    UNLESS every row in the schedule is heldout-labeled (an intentional held-out
    schedule is exempt -- it is SUPPOSED to reference held-out teams).

    Checks `opp_team_path` and `opp_team_hash` per row against `heldout_ids`.
    """
    schedule = load_schedule(str(schedule_path))
    all_heldout = all(r.panel_split == "heldout" for r in schedule.rows)
    if all_heldout:
        return
    for row in schedule.rows:
        if row.panel_split not in ("dev", None):
            continue
        assert row.opp_team_path not in heldout_ids, (
            f"{schedule_path}: held-out identifier leaked via opp_team_path "
            f"{row.opp_team_path!r} in a {row.panel_split!r}-labeled row"
        )
        assert row.opp_team_hash not in heldout_ids, (
            f"{schedule_path}: held-out identifier leaked via opp_team_hash "
            f"{row.opp_team_hash!r} in a {row.panel_split!r}-labeled row"
        )


def _write_single_row_schedule(tmp_path, name, *, team_path, team_hash, panel_split):
    row = ScheduleRow(
        format_id="gen9vgc2025regi", hero_team_path="teams/fixed_team.txt",
        opp_policy="heuristic", opp_team_path=team_path, seed_index=0,
        hero_team_hash=None, opp_team_hash=team_hash, panel_split=panel_split,
    )
    sched = Schedule(
        version="v001", rows=(row,),
        schedule_hash=compute_schedule_hash("v001", (row,)), panel_hash="deadbeef",
    )
    out = tmp_path / name
    write_schedule_yaml(sched, str(out))
    return out


# --- repo-wide scan: every committed schedule, held-out identifiers from the real panel ---

def test_committed_schedules_have_no_heldout_leakage():
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    heldout_ids = _heldout_identifiers(panel)
    schedule_files = sorted(_SCHEDULES_DIR.glob("*.yaml"))
    assert schedule_files, "expected at least one committed schedule to scan"
    for path in schedule_files:
        assert_schedule_file_has_no_heldout_leakage(path, heldout_ids)


# --- synthetic negative cases: prove the check helper actually catches a leak -------------

def test_leakage_check_catches_synthetic_leaky_dev_schedule(tmp_path):
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    heldout_ids = _heldout_identifiers(panel)
    leaky_team = panel.heldout_teams[0]
    path = _write_single_row_schedule(
        tmp_path, "leaky_dev.yaml",
        team_path=leaky_team.team_path, team_hash=leaky_team.team_hash, panel_split="dev",
    )
    with pytest.raises(AssertionError):
        assert_schedule_file_has_no_heldout_leakage(path, heldout_ids)


def test_leakage_check_catches_synthetic_leaky_unlabeled_schedule(tmp_path):
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    heldout_ids = _heldout_identifiers(panel)
    leaky_team = panel.heldout_teams[1]
    path = _write_single_row_schedule(
        tmp_path, "leaky_unlabeled.yaml",
        team_path=leaky_team.team_path, team_hash=leaky_team.team_hash, panel_split=None,
    )
    with pytest.raises(AssertionError):
        assert_schedule_file_has_no_heldout_leakage(path, heldout_ids)


def test_leakage_check_exempts_all_heldout_labeled_schedule(tmp_path):
    # A future all-heldout schedule (like T6's own) references held-out teams by design --
    # the check must NOT flag it, proving the exemption branch works, not just the fail path.
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    heldout_ids = _heldout_identifiers(panel)
    heldout_team = panel.heldout_teams[0]
    path = _write_single_row_schedule(
        tmp_path, "all_heldout.yaml",
        team_path=heldout_team.team_path, team_hash=heldout_team.team_hash,
        panel_split="heldout",
    )
    assert_schedule_file_has_no_heldout_leakage(path, heldout_ids)  # must not raise

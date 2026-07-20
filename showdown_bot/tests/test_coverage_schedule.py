"""Task 4: the fixed coverage battle schedule -- 8 manifest matchups (4 cells x 2 policies) cycled
over exactly 200 battles = 25 per matchup, contiguous seed_index 0..199, hash-stable. Generation
only; no server, no battle. verify_coverage_schedule re-locks it and verify_coverage_panel_and_teams
re-hashes the panel + teams from disk.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.schedule import Schedule, compute_schedule_hash
from showdown_bot.eval.coverage_schedule import (
    COVERAGE_MAX_BATTLES,
    COVERAGE_PANEL_PATH,
    CoverageScheduleError,
    build_coverage_schedule,
    load_coverage_manifest,
    verify_coverage_panel_and_teams,
    verify_coverage_schedule,
)

_REPO = Path(__file__).resolve().parents[2]
_TEAMS_ROOT = str(_REPO / "showdown_bot")


def _panel():
    return load_panel(str(_REPO / COVERAGE_PANEL_PATH), teams_root=_TEAMS_ROOT)


def _schedule():
    return build_coverage_schedule(_panel(), load_coverage_manifest(), teams_root=_TEAMS_ROOT)


def test_the_coverage_panel_loads_with_the_fixed_dev_heldout_split():
    panel = _panel()
    assert tuple(t.team_id for t in panel.dev_teams) == ("cov_foe_slot0", "cov_foe_slot1")
    assert tuple(t.team_id for t in panel.heldout_teams) == ("cov_foe_both", "cov_foe_tie")
    assert tuple(panel.policies) == ("heuristic", "max_damage")


def test_build_coverage_schedule_targets_all_four_cells():
    sched = _schedule()
    assert len(sched.rows) == COVERAGE_MAX_BATTLES
    manifest = load_coverage_manifest()
    assert {m.target_cell for m in manifest.matchups} == {"slot0", "slot1", "both_foe_slots", "order_tie"}
    # every scheduled opp team is one of the four coverage foe teams
    opp_paths = {r.opp_team_path for r in sched.rows}
    assert len(opp_paths) == 4


def test_the_200_battle_composition_is_frozen_25_per_matchup():
    sched = _schedule()
    verify_coverage_schedule(sched)
    assert len(sched.rows) == 200
    counts = Counter((r.opp_team_path, r.opp_policy) for r in sched.rows)
    assert len(counts) == 8 and set(counts.values()) == {25}
    assert [r.seed_index for r in sched.rows] == list(range(200))
    # a truncated / reshaped schedule is rejected
    trunc_rows = sched.rows[:100]
    trunc = Schedule(version=sched.version, rows=trunc_rows,
                     schedule_hash=compute_schedule_hash(sched.version, trunc_rows),
                     panel_hash=sched.panel_hash)
    with pytest.raises(CoverageScheduleError):
        verify_coverage_schedule(trunc)


def test_verify_coverage_schedule_recomputes_the_hash():
    sched = _schedule()
    forged = Schedule(version=sched.version, rows=sched.rows,
                      schedule_hash="0" * 16, panel_hash=sched.panel_hash)
    with pytest.raises(CoverageScheduleError):
        verify_coverage_schedule(forged)


def test_verify_coverage_panel_and_teams_rehashes_from_disk():
    sched = _schedule()
    verify_coverage_panel_and_teams(sched, teams_root=_TEAMS_ROOT)
    with pytest.raises(CoverageScheduleError):
        verify_coverage_panel_and_teams(sched, teams_root=_TEAMS_ROOT, expected_panel_hash="0" * 16)

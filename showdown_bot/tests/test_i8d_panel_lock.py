"""Re-review blocker 2: bind the panel + team CONTENTS to the run identity.

``schedule_hash`` covers only team PATHS / policies / indices, so different team CONTENTS under the
same paths would share a verdict identity. ``verify_i8d_panel_and_teams`` closes that: the
content-derived ``panel_hash`` must equal the frozen champions value, and every distinct team file
is re-read and re-hashed against the schedule's recorded hash (a TOCTOU guard before battle 1). No
server, no battle -- real team fixture files on disk.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from showdown_bot.eval.panel import team_content_hash
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash
from showdown_bot.eval.i8d_schedule import (
    I8D_EXPECTED_PANEL_HASH,
    I8D_FORMAT,
    I8D_HERO_TEAM,
    I8DScheduleError,
    verify_i8d_panel_and_teams,
)

_GOODSTUFF = "teams/panel_champions_v0/goodstuff.txt"


def _write_team(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    p.with_suffix(".packed").write_text(content + "|packed", encoding="utf-8")


def _sched(tmp_path, *, panel_hash, hero="HERO-v0", goodstuff="GS-v0"):
    _write_team(tmp_path, I8D_HERO_TEAM, hero)
    _write_team(tmp_path, _GOODSTUFF, goodstuff)
    root = str(tmp_path)
    hero_h = team_content_hash(root, I8D_HERO_TEAM)
    gs_h = team_content_hash(root, _GOODSTUFF)
    rows = tuple(
        ScheduleRow(format_id=I8D_FORMAT, hero_team_path=I8D_HERO_TEAM,
                    opp_policy=pol, opp_team_path=_GOODSTUFF, seed_index=i,
                    hero_team_hash=hero_h, opp_team_hash=gs_h, panel_split="dev")
        for i, pol in enumerate(("heuristic", "max_damage"))
    )
    return Schedule(version="champions_v0", rows=rows,
                    schedule_hash=compute_schedule_hash("champions_v0", rows), panel_hash=panel_hash)


def test_the_default_expected_hash_is_the_frozen_champions_value():
    assert I8D_EXPECTED_PANEL_HASH == "aac1ea30446fde88"


def test_matching_panel_hash_and_unchanged_team_files_verify(tmp_path):
    s = _sched(tmp_path, panel_hash="PH-approved")
    verify_i8d_panel_and_teams(s, teams_root=str(tmp_path), expected_panel_hash="PH-approved")


def test_a_wrong_panel_hash_is_rejected(tmp_path):
    # Different team CONTENTS -> a different content-derived panel_hash -> refused even though the
    # paths, policies and indices (and thus schedule_hash) are unchanged.
    s = _sched(tmp_path, panel_hash="PH-different")
    with pytest.raises(I8DScheduleError, match="panel_hash"):
        verify_i8d_panel_and_teams(s, teams_root=str(tmp_path), expected_panel_hash="PH-approved")


def test_a_team_file_changed_since_build_is_rejected(tmp_path):
    s = _sched(tmp_path, panel_hash="PH-approved")
    _write_team(tmp_path, _GOODSTUFF, "GS-TAMPERED")   # content changed after the schedule recorded it
    with pytest.raises(I8DScheduleError, match="the schedule's recorded"):
        verify_i8d_panel_and_teams(s, teams_root=str(tmp_path), expected_panel_hash="PH-approved")


def test_a_missing_recorded_team_hash_is_rejected(tmp_path):
    s = _sched(tmp_path, panel_hash="PH-approved")
    rows = list(s.rows)
    rows[0] = dataclasses.replace(rows[0], opp_team_hash=None)   # a provenance gap can't bind contents
    s2 = Schedule(version=s.version, rows=tuple(rows),
                  schedule_hash=s.schedule_hash, panel_hash=s.panel_hash)
    with pytest.raises(I8DScheduleError, match="no recorded content hash"):
        verify_i8d_panel_and_teams(s2, teams_root=str(tmp_path), expected_panel_hash="PH-approved")

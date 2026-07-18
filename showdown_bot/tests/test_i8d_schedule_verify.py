"""Code-review finding 3: the fixed I8-D schedule must be RE-LOCKED at the execution point.

A runner must never trust a caller's ``Schedule`` object or its self-reported ``schedule_hash``:
a truncated or replaced schedule would silently run different battles under the approved
identity. ``verify_i8d_schedule`` re-checks the full structure -- exact count, contiguous
``seed_index`` 0..N-1, the six matchups in the fixed cyclic order, the dev split, the bound format
and hero team, and the three dev teams -- AND recomputes ``compute_schedule_hash`` rather than
trusting the stored one. Generation only; no server, no battle.
"""
from __future__ import annotations

import dataclasses

import pytest

from showdown_bot.eval.panel import Panel, PanelTeam
from showdown_bot.eval.schedule import Schedule, compute_schedule_hash
from showdown_bot.eval.i8d_schedule import (
    I8DScheduleError,
    build_i8d_schedule,
    verify_i8d_schedule,
)


def _panel() -> Panel:
    def t(tid, arch):
        return PanelTeam(team_id=tid, team_path=f"teams/panel_champions_v0/{tid}.txt",
                         archetype=arch, team_hash=f"hash_{tid}")
    return Panel(
        version="champions_v0", policies=("heuristic", "max_damage"),
        dev_teams=(t("goodstuff", "balance_goodstuff"),
                   t("tailwind_offense", "tailwind_offense"),
                   t("trick_room", "trick_room")),
        heldout_teams=(t("rain_offense", "weather_rain"), t("disruption", "bulky_disruption")),
        panel_hash="aac1ea30446fde88")


def _canonical(n=200):
    return build_i8d_schedule(_panel(), n_battles=n, teams_root=".")


def _rehash(rows, version="champions_v0"):
    """A schedule whose stored hash HONESTLY matches its (mutated) rows -- so a rejection proves
    the STRUCTURE check fired, not merely a hash mismatch."""
    rows = tuple(rows)
    return Schedule(version=version, rows=rows,
                    schedule_hash=compute_schedule_hash(version, rows), panel_hash="x")


def test_the_canonical_200_row_schedule_verifies():
    verify_i8d_schedule(_canonical(200))   # no raise


def test_a_short_or_replaced_schedule_is_rejected_on_count():
    short = _canonical(24)
    with pytest.raises(I8DScheduleError, match="exactly 200 rows"):
        verify_i8d_schedule(short)                     # default expected_battles = 200 (the real gate)
    verify_i8d_schedule(short, expected_battles=24)    # ...but is otherwise canonical


def test_noncontiguous_seed_index_is_rejected():
    rows = list(_canonical(24).rows)
    rows[5] = dataclasses.replace(rows[5], seed_index=999)
    with pytest.raises(I8DScheduleError, match="seed_index"):
        verify_i8d_schedule(_rehash(rows), expected_battles=24)


def test_a_swapped_opponent_policy_is_rejected():
    rows = list(_canonical(24).rows)
    rows[0] = dataclasses.replace(rows[0], opp_policy="max_damage")   # row 0 is goodstuff×heuristic
    with pytest.raises(I8DScheduleError, match="opp_policy"):
        verify_i8d_schedule(_rehash(rows), expected_battles=24)


def test_a_swapped_opponent_team_is_rejected():
    rows = list(_canonical(24).rows)
    rows[6] = dataclasses.replace(rows[6], opp_team_path="teams/panel_champions_v0/rain_offense.txt")
    with pytest.raises(I8DScheduleError, match="opp_team_path"):
        verify_i8d_schedule(_rehash(rows), expected_battles=24)


def test_a_heldout_split_row_is_rejected():
    rows = list(_canonical(24).rows)
    rows[3] = dataclasses.replace(rows[3], panel_split="heldout")
    with pytest.raises(I8DScheduleError, match="panel_split"):
        verify_i8d_schedule(_rehash(rows), expected_battles=24)


def test_a_wrong_format_is_rejected():
    rows = list(_canonical(24).rows)
    rows[1] = dataclasses.replace(rows[1], format_id="gen9vgc2025regi")
    with pytest.raises(I8DScheduleError, match="format_id"):
        verify_i8d_schedule(_rehash(rows), expected_battles=24)


def test_a_wrong_hero_team_is_rejected():
    rows = list(_canonical(24).rows)
    rows[1] = dataclasses.replace(rows[1], hero_team_path="teams/other.txt")
    with pytest.raises(I8DScheduleError, match="hero_team_path"):
        verify_i8d_schedule(_rehash(rows), expected_battles=24)


def test_a_forged_hash_is_rejected():
    # `version` is in the hash but NOT in the per-row structure check: change it and keep the old
    # hash -> the recompute is the only thing that can catch this. Isolates the hash check.
    s = _canonical(24)
    forged = Schedule(version="tampered", rows=s.rows,
                      schedule_hash=s.schedule_hash, panel_hash=s.panel_hash)
    with pytest.raises(I8DScheduleError, match="schedule_hash"):
        verify_i8d_schedule(forged, expected_battles=24)

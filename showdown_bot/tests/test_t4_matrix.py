"""T4 pinned matrix: committed schedules must match the generator (drift guard)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.panel_schedule import generate_dev_schedule
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.t4_matrix import (
    T4_PREFIX_CELLS,
    T4_PREFIX_LEN,
    T4_SEEDS_PER_CELL,
    generate_t4_schedules,
)

_REPO = Path(__file__).resolve().parents[2]
_PANEL = _REPO / "config" / "eval" / "panels" / "panel_v001.yaml"
_FULL = _REPO / "config" / "eval" / "schedules" / "t4_smoke_v001.yaml"
_PREFIX = _REPO / "config" / "eval" / "schedules" / "t4_smoke_v001_prefix.yaml"
_TEAMS_ROOT = str(_REPO / "showdown_bot")


def _generated():
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    return generate_t4_schedules(panel, teams_root=_TEAMS_ROOT)


def test_matrix_constants_pinned():
    assert T4_SEEDS_PER_CELL == {
        "heuristic": 5, "max_damage": 5, "simple_heuristic": 3,
        "greedy_protect": 2, "scripted_vgc": 2,
    }
    assert T4_PREFIX_LEN == 10 == len(T4_PREFIX_CELLS)


def test_full_schedule_shape_and_weights():
    full, pre = _generated()
    assert len(full.rows) == 51
    assert Counter(r.opp_policy for r in full.rows) == {
        "heuristic": 15, "max_damage": 15, "simple_heuristic": 9,
        "greedy_protect": 6, "scripted_vgc": 6,
    }
    assert full.reproducible is True
    assert {r.panel_split for r in full.rows} == {"dev"}
    # Stratified prefix: rows 0..9 cover all 5 policies and all 3 dev teams.
    head = full.rows[:T4_PREFIX_LEN]
    assert {r.opp_policy for r in head} == set(T4_SEEDS_PER_CELL)
    assert len({r.opp_team_path for r in head}) == 3
    # Prefix schedule == first 10 rows of the full schedule.
    assert pre.rows == head
    assert pre.panel_hash == full.panel_hash


def test_committed_yamls_match_generator():
    full, pre = _generated()
    committed_full = load_schedule(str(_FULL))
    committed_pre = load_schedule(str(_PREFIX))
    assert committed_full.schedule_hash == full.schedule_hash
    assert committed_pre.schedule_hash == pre.schedule_hash
    assert committed_full.panel_hash == full.panel_hash == "760c1e5935fe0474"
    # Full field equality incl. provenance (team hashes, panel_split) — not covered by the hash.
    assert committed_full.rows == full.rows
    assert committed_pre.rows == pre.rows


def test_t3e_six_battle_regression_hash_unchanged():
    # The T3e/T3f smoke schedule regenerated with the extended generator must keep its
    # historical identity — proves the extensions changed nothing for existing call shapes.
    panel = load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)
    sched = generate_dev_schedule(
        panel, policies=["simple_heuristic", "greedy_protect"], teams_root=_TEAMS_ROOT,
    )
    assert sched.schedule_hash == "db4d0a7a31070a62"

"""2b-4 Task 3: committed schedules must match the generator (drift guard), mirroring
test_t4_matrix.py / test_datagen_2b25a.py's pattern. Pins both schedule hashes so drift in
either the generator or the committed YAML is caught."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.schedule_2b4 import (
    BASELINE_POLICY,
    DETERMINISM_SEEDS_PER_CELL,
    DEVSTRENGTH_SEEDS_PER_CELL,
    HERO_TEAM,
    generate_2b4_schedules,
    generate_determinism_schedule,
    generate_devstrength_schedule,
    schedule_relpath,
)

_REPO = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_PANEL = _REPO / "config" / "eval" / "panels" / "panel_v001.yaml"
_TEAMS_ROOT = str(_REPO / "showdown_bot")

_DETERMINISM_HASH = "1638a2d9034eb0f3"
_DEVSTRENGTH_HASH = "9ce8872b75065c63"
_PANEL_HASH = "760c1e5935fe0474"


def _panel():
    return load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)


def _generated():
    return generate_2b4_schedules(_panel(), teams_root=_TEAMS_ROOT)


def test_hero_team_and_baseline_policy_pinned():
    assert HERO_TEAM == "teams/fixed_team.txt"
    assert BASELINE_POLICY == "max_damage"


def test_seeds_per_cell_pinned():
    assert DETERMINISM_SEEDS_PER_CELL == 8
    assert DEVSTRENGTH_SEEDS_PER_CELL == 50


def test_schedule_relpath():
    assert schedule_relpath("determinism") == "config/eval/schedules/2b4_determinism_v001.yaml"
    assert schedule_relpath("devstrength") == "config/eval/schedules/2b4_devstrength_v001.yaml"


def test_generate_2b4_schedules_keyed():
    scheds = _generated()
    assert set(scheds) == {"determinism", "devstrength"}


# --- determinism schedule shape --------------------------------------------------------------

def test_determinism_schedule_shape():
    sched = generate_determinism_schedule(_panel(), teams_root=_TEAMS_ROOT)

    assert len(sched.rows) == 24  # 8 seeds/cell x 3 dev teams
    assert 20 <= len(sched.rows) <= 30  # plan's stated range
    assert Counter(r.opp_policy for r in sched.rows) == {BASELINE_POLICY: 24}
    assert [r.seed_index for r in sched.rows] == list(range(24))
    assert {r.panel_split for r in sched.rows} == {"dev"}
    assert all(r.hero_team_path == HERO_TEAM for r in sched.rows)
    assert sched.reproducible is True
    assert sched.panel_hash == _PANEL_HASH


def test_determinism_schedule_hash_pinned():
    sched = generate_determinism_schedule(_panel(), teams_root=_TEAMS_ROOT)
    assert sched.schedule_hash == _DETERMINISM_HASH


def test_determinism_committed_yaml_matches_generator():
    sched = generate_determinism_schedule(_panel(), teams_root=_TEAMS_ROOT)
    committed = load_schedule(str(_REPO / schedule_relpath("determinism")))

    assert committed.schedule_hash == sched.schedule_hash == _DETERMINISM_HASH
    assert committed.panel_hash == sched.panel_hash == _PANEL_HASH
    assert committed.rows == sched.rows


# --- dev-strength schedule shape ---------------------------------------------------------

def test_devstrength_schedule_shape():
    sched = generate_devstrength_schedule(_panel(), teams_root=_TEAMS_ROOT)

    assert len(sched.rows) == 150  # 50 seeds/cell x 3 dev teams
    assert len(sched.rows) >= 150  # T5/PokéAgent discipline floor
    assert Counter(r.opp_policy for r in sched.rows) == {BASELINE_POLICY: 150}
    assert [r.seed_index for r in sched.rows] == list(range(150))
    assert {r.panel_split for r in sched.rows} == {"dev"}
    assert all(r.hero_team_path == HERO_TEAM for r in sched.rows)
    assert sched.reproducible is True
    assert sched.panel_hash == _PANEL_HASH


def test_devstrength_schedule_hash_pinned():
    sched = generate_devstrength_schedule(_panel(), teams_root=_TEAMS_ROOT)
    assert sched.schedule_hash == _DEVSTRENGTH_HASH


def test_devstrength_committed_yaml_matches_generator():
    sched = generate_devstrength_schedule(_panel(), teams_root=_TEAMS_ROOT)
    committed = load_schedule(str(_REPO / schedule_relpath("devstrength")))

    assert committed.schedule_hash == sched.schedule_hash == _DEVSTRENGTH_HASH
    assert committed.panel_hash == sched.panel_hash == _PANEL_HASH
    assert committed.rows == sched.rows


# --- the two schedules must actually be distinct (different hash), same panel ----------------

def test_determinism_and_devstrength_schedules_are_distinct():
    scheds = _generated()
    assert scheds["determinism"].schedule_hash != scheds["devstrength"].schedule_hash
    assert scheds["determinism"].panel_hash == scheds["devstrength"].panel_hash

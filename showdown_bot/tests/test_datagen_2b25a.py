"""Datagen schedules (2b-2.5a Task 4): committed schedules must match the generator
(drift guard), mirroring `test_t6_heldout.py` / `test_t4_matrix.py`'s pattern. Uniform
5 seeds/cell across all 5 T4_POLICIES, per hero team, against the panel's 3 dev teams --
deliberately different from T4's weighted eval matrix (see `datagen_2b25a`'s module
docstring for the rationale)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from showdown_bot.eval.datagen_2b25a import (
    DATAGEN_POLICIES,
    HERO_TEAMS,
    SEED_BASES,
    generate_datagen_schedules,
    schedule_relpath,
)
from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.t4_matrix import T4_POLICIES

_REPO = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_PANEL = _REPO / "config" / "eval" / "panels" / "panel_v001.yaml"
_TEAMS_ROOT = str(_REPO / "showdown_bot")

_FIXED_TEAM_HASH = "5aef213f351a6627"


def _panel():
    return load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)


def _generated():
    return generate_datagen_schedules(_panel(), teams_root=_TEAMS_ROOT)


def test_hero_teams_pinned():
    assert HERO_TEAMS == {
        "fixed": "teams/fixed_team.txt",
        "trickroom": "teams/panel_v001/trickroom_dev.txt",
        "sun": "teams/panel_v001/sun_dev.txt",
        "rain": "teams/panel_v001/rain_dev.txt",
    }


def test_seed_bases_pinned_and_distinct():
    # SEED_BASES are provenance strings (Task 5 kernel wiring) -- pin the literals.
    assert SEED_BASES == {
        "fixed": "dg25a-fixed",
        "trickroom": "dg25a-trickroom",
        "sun": "dg25a-sun",
        "rain": "dg25a-rain",
    }
    assert len(set(SEED_BASES.values())) == 4


def test_policies_are_all_five_t4_policies():
    assert DATAGEN_POLICIES == T4_POLICIES
    assert len(DATAGEN_POLICIES) == 5


def test_schedule_relpath():
    for key in HERO_TEAMS:
        assert schedule_relpath(key) == f"config/eval/schedules/datagen_2b25a_hero_{key}.yaml"


def test_schedules_keyed_by_hero():
    scheds = _generated()
    assert set(scheds) == set(HERO_TEAMS)


def test_schedule_shape_and_uniform_weights():
    scheds = _generated()
    for key, sched in scheds.items():
        assert len(sched.rows) == 75, key
        assert Counter(r.opp_policy for r in sched.rows) == {p: 15 for p in DATAGEN_POLICIES}, key
        assert [r.seed_index for r in sched.rows] == list(range(75)), key
        assert {r.panel_split for r in sched.rows} == {"dev"}, key
        assert sched.reproducible is True, key
        assert sched.panel_hash == "760c1e5935fe0474", key


def test_hero_provenance_per_schedule():
    panel = _panel()
    scheds = generate_datagen_schedules(panel, teams_root=_TEAMS_ROOT)
    dev_hash_by_id = {t.team_id: t.team_hash for t in panel.dev_teams}

    all_hashes = set()
    for key, sched in scheds.items():
        expected_path = HERO_TEAMS[key]
        assert all(r.hero_team_path == expected_path for r in sched.rows), key
        hashes = {r.hero_team_hash for r in sched.rows}
        assert len(hashes) == 1, key  # single hero per schedule -> single hero_team_hash
        h = hashes.pop()
        assert h is not None, key
        all_hashes.add(h)
        if key == "fixed":
            assert h == _FIXED_TEAM_HASH
        else:
            assert h == dev_hash_by_id[key]

    # Across the 4 schedules: exactly 4 distinct hero_team_hash values.
    assert len(all_hashes) == 4


def test_committed_yamls_match_generator():
    scheds = _generated()
    for key, sched in scheds.items():
        path = _REPO / schedule_relpath(key)
        committed = load_schedule(str(path))
        assert committed.schedule_hash == sched.schedule_hash, key
        assert committed.panel_hash == sched.panel_hash == "760c1e5935fe0474", key
        # Full field equality incl. provenance (team hashes, panel_split) -- not covered by hash.
        assert committed.rows == sched.rows, key

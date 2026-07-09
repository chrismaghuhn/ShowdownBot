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


# --- T3e P1: chosen policies must be a subset of panel.policies (truthful panel_hash) ---

def test_explicit_policy_not_in_panel_raises():
    # greedy_protect is known + reproducible but NOT in this panel.policies -> a schedule
    # using it would not be covered by panel_hash -> fail fast.
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["greedy_protect"])


def test_explicit_valid_subset_generates():
    sched = generate_dev_schedule(_panel(), policies=["heuristic"])
    assert {r.opp_policy for r in sched.rows} == {"heuristic"}


def test_default_selection_is_subset_of_panel_policies():
    sched = generate_dev_schedule(_panel())
    assert {r.opp_policy for r in sched.rows} <= set(_panel().policies)


def test_dev_generation_enforces_panel_subset():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["simple_heuristic"])  # not in panel.policies


def test_heldout_generation_enforces_panel_subset():
    with pytest.raises(PanelScheduleError):
        generate_heldout_schedule(
            _panel(), confirm_heldout=True, policies=["simple_heuristic"]  # not in panel.policies
        )


# --- T3e P4: generated rows carry team-hash provenance -------------------------------

def _hero_team(tmp_path):
    (tmp_path / "hero.txt").write_text("Incineroar @ Sitrus Berry\n", encoding="utf-8")
    (tmp_path / "hero.packed").write_text("Incineroar||sitrusberry|...", encoding="utf-8")


def test_generated_rows_carry_team_hashes(tmp_path):
    _hero_team(tmp_path)
    sched = generate_dev_schedule(
        _panel(), hero_team_path="hero.txt", teams_root=str(tmp_path), policies=["heuristic"],
    )
    # opp_team_hash comes straight from each PanelTeam.team_hash (h1/h2 in _panel()).
    assert {r.opp_team_hash for r in sched.rows} == {"h1", "h2"}
    # hero_team_hash is computed from the hero team file content — one hero team -> one hash.
    assert all(r.hero_team_hash for r in sched.rows)
    assert len({r.hero_team_hash for r in sched.rows}) == 1


def test_write_yaml_roundtrips_team_hashes(tmp_path):
    _hero_team(tmp_path)
    sched = generate_dev_schedule(
        _panel(), hero_team_path="hero.txt", teams_root=str(tmp_path), policies=["heuristic"],
    )
    out = tmp_path / "dev.yaml"
    write_schedule_yaml(sched, str(out))
    reloaded = load_schedule(str(out))
    assert reloaded.schedule_hash == sched.schedule_hash  # unchanged by provenance hashes
    assert [r.opp_team_hash for r in reloaded.rows] == [r.opp_team_hash for r in sched.rows]
    assert [r.hero_team_hash for r in reloaded.rows] == [r.hero_team_hash for r in sched.rows]
    assert all(r.hero_team_hash for r in reloaded.rows)


# --- T3f Task 4: panel_split stamped by generation -------------------------------------

def test_generated_dev_rows_are_stamped_dev():
    sched = generate_dev_schedule(_panel(), policies=["heuristic"])
    assert {r.panel_split for r in sched.rows} == {"dev"}


def test_generated_heldout_rows_are_stamped_heldout():
    sched = generate_heldout_schedule(_panel(), confirm_heldout=True, policies=["heuristic"])
    assert {r.panel_split for r in sched.rows} == {"heldout"}


def test_write_yaml_roundtrips_panel_split(tmp_path):
    sched = generate_dev_schedule(_panel(), policies=["heuristic"])
    out = tmp_path / "dev.yaml"
    write_schedule_yaml(sched, str(out))
    reloaded = load_schedule(str(out))
    assert reloaded.schedule_hash == sched.schedule_hash          # provenance -> hash unchanged
    assert {r.panel_split for r in reloaded.rows} == {"dev"}


# --- T4: per-policy seeds_per_cell mapping ---------------------------------------------

def test_seeds_per_cell_mapping_counts_and_order():
    sched = generate_dev_schedule(
        _panel(), policies=["heuristic", "max_damage"],
        seeds_per_cell={"heuristic": 3, "max_damage": 1},
    )
    # 2 teams x (3 + 1) = 8 rows, team-major then policy order, contiguous seed_index
    assert len(sched.rows) == 8
    assert [r.seed_index for r in sched.rows] == list(range(8))
    assert [r.opp_policy for r in sched.rows] == (
        ["heuristic"] * 3 + ["max_damage"] + ["heuristic"] * 3 + ["max_damage"]
    )


def test_seeds_per_cell_mapping_missing_policy_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(
            _panel(), policies=["heuristic", "max_damage"], seeds_per_cell={"heuristic": 3},
        )


def test_seeds_per_cell_mapping_unknown_policy_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(
            _panel(), policies=["heuristic"], seeds_per_cell={"heuristic": 1, "scripted_vgc": 2},
        )


def test_seeds_per_cell_mapping_invalid_value_raises():
    for bad in (0, -1, True, "2"):
        with pytest.raises(PanelScheduleError):
            generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell={"heuristic": bad})


def test_seeds_per_cell_int_backcompat_unchanged():
    a = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=3)
    b = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell={"heuristic": 3})
    assert a.schedule_hash == b.schedule_hash  # mapping == uniform int when counts agree


# --- T4: prefix_cells — stratified reproduction-prefix ordering --------------------------

def test_prefix_cells_come_first_then_canonical_remainder():
    sched = generate_dev_schedule(
        _panel(), policies=["heuristic", "max_damage"],
        seeds_per_cell={"heuristic": 2, "max_damage": 1},
        prefix_cells=[("max_damage", "d2"), ("heuristic", "d1")],
    )
    # 2 teams x (2 + 1) = 6 rows total; prefix picks occupy seed_index 0 and 1 in given order.
    assert len(sched.rows) == 6
    assert (sched.rows[0].opp_policy, sched.rows[0].opp_team_path) == (
        "max_damage", "teams/panel_v001/sun_dev.txt")
    assert (sched.rows[1].opp_policy, sched.rows[1].opp_team_path) == (
        "heuristic", "teams/panel_v001/trickroom_dev.txt")
    # Remainder is canonical (team-major, policy order), each cell reduced by its prefix picks:
    assert [(r.opp_policy, r.opp_team_path) for r in sched.rows[2:]] == [
        ("heuristic", "teams/panel_v001/trickroom_dev.txt"),
        ("max_damage", "teams/panel_v001/trickroom_dev.txt"),
        ("heuristic", "teams/panel_v001/sun_dev.txt"),
        ("heuristic", "teams/panel_v001/sun_dev.txt"),
    ]
    assert [r.seed_index for r in sched.rows] == list(range(6))  # still contiguous


def test_prefix_cells_preserve_per_cell_totals():
    sched = generate_dev_schedule(
        _panel(), policies=["heuristic"], seeds_per_cell=2,
        prefix_cells=[("heuristic", "d2")],
    )
    from collections import Counter
    assert Counter((r.opp_policy, r.opp_team_path) for r in sched.rows) == Counter({
        ("heuristic", "teams/panel_v001/trickroom_dev.txt"): 2,
        ("heuristic", "teams/panel_v001/sun_dev.txt"): 2,
    })


def test_prefix_cells_overconsuming_a_cell_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(
            _panel(), policies=["heuristic"], seeds_per_cell=1,
            prefix_cells=[("heuristic", "d1"), ("heuristic", "d1")],  # cell has only 1 seed
        )


def test_prefix_cells_unknown_policy_or_team_raises():
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["heuristic"], prefix_cells=[("max_damage", "d1")])
    with pytest.raises(PanelScheduleError):
        generate_dev_schedule(_panel(), policies=["heuristic"], prefix_cells=[("heuristic", "nope")])


def test_prefix_cells_none_is_unchanged():
    a = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=2)
    b = generate_dev_schedule(_panel(), policies=["heuristic"], seeds_per_cell=2, prefix_cells=None)
    assert a.schedule_hash == b.schedule_hash

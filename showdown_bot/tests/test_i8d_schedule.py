"""The fixed I8-D 200-battle schedule (bound execution decisions).

Dev-only 6-matchup cyclic round-robin, seed_index 0..199, distribution 34/34/33/33/33/33,
seed base champions-panel-v0-i8d-latency. Deterministic and hash-stable. Generation only —
no server, no battle, no run.
"""
from __future__ import annotations

import pytest

from showdown_bot.eval.panel import Panel, PanelTeam
from showdown_bot.eval.schedule import compute_schedule_hash, load_schedule
from showdown_bot.eval.i8d_schedule import (
    I8D_FORMAT,
    I8D_HERO_TEAM,
    I8D_MATCHUPS,
    I8D_MAX_BATTLES,
    I8D_SEED_BASE,
    build_i8d_schedule,
    write_i8d_schedule,
)


def _panel() -> Panel:
    def t(tid, arch):
        return PanelTeam(team_id=tid, team_path=f"teams/panel_champions_v0/{tid}.txt",
                         archetype=arch, team_hash=f"hash_{tid}")
    return Panel(
        version="champions_v0",
        policies=("heuristic", "max_damage"),
        dev_teams=(t("goodstuff", "balance_goodstuff"),
                   t("tailwind_offense", "tailwind_offense"),
                   t("trick_room", "trick_room")),
        heldout_teams=(t("rain_offense", "weather_rain"),
                       t("disruption", "bulky_disruption")),
        panel_hash="aac1ea30446fde88",
    )


def _sched():
    return build_i8d_schedule(_panel(), teams_root=".")


def test_the_seed_base_and_matrix_are_the_bound_values():
    assert I8D_SEED_BASE == "champions-panel-v0-i8d-latency"
    assert I8D_MAX_BATTLES == 200
    assert I8D_FORMAT == "gen9championsvgc2026regma"
    assert I8D_HERO_TEAM == "teams/fixed_champions_v0.txt"
    assert I8D_MATCHUPS == (
        ("goodstuff", "heuristic"), ("goodstuff", "max_damage"),
        ("tailwind_offense", "heuristic"), ("tailwind_offense", "max_damage"),
        ("trick_room", "heuristic"), ("trick_room", "max_damage"),
    )


def test_exactly_200_rows():
    assert len(_sched().rows) == 200


def test_seed_indices_are_0_to_199_unique_and_gapless():
    rows = _sched().rows
    assert [r.seed_index for r in rows] == list(range(200))


def test_matchups_appear_only_in_the_fixed_cyclic_order():
    rows = _sched().rows
    id_of = {"teams/panel_champions_v0/goodstuff.txt": "goodstuff",
             "teams/panel_champions_v0/tailwind_offense.txt": "tailwind_offense",
             "teams/panel_champions_v0/trick_room.txt": "trick_room"}
    for i, r in enumerate(rows):
        team_id, policy = I8D_MATCHUPS[i % 6]
        assert (id_of[r.opp_team_path], r.opp_policy) == (team_id, policy), i
    # the set of distinct (team, policy) is exactly the six matchups
    seen = {(id_of[r.opp_team_path], r.opp_policy) for r in rows}
    assert seen == set(I8D_MATCHUPS)


def test_distribution_is_exactly_34_34_33_33_33_33():
    rows = _sched().rows
    counts = [sum(1 for i in range(200) if i % 6 == m) for m in range(6)]
    assert counts == [34, 34, 33, 33, 33, 33]
    # and that is what the schedule actually realises, matchup by matchup
    from collections import Counter
    per = Counter((r.opp_team_path, r.opp_policy) for r in rows)
    ordered = [per[(f"teams/panel_champions_v0/{tid}.txt", pol)] for tid, pol in I8D_MATCHUPS]
    assert ordered == [34, 34, 33, 33, 33, 33]


def test_no_held_out_team_appears():
    rows = _sched().rows
    for r in rows:
        assert "rain_offense" not in r.opp_team_path
        assert "disruption" not in r.opp_team_path
        assert r.panel_split == "dev"


def test_every_row_carries_the_bound_format_hero_and_provenance():
    for r in _sched().rows:
        assert r.format_id == I8D_FORMAT
        assert r.hero_team_path == I8D_HERO_TEAM
        assert r.opp_policy in ("heuristic", "max_damage")
        assert r.opp_team_hash is not None            # from the panel team


def test_deterministic_same_rows_and_same_hash():
    a, b = build_i8d_schedule(_panel(), teams_root="."), build_i8d_schedule(_panel(), teams_root=".")
    assert a.rows == b.rows
    assert a.schedule_hash == b.schedule_hash
    assert a.schedule_hash == compute_schedule_hash(a.version, a.rows)
    assert a.panel_hash == "aac1ea30446fde88"


def test_write_is_byte_identical_and_round_trips(tmp_path):
    s = _sched()
    p1, p2 = tmp_path / "a.yaml", tmp_path / "b.yaml"
    write_i8d_schedule(s, str(p1))
    write_i8d_schedule(s, str(p2))
    assert p1.read_bytes() == p2.read_bytes()          # byte-identical
    assert b"\r\n" not in p1.read_bytes()              # LF-only
    loaded = load_schedule(str(p1))                    # consumable by the runner's loader
    assert len(loaded.rows) == 200
    assert loaded.schedule_hash == s.schedule_hash


def test_held_out_team_in_the_matrix_is_refused():
    """A panel whose dev set is missing a required matchup team (or whose team is only held-out)
    must fail closed, not silently drop or substitute."""
    bad = _panel()
    # move trick_room to held-out only
    dev = tuple(t for t in bad.dev_teams if t.team_id != "trick_room")
    bad = Panel(version=bad.version, policies=bad.policies, dev_teams=dev,
                heldout_teams=bad.heldout_teams + (
                    PanelTeam("trick_room", "teams/panel_champions_v0/trick_room.txt",
                              "trick_room", "hash_trick_room"),),
                panel_hash=bad.panel_hash)
    with pytest.raises(Exception):
        build_i8d_schedule(bad, teams_root=".")


def test_n_battles_is_bound_to_max_battles_and_cannot_exceed_it():
    with pytest.raises(Exception):
        build_i8d_schedule(_panel(), n_battles=201, teams_root=".")

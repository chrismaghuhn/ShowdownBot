"""T1c: run_local_gauntlet per-side team resolution (non-mirror plumbing).

Verifies the seam without a live server: mirror (opp_team_path=None) gives both sides
the same packed team; a distinct opp_team_path gives the villain a different packed team.
"""
from __future__ import annotations

from pathlib import Path

from showdown_bot.client.gauntlet import _is_mirror_battle, _resolve_side_teams

_TEAMS = Path(__file__).resolve().parents[1] / "teams"
_HERO = str(_TEAMS / "fixed_team.txt")
_OPP_A = str(_TEAMS / "opp_variant_a.txt")
_OPP_B = str(_TEAMS / "opp_variant_b.txt")


def test_mirror_when_no_opp_team():
    hero, villain = _resolve_side_teams(_HERO, None)
    assert hero and hero == villain  # non-empty, mirror (back-compat)


def test_nonmirror_with_distinct_opp_team():
    hero, villain = _resolve_side_teams(_HERO, _OPP_A)
    assert hero and villain
    assert hero != villain  # villain fields a different packed team


def test_two_opp_variants_differ():
    _, va = _resolve_side_teams(_HERO, _OPP_A)
    _, vb = _resolve_side_teams(_HERO, _OPP_B)
    assert va and vb and va != vb  # the schedule can drive distinct opp teams per row


# ---------------------------------------------------------------------------
# 2b-2.5a wiring fix: `_is_mirror_battle` is the real mirror_flag computation threaded into
# `run_local_gauntlet` -> `_Client` -> `DatasetExportRuntime` (replacing the pre-fix hardcoded
# `mirror_flag=False` at both construction sites in gauntlet.py). It mirrors
# `_resolve_side_teams`' own "no opp path -> mirror" convention exactly.
# ---------------------------------------------------------------------------


def test_is_mirror_battle_true_when_no_opp_team_path():
    assert _is_mirror_battle(_HERO, None) is True


def test_is_mirror_battle_true_when_opp_team_path_is_empty_string():
    assert _is_mirror_battle(_HERO, "") is True


def test_is_mirror_battle_true_when_paths_are_identical():
    assert _is_mirror_battle(_HERO, _HERO) is True


def test_is_mirror_battle_false_when_paths_differ():
    assert _is_mirror_battle(_HERO, _OPP_A) is False
    assert _is_mirror_battle(_HERO, _OPP_B) is False

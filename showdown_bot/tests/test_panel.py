"""T3a panel schema + content-hashed panel_hash + dev/held-out split.

panel_hash includes team CONTENT hashes (Fix 1): editing a team file without changing its
path must change panel_hash. Dev and held-out teams must be disjoint.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from showdown_bot.eval.panel import PanelError, load_panel


def _team(root: Path, team_id: str, txt: str, packed: str) -> None:
    (root / f"{team_id}.txt").write_text(txt, encoding="utf-8")
    (root / f"{team_id}.packed").write_text(packed, encoding="utf-8")


def _panel_yaml(root: Path, body: str) -> str:
    p = root / "panel.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(p)


_BODY = """
    version: v001
    policies: [heuristic, max_damage]
    dev_teams:
      - {team_id: alpha, team_path: alpha.txt, archetype: sun}
    heldout_teams:
      - {team_id: beta, team_path: beta.txt, archetype: rain}
"""


def _make_stub(root: Path):
    _team(root, "alpha", "Incineroar @ Sitrus Berry\n", "Incineroar||sitrusberry|...")
    _team(root, "beta", "Pelipper @ Focus Sash\n", "Pelipper||focussash|...")
    return _panel_yaml(root, _BODY)


def test_load_and_split(tmp_path):
    panel = load_panel(_make_stub(tmp_path), teams_root=str(tmp_path))
    assert panel.version == "v001"
    assert [t.team_id for t in panel.dev_teams] == ["alpha"]
    assert [t.team_id for t in panel.heldout_teams] == ["beta"]
    assert panel.dev_teams[0].archetype == "sun"
    assert panel.dev_teams[0].team_hash  # non-empty content hash
    # dev/held-out disjoint
    assert not ({t.team_id for t in panel.dev_teams} & {t.team_id for t in panel.heldout_teams})


def test_panel_hash_stable(tmp_path):
    h1 = load_panel(_make_stub(tmp_path), teams_root=str(tmp_path)).panel_hash
    h2 = load_panel(_make_stub(tmp_path), teams_root=str(tmp_path)).panel_hash
    assert h1 == h2 and h1


def test_editing_team_content_without_path_changes_panel_hash(tmp_path):
    path = _make_stub(tmp_path)
    h1 = load_panel(path, teams_root=str(tmp_path)).panel_hash
    # same path, different .packed CONTENT
    (tmp_path / "alpha.packed").write_text("Incineroar||CHANGED|...", encoding="utf-8")
    h2 = load_panel(path, teams_root=str(tmp_path)).panel_hash
    assert h2 != h1


def test_unknown_policy_fails_fast(tmp_path):
    _make_stub(tmp_path)
    body = _BODY.replace("[heuristic, max_damage]", "[heuristic, mystery_bot]")
    with pytest.raises(PanelError):
        load_panel(_panel_yaml(tmp_path, body), teams_root=str(tmp_path))


def test_team_in_both_dev_and_heldout_fails_fast(tmp_path):
    _make_stub(tmp_path)
    body = _BODY.replace(
        "heldout_teams:\n      - {team_id: beta, team_path: beta.txt, archetype: rain}",
        "heldout_teams:\n      - {team_id: alpha, team_path: alpha.txt, archetype: sun}",
    )
    with pytest.raises(PanelError):
        load_panel(_panel_yaml(tmp_path, body), teams_root=str(tmp_path))


def test_same_team_under_two_ids_fails_fast(tmp_path):
    # Different team_id, but SAME team_path (=> same team_hash) across dev/held-out.
    _team(tmp_path, "alpha", "Incineroar @ Sitrus Berry\n", "Incineroar||x")
    body = """
        version: v001
        policies: [heuristic, max_damage]
        dev_teams:
          - {team_id: alpha, team_path: alpha.txt, archetype: x}
        heldout_teams:
          - {team_id: alpha_copy, team_path: alpha.txt, archetype: x}
    """
    with pytest.raises(PanelError):
        load_panel(_panel_yaml(tmp_path, body), teams_root=str(tmp_path))


def test_missing_team_file_fails_fast(tmp_path):
    # alpha exists, beta does not
    _team(tmp_path, "alpha", "x\n", "y")
    with pytest.raises(PanelError):
        load_panel(_panel_yaml(tmp_path, _BODY), teams_root=str(tmp_path))


def test_empty_pool_fails_fast(tmp_path):
    _make_stub(tmp_path)
    body = _BODY.replace(
        "dev_teams:\n      - {team_id: alpha, team_path: alpha.txt, archetype: sun}",
        "dev_teams: []",
    )
    with pytest.raises(PanelError):
        load_panel(_panel_yaml(tmp_path, body), teams_root=str(tmp_path))


def test_panel_v001_real_pool_loads():
    # The committed archetype-diverse pool (T3b): 3 dev + 2 held-out, all content-hashed + distinct.
    showdown_bot = Path(__file__).resolve().parents[1]
    panel_path = showdown_bot.parent / "config" / "eval" / "panels" / "panel_v001.yaml"
    panel = load_panel(str(panel_path), teams_root=str(showdown_bot))
    assert panel.version == "v001"
    assert [t.team_id for t in panel.dev_teams] == ["trickroom", "sun", "rain"]
    assert [t.team_id for t in panel.heldout_teams] == ["balance", "tailwind"]
    assert len(panel.dev_teams) >= 3 and len(panel.heldout_teams) >= 2
    hashes = [t.team_hash for t in panel.dev_teams + panel.heldout_teams]
    assert all(hashes) and len(set(hashes)) == len(hashes)  # every team distinct by content
    assert panel.panel_hash

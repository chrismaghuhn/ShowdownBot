# showdown_bot/tests/test_strength_holdout_freeze.py
"""Gate B (Champions strength-holdout) STEP 3 freeze -- the REAL committed artifacts.

Unlike test_baseline_strength_holdout.py's closed-schema tests (which build a throwaway repo in
tmp_path), every test here binds the ACTUAL committed panel YAML, holdout manifest, baseline
manifest, and frozen hash constants against the real six sealed teams in this repo. These are the
step-3 "hash freeze" pins: they fail the moment the panel, a sealed team, the hero, the schedule
geometry, the seed namespace, the server pins, or the pinned PYTHONHASHSEED drift.

Nothing here starts a server or plays a battle; every value is re-derived offline from the
committed files via the real production functions (load_panel, team_content_hash,
build_strength_holdout_schedule, load/verify_strength_holdout_baseline, load_showdown_commit,
server_patch_hash).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from showdown_bot.eval.baseline import (
    BaselineDriftError,
    load_strength_holdout_baseline,
    verify_strength_holdout_baseline,
)
from showdown_bot.eval.panel import load_panel, team_content_hash
from showdown_bot.eval.run_manifest import load_showdown_commit, server_patch_hash
from showdown_bot.eval.strength_holdout_schedule import (
    STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH,
    STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH,
    STRENGTH_HOLDOUT_HERO_TEAM_PATH,
    STRENGTH_HOLDOUT_MANIFEST_PATH,
    STRENGTH_HOLDOUT_PANEL_PATH,
    STRENGTH_HOLDOUT_SEED_BASE,
    build_strength_holdout_schedule,
    strength_holdout_manifest_hash,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/ -> showdown_bot/ -> <repo>
_BASELINE_PATH = _REPO_ROOT / "config" / "eval" / "baselines" / "champions-strength-holdout-v0.json"


def _panel():
    return load_panel(str(_REPO_ROOT / STRENGTH_HOLDOUT_PANEL_PATH), teams_root=str(_REPO_ROOT))


def _manifest_teams():
    man = json.loads((_REPO_ROOT / STRENGTH_HOLDOUT_MANIFEST_PATH).read_text(encoding="utf-8"))
    return man["teams"]


def _real_baseline():
    return load_strength_holdout_baseline(str(_BASELINE_PATH))


# --- panel binds exactly the six manifest teams ------------------------------------------------


def test_real_panel_binds_exactly_the_six_manifest_team_ids_and_paths():
    panel = _panel()
    panel_teams = [*panel.dev_teams, *panel.heldout_teams]
    assert len(panel_teams) == 6
    man_teams = _manifest_teams()
    assert {t.team_id for t in panel_teams} == {t["team_id"] for t in man_teams}
    by_id = {t.team_id: t for t in panel_teams}
    for mt in man_teams:
        assert by_id[mt["team_id"]].team_path == mt["team_path"]


def test_real_panel_manifest_and_ondisk_hashes_all_agree():
    panel = _panel()
    panel_teams = {t.team_id: t for t in (*panel.dev_teams, *panel.heldout_teams)}
    for mt in _manifest_teams():
        panel_team = panel_teams[mt["team_id"]]
        on_disk = team_content_hash(str(_REPO_ROOT), mt["team_path"])
        assert panel_team.team_hash == mt["team_content_hash"] == on_disk


# --- frozen hash constants ---------------------------------------------------------------------


def test_expected_panel_hash_constant_is_frozen_to_the_real_panel():
    panel = _panel()
    assert STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH == panel.panel_hash
    assert STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH  # non-empty


def test_expected_manifest_hash_constant_is_frozen_to_the_real_manifest():
    assert STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH == strength_holdout_manifest_hash(
        str(_REPO_ROOT / STRENGTH_HOLDOUT_MANIFEST_PATH)
    )
    assert STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH  # non-empty


# --- schedule geometry over the real six teams -------------------------------------------------


def test_real_schedule_rebuild_has_exactly_180_keys():
    panel = _panel()
    team_ids = sorted(t.team_id for t in (*panel.dev_teams, *panel.heldout_teams))
    schedule = build_strength_holdout_schedule(
        holdout_team_ids=team_ids, panel_hash=panel.panel_hash, seed_base=STRENGTH_HOLDOUT_SEED_BASE,
    )
    assert len(schedule.battle_keys) == 180


def test_real_schedule_hash_changes_if_panel_hash_changes():
    panel = _panel()
    team_ids = sorted(t.team_id for t in (*panel.dev_teams, *panel.heldout_teams))
    a = build_strength_holdout_schedule(holdout_team_ids=team_ids, panel_hash=panel.panel_hash)
    b = build_strength_holdout_schedule(holdout_team_ids=team_ids, panel_hash="0" * 16)
    assert a.schedule_hash != b.schedule_hash


# --- the real baseline manifest loads and verifies against the real tree -----------------------


def test_real_baseline_loads_under_the_closed_schema():
    baseline = _real_baseline()
    assert baseline["baseline_id"] == "champions-strength-holdout-v0"
    assert baseline["hero_agent"] == "max_damage"
    assert len(baseline["opponent_teams"]) == 6


def test_real_baseline_hero_is_the_canonical_champions_hero():
    baseline = _real_baseline()
    assert baseline["hero_team_path"] == STRENGTH_HOLDOUT_HERO_TEAM_PATH
    assert baseline["hero_team_hash"] == team_content_hash(
        str(_REPO_ROOT), STRENGTH_HOLDOUT_HERO_TEAM_PATH
    )


def test_real_baseline_verifies_clean_against_the_real_repo():
    baseline = _real_baseline()
    checks = verify_strength_holdout_baseline(baseline, repo_root=str(_REPO_ROOT))
    assert all(c.ok for c in checks)
    assert {c.name for c in checks} >= {
        "panel_hash", "holdout_manifest", "hero_team_hash", "opponent_team_hashes",
        "schedule_hash", "seed_base", "format_id", "hero_agent", "showdown_commit",
        "server_patch_hash",
    }


# --- tamper: every re-derived pin fails closed -------------------------------------------------


@pytest.mark.parametrize("field", [
    "panel_hash", "hero_team_hash", "schedule_hash", "seed_base", "showdown_commit",
    "server_patch_hash",
])
def test_real_baseline_tamper_on_a_top_level_pin_fails_closed(field):
    baseline = _real_baseline()
    baseline[field] = baseline[field] + "-tampered" if isinstance(baseline[field], str) else "x"
    with pytest.raises(BaselineDriftError):
        verify_strength_holdout_baseline(baseline, repo_root=str(_REPO_ROOT))


def test_real_baseline_tamper_on_an_opponent_team_hash_fails_closed():
    baseline = _real_baseline()
    baseline["opponent_teams"][0]["team_content_hash"] = "deadbeefdeadbeef"
    with pytest.raises(BaselineDriftError):
        verify_strength_holdout_baseline(baseline, repo_root=str(_REPO_ROOT))


def test_reference_near_duplicate_audit_is_reproducible_and_diagnostic():
    """Task 13 item 5: run find_near_duplicate_flags for every sealed holdout team against exactly
    the nine canonical reference teams (species from the real .packed), and pin the audit's
    load-bearing claims recorded in the selection audit's near-duplicate section. Diagnostic only --
    a flag is a normal return value, never a raised exception or an auto-FAIL."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    from showdown_bot.eval.near_duplicate import find_near_duplicate_flags, load_team_species
    from showdown_bot.eval.strength_holdout_runner import CANONICAL_REFERENCE_TEAM_PATHS

    holdout_ids = [t["team_id"] for t in _manifest_teams()]  # from the manifest, never hardcoded
    references = {
        rid: load_team_species(path, teams_root=str(_REPO_ROOT))
        for rid, path in CANONICAL_REFERENCE_TEAM_PATHS.items()
    }
    assert len(references) == 9

    flagged_teams = 0
    all_flags = []
    for tid in holdout_ids:
        species = load_team_species(f"{HOLDOUT_TEAMS_DIR}{tid}.txt", teams_root=str(_REPO_ROOT))
        flags = find_near_duplicate_flags(
            candidate_team_id=tid, candidate_species=species, reference_teams=references,
        )
        if flags:
            flagged_teams += 1
        all_flags.extend(flags)

    # No holdout team is a TRUE near-duplicate of any reference: every flag sits exactly at the
    # inclusive 0.5 threshold (4 of 6 shared), none above it.
    assert all_flags, "expected the documented threshold-edge staple flags to reproduce"
    assert all(f.overlap_fraction == pytest.approx(0.5) for f in all_flags)
    # Exactly three of the six holdout teams carry any flag (the selection audit's §8 count).
    assert flagged_teams == 3
    # Every flag is against an engineered COVERAGE foe (cov_foe_*), never a panel_champions_v0
    # dev/held-out team -- the holdout set does not near-duplicate the development panel at all.
    assert all(f.reference_team_id.startswith("cov_foe_") for f in all_flags)


def test_placeholder_valued_baseline_is_refused_fail_closed():
    # A blanked hash is the shape the pre-freeze placeholder carried; verify must refuse it against
    # the real tree even though the dict is otherwise well-formed.
    baseline = _real_baseline()
    baseline["panel_hash"] = ""
    baseline["schedule_hash"] = ""
    with pytest.raises(BaselineDriftError):
        verify_strength_holdout_baseline(baseline, repo_root=str(_REPO_ROOT))

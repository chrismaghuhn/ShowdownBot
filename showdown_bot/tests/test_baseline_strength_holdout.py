# showdown_bot/tests/test_baseline_strength_holdout.py
"""Gate B (Champions strength-holdout) baseline manifest -- Task 6 + Task 13 step-3 freeze.

The committed manifest is now the CLOSED A1.3 contract with REAL frozen values (Task 13 step 3),
loaded/verified ONLY by ``load_strength_holdout_baseline`` / ``verify_strength_holdout_baseline``
(the additive Gate B loader below). The generic T6 ``load_baseline`` must REFUSE it -- the two
contracts never cross-load (§A1.3). The real committed manifest's clean load + verify against the
real tree is exercised in ``test_strength_holdout_freeze.py``; this file covers the closed loader/
verifier contract on synthetic tmp_path repos.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.eval.baseline import BaselineDriftError, BaselineError, load_baseline

_REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/ -> showdown_bot/ -> <repo>
_MANIFEST_PATH = _REPO_ROOT / "config" / "eval" / "baselines" / "champions-strength-holdout-v0.json"


def test_generic_load_baseline_refuses_the_gate_b_closed_manifest():
    # A1.3 separation: the committed Gate B manifest is the CLOSED contract (frozen at step 3), not
    # a generic T6 result-baseline. The generic load_baseline must refuse it rather than silently
    # accept a manifest lacking config_hash/dev_schedule_hash/reference_jsonl -- the two contracts
    # never cross-load. The Gate B loader/verifier are exercised on this same file, and pass, in
    # test_strength_holdout_freeze.py.
    with pytest.raises(BaselineError):
        load_baseline(str(_MANIFEST_PATH))


def test_gate_b_manifest_is_distinct_from_the_reg_i_manifest():
    # The Reg-I heuristic-v1 manifest stays a valid GENERIC manifest; the Gate B one is the closed
    # contract. They are different files with different identities and different loaders.
    reg_i_path = _REPO_ROOT / "config" / "eval" / "baselines" / "heuristic-v1.json"
    reg_i = load_baseline(str(reg_i_path))  # generic still loads its own manifest
    gate_b = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert reg_i["baseline_id"] != gate_b["baseline_id"]


# =================================================================================================
# Gate-B-specific STATIC baseline contract (spec Amendment A1.3), review-fix round.
#
# Path geometry (Task 9 contract): teams_root for Gate B is the REPO ROOT, and every path is
# repo-root-relative -- the hero is exactly STRENGTH_HOLDOUT_HERO_TEAM_PATH and each opponent is
# exactly HOLDOUT_TEAMS_DIR + team_id + ".txt". The verifier also binds the authoritative holdout
# manifest at STRENGTH_HOLDOUT_MANIFEST_PATH, not just the panel.
# =================================================================================================
import copy

from showdown_bot.eval.baseline import (
    load_strength_holdout_baseline, verify_strength_holdout_baseline,
    SH_BASELINE_PYTHONHASHSEED,
)
from showdown_bot.eval.strength_holdout_schedule import (
    STRENGTH_HOLDOUT_HERO_TEAM_PATH, STRENGTH_HOLDOUT_MANIFEST_PATH,
)
from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR

FORMAT_ID = "gen9championsvgc2026regma"
SEED_BASE = "champions-strength-holdout-v0"
# Synthetic fixture team ids -- NOT the real gbh_* ids (never hardcode those in a test); these
# live only in a throwaway tmp_path repo and its own holdout manifest.
FIX_IDS = [f"sh{i}" for i in range(6)]


def _fixture_repo(tmp_path):
    """An isolated repo in repo-root geometry: hero + six opponents + panel + holdout manifest."""
    import yaml
    from showdown_bot.eval.panel import team_content_hash

    repo = tmp_path / "repo"
    (repo / "showdown_bot" / "teams" / "panel_champions_strength_holdout_v0").mkdir(parents=True)
    hero_abs = repo / STRENGTH_HOLDOUT_HERO_TEAM_PATH
    hero_abs.write_text("Hero Mon @ Leftovers\n", encoding="utf-8")
    hero_abs.with_suffix(".packed").write_text("|HeroMon|||||||||", encoding="utf-8")

    for i, tid in enumerate(FIX_IDS):
        base = repo / f"{HOLDOUT_TEAMS_DIR}{tid}"
        base.with_suffix(".txt").write_text(f"Mon{i} @ Focus Sash\n", encoding="utf-8")
        base.with_suffix(".packed").write_text(f"|Mon{i}A|||||||||]|Mon{i}B|||||||||", encoding="utf-8")

    def _hash(rel):
        return team_content_hash(str(repo), rel)

    # panel: repo-root-relative team_paths, loaded with teams_root=repo_root
    panel_dir = repo / "config" / "eval" / "panels"
    panel_dir.mkdir(parents=True)
    panel = {
        "version": "champions_strength_holdout_v0",
        "policies": ["heuristic", "max_damage"],
        "dev_teams": [{"team_id": t, "team_path": f"{HOLDOUT_TEAMS_DIR}{t}.txt",
                       "archetype": f"a{i}"} for i, t in enumerate(FIX_IDS[:3])],
        "heldout_teams": [{"team_id": t, "team_path": f"{HOLDOUT_TEAMS_DIR}{t}.txt",
                           "archetype": f"a{i}"} for i, t in enumerate(FIX_IDS[3:], start=3)],
    }
    (panel_dir / "panel_champions_strength_holdout_v0.yaml").write_text(
        yaml.safe_dump(panel, sort_keys=False), encoding="utf-8")

    # holdout manifest: the authoritative id/path/hash source
    holdout = {
        "manifest_id": "champions_strength_holdout_v0",
        "teams": [{"selection_index": i + 1, "team_id": t,
                   "team_path": f"{HOLDOUT_TEAMS_DIR}{t}.txt",
                   "team_content_hash": _hash(f"{HOLDOUT_TEAMS_DIR}{t}.txt")}
                  for i, t in enumerate(FIX_IDS)],
    }
    man_dir = repo / "config" / "eval" / "holdout"
    man_dir.mkdir(parents=True)
    (repo / STRENGTH_HOLDOUT_MANIFEST_PATH).write_text(json.dumps(holdout, indent=2), encoding="utf-8")

    prov = repo / "config" / "eval"
    (prov / "provenance.yaml").write_text("showdown_commit: abc123def456\n", encoding="utf-8")
    patch_dir = repo / "tools" / "eval" / "patches"
    patch_dir.mkdir(parents=True)
    (patch_dir / "pokemon-showdown-seeded-battle.patch").write_text("--- fixture patch ---\n", encoding="utf-8")
    return repo, FIX_IDS


def _good_manifest(repo, ids):
    from showdown_bot.eval.panel import load_panel, team_content_hash
    from showdown_bot.eval.run_manifest import load_showdown_commit, server_patch_hash
    from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule

    panel = load_panel(str(repo / "config/eval/panels/panel_champions_strength_holdout_v0.yaml"),
                       teams_root=str(repo))
    schedule = build_strength_holdout_schedule(
        holdout_team_ids=sorted(ids), panel_hash=panel.panel_hash, seed_base=SEED_BASE)
    return {
        "schema_version": 1,
        "baseline_id": "champions-strength-holdout-v0",
        "hero_agent": "max_damage",
        "format_id": FORMAT_ID,
        "panel_version": "champions_strength_holdout_v0",
        "panel_hash": panel.panel_hash,
        "hero_team_path": STRENGTH_HOLDOUT_HERO_TEAM_PATH,
        "hero_team_hash": team_content_hash(str(repo), STRENGTH_HOLDOUT_HERO_TEAM_PATH),
        "opponent_teams": [
            {"team_id": t, "team_path": f"{HOLDOUT_TEAMS_DIR}{t}.txt",
             "team_content_hash": team_content_hash(str(repo), f"{HOLDOUT_TEAMS_DIR}{t}.txt")}
            for t in sorted(ids)
        ],
        "schedule_hash": schedule.schedule_hash,
        "seed_base": SEED_BASE,
        "showdown_commit": load_showdown_commit(str(repo / "config/eval/provenance.yaml")),
        "server_patch_hash": server_patch_hash(
            str(repo / "tools/eval/patches/pokemon-showdown-seeded-battle.patch")),
        "pythonhashseed": SH_BASELINE_PYTHONHASHSEED,
    }


def _write(tmp_path, manifest, name="baseline.json"):
    p = tmp_path / name
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(p)


def _verify(repo, manifest):
    return verify_strength_holdout_baseline(manifest, repo_root=str(repo))


# --- loader: closed schema ---------------------------------------------------------------------


def test_specific_loader_accepts_a_well_formed_manifest(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    loaded = load_strength_holdout_baseline(_write(tmp_path, _good_manifest(repo, ids)))
    assert loaded["hero_agent"] == "max_damage"
    assert len(loaded["opponent_teams"]) == 6


def test_specific_loader_rejects_non_object_json(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(BaselineError, match="object"):
        load_strength_holdout_baseline(str(p))


@pytest.mark.parametrize("field", [
    "schema_version", "baseline_id", "hero_agent", "format_id", "panel_version", "panel_hash",
    "hero_team_path", "hero_team_hash", "opponent_teams", "schedule_hash", "seed_base",
    "showdown_commit", "server_patch_hash", "pythonhashseed",
])
def test_specific_loader_rejects_a_missing_field(tmp_path, field):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    del m[field]
    with pytest.raises(BaselineError, match=field):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_rejects_an_unknown_top_level_field(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["reference_jsonl"] = "data/eval/whatever.jsonl"
    with pytest.raises(BaselineError, match="reference_jsonl|unknown"):
        load_strength_holdout_baseline(_write(tmp_path, m))


@pytest.mark.parametrize("banned", ["reference_jsonl", "reference_sha256", "dev_schedule_path",
                                    "git_sha", "candidate_identity"])
def test_specific_loader_refuses_result_and_caller_supplied_identity_fields(tmp_path, banned):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m[banned] = "x"
    with pytest.raises(BaselineError):
        load_strength_holdout_baseline(_write(tmp_path, m))


@pytest.mark.parametrize("field,value", [
    ("schema_version", "1"), ("baseline_id", 7), ("hero_agent", None),
    ("opponent_teams", {}), ("panel_hash", 123), ("pythonhashseed", 0),
])
def test_specific_loader_rejects_a_wrong_field_type(tmp_path, field, value):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m[field] = value
    with pytest.raises(BaselineError, match=field):
        load_strength_holdout_baseline(_write(tmp_path, m))


@pytest.mark.parametrize("field", ["baseline_id", "panel_hash", "hero_team_hash", "schedule_hash"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_specific_loader_rejects_blank_ids_paths_and_hashes(tmp_path, field, blank):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m[field] = blank
    with pytest.raises(BaselineError, match=field):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_requires_the_max_damage_baseline_role(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["hero_agent"] = "heuristic"
    with pytest.raises(BaselineError, match="max_damage"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_requires_the_champions_format(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["format_id"] = "gen9vgc2024regg"
    with pytest.raises(BaselineError, match="format_id"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_requires_the_pinned_seed_namespace(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["seed_base"] = "some-other-namespace"
    with pytest.raises(BaselineError, match="seed_base"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_requires_the_canonical_hero_path(tmp_path):
    """P1 (review): the hero path is pinned, not caller-controlled. A different existing hero file
    with a correctly co-updated hash must be refused, because it is not the canonical hero."""
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["hero_team_path"] = "showdown_bot/teams/fixed_team.txt"  # a real, different hero
    with pytest.raises(BaselineError, match="hero_team_path"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_requires_each_opponent_path_under_the_canonical_holdout_dir(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    tid = m["opponent_teams"][0]["team_id"]
    m["opponent_teams"][0]["team_path"] = f"showdown_bot/teams/panel_champions_v0/{tid}.txt"
    with pytest.raises(BaselineError, match="team_path|holdout"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_requires_pythonhashseed_zero(tmp_path):
    """P1 (review): pythonhashseed was a dead field -- loaded as a non-empty string, never checked."""
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["pythonhashseed"] = "not-zero"
    with pytest.raises(BaselineError, match="pythonhashseed"):
        load_strength_holdout_baseline(_write(tmp_path, m))


@pytest.mark.parametrize("count", [5, 7])
def test_specific_loader_requires_exactly_six_opponent_teams(tmp_path, count):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    if count < 6:
        m["opponent_teams"] = m["opponent_teams"][:count]
    else:
        m["opponent_teams"] = m["opponent_teams"] + [dict(m["opponent_teams"][0], team_id="extra",
                                                          team_path=f"{HOLDOUT_TEAMS_DIR}extra.txt")]
    with pytest.raises(BaselineError, match="six|6"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_rejects_an_unknown_field_inside_a_team_entry(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][0]["source_team_id"] = "PC1102"
    with pytest.raises(BaselineError, match="unknown|source_team_id"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_rejects_a_duplicated_team_entry(tmp_path):
    # With paths pinned to HOLDOUT_TEAMS_DIR + team_id, a duplicate path can only arise from a
    # duplicate id, so a genuine duplicate is a fully-copied entry -- caught by the id check.
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][1] = dict(m["opponent_teams"][0])
    with pytest.raises(BaselineError, match="duplicate"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_still_guards_duplicate_ids_independently_of_path_geometry(tmp_path):
    # The duplicate-id check must not silently depend on the path check: even if a future edit
    # relaxed the path pin, two teams sharing an id must still be rejected. Force that by giving
    # the collided entry a geometry-valid path for ITS (duplicated) id.
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    dup_id = m["opponent_teams"][0]["team_id"]
    m["opponent_teams"][1]["team_id"] = dup_id
    m["opponent_teams"][1]["team_path"] = f"{HOLDOUT_TEAMS_DIR}{dup_id}.txt"
    with pytest.raises(BaselineError, match="duplicate"):
        load_strength_holdout_baseline(_write(tmp_path, m))


# --- loader: load-error wrapping (P1 review) ---------------------------------------------------


def test_specific_loader_wraps_a_missing_file_as_baseline_error(tmp_path):
    with pytest.raises(BaselineError, match="not.*read|No such|cannot"):
        load_strength_holdout_baseline(str(tmp_path / "does_not_exist.json"))


def test_specific_loader_wraps_broken_json_as_baseline_error(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"schema_version": 1,', encoding="utf-8")  # truncated
    with pytest.raises(BaselineError, match="JSON|json"):
        load_strength_holdout_baseline(str(p))


def test_specific_loader_wraps_invalid_utf8_as_baseline_error(tmp_path):
    p = tmp_path / "b.json"
    p.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(BaselineError, match="utf-8|decode|encoding"):
        load_strength_holdout_baseline(str(p))


# --- verifier: static pins re-derived from the checkout ----------------------------------------


def test_specific_verifier_passes_against_a_matching_checkout(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    checks = _verify(repo, _good_manifest(repo, ids))
    assert checks and all(c.ok for c in checks)
    names = {c.name for c in checks}
    for expected in ("panel_hash", "hero_team_hash", "opponent_team_hashes", "schedule_hash",
                     "seed_base", "format_id", "showdown_commit", "server_patch_hash",
                     "holdout_manifest"):
        assert expected in names, expected


def test_specific_verifier_detects_panel_hash_drift(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["panel_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="panel_hash"):
        _verify(repo, m)


def test_specific_verifier_detects_hero_team_hash_drift(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["hero_team_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="hero_team_hash"):
        _verify(repo, m)


def test_specific_verifier_detects_a_wrongly_hashed_opponent_team(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][2]["team_content_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="opponent_team_hashes|holdout_manifest"):
        _verify(repo, m)


def test_specific_verifier_detects_schedule_hash_drift(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["schedule_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="schedule_hash"):
        _verify(repo, m)


def test_specific_verifier_rebuilds_the_canonical_180_key_schedule(tmp_path):
    from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule
    from showdown_bot.eval.panel import load_panel

    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    panel = load_panel(str(repo / "config/eval/panels/panel_champions_strength_holdout_v0.yaml"),
                       teams_root=str(repo))
    rebuilt = build_strength_holdout_schedule(
        holdout_team_ids=sorted(ids), panel_hash=panel.panel_hash, seed_base=SEED_BASE)
    assert len(rebuilt.battle_keys) == 180
    assert m["schedule_hash"] == rebuilt.schedule_hash
    assert all(c.ok for c in _verify(repo, m))


def test_specific_verifier_detects_showdown_commit_drift(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["showdown_commit"] = "deadbeef"
    with pytest.raises(BaselineDriftError, match="showdown_commit"):
        _verify(repo, m)


def test_specific_verifier_detects_server_patch_hash_drift(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["server_patch_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="server_patch_hash"):
        _verify(repo, m)


def test_specific_verifier_reports_every_failed_check_not_just_the_first(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["panel_hash"] = "0" * 16
    m["hero_team_hash"] = "1" * 16
    m["showdown_commit"] = "deadbeef"
    with pytest.raises(BaselineDriftError) as excinfo:
        _verify(repo, m)
    message = str(excinfo.value)
    for name in ("panel_hash", "hero_team_hash", "showdown_commit"):
        assert name in message


# --- verifier: holdout-manifest binding (P1 review) --------------------------------------------


def test_specific_verifier_binds_the_authoritative_holdout_manifest(tmp_path):
    """Baseline + panel agreeing is not enough -- both could be changed together to a DIFFERENT
    six teams while the authoritative holdout manifest is unchanged. The verifier must catch that.
    """
    from showdown_bot.eval.panel import team_content_hash

    repo, ids = _fixture_repo(tmp_path)
    # Add a seventh committed team and repoint BOTH baseline and panel opponent[0] at it, leaving
    # the holdout manifest untouched.
    other = repo / f"{HOLDOUT_TEAMS_DIR}other"
    other.with_suffix(".txt").write_text("Other Mon @ Sitrus Berry\n", encoding="utf-8")
    other.with_suffix(".packed").write_text("|OtherA|||||||||]|OtherB|||||||||", encoding="utf-8")
    other_hash = team_content_hash(str(repo), f"{HOLDOUT_TEAMS_DIR}other.txt")

    import yaml
    panel_path = repo / "config/eval/panels/panel_champions_strength_holdout_v0.yaml"
    panel = yaml.safe_load(panel_path.read_text(encoding="utf-8"))
    panel["dev_teams"][0] = {"team_id": "other", "team_path": f"{HOLDOUT_TEAMS_DIR}other.txt", "archetype": "x"}
    panel_path.write_text(yaml.safe_dump(panel, sort_keys=False), encoding="utf-8")

    m = _good_manifest(repo, ids)  # rebuilt against the mutated panel -> panel/schedule self-consistent
    with pytest.raises(BaselineDriftError, match="holdout_manifest"):
        _verify(repo, m)


def test_specific_verifier_fails_when_the_holdout_manifest_is_missing(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    (repo / STRENGTH_HOLDOUT_MANIFEST_PATH).unlink()
    with pytest.raises(BaselineDriftError, match="holdout_manifest"):
        _verify(repo, m)


def test_specific_verifier_fails_when_the_holdout_manifest_is_malformed(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    (repo / STRENGTH_HOLDOUT_MANIFEST_PATH).write_text("{ broken", encoding="utf-8")
    with pytest.raises(BaselineDriftError, match="holdout_manifest"):
        _verify(repo, m)


# --- the generic contract is untouched ----------------------------------------------------------


def test_the_generic_required_fields_are_unchanged_by_the_specific_contract():
    from showdown_bot.eval.baseline import _REQUIRED_FIELDS

    assert _REQUIRED_FIELDS == frozenset({
        "baseline_id", "config_id", "config_hash", "git_sha", "panel_version", "panel_hash",
        "dev_schedule_hash", "dev_schedule_path", "hero_team_hash", "opp_team_hashes",
        "showdown_commit", "server_patch_hash", "seed_base", "pythonhashseed",
        "reference_jsonl", "reference_sha256",
    })


def test_the_committed_manifest_loads_under_the_closed_loader():
    # Task 13 step 3: the committed manifest is now the REAL closed-schema baseline, so the closed
    # loader accepts it (the generic loader refuses it -- see the top of this file). Its clean
    # verify against the real repo tree is in test_strength_holdout_freeze.py.
    loaded = load_strength_holdout_baseline(str(_MANIFEST_PATH))
    assert loaded["baseline_id"] == "champions-strength-holdout-v0"
    assert loaded["hero_agent"] == "max_damage"


# --- review-fix round 2 ------------------------------------------------------------------------


def test_specific_verifier_requires_a_closed_1_to_6_selection_order(tmp_path):
    """P2: unique selection_index is not enough -- it must be exactly {1..6}, so the frozen
    selection order is fully pinned and no index can be dropped, repeated by value, or renumbered."""
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    man_path = repo / STRENGTH_HOLDOUT_MANIFEST_PATH
    man = json.loads(man_path.read_text(encoding="utf-8"))
    man["teams"] = sorted(man["teams"], key=lambda t: t["selection_index"])
    man["teams"][5]["selection_index"] = 99  # unique, but not a closed 1..6 set
    man_path.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(BaselineDriftError, match="holdout_manifest"):
        _verify(repo, m)

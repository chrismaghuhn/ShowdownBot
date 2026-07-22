# showdown_bot/tests/test_baseline_strength_holdout.py
"""Gate B (Champions strength-holdout) baseline manifest -- Task 6.

This manifest is deliberately a schema-loadable PLACEHOLDER, not a frozen baseline proof and
not a strength result: every hash/path field that depends on real panel/schedule/team/reference
content is an intentional empty string (or an empty ``opp_team_hashes`` mapping) until Task 13
seals the six holdout teams, builds the real panel/schedule, and records real reference data.
``load_baseline`` must accept it (the schema is satisfied); ``verify_baseline`` must refuse it
(fail-closed) for exactly that reason -- there is nothing real yet to verify against.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.eval.baseline import BaselineDriftError, BaselineError, load_baseline, verify_baseline

_REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/ -> showdown_bot/ -> <repo>
_MANIFEST_PATH = _REPO_ROOT / "config" / "eval" / "baselines" / "champions-strength-holdout-v0.json"


def test_manifest_has_every_required_field():
    # load_baseline itself enforces the full required-field set (BaselineError on any missing
    # field) -- a successful load is the proof, not a duplicated field list here.
    baseline = load_baseline(str(_MANIFEST_PATH))
    assert "hero_team_path" in baseline


def test_manifest_baseline_id_identifies_this_gate():
    baseline = load_baseline(str(_MANIFEST_PATH))
    assert baseline["baseline_id"] == "champions-strength-holdout-v0"


def test_manifest_uses_the_champions_hero_path():
    # Task 6 grounding P1: the Reg-I default hero ("teams/fixed_team.txt") is the WRONG hero for
    # Gate B -- Champions plays "teams/fixed_champions_v0.txt". This manifest must carry that
    # explicit override, or a future verify_baseline run (once Task 13 fills in the rest) would
    # hash the wrong team entirely.
    baseline = load_baseline(str(_MANIFEST_PATH))
    assert baseline["hero_team_path"] == "teams/fixed_champions_v0.txt"


def test_manifest_is_distinct_from_the_reg_i_manifest():
    reg_i_path = _REPO_ROOT / "config" / "eval" / "baselines" / "heuristic-v1.json"
    champions_baseline = load_baseline(str(_MANIFEST_PATH))
    reg_i_baseline = load_baseline(str(reg_i_path))
    assert champions_baseline["baseline_id"] != reg_i_baseline["baseline_id"]
    assert champions_baseline != reg_i_baseline


def test_load_baseline_rejects_a_manifest_missing_a_required_field(tmp_path):
    with open(_MANIFEST_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    del data["config_hash"]
    incomplete_path = tmp_path / "incomplete.json"
    incomplete_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BaselineError):
        load_baseline(str(incomplete_path))


def test_placeholder_manifest_refuses_verification_fail_closed():
    # THIS IS NOT A FROZEN BASELINE PROOF AND NOT A STRENGTH RESULT. Every hash/path field that
    # depends on real content (panel_hash, hero_team_hash, dev_schedule_hash/dev_schedule_path,
    # showdown_commit, server_patch_hash, reference_sha256/reference_jsonl) is a deliberate empty
    # placeholder -- load_baseline succeeds (the manifest is schema-loadable), but
    # verify_baseline must refuse, fail-closed, against the REAL repo tree. Multiple fields are
    # deliberately invalid at once, so no single specific drift cause is asserted here -- only
    # that verification refuses, exactly as it must until Task 13 lands real panel/schedule/team/
    # reference content and this placeholder is superseded by a real, frozen manifest.
    baseline = load_baseline(str(_MANIFEST_PATH))
    with pytest.raises(BaselineDriftError):
        verify_baseline(baseline, repo_root=str(_REPO_ROOT))


# =============================================================================================
# Gate-B-specific STATIC baseline contract (spec Amendment A1.3).
#
# The generic T6 contract freezes a heuristic policy's *reference run*: it requires
# reference_jsonl/reference_sha256 and a loadable YAML dev_schedule_path. Neither can exist for
# Gate B -- a result file cannot predate the run it describes, and Gate B's schedule is generated
# from code, not YAML. This contract instead freezes Baseline B (max_damage) and its STATIC
# environment, before the run. The generic loader/verifier are untouched.
# =============================================================================================
import copy
import subprocess

from showdown_bot.eval.baseline import (
    load_strength_holdout_baseline, verify_strength_holdout_baseline,
)

HERO = "teams/fixed_champions_v0.txt"
FORMAT_ID = "gen9championsvgc2026regma"
SEED_BASE = "champions-strength-holdout-v0"


def _packed_for(txt: str) -> str:
    return txt[:-4] + ".packed"


def _fixture_repo(tmp_path):
    """An isolated repo with a panel, a hero team and six opponent teams -- no live data."""
    import yaml
    from showdown_bot.eval.panel import team_content_hash

    repo = tmp_path / "repo"
    teams = repo / "showdown_bot" / "teams"
    holdout_dir = teams / "panel_champions_strength_holdout_v0"
    holdout_dir.mkdir(parents=True)
    (teams / "fixed_champions_v0.txt").write_text("Hero Mon @ Leftovers\n", encoding="utf-8")
    (teams / "fixed_champions_v0.packed").write_text("|HeroMon|||||||||", encoding="utf-8")

    ids = [f"t{i}" for i in range(6)]
    for i, tid in enumerate(ids):
        (holdout_dir / f"{tid}.txt").write_text(f"Mon{i} @ Focus Sash\n", encoding="utf-8")
        (holdout_dir / f"{tid}.packed").write_text(f"|Mon{i}A|||||||||]|Mon{i}B|||||||||", encoding="utf-8")

    panel_dir = repo / "config" / "eval" / "panels"
    panel_dir.mkdir(parents=True)
    panel = {
        "version": "champions_strength_holdout_v0",
        "policies": ["heuristic", "max_damage"],
        "dev_teams": [
            {"team_id": t, "team_path": f"teams/panel_champions_strength_holdout_v0/{t}.txt",
             "archetype": f"a{i}"} for i, t in enumerate(ids[:3])
        ],
        "heldout_teams": [
            {"team_id": t, "team_path": f"teams/panel_champions_strength_holdout_v0/{t}.txt",
             "archetype": f"a{i}"} for i, t in enumerate(ids[3:], start=3)
        ],
    }
    (panel_dir / "panel_champions_strength_holdout_v0.yaml").write_text(
        yaml.safe_dump(panel, sort_keys=False), encoding="utf-8")

    prov = repo / "config" / "eval"
    (prov / "provenance.yaml").write_text("showdown_commit: abc123def456\n", encoding="utf-8")
    patch_dir = repo / "tools" / "eval" / "patches"
    patch_dir.mkdir(parents=True)
    (patch_dir / "pokemon-showdown-seeded-battle.patch").write_text("--- fixture patch ---\n", encoding="utf-8")
    return repo, ids


def _good_manifest(repo, ids):
    from showdown_bot.eval.panel import load_panel, team_content_hash
    from showdown_bot.eval.run_manifest import load_showdown_commit, server_patch_hash
    from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule

    teams_root = str(repo / "showdown_bot")
    panel = load_panel(str(repo / "config/eval/panels/panel_champions_strength_holdout_v0.yaml"),
                       teams_root=teams_root)
    schedule = build_strength_holdout_schedule(
        holdout_team_ids=sorted(ids), panel_hash=panel.panel_hash, seed_base=SEED_BASE)
    return {
        "schema_version": 1,
        "baseline_id": "champions-strength-holdout-v0",
        "hero_agent": "max_damage",
        "format_id": FORMAT_ID,
        "panel_version": "champions_strength_holdout_v0",
        "panel_hash": panel.panel_hash,
        "hero_team_path": HERO,
        "hero_team_hash": team_content_hash(teams_root, HERO),
        "opponent_teams": [
            {"team_id": t,
             "team_path": f"teams/panel_champions_strength_holdout_v0/{t}.txt",
             "team_content_hash": team_content_hash(
                 teams_root, f"teams/panel_champions_strength_holdout_v0/{t}.txt")}
            for t in sorted(ids)
        ],
        "schedule_hash": schedule.schedule_hash,
        "seed_base": SEED_BASE,
        "showdown_commit": load_showdown_commit(str(repo / "config/eval/provenance.yaml")),
        "server_patch_hash": server_patch_hash(
            str(repo / "tools/eval/patches/pokemon-showdown-seeded-battle.patch")),
        "pythonhashseed": "0",
    }


def _write(tmp_path, manifest, name="baseline.json"):
    p = tmp_path / name
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(p)


# --- loader: closed schema ---------------------------------------------------------------------


def test_specific_loader_rejects_non_object_json(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(BaselineError, match="object"):
        load_strength_holdout_baseline(str(p))


def test_specific_loader_accepts_a_well_formed_manifest(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    loaded = load_strength_holdout_baseline(_write(tmp_path, _good_manifest(repo, ids)))
    assert loaded["hero_agent"] == "max_damage"
    assert len(loaded["opponent_teams"]) == 6


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
    """A1.3: this contract is static pre-run data only -- no result artifact, no caller SHA."""
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


@pytest.mark.parametrize("field", ["baseline_id", "panel_hash", "hero_team_path", "schedule_hash"])
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


@pytest.mark.parametrize("count", [5, 7])
def test_specific_loader_requires_exactly_six_opponent_teams(tmp_path, count):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    entry = m["opponent_teams"][0]
    m["opponent_teams"] = (m["opponent_teams"] * 2)[:count] if count > 6 else m["opponent_teams"][:count]
    if count > 6:
        m["opponent_teams"] = m["opponent_teams"][:6] + [dict(entry, team_id="extra")]
    with pytest.raises(BaselineError, match="six|6"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_rejects_an_unknown_field_inside_a_team_entry(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][0]["source_team_id"] = "PC1102"
    with pytest.raises(BaselineError, match="unknown|source_team_id"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_rejects_duplicate_team_ids(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][1]["team_id"] = m["opponent_teams"][0]["team_id"]
    with pytest.raises(BaselineError, match="duplicate"):
        load_strength_holdout_baseline(_write(tmp_path, m))


def test_specific_loader_rejects_duplicate_team_paths(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][1]["team_path"] = m["opponent_teams"][0]["team_path"]
    with pytest.raises(BaselineError, match="duplicate"):
        load_strength_holdout_baseline(_write(tmp_path, m))


# --- verifier: every static pin re-derived from the checkout -----------------------------------


def _verify(repo, manifest):
    return verify_strength_holdout_baseline(
        manifest, repo_root=str(repo), teams_root=str(repo / "showdown_bot"))


def test_specific_verifier_passes_against_a_matching_checkout(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    checks = _verify(repo, _good_manifest(repo, ids))
    assert checks and all(c.ok for c in checks)
    names = {c.name for c in checks}
    for expected in ("panel_hash", "hero_team_hash", "opponent_team_hashes", "schedule_hash",
                     "seed_base", "format_id", "showdown_commit", "server_patch_hash"):
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


def test_specific_verifier_detects_a_hero_path_that_does_not_exist(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["hero_team_path"] = "teams/not_a_real_hero.txt"
    with pytest.raises(BaselineDriftError, match="hero"):
        _verify(repo, m)


def test_specific_verifier_detects_a_wrongly_hashed_opponent_team(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][2]["team_content_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="opponent_team_hashes"):
        _verify(repo, m)


def test_specific_verifier_detects_an_opponent_team_absent_from_the_panel(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["opponent_teams"][0]["team_id"] = "not_in_panel"
    with pytest.raises(BaselineDriftError, match="opponent_team_hashes"):
        _verify(repo, m)


def test_specific_verifier_detects_schedule_hash_drift(tmp_path):
    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    m["schedule_hash"] = "0" * 16
    with pytest.raises(BaselineDriftError, match="schedule_hash"):
        _verify(repo, m)


def test_specific_verifier_rebuilds_the_canonical_180_key_schedule(tmp_path):
    """The schedule hash must be REBUILT from the panel's six teams, not trusted."""
    from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule
    from showdown_bot.eval.panel import load_panel

    repo, ids = _fixture_repo(tmp_path)
    m = _good_manifest(repo, ids)
    panel = load_panel(str(repo / "config/eval/panels/panel_champions_strength_holdout_v0.yaml"),
                       teams_root=str(repo / "showdown_bot"))
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


# --- the generic contract is untouched ----------------------------------------------------------


def test_the_generic_required_fields_are_unchanged_by_the_specific_contract():
    from showdown_bot.eval.baseline import _REQUIRED_FIELDS

    assert _REQUIRED_FIELDS == frozenset({
        "baseline_id", "config_id", "config_hash", "git_sha", "panel_version", "panel_hash",
        "dev_schedule_hash", "dev_schedule_path", "hero_team_hash", "opp_team_hashes",
        "showdown_commit", "server_patch_hash", "seed_base", "pythonhashseed",
        "reference_jsonl", "reference_sha256",
    })


def test_the_committed_placeholder_manifest_never_yields_a_false_pass():
    """Until Step 3 fills it with real values it must be REFUSED, not quietly accepted."""
    with pytest.raises(BaselineError):
        load_strength_holdout_baseline(str(_MANIFEST_PATH))

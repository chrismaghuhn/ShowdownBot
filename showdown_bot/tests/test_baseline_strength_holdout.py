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

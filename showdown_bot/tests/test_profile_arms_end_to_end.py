"""C3 arm-by-arm proof: every §4 arm is CONSTRUCTIBLE and runs end-to-end through the real
scoring path, producing rows that pass both validator tiers.

This is what unblocks the six arms C2 recorded as unconstructible (P-1..P-5). The proof is a
test, not a run: reps are tiny and passed explicitly (no default), and everything writes into
tmp_path. It freezes no evidence, measures no latency, and starts no battle.

The boards and the production-topology ``ProfileSession`` this proof used to define inline now
live in ``showdown_bot.eval.profile_fixtures`` -- promoted so the microprofile runner can import
them without a runner ever reaching into ``tests/``. This module now CONSUMES that single
implementation (no second copy) and keeps the arm-by-arm assertions unchanged.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval import profile_fixtures as pf
from showdown_bot.eval.decision_profile import (
    profile_manifest_hash,
    validate_decision_profile_dataset,
    validate_decision_profile_row,
)
from showdown_bot.eval.profile_arms import PROFILE_ARMS, arm_specs
from showdown_bot.eval.profile_harness import run_arm
from showdown_bot.eval.profile_manifest import build_profile_manifest

FORMAT = pf.FORMAT


def _manifest():
    specs = arm_specs(pf.FIXTURE_HASHES, reps=1)
    return build_profile_manifest(agent="heuristic", format_id=FORMAT, arms=specs)


def _arm_by_design(design_arm: str):
    return next(a for a in PROFILE_ARMS if a.design_arm == design_arm)


def _run_one_arm(arm, manifest, *, reps):
    """Run one arm through the harness with its own fresh sessions, closing them after."""
    mhash = profile_manifest_hash(manifest)
    entry = next(e for e in manifest["arms"] if e["arm_id"] == arm.arm_id)
    built: list[pf.ProfileSession] = []

    def factory():
        s = pf.make_session(arm.fixture)
        built.append(s)
        return s

    try:
        rows = run_arm(
            arm, factory, agent="heuristic", format_id=FORMAT, config_id="c3-proof",
            git_sha=manifest["git_sha"], config_hash=entry["effective_config_hash"],
            profile_manifest_hash=mhash, reps=reps,
            behavior_env=entry["behavior_env"],   # from the manifest arm, mandatory
        )
    finally:
        for s in built:
            s.close()
    return rows


# The six arms C2 recorded as unconstructible -- the C3 deliverable.
_C3_ARMS = ["5", "7", "8", "10", "13b", "14"]


@pytest.mark.parametrize("design_arm", _C3_ARMS)
def test_each_c3_arm_is_constructible_and_its_rows_validate(design_arm):
    """Each formerly-blocked arm builds a coherent board, runs the REAL scoring path through
    the harness, and every row it emits passes the per-row validator."""
    manifest = _manifest()
    arm = _arm_by_design(design_arm)
    rows = _run_one_arm(arm, manifest, reps=1)
    assert rows, f"arm {arm.arm_id} produced no rows"
    for row in rows:
        validate_decision_profile_row(row, manifest=manifest)   # raises on any violation
    r = rows[0]
    assert r["source"] == "microprofile"
    assert r["timer_scope"] == arm.timer_scope
    assert r["outcome"] == "ok", f"arm {arm.arm_id} crashed: {r}"


def test_foe_mega_arms_actually_reach_the_foe_mega_path():
    """The point of arms 5/7/8/10 is a foe-Mega hypothesis that really composes. Prove the
    branches are non-empty -- otherwise the arm would be measuring the no-mega path under a
    foe-mega label."""
    manifest = _manifest()
    for design_arm in ["5", "7", "8", "10"]:
        arm = _arm_by_design(design_arm)
        rows = _run_one_arm(arm, manifest, reps=1)
        assert rows[0]["foe_mega_active"], f"arm {arm.arm_id} did not reach the foe-Mega path"
        assert rows[0]["n_mega_twins"] > 0


def test_arm_12_reaches_the_depth2_frontier():
    """§4 arm 12 is depth-2 with the foe-Mega frontier actually reached (TOPM>=4). Its rows
    must report depth2_frontier > 0 -- the count that was provably wrong when the shape was
    hard-coded 0. The arm's env (SEARCH_DEPTH=2, TOPM=4) flows through run_arm's boundary into
    the real scoring path, and the at-origin sink counts the refinements."""
    manifest = _manifest()
    rows = _run_one_arm(_arm_by_design("12"), manifest, reps=1)
    assert rows[0]["depth2_frontier"] > 0, rows[0]


def test_persistent_cold_and_warm_differ_in_backend_class():
    """13b (cold) and 14 (warm) at the wide scope must land on opposite sides of the backend
    contrast: cold spawns inside the window (clean_cold), warm is already alive (clean_warm).
    This is the P-5 payoff -- a shared backend measured at contexts_and_score."""
    manifest = _manifest()
    cold = _run_one_arm(_arm_by_design("13b"), manifest, reps=1)
    warm = _run_one_arm(_arm_by_design("14"), manifest, reps=1)
    assert cold[0]["backend_class"] == "clean_cold", cold[0]
    assert warm[0]["backend_class"] == "clean_warm", warm[0]


def test_the_whole_matrix_writes_a_dataset_that_passes_the_dataset_validator(tmp_path):
    """End to end, into tmp only: every runnable arm -> harness rows -> the dataset tier.

    This is the strongest single check: the dataset validator re-runs the per-row validator
    on every row AND enforces the cross-row identities (per-arm backend/cache lifecycle,
    fixture -> constant n_candidates). tmp_path, deliberately: this slice freezes no evidence.
    """
    manifest = _manifest()
    out = tmp_path / "profile.jsonl"
    with open(out, "a", encoding="utf-8", newline="") as fh:
        for arm in PROFILE_ARMS:
            rows = _run_one_arm(arm, manifest, reps=2)
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    report = validate_decision_profile_dataset(str(out), manifest)
    assert report["arms"], "no arms in the report"
    assert report["rows"] == 2 * len(PROFILE_ARMS)
    # cold arms are clean_cold or oneshot; the one warm arm contributes clean_warm.
    assert report["backend_class_counts"].get("clean_warm", 0) >= 1

"""I8-C Task C2 — the arm matrix: complete, unique, ordered, and the only road to a manifest.

Design §4. The matrix is pure declaration and lives in src/ so it can be unit-tested,
following the convention `scripts/run_cap_latency_sweep.py` states for itself: pure logic
belongs in a module, imported by the driver, "rather than as a private helper in this
driver script".

COMPLETENESS is the load-bearing property. §4 audits 15 arm rows and finds six of them
unconstructible today (P-1…P-5). An arm that is simply absent from the matrix reads as
"covered" to anyone counting; the design's §5 forbids exactly that ("None is silently
skipped … §5 forbids a bounded coverage claim that reads as complete"). So every §4 arm is
either RUNNABLE or BLOCKED-with-its-blocker, and the test below asserts the partition.
"""

from __future__ import annotations

import pytest

from showdown_bot.eval.profile_arms import (
    BLOCKED_ARMS,
    PROFILE_ARMS,
    ArmDecl,
    arm_specs,
    design_arm_ids,
)
from showdown_bot.eval.profile_manifest import ArmSpec


# ==========================================================================
# completeness: every §4 arm is accounted for, one way or the other
# ==========================================================================


def test_every_design_arm_is_either_runnable_or_blocked():
    runnable = {a.design_arm for a in PROFILE_ARMS}
    blocked = set(BLOCKED_ARMS)
    assert runnable | blocked == set(design_arm_ids())
    assert not (runnable & blocked), "an arm cannot be both runnable and blocked"


def test_no_design_arm_is_silently_missing():
    missing = set(design_arm_ids()) - {a.design_arm for a in PROFILE_ARMS} - set(BLOCKED_ARMS)
    assert not missing, f"§4 arms accounted for nowhere: {sorted(missing)}"


def test_every_blocked_arm_names_its_blocker():
    # "dropped with its blocker named" -- a bare exclusion list would read as a decision
    # nobody has to justify.
    for arm_id, reason in BLOCKED_ARMS.items():
        assert reason.startswith("P-"), f"{arm_id}: {reason!r} does not name a P-blocker"
        assert len(reason) > 6, f"{arm_id}: blocker reason is not a reason"


def test_the_blocked_set_is_exactly_the_designs_five_blockers():
    # P-1 slot 1, P-2 no-own-Mega board, P-3 unequal-speed decision board, P-4 Trick Room,
    # P-5 fixtures do not share the backend (13b cold and 14 warm).
    assert set(BLOCKED_ARMS) == {"5", "7", "8", "10", "13b", "14"}


# ==========================================================================
# uniqueness
# ==========================================================================


def test_arm_ids_are_unique():
    ids = [a.arm_id for a in PROFILE_ARMS]
    assert len(ids) == len(set(ids))


def test_design_arms_are_unique():
    refs = [a.design_arm for a in PROFILE_ARMS]
    assert len(refs) == len(set(refs))


def test_arm_ids_are_stable_and_readable():
    for a in PROFILE_ARMS:
        assert a.arm_id and a.arm_id == a.arm_id.strip()
        assert " " not in a.arm_id


# ==========================================================================
# order
# ==========================================================================


def test_the_matrix_order_is_deterministic():
    assert [a.arm_id for a in PROFILE_ARMS] == [a.arm_id for a in PROFILE_ARMS]


def test_the_matrix_follows_the_designs_arm_order():
    # Not cosmetic: the manifest's `arms` is a LIST, so its order is part of the artifact
    # and of its hash. Anchoring it to §4's own order keeps the manifest diffable against
    # the design by eye, and keeps the hash from moving when someone re-sorts a literal.
    order = design_arm_ids()
    positions = [order.index(a.design_arm) for a in PROFILE_ARMS]
    assert positions == sorted(positions)


# ==========================================================================
# per-arm values: lifecycle, warmup, scoring, environment
# ==========================================================================


def test_every_arm_declares_a_complete_lifecycle():
    for a in PROFILE_ARMS:
        assert set(a.lifecycle) == {
            "calc_backend", "damage_oracle", "speed_oracle", "species_dex",
            "contexts_and_variants",
        }, a.arm_id


def test_every_arms_three_caches_share_one_lifecycle():
    # §2.8: the constraint that keeps expected_cache_class total.
    for a in PROFILE_ARMS:
        declared = {a.lifecycle[k] for k in ("damage_oracle", "speed_oracle", "species_dex")}
        assert len(declared) == 1, f"{a.arm_id}: caches disagree {declared}"


def test_no_cold_cache_arm_warms_up():
    # §2.8: a cold-cache arm that warms up is a contradiction; its caches are discarded.
    for a in PROFILE_ARMS:
        if a.lifecycle["damage_oracle"] == "per_rep":
            assert a.warmup == 0, f"{a.arm_id} is cold-cache but declares warmup={a.warmup}"


def test_reps_is_a_run_parameter_not_an_arm_property():
    """An arm cannot choose its own rep count.

    An earlier cut carried reps=30 per arm -- a number neither the spec nor the plan states,
    invented here and then readable back as though the design had asked for it. It is fixed
    in advance by whoever authorizes the run, uniformly, because a per-arm count would be an
    unlogged lever on which arm looks cheap.
    """
    for a in PROFILE_ARMS:
        assert not hasattr(a, "reps"), f"{a.arm_id} declares its own reps"


@pytest.mark.parametrize("bad", [0, -1, None, "30", 1.5, True])
def test_arm_specs_rejects_a_non_positive_reps(bad):
    with pytest.raises((ValueError, TypeError)):
        arm_specs({a.fixture: "h" for a in PROFILE_ARMS}, reps=bad)


def test_arm_specs_has_no_default_reps():
    with pytest.raises(TypeError):
        arm_specs({a.fixture: "h" for a in PROFILE_ARMS})


def test_the_click_rate_arms_declare_the_designs_rates():
    rates = {a.design_arm: a.env.get("SHOWDOWN_OPP_MEGA_CLICK_RATE") for a in PROFILE_ARMS}
    assert rates["2"] == "0.0", "arm 2 is the inertness control: rate 0.0"
    assert rates["3"] == "0.35", "arm 3 is the default rate"


def test_the_depth2_arm_raises_TOPM_because_the_default_never_reaches_the_frontier():
    # §4 arm 12's measured fact: at the default TOPM=2 and rate 0.35 the top-M frontier is
    # all-no-mega, so the foe-Mega depth-2 path is NEVER reached. An arm 12 at TOPM=2 would
    # measure depth-1 wearing a depth-2 label.
    arm12 = next(a for a in PROFILE_ARMS if a.design_arm == "12")
    assert arm12.env["SHOWDOWN_SEARCH_DEPTH"] == "2"
    assert int(arm12.env["SHOWDOWN_SEARCH_TOPM"]) >= 4


def test_the_oneshot_arm_declares_the_oneshot_backend():
    arm13a = next(a for a in PROFILE_ARMS if a.design_arm == "13a")
    assert arm13a.env["SHOWDOWN_CALC_BACKEND"] == "oneshot"


# ==========================================================================
# ArmSpec is the ONLY road to the producer
# ==========================================================================


def test_arm_specs_returns_ArmSpecs():
    specs = arm_specs({a.fixture: "fix-" + a.fixture for a in PROFILE_ARMS}, reps=30)
    assert specs and all(isinstance(s, ArmSpec) for s in specs)


def test_arm_specs_preserves_the_matrix_order():
    specs = arm_specs({a.fixture: "fix-" + a.fixture for a in PROFILE_ARMS}, reps=30)
    assert [s.arm_id for s in specs] == [a.arm_id for a in PROFILE_ARMS]


def test_arm_specs_refuses_an_unresolved_fixture():
    # A missing fixture hash must fail closed rather than produce an arm whose
    # fixture_input_hash is None -- which would sail through as "a hash" and bind nothing.
    with pytest.raises(KeyError):
        arm_specs({}, reps=30)


def test_behavior_env_is_derived_by_the_shared_function_not_hand_filtered():
    """The arm's behavior_env is config_env.behavior_env() of its declared env.

    Hand-filtering it here would be a second classification of the same vars, free to
    disagree with the one config_hash actually uses -- and the arm's effective_config_hash
    is computed FROM this mapping.
    """
    from showdown_bot.eval.config_env import behavior_env

    for a, s in zip(PROFILE_ARMS, arm_specs({x.fixture: "h" for x in PROFILE_ARMS}, reps=30)):
        assert s.behavior_env == behavior_env(a.env)


def test_non_behavioral_and_excluded_knobs_stay_out_of_behavior_env_but_are_recorded():
    """SHOWDOWN_CALC_BACKEND is NON_BEHAVIORAL and TOPM/TOPN are EXCLUDED_BY_REASON, so
    neither moves config_hash -- which is exactly what makes cold/warm arms comparable.
    They must still be recorded, or the difference between two arms becomes invisible.
    """
    specs = {s.arm_id: s for s in arm_specs({a.fixture: "h" for a in PROFILE_ARMS}, reps=30)}
    a13a = next(a for a in PROFILE_ARMS if a.design_arm == "13a")
    s = specs[a13a.arm_id]
    assert "SHOWDOWN_CALC_BACKEND" not in s.behavior_env
    assert s.arm_params["SHOWDOWN_CALC_BACKEND"] == "oneshot"

    a12 = next(a for a in PROFILE_ARMS if a.design_arm == "12")
    s12 = specs[a12.arm_id]
    assert "SHOWDOWN_SEARCH_TOPM" not in s12.behavior_env
    assert s12.arm_params["SHOWDOWN_SEARCH_TOPM"] == a12.env["SHOWDOWN_SEARCH_TOPM"]


def test_arms_that_differ_only_in_a_non_behavioral_knob_share_a_config_hash():
    # The design's §2.7 note: SHOWDOWN_CALC_BACKEND is NON_BEHAVIORAL, and that is
    # "exactly what makes cold/warm arms comparable".
    from showdown_bot.eval.config_env import behavior_env

    a3 = next(a for a in PROFILE_ARMS if a.design_arm == "3")
    a13a = next(a for a in PROFILE_ARMS if a.design_arm == "13a")
    assert behavior_env(a3.env) == behavior_env(a13a.env)


# ==========================================================================
# the matrix reaches a real manifest
# ==========================================================================


def test_the_matrix_builds_a_valid_manifest_and_roundtrips(tmp_path):
    from showdown_bot.eval.decision_profile import (
        profile_manifest_hash,
        validate_profile_manifest,
    )
    from showdown_bot.eval.profile_manifest import (
        build_profile_manifest,
        read_profile_manifest,
        write_profile_manifest,
    )

    specs = arm_specs({a.fixture: "0123456789abcdef" for a in PROFILE_ARMS}, reps=30)
    manifest = build_profile_manifest(
        agent="heuristic", format_id="gen9championsvgc2026regma", arms=specs
    )
    validate_profile_manifest(manifest)

    out = tmp_path / "manifest.json"  # tmp only: this slice freezes no evidence
    mhash = write_profile_manifest(manifest, str(out))
    assert profile_manifest_hash(read_profile_manifest(str(out))) == mhash
    assert [a["arm_id"] for a in manifest["arms"]] == [a.arm_id for a in PROFILE_ARMS]


def test_every_arm_gets_a_distinct_entry_in_the_manifest():
    from showdown_bot.eval.profile_manifest import build_profile_manifest

    specs = arm_specs({a.fixture: "0123456789abcdef" for a in PROFILE_ARMS}, reps=30)
    m = build_profile_manifest(
        agent="heuristic", format_id="gen9championsvgc2026regma", arms=specs
    )
    ids = [a["arm_id"] for a in m["arms"]]
    assert len(ids) == len(set(ids)) == len(PROFILE_ARMS)


# ==========================================================================
# immutability -- all the way down, because frozen=True is not enough
# ==========================================================================


def test_an_ArmDecl_field_cannot_be_rebound():
    with pytest.raises(Exception):
        PROFILE_ARMS[0].warmup = 99  # type: ignore[misc]


@pytest.mark.parametrize("field", ["env", "scoring_params", "lifecycle"])
def test_an_ArmDecls_mappings_cannot_be_mutated(field):
    """frozen=True blocks REBINDING a field, not mutating what it points at.

    That gap was live: `arm.lifecycle["damage_oracle"] = ...` used to succeed, and every
    manifest built afterwards would have carried the change.
    """
    with pytest.raises(TypeError):
        getattr(PROFILE_ARMS[0], field)["injected"] = "x"


def test_arms_do_not_share_one_lifecycle_object():
    """THE aliasing defect: every cold arm pointed at one _COLD literal.

    So a single mutation did not corrupt one arm -- it corrupted every cold arm at once,
    and each one's manifest entry with it. Read-only proxies are per-arm even when they
    wrap a shared literal, which closes the aliasing as well as the mutation.
    """
    cold = [a for a in PROFILE_ARMS if a.lifecycle["damage_oracle"] == "per_rep"]
    assert len(cold) >= 2
    for other in cold[1:]:
        assert cold[0].lifecycle is not other.lifecycle


def test_BLOCKED_ARMS_cannot_be_edited_at_runtime():
    # A caller able to add or drop an entry could make an arm "covered" or "excused"
    # without anyone amending the design.
    with pytest.raises(TypeError):
        BLOCKED_ARMS["99"] = "injected"
    with pytest.raises(TypeError):
        del BLOCKED_ARMS["5"]


def test_mutating_a_returned_ArmSpec_cannot_reach_back_into_the_matrix():
    specs = arm_specs({a.fixture: "h" for a in PROFILE_ARMS}, reps=30)
    specs[0].lifecycle["damage_oracle"] = "MUTANT"
    assert PROFILE_ARMS[0].lifecycle["damage_oracle"] != "MUTANT"


# ==========================================================================
# A11 <-> A12 moves exactly one knob
# ==========================================================================


def test_A11_and_A12_differ_only_in_search_depth():
    """The depth contrast must be a ONE-knob contrast.

    A12 needs TOPM>=4 to reach the foe-Mega frontier at all, so leaving A11 at the default
    2 made the pair differ in depth AND topm -- a two-variable contrast for no reason. §2.7
    records that TOPM cannot affect output at depth 1 (it is EXCLUDED_BY_REASON precisely
    because of that), so pinning A11 at 4 changes nothing A11 measures.
    """
    a11 = next(a for a in PROFILE_ARMS if a.design_arm == "11")
    a12 = next(a for a in PROFILE_ARMS if a.design_arm == "12")

    differing = {k for k in set(a11.env) | set(a12.env) if a11.env.get(k) != a12.env.get(k)}
    assert differing == {"SHOWDOWN_SEARCH_DEPTH"}
    assert a11.fixture == a12.fixture
    assert a11.lifecycle == a12.lifecycle

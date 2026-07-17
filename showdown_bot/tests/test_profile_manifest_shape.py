"""I8-B correction — the manifest is a LIST of arms, validated in full before any lookup.

Design §2.7 + Erratum 1.

Two defects this replaces, both mine, both found at the C1 checkpoint before a producer
existed to bake them in:

  * B2 read `manifest["arms"][arm_id]` -- a mapping. The design says `arms[]`, "one entry per
    arm", with `arm_id` as a FIELD of the entry (redundant in a mapping: the tell). It is not
    style. A mapping **cannot represent** a duplicate `arm_id` -- `{a["arm_id"]: a for a in …}`
    drops one at construction -- so the duplicate is invisible in the frozen artifact and can
    only ever be caught by trusting the producer. The dataset tier already rests on the
    opposite principle: frozen evidence must not blindly trust the writer that made it.

  * `warmup` was read per-arm by §2.8/§2.4/§5.4 and declared run-level by §2.7's table. Erratum
    1 settles it per-arm and forbids a top-level `warmup`, so the two readings cannot coexist.

Load order is the contract: validate the whole list, THEN index. An index built first would
have to decide what a duplicate means before anything had judged it.
"""

from __future__ import annotations

import pytest

from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    arm_by_id,
    validate_profile_manifest,
)

ARM = "arm-01"
ARM2 = "arm-02"
CFG_HASH = "0123456789abcdef"


def _arm(arm_id=ARM, *, calc_backend="per_rep", cache="per_rep", warmup=0, fixture="fix-a"):
    return {
        "arm_id": arm_id,
        "effective_config_hash": CFG_HASH,
        "warmup": warmup,
        "fixture_input_hash": fixture,
        "reps": 3,
        "lifecycle": {
            "calc_backend": calc_backend,
            "damage_oracle": cache,
            "speed_oracle": cache,
            "species_dex": cache,
            "contexts_and_variants": "per_rep",
        },
    }


def _manifest(*arms):
    return {"arms": list(arms) or [_arm()]}


# ==========================================================================
# shape
# ==========================================================================


def test_a_valid_manifest_indexes_by_arm_id():
    index = validate_profile_manifest(_manifest(_arm(ARM), _arm(ARM2)))
    assert set(index) == {ARM, ARM2}
    assert index[ARM]["arm_id"] == ARM


def test_arms_must_be_a_list_not_a_mapping():
    # The mapping form is exactly what made a duplicate arm_id unrepresentable.
    with pytest.raises(DecisionProfileError, match="list"):
        validate_profile_manifest({"arms": {ARM: _arm(ARM)}})


def test_a_manifest_with_no_arms_is_rejected():
    with pytest.raises(DecisionProfileError, match="no arms"):
        validate_profile_manifest({"arms": []})


def test_an_arm_without_an_arm_id_is_rejected():
    arm = _arm()
    del arm["arm_id"]
    with pytest.raises(DecisionProfileError, match="arm_id"):
        validate_profile_manifest({"arms": [arm]})


def test_an_empty_arm_id_is_rejected():
    with pytest.raises(DecisionProfileError, match="arm_id"):
        validate_profile_manifest({"arms": [_arm("")]})


# ==========================================================================
# the check the list form exists to make possible
# ==========================================================================


def test_a_duplicate_arm_id_is_rejected_fail_closed():
    """THE reason `arms` is a list.

    Two entries, same id. In the mapping form this manifest is not merely unrejected --
    it is *unrepresentable*: one entry silently wins at construction and the frozen
    artifact shows a single arm. Here the duplicate survives into the artifact and is
    caught by anyone who reads it.
    """
    m = _manifest(_arm(ARM), _arm(ARM2), _arm(ARM))
    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        validate_profile_manifest(m)


def test_a_duplicate_is_rejected_even_when_the_entries_are_identical():
    # Identical twins are still two arms claiming one identity; which rep belongs to which
    # is then unanswerable, and the dataset tier's per-arm identity runs over both.
    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        validate_profile_manifest(_manifest(_arm(ARM), _arm(ARM)))


def test_the_whole_list_is_validated_before_any_index_exists():
    # A duplicate LATE in the list must still be caught: an implementation that indexed as
    # it went and validated afterwards would already have lost the first entry.
    m = _manifest(_arm(ARM), _arm(ARM2), _arm("arm-03"), _arm(ARM2))
    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        validate_profile_manifest(m)


# ==========================================================================
# warmup: per arm, and coherent with the lifecycle  (Erratum 1)
# ==========================================================================


def test_a_top_level_warmup_is_rejected():
    # Erratum 1: a run-level warmup alongside the per-arm one would be a second truth about
    # the same quantity -- precisely the drift the erratum removes.
    m = _manifest(_arm())
    m["warmup"] = 2
    with pytest.raises(DecisionProfileError, match="run-level"):
        validate_profile_manifest(m)


def test_arms_may_declare_different_warmups():
    index = validate_profile_manifest(
        _manifest(
            _arm(ARM, calc_backend="per_arm", cache="per_arm", warmup=3),
            _arm(ARM2, calc_backend="per_arm", cache="per_arm", warmup=1),
        )
    )
    assert index[ARM]["warmup"] == 3
    assert index[ARM2]["warmup"] == 1


def test_a_cold_cache_arm_that_warms_up_is_rejected():
    # §2.8: "a cold-cache arm that 'warms up' is a contradiction, because its caches are
    # discarded anyway". per_rep caches => warmup must be 0.
    with pytest.raises(DecisionProfileError, match="cold-cache arm"):
        validate_profile_manifest(_manifest(_arm(cache="per_rep", warmup=2)))


def test_a_cold_cache_arm_with_zero_warmup_is_fine():
    validate_profile_manifest(_manifest(_arm(cache="per_rep", warmup=0)))


def test_a_warm_cache_arm_may_warm_up():
    validate_profile_manifest(
        _manifest(_arm(calc_backend="per_arm", cache="per_arm", warmup=2))
    )


@pytest.mark.parametrize("bad", [-1, "2", 1.5, True, None])
def test_warmup_must_be_a_non_negative_int(bad):
    with pytest.raises(DecisionProfileError, match="warmup"):
        validate_profile_manifest(_manifest(_arm(warmup=bad)))


def test_a_missing_warmup_is_rejected():
    arm = _arm()
    del arm["warmup"]
    with pytest.raises(DecisionProfileError, match="warmup"):
        validate_profile_manifest({"arms": [arm]})


# ==========================================================================
# mixed cache lifecycles  (§2.8)
# ==========================================================================


def test_mixed_cache_lifecycles_are_rejected_at_load():
    # Rejecting the manifest is what keeps expected_cache_class total without inventing a
    # `mixed` class -- the enumeration reflex that produced §9 entries 27-30.
    arm = _arm(cache="per_arm", calc_backend="per_arm", warmup=1)
    arm["lifecycle"]["speed_oracle"] = "per_rep"
    with pytest.raises(DecisionProfileError, match="disagreeing cache lifecycles"):
        validate_profile_manifest({"arms": [arm]})


def test_a_missing_lifecycle_is_rejected():
    arm = _arm()
    del arm["lifecycle"]
    with pytest.raises(DecisionProfileError):
        validate_profile_manifest({"arms": [arm]})


# ==========================================================================
# arm_by_id: ONE central lookup, never a scan at each call site
# ==========================================================================


def test_arm_by_id_resolves():
    m = _manifest(_arm(ARM), _arm(ARM2))
    assert arm_by_id(m, ARM2)["arm_id"] == ARM2


def test_arm_by_id_rejects_an_unknown_arm_id():
    with pytest.raises(DecisionProfileError, match="unknown arm_id"):
        arm_by_id(_manifest(_arm(ARM)), "no-such-arm")


def test_arm_by_id_validates_the_manifest_before_resolving():
    # A lookup that succeeded against a manifest nobody had judged would let a duplicate
    # elsewhere in the list pass unnoticed for every row that did not name it.
    m = _manifest(_arm(ARM), _arm(ARM2), _arm(ARM2))
    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        arm_by_id(m, ARM)  # ARM itself is fine; the manifest is not

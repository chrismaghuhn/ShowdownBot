"""I8-B Task B2 — the per-row validator: one violating row per rule.

Design `docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md` (Rev. 11) §2.4's
validator list, rule for rule.

WRITTEN BEFORE THE VALIDATOR, deliberately. A validator authored first and tested second is
a validator written against an imagined row: it passes because it was shaped to. Every rule
below therefore gets a row that violates it and must raise -- and, just as load-bearing, the
rows that must NOT raise. The design's §9 records two revisions whose validators would have
rejected real, successful rows (entries 23, 51) and one whose rules no live row could satisfy
at all (entry 49). Those three are the `_MUST_PASS` cases here.
"""

from __future__ import annotations

import pytest

from showdown_bot.eval.decision_profile import (
    SCHEMA_VERSION,
    DecisionProfileError,
    backend_class_of,
    expected_cache_class,
    profile_manifest_hash,
    validate_decision_profile_row,
)

ARM = "arm-01"
CFG_HASH = "0123456789abcdef"


def _manifest(*, calc_backend="per_rep", cache="per_rep", warmup=0, config_hash=CFG_HASH):
    """`arms` is a LIST with arm_id as a field (design §2.7 + Erratum 1).

    Not a mapping keyed by arm_id: a mapping cannot represent a duplicate arm_id, so the
    duplicate would vanish at construction and the frozen manifest could never be
    re-checked for it.
    """
    return {
        "arms": [
            {
                "arm_id": ARM,
                "effective_config_hash": config_hash,
                "warmup": warmup,
                "reps": 3,
                "lifecycle": {
                    "calc_backend": calc_backend,
                    "damage_oracle": cache,
                    "speed_oracle": cache,
                    "species_dex": cache,
                    "contexts_and_variants": "per_rep",
                },
            }
        ],
    }


def _micro(manifest: dict | None = None, **over) -> dict:
    """A VALID microprofile row: persistent, cold cache, one clean spawn, rep 0.

    Bound to ``manifest`` because profile_manifest_hash is computed from the manifest's
    CONTENT: a row built against one manifest and validated against another fails on the
    hash, which would make a negative test pass for the wrong reason.
    """
    m = _manifest() if manifest is None else manifest
    row = {
        "schema_version": SCHEMA_VERSION,
        "source": "microprofile",
        "battle_id": None,
        "decision_index": None,
        "arm_id": ARM,
        "rep": 0,
        "config_id": "cfg",
        "format_id": "gen9championsvgc2026regma",
        "git_sha": "deadbeef",
        "config_hash": CFG_HASH,
        "schedule_hash": None,
        "profile_manifest_hash": profile_manifest_hash(m),
        "calc_backend": "persistent",
        "backend_class": "clean_cold",
        "cache_class": "cold",
        "damage_cache_size_at_rep_start": 0,
        "speed_cache_size_at_rep_start": 0,
        "dex_cache_size_at_rep_start": 0,
        "spawn_count_before": 0,
        "transport_retried": False,
        "timer_scope": "score_evaluated_variants",
        "measured_ms": 12.5,
        "damage_batch_calls": 1,
        "planned_damage_batches": 1,
        "implicit_damage_batches": 0,
        "stats_batch_calls": 0,
        "types_batch_calls": 0,
        "transport_calls": 1,
        "transport_attempts": 1,
        "spawn_calls": 1,
        "requests_total": 4,
        "requests_unique": 4,
        "cache_hits": 0,
        "n_candidates": 12,
        "n_responses": 3,
        "n_mega_twins": 2,
        "n_branches": 2,
        "n_worlds": 1,
        "depth2_frontier": 0,
        "foe_mega_active": True,
        "outcome": "ok",
    }
    row.update(over)
    return row


def _live(**over) -> dict:
    """A VALID live row: no arm, no rep, no manifest, cache fields null."""
    row = _micro(
        source="live",
        battle_id="b0",
        decision_index=4,
        arm_id=None,
        rep=None,
        schedule_hash="aabbccdd11223344",
        profile_manifest_hash=None,
        timer_scope="agent_choose",
        cache_class=None,
        damage_cache_size_at_rep_start=None,
        speed_cache_size_at_rep_start=None,
        dex_cache_size_at_rep_start=None,
    )
    row.update(over)
    return row


# ==========================================================================
# the baselines must pass, or every negative test below is vacuous
# ==========================================================================


def test_the_valid_microprofile_row_passes():
    validate_decision_profile_row(_micro(), manifest=_manifest())


def test_the_valid_live_row_passes():
    validate_decision_profile_row(_live(), manifest=None)


# ==========================================================================
# enumerated values and types -- structural completeness is not validity
# ==========================================================================


def test_a_wrong_schema_version_is_rejected():
    # The design pins the literal string "decision-profile-v1". The integer 1 satisfied
    # every arithmetic rule and was still not a v1 row.
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(schema_version=1), manifest=_manifest())


@pytest.mark.parametrize("bad", ["banana", "OK", "", None])
def test_an_unenumerated_outcome_is_rejected(bad):
    """Rejected BY THE ENUM, and match= is what makes that claim true.

    Without it this test was vacuous: every value above is also rejected by the
    outcome == "ok" <=> measured_ms equivalence, so the test passed even when the enum
    check was weakened to `outcome is not None`. It named a rule it never exercised --
    caught by mutating the enum away and watching all 83 tests stay green.

    measured_ms=None keeps the equivalence rule satisfied for a non-"ok" outcome, so the
    enum is the only rule left that can fire.
    """
    row = _micro(outcome=bad, measured_ms=None)
    with pytest.raises(DecisionProfileError, match="unknown outcome"):
        validate_decision_profile_row(row, manifest=_manifest())


@pytest.mark.parametrize("outcome", ["ok", "crash", "fallback", "degraded_state"])
def test_every_enumerated_outcome_is_accepted(outcome):
    row = _micro(outcome=outcome, measured_ms=12.5 if outcome == "ok" else None)
    validate_decision_profile_row(row, manifest=_manifest())


def test_an_unenumerated_calc_backend_is_rejected():
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(calc_backend="magic"), manifest=_manifest())


def test_an_unenumerated_cache_class_is_rejected_by_the_equality_rule():
    """Rejected -- but by the equality rule, and there is no separate enum to test.

    expected_cache_class returns only "cold" or "warm", so cache_class == expected_...
    already constrains the domain and a cache_class enum would be dead code. One was
    written; mutating it away changed nothing, which is how the redundancy surfaced.
    match= records which rule actually does the work.
    """
    with pytest.raises(DecisionProfileError, match="contradicts the arm's declared lifecycle"):
        validate_decision_profile_row(_micro(cache_class="tepid"), manifest=_manifest())


@pytest.mark.parametrize("field", ["config_id", "format_id", "git_sha", "config_hash"])
def test_provenance_fields_must_be_non_empty_strings(field):
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(**{field: ""}), manifest=_manifest())
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(**{field: None}), manifest=_manifest())


@pytest.mark.parametrize("field", ["transport_retried", "foe_mega_active"])
def test_a_bool_field_must_be_a_bool(field):
    # 0/1 are ints that compare equal to False/True, so an == check would pass them.
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(**{field: 0}), manifest=_manifest())


def test_measured_ms_must_be_a_float_not_a_string():
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(measured_ms="12.5"), manifest=_manifest())


def test_measured_ms_may_not_be_negative():
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(measured_ms=-1.0), manifest=_manifest())


def test_a_bool_is_not_an_acceptable_counter():
    # bool is a subclass of int, so a naive isinstance(int) check accepts True as 1.
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(cache_hits=True), manifest=_manifest())


# ==========================================================================
# arithmetic / counter rules
# ==========================================================================


def test_damage_batches_must_equal_planned_plus_implicit():
    row = _micro(damage_batch_calls=3, planned_damage_batches=1, implicit_damage_batches=1)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_transport_calls_must_equal_the_three_logical_methods():
    row = _micro(transport_calls=9)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_attempts_may_not_be_fewer_than_calls():
    # A retry adds attempts, never calls -- so attempts < calls is impossible.
    row = _micro(transport_attempts=0, transport_calls=1, spawn_calls=0)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_negative_counter_is_a_contract_violation_not_a_datum():
    row = _micro(cache_hits=-1)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_unique_requests_may_not_exceed_total():
    row = _micro(requests_total=2, requests_unique=3)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_mega_twins_imply_an_active_foe_mega():
    row = _micro(n_mega_twins=2, foe_mega_active=False)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


# ==========================================================================
# outcome <-> measured_ms  (§2.6)
# ==========================================================================


def test_a_crashed_row_may_not_carry_a_latency():
    # A crashed decision's wall clock is the crash handler, not decision work.
    row = _micro(outcome="crash", measured_ms=17.0)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_an_ok_row_must_carry_a_latency():
    row = _micro(outcome="ok", measured_ms=None)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_crashed_row_with_null_latency_passes_and_keeps_its_counters():
    # §2.6: the row IS emitted, and its counters describe transport that really happened.
    row = _micro(outcome="crash", measured_ms=None)
    validate_decision_profile_row(row, manifest=_manifest())


# ==========================================================================
# transport_retried -- the ONLY definition (§5.5)
# ==========================================================================


def test_retried_must_equal_attempts_greater_than_calls():
    row = _micro(transport_retried=True)  # attempts == calls, so retried must be False
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_real_retry_row_passes():
    row = _micro(
        transport_attempts=2, transport_calls=1, transport_retried=True,
        damage_batch_calls=1, planned_damage_batches=1, implicit_damage_batches=0,
        stats_batch_calls=0, types_batch_calls=0,
        spawn_count_before=0, spawn_calls=2, backend_class="contaminated",
    )
    validate_decision_profile_row(row, manifest=_manifest())


# ==========================================================================
# backend_class is RECOMPUTED, never trusted (§5.5)
# ==========================================================================


def test_oneshot_must_classify_as_oneshot():
    row = _micro(calc_backend="oneshot", backend_class="clean_cold")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_oneshot_spawns_once_per_attempt():
    row = _micro(calc_backend="oneshot", backend_class="oneshot",
                 spawn_calls=5, transport_attempts=1)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_mislabelled_backend_class_is_rejected():
    # spawn_count_before=0, spawn_calls=1, not retried -> clean_cold, not clean_warm.
    row = _micro(backend_class="clean_warm")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


@pytest.mark.parametrize(
    "backend, before, calls, retried, expected",
    [
        ("oneshot", 0, 3, False, "oneshot"),
        ("persistent", 0, 1, False, "clean_cold"),
        ("persistent", 2, 0, False, "clean_warm"),
        # the three cells the enums missed (design §9 entries 23, 27, 51)
        ("persistent", 0, 2, True, "contaminated"),    # cold + retry
        ("persistent", 1, 1, False, "contaminated"),   # respawn between decisions, NO retry
        ("persistent", 0, 2, False, "contaminated"),   # cold + mid-decision respawn, no retry
        ("persistent", 0, 0, False, "contaminated"),   # used no calc at all
    ],
)
def test_the_backend_predicate_is_exhaustive(backend, before, calls, retried, expected):
    assert backend_class_of(backend, before, calls, retried) == expected


def test_a_respawn_row_is_LEGITIMATE_and_must_not_be_rejected():
    # THE row two design revisions would have wrongly rejected (§9 entries 23, 51):
    # _ensure revives a process that died between decisions BEFORE the first attempt --
    # no failure, no retry, correct result. It is contaminated (excluded from the
    # contrast), never invalid (rejected).
    row = _micro(spawn_count_before=1, spawn_calls=1, transport_retried=False,
                 backend_class="contaminated")
    validate_decision_profile_row(row, manifest=_manifest())


# ==========================================================================
# the cache contract is a MICROPROFILE concept (§2.8, §9 entry 49)
# ==========================================================================


@pytest.mark.parametrize(
    "field",
    ["cache_class", "damage_cache_size_at_rep_start",
     "speed_cache_size_at_rep_start", "dex_cache_size_at_rep_start"],
)
def test_a_live_row_may_not_carry_any_cache_field(field):
    row = _live(**{field: 0 if field != "cache_class" else "cold"})
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


@pytest.mark.parametrize(
    "lifecycle, warmup, rep, expected",
    [
        ("per_rep", 0, 0, "cold"),
        ("per_rep", 0, 5, "cold"),
        ("per_rep", 2, 3, "cold"),
        # rep is 0-BASED: rep 0 is the FIRST timed rep and is genuinely cold;
        # rep 1 is the SECOND and is warm. Rev. 10 read it as 1-based, so rep 0
        # matched no branch at all and rep 1 was labelled "cold" (§9 entry 50).
        ("per_arm", 0, 0, "cold"),
        ("per_arm", 0, 1, "warm"),
        ("per_arm", 0, 2, "warm"),
        ("per_arm", 1, 0, "warm"),   # warmup already populated the caches
        ("per_arm", 3, 0, "warm"),
    ],
)
def test_expected_cache_class_is_total_and_zero_based(lifecycle, warmup, rep, expected):
    arm = _manifest(cache=lifecycle, warmup=warmup)["arms"][0]
    assert expected_cache_class(arm, rep) == expected


def test_a_mislabelled_cache_class_is_rejected():
    row = _micro(cache_class="warm", rep=0)
    with pytest.raises(DecisionProfileError, match="contradicts the arm's declared lifecycle"):
        validate_decision_profile_row(row, manifest=_manifest(cache="per_rep"))


def test_a_cold_claim_with_a_populated_cache_is_rejected():
    # The sound direction: a fresh cache is provably empty, so a non-empty one at rep
    # start disproves the declared lifecycle -- catching a HARNESS that reused an object
    # the manifest said was fresh, which manifest-equality alone cannot.
    row = _micro(cache_class="cold", damage_cache_size_at_rep_start=7)
    with pytest.raises(DecisionProfileError, match="already populated at rep start"):
        validate_decision_profile_row(row, manifest=_manifest(cache="per_rep"))


def test_a_warm_claim_with_an_empty_dex_cache_is_ACCEPTED():
    # The CONVERSE is unsound and deliberately NOT asserted: a reused SpeciesDex on a
    # board whose species were never looked up is legitimately empty. Rev. 5 shipped
    # exactly this shape of over-strict rule for backend_state (§9 entry 23).
    m = _manifest(calc_backend="per_arm", cache="per_arm")
    row = _micro(
        m,
        rep=1, cache_class="warm",
        damage_cache_size_at_rep_start=4,
        speed_cache_size_at_rep_start=2,
        dex_cache_size_at_rep_start=0,
        spawn_count_before=1, spawn_calls=0, backend_class="clean_warm",
    )
    validate_decision_profile_row(row, manifest=m)


def test_a_warm_claim_on_the_first_rep_without_warmup_is_rejected():
    """Rejected -- but by the EQUALITY rule, and the distinction is worth recording.

    The design lists two cache rules: cache_class == expected_cache_class(arm, rep), and
    cache_class == "warm" => rep >= 1 or warmup >= 1. The second is UNREACHABLE while the
    first holds: expected_cache_class(per_arm, warmup=0, rep=0) is already "cold", so a
    "warm" row fails equality before the warm rule is ever consulted. It is a backstop
    against expected_cache_class itself being wrong, not an independently reachable rule.

    That is worth pinning rather than papering over: a first cut of this test asserted the
    warm rule's message and failed, which is how the redundancy surfaced. match= is what
    made it visible -- without it the test would have "passed" while proving nothing about
    the rule it named.
    """
    m = _manifest(cache="per_arm", warmup=0)
    row = _micro(m, rep=0, cache_class="warm")
    with pytest.raises(DecisionProfileError, match="contradicts the arm's declared lifecycle"):
        validate_decision_profile_row(row, manifest=m)


def test_the_warm_backstop_fires_only_if_expected_cache_class_is_itself_wrong(monkeypatch):
    # Reachable ONLY by breaking the equality rule's source of truth. This is what the
    # design's second cache rule actually defends: a bug in expected_cache_class.
    import showdown_bot.eval.decision_profile as dp

    m = _manifest(cache="per_arm", warmup=0)
    row = _micro(m, rep=0, cache_class="warm")
    monkeypatch.setattr(dp, "expected_cache_class", lambda arm, rep: "warm")
    with pytest.raises(DecisionProfileError, match="nothing ran before it"):
        dp.validate_decision_profile_row(row, manifest=m)


def test_a_manifest_whose_three_caches_disagree_is_invalid():
    # §2.8: the three semantic caches must share one lifecycle, else expected_cache_class
    # is not total. Rejecting the manifest is what avoids inventing a `mixed` class --
    # the reflex that produced §9 entries 27-30.
    m = _manifest(cache="per_arm")
    m["arms"][0]["lifecycle"]["speed_oracle"] = "per_rep"
    with pytest.raises(DecisionProfileError, match="disagreeing cache lifecycles"):
        validate_decision_profile_row(_micro(m), manifest=m)


# ==========================================================================
# source <-> timer_scope is a CONTRACT, not documentation (§2.5)
# ==========================================================================


@pytest.mark.parametrize("scope", ["contexts_and_score", "score_evaluated_variants"])
def test_a_live_row_at_a_microprofile_scope_is_rejected(scope):
    row = _live(timer_scope=scope)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_a_microprofile_row_at_agent_choose_is_rejected():
    row = _micro(timer_scope="agent_choose")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_an_unknown_timer_scope_is_rejected():
    row = _micro(timer_scope="whenever")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_the_wider_microprofile_scope_is_accepted():
    row = _micro(timer_scope="contexts_and_score")
    validate_decision_profile_row(row, manifest=_manifest())


# ==========================================================================
# identity / source consistency, and the manifest join
# ==========================================================================


@pytest.mark.parametrize("field", ["arm_id", "rep", "profile_manifest_hash"])
def test_a_live_row_may_not_carry_microprofile_identity(field):
    row = _live(**{field: 1 if field == "rep" else "x"})
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


@pytest.mark.parametrize("field", ["battle_id", "decision_index", "schedule_hash"])
def test_a_microprofile_row_may_not_carry_live_identity(field):
    row = _micro(**{field: 1 if field == "decision_index" else "x"})
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_live_row_must_carry_its_own_identity():
    row = _live(battle_id=None)
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=None)


def test_a_microprofile_config_hash_must_match_its_arm_in_the_manifest():
    row = _micro(config_hash="ffffffffffffffff")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_microprofile_row_naming_an_unknown_arm_is_rejected():
    row = _micro(arm_id="no-such-arm")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_a_microprofile_row_whose_manifest_hash_disagrees_is_rejected():
    row = _micro(profile_manifest_hash="0000000000000000")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


def test_the_manifest_hash_is_COMPUTED_not_read_from_the_manifest():
    # A manifest must not state its own hash: the field would be an input to the digest
    # that depends on the digest. So a manifest that ASSERTS an identity cannot buy one --
    # the validator recomputes from content, and a mutated manifest gets a new hash even
    # if it carries the old one.
    m = _manifest()
    row = _micro(profile_manifest_hash=profile_manifest_hash(m))
    validate_decision_profile_row(row, manifest=m)

    tampered = _manifest()
    tampered["arms"][0]["warmup"] = 5           # content changed -> identity changed
    tampered["profile_manifest_hash"] = row["profile_manifest_hash"]   # a lie in a field
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=tampered)


def test_the_manifest_hash_is_stable_and_order_independent():
    a = _manifest()
    b = {"arms": [dict(reversed(list(a["arms"][0].items())))]}
    assert profile_manifest_hash(a) == profile_manifest_hash(b)


def test_a_microprofile_row_without_a_manifest_is_rejected():
    # Half the rules are unevaluable without it; passing None would silently skip them.
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(), manifest=None)


def test_an_unknown_source_is_rejected():
    row = _micro(source="guesswork")
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())


# ==========================================================================
# B1's field set is still enforced here
# ==========================================================================


def test_the_validator_still_rejects_an_unknown_field():
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(_micro(surprise=1), manifest=_manifest())


def test_the_validator_still_rejects_a_missing_field():
    row = _micro()
    del row["outcome"]
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_row(row, manifest=_manifest())

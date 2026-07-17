"""I8-B Task B3 — the dataset validator: deterministic rules, corrupted files first.

Design §2.4's second tier. It runs ONCE over a finished sidecar, before any row is read as
evidence, and it FAILS THE RUN rather than annotating it.

Every rule here is an exact predicate. The design's prose said a `per_arm` arm whose rows
are "predominantly clean_cold" disagrees with its declaration -- but "predominantly" is not
a rule: it has no threshold and no direction, and nothing could return False from it. It is
replaced by an accounting IDENTITY, which is both deterministic and strictly stronger:

    spawn_count is cumulative on the backend OBJECT and never resets while it lives, so

      per_arm : spawn_count_before[0] == 0
                spawn_count_before[n+1] == spawn_count_before[n] + spawn_calls[n]
      per_rep : spawn_count_before[n] == 0   for every n

The identity catches a harness that REUSES when it declared per_rep (a reused object carries
a count into rep 1) and one that REBUILDS when it declared per_arm (a fresh object resets the
count, breaking the sum) -- and it never rejects a legitimate respawn, which only adds to
spawn_calls[n] and leaves the identity exact. That last property is the one two design
revisions got wrong (§9 entries 23, 51).
"""

from __future__ import annotations

import json

import pytest

from showdown_bot.eval.decision_profile import (
    PROFILE_MANIFEST_SCHEMA_VERSION,
    SCHEMA_VERSION,
    DecisionProfileError,
    profile_manifest_hash,
    validate_decision_profile_dataset,
)

ARM = "arm-01"
ARM2 = "arm-02"
CFG_HASH = "0123456789abcdef"


def _manifest(*, calc_backend="per_arm", cache="per_arm", warmup=1, arms=(ARM,), fixture="fix-a"):
    """`arms` is a LIST with arm_id as a field (design §2.7 + Erratum 1)."""
    return {
        "schema_version": PROFILE_MANIFEST_SCHEMA_VERSION,
        "git_sha": "a1bb619f52c635013782de6f12f06f29b43a4fa6",
        "dirty": False,
        "calc_pin_hash": "79a4877538c8740f",
        "format_id": "gen9championsvgc2026regma",
        "format_config_hash": "fa8eb689e95c03c6",
        "speciesdata_hash": "b6e121e58c592056",
        "itemdata_hash": "c5b00bfb5f093e98",
        "movedata_hash": "20b3c72e72480ee1",
        "arms": [
            {
                "arm_id": a,
                "behavior_env": {"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
                "arm_params": {},
                "scoring_params": {},
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
            for a in arms
        ],
    }


def _row(manifest, *, arm=ARM, rep=0, **over) -> dict:
    row = {
        "schema_version": SCHEMA_VERSION,
        "source": "microprofile",
        "battle_id": None,
        "decision_index": None,
        "arm_id": arm,
        "rep": rep,
        "config_id": "cfg",
        "format_id": "gen9championsvgc2026regma",
        "git_sha": "deadbeef",
        "config_hash": CFG_HASH,
        "schedule_hash": None,
        "profile_manifest_hash": profile_manifest_hash(manifest),
        "calc_backend": "persistent",
        "backend_class": "clean_warm",
        "cache_class": "warm",
        "damage_cache_size_at_rep_start": 4,
        "speed_cache_size_at_rep_start": 2,
        "dex_cache_size_at_rep_start": 1,
        "spawn_count_before": 1,
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
        "spawn_calls": 0,
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


def _write(tmp_path, rows) -> str:
    p = tmp_path / "profile.jsonl"
    with open(p, "a", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return str(p)


def _warm_arm_rows(m, n=3, arm=ARM):
    """A coherent per_arm run: the backend spawned during warmup, so every timed rep
    starts with spawn_count_before == 1 and never spawns again."""
    return [_row(m, arm=arm, rep=i, spawn_count_before=1, spawn_calls=0,
                 damage_cache_size_at_rep_start=4 + i) for i in range(n)]


# ==========================================================================
# the baseline must pass, or every negative test below is vacuous
# ==========================================================================


def test_a_coherent_per_arm_dataset_passes(tmp_path):
    m = _manifest()
    report = validate_decision_profile_dataset(_write(tmp_path, _warm_arm_rows(m)), m)
    assert report["rows"] == 3


def test_a_coherent_per_rep_dataset_passes(tmp_path):
    m = _manifest(calc_backend="per_rep", cache="per_rep", warmup=0)
    rows = [
        _row(m, rep=i, spawn_count_before=0, spawn_calls=1, backend_class="clean_cold",
             cache_class="cold", damage_cache_size_at_rep_start=0,
             speed_cache_size_at_rep_start=0, dex_cache_size_at_rep_start=0)
        for i in range(3)
    ]
    report = validate_decision_profile_dataset(_write(tmp_path, rows), m)
    assert report["rows"] == 3


# ==========================================================================
# fixture identity: same fixture => same V   (§2.7)
# ==========================================================================


def test_same_fixture_hash_with_different_n_candidates_is_rejected(tmp_path):
    # V depends only on the group-A inputs the fixture hash binds, so two rows of one
    # fixture cannot legitimately disagree about it. When they do, the hash bound FEWER
    # inputs than the scoring path actually consumed -- the failure §9 entries 20, 25, 30,
    # 33-35 and 39 were each an instance of.
    m = _manifest()
    rows = _warm_arm_rows(m, n=2)
    rows[1]["n_candidates"] = 13
    with pytest.raises(DecisionProfileError, match="n_candidates"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_two_arms_sharing_a_fixture_must_agree_on_n_candidates(tmp_path):
    # The grouping key is the ARM's fixture_input_hash, not arm_id: two arms differing
    # only in scoring_params share a fixture, and V is fixture-determined.
    m = _manifest(arms=(ARM, ARM2), fixture="fix-a")
    rows = _warm_arm_rows(m, n=2) + _warm_arm_rows(m, n=2, arm=ARM2)
    rows[-1]["n_candidates"] = 99
    with pytest.raises(DecisionProfileError, match="n_candidates"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


# ==========================================================================
# backend lifecycle: an exact identity, never a distribution
# ==========================================================================


def test_per_rep_arm_that_reused_the_backend_is_rejected(tmp_path):
    # Declared per_rep, but rep 1 inherited a spawn count -> the object was reused.
    m = _manifest(calc_backend="per_rep", cache="per_rep", warmup=0)
    rows = [
        _row(m, rep=0, spawn_count_before=0, spawn_calls=1, backend_class="clean_cold",
             cache_class="cold", damage_cache_size_at_rep_start=0,
             speed_cache_size_at_rep_start=0, dex_cache_size_at_rep_start=0),
        _row(m, rep=1, spawn_count_before=1, spawn_calls=1, backend_class="contaminated",
             cache_class="cold", damage_cache_size_at_rep_start=0,
             speed_cache_size_at_rep_start=0, dex_cache_size_at_rep_start=0),
    ]
    with pytest.raises(DecisionProfileError, match="per_rep"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_per_arm_arm_that_silently_rebuilt_the_backend_is_rejected(tmp_path):
    # The identity breaks: rep 1 should start at spawn_count_before[0] + spawn_calls[0].
    m = _manifest(warmup=0)
    rows = [
        _row(m, rep=0, spawn_count_before=0, spawn_calls=1, backend_class="clean_cold",
             cache_class="cold", damage_cache_size_at_rep_start=0,
             speed_cache_size_at_rep_start=0, dex_cache_size_at_rep_start=0),
        _row(m, rep=1, spawn_count_before=0, spawn_calls=1, backend_class="clean_cold",
             cache_class="warm", damage_cache_size_at_rep_start=1,
             speed_cache_size_at_rep_start=1, dex_cache_size_at_rep_start=1),
    ]
    with pytest.raises(DecisionProfileError, match="spawn_count_before"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_a_per_arm_respawn_is_LEGITIMATE_and_must_pass(tmp_path):
    """THE case two design revisions rejected (§9 entries 23, 51).

    The process died between reps and _ensure revived it before the first attempt: no
    failure, no retry, correct result. spawn_calls goes to 1 and the identity STAYS EXACT
    -- rep 2 simply starts one higher. A distribution rule would have called this arm
    'not predominantly clean_warm' and voided it; the identity does not.
    """
    m = _manifest()
    rows = [
        _row(m, rep=0, spawn_count_before=1, spawn_calls=0),
        _row(m, rep=1, spawn_count_before=1, spawn_calls=1, backend_class="contaminated",
             damage_cache_size_at_rep_start=5),
        _row(m, rep=2, spawn_count_before=2, spawn_calls=0, damage_cache_size_at_rep_start=6),
    ]
    report = validate_decision_profile_dataset(_write(tmp_path, rows), m)
    assert report["backend_class_counts"]["contaminated"] == 1
    assert report["backend_class_counts"]["clean_warm"] == 2


def test_a_per_arm_arm_whose_first_timed_rep_carries_no_spawn_after_warmup_is_rejected(tmp_path):
    # warmup >= 1 means the backend was started before the timed reps; a per_arm arm whose
    # rep 0 reports spawn_count_before == 0 contradicts its own warmup declaration.
    m = _manifest(warmup=1)
    rows = [_row(m, rep=0, spawn_count_before=0, spawn_calls=1, backend_class="clean_cold")]
    with pytest.raises(DecisionProfileError, match="warmup"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


# ==========================================================================
# cache lifecycle: monotone, because the caches are never cleared (F-14)
# ==========================================================================


def test_per_arm_caches_may_not_shrink(tmp_path):
    # The three caches are never cleared or evicted, so a reused object's size at rep start
    # can only grow. A shrink means the object was NOT the same object.
    m = _manifest()
    rows = _warm_arm_rows(m, n=2)
    rows[1]["damage_cache_size_at_rep_start"] = 1  # was 4
    with pytest.raises(DecisionProfileError, match="shrank"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_per_rep_caches_must_be_empty_on_every_rep(tmp_path):
    m = _manifest(calc_backend="per_rep", cache="per_rep", warmup=0)
    rows = [
        _row(m, rep=0, spawn_count_before=0, spawn_calls=1, backend_class="clean_cold",
             cache_class="cold", damage_cache_size_at_rep_start=0,
             speed_cache_size_at_rep_start=0, dex_cache_size_at_rep_start=0),
    ]
    rows[0]["damage_cache_size_at_rep_start"] = 3
    # per-row already forbids cold-with-a-populated-cache; the dataset tier states the
    # lifecycle form of it, so a file assembled by hand cannot slip past either.
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


# ==========================================================================
# the dataset tier re-validates every row: a file on disk is not a trusted writer
# ==========================================================================


def test_a_hand_edited_invalid_row_is_rejected(tmp_path):
    m = _manifest()
    rows = _warm_arm_rows(m, n=2)
    rows[0]["damage_batch_calls"] = 7  # != planned + implicit
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_a_row_naming_a_foreign_manifest_is_rejected(tmp_path):
    m = _manifest()
    rows = _warm_arm_rows(m, n=1)
    rows[0]["profile_manifest_hash"] = "0000000000000000"
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_a_live_row_in_a_microprofile_sidecar_is_rejected(tmp_path):
    # §2.5: the two sources measure different boundaries and must never share a file that
    # is later read as one dataset.
    m = _manifest()
    rows = _warm_arm_rows(m, n=1)
    rows.append(_row(m, rep=1, source="live", battle_id="b0", decision_index=1,
                     arm_id=None, schedule_hash="aabb", profile_manifest_hash=None,
                     timer_scope="agent_choose", cache_class=None,
                     damage_cache_size_at_rep_start=None,
                     speed_cache_size_at_rep_start=None,
                     dex_cache_size_at_rep_start=None))
    with pytest.raises(DecisionProfileError, match="microprofile"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_a_duplicate_rep_is_rejected(tmp_path):
    # Two rows for one (arm, rep) means the file interleaves runs, or a rep was written
    # twice -- either way the identity above is evaluated over an ambiguous sequence.
    m = _manifest()
    rows = _warm_arm_rows(m, n=2)
    rows.append(_row(m, rep=1, spawn_count_before=1, spawn_calls=0,
                     damage_cache_size_at_rep_start=5))
    with pytest.raises(DecisionProfileError, match="duplicate"):
        validate_decision_profile_dataset(_write(tmp_path, rows), m)


def test_an_empty_sidecar_is_rejected(tmp_path):
    # Zero rows is not a clean run; it is a run that produced no evidence.
    m = _manifest()
    with pytest.raises(DecisionProfileError, match="no rows"):
        validate_decision_profile_dataset(_write(tmp_path, []), m)


def test_malformed_json_is_rejected(tmp_path):
    m = _manifest()
    p = tmp_path / "profile.jsonl"
    p.write_bytes(b'{"not":"a row"\n')
    with pytest.raises(DecisionProfileError):
        validate_decision_profile_dataset(str(p), m)


# ==========================================================================
# what it reports
# ==========================================================================


def test_the_report_counts_contaminated_and_clean_rows(tmp_path):
    # §5.5: contaminated rows are EXCLUDED from a contrast and reported by count -- never
    # silently dropped, and never rejected.
    m = _manifest()
    rows = [
        _row(m, rep=0, spawn_count_before=1, spawn_calls=0),
        _row(m, rep=1, spawn_count_before=1, spawn_calls=1, backend_class="contaminated",
             damage_cache_size_at_rep_start=5),
        _row(m, rep=2, spawn_count_before=2, spawn_calls=0, damage_cache_size_at_rep_start=6),
    ]
    report = validate_decision_profile_dataset(_write(tmp_path, rows), m)

    assert report["rows"] == 3
    assert report["backend_class_counts"] == {"clean_warm": 2, "contaminated": 1}
    assert report["excluded_from_contrast"] == 1
    assert report["arms"][ARM]["reps"] == 3

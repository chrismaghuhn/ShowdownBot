"""I8-C Task C1 — the manifest producer, and the producer -> file -> hash -> validator roundtrip.

Design §2.7 + Erratum 1. C1 owns ONLY the manifest: its exact shape, its provenance, the
validation that gates writing and hashing, and the file. Which arms exist and what is in
them is C2's and is not authorized here -- the producer takes arm specs and emits a manifest.

The roundtrip is the point. A manifest that validates in memory but cannot be written,
re-read and re-hashed to the same identity is not a provenance anchor. So the tests drive
producer -> file -> read back -> hash -> B2 row validator -> B3 dataset validator, and the
counter-proofs break each link in turn.
"""

from __future__ import annotations

import json

import pytest

from showdown_bot.eval.decision_profile import (
    SCHEMA_VERSION,
    DecisionProfileError,
    profile_manifest_hash,
    validate_decision_profile_dataset,
    validate_decision_profile_row,
)
from showdown_bot.eval.profile_manifest import (
    PROFILE_MANIFEST_SCHEMA_VERSION,
    ArmSpec,
    build_profile_manifest,
    read_profile_manifest,
    write_profile_manifest,
)

FORMAT = "gen9championsvgc2026regma"
ARM = "A9_dual_mega_tie"
ARM2 = "A1_baseline"


def _spec(arm_id=ARM, *, warmup=0, cache="per_rep", calc_backend="per_rep", fixture="fix-a"):
    return ArmSpec(
        arm_id=arm_id,
        behavior_env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        arm_params={"SHOWDOWN_CALC_BACKEND": "persistent", "SHOWDOWN_SEARCH_TOPM": "2"},
        scoring_params={"mode": "NEUTRAL", "risk_lambda": 0.0},
        fixture_input_hash=fixture,
        reps=3,
        warmup=warmup,
        lifecycle={
            "calc_backend": calc_backend,
            "damage_oracle": cache,
            "speed_oracle": cache,
            "species_dex": cache,
            "contexts_and_variants": "per_rep",
        },
    )


def _built(*specs):
    return build_profile_manifest(agent="heuristic", format_id=FORMAT, arms=list(specs) or [_spec()])


# ==========================================================================
# shape: exactly design §2.7, and `arms` is a LIST
# ==========================================================================


def test_the_manifest_carries_the_designs_run_level_fields():
    m = _built()
    assert m["schema_version"] == PROFILE_MANIFEST_SCHEMA_VERSION == "profile-manifest-v1"
    for field in (
        "git_sha", "dirty", "calc_pin_hash", "format_id", "format_config_hash",
        "speciesdata_hash", "itemdata_hash", "movedata_hash", "arms",
    ):
        assert field in m, field
    assert m["format_id"] == FORMAT


def test_arms_is_a_list_with_arm_id_as_a_field():
    m = _built(_spec(ARM), _spec(ARM2))
    assert isinstance(m["arms"], list)
    assert [a["arm_id"] for a in m["arms"]] == [ARM, ARM2]


def test_the_manifest_never_carries_a_run_level_warmup():
    # Erratum 1: warmup is per-arm. A run-level one would be a second truth.
    assert "warmup" not in _built()


def test_each_arm_carries_the_designs_arm_entry_fields():
    arm = _built()["arms"][0]
    assert set(arm) == {
        "arm_id", "effective_config_hash", "behavior_env", "arm_params",
        "scoring_params", "fixture_input_hash", "reps", "warmup", "lifecycle", "timer_scope",
    }


def test_warmup_is_per_arm_and_arms_may_differ():
    m = _built(
        _spec(ARM, warmup=3, cache="per_arm", calc_backend="per_arm"),
        _spec(ARM2, warmup=1, cache="per_arm", calc_backend="per_arm"),
    )
    assert [a["warmup"] for a in m["arms"]] == [3, 1]


# ==========================================================================
# provenance is SOURCED, never invented
# ==========================================================================


def test_run_provenance_matches_the_canonical_helpers():
    from showdown_bot.eval.config_env import config_provenance_for_format, file_content_hash
    from showdown_bot.engine.moves import movedata_path

    m = _built()
    prov = config_provenance_for_format(FORMAT)
    assert m["calc_pin_hash"] == prov["calc_pin_hash"]
    assert m["format_config_hash"] == prov["format_config_hash"]
    assert m["itemdata_hash"] == prov["itemdata_hash"]
    assert m["speciesdata_hash"] == prov["speciesdata_hash"]
    # movedata has no *_content_hash helper of its own; the canonical assembly hashes the
    # file's bytes (config_env.effective_config_manifest does exactly this), so the
    # producer uses the same call rather than inventing a second one.
    assert m["movedata_hash"] == file_content_hash(movedata_path())


def test_effective_config_hash_comes_from_the_canonical_assembly():
    """Never re-derived. config_env.effective_config_manifest documents itself as "the ONE
    place that assembles" these hashes, and warns that a second, independently-written
    assembly is exactly the drift risk it exists to close."""
    from showdown_bot.eval.config_env import effective_config_manifest
    from showdown_bot.eval.result_jsonl import make_config_hash

    spec = _spec()
    arm = _built(spec)["arms"][0]
    expected = make_config_hash(
        effective_config_manifest(agent="heuristic", format_id=FORMAT, env=spec.behavior_env)
    )
    assert arm["effective_config_hash"] == expected


def test_arms_with_different_behavior_env_get_different_config_hashes():
    # The whole reason a single top-level config_hash cannot describe an arm matrix (§2.7).
    a = _spec(ARM)
    b = _spec(ARM2)
    b.behavior_env = {"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.9"}
    m = _built(a, b)
    assert m["arms"][0]["effective_config_hash"] != m["arms"][1]["effective_config_hash"]


# ==========================================================================
# validation gates BOTH writing and hashing
# ==========================================================================


def test_an_invalid_arm_is_rejected_at_build_before_anything_exists():
    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        _built(_spec(ARM), _spec(ARM))


def test_a_cold_cache_arm_that_warms_up_is_rejected_at_build():
    with pytest.raises(DecisionProfileError, match="cold-cache arm"):
        _built(_spec(cache="per_rep", warmup=2))


def test_writing_an_invalid_manifest_creates_no_file(tmp_path):
    # Validation precedes the write, so a rejected manifest leaves no artifact behind to
    # be picked up later as though it were evidence.
    out = tmp_path / "manifest.json"
    m = _built()
    m["arms"].append(dict(m["arms"][0]))  # duplicate arm_id, injected post-build
    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        write_profile_manifest(m, str(out))
    assert not out.exists()


def test_writing_refuses_to_overwrite(tmp_path):
    out = tmp_path / "manifest.json"
    write_profile_manifest(_built(), str(out))
    with pytest.raises(DecisionProfileError, match="exists"):
        write_profile_manifest(_built(), str(out))


def test_a_gitless_environment_produces_no_manifest_and_no_file(tmp_path, monkeypatch):
    """git unavailable -> ("unknown", False) -> no manifest, no artifact.

    A git-less environment may run tests. It may not produce I8 evidence: a manifest that
    cannot name the commit does not bind the code the arms ran against, so the run has no
    provenance anchor and its measurements are attributable to nothing.

    Rejected at BUILD, so nothing reaches a file and no half-anchor is left behind for a
    later reader to mistake for evidence.
    """
    import showdown_bot.eval.profile_manifest as pm

    monkeypatch.setattr(pm, "_git_sha_and_dirty", lambda: ("unknown", False))

    with pytest.raises(DecisionProfileError, match="unknown"):
        _built()

    out = tmp_path / "manifest.json"
    assert not out.exists()


# ==========================================================================
# the hash: the SAME encode() path, computed from content
# ==========================================================================


def test_write_returns_the_same_hash_as_the_pure_function(tmp_path):
    m = _built()
    returned = write_profile_manifest(m, str(tmp_path / "manifest.json"))
    assert returned == profile_manifest_hash(m)
    assert len(returned) == 16


def test_the_manifest_file_is_LF_only(tmp_path):
    out = tmp_path / "manifest.json"
    write_profile_manifest(_built(), str(out))
    raw = out.read_bytes()  # BYTES: a text-mode read hides CRLF on the platform writing it
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_the_file_stores_the_manifest_not_its_encoding(tmp_path):
    """The artifact is the MANIFEST. `encode` is for identity, not storage.

    `encode` renders floats via repr, so a risk_lambda of 0.0 would freeze into the file as
    the STRING "0.0". The first cut wrote encode(manifest) -- reaching for the tidy property
    "the bytes are the digest's input" -- and the roundtrip below caught it: read(write(m))
    came back with a string where the producer meant a float. A provenance artifact that
    misreports its own types is worse than one whose hash needs a function to verify.
    """
    out = tmp_path / "manifest.json"
    built = _built()
    write_profile_manifest(built, str(out))

    stored = json.loads(out.read_text(encoding="utf-8"))
    assert stored == built
    assert isinstance(stored["arms"][0]["scoring_params"]["risk_lambda"], float)


def test_the_identity_is_checkable_from_the_file_alone(tmp_path):
    # Weaker than "the bytes ARE the digest's input", and honest: re-read, re-encode,
    # re-hash -- through the same encode() every consumer already uses.
    out = tmp_path / "manifest.json"
    returned = write_profile_manifest(_built(), str(out))
    assert profile_manifest_hash(read_profile_manifest(str(out))) == returned


# ==========================================================================
# ROUNDTRIP: producer -> file -> hash -> B2 -> B3
# ==========================================================================


def _row(manifest, mhash, *, arm=ARM, rep=0, **over):
    row = {
        "schema_version": SCHEMA_VERSION,
        "source": "microprofile",
        "battle_id": None,
        "decision_index": None,
        "arm_id": arm,
        "rep": rep,
        "config_id": "cfg",
        "format_id": FORMAT,
        "git_sha": manifest["git_sha"] or "unknown",
        "config_hash": next(
            (a["effective_config_hash"] for a in manifest["arms"] if a["arm_id"] == arm),
            "ffffffffffffffff",  # arm deliberately absent: the unknown-arm test needs a row
        ),
        "schedule_hash": None,
        "profile_manifest_hash": mhash,
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


def test_roundtrip_producer_file_hash_row_validator(tmp_path):
    out = tmp_path / "manifest.json"
    built = _built()
    mhash = write_profile_manifest(built, str(out))

    reread = read_profile_manifest(str(out))
    assert reread == built                                  # file -> same manifest
    assert profile_manifest_hash(reread) == mhash           # -> same identity

    # -> and a row carrying that identity validates against the re-read manifest
    validate_decision_profile_row(_row(reread, mhash), manifest=reread)


def test_roundtrip_reaches_the_dataset_validator(tmp_path):
    out = tmp_path / "manifest.json"
    built = _built()
    mhash = write_profile_manifest(built, str(out))
    reread = read_profile_manifest(str(out))

    sidecar = tmp_path / "profile.jsonl"
    with open(sidecar, "a", encoding="utf-8", newline="") as fh:
        for rep in range(3):
            row = _row(reread, mhash, rep=rep)
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    report = validate_decision_profile_dataset(str(sidecar), reread)
    assert report["rows"] == 3
    assert report["arms"][ARM]["reps"] == 3


# ==========================================================================
# counter-proofs: every link of the roundtrip, broken
# ==========================================================================


def test_a_tampered_manifest_no_longer_matches_its_rows_hash(tmp_path):
    """A manifest edited after the fact loses its identity, and its rows stop validating.

    This is what makes the hash an anchor rather than a label: the row does not trust a
    field the manifest asserts about itself -- the validator recomputes from content.
    """
    out = tmp_path / "manifest.json"
    built = _built()
    mhash = write_profile_manifest(built, str(out))
    row = _row(built, mhash)

    tampered = read_profile_manifest(str(out))
    tampered["arms"][0]["reps"] = 999                       # content changed
    assert profile_manifest_hash(tampered) != mhash         # identity changed with it

    with pytest.raises(DecisionProfileError, match="profile_manifest_hash"):
        validate_decision_profile_row(row, manifest=tampered)


def test_a_tampered_file_is_detected_by_rehashing_it(tmp_path):
    out = tmp_path / "manifest.json"
    mhash = write_profile_manifest(_built(), str(out))

    poked = json.loads(out.read_text(encoding="utf-8"))
    poked["git_sha"] = "0000000"
    out.write_text(json.dumps(poked), encoding="utf-8", newline="")

    assert profile_manifest_hash(read_profile_manifest(str(out))) != mhash


def test_a_row_naming_an_unknown_arm_is_rejected(tmp_path):
    built = _built()
    mhash = write_profile_manifest(built, str(tmp_path / "manifest.json"))
    row = _row(built, mhash, arm="no-such-arm")
    with pytest.raises(DecisionProfileError, match="unknown arm_id"):
        validate_decision_profile_row(row, manifest=built)


def test_a_duplicate_arm_injected_into_a_written_manifest_is_caught_on_read(tmp_path):
    """The reason `arms` is a list, end to end.

    In the mapping form this manifest could not exist: one entry would win at
    construction and the frozen file would show a single arm. Here the duplicate survives
    into the artifact and every reader rejects it.
    """
    out = tmp_path / "manifest.json"
    write_profile_manifest(_built(), str(out))

    poked = json.loads(out.read_text(encoding="utf-8"))
    poked["arms"].append(dict(poked["arms"][0]))
    out.write_text(json.dumps(poked), encoding="utf-8", newline="")

    with pytest.raises(DecisionProfileError, match="duplicate arm_id"):
        read_profile_manifest(str(out))


def test_an_unknown_arm_field_injected_into_a_written_manifest_is_caught_on_read(tmp_path):
    """The arm entry is exact-closed, and this is what makes that check load-bearing.

    Mutation testing found it dead as originally tested: the producer always emits exactly
    the design's arm fields, so removing the check changed nothing that any test could see.
    Its real job is guarding a manifest that was edited AFTER it was written -- which is
    precisely the case a frozen artifact must not be trusted about.
    """
    out = tmp_path / "manifest.json"
    write_profile_manifest(_built(), str(out))

    poked = json.loads(out.read_text(encoding="utf-8"))
    poked["arms"][0]["surprise"] = "a field nothing validates"
    out.write_text(json.dumps(poked), encoding="utf-8", newline="")

    with pytest.raises(DecisionProfileError, match=r"unknown=\['surprise'\]"):
        read_profile_manifest(str(out))


def test_an_arm_missing_a_field_is_caught_on_read(tmp_path):
    out = tmp_path / "manifest.json"
    write_profile_manifest(_built(), str(out))

    poked = json.loads(out.read_text(encoding="utf-8"))
    del poked["arms"][0]["scoring_params"]
    out.write_text(json.dumps(poked), encoding="utf-8", newline="")

    with pytest.raises(DecisionProfileError, match=r"missing=\['scoring_params'\]"):
        read_profile_manifest(str(out))


def test_a_run_level_warmup_injected_into_a_written_manifest_is_caught_on_read(tmp_path):
    """Rejected -- by the run-level exact-closed field check, which fires first.

    Two layers forbid it and match= records which one does the work here. The producer's
    shape check is exact-closed, so an injected `warmup` is simply an unknown run field.
    validate_profile_manifest's dedicated "run-level warmup" rule is not redundant: it is
    what catches the same injection for a consumer that resolves a manifest WITHOUT going
    through this module -- which is exactly what B2 and B3 do.
    """
    out = tmp_path / "manifest.json"
    write_profile_manifest(_built(), str(out))

    poked = json.loads(out.read_text(encoding="utf-8"))
    poked["warmup"] = 2
    out.write_text(json.dumps(poked), encoding="utf-8", newline="")

    with pytest.raises(DecisionProfileError, match=r"unknown=\['warmup'\]"):
        read_profile_manifest(str(out))


def test_the_dedicated_run_level_warmup_rule_still_guards_the_consumer_path(tmp_path):
    # B2/B3 never call this module: they take a manifest dict and resolve arms from it.
    # For them, validate_profile_manifest's own rule is the only thing standing between a
    # run-level warmup and a second truth.
    from showdown_bot.eval.decision_profile import validate_profile_manifest

    m = _built()
    m["warmup"] = 2
    with pytest.raises(DecisionProfileError, match="run-level"):
        validate_profile_manifest(m)

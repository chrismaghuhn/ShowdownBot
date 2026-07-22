# showdown_bot/tests/test_holdout_disjointness.py
import pytest

from showdown_bot.eval.coverage_schedule import COVERAGE_MANIFEST_PATH, load_coverage_manifest
from showdown_bot.eval.holdout_disjointness import (
    HoldoutNotDisjointError, assert_disjoint_from_coverage, load_frozen_coverage_hashes,
)


def test_load_frozen_coverage_hashes_returns_the_four_real_coverage_opponent_hashes():
    # Expectation derived from the real, closed-schema-validated manifest itself -- not a copied
    # constant -- so this test tracks the manifest's actual frozen content rather than a second,
    # independently-maintained assumption of what it contains.
    manifest = load_coverage_manifest(COVERAGE_MANIFEST_PATH)
    expected = frozenset(
        manifest.team_content_hashes[team_id]
        for team_id in ("cov_foe_slot0", "cov_foe_slot1", "cov_foe_both", "cov_foe_tie")
    )
    result = load_frozen_coverage_hashes()
    assert result == expected
    assert len(result) == 4
    # The shared hero is not an opponent team -- its hash must never be treated as part of the
    # coverage opponent set this holdout must stay disjoint from.
    assert manifest.team_content_hashes["fixed_champions_v0"] not in result


def test_assert_disjoint_from_coverage_accepts_a_disjoint_holdout():
    holdout_content_hashes = {f"holdout_{i}": f"{i:016x}" for i in range(6)}
    result = assert_disjoint_from_coverage(holdout_content_hashes)
    assert result is None


def test_assert_disjoint_from_coverage_rejects_an_exact_hash_collision():
    manifest = load_coverage_manifest(COVERAGE_MANIFEST_PATH)
    colliding_hash = manifest.team_content_hashes["cov_foe_slot0"]
    holdout_content_hashes = {f"holdout_{i}": f"{i:016x}" for i in range(6)}
    holdout_content_hashes["holdout_2"] = colliding_hash

    with pytest.raises(HoldoutNotDisjointError) as exc_info:
        assert_disjoint_from_coverage(holdout_content_hashes)
    message = str(exc_info.value)
    assert "holdout_2" in message
    assert colliding_hash in message

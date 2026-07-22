"""Hash disjointness between the six future strength-holdout teams and the four opponent teams
of the frozen Champions coverage panel (DESIGN sec 3.3 / D-3: "the engineered coverage team set
and the holdout team set are disjoint and strictly separated; neither selection may optimize the
other, and holdout results never reshape coverage nor vice-versa"). Reads the real, closed-schema,
hash-pinned coverage manifest via ``coverage_schedule.load_coverage_manifest`` -- never a raw,
unchecked JSON load, and never a copied/hardcoded hash constant duplicating that manifest's own
frozen content."""
from __future__ import annotations

from showdown_bot.eval.coverage_schedule import (
    COVERAGE_MANIFEST_PATH, CoverageManifestError, load_coverage_manifest,
)

# The coverage manifest's four opponent-side team_ids, pinned here as an explicit expectation
# (not merely "whatever matchups happen to list") -- the manifest's own content is already
# cryptographically bound by load_coverage_manifest's expected_hash check, but this second,
# readable check gives a clear, specific failure if the pinned manifest is ever swapped for one
# with a different opponent roster, rather than silently adapting downstream code that assumes
# exactly these four.
_EXPECTED_COVERAGE_OPPONENT_IDS = frozenset({
    "cov_foe_slot0", "cov_foe_slot1", "cov_foe_both", "cov_foe_tie",
})


class HoldoutNotDisjointError(ValueError):
    """A holdout team's content hash collides with a frozen coverage opponent's -- the holdout
    set is not disjoint from the coverage team set, violating DESIGN's firewall requirement
    (D-3)."""


def load_frozen_coverage_hashes() -> frozenset[str]:
    """Loads the real coverage manifest and returns the four coverage OPPONENT teams' content
    hashes -- never the shared hero's. The hero (``fixed_champions_v0``) appears in the
    manifest's own ``team_content_hashes`` alongside the four opponents, but it is the bot's own
    team, not a "touched or coverage" opponent team; including it would make every future holdout
    hero comparison meaningless and is excluded by deriving the team_id set from
    ``matchups[*].opp_team`` rather than from ``team_content_hashes`` directly.

    Fails closed: any manifest read/schema/hash failure (``CoverageManifestError``, raised by
    ``load_coverage_manifest`` itself) propagates unwrapped, never swallowed and never replaced
    by an empty result. Also fails closed if the manifest's actual opponent team_id set is not
    exactly the four expected ids, or if any of them lacks a non-empty content hash."""
    manifest = load_coverage_manifest(COVERAGE_MANIFEST_PATH)
    opponent_ids = frozenset(matchup.opp_team for matchup in manifest.matchups)
    if opponent_ids != _EXPECTED_COVERAGE_OPPONENT_IDS:
        raise CoverageManifestError(
            f"coverage manifest's opponent team_ids {sorted(opponent_ids)} != expected "
            f"{sorted(_EXPECTED_COVERAGE_OPPONENT_IDS)} -- the pinned manifest no longer matches "
            "the opponent roster this check was written against"
        )
    hashes = []
    for team_id in sorted(opponent_ids):
        content_hash = manifest.team_content_hashes.get(team_id)
        if not content_hash:
            raise CoverageManifestError(
                f"coverage manifest has no non-empty content hash for opponent team {team_id!r}"
            )
        hashes.append(content_hash)
    return frozenset(hashes)


def assert_disjoint_from_coverage(holdout_content_hashes: dict[str, str]) -> None:
    """Asserts none of the holdout teams' content hashes collide with a frozen coverage
    opponent's. Returns ``None`` on success; raises ``HoldoutNotDisjointError`` naming every
    colliding holdout team_id and its colliding hash on failure -- deterministic (sorted by
    team_id), never a silent filter or automatic correction of the offending entries."""
    coverage_hashes = load_frozen_coverage_hashes()
    collisions = sorted(
        (team_id, content_hash)
        for team_id, content_hash in holdout_content_hashes.items()
        if content_hash in coverage_hashes
    )
    if collisions:
        detail = ", ".join(f"{team_id!r} (hash {content_hash!r})" for team_id, content_hash in collisions)
        raise HoldoutNotDisjointError(
            f"holdout team(s) collide with a frozen coverage opponent's content hash: {detail}"
        )

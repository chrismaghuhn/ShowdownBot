"""Gate B (Independent Strength Holdout) schedule construction (DESIGN sec 3.2)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

STRENGTH_HOLDOUT_PANEL_PATH = "config/eval/panels/panel_champions_strength_holdout_v0.yaml"
STRENGTH_HOLDOUT_MANIFEST_PATH = "config/eval/holdout/champions_strength_holdout_v0_manifest.json"
STRENGTH_HOLDOUT_SEED_BASE = "champions-strength-holdout-v0"  # PROPOSED, DESIGN:333-334
STRENGTH_HOLDOUT_FORMAT_ID = "gen9championsvgc2026regma"
STRENGTH_HOLDOUT_N_SEEDS = 15
STRENGTH_HOLDOUT_OPPONENT_POLICIES = ("heuristic", "max_damage")
# PROPOSED (grounding report sec 3): reuses I8-D/Coverage's standing Champions hero team.
STRENGTH_HOLDOUT_HERO_TEAM_PATH = "showdown_bot/teams/fixed_champions_v0.txt"

# Frozen at Task 13 step 3 from the real sealed six teams, panel, and manifest -- derived via the
# production functions (load_panel(...).panel_hash and strength_holdout_manifest_hash), never
# hand-entered. test_strength_holdout_freeze.py re-derives both and pins these constants to them.
STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH = "122764211b6db3ba"
STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH = "6c37277bd1bd2a71"


def _sha16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def strength_holdout_manifest_hash(manifest_path: str) -> str:
    """Content identity of the holdout manifest's authoritative team set (Task 13 hash-freeze).

    Hashes exactly the sorted ``(team_id, team_path, team_content_hash)`` projection -- the same
    triple ``verify_strength_holdout_baseline`` binds panel/baseline/on-disk against -- with this
    module's own ``_sha16`` + canonical-JSON convention. Deliberately independent of the manifest's
    incidental fields (source URLs, ranks, formatting) and of key order, so a provenance-only edit
    does not move it while any change to WHICH six teams are registered, their paths, or their
    sealed content does. Raises ``ValueError`` on a manifest that is not an object with a ``teams``
    list of the closed triple shape -- never a raw ``KeyError``/``OSError`` escaping to the caller.
    """
    try:
        man = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"holdout manifest at {manifest_path!r} could not be read: {exc}") from exc
    if not isinstance(man, dict) or not isinstance(man.get("teams"), list):
        raise ValueError("holdout manifest must be an object with a 'teams' list")
    projection = []
    for i, t in enumerate(man["teams"]):
        if not isinstance(t, dict):
            raise ValueError(f"holdout manifest teams[{i}] must be an object")
        try:
            triple = (t["team_id"], t["team_path"], t["team_content_hash"])
        except KeyError as exc:
            raise ValueError(f"holdout manifest teams[{i}] missing field {exc}") from exc
        if not all(isinstance(v, str) and v.strip() for v in triple):
            raise ValueError(f"holdout manifest teams[{i}] has a blank/non-string id/path/hash")
        projection.append(list(triple))
    return _sha16(json.dumps(sorted(projection), sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class BattleKey:
    holdout_team_id: str
    opponent_policy: str
    seed: int          # 0..14: the per-(team, policy) seed slot (DESIGN's own vocabulary)
    seed_index: int     # 0..179: GLOBAL contiguous index. `seed` repeats across the 12
                        # (team, policy) cells and must NEVER be passed to derive_battle_seed --
                        # only seed_index is unique per battle-key.


@dataclass(frozen=True)
class StrengthHoldoutSchedule:
    battle_keys: tuple[BattleKey, ...]
    schedule_hash: str
    panel_hash: str
    seed_base: str
    format_id: str


def build_strength_holdout_schedule(
    *, holdout_team_ids: list[str], panel_hash: str,
    seed_base: str = STRENGTH_HOLDOUT_SEED_BASE,
    n_seeds: int = STRENGTH_HOLDOUT_N_SEEDS,
    opponent_policies: tuple[str, ...] = STRENGTH_HOLDOUT_OPPONENT_POLICIES,
) -> StrengthHoldoutSchedule:
    if len(holdout_team_ids) != 6:
        raise ValueError(f"strength holdout requires exactly 6 teams, got {len(holdout_team_ids)}")
    if len(set(holdout_team_ids)) != 6:
        raise ValueError("holdout_team_ids must be unique")
    if list(holdout_team_ids) != sorted(holdout_team_ids):
        raise ValueError("holdout_team_ids must be pre-sorted for a deterministic hash")

    triples = [
        (team_id, policy, seed)
        for team_id in holdout_team_ids
        for policy in opponent_policies
        for seed in range(n_seeds)
    ]
    keys = tuple(
        BattleKey(holdout_team_id=t, opponent_policy=p, seed=s, seed_index=idx)
        for idx, (t, p, s) in enumerate(triples)
    )
    expected = len(holdout_team_ids) * len(opponent_policies) * n_seeds
    if len(keys) != expected:
        raise ValueError(f"expected {expected} battle-keys, built {len(keys)}")

    schedule_hash = _sha16(json.dumps(
        {
            "keys": [[k.holdout_team_id, k.opponent_policy, k.seed, k.seed_index] for k in keys],
            "seed_base": seed_base, "format_id": STRENGTH_HOLDOUT_FORMAT_ID,
            # panel_hash binds panel identity into schedule identity -- more directly than the
            # other gates' own compute_schedule_hash(version, rows) actually achieves. That
            # function hashes `version` (a bare label string from the panel YAML, not a content
            # hash) plus each row's hero_team_path/opp_team_path (path STRINGS, not content). A
            # team file edited in place -- same path, same version -- changes panel_hash (which
            # embeds every team's real .txt+.packed content hash, per panel.py's own docstring:
            # "editing a team file without changing its path changes panel_hash") without
            # changing version or any path string, so compute_schedule_hash would miss that edit
            # too. Hashing panel_hash here directly closes that gap instead of reproducing
            # compute_schedule_hash's own partial coverage.
            # compute_schedule_hash itself is still not reusable here, for a separate, structural
            # reason: its rows need hero_team_path/opp_team_path fields, and BattleKey has
            # neither -- only holdout_team_id, since team files don't exist before Task 13.
            "panel_hash": panel_hash,
        },
        sort_keys=True, separators=(",", ":"),
    ))
    return StrengthHoldoutSchedule(
        battle_keys=keys, schedule_hash=schedule_hash, panel_hash=panel_hash,
        seed_base=seed_base, format_id=STRENGTH_HOLDOUT_FORMAT_ID,
    )

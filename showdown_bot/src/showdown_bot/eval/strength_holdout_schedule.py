"""Gate B (Independent Strength Holdout) schedule construction (DESIGN sec 3.2)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

STRENGTH_HOLDOUT_PANEL_PATH = "config/eval/panels/panel_champions_strength_holdout_v0.yaml"
STRENGTH_HOLDOUT_MANIFEST_PATH = "config/eval/holdout/champions_strength_holdout_v0_manifest.json"
STRENGTH_HOLDOUT_SEED_BASE = "champions-strength-holdout-v0"  # PROPOSED, DESIGN:333-334
STRENGTH_HOLDOUT_FORMAT_ID = "gen9championsvgc2026regma"
STRENGTH_HOLDOUT_N_SEEDS = 15
STRENGTH_HOLDOUT_OPPONENT_POLICIES = ("heuristic", "max_damage")
# PROPOSED (grounding report sec 3): reuses I8-D/Coverage's standing Champions hero team.
STRENGTH_HOLDOUT_HERO_TEAM_PATH = "showdown_bot/teams/fixed_champions_v0.txt"

STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH = ""    # frozen once Task 13 seals the six teams
STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH = ""


def _sha16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


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
            # panel_hash binds panel identity into schedule identity, matching every other gate's
            # convention: coverage_schedule/i8d_schedule/panel_schedule/generalisation-planner and
            # schedule.py's own loader all bind it via compute_schedule_hash(version, rows) --
            # without this, two schedules built from the same six team IDs but different panel
            # content (different team files behind those IDs) would collide on schedule_hash.
            # compute_schedule_hash itself is not reusable here, and that is a deliberate,
            # disclosed divergence, not an oversight: its rows carry real hero_team_path/
            # opp_team_path strings, which change if a team's file content changes under a fixed
            # path. BattleKey has no such field -- only holdout_team_id -- because team files do
            # not exist until Task 13 seals them. Hashing panel_hash directly closes the same gap
            # without depending on paths that do not exist yet.
            "panel_hash": panel_hash,
        },
        sort_keys=True, separators=(",", ":"),
    ))
    return StrengthHoldoutSchedule(
        battle_keys=keys, schedule_hash=schedule_hash, panel_hash=panel_hash,
        seed_base=seed_base, format_id=STRENGTH_HOLDOUT_FORMAT_ID,
    )

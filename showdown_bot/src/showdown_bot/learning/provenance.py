"""Run provenance + FeatureContext minting for dataset export (Phase 3 slice 1b-B3).

Gathers the code/team/config fingerprint ONCE per run; mints a per-decision
FeatureContext with deterministic IDs (via the B2 ID helpers). No per-decision
git/subprocess calls.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

from showdown_bot.learning.export import make_run_id, make_game_id, make_decision_id
from showdown_bot.learning.features import FeatureContext


def git_sha_and_dirty() -> tuple[str, bool]:
    """Current commit + dirty flag; ('unknown', False) if git is unavailable.
    Call ONCE at run start (not per decision)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True).stdout.strip())
        return sha or "unknown", dirty
    except Exception:  # noqa: BLE001
        return "unknown", False


def _sha16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def team_hash(packed_team: str) -> str:
    return _sha16(packed_team or "")


def config_hash(config: dict) -> str:
    return _sha16(json.dumps(config, sort_keys=True, separators=(",", ":"), default=str))


def canonical_hash(value: object) -> str:
    """Stable 16-hex-char hash of any JSON-serializable value.

    Canonical form: sort_keys=True, no whitespace, default=str for non-JSON
    types (e.g. pathlib.Path).  Equivalent to config_hash but accepts any
    value (not just dict) so it can be used for lists, ints, etc.

    Used by from_env to hash rollout_config / move_priors / likely_sets
    into the config_hash so dataset consumers can tell which build produced rows.
    """
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return _sha16(payload)


def build_feature_context(
    *, git_sha: str, dirty_flag: bool, team_hash_: str, config_hash_: str, run_seed,
    game_index: int, decision_local_index: int, turn_number: int, our_side: str,
    format_id: str, mirror_flag: bool, teacher_config: dict, sampling_policy: str,
    dex=None, move_meta=None, speed_oracle=None, protect_priors_by_opp_slot=None,
) -> FeatureContext:
    run_id = make_run_id(git_sha, dirty_flag, team_hash_, config_hash_, run_seed)
    game_id = make_game_id(run_id, game_index)
    decision_id = make_decision_id(game_id, decision_local_index, turn_number, our_side)
    return FeatureContext(
        run_id=run_id, game_id=game_id, decision_id=decision_id,
        decision_local_index=decision_local_index, turn_number=turn_number, our_side=our_side,
        format_id=format_id, team_hash=team_hash_, config_hash=config_hash_, git_sha=git_sha,
        dirty_flag=dirty_flag, teacher_config=teacher_config, sampling_policy=sampling_policy,
        mirror_flag=mirror_flag, dex=dex, move_meta=move_meta, speed_oracle=speed_oracle,
        protect_priors_by_opp_slot=protect_priors_by_opp_slot,
    )

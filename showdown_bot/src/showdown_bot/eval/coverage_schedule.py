"""The fixed opponent-Mega COVERAGE battle schedule + closed-schema coverage manifest (Task 4).

Generation only -- this module builds and hashes the schedule; it never starts a server or a
battle. The schedule is a fixed, cyclic round-robin over the manifest's 8 matchups (4 coverage
cells x 2 opponent policies), materialised in one order that never changes:

    seed_index i  ->  manifest.matchups[i % 8]

At ``COVERAGE_MAX_BATTLES = 200`` this yields exactly 25 battles per matchup (200 / 8), a fixed
composition frozen by ``schedule_hash``. ``target_cell`` lives ONLY in the coverage manifest (the
standard panel/schedule schema has no such field); the offline constructibility proofs bind each
cell to a node-free proof board via ``COVERAGE_PROOF_BOARDS``.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.eval.panel import team_content_hash
from showdown_bot.eval.policies import is_known
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash

COVERAGE_SEED_BASE = "champions-coverage-v0"
COVERAGE_FORMAT = "gen9championsvgc2026regma"
COVERAGE_HERO_TEAM = "teams/fixed_champions_v0.txt"
COVERAGE_MAX_BATTLES = 200

COVERAGE_PANEL_PATH = "config/eval/panels/panel_champions_coverage_v0.yaml"
COVERAGE_MANIFEST_PATH = "config/eval/coverage/champions_coverage_v0_manifest.json"
# Frozen content-derived hashes (Task 4): panel_hash binds the four team files' CONTENT; the
# manifest hash binds the matchup order, target_cells and frozen team_content_hashes.
COVERAGE_EXPECTED_PANEL_HASH = "6f4c98537a320bed"
COVERAGE_EXPECTED_MANIFEST_HASH = "6278dc41907cf63c"

COVERAGE_CELLS = ("slot0", "slot1", "both_foe_slots", "order_tie")

# Each cell's node-free proof board (profile_fixtures): scored through the real path it forces that
# cell on the resulting MegaShapeCounts (see test_coverage_constructibility).
COVERAGE_PROOF_BOARDS = {
    "slot0": "mega_decision_dual_unequal_fixture",
    "slot1": "mega_decision_foe_slotb_fixture",
    "both_foe_slots": "mega_decision_both_foe_slots_fixture",
    "order_tie": "mega_decision_tie_fixture",
}

_MANIFEST_KEYS = frozenset({"version", "format_id", "matchups", "team_content_hashes"})
_MATCHUP_KEYS = frozenset({"hero_team", "opp_team", "opp_policy", "target_cell"})

_REPO_ROOT = Path(__file__).resolve().parents[4]  # eval -> showdown_bot(pkg) -> src -> showdown_bot -> repo


class CoverageManifestError(ValueError):
    """The coverage manifest is malformed, violates its closed schema, or fails its frozen hash."""


class CoverageScheduleError(ValueError):
    """The coverage schedule/panel cannot be built or re-verified (bad composition, hash, teams)."""


@dataclass(frozen=True)
class CoverageMatchup:
    hero_team: str
    opp_team: str
    opp_policy: str
    target_cell: str


@dataclass(frozen=True)
class CoverageManifest:
    version: str
    format_id: str
    matchups: tuple[CoverageMatchup, ...]
    team_content_hashes: dict[str, str]
    manifest_hash: str


def _manifest_hash(data: dict) -> str:
    canon = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()[:16]


def load_coverage_manifest(path: str = COVERAGE_MANIFEST_PATH,
                           *, expected_hash: str = COVERAGE_EXPECTED_MANIFEST_HASH) -> CoverageManifest:
    """Load + closed-schema-validate the coverage manifest and bind its frozen hash.

    A default (repo-relative) path resolves against the repo root, so this works from any CWD; an
    absolute path (e.g. a test's tmp file) is used as-is. Unknown/missing top-level or per-matchup
    keys, an unknown target_cell or opponent policy, or a hash mismatch all raise
    ``CoverageManifestError``.
    """
    full = path if os.path.isabs(path) else str(_REPO_ROOT / path)
    try:
        data = json.loads(Path(full).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageManifestError(f"cannot read coverage manifest {full!r}: {exc}") from exc
    if not isinstance(data, dict):
        raise CoverageManifestError("coverage manifest must be a JSON object")
    unknown = set(data) - _MANIFEST_KEYS
    missing = _MANIFEST_KEYS - set(data)
    if unknown or missing:
        raise CoverageManifestError(
            f"coverage manifest keys missing={sorted(missing)} unknown={sorted(unknown)}"
        )
    raw_matchups = data["matchups"]
    if not isinstance(raw_matchups, list) or not raw_matchups:
        raise CoverageManifestError("coverage manifest 'matchups' must be a non-empty list")
    matchups: list[CoverageMatchup] = []
    for i, m in enumerate(raw_matchups):
        if not isinstance(m, dict) or set(m) != _MATCHUP_KEYS:
            raise CoverageManifestError(
                f"matchup {i} must have exactly {sorted(_MATCHUP_KEYS)}, got {sorted(m) if isinstance(m, dict) else type(m)}"
            )
        if m["target_cell"] not in COVERAGE_CELLS:
            raise CoverageManifestError(f"matchup {i} unknown target_cell {m['target_cell']!r}")
        if not is_known(m["opp_policy"]):
            raise CoverageManifestError(f"matchup {i} unknown opp_policy {m['opp_policy']!r}")
        matchups.append(CoverageMatchup(
            hero_team=str(m["hero_team"]), opp_team=str(m["opp_team"]),
            opp_policy=str(m["opp_policy"]), target_cell=str(m["target_cell"]),
        ))
    thashes = data["team_content_hashes"]
    if not isinstance(thashes, dict) or not all(isinstance(v, str) and v for v in thashes.values()):
        raise CoverageManifestError("team_content_hashes must be a map of team -> non-empty hash")
    computed = _manifest_hash(data)
    if computed != expected_hash:
        raise CoverageManifestError(
            f"coverage manifest hash {computed!r} != expected {expected_hash!r} (content changed)"
        )
    return CoverageManifest(
        version=str(data["version"]), format_id=str(data["format_id"]),
        matchups=tuple(matchups), team_content_hashes=dict(thashes), manifest_hash=computed,
    )


def build_coverage_schedule(panel, manifest: CoverageManifest, *,
                            n_battles: int = COVERAGE_MAX_BATTLES, teams_root: str = ".") -> Schedule:
    """Build the fixed cyclic coverage schedule from ``panel`` + ``manifest``. Deterministic and
    hash-stable. Fails closed if a manifest opp_team is not in the panel (dev OR heldout) or an
    opp_policy is not in the panel's policies. ``n_battles`` may not exceed the D-2 cap."""
    if not isinstance(n_battles, int) or isinstance(n_battles, bool) or n_battles < 1:
        raise CoverageScheduleError(f"n_battles must be a positive int, got {n_battles!r}")
    if n_battles > COVERAGE_MAX_BATTLES:
        raise CoverageScheduleError(
            f"n_battles {n_battles} exceeds COVERAGE_MAX_BATTLES {COVERAGE_MAX_BATTLES}: the cap is bound"
        )
    teams = {t.team_id: (t, "dev") for t in panel.dev_teams}
    teams.update({t.team_id: (t, "heldout") for t in panel.heldout_teams})
    panel_policies = set(panel.policies)
    for m in manifest.matchups:
        if m.opp_team not in teams:
            raise CoverageScheduleError(
                f"manifest opp_team {m.opp_team!r} is not in the coverage panel (dev or heldout)"
            )
        if m.opp_policy not in panel_policies:
            raise CoverageScheduleError(
                f"policy {m.opp_policy!r} not in panel.policies {sorted(panel_policies)} — "
                f"panel_hash would not cover the schedule"
            )
    try:
        hero_hash = team_content_hash(teams_root, COVERAGE_HERO_TEAM)
    except Exception:  # noqa: BLE001 - hero_team_hash is nullable provenance
        hero_hash = None

    matchups = manifest.matchups
    rows: list[ScheduleRow] = []
    for i in range(n_battles):
        m = matchups[i % len(matchups)]
        team, split = teams[m.opp_team]
        rows.append(ScheduleRow(
            format_id=COVERAGE_FORMAT, hero_team_path=COVERAGE_HERO_TEAM, opp_policy=m.opp_policy,
            opp_team_path=team.team_path, seed_index=i, hero_team_hash=hero_hash,
            opp_team_hash=team.team_hash, panel_split=split,
        ))
    return Schedule(
        version=panel.version, rows=tuple(rows),
        schedule_hash=compute_schedule_hash(panel.version, rows), panel_hash=panel.panel_hash,
    )


def verify_coverage_schedule(schedule: Schedule, *, expected_battles: int = COVERAGE_MAX_BATTLES) -> None:
    """Re-lock the fixed coverage schedule at the execution point (never trust a caller's Schedule).

    Re-derives every structural invariant AND recomputes the hash: exactly ``expected_battles``
    rows, contiguous ``seed_index`` 0..N-1, every row COVERAGE_FORMAT + COVERAGE_HERO_TEAM, the
    matchup at each cyclic position (i % 8) is ONE fixed (opp_team_path, opp_policy) across cycles,
    there are exactly 8 distinct matchups each appearing exactly ``expected_battles // 8`` times,
    and ``compute_schedule_hash`` re-derives ``schedule.schedule_hash``.
    """
    rows = schedule.rows
    if len(rows) != expected_battles:
        raise CoverageScheduleError(
            f"coverage schedule must have exactly {expected_battles} rows, got {len(rows)}"
        )
    n_matchups = 8
    if expected_battles % n_matchups != 0:
        raise CoverageScheduleError(
            f"expected_battles {expected_battles} is not a whole multiple of {n_matchups} matchups"
        )
    per_matchup = expected_battles // n_matchups
    pos_matchup: dict[int, tuple[str, str]] = {}
    counts: dict[tuple[str, str], int] = {}
    for i, row in enumerate(rows):
        if row.seed_index != i:
            raise CoverageScheduleError(
                f"coverage row {i} seed_index {row.seed_index} != {i} (must be contiguous 0..N-1)"
            )
        if row.format_id != COVERAGE_FORMAT:
            raise CoverageScheduleError(f"coverage row {i} format_id {row.format_id!r} != {COVERAGE_FORMAT!r}")
        if row.hero_team_path != COVERAGE_HERO_TEAM:
            raise CoverageScheduleError(
                f"coverage row {i} hero_team_path {row.hero_team_path!r} != {COVERAGE_HERO_TEAM!r}"
            )
        matchup = (row.opp_team_path, row.opp_policy)
        pos = i % n_matchups
        if pos in pos_matchup:
            if pos_matchup[pos] != matchup:
                raise CoverageScheduleError(
                    f"coverage row {i} matchup {matchup!r} != position {pos}'s {pos_matchup[pos]!r} "
                    f"(the fixed composition was reshuffled)"
                )
        else:
            pos_matchup[pos] = matchup
        counts[matchup] = counts.get(matchup, 0) + 1
    if len(counts) != n_matchups or set(counts.values()) != {per_matchup}:
        raise CoverageScheduleError(
            f"coverage composition must be {n_matchups} matchups x {per_matchup} = {expected_battles}, "
            f"got {len(counts)} matchups with counts {sorted(counts.values())}"
        )
    recomputed = compute_schedule_hash(schedule.version, rows)
    if recomputed != schedule.schedule_hash:
        raise CoverageScheduleError(
            f"coverage schedule_hash {schedule.schedule_hash!r} != recomputed {recomputed!r} "
            f"(rows tampered or hash forged)"
        )


def verify_coverage_panel_and_teams(schedule, *, teams_root: str,
                                    expected_panel_hash: str = COVERAGE_EXPECTED_PANEL_HASH) -> None:
    """Bind the panel + team CONTENTS to the run identity: the content-derived ``panel_hash`` must
    equal the frozen coverage value, and every distinct team file is re-read + re-hashed NOW (a
    TOCTOU guard before battle 1). Raises ``CoverageScheduleError`` on any mismatch."""
    if schedule.panel_hash != expected_panel_hash:
        raise CoverageScheduleError(
            f"panel_hash {schedule.panel_hash!r} != expected coverage panel {expected_panel_hash!r}: "
            f"the panel or a team's content is not the approved one"
        )
    seen: dict[str, str] = {}
    for row in schedule.rows:
        for path, stored in ((row.hero_team_path, row.hero_team_hash),
                             (row.opp_team_path, row.opp_team_hash)):
            if stored is None:
                raise CoverageScheduleError(f"team {path!r} has no recorded content hash")
            if seen.get(path) == stored:
                continue
            actual = team_content_hash(teams_root, path)
            if actual != stored:
                raise CoverageScheduleError(
                    f"team file {path!r} content hash {actual!r} != recorded {stored!r}: "
                    f"the team files changed since the schedule was built"
                )
            seen[path] = stored

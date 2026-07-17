"""The fixed I8-D live-latency battle schedule (bound execution decisions, plan §5.4).

Generation only — this module builds and hashes the schedule; it never starts a server or a
battle. The schedule is a **fixed, cyclic round-robin over three dev matchup teams × two
opponent policies**, materialised in one order that never changes with exposure or latency:

    seed_index i  ->  I8D_MATCHUPS[i % 6]

At ``MAX_BATTLES = 200`` this yields the distribution ``34, 34, 33, 33, 33, 33`` (the first two
matchups take the +2 remainder). Held-out teams are excluded by construction and rejected if a
panel tries to supply one only from its held-out split. ``seed_index`` is ``0..n-1``,
contiguous, and belongs immutably to schedule row ``i``; the seed itself is
``derive_battle_seed(I8D_SEED_BASE, seed_index)`` (Channel A), so the whole seed set is fixed
before the first battle and bound through ``schedule_hash``.
"""
from __future__ import annotations

from showdown_bot.eval.panel import team_content_hash
from showdown_bot.eval.policies import is_known
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash
from showdown_bot.eval.panel_schedule import write_schedule_yaml

I8D_SEED_BASE = "champions-panel-v0-i8d-latency"
I8D_FORMAT = "gen9championsvgc2026regma"
I8D_HERO_TEAM = "teams/fixed_champions_v0.txt"
I8D_MAX_BATTLES = 200

# The six matchups in their FIXED order (dev team_id, opponent policy). Dev-only: the two
# held-out teams (rain_offense, disruption) are reserved for later independent work and never
# appear here.
I8D_MATCHUPS: tuple[tuple[str, str], ...] = (
    ("goodstuff", "heuristic"),
    ("goodstuff", "max_damage"),
    ("tailwind_offense", "heuristic"),
    ("tailwind_offense", "max_damage"),
    ("trick_room", "heuristic"),
    ("trick_room", "max_damage"),
)


class I8DScheduleError(ValueError):
    """The panel cannot supply the fixed I8-D dev matrix (missing/held-out team, unknown policy)."""


def build_i8d_schedule(panel, *, n_battles: int = I8D_MAX_BATTLES, teams_root: str = ".") -> Schedule:
    """Build the fixed cyclic I8-D schedule from ``panel``. Deterministic; hash-stable.

    Fails closed if a matchup team is not in the panel's **dev** split (so a held-out team can
    never enter I8-D), if a matchup team appears only in the held-out split, or if a matchup
    policy is unknown. ``n_battles`` may not exceed ``MAX_BATTLES`` — the D-2 cap is a schedule
    bound, not a caller knob.
    """
    if not isinstance(n_battles, int) or isinstance(n_battles, bool) or n_battles < 1:
        raise I8DScheduleError(f"n_battles must be a positive int, got {n_battles!r}")
    if n_battles > I8D_MAX_BATTLES:
        raise I8DScheduleError(
            f"n_battles {n_battles} exceeds MAX_BATTLES {I8D_MAX_BATTLES}: the D-2 cap is bound"
        )

    dev_by_id = {t.team_id: t for t in panel.dev_teams}
    heldout_ids = {t.team_id for t in panel.heldout_teams}
    panel_policies = set(panel.policies)
    for team_id, policy in I8D_MATCHUPS:
        if team_id not in dev_by_id:
            where = " (it is held-out)" if team_id in heldout_ids else ""
            raise I8DScheduleError(
                f"I8-D matchup team {team_id!r} is not in the panel's dev split{where}; the "
                f"fixed dev-only matrix cannot be built and no substitution is allowed"
            )
        if not is_known(policy):
            raise I8DScheduleError(f"unknown opponent policy {policy!r}")
        if policy not in panel_policies:
            raise I8DScheduleError(
                f"policy {policy!r} not in panel.policies {sorted(panel_policies)} — panel_hash "
                f"would not cover the schedule (untruthful provenance)"
            )

    # hero team hash is provenance only (not part of schedule_hash); best-effort like the
    # panel generator, so schedule construction never depends on the hero files being present.
    try:
        hero_hash = team_content_hash(teams_root, I8D_HERO_TEAM)
    except Exception:  # noqa: BLE001 - hero_team_hash is nullable provenance
        hero_hash = None

    rows: list[ScheduleRow] = []
    for i in range(n_battles):
        team_id, policy = I8D_MATCHUPS[i % len(I8D_MATCHUPS)]
        team = dev_by_id[team_id]
        rows.append(ScheduleRow(
            format_id=I8D_FORMAT,
            hero_team_path=I8D_HERO_TEAM,
            opp_policy=policy,
            opp_team_path=team.team_path,
            seed_index=i,
            hero_team_hash=hero_hash,
            opp_team_hash=team.team_hash,
            panel_split="dev",
        ))
    return Schedule(
        version=panel.version,
        rows=tuple(rows),
        schedule_hash=compute_schedule_hash(panel.version, rows),
        panel_hash=panel.panel_hash,
    )


def write_i8d_schedule(schedule: Schedule, path: str) -> None:
    """Emit the schedule as a YAML the runner's ``load_schedule`` round-trips (LF-only,
    byte-deterministic for identical inputs)."""
    write_schedule_yaml(schedule, path)

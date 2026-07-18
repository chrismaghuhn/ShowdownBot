"""The fixed I8-D live-latency battle schedule (bound execution decisions, plan §5.4).

Generation only — this module builds and hashes the schedule; it never starts a server or a
battle. The schedule is a **fixed, cyclic round-robin over three dev matchup teams × two
opponent policies**, materialised in one order that never changes with exposure or latency:

    seed_index i  ->  I8D_MATCHUPS[i % 6]

At ``MAX_BATTLES = 200`` this yields the distribution ``34, 34, 33, 33, 33, 33`` (the first two
matchups take the +2 remainder). Held-out teams are excluded by construction and rejected if a
panel tries to supply one only from its held-out split. ``seed_index`` is ``0..n-1``,
contiguous, and belongs immutably to schedule row ``i``; the seed itself is
``derive_battle_seed(I8D_SEED_BASE, seed_index)`` (Channel A). The ``seed_index`` values are
bound through ``schedule_hash`` (``compute_schedule_hash`` covers them), but the seed
**namespace** ``I8D_SEED_BASE`` is NOT in that hash -- it is bound instead by explicit
verification at the execution point: ``i8d_runner`` asserts ``SHOWDOWN_BATTLE_SEED_BASE ==
I8D_SEED_BASE`` and proves the server's Channel-A seed log matches ``derive_battle_seed`` before
any verdict is written.
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

# The canonical champions panel and its FROZEN content-derived panel_hash (re-review blocker 2).
# ``panel_hash`` (eval/panel.py) covers each team's CONTENT hash, so locking it to this value binds
# the exact team file contents -- which ``schedule_hash`` (paths/policies/indices only) does not.
# The value is the P3-frozen champions panel_hash recorded in committed evidence
# (data/eval/champions-panel-v0/smoke/report.json).
I8D_PANEL_PATH = "config/eval/panels/panel_champions_v0.yaml"
I8D_EXPECTED_PANEL_HASH = "aac1ea30446fde88"

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


def verify_i8d_schedule(schedule: Schedule, *, expected_battles: int = I8D_MAX_BATTLES) -> None:
    """Re-lock the fixed I8-D schedule at the EXECUTION point (code-review finding 3).

    The runner must never trust a caller's ``Schedule`` or its self-reported ``schedule_hash``: a
    truncated or replaced schedule would run different battles under the approved identity. This
    re-derives every structural invariant AND recomputes the hash. Raises ``I8DScheduleError`` on
    the first deviation:

      - exactly ``expected_battles`` rows (default the D-2 cap, 200), ``seed_index`` contiguous
        ``0..N-1``;
      - every row: ``format_id == I8D_FORMAT``, ``hero_team_path == I8D_HERO_TEAM``,
        ``panel_split == "dev"`` (held-out teams can never enter);
      - ``opp_policy`` follows ``I8D_MATCHUPS`` in the fixed cyclic order, and each matchup
        position keeps ONE opponent team across cycles, with the two policies of a matchup team
        naming the SAME team (binds the three dev teams without needing the panel here);
      - ``compute_schedule_hash(version, rows) == schedule.schedule_hash`` (recomputed, not
        trusted).
    """
    rows = schedule.rows
    if len(rows) != expected_battles:
        raise I8DScheduleError(
            f"I8-D schedule must have exactly {expected_battles} rows, got {len(rows)}"
        )
    team_for_pos: dict[int, str] = {}
    for i, row in enumerate(rows):
        pos = i % len(I8D_MATCHUPS)
        _expected_team_id, expected_policy = I8D_MATCHUPS[pos]
        if row.seed_index != i:
            raise I8DScheduleError(
                f"I8-D row {i} seed_index {row.seed_index} != {i} (must be contiguous 0..N-1)"
            )
        if row.format_id != I8D_FORMAT:
            raise I8DScheduleError(f"I8-D row {i} format_id {row.format_id!r} != {I8D_FORMAT!r}")
        if row.hero_team_path != I8D_HERO_TEAM:
            raise I8DScheduleError(
                f"I8-D row {i} hero_team_path {row.hero_team_path!r} != {I8D_HERO_TEAM!r}"
            )
        if row.panel_split != "dev":
            raise I8DScheduleError(
                f"I8-D row {i} panel_split {row.panel_split!r} != 'dev' (held-out teams excluded)"
            )
        if row.opp_policy != expected_policy:
            raise I8DScheduleError(
                f"I8-D row {i} opp_policy {row.opp_policy!r} != {expected_policy!r} "
                f"(matchup order changed)"
            )
        if pos in team_for_pos:
            if row.opp_team_path != team_for_pos[pos]:
                raise I8DScheduleError(
                    f"I8-D row {i} opp_team_path {row.opp_team_path!r} != {team_for_pos[pos]!r} "
                    f"(the matchup's opponent team was swapped mid-schedule)"
                )
        else:
            team_for_pos[pos] = row.opp_team_path
    # Each dev team fields two policies: positions (0,1)=goodstuff, (2,3)=tailwind, (4,5)=trick_room
    # must each name ONE team, or the six matchups do not cover exactly three dev teams.
    for a, b in ((0, 1), (2, 3), (4, 5)):
        if a in team_for_pos and b in team_for_pos and team_for_pos[a] != team_for_pos[b]:
            raise I8DScheduleError(
                f"I8-D matchup positions {a},{b} must share one dev team, got "
                f"{team_for_pos[a]!r} vs {team_for_pos[b]!r}"
            )
    recomputed = compute_schedule_hash(schedule.version, rows)
    if recomputed != schedule.schedule_hash:
        raise I8DScheduleError(
            f"I8-D schedule_hash {schedule.schedule_hash!r} != recomputed {recomputed!r} "
            f"(rows tampered or hash forged)"
        )


def verify_i8d_panel_and_teams(schedule, *, teams_root: str,
                               expected_panel_hash: str = I8D_EXPECTED_PANEL_HASH) -> None:
    """Bind the panel + team CONTENTS to the run identity (re-review blocker 2).

    ``schedule_hash`` covers only team PATHS, policies and indices, so different team CONTENTS under
    the same paths would share a verdict identity. This closes that hole two ways:

      - the content-derived ``panel_hash`` (``eval/panel.py`` hashes each team's ``.txt`` + ``.packed``)
        must equal the FROZEN champions value, so a swapped panel or any changed team content is
        refused;
      - every distinct team file is re-read NOW and re-hashed, proving the files on disk are exactly
        the ones the schedule was built from and have not changed since (a TOCTOU guard before
        battle 1).

    Raises ``I8DScheduleError`` on any mismatch. Requires the team files to be present (the
    authorizable CLI path calls this with the real ``teams_root`` before the first battle).
    """
    from showdown_bot.eval.panel import team_content_hash

    if schedule.panel_hash != expected_panel_hash:
        raise I8DScheduleError(
            f"panel_hash {schedule.panel_hash!r} != expected champions panel {expected_panel_hash!r}: "
            f"the panel or a team's content is not the approved one"
        )
    seen: dict[str, str] = {}
    for row in schedule.rows:
        for path, stored in ((row.hero_team_path, row.hero_team_hash),
                             (row.opp_team_path, row.opp_team_hash)):
            if stored is None:
                raise I8DScheduleError(
                    f"team {path!r} has no recorded content hash; its contents cannot be bound"
                )
            if seen.get(path) == stored:
                continue
            actual = team_content_hash(teams_root, path)
            if actual != stored:
                raise I8DScheduleError(
                    f"team file {path!r} content hash {actual!r} != the schedule's recorded "
                    f"{stored!r}: the team files changed since the schedule was built"
                )
            seen[path] = stored


def write_i8d_schedule(schedule: Schedule, path: str) -> None:
    """Emit the schedule as a YAML the runner's ``load_schedule`` round-trips (LF-only,
    byte-deterministic for identical inputs)."""
    write_schedule_yaml(schedule, path)

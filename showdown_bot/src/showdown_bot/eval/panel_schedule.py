"""Panel-driven schedule generation (T3d).

Turns a `Panel` into T1c-format `Schedule`s: dev = (dev_team × policy) cells, held-out
gated behind an explicit `confirm_heldout=True`. Reproducible-only by default (`random`
and other non-reproducible policies require `allow_nonreproducible=True`, T3-CC-3).
`write_schedule_yaml` emits a YAML the existing `eval/schedule.load_schedule` round-trips
(schedule_hash stable, panel_hash preserved).
"""
from __future__ import annotations

import yaml

from showdown_bot.eval.policies import is_known, is_reproducible
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash

_DEFAULT_HERO = "teams/fixed_team.txt"
_DEFAULT_FORMAT = "gen9vgc2025regi"


class PanelScheduleError(ValueError):
    """Invalid generation request (unknown/non-reproducible policy, missing confirm, …)."""


def _resolve_policies(panel, policies, allow_nonreproducible: bool) -> list[str]:
    if policies is None:
        chosen = list(panel.policies)
        if not allow_nonreproducible:
            chosen = [p for p in chosen if is_reproducible(p)]
        if not chosen:
            raise PanelScheduleError("no reproducible policies in the panel (or all filtered out)")
        return chosen
    for p in policies:
        if not is_known(p):
            raise PanelScheduleError(f"unknown policy {p!r}")
        if not is_reproducible(p) and not allow_nonreproducible:
            raise PanelScheduleError(
                f"non-reproducible policy {p!r} requires allow_nonreproducible=True"
            )
    if not policies:
        raise PanelScheduleError("empty policy list")
    return list(policies)


def _build(panel, teams, hero_team_path, format_id, policies, seeds_per_cell) -> Schedule:
    if seeds_per_cell < 1:
        raise PanelScheduleError("seeds_per_cell must be >= 1")
    rows: list[ScheduleRow] = []
    idx = 0
    for team in teams:
        for policy in policies:
            for _ in range(seeds_per_cell):
                rows.append(ScheduleRow(
                    format_id=format_id, hero_team_path=hero_team_path,
                    opp_policy=policy, opp_team_path=team.team_path, seed_index=idx,
                ))
                idx += 1
    return Schedule(
        version=panel.version, rows=tuple(rows),
        schedule_hash=compute_schedule_hash(panel.version, rows), panel_hash=panel.panel_hash,
    )


def generate_dev_schedule(panel, *, hero_team_path=_DEFAULT_HERO, format_id=_DEFAULT_FORMAT,
                          policies=None, seeds_per_cell=1, allow_nonreproducible=False) -> Schedule:
    chosen = _resolve_policies(panel, policies, allow_nonreproducible)
    return _build(panel, panel.dev_teams, hero_team_path, format_id, chosen, seeds_per_cell)


def generate_heldout_schedule(panel, *, confirm_heldout=False, hero_team_path=_DEFAULT_HERO,
                              format_id=_DEFAULT_FORMAT, policies=None, seeds_per_cell=1,
                              allow_nonreproducible=False) -> Schedule:
    if not confirm_heldout:
        raise PanelScheduleError(
            "held-out schedule generation requires confirm_heldout=True (T3-CC-1)"
        )
    chosen = _resolve_policies(panel, policies, allow_nonreproducible)
    return _build(panel, panel.heldout_teams, hero_team_path, format_id, chosen, seeds_per_cell)


def write_schedule_yaml(schedule: Schedule, path: str) -> None:
    """Emit a YAML the T1c loader round-trips (schedule_hash stable, panel_hash preserved)."""
    data: dict = {"version": schedule.version}
    if schedule.panel_hash is not None:
        data["panel_hash"] = schedule.panel_hash
    data["rows"] = [
        {
            "format_id": r.format_id, "hero_team_path": r.hero_team_path,
            "opp_policy": r.opp_policy, "opp_team_path": r.opp_team_path,
            "seed_index": r.seed_index,
        }
        for r in schedule.rows
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)

"""Panel-driven schedule generation (T3d).

Turns a `Panel` into T1c-format `Schedule`s: dev = (dev_team × policy) cells, held-out
gated behind an explicit `confirm_heldout=True`. Reproducible-only by default (`random`
and other non-reproducible policies require `allow_nonreproducible=True`, T3-CC-3).
`write_schedule_yaml` emits a YAML the existing `eval/schedule.load_schedule` round-trips
(schedule_hash stable, panel_hash preserved). `seeds_per_cell` accepts an int or a
per-policy mapping (T4).
"""
from __future__ import annotations

import yaml

from showdown_bot.eval.panel import PanelError, team_content_hash
from showdown_bot.eval.policies import is_known, is_reproducible
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash

_DEFAULT_HERO = "teams/fixed_team.txt"
_DEFAULT_FORMAT = "gen9vgc2025regi"


class PanelScheduleError(ValueError):
    """Invalid generation request (unknown/non-reproducible policy, missing confirm, …)."""


def _hero_team_hash(teams_root: str, hero_team_path: str) -> str | None:
    """Content hash of the hero team (T3e P4 provenance). Best-effort: if the team files
    are missing, return None (the row's hero_team_hash is nullable)."""
    try:
        return team_content_hash(teams_root, hero_team_path)
    except PanelError:
        return None


def _resolve_policies(panel, policies, allow_nonreproducible: bool) -> list[str]:
    # Chosen policies MUST be a subset of panel.policies so panel_hash actually covers the
    # schedule (T3e P1). The default (policies=None) draws from panel.policies and is a subset
    # by construction; an explicit list is checked member-by-member.
    panel_policies = set(panel.policies)
    if policies is None:
        chosen = list(panel.policies)
        if not allow_nonreproducible:
            chosen = [p for p in chosen if is_reproducible(p)]
        if not chosen:
            raise PanelScheduleError("no reproducible policies in the panel (or all filtered out)")
        return chosen
    if not policies:
        raise PanelScheduleError("empty policy list")
    for p in policies:
        if not is_known(p):
            raise PanelScheduleError(f"unknown policy {p!r}")
        if p not in panel_policies:
            raise PanelScheduleError(
                f"policy {p!r} not in panel.policies {sorted(panel_policies)} — it would not be "
                f"covered by panel_hash (untruthful provenance)"
            )
        if not is_reproducible(p) and not allow_nonreproducible:
            raise PanelScheduleError(
                f"non-reproducible policy {p!r} requires allow_nonreproducible=True"
            )
    return list(policies)


def _validate_seeds_per_cell(seeds_per_cell, policies) -> None:
    if isinstance(seeds_per_cell, bool):
        raise PanelScheduleError(f"seeds_per_cell must be an int or a mapping, got {seeds_per_cell!r}")
    if isinstance(seeds_per_cell, int):
        if seeds_per_cell < 1:
            raise PanelScheduleError("seeds_per_cell must be >= 1")
        return
    unknown = set(seeds_per_cell) - set(policies)
    if unknown:
        raise PanelScheduleError(
            f"seeds_per_cell has policies not in the chosen set: {sorted(unknown)}"
        )
    missing = set(policies) - set(seeds_per_cell)
    if missing:
        raise PanelScheduleError(f"seeds_per_cell missing policies: {sorted(missing)}")
    for p, n in seeds_per_cell.items():
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise PanelScheduleError(f"seeds_per_cell[{p!r}] must be an int >= 1, got {n!r}")


def _seeds_for(policy: str, seeds_per_cell) -> int:
    """Per-cell seed count: a plain int applies to every cell; a mapping is per-policy."""
    return seeds_per_cell if isinstance(seeds_per_cell, int) else seeds_per_cell[policy]


def _build(panel, teams, hero_team_path, hero_team_hash, format_id, policies,
           seeds_per_cell, panel_split) -> Schedule:
    _validate_seeds_per_cell(seeds_per_cell, policies)
    rows: list[ScheduleRow] = []
    idx = 0
    for team in teams:
        for policy in policies:
            for _ in range(_seeds_for(policy, seeds_per_cell)):
                rows.append(ScheduleRow(
                    format_id=format_id, hero_team_path=hero_team_path,
                    opp_policy=policy, opp_team_path=team.team_path, seed_index=idx,
                    hero_team_hash=hero_team_hash,   # T3e P4 provenance
                    opp_team_hash=team.team_hash,    # straight from the PanelTeam content hash
                    panel_split=panel_split,         # T3f Task 4 provenance ("dev"/"heldout")
                ))
                idx += 1
    return Schedule(
        version=panel.version, rows=tuple(rows),
        schedule_hash=compute_schedule_hash(panel.version, rows), panel_hash=panel.panel_hash,
    )


def generate_dev_schedule(panel, *, hero_team_path=_DEFAULT_HERO, format_id=_DEFAULT_FORMAT,
                          policies=None, seeds_per_cell=1, allow_nonreproducible=False,
                          teams_root=".") -> Schedule:
    chosen = _resolve_policies(panel, policies, allow_nonreproducible)
    hero_hash = _hero_team_hash(teams_root, hero_team_path)
    return _build(panel, panel.dev_teams, hero_team_path, hero_hash, format_id, chosen,
                  seeds_per_cell, "dev")


def generate_heldout_schedule(panel, *, confirm_heldout=False, hero_team_path=_DEFAULT_HERO,
                              format_id=_DEFAULT_FORMAT, policies=None, seeds_per_cell=1,
                              allow_nonreproducible=False, teams_root=".") -> Schedule:
    if not confirm_heldout:
        raise PanelScheduleError(
            "held-out schedule generation requires confirm_heldout=True (T3-CC-1)"
        )
    chosen = _resolve_policies(panel, policies, allow_nonreproducible)
    hero_hash = _hero_team_hash(teams_root, hero_team_path)
    return _build(panel, panel.heldout_teams, hero_team_path, hero_hash, format_id, chosen,
                  seeds_per_cell, "heldout")


def write_schedule_yaml(schedule: Schedule, path: str) -> None:
    """Emit a YAML the T1c loader round-trips (schedule_hash stable, panel_hash preserved)."""
    data: dict = {"version": schedule.version}
    if schedule.panel_hash is not None:
        data["panel_hash"] = schedule.panel_hash
    rows_out: list[dict] = []
    for r in schedule.rows:
        row: dict = {
            "format_id": r.format_id, "hero_team_path": r.hero_team_path,
            "opp_policy": r.opp_policy, "opp_team_path": r.opp_team_path,
            "seed_index": r.seed_index,
        }
        # Emit provenance fields only when present (legacy rows omit them).
        if r.hero_team_hash is not None:
            row["hero_team_hash"] = r.hero_team_hash          # T3e P4
        if r.opp_team_hash is not None:
            row["opp_team_hash"] = r.opp_team_hash            # T3e P4
        if r.panel_split is not None:
            row["panel_split"] = r.panel_split                # T3f Task 4
        rows_out.append(row)
    data["rows"] = rows_out
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)

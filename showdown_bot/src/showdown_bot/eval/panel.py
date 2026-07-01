"""Panel v001 schema + content-hashed panel_hash + dev/held-out split (T3a).

`panel_hash` covers the panel version, policy list, dev/held-out split, and per-team
`{team_id, archetype, team_path, team_hash}` where `team_hash` is a **content** hash of the
`.txt` + `.packed` (Fix 1) — so editing a team file without changing its path changes
`panel_hash`. Policies are validated against the central `eval/policies` registry.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from showdown_bot.eval.policies import is_known

_TEAM_REQUIRED = frozenset({"team_id", "team_path", "archetype"})


class PanelError(ValueError):
    """The panel file is malformed, references a missing team, or violates the split."""


@dataclass(frozen=True)
class PanelTeam:
    team_id: str
    team_path: str
    archetype: str
    team_hash: str  # content hash of the .txt + .packed (Fix 1)


@dataclass(frozen=True)
class Panel:
    version: str
    policies: tuple[str, ...]
    dev_teams: tuple[PanelTeam, ...]
    heldout_teams: tuple[PanelTeam, ...]
    panel_hash: str


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def _team_content_hash(teams_root: str, team_path: str) -> str:
    txt = Path(teams_root) / team_path
    packed = txt.with_suffix(".packed")
    if not txt.exists() or not packed.exists():
        raise PanelError(f"team files missing for {team_path!r}: need {txt} + {packed}")
    return _sha16(_canonical({
        "team_txt_content": txt.read_text(encoding="utf-8"),
        "packed_content": packed.read_text(encoding="utf-8"),
    }))


def _load_team_list(raw, teams_root: str, side: str) -> list[PanelTeam]:
    if not isinstance(raw, list):
        raise PanelError(f"{side} must be a list")
    teams: list[PanelTeam] = []
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            raise PanelError(f"{side}[{i}] is not a mapping")
        keys = set(t.keys())
        missing = _TEAM_REQUIRED - keys
        unknown = keys - _TEAM_REQUIRED
        if missing:
            raise PanelError(f"{side}[{i}] missing fields: {sorted(missing)}")
        if unknown:
            raise PanelError(f"{side}[{i}] unknown fields: {sorted(unknown)}")
        team_path = str(t["team_path"])
        teams.append(PanelTeam(
            team_id=str(t["team_id"]),
            team_path=team_path,
            archetype=str(t["archetype"]),
            team_hash=_team_content_hash(teams_root, team_path),
        ))
    return teams


def load_panel(path: str, *, teams_root: str = ".") -> Panel:
    """Load + validate a panel YAML; `teams_root` resolves each team's `team_path`."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise PanelError("panel must be a mapping")
    for key in ("version", "policies", "dev_teams", "heldout_teams"):
        if key not in data:
            raise PanelError(f"panel missing required key: {key}")

    version = str(data["version"])
    policies_raw = data["policies"]
    if not isinstance(policies_raw, list) or not policies_raw:
        raise PanelError("policies must be a non-empty list")
    policies = tuple(str(p) for p in policies_raw)
    for p in policies:
        if not is_known(p):
            raise PanelError(f"unknown policy {p!r} (see eval/policies.POLICIES)")

    dev = _load_team_list(data["dev_teams"], teams_root, "dev_teams")
    held = _load_team_list(data["heldout_teams"], teams_root, "heldout_teams")
    if not dev or not held:
        raise PanelError("dev_teams and heldout_teams must both be non-empty")
    overlap = {t.team_id for t in dev} & {t.team_id for t in held}
    if overlap:
        raise PanelError(f"teams in both dev and held-out: {sorted(overlap)}")

    panel_hash = _sha16(_canonical({
        "version": version,
        "policies": list(policies),
        "dev": [[t.team_id, t.archetype, t.team_path, t.team_hash] for t in dev],
        "heldout": [[t.team_id, t.archetype, t.team_path, t.team_hash] for t in held],
    }))
    return Panel(
        version=version, policies=policies,
        dev_teams=tuple(dev), heldout_teams=tuple(held), panel_hash=panel_hash,
    )

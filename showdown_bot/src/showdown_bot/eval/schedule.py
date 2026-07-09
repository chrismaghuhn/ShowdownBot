"""Non-mirror eval schedule (T1c).

A versioned list of battles for the non-mirror gauntlet. Each row pairs our team against
an opponent team + policy and carries a ``seed_index``. Under Channel A (per-battle seed =
server base+counter), ``seed_index`` aligns with the server's creation counter ONLY by
execution order, so the loader enforces unique + contiguous-from-0 indices and the runner
executes rows in that order (parent plan T1-CC-B). ``schedule_hash`` is a stable canonical
digest for the report.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import yaml

# The format field is either `format_id` (preferred) or `config_id` (deprecated alias,
# T3a). Exactly one is required. The rest are core required fields.
_CORE_REQUIRED = frozenset({"hero_team_path", "opp_policy", "opp_team_path", "seed_index"})
_FORMAT_FIELDS = frozenset({"format_id", "config_id"})
# Optional per-row provenance: NOT part of schedule identity (excluded from schedule_hash);
# legacy rows omit them -> None. team hashes (T3e P4), panel_split (T3f Task 4).
_OPTIONAL_FIELDS = frozenset({"hero_team_hash", "opp_team_hash", "panel_split"})
_ALLOWED_FIELDS = _CORE_REQUIRED | _FORMAT_FIELDS | _OPTIONAL_FIELDS
_PANEL_SPLITS = frozenset({"dev", "heldout"})
# Single source of truth for known policies is the T3a registry (eval/policies.py).
# (Implemented-vs-declared is a runner-level concern — the loader only checks "known".)
from showdown_bot.eval.policies import POLICIES as _POLICIES  # noqa: E402

KNOWN_POLICIES = frozenset(_POLICIES)


class ScheduleError(ValueError):
    """The schedule file is malformed or violates the seed_index contract."""


@dataclass(frozen=True)
class ScheduleRow:
    format_id: str  # was `config_id` (T3a rename); loader still accepts the config_id alias
    hero_team_path: str
    opp_policy: str
    opp_team_path: str
    seed_index: int
    hero_team_hash: str | None = None  # T3e P4 provenance; not in schedule_hash
    opp_team_hash: str | None = None   # T3e P4 provenance; not in schedule_hash
    panel_split: str | None = None     # T3f Task 4 provenance ("dev"/"heldout"); not in schedule_hash


@dataclass(frozen=True)
class Schedule:
    version: str
    rows: tuple[ScheduleRow, ...]
    schedule_hash: str
    panel_hash: str | None = None  # set by the T3d panel generator; legacy schedules -> None

    @property
    def reproducible(self) -> bool:
        """False iff any row uses a non-reproducible policy (e.g. random) — T3-CC-3."""
        from showdown_bot.eval.policies import is_reproducible
        return all(is_reproducible(r.opp_policy) for r in self.rows)


def _canonical_hash(payload) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def compute_schedule_hash(version: str, rows) -> str:
    """schedule_hash over VALUES only (key names excluded) — shared by loader + generator."""
    return _canonical_hash({
        "version": version,
        "rows": [
            [r.format_id, r.hero_team_path, r.opp_policy, r.opp_team_path, r.seed_index]
            for r in rows
        ],
    })


def load_schedule(path: str) -> Schedule:
    """Load + validate a schedule YAML. Raises ``ScheduleError`` on any violation."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict) or "version" not in data:
        raise ScheduleError("schedule must be a mapping with a 'version' key")
    version = str(data["version"])

    raw_rows = data.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ScheduleError("schedule must have a non-empty 'rows' list")

    rows: list[ScheduleRow] = []
    for i, r in enumerate(raw_rows):
        if not isinstance(r, dict):
            raise ScheduleError(f"row {i} is not a mapping")
        keys = set(r.keys())
        fmt_keys = keys & _FORMAT_FIELDS
        if len(fmt_keys) != 1:
            raise ScheduleError(
                f"row {i} must have exactly one of format_id/config_id "
                f"(config_id is a deprecated alias), got {sorted(fmt_keys)}"
            )
        missing = _CORE_REQUIRED - keys
        unknown = keys - _ALLOWED_FIELDS
        if missing:
            raise ScheduleError(f"row {i} missing fields: {sorted(missing)}")
        if unknown:
            raise ScheduleError(f"row {i} unknown fields: {sorted(unknown)}")
        format_id = str(r["format_id"] if "format_id" in r else r["config_id"])
        policy = str(r["opp_policy"])
        if policy not in KNOWN_POLICIES:
            raise ScheduleError(
                f"row {i} unknown opp_policy {policy!r} (known: {sorted(KNOWN_POLICIES)})"
            )
        try:
            seed_index = int(r["seed_index"])
        except (TypeError, ValueError):
            raise ScheduleError(f"row {i} seed_index not an int: {r['seed_index']!r}") from None
        hero_team_hash = r.get("hero_team_hash")  # T3e P4 provenance; absent -> None (legacy)
        opp_team_hash = r.get("opp_team_hash")
        panel_split = r.get("panel_split")        # T3f Task 4 provenance; absent -> None (legacy)
        if panel_split is not None and panel_split not in _PANEL_SPLITS:
            raise ScheduleError(
                f"row {i} panel_split must be one of {sorted(_PANEL_SPLITS)} or absent, "
                f"got {panel_split!r}"
            )
        rows.append(
            ScheduleRow(
                format_id=format_id,
                hero_team_path=str(r["hero_team_path"]),
                opp_policy=policy,
                opp_team_path=str(r["opp_team_path"]),
                seed_index=seed_index,
                hero_team_hash=str(hero_team_hash) if hero_team_hash is not None else None,
                opp_team_hash=str(opp_team_hash) if opp_team_hash is not None else None,
                panel_split=str(panel_split) if panel_split is not None else None,
            )
        )

    rows.sort(key=lambda x: x.seed_index)
    indices = [r.seed_index for r in rows]
    if len(set(indices)) != len(indices):
        raise ScheduleError(f"seed_index values must be unique: {indices}")
    if indices != list(range(len(indices))):
        raise ScheduleError(f"seed_index must be contiguous from 0: got {indices}")

    panel_hash = data.get("panel_hash")
    panel_hash = str(panel_hash) if panel_hash is not None else None
    return Schedule(
        version=version, rows=tuple(rows),
        schedule_hash=compute_schedule_hash(version, rows), panel_hash=panel_hash,
    )


def verify_schedule_alignment(schedule: Schedule, seed_log_path: str, base: str):
    """Assert the server seed log lines up with the schedule (Channel-A guard).

    Runs ``verify_seed_log`` for exactly ``len(schedule.rows)`` battles (fails fast on a
    retry/extra battle or a Python↔server derivation mismatch), then cross-checks that
    each row's ``seed_index`` equals the corresponding logged ``battle_index``. Returns
    the parsed seed-log records.
    """
    # Imported here to keep the module import graph flat (seeding has no schedule dep).
    from showdown_bot.eval.seeding import verify_seed_log

    records = verify_seed_log(seed_log_path, base, len(schedule.rows))
    for row, rec in zip(schedule.rows, records):
        if row.seed_index != rec["battle_index"]:
            raise ScheduleError(
                f"schedule/seed-log misalignment: row seed_index {row.seed_index} "
                f"!= logged battle_index {rec['battle_index']}"
            )
    return records

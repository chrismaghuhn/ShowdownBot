"""Baseline manifest loader + drift-refusing verification + winner-sequence spot-check
(T6 Task 3, spec Sec.2).

A baseline manifest freezes a heuristic policy's reference run against a fully specified
working-tree state -- panel, teams, schedules, server provenance, patch, and reference
results. ``verify_baseline`` re-derives every one of these from the CURRENT tree and refuses
(raises ``BaselineDriftError``) the moment any single one no longer matches: "baseline drift
-> refuse" (spec Sec.2). A baseline manifest is meant to be immutable once committed (see
``test_baseline.py::test_baseline_manifest_git_immutability`` for the git-history
enforcement, stricter than the T6 Task 1 ledger's append-only check).

Schema note (spec-gap resolution, flagged for spec amendment): spec Sec.2's example manifest
lists only ``dev_schedule_hash``/``heldout_schedule_hash`` -- a hash alone is not loadable.
This module adds ``dev_schedule_path`` (required) and ``heldout_schedule_path`` (optional,
travels with the other four ``heldout_*`` fields) so ``verify_baseline`` has something to
pass to ``load_schedule``. Both are repo-relative paths, consistent with
``reference_jsonl``/``heldout_reference_jsonl``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.eval.panel import load_panel, team_content_hash
from showdown_bot.eval.run_manifest import load_showdown_commit, server_patch_hash
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule

# The hero team is fixed repo-wide (every dev/held-out schedule pairs it against panel
# opponents) -- there is no per-manifest field for it, matching how every committed schedule
# hardcodes ``teams/fixed_team.txt`` as THE hero team (see e.g. panel_schedule.py rows).
_HERO_TEAM_PATH = "teams/fixed_team.txt"

_REQUIRED_FIELDS = frozenset({
    "baseline_id", "config_id", "config_hash", "git_sha", "panel_version", "panel_hash",
    "dev_schedule_hash", "dev_schedule_path", "hero_team_hash", "opp_team_hashes",
    "showdown_commit", "server_patch_hash", "seed_base", "pythonhashseed",
    "reference_jsonl", "reference_sha256",
})
# Present together or absent together (validated by `load_baseline`).
_HELDOUT_FIELDS = (
    "heldout_schedule_hash", "heldout_schedule_path",
    "heldout_reference_jsonl", "heldout_reference_sha256", "heldout_seed_base",
)


class BaselineError(ValueError):
    """The baseline manifest is malformed, or a ``verify_baseline`` check found drift."""


class BaselineDriftError(BaselineError):
    """>=1 ``verify_baseline`` check failed against the current working tree: refuse."""


class WinnerSequenceError(BaselineError):
    """``verify_winner_sequence`` found a length, winner, or seed mismatch."""


@dataclass(frozen=True)
class BaselineCheck:
    name: str
    ok: bool
    measured: object


def load_baseline(path) -> dict:
    """Load + schema-validate a baseline manifest JSON file. Raises ``BaselineError``."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise BaselineError("baseline manifest must be a JSON object")
    missing = _REQUIRED_FIELDS - set(data)
    if missing:
        raise BaselineError(f"baseline manifest missing required field(s): {sorted(missing)}")
    if not isinstance(data["opp_team_hashes"], dict):
        raise BaselineError("baseline manifest field 'opp_team_hashes' must be an object")
    # Optional field (Task 6 grounding P1): absent or explicit null means "unchanged Reg-I
    # default" (_HERO_TEAM_PATH) -- matching how the _HELDOUT_FIELDS group already treats a
    # null value as "not present" below. If PRESENT with a real value, it must be a genuine,
    # non-empty, non-whitespace-only string; anything else would silently make verify_baseline
    # hash an empty or garbage path.
    hero_team_path = data.get("hero_team_path")
    if hero_team_path is not None and (
        not isinstance(hero_team_path, str) or not hero_team_path.strip()
    ):
        raise BaselineError(
            f"baseline manifest field 'hero_team_path' must be a non-empty string, "
            f"got {hero_team_path!r}"
        )
    present = [f for f in _HELDOUT_FIELDS if data.get(f) is not None]
    if present and len(present) != len(_HELDOUT_FIELDS):
        absent = [f for f in _HELDOUT_FIELDS if f not in present]
        raise BaselineError(
            "held-out fields must all be present or all be absent, got "
            f"present={present} absent={absent}"
        )
    return data


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _panel_path(repo_root: Path, panel_version: str) -> Path:
    return repo_root / "config" / "eval" / "panels" / f"panel_{panel_version}.yaml"


def _add_check(checks: list[BaselineCheck], name: str, compute) -> None:
    """Run ``compute() -> (measured, ok)``; append the resulting ``BaselineCheck``.

    Fail-closed: any exception raised inside ``compute`` is captured as a failed check
    (never propagates mid-verification -- every check always runs to completion).
    """
    try:
        measured, ok = compute()
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: fail-closed per check
        checks.append(BaselineCheck(name=name, ok=False, measured=f"{type(exc).__name__}: {exc}"))
        return
    checks.append(BaselineCheck(name=name, ok=ok, measured=measured))


def verify_baseline(baseline: dict, *, repo_root, teams_root=None) -> list[BaselineCheck]:
    """Re-derive every hash in ``baseline`` against the CURRENT working tree.

    Returns the list of ``BaselineCheck`` results iff every check passed. Raises
    ``BaselineDriftError`` naming every failed check otherwise ("baseline drift -> refuse").
    ``teams_root`` defaults to ``repo_root/showdown_bot`` (where panel/schedule team_paths
    are resolved elsewhere in this codebase).
    """
    repo_root = Path(repo_root)
    teams_root = Path(teams_root) if teams_root is not None else repo_root / "showdown_bot"
    checks: list[BaselineCheck] = []

    def _panel():
        return load_panel(
            str(_panel_path(repo_root, baseline["panel_version"])), teams_root=str(teams_root)
        )

    def _panel_check():
        p = _panel()
        return p.panel_hash, p.panel_hash == baseline["panel_hash"]

    _add_check(checks, "panel_hash", _panel_check)

    def _hero_check():
        # Task 6 grounding P1: an explicit hero_team_path (already validated non-empty by
        # load_baseline, if present) overrides the Reg-I default -- Gate B's hero
        # ("teams/fixed_champions_v0.txt") is a genuinely different team from
        # _HERO_TEAM_PATH ("teams/fixed_team.txt"). `or` correctly falls back to the default
        # for both "key absent" and "key present with an explicit null" (load_baseline treats
        # both as "not present", matching the existing _HELDOUT_FIELDS convention).
        hero_team_path = baseline.get("hero_team_path") or _HERO_TEAM_PATH
        h = team_content_hash(str(teams_root), hero_team_path)
        return h, h == baseline["hero_team_hash"]

    _add_check(checks, "hero_team_hash", _hero_check)

    def _opp_check():
        p = _panel()
        by_id = {t.team_id: t.team_hash for t in (*p.dev_teams, *p.heldout_teams)}
        expected = baseline["opp_team_hashes"]
        measured = {tid: by_id.get(tid) for tid in expected}
        ok = all(tid in by_id and by_id[tid] == h for tid, h in expected.items())
        return measured, ok

    _add_check(checks, "opp_team_hashes", _opp_check)

    def _dev_schedule_check():
        sched = load_schedule(str(repo_root / baseline["dev_schedule_path"]))
        return sched.schedule_hash, sched.schedule_hash == baseline["dev_schedule_hash"]

    _add_check(checks, "dev_schedule_hash", _dev_schedule_check)

    if baseline.get("heldout_schedule_path") is not None:
        def _heldout_schedule_check():
            sched = load_schedule(str(repo_root / baseline["heldout_schedule_path"]))
            return sched.schedule_hash, sched.schedule_hash == baseline["heldout_schedule_hash"]

        _add_check(checks, "heldout_schedule_hash", _heldout_schedule_check)

    def _commit_check():
        commit = load_showdown_commit(str(repo_root / "config" / "eval" / "provenance.yaml"))
        return commit, commit == baseline["showdown_commit"]

    _add_check(checks, "showdown_commit", _commit_check)

    def _patch_check():
        h = server_patch_hash(
            str(repo_root / "tools" / "eval" / "patches" / "pokemon-showdown-seeded-battle.patch")
        )
        return h, h == baseline["server_patch_hash"]

    _add_check(checks, "server_patch_hash", _patch_check)

    def _reference_check():
        h = _sha256_file(repo_root / baseline["reference_jsonl"])
        return h, h == baseline["reference_sha256"]

    _add_check(checks, "reference_sha256", _reference_check)

    if baseline.get("heldout_reference_jsonl") is not None:
        def _heldout_reference_check():
            h = _sha256_file(repo_root / baseline["heldout_reference_jsonl"])
            return h, h == baseline["heldout_reference_sha256"]

        _add_check(checks, "heldout_reference_sha256", _heldout_reference_check)

    failed = [c.name for c in checks if not c.ok]
    if failed:
        raise BaselineDriftError(f"baseline drift -> refuse: failed check(s): {failed}")
    return checks


def verify_winner_sequence(reference_rows, fresh_rows) -> None:
    """Compare a reference run's winner+seed sequence against a fresh reproduction run.

    Raises ``WinnerSequenceError`` on a length mismatch, or naming the first index where
    ``winner`` or ``seed`` differ. Returns ``None`` on a full match.
    """
    if len(reference_rows) != len(fresh_rows):
        raise WinnerSequenceError(
            f"winner-sequence length mismatch: reference has {len(reference_rows)} row(s), "
            f"fresh has {len(fresh_rows)} row(s)"
        )
    for i, (ref, fresh) in enumerate(zip(reference_rows, fresh_rows)):
        if ref.get("winner") != fresh.get("winner") or ref.get("seed") != fresh.get("seed"):
            raise WinnerSequenceError(
                f"winner-sequence mismatch at index {i}: reference winner="
                f"{ref.get('winner')!r} seed={ref.get('seed')!r} vs fresh winner="
                f"{fresh.get('winner')!r} seed={fresh.get('seed')!r}"
            )


# =================================================================================================
# Gate B (Independent Strength Holdout) — STATIC baseline contract (spec Amendment A1.3, APPROVED)
#
# Additive. The generic T6 contract above (`_REQUIRED_FIELDS`, `load_baseline`, `verify_baseline`)
# is deliberately untouched: it freezes a heuristic policy's *reference run* and therefore needs
# `reference_jsonl`/`reference_sha256` plus a loadable YAML `dev_schedule_path`. Gate B can satisfy
# neither, and neither should be faked:
#
#   * a reference result file cannot predate the run it describes, and committing one afterwards
#     would change the candidate SHA the gate is bound to;
#   * Gate B's schedule is generated from code (`build_strength_holdout_schedule`), so there is no
#     YAML for `load_schedule` to read.
#
# What IS freezable before the run is Baseline B itself -- the `max_damage` configuration and the
# static environment it will run in. That is what this contract binds, and every field is
# re-derived from the current checkout at verification time.
# =================================================================================================

SH_BASELINE_SCHEMA_VERSION = 1
SH_BASELINE_ID = "champions-strength-holdout-v0"
SH_BASELINE_HERO_AGENT = "max_damage"
SH_BASELINE_FORMAT_ID = "gen9championsvgc2026regma"
SH_BASELINE_SEED_BASE = "champions-strength-holdout-v0"
SH_BASELINE_PANEL_VERSION = "champions_strength_holdout_v0"
SH_OPPONENT_TEAM_COUNT = 6

# Closed schema: exactly these keys, no more, no less.
_SH_REQUIRED_FIELDS = (
    "schema_version", "baseline_id", "hero_agent", "format_id", "panel_version", "panel_hash",
    "hero_team_path", "hero_team_hash", "opponent_teams", "schedule_hash", "seed_base",
    "showdown_commit", "server_patch_hash", "pythonhashseed",
)
_SH_TEAM_FIELDS = ("team_id", "team_path", "team_content_hash")
# Non-empty strings; `schema_version` is an int and `opponent_teams` a list, handled separately.
_SH_STRING_FIELDS = tuple(f for f in _SH_REQUIRED_FIELDS
                          if f not in ("schema_version", "opponent_teams"))


def _sh_require_text(data: dict, field: str) -> None:
    value = data[field]
    if not isinstance(value, str):
        raise BaselineError(
            f"strength-holdout baseline field {field!r} must be a string, got "
            f"{type(value).__name__}"
        )
    if not value.strip():
        raise BaselineError(f"strength-holdout baseline field {field!r} must not be blank")


def load_strength_holdout_baseline(path) -> dict:
    """Load + schema-validate the Gate B static baseline manifest (Amendment A1.3).

    Closed schema, fail-closed. Raises ``BaselineError`` on anything unexpected, including any
    field belonging to the generic *result* contract -- a manifest carrying `reference_jsonl`,
    `reference_sha256` or `dev_schedule_path` is rejected outright rather than silently ignored,
    so a generic manifest can never be loaded here by mistake (or vice versa).
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise BaselineError("strength-holdout baseline manifest must be a JSON object")

    missing = [f for f in _SH_REQUIRED_FIELDS if f not in data]
    if missing:
        raise BaselineError(
            f"strength-holdout baseline manifest missing required field(s): {sorted(missing)}"
        )
    unknown = sorted(set(data) - set(_SH_REQUIRED_FIELDS))
    if unknown:
        raise BaselineError(
            f"strength-holdout baseline manifest has unknown field(s): {unknown} -- this schema is "
            "closed and carries STATIC pre-run data only (Amendment A1.3); result artifacts, "
            "caller-supplied git SHAs and candidate identities do not belong in it"
        )

    if not isinstance(data["schema_version"], int) or isinstance(data["schema_version"], bool):
        raise BaselineError(
            f"strength-holdout baseline field 'schema_version' must be an int, got "
            f"{type(data['schema_version']).__name__}"
        )
    if data["schema_version"] != SH_BASELINE_SCHEMA_VERSION:
        raise BaselineError(
            f"strength-holdout baseline 'schema_version' must be {SH_BASELINE_SCHEMA_VERSION}, "
            f"got {data['schema_version']!r}"
        )
    for field in _SH_STRING_FIELDS:
        _sh_require_text(data, field)

    if data["baseline_id"] != SH_BASELINE_ID:
        raise BaselineError(
            f"strength-holdout baseline 'baseline_id' must be {SH_BASELINE_ID!r}, got "
            f"{data['baseline_id']!r}"
        )
    if data["hero_agent"] != SH_BASELINE_HERO_AGENT:
        raise BaselineError(
            f"strength-holdout baseline 'hero_agent' must be {SH_BASELINE_HERO_AGENT!r} -- this "
            f"manifest defines Baseline B, not the candidate -- got {data['hero_agent']!r}"
        )
    if data["format_id"] != SH_BASELINE_FORMAT_ID:
        raise BaselineError(
            f"strength-holdout baseline 'format_id' must be {SH_BASELINE_FORMAT_ID!r}, got "
            f"{data['format_id']!r}"
        )
    if data["seed_base"] != SH_BASELINE_SEED_BASE:
        raise BaselineError(
            f"strength-holdout baseline 'seed_base' must be the pinned namespace "
            f"{SH_BASELINE_SEED_BASE!r}, got {data['seed_base']!r}"
        )
    if data["panel_version"] != SH_BASELINE_PANEL_VERSION:
        raise BaselineError(
            f"strength-holdout baseline 'panel_version' must be {SH_BASELINE_PANEL_VERSION!r}, "
            f"got {data['panel_version']!r}"
        )

    teams = data["opponent_teams"]
    if not isinstance(teams, list):
        raise BaselineError(
            f"strength-holdout baseline field 'opponent_teams' must be a list, got "
            f"{type(teams).__name__}"
        )
    if len(teams) != SH_OPPONENT_TEAM_COUNT:
        raise BaselineError(
            f"strength-holdout baseline must register exactly six (6) opponent teams, got "
            f"{len(teams)}"
        )
    for i, entry in enumerate(teams):
        if not isinstance(entry, dict):
            raise BaselineError(
                f"strength-holdout baseline opponent_teams[{i}] must be an object, got "
                f"{type(entry).__name__}"
            )
        entry_missing = [f for f in _SH_TEAM_FIELDS if f not in entry]
        if entry_missing:
            raise BaselineError(
                f"strength-holdout baseline opponent_teams[{i}] missing field(s): "
                f"{sorted(entry_missing)}"
            )
        entry_unknown = sorted(set(entry) - set(_SH_TEAM_FIELDS))
        if entry_unknown:
            raise BaselineError(
                f"strength-holdout baseline opponent_teams[{i}] has unknown field(s): "
                f"{entry_unknown} -- the public-to-internal id mapping lives in the holdout "
                "manifest, not here (Amendment A1.1)"
            )
        for field in _SH_TEAM_FIELDS:
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise BaselineError(
                    f"strength-holdout baseline opponent_teams[{i}][{field!r}] must be a "
                    f"non-empty string, got {entry[field]!r}"
                )
    for field in ("team_id", "team_path"):
        seen = [t[field] for t in teams]
        if len(set(seen)) != len(seen):
            dupes = sorted({v for v in seen if seen.count(v) > 1})
            raise BaselineError(
                f"strength-holdout baseline has duplicate opponent {field}(s): {dupes}"
            )
    return data


def verify_strength_holdout_baseline(baseline: dict, *, repo_root, teams_root=None) -> list[BaselineCheck]:
    """Re-derive every static pin in ``baseline`` from the CURRENT checkout.

    Same contract as ``verify_baseline``: every check runs to completion, and the failures are
    reported together via ``BaselineDriftError``. What differs is WHAT is pinned -- panel, hero and
    opponent team content, the canonically REBUILT schedule, and the server/seed pins, with no
    result artifact anywhere.
    """
    repo_root = Path(repo_root)
    teams_root = Path(teams_root) if teams_root is not None else repo_root / "showdown_bot"
    checks: list[BaselineCheck] = []

    def _panel():
        return load_panel(
            str(_panel_path(repo_root, baseline["panel_version"])), teams_root=str(teams_root)
        )

    _add_check(checks, "panel_hash",
               lambda: (_panel().panel_hash, _panel().panel_hash == baseline["panel_hash"]))

    def _hero_check():
        measured = team_content_hash(str(teams_root), baseline["hero_team_path"])
        return measured, measured == baseline["hero_team_hash"]

    _add_check(checks, "hero_team_hash", _hero_check)

    def _opponents_check():
        panel = _panel()
        by_id = {t.team_id: t for t in (*panel.dev_teams, *panel.heldout_teams)}
        measured = {}
        ok = True
        for entry in baseline["opponent_teams"]:
            team_id = entry["team_id"]
            panel_team = by_id.get(team_id)
            fresh = team_content_hash(str(teams_root), entry["team_path"])
            measured[team_id] = fresh
            if panel_team is None or panel_team.team_path != entry["team_path"]:
                ok = False
                continue
            if fresh != entry["team_content_hash"] or panel_team.team_hash != fresh:
                ok = False
        # the panel must not carry teams the baseline does not register, either
        if set(by_id) != {e["team_id"] for e in baseline["opponent_teams"]}:
            ok = False
        return measured, ok

    _add_check(checks, "opponent_team_hashes", _opponents_check)

    def _schedule_check():
        panel = _panel()
        team_ids = sorted(t.team_id for t in (*panel.dev_teams, *panel.heldout_teams))
        rebuilt = build_strength_holdout_schedule(
            holdout_team_ids=team_ids, panel_hash=panel.panel_hash, seed_base=baseline["seed_base"],
        )
        return rebuilt.schedule_hash, rebuilt.schedule_hash == baseline["schedule_hash"]

    _add_check(checks, "schedule_hash", _schedule_check)

    _add_check(checks, "seed_base",
               lambda: (SH_BASELINE_SEED_BASE, baseline["seed_base"] == SH_BASELINE_SEED_BASE))
    _add_check(checks, "format_id",
               lambda: (SH_BASELINE_FORMAT_ID, baseline["format_id"] == SH_BASELINE_FORMAT_ID))
    _add_check(checks, "hero_agent",
               lambda: (SH_BASELINE_HERO_AGENT, baseline["hero_agent"] == SH_BASELINE_HERO_AGENT))

    def _commit_check():
        commit = load_showdown_commit(str(repo_root / "config" / "eval" / "provenance.yaml"))
        return commit, commit == baseline["showdown_commit"]

    _add_check(checks, "showdown_commit", _commit_check)

    def _patch_check():
        h = server_patch_hash(
            str(repo_root / "tools" / "eval" / "patches" / "pokemon-showdown-seeded-battle.patch")
        )
        return h, h == baseline["server_patch_hash"]

    _add_check(checks, "server_patch_hash", _patch_check)

    failed = [c.name for c in checks if not c.ok]
    if failed:
        raise BaselineDriftError(
            f"strength-holdout baseline drift -> refuse: failed check(s): {failed}"
        )
    return checks

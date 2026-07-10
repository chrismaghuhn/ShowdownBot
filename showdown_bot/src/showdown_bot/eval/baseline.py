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
        h = team_content_hash(str(teams_root), _HERO_TEAM_PATH)
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

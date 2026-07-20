"""Task 6: the opponent-Mega coverage runner + derived provenance (offline).

Mirrors ``i8d_runner.run_i8d_live_gate`` structurally, but: provenance is DERIVED internally (never
caller-supplied), the panel + out-dir are locked, live output never lands under ``data/eval/``, and
safety is per-seat AND foe-Mega-bound via the hero seat's ``hero_invalid_decision_indices``
(GauntletStats) joined to each decision's ``foe_mega_active``. Three fail-closed guards protect the
verdict end-to-end (Guard 1 lives at the gauntlet seam; Guards 2/3 here). Unit-tested with an
injected ``run_local_gauntlet`` -- no server, no battle.
"""
from __future__ import annotations

import asyncio
import json
import os

from showdown_bot.eval.coverage import coverage_cell_counts
from showdown_bot.eval.coverage_schedule import (
    _REPO_ROOT,
    COVERAGE_FORMAT,
    COVERAGE_MANIFEST_PATH,
    COVERAGE_MAX_BATTLES,
    COVERAGE_PANEL_PATH,
    COVERAGE_SEED_BASE,
    CoverageScheduleError,
    build_coverage_schedule,
    load_coverage_manifest,
    verify_coverage_panel_and_teams,
    verify_coverage_schedule,
)
from showdown_bot.eval.coverage_verdict import (
    COVERAGE_MAX_SCORED_DECISIONS,
    coverage_should_stop,
    coverage_verdict,
)
from showdown_bot.eval.decision_profile import (
    DecisionProfileWriter,
    LiveProfileContext,
    _read_rows,
    validate_live_profile_dataset,
)
from showdown_bot.eval.i8d_runner import _adopt_battle_atomic, _write_json_atomic


class CoverageRunError(ValueError):
    """The coverage gate cannot run or must abort fail-closed: a bad schedule/panel, dirty or
    caller-supplied provenance, an out_dir under data/eval/, a partial battle (Guard 2), or an
    unjoinable hero-invalid decision index (Guard 3)."""


def resolve_coverage_provenance(*, hero_agent: str = "heuristic", format_id: str = COVERAGE_FORMAT) -> dict:
    """Derive the gate's provenance from the REAL repo/env, fail-closed: none of git_sha /
    config_hash / calc_backend is caller-supplied, a dirty tree is refused, and the candidate
    identity is a canonical, unambiguous sha1 of {hero_agent, git_sha, config_hash}[:16] (a
    delimited JSON object, never bare string concatenation, so ('a','bc') and ('ab','c') can't
    collide)."""
    from showdown_bot.eval.config_env import behavior_env, effective_config_manifest
    from showdown_bot.eval.result_jsonl import make_config_hash
    from showdown_bot.learning.provenance import git_sha_and_dirty, make_candidate_identity

    git_sha, dirty = git_sha_and_dirty()
    if not git_sha or git_sha == "unknown":
        raise CoverageRunError(
            "cannot resolve a git sha for the coverage gate (not a git checkout?); the verdict's "
            "provenance would be unverifiable"
        )
    if dirty:
        raise CoverageRunError(
            "the working tree is dirty; commit or stash before a coverage gate run so the verdict's "
            "git_sha identifies exactly the code that produced it"
        )
    manifest = effective_config_manifest(
        agent=hero_agent, format_id=format_id, env=behavior_env(),
        model_hash=None, model_manifest_hash=None,
    )
    config_hash = make_config_hash(manifest)
    raw_backend = os.environ.get("SHOWDOWN_CALC_BACKEND", "oneshot")
    if raw_backend in ("", "oneshot"):
        calc_backend = "oneshot"
    elif raw_backend == "persistent":
        calc_backend = "persistent"
    else:
        raise CoverageRunError(
            f"unknown SHOWDOWN_CALC_BACKEND={raw_backend!r} (expected 'oneshot' or 'persistent')"
        )
    candidate_identity = make_candidate_identity(
        hero_agent=hero_agent, git_sha=git_sha, config_hash=config_hash)
    return {"git_sha": git_sha, "config_hash": config_hash, "calc_backend": calc_backend,
            "hero_agent": hero_agent, "candidate_identity": candidate_identity}


def build_coverage_live_schedule(panel_path: str = COVERAGE_PANEL_PATH,
                                 manifest_path: str = COVERAGE_MANIFEST_PATH, *,
                                 n_battles: int = COVERAGE_MAX_BATTLES, teams_root: str = "."):
    """Bind the fixed coverage schedule (all matchups materialised, frozen in ``schedule_hash``)
    BEFORE the first battle. Thin wrapper over ``load_panel`` + ``load_coverage_manifest`` +
    ``build_coverage_schedule`` -- the CLI locks ``panel_path``/``manifest_path`` to the coverage
    ones, never a caller path."""
    from showdown_bot.eval.panel import load_panel
    panel = load_panel(panel_path, teams_root=teams_root)
    manifest = load_coverage_manifest(manifest_path)
    return build_coverage_schedule(panel, manifest, n_battles=n_battles, teams_root=teams_root)


_CANONICAL_DATA_EVAL = os.path.normcase(os.path.realpath(str(_REPO_ROOT / "data" / "eval")))


def _is_under_data_eval(path: str) -> bool:
    """True iff ``path`` resolves -- following symlinks/junctions, then compared
    platform-appropriately for case -- to THIS repo's own protected data/eval tree, or a
    descendant of it.

    Never a pure string/segment match: that both under- and over-blocks. Under-blocks because a
    junction/symlink under a differently-named path that points AT data/eval would never contain
    the literal substring "data/eval", yet the write would still land there. Over-blocks because
    ANY unrelated directory elsewhere that merely happens to have a "data" segment immediately
    followed by an "eval" segment (a different project's own data/eval, reached via a completely
    different root) would be flagged too, even though this guard only protects THIS repo's tree.
    ``os.path.realpath`` resolves symlinks/junctions and does not require the path to exist;
    ``os.path.normcase`` is a case-insensitive comparison on Windows (this repo's platform, where
    NTFS is case-insensitive) and a no-op on case-sensitive filesystems.
    """
    resolved = os.path.normcase(os.path.realpath(path))
    return resolved == _CANONICAL_DATA_EVAL or resolved.startswith(_CANONICAL_DATA_EVAL + os.sep)


def _verify_seed_alignment(seed_log_path: str, seed_base: str, schedule, battles_played: int) -> None:
    from showdown_bot.eval.seeding import SeedLogError, verify_seed_log
    try:
        records = verify_seed_log(seed_log_path, seed_base, battles_played)
    except SeedLogError as exc:
        raise CoverageRunError(f"seed-log verification failed: {exc}") from exc
    for row, rec in zip(schedule.rows, records):
        if row.seed_index != rec["battle_index"]:
            raise CoverageRunError(
                f"seed-log/schedule misalignment: row seed_index {row.seed_index} != logged "
                f"battle_index {rec['battle_index']}"
            )


def run_coverage_gate(*, schedule, out_dir: str, seed_log_path: str,
                      hero_agent: str = "heuristic", expected_battles: int = COVERAGE_MAX_BATTLES,
                      teams_root: str = ".") -> dict:
    """Drive the coverage schedule with whole-battle stop and render the three-way verdict, deriving
    provenance internally and verifying every execution boundary. A technical abort (Guard 2 partial
    battle, Guard 3 unjoinable index, seed-log failure) leaves the un-published staging dir, never an
    out_dir and never a verdict."""
    from showdown_bot.client.gauntlet import run_local_gauntlet
    from showdown_bot.eval.result_jsonl import make_battle_id
    from showdown_bot.eval.seeding import derive_battle_seed
    from showdown_bot.team.pack import load_packed_team

    verify_coverage_schedule(schedule, expected_battles=expected_battles)
    # panel_hash covers team CONTENT; schedule_hash covers matchup ORDER/assignment. Neither is
    # checked against a caller-suppliable "expected" value (a forged panel_hash paired with a
    # matching caller-supplied expected_panel_hash argument used to sail through unnoticed, since
    # the rows were otherwise legitimate and schedule_hash alone doesn't cover panel_hash). Both
    # fields are checked against a schedule freshly rebuilt from the LOCKED panel/manifest instead
    # -- never trust a caller-supplied Schedule's fields, self-consistent or not, on their own.
    canonical = build_coverage_live_schedule(n_battles=expected_battles, teams_root=teams_root)
    if canonical.panel_hash != schedule.panel_hash:
        raise CoverageRunError(
            f"schedule panel_hash {schedule.panel_hash!r} != the canonical panel_hash freshly "
            f"derived from the locked panel ({canonical.panel_hash!r}): the panel/team contents "
            f"are not the approved ones"
        )
    if canonical.schedule_hash != schedule.schedule_hash:
        raise CoverageRunError(
            f"schedule_hash {schedule.schedule_hash!r} != the canonical schedule freshly rebuilt "
            f"from the locked panel/manifest ({canonical.schedule_hash!r}): the caller's schedule "
            f"composition (matchup order/assignment) does not match the approved one"
        )
    if _is_under_data_eval(out_dir):
        raise CoverageRunError(
            f"out_dir {out_dir!r} is under data/eval/; the runner writes only to a scratch/run tree. "
            f"Freezing a run's output into data/eval/ is a separate, separately-authorized commit."
        )

    prov = resolve_coverage_provenance(hero_agent=hero_agent)   # DERIVED, never caller-supplied
    git_sha, config_hash = prov["git_sha"], prov["config_hash"]
    calc_backend = prov["calc_backend"]
    candidate_identity = prov["candidate_identity"]

    seed_base = os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "")
    if seed_base != COVERAGE_SEED_BASE:
        raise CoverageRunError(
            f"SHOWDOWN_BATTLE_SEED_BASE must be {COVERAGE_SEED_BASE!r} for coverage (Channel A), got "
            f"{seed_base!r}: the server must be started with the approved seed namespace"
        )
    if not seed_log_path:
        raise CoverageRunError(
            "coverage requires the server's seed log (SHOWDOWN_EVAL_SEED_LOG) so played seeds can be proven"
        )

    # TOCTOU guard immediately before battle 1: re-hash every team file this schedule references
    # FROM DISK, right now -- inside the runner itself, not only from a CLI wrapper a caller might
    # skip. hero_team_hash/opp_team_hash are excluded from schedule_hash (eval/schedule.py), so the
    # canonical-schedule check above cannot catch a team file that changed since the schedule was
    # built; only this can.
    try:
        verify_coverage_panel_and_teams(schedule, teams_root=teams_root)
    except CoverageScheduleError as exc:
        raise CoverageRunError(str(exc)) from exc

    staging_dir = f"{out_dir}.staging"
    for label, p in (("output", out_dir), ("staging", staging_dir)):
        if os.path.exists(p):
            raise CoverageRunError(
                f"{label} directory {p} already exists; a coverage restart runs from seed 0 into a "
                f"fresh directory and never merges a partial run"
            )
    os.makedirs(staging_dir)
    staging_profile = os.path.join(staging_dir, "profile.jsonl")
    staging_battle = os.path.join(staging_dir, "battle.jsonl")
    open(staging_profile, "a", encoding="utf-8", newline="").close()

    battles_played = 0
    scored_decisions = 0
    safety_violations = 0
    cell_counts: dict = {}
    stop_reason: str | None = None
    for row in schedule.rows:
        seed = derive_battle_seed(seed_base, row.seed_index)
        battle_id = make_battle_id(schedule.schedule_hash, row.seed_index, seed)
        context = LiveProfileContext(
            battle_id=battle_id, config_id=hero_agent, config_hash=config_hash,
            schedule_hash=schedule.schedule_hash, format_id=row.format_id,
            git_sha=git_sha, calc_backend=calc_backend)
        hero_team_abs = os.path.abspath(os.path.join(teams_root, row.hero_team_path))
        opp_team_abs = os.path.abspath(os.path.join(teams_root, row.opp_team_path))
        for label, rel, abs_path in (("hero", row.hero_team_path, hero_team_abs),
                                     ("opponent", row.opp_team_path, opp_team_abs)):
            try:
                packed = load_packed_team(abs_path)
            except FileNotFoundError as exc:
                raise CoverageRunError(
                    f"{label} team {rel!r} not found under teams_root {teams_root!r} (resolved to "
                    f"{abs_path!r}); refusing to challenge with an empty team"
                ) from exc
            if not packed:
                raise CoverageRunError(f"{label} team {rel!r} resolves to an EMPTY packed team at {abs_path!r}")

        if os.path.exists(staging_battle):
            os.remove(staging_battle)
        stage_writer = DecisionProfileWriter(staging_battle, manifest=None)
        stats = asyncio.run(run_local_gauntlet(
            games=1, hero_agent=hero_agent, villain_agent=row.opp_policy,
            format_id=row.format_id, team_path=hero_team_abs, opp_team_path=opp_team_abs,
            decision_profile_writer=stage_writer, decision_profile_context=context))

        # Guard 2 (whole-battle only): a battle that did not complete exactly one game is discarded
        # (its rows AND its hero_invalid_decision_indices), and the run fails closed (restart seed 0).
        if stats.games != 1:
            if os.path.exists(staging_battle):
                os.remove(staging_battle)
            raise CoverageRunError(
                f"battle at seed_index {row.seed_index} did not complete exactly one game "
                f"(games={stats.games}); its partial rows are discarded -- restart from seed 0"
            )

        # Safety join (per-seat, foe-Mega-bound) + Guard 3 (complete join): each hero-invalid index
        # must resolve to a PRESENT (battle_id, decision_index) row; a present row is judged by its
        # foe_mega_active (True -> violation, False -> out of scope); a MISSING row or the -1 sentinel
        # ABORTS fail-closed (no out_dir, no verdict).
        battle_rows = _read_rows(staging_battle) if os.path.exists(staging_battle) else []
        foe_mega_by_index = {r["decision_index"]: r["foe_mega_active"]
                             for r in battle_rows if r["battle_id"] == battle_id}
        for idx in stats.hero_invalid_decision_indices:
            if idx not in foe_mega_by_index:
                raise CoverageRunError(
                    f"hero invalid choice at decision_index {idx} (battle {battle_id!r}) has no present "
                    f"decision row (or is the -1 sentinel); aborting fail-closed -- an unresolved "
                    f"safety join must never become a PASS"
                )
            if foe_mega_by_index[idx] is True:
                safety_violations += 1
            # foe_mega_active False -> a non-foe-Mega illegal choice, out of this gate's scope: ignored.

        if os.path.exists(staging_battle):
            validate_live_profile_dataset(staging_battle)
            _adopt_battle_atomic(staging_profile, staging_battle)
            os.remove(staging_battle)
        battles_played += 1
        scored_decisions = validate_live_profile_dataset(staging_profile)["rows"]
        cell_counts = coverage_cell_counts(staging_profile)
        stop, stop_reason = coverage_should_stop(
            battles_played=battles_played, scored_decisions=scored_decisions,
            cell_counts=cell_counts, safety_violations=safety_violations)
        if stop:
            break

    # battles_played reaching the schedule's own row count IS "schedule exhausted" -- regardless of
    # which stop_reason fired. In production COVERAGE_MAX_BATTLES always equals len(schedule.rows)
    # (the CLI locks expected_battles=COVERAGE_MAX_BATTLES), so the max_battles cap can only ever
    # fire on the LAST row: relying on the for/else's `else` clause instead (which Python skips
    # whenever the loop `break`s, even on its final iteration) misreported a fully-exhausted
    # schedule with an unmet floor as INCONCLUSIVE/max_battles rather than FAIL/schedule_exhausted.
    schedule_complete = battles_played >= len(schedule.rows)

    _verify_seed_alignment(seed_log_path, seed_base, schedule, battles_played)
    validate_live_profile_dataset(staging_profile)   # final dataset validation before publishing

    verdict = coverage_verdict(
        cell_counts=cell_counts, safety_violations=safety_violations,
        schedule_complete=schedule_complete, stop_reason=stop_reason or "schedule_exhausted")
    report = {
        "schedule_hash": schedule.schedule_hash,
        "panel_hash": schedule.panel_hash,
        "candidate_identity": candidate_identity,
        "git_sha": git_sha,
        "config_hash": config_hash,
        "calc_backend": calc_backend,
        "hero_agent": hero_agent,
        "hero_team_hash": schedule.rows[0].hero_team_hash if schedule.rows else None,
        "opp_team_hashes": sorted({r.opp_team_hash for r in schedule.rows if r.opp_team_hash is not None}),
        "seed_base": seed_base,
        "seed_log_verified": True,
        "battles_played": battles_played,
        "scored_decisions": scored_decisions,
        "max_scored_decisions": COVERAGE_MAX_SCORED_DECISIONS,
        **verdict,
    }
    _write_json_atomic(os.path.join(staging_dir, "verdict.json"), report)
    os.replace(staging_dir, out_dir)   # single atomic publish AFTER all validation
    return report

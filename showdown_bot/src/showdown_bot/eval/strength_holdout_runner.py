"""Gate B (Independent Strength Holdout) — single-arm battle execution.

Plays exactly ONE arm (hero_agent='heuristic' for Candidate A, 'max_damage' for Baseline B) of
the 180-battle-key schedule. The caller (see Task 11's CLI) is responsible for ensuring the
server this connects to was FRESHLY STARTED for this specific call, with the seed namespace
SHOWDOWN_BATTLE_SEED_BASE set to the schedule's own seed_base -- exactly like i8d_runner.py and
coverage_runner.py already require of their own callers. Two arms must never share one server
session (grounding report Rev.2 addendum, Finding 4): the server's seed counter is process-
lifetime global, so sharing a session gives the two arms disjoint real seeds despite matching
labels. combine_strength_holdout_arms (Task 10) is what actually pairs and verdicts the two
arms' already-published output.
"""
from __future__ import annotations

import asyncio
import os
import platform
import subprocess
from pathlib import Path

from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
from showdown_bot.eval.i8d_runner import _write_json_atomic
from showdown_bot.eval.result_jsonl import BattleResultWriter, make_battle_id, ResultRowError
from showdown_bot.eval.seeding import derive_battle_seed, verify_seed_log, SeedLogError
from showdown_bot.eval.strata_guard import detect_stratum, stratum_output_root
from showdown_bot.eval.strength_holdout_schedule import (
    STRENGTH_HOLDOUT_HERO_TEAM_PATH, STRENGTH_HOLDOUT_FORMAT_ID,
)
from showdown_bot.learning.provenance import make_candidate_identity
from showdown_bot.team.pack import load_packed_team

# Rev. 15 fix (§1n, Task-3-review P1 #2): matches holdout_leakage_scan.ALLOWED_DIRECTORY_PREFIXES'
# "data/eval/champions-panel-v0/strength-holdout-v0/" entry (Task 2) exactly, minus the trailing
# slash stratum_output_root's own f"{base_dir}/{stratum}" join adds back -- every arm this
# function publishes therefore lands somewhere the leakage guard's allowlist already covers,
# with no allowlist change needed.
STRENGTH_HOLDOUT_OUTPUT_BASE = "data/eval/champions-panel-v0/strength-holdout-v0"


class GateBAbort(Exception):
    """A technical abort -- dirty tree, hash mismatch, infra failure, or zero-battle timeout.
    NOT a verdict (ports Gate A's DESIGN sec 2.6 taxonomy, since Gate B has no equivalent
    dedicated section -- grounding report sec 2)."""


def _git_is_dirty() -> bool:
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError outside a git checkout;
    # a missing git executable raises FileNotFoundError regardless of check=. Both were unguarded
    # and would escape resolve_strength_holdout_provenance -> run_strength_holdout_arm as a raw
    # traceback, before a single battle is played -- not caught by the arm CLI, which only ever
    # catches GateBAbort. Defined in this module (unlike the leakage-scan git calls), so the fix
    # can fold directly into GateBAbort with no cross-module dependency.
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise GateBAbort(f"cannot determine git dirty-state: {exc}") from exc
    return bool(result.stdout.strip())


def _git_sha() -> str:
    # NF4 fix (Rev. 8): same as _git_is_dirty above.
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise GateBAbort(f"cannot determine git sha: {exc}") from exc
    return result.stdout.strip()


def _derive_config_hash(hero_agent: str) -> str:
    """RECONCILED, Rev. 10 (closes the Rev. 1/2 debt, per the user's explicit direction --
    §1i): calls the real `resolve_coverage_provenance`, and this is now PROVEN, not assumed,
    to produce the same config_hash I8-D's own `resolve_i8d_provenance` would derive for the
    same hero_agent -- verified by reading both functions in full (`coverage_runner.py:75-113`,
    `i8d_runner.py:157-202`). They are structurally identical: same `git_sha_and_dirty()` call,
    same dirty-tree refusal, the SAME `effective_config_manifest(agent=hero_agent,
    format_id=format_id, env=behavior_env(), model_hash=None, model_manifest_hash=None)` call
    with identical arguments, the same `make_config_hash(manifest)`, the same
    SHOWDOWN_CALC_BACKEND normalization. The only difference is which domain exception class
    each raises (`CoverageRunError` vs `I8DRunError`) -- irrelevant to the returned config_hash
    VALUE. `format_id` defaults to each function's own gate constant (`COVERAGE_FORMAT` /
    `I8D_FORMAT`); both equal `"gen9championsvgc2026regma"`, confirmed by reading
    `coverage_schedule.py:27` and `i8d_schedule.py:28` directly -- the same value
    `STRENGTH_HOLDOUT_FORMAT_ID` (Task 1) already uses. So for the same hero_agent, same commit,
    and same environment (guaranteed by DESIGN sec 8's gate ordering -- Gate B runs against the
    SAME candidate SHA I8-D and Coverage already passed), all three gates' config_hash values
    are provably identical by construction, not by naming convention.

    P3 fix (Rev. 10 continued): "provably identical" above was only ever proven for
    `COVERAGE_FORMAT == I8D_FORMAT` -- the call below never passed `format_id`, so it silently
    inherited `resolve_coverage_provenance`'s OWN default rather than binding to
    `STRENGTH_HOLDOUT_FORMAT_ID`, the format Gate B's own schedule actually plays under
    (`strength_holdout_schedule.py`, `build_strength_holdout_schedule`'s `format_id=
    STRENGTH_HOLDOUT_FORMAT_ID`). Today all three constants hold the same string, so this was
    inert -- but the failure direction if Gate B's format ever changed while I8-D/Coverage did
    not would have been silent, not loud: battles played under the new format, config_hash (and
    candidate_identity) computed for the old one, and `verify_i8d_verdict_artifact` would still
    PASS, because Gate B's identity would still match I8-D's -- a gate certifying it verified the
    same candidate I8-D did while having actually played a different format. `format_id` is now
    passed explicitly, binding this function's config_hash to the format Gate B actually plays,
    not to whatever `resolve_coverage_provenance` happens to default to.

    Exception surface, also now read rather than assumed (`config_env.py:254-320`):
    `CoverageRunError` (dirty tree / unresolvable git sha / bad SHOWDOWN_CALC_BACKEND);
    `ItemdataStaleError` (`engine/items.py`) and `SpeciesMetaStaleError` (`engine/species_meta.py`)
    -- both DELIBERATELY fail-closed per I7a sec 14, propagated unguarded through
    `effective_config_manifest` -> `config_provenance_for_format` by that slice's own design, not
    an oversight of this one; `PinnedCalcError` (`engine/calc/pin.py`) -- deliberately fail-closed
    per sec 5.4, same propagation shape. `load_format_config`'s own malformed-YAML/schema-error
    path is NOT further named here (its exact exception type was not independently confirmed --
    disclosed, not silently assumed); `FileNotFoundError` from a missing format yaml is already
    caught one level down, inside `config_provenance_for_format` itself, and does not reach here.

    These are caught SPECIFICALLY, not via a blanket `except Exception` -- unlike gauntlet_runner
    (NF5, Rev. 9), this callee IS auditable at reasonable cost, was actually audited, and a
    generic catch here would flatten a genuine cross-gate provenance defect (config derivation
    drifting between gates) into the same undifferentiated abort as a routine dirty-tree stop."""
    from showdown_bot.eval.coverage_runner import resolve_coverage_provenance, CoverageRunError
    from showdown_bot.engine.calc.pin import PinnedCalcError
    from showdown_bot.engine.items import ItemdataStaleError
    from showdown_bot.engine.species_meta import SpeciesMetaStaleError
    try:
        return resolve_coverage_provenance(
            hero_agent=hero_agent, format_id=STRENGTH_HOLDOUT_FORMAT_ID,
        )["config_hash"]
    except (CoverageRunError, ItemdataStaleError, SpeciesMetaStaleError, PinnedCalcError) as exc:
        raise GateBAbort(
            f"config provenance derivation failed for hero_agent={hero_agent!r}: {exc}"
        ) from exc


def resolve_strength_holdout_provenance(*, hero_agent: str = "heuristic") -> dict:
    """Derive this run's own git_sha/config_hash/candidate_identity fresh -- never caller-
    trusted. Refuses on a dirty tree (GateBAbort, not a verdict)."""
    if _git_is_dirty():
        raise GateBAbort("dirty tree: refusing to derive a candidate identity from uncommitted changes")
    git_sha = _git_sha()
    config_hash = _derive_config_hash(hero_agent)
    candidate_identity = make_candidate_identity(hero_agent=hero_agent, git_sha=git_sha, config_hash=config_hash)
    return {"hero_agent": hero_agent, "git_sha": git_sha, "config_hash": config_hash,
            "candidate_identity": candidate_identity}


def _assert_out_dir_contained(out_dir: str, expected_root: str, *, stratum: str) -> None:
    """Task 9 known-P1 fix: bind out_dir to expected_root via each path's REAL canonical
    absolute form, never a lexical/substring comparison.

    Both paths are resolved through ``Path.resolve()`` (``strict=False``, the default): any
    EXISTING prefix component is resolved through the real filesystem, following symlinks and
    Windows junctions to their true target, while a non-existent tail (out_dir itself must not
    exist yet -- checked separately by the caller) is appended as given, with no filesystem
    lookup required. Containment is then checked by COMPONENT, not by string prefix/substring --
    a foreign path that merely contains expected_root's text (e.g. a differently-named sibling,
    or a decoy directory that happens to nest the same path segments) fails this check even
    though it would have passed a bare substring test. Windows path components are folded to
    lowercase before comparing (NTFS is case-insensitive); every other platform compares
    case-sensitively.

    ``expected_root`` is typically a relative, repo-root path (``stratum_output_root``'s own
    return shape) -- it resolves against the current working directory, matching how every real
    caller of this function is expected to run (from the repo root, exactly like every other
    gate in this codebase resolves its own relative paths)."""
    out_resolved = Path(out_dir).resolve()
    root_resolved = Path(expected_root).resolve()
    out_parts = out_resolved.parts
    root_parts = root_resolved.parts
    if platform.system() == "Windows":
        out_parts = tuple(p.lower() for p in out_parts)
        root_parts = tuple(p.lower() for p in root_parts)
    if out_parts[: len(root_parts)] != root_parts:
        raise GateBAbort(
            f"out_dir={out_dir!r} resolves to {str(out_resolved)!r}, which is not contained "
            f"within the required stratum root {expected_root!r} (resolved: "
            f"{str(root_resolved)!r}) for stratum={stratum!r} -- DESIGN sec 3.5 requires each "
            "stratum to publish under its own separate output tree, never a shared, ambiguous, "
            "or escaped location"
        )


def run_strength_holdout_arm(
    *, hero_agent: str, schedule, out_dir: str, seed_log_path: str,
    holdout_team_content_hashes: dict[str, str], date_stratum_id: str, teams_root: str = ".",
    calc_backend: str = "oneshot", gauntlet_runner=None, stratum_env_override: str | None = None,
) -> dict:
    """Plays all len(schedule.battle_keys) battles for ONE arm, staged+atomically published.
    gauntlet_runner defaults to the real client.gauntlet.run_local_gauntlet; tests inject a fake
    so this whole function is testable without a live server.

    holdout_team_content_hashes maps holdout_team_id -> its REAL sealed team_content_hash
    (Task 12's seal_team output, .txt+.packed together) -- required, no default. A scheduled
    team missing from this mapping aborts before the first battle plays; the row's opp_team_hash
    field must never fall back to the bare team_id string (Rev. 3 P2 fix: that field name
    promises a hash to every downstream consumer -- the leakage scan, the disjointness check,
    cell grouping -- and a non-hash placeholder there would silently defeat all three).

    Rev. 15 fix (§1n, Task-3-review P1 #1): stratum/platform/date-stratum identity is established
    HERE, on the machine that actually plays this arm's battles -- never re-derived later by
    combine_strength_holdout_arms (Task 10, its own Rev. 15 fix), which reads what THIS function
    wrote into the manifest instead. date_stratum_id is a pre-registered identifier for this run
    (DESIGN sec 3.5: "a Kaggle strength stratum is a separate pre-registered run"), required with
    no default -- an auto-derived "today's date" would not be pre-registered, so the caller must
    supply it. stratum_env_override threads into detect_stratum's own explicit-override escape
    hatch (Task 3) -- required for any real Kaggle run, since detect_stratum() refuses to guess
    Kaggle from a bare non-Windows platform.system() read; also used by tests to pin the stratum
    deterministically regardless of the box actually running the suite."""
    if gauntlet_runner is None:
        from showdown_bot.client.gauntlet import run_local_gauntlet as gauntlet_runner

    provenance = resolve_strength_holdout_provenance(hero_agent=hero_agent)

    scheduled_team_ids = {key.holdout_team_id for key in schedule.battle_keys}
    missing_hashes = scheduled_team_ids - set(holdout_team_content_hashes)
    if missing_hashes:
        raise GateBAbort(
            f"holdout_team_content_hashes is missing a sealed hash for: {sorted(missing_hashes)} "
            "-- every scheduled team must be sealed (Task 12) before any arm can be played"
        )

    # Channel-A seed-namespace gate (mirrors i8d_runner.py:265-275 / coverage_runner.py:485-494
    # exactly) -- fail BEFORE spending a single battle on an unproven seed run.
    seed_base_env = os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "")
    if seed_base_env != schedule.seed_base:
        raise GateBAbort(
            f"SHOWDOWN_BATTLE_SEED_BASE must be {schedule.seed_base!r} for this arm (Channel A), "
            f"got {seed_base_env!r}: the server must be started with the approved seed namespace"
        )
    if not seed_log_path:
        raise GateBAbort(
            "seed_log_path (SHOWDOWN_EVAL_SEED_LOG) is required so the played seeds can be "
            "proven; without it the run's seeds are only labelled, not verified"
        )

    # Rev. 15 fix (§1n, Task-3-review P1 #1/#2): stratum/platform/out_dir identity, established
    # ONCE here and written into the manifest below -- never re-derived by the combiner.
    if not date_stratum_id:
        raise GateBAbort(
            "date_stratum_id is required and must be non-empty -- DESIGN sec 3.5 requires a "
            "pre-registered stratum/date identifier, fixed before the run, never derived after "
            "the fact"
        )
    stratum = detect_stratum(env_override=stratum_env_override)
    platform_attestation = platform.platform()
    expected_root = stratum_output_root(stratum, STRENGTH_HOLDOUT_OUTPUT_BASE)
    # Task 9 known P1 fix: canonical, symlink/junction-aware, component-based containment --
    # see _assert_out_dir_contained's own docstring for the full rationale. Replaces the Rev. 18
    # sketch's posixpath.normpath + slash-bounded substring check, which was purely lexical and
    # so could be defeated by a foreign path that merely CONTAINS the root's text, a pre-existing
    # symlink/junction escaping the root, or Windows' case-insensitive filesystem.
    _assert_out_dir_contained(out_dir, expected_root, stratum=stratum)

    staging_dir = f"{out_dir}.staging"
    for label, p in (("output", out_dir), ("staging", staging_dir)):
        if os.path.exists(p):
            raise GateBAbort(f"{label} directory {p} already exists; restart runs from a fresh directory")
    os.makedirs(staging_dir)
    writer = BattleResultWriter(os.path.join(staging_dir, "rows.jsonl"))

    hero_team_abs = os.path.abspath(os.path.join(teams_root, STRENGTH_HOLDOUT_HERO_TEAM_PATH))
    rows: list[dict] = []
    for key in schedule.battle_keys:
        seed = derive_battle_seed(schedule.seed_base, key.seed_index)  # GLOBAL index, never `key.seed`
        battle_id = make_battle_id(schedule.schedule_hash, key.seed_index, seed)
        # Rev. 14 fix (§1m, third review round): HOLDOUT_TEAMS_DIR is now imported from
        # holdout_leakage_scan.py rather than hardcoded inline here a second time -- it is also
        # the source the manifest's holdout_teams mapping (below) derives each team_path from,
        # so the two can never independently drift apart.
        opp_team_path = f"{HOLDOUT_TEAMS_DIR}{key.holdout_team_id}.txt"
        opp_team_abs = os.path.abspath(os.path.join(teams_root, opp_team_path))

        for label, abs_path in (("hero", hero_team_abs), ("opponent", opp_team_abs)):
            try:
                packed = load_packed_team(abs_path)
            except FileNotFoundError as exc:
                raise GateBAbort(f"{label} team not found at {abs_path!r}; refusing to challenge with an empty team") from exc
            except ValueError as exc:
                # load_packed_team also raises a bare ValueError for a malformed (multi-line)
                # .packed file -- caught here too so a corrupted team file fails closed as
                # GateBAbort like every other malformed-input path in this function, rather than
                # escaping raw.
                raise GateBAbort(f"{label} team at {abs_path!r} is malformed: {exc}") from exc
            if not packed:
                raise GateBAbort(f"{label} team resolves to an EMPTY packed team at {abs_path!r}")

        # winner/turns/end_reason/invalid_choices/crashes/decision_latency_p95_ms are
        # STRUCTURALLY UNREACHABLE from the returned `stats` object (verified against the full
        # real GauntletStats class -- it has only games/hero_wins/villain_wins/ties/
        # invalid_choices/crashes/latencies, all RUN-LIFETIME aggregates, no per-battle winner
        # or end_reason under any name). The real per-battle record only ever arrives through
        # this callback, exactly mirroring cli.py's run_schedule/on_br closure.
        captured: dict = {}

        def _capture(record, _key=key, _battle_id=battle_id, _seed=seed, _opp_team_path=opp_team_path):
            captured.update({
                "battle_id": _battle_id, "run_id": f"{provenance['candidate_identity']}-{hero_agent}",
                "config_id": hero_agent, "format_id": schedule.format_id,
                "config_hash": provenance["config_hash"], "schedule_hash": schedule.schedule_hash,
                "seed_index": _key.seed_index, "opp_policy": _key.opponent_policy,
                "hero_team_path": STRENGTH_HOLDOUT_HERO_TEAM_PATH, "opp_team_path": _opp_team_path,
                "seed": _seed, "seed_base": schedule.seed_base,
                "git_sha": provenance["git_sha"], "dirty": False,
                "opp_team_hash": holdout_team_content_hashes[_key.holdout_team_id],  # real sealed hash, never the bare team_id
                # panel_hash is NULLABLE per result_jsonl.py's schema, but pairing.py's
                # _check_constant_fields indexes row["panel_hash"] directly (pairing.py:105,
                # no .get) -- omitting it doesn't fail validate_battle_row, it crashes pair_runs
                # with a raw KeyError (not a PairingError, so combine's except clause wouldn't
                # even catch it). Required in practice regardless of what result_jsonl.py alone
                # would tolerate.
                "panel_hash": schedule.panel_hash,
                **record,  # winner, turns, end_reason, end_hp_diff, invalid_choices, crashes,
                           # decision_latency_p95_ms, room_raw_path, normalized_room_log_sha256
            })

        try:
            stats = asyncio.run(gauntlet_runner(
                games=1, hero_agent=hero_agent, villain_agent=key.opponent_policy,
                format_id=schedule.format_id, team_path=hero_team_abs, opp_team_path=opp_team_abs,
                on_battle_result=_capture,
            ))
        except Exception as exc:
            # NF5 fix (Rev. 9): gauntlet_runner is the real run_local_gauntlet, an external
            # websocket client this plan does not author -- a server disconnect mid-battle
            # (arguably the single most likely runtime failure of this whole 180-battle loop) is
            # not GateBAbort, and nothing wrapped this call before (flagged but not fixed in
            # §1g's Rev. 8 audit table as an untraced trust boundary -- the CLI handler's own
            # comment then claimed this whole call graph was proven GateBAbort-only WITHOUT that
            # table's qualifier, the same false-unqualified-claim shape as NF2). A boundary wrap
            # does not need the callee's exception contract audited first -- that is the point of
            # a boundary: convert whatever crosses it to this function's own contract regardless
            # of what the un-audited callee can raise. except Exception (not a narrower type) is
            # deliberate for exactly that reason; BaseException subclasses (KeyboardInterrupt,
            # SystemExit) are NOT Exception subclasses and still propagate uninterrupted.
            raise GateBAbort(
                f"gauntlet runner failed at seed_index {key.seed_index}: {exc}"
            ) from exc
        if stats.games != 1:
            raise GateBAbort(
                f"battle at seed_index {key.seed_index} did not complete exactly one game "
                f"(games={stats.games}); restart from a fresh arm run"
            )
        if not captured:
            raise GateBAbort(
                f"battle at seed_index {key.seed_index} completed but on_battle_result never "
                "fired -- no result to publish; restart from a fresh arm run"
            )

        try:
            writer.write(captured)  # validates against result_jsonl's REQUIRED/NULLABLE schema, then appends
        except ResultRowError as exc:
            # NF3 fix (Rev. 8): BattleResultWriter.write() calls validate_battle_row internally
            # (result_jsonl.py:107-110) and can raise ResultRowError -- NF1 (Rev. 7) fixed the
            # READ-side call to the same validator in _read_arm, but this is the WRITE side, a
            # different function the Rev. 7 audit table did not cover because it was scoped to
            # "functions touched in Rev. 7," not to this function's full exception surface (the
            # scoping mistake itself, corrected in Rev. 8 -- see §1g). Reachable in practice:
            # _capture merges **record from _battle_result_record, whose field set has grown
            # historically (decision_trace_count/_sha256, normalized_room_log_sha256, panel_split
            # were all added after this schema's original shape) -- a field result_jsonl.py
            # doesn't yet know about raises "unknown fields" here, mid-loop, potentially after
            # staging_dir and prior rows already exist on disk (left in place on abort, same as
            # every other GateBAbort raised inside this loop -- no new cleanup behavior).
            raise GateBAbort(
                f"battle at seed_index {key.seed_index} produced a row that fails schema "
                f"validation: {exc}"
            ) from exc
        rows.append(captured)

    # Seed-log proof AFTER the battle loop, BEFORE any publish -- mirrors i8d_runner.py/
    # coverage_runner.py's own private _verify_seed_alignment call site exactly (same position
    # in the flow: after the loop, before the verdict/manifest write, before os.replace).
    try:
        seed_records = verify_seed_log(seed_log_path, schedule.seed_base, len(rows))
    except SeedLogError as exc:
        raise GateBAbort(f"seed-log verification failed: {exc}") from exc
    for key, rec in zip(schedule.battle_keys, seed_records):
        if key.seed_index != rec["battle_index"]:
            raise GateBAbort(
                f"seed-log/schedule misalignment: battle-key seed_index {key.seed_index} != "
                f"logged battle_index {rec['battle_index']}"
            )

    # Rev. 14 fix (§1m, third review round P1): a bare team_id LIST (Rev. 13) only ever ASSERTED
    # which six teams this arm scheduled -- it was never BOUND to what the rows themselves
    # actually contain. A canonical MAPPING closes that gap: team_path is the real path each row's
    # opp_team_path was built from (same HOLDOUT_TEAMS_DIR expression, just above) and
    # content_hash is the exact value each row's opp_team_hash was stamped with
    # (holdout_team_content_hashes[team_id], _capture's own opp_team_hash line above) -- so Task
    # 10 can now PROVE agreement between the manifest and the rows, not just trust it.
    holdout_teams = {
        team_id: {
            "team_path": f"{HOLDOUT_TEAMS_DIR}{team_id}.txt",
            "content_hash": holdout_team_content_hashes[team_id],
        }
        for team_id in sorted(scheduled_team_ids)
    }
    _write_json_atomic(os.path.join(staging_dir, "arm_manifest.json"), {
        "hero_agent": hero_agent, "schedule_hash": schedule.schedule_hash,
        "seed_base": schedule.seed_base, "panel_hash": schedule.panel_hash,
        "holdout_teams": holdout_teams,
        # Rev. 15 fix (§1n, Task-3-review P1 #1): the three fields established near the top of
        # this function (stratum/platform_attestation/date_stratum_id) are recorded here so
        # combine_strength_holdout_arms (Task 10) can validate and compare them WITHOUT ever
        # calling detect_stratum() itself.
        "stratum": stratum, "platform_attestation": platform_attestation,
        "date_stratum_id": date_stratum_id,
        **provenance, "seed_log_path": seed_log_path, "n_rows": len(rows),
    })
    os.replace(staging_dir, out_dir)
    return {"hero_agent": hero_agent, "rows": rows, "out_dir": out_dir, **provenance}

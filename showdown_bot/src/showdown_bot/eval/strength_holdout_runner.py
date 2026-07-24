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

Nothing in this function trusts a caller-supplied claim it can instead re-derive or re-verify
from the real repo/filesystem state (review-fix, five P1s): the schedule is rebuilt from its own
team_ids/panel_hash/seed_base and compared field-for-field; every sealed team hash is
recomputed from the real .txt+.packed files before battle 1; the seed log must be built DURING
this run (SHOWDOWN_EVAL_SEED_LOG canonically equals seed_log_path, and the file must be absent
or empty before battle 1) and is copied byte-exact into the published artifact; the
on_battle_result callback's record is checked against an exact field whitelist so it can never
overwrite a runner-owned provenance field; calc_backend is derived internally (never caller-
supplied) and recorded in the manifest.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date
from pathlib import Path

from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
from showdown_bot.eval.i8d_runner import _write_json_atomic
from showdown_bot.eval.panel import PanelError, team_content_hash
from showdown_bot.eval.result_jsonl import BattleResultWriter, make_battle_id, ResultRowError
from showdown_bot.eval.seeding import derive_battle_seed, verify_seed_log, SeedLogError
from showdown_bot.eval.strata_guard import detect_stratum, stratum_output_root
from showdown_bot.eval.strength_holdout_schedule import (
    build_strength_holdout_schedule, STRENGTH_HOLDOUT_FORMAT_ID, STRENGTH_HOLDOUT_HERO_TEAM_PATH,
    STRENGTH_HOLDOUT_SEED_BASE, StrengthHoldoutSchedule,
)
from showdown_bot.learning.provenance import make_candidate_identity
from showdown_bot.team.pack import load_packed_team

# Rev. 15 fix (§1n, Task-3-review P1 #2): matches holdout_leakage_scan.ALLOWED_DIRECTORY_PREFIXES'
# "data/eval/champions-panel-v0/strength-holdout-v0/" entry (Task 2) exactly, minus the trailing
# slash stratum_output_root's own f"{base_dir}/{stratum}" join adds back -- every arm this
# function publishes therefore lands somewhere the leakage guard's allowlist already covers,
# with no allowlist change needed.
STRENGTH_HOLDOUT_OUTPUT_BASE = "data/eval/champions-panel-v0/strength-holdout-v0"

# Task-10 review-fix, P1 #3: the NINE existing Champions M-A teams the six holdout candidates are
# compared against by the near-duplicate guard (DESIGN sec 3.3 / plan §16 item 5) -- five
# panel_champions_v0 teams plus the four frozen coverage opponents. Pinned here as PATHS, not as a
# caller-supplied species mapping: before this fix both sides of that comparison were bare caller
# assertions (`holdout_candidate_species`/`reference_species`), so a caller could hand combine any
# species lists it liked -- including ones that trivially never overlap -- and the guard would
# happily "pass". near_duplicate.load_team_species already existed to derive species from a team's
# REAL sealed .packed content and was verified by its own tests, but had no production call site
# at all. Both sides are now derived through it, from these pinned paths and from the arm's own
# row-bound holdout_teams mapping respectively.
CANONICAL_REFERENCE_TEAM_PATHS = {
    "disruption": "showdown_bot/teams/panel_champions_v0/disruption.txt",
    "goodstuff": "showdown_bot/teams/panel_champions_v0/goodstuff.txt",
    "rain_offense": "showdown_bot/teams/panel_champions_v0/rain_offense.txt",
    "tailwind_offense": "showdown_bot/teams/panel_champions_v0/tailwind_offense.txt",
    "trick_room": "showdown_bot/teams/panel_champions_v0/trick_room.txt",
    "cov_foe_slot0": "showdown_bot/teams/panel_champions_coverage_v0/cov_foe_slot0.txt",
    "cov_foe_slot1": "showdown_bot/teams/panel_champions_coverage_v0/cov_foe_slot1.txt",
    "cov_foe_both": "showdown_bot/teams/panel_champions_coverage_v0/cov_foe_both.txt",
    "cov_foe_tie": "showdown_bot/teams/panel_champions_coverage_v0/cov_foe_tie.txt",
}

_VALID_HERO_AGENTS = frozenset({"heuristic", "max_damage"})
_SAFE_TEAM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
# The exact, closed field set gauntlet.py's real on_battle_result(record) callback always
# carries (_battle_result_record, gauntlet.py) -- review-fix P1 #3: **record used to be
# unpacked LAST in the row dict literal, so a record containing any runner-owned key name (e.g.
# git_sha, config_hash, opp_team_hash) would silently overwrite that trusted value. Checked
# against this exact whitelist BEFORE the row is ever built, not fixed by dict key ordering.
_CALLBACK_RECORD_FIELDS = frozenset({
    "winner", "turns", "end_reason", "end_hp_diff", "invalid_choices", "crashes",
    "decision_latency_p95_ms", "room_raw_path", "normalized_room_log_sha256",
    # Gate B finding 4: per-seat degraded-decision counts. An EXACT set -- any unexpected OR
    # missing field makes the arm refuse the battle -- so these must be listed here in lockstep
    # with _battle_result_record, or every Gate B battle aborts.
    "hero_degraded_decisions", "villain_degraded_decisions",
    # Gate B finding 5: per-seat invalid-choice counts, same lockstep requirement.
    # `invalid_choices` (above) stays required and unchanged.
    "hero_invalid_choices", "villain_invalid_choices",
})


class GateBAbort(Exception):
    """A technical abort -- dirty tree, hash mismatch, infra failure, or zero-battle timeout.
    NOT a verdict (ports Gate A's DESIGN sec 2.6 taxonomy, since Gate B has no equivalent
    dedicated section -- grounding report sec 2)."""


def _default_calc_factory():
    """The same CalcClient the battle loop builds, constructed exactly the same way."""
    from showdown_bot.engine.calc.client import CalcClient

    return CalcClient()


def assert_calc_answers(*, calc_factory=_default_calc_factory) -> None:
    """Prove the damage calculator ANSWERS before battle 1, or abort (Gate B finding 4).

    This does NOT replace the per-decision degraded counter -- calc can die mid-run, and only the
    counter sees that. It catches the common case (a worktree with no `npm ci --prefix tools/calc`,
    a missing node, a dead transport) before 180 battles are spent producing rows that look clean.

    The check is a real probe damage call whose result must be a positive number. Deliberately
    NOT checked: whether `node_modules` exists, whether a binary is on PATH, or what
    `calc_backend` says -- `calc_backend` is derived from CONFIGURATION and records intent, which
    is precisely why a 30-battle run with the calc backend dead still stamped itself
    `calc_backend: oneshot`. Existence is not an answer; a number is.
    """
    from showdown_bot.engine.calc.models import CalcMon, DamageRequest

    try:
        calc = calc_factory()
    except Exception as exc:
        raise GateBAbort(
            f"calc preflight: the damage-calc backend could not be built ({exc}) -- refusing to "
            "play before battle 1, because every decision would silently fall back to a legal "
            "default and the run would publish clean-looking rows"
        ) from exc

    try:
        result = calc.damage(DamageRequest(
            attacker=CalcMon(species="Pikachu", level=50),
            defender=CalcMon(species="Blissey", level=50),
            move="Thunderbolt",
        ))
        damage = getattr(result, "max_damage", None)
        error = getattr(result, "error", None)
        if error or not isinstance(damage, int) or isinstance(damage, bool) or damage <= 0:
            raise GateBAbort(
                f"calc preflight: probe damage call did not answer (max_damage={damage!r}, "
                f"error={error!r}) -- refusing to play before battle 1"
            )
    except GateBAbort:
        raise
    except Exception as exc:
        raise GateBAbort(
            f"calc preflight: probe damage call failed ({exc}) -- refusing to play before battle 1"
        ) from exc
    finally:
        # The arm builds one calc per battle; leaking the probe's subprocess would regress the
        # very path the Kaggle-OOM per-battle-teardown fix exists to protect.
        try:
            calc.close()
        except Exception:  # noqa: BLE001 - teardown is best-effort; never masks the verdict above
            pass


# Windows-only transient directory-rename failures that a fully-valid ``os.replace(staging, out)``
# can still hit: another process (search indexer, AV real-time scan, a not-yet-released handle on a
# just-written staging file) holds the directory or a file inside it for a brief window. POSIX does
# not raise these for a plain rename, so the retry loop below is a no-op cost off Windows. 5 =
# ERROR_ACCESS_DENIED, 32 = ERROR_SHARING_VIOLATION, 33 = ERROR_LOCK_VIOLATION -- and ONLY these.
_PUBLISH_TRANSIENT_WINERRORS = frozenset({5, 32, 33})
_PUBLISH_RETRY_DEADLINE_S = 10.0   # bounded wall-clock window; never an unbounded retry
_PUBLISH_RETRY_BACKOFF_S = 0.2


def _atomic_publish_dir(
    staging_dir: str, out_dir: str, *, replace=os.replace, exists=os.path.exists,
    monotonic=time.monotonic, sleep=time.sleep,
    deadline_s: float = _PUBLISH_RETRY_DEADLINE_S, backoff_s: float = _PUBLISH_RETRY_BACKOFF_S,
) -> None:
    """Publish a fully-staged directory via the SINGLE atomic rename ``os.replace(staging_dir,
    out_dir)`` -- the one shared publish primitive for both the strength-holdout arm and combine.

    Problem it fixes: the lone unguarded ``os.replace`` reproducibly aborted a completed arm on
    Windows with ``PermissionError [WinError 5]`` at publish time (candidate ``c8752b3``, Arm A --
    all 180 battles had already run and staged). Effect: a completed run threw its evidence away at
    the very last step. Fix: retry ONLY the classified transient Windows rename errors (5/32/33)
    within a bounded wall-clock deadline, with a fixed backoff, keeping every other property of the
    original single-rename publish:

    - **no copy fallback, no partial promotion**: the ONLY operation is the atomic directory rename;
    - **fail-closed, never overwrite**: if ``out_dir`` exists at entry OR appears during the retry
      window (another writer got there first), abort without renaming;
    - **persistent transient error**: after ``deadline_s`` the staging dir is left intact for
      diagnosis and ``out_dir`` is still absent -- a clean ``GateBAbort``, not a raw traceback;
    - **non-transient ``OSError``**: re-raised immediately, with no retry (a real bug must not be
      masked by waiting).

    All of ``replace``/``exists``/``monotonic``/``sleep`` are injectable so the contract is unit
    tested without a real clock or a real filesystem race.
    """
    start = monotonic()
    while True:
        # Fail closed BEFORE every attempt: os.replace onto an existing directory would either
        # raise or (for an empty target on POSIX) silently overwrite -- neither is acceptable for a
        # published held-out bundle. Checked each iteration so a final dir appearing mid-retry is
        # caught too, never overwritten.
        if exists(out_dir):
            raise GateBAbort(
                f"refusing to publish {staging_dir!r} -> {out_dir!r}: the final directory already "
                "exists -- never overwrite a published bundle; the staging dir is left intact"
            )
        try:
            replace(staging_dir, out_dir)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            if winerror not in _PUBLISH_TRANSIENT_WINERRORS:
                raise  # non-transient: immediate abort, no retry (do not mask a real failure)
            if monotonic() - start >= deadline_s:
                raise GateBAbort(
                    f"could not atomically publish {staging_dir!r} -> {out_dir!r} within "
                    f"{deadline_s:g}s: a transient Windows rename error (WinError {winerror}) "
                    "persisted. Staging is preserved and the final dir was not created; nothing "
                    "was copied or partially promoted."
                ) from exc
            sleep(backoff_s)


def _hash_randomization_enabled() -> bool:
    # Review-fix (Step 2 round 2, P1): the AUTHORITATIVE reproducibility signal. Whether string
    # hashing is randomized this run is fixed at interpreter startup and exposed read-only as
    # sys.flags.hash_randomization (0 == PYTHONHASHSEED was 0/disabled at start; 1 == randomized).
    # Assigning os.environ["PYTHONHASHSEED"] mid-process does NOT change it -- that is exactly the
    # hole the env-only check left open. Wrapped in this seam so unit tests can force the
    # on-state without spawning a differently-seeded interpreter.
    return bool(sys.flags.hash_randomization)


def _git_is_dirty(cwd: str | None = None) -> bool:
    # Task-10 review-fix, P1 #2: `cwd` added so combine_strength_holdout_arms can ask about the
    # SAME checkout its repo-dependent guards (verify_baseline, the leakage scan's `git show
    # HEAD:<path>`) actually read, rather than whatever directory the process happens to sit in.
    # Defaults to None -- unchanged behaviour for Task 9's own callers.
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError outside a git checkout;
    # a missing git executable raises FileNotFoundError regardless of check=. Both were unguarded
    # and would escape resolve_strength_holdout_provenance -> run_strength_holdout_arm as a raw
    # traceback, before a single battle is played -- not caught by the arm CLI, which only ever
    # catches GateBAbort. Defined in this module (unlike the leakage-scan git calls), so the fix
    # can fold directly into GateBAbort with no cross-module dependency.
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True, cwd=cwd,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GateBAbort(f"cannot determine git dirty-state: {exc}") from exc
    return bool(result.stdout.strip())


def _git_sha(cwd: str | None = None) -> str:
    # NF4 fix (Rev. 8): same as _git_is_dirty above. Task-10 review-fix, P1 #2: same `cwd`.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=cwd,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GateBAbort(f"cannot determine git sha: {exc}") from exc
    return result.stdout.strip()


def _derive_config_provenance(hero_agent: str) -> dict:
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
    STRENGTH_HOLDOUT_FORMAT_ID`). `format_id` is passed explicitly, binding this function's
    config_hash to the format Gate B actually plays, not to whatever `resolve_coverage_provenance`
    happens to default to.

    Review-fix P1 #5: this function used to extract only `["config_hash"]`, silently discarding
    `resolve_coverage_provenance`'s ALSO-derived `calc_backend` -- the caller-supplied
    `calc_backend` parameter `run_strength_holdout_arm` used to accept was therefore both
    UNVERIFIED (never checked against the real environment) and UNUSED (never actually threaded
    into anything). `oneshot` and `persistent` produce the SAME config_hash/candidate_identity
    (confirmed: `make_config_hash`'s manifest does not include calc_backend), so without binding
    the REAL derived value somewhere, a run could silently switch backends between arms with no
    way to detect it after the fact -- the same class of gap already treated as a P1 at the
    Coverage gate. Both `config_hash` and `calc_backend` are now returned together and the
    caller propagates both into the manifest.

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
        provenance = resolve_coverage_provenance(
            hero_agent=hero_agent, format_id=STRENGTH_HOLDOUT_FORMAT_ID,
        )
    except (CoverageRunError, ItemdataStaleError, SpeciesMetaStaleError, PinnedCalcError) as exc:
        raise GateBAbort(
            f"config provenance derivation failed for hero_agent={hero_agent!r}: {exc}"
        ) from exc
    return {"config_hash": provenance["config_hash"], "calc_backend": provenance["calc_backend"]}


def resolve_strength_holdout_provenance(*, hero_agent: str = "heuristic") -> dict:
    """Derive this run's own git_sha/config_hash/calc_backend/candidate_identity fresh -- never
    caller-trusted. Refuses on a dirty tree (GateBAbort, not a verdict)."""
    if _git_is_dirty():
        raise GateBAbort("dirty tree: refusing to derive a candidate identity from uncommitted changes")
    git_sha = _git_sha()
    config_provenance = _derive_config_provenance(hero_agent)
    config_hash = config_provenance["config_hash"]
    candidate_identity = make_candidate_identity(hero_agent=hero_agent, git_sha=git_sha, config_hash=config_hash)
    return {
        "hero_agent": hero_agent, "git_sha": git_sha, "config_hash": config_hash,
        "calc_backend": config_provenance["calc_backend"], "candidate_identity": candidate_identity,
    }


def _resolve_canonical(path: str) -> Path:
    """Absolute, symlink/junction-resolved, OS-normalized form of ``path`` (``Path.resolve()``,
    ``strict=False`` by default -- a non-existent tail is appended as given, no filesystem lookup
    required for it)."""
    return Path(path).resolve()


def _assert_out_dir_contained(out_dir: str, expected_root: str, *, stratum: str) -> None:
    """Task 9 known-P1 fix: bind out_dir to expected_root via each path's REAL canonical
    absolute form, never a lexical/substring comparison.

    Both paths are resolved through ``_resolve_canonical``: any EXISTING prefix component is
    resolved through the real filesystem, following symlinks and Windows junctions to their true
    target, while a non-existent tail (out_dir itself must not exist yet -- checked separately by
    the caller) is appended as given. Containment is then checked by COMPONENT, not by string
    prefix/substring -- a foreign path that merely contains expected_root's text (e.g. a
    differently-named sibling, or a decoy directory that happens to nest the same path segments)
    fails this check even though it would have passed a bare substring test. Windows path
    components are folded to lowercase before comparing (NTFS is case-insensitive); every other
    platform compares case-sensitively.

    ``expected_root`` is typically a relative, repo-root path (``stratum_output_root``'s own
    return shape) -- it resolves against the current working directory, matching how every real
    caller of this function is expected to run (from the repo root, exactly like every other
    gate in this codebase resolves its own relative paths)."""
    out_resolved = _resolve_canonical(out_dir)
    root_resolved = _resolve_canonical(expected_root)
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


def _assert_seed_log_bound_to_this_run(seed_log_path: str) -> None:
    """Review-fix P1 #2: SHOWDOWN_EVAL_SEED_LOG (what a real server would be told to write to)
    must canonically equal seed_log_path (what this run reads back and verifies) -- otherwise a
    caller could point this run at an arbitrary pre-existing file with no relationship to what
    the server actually wrote. The file must ALSO be absent or empty before battle 1: a
    genuinely fresh, run-specific log is the only thing that can prove THESE seeds, not a stale
    or pre-populated one (even one that would itself verify)."""
    env_seed_log = os.environ.get("SHOWDOWN_EVAL_SEED_LOG", "")
    if not env_seed_log:
        raise GateBAbort(
            f"SHOWDOWN_EVAL_SEED_LOG must be set and canonically equal seed_log_path "
            f"{seed_log_path!r} -- the server must be started writing its seed log to exactly "
            "the path this run will read back and verify"
        )
    env_resolved = str(_resolve_canonical(env_seed_log))
    target_resolved = str(_resolve_canonical(seed_log_path))
    if platform.system() == "Windows":
        env_resolved, target_resolved = env_resolved.lower(), target_resolved.lower()
    if env_resolved != target_resolved:
        raise GateBAbort(
            f"SHOWDOWN_EVAL_SEED_LOG={env_seed_log!r} does not canonically equal "
            f"seed_log_path={seed_log_path!r} (resolved {env_resolved!r} != {target_resolved!r}) "
            "-- the server must be started writing its seed log to exactly the path this run "
            "will read back and verify"
        )
    if os.path.exists(seed_log_path) and os.path.getsize(seed_log_path) > 0:
        raise GateBAbort(
            f"seed_log_path {seed_log_path!r} already exists and is non-empty before any "
            "battle has played -- a stale or pre-populated seed log cannot prove THIS run's "
            "seeds; restart from a fresh, empty (or absent) seed log"
        )


def _assert_schedule_is_genuine(schedule) -> list[str]:
    """Review-fix P1 #4: the caller-supplied schedule must be a REAL StrengthHoldoutSchedule
    that rebuilds byte-for-byte from ``build_strength_holdout_schedule`` given its own
    team_ids/panel_hash/seed_base -- never trusted as-is. A caller-controlled empty/reshaped/
    forged schedule (fewer battle_keys, non-pinned policies, a foreign seed_base, ...) could
    otherwise publish a self-consistent but meaningless "0 real battles" arm artifact. Rebuilding
    with the schedule's OWN team_ids/panel_hash/seed_base and comparing every field (battle_keys,
    schedule_hash, panel_hash, seed_base, format_id -- StrengthHoldoutSchedule's full dataclass
    equality) transitively proves the six team IDs are unique-and-exactly-six, the two policies
    are the pinned pair, there are 15 seeds, 180 keys with contiguous global indices 0..179, and
    format_id is the pinned constant -- everything ``build_strength_holdout_schedule`` itself
    always produces for those inputs. seed_base is checked SEPARATELY against the one true
    pinned constant, since feeding the schedule's own (possibly wrong) seed_base back into the
    rebuild would make that one check vacuous. Returns the sorted team_ids on success."""
    if not isinstance(schedule, StrengthHoldoutSchedule):
        raise GateBAbort(
            f"schedule must be a real StrengthHoldoutSchedule built by "
            f"build_strength_holdout_schedule, got {type(schedule).__name__}"
        )
    if schedule.seed_base != STRENGTH_HOLDOUT_SEED_BASE:
        raise GateBAbort(
            f"schedule.seed_base={schedule.seed_base!r} != the pinned seed namespace "
            f"{STRENGTH_HOLDOUT_SEED_BASE!r} -- refusing an unpinned seed namespace"
        )
    team_ids = sorted({key.holdout_team_id for key in schedule.battle_keys})
    unsafe = [t for t in team_ids if not _SAFE_TEAM_ID_PATTERN.fullmatch(t)]
    if unsafe:
        raise GateBAbort(
            f"holdout team_id(s) {unsafe} contain unsafe characters -- team_id is used to build "
            "a file path and must match [A-Za-z0-9_-]+ only"
        )
    try:
        canonical = build_strength_holdout_schedule(
            holdout_team_ids=team_ids, panel_hash=schedule.panel_hash, seed_base=schedule.seed_base,
        )
    except ValueError as exc:
        raise GateBAbort(
            f"schedule does not rebuild to a genuine strength-holdout schedule: {exc}"
        ) from exc
    if schedule != canonical:
        raise GateBAbort(
            "schedule does not match the canonical rebuild from its own team_ids/panel_hash/"
            "seed_base -- refusing a caller-controlled or tampered schedule"
        )
    return team_ids


def _assert_hero_and_opponent_teams_are_valid(
    *, teams_root: str, scheduled_team_ids, holdout_team_content_hashes: dict[str, str],
) -> None:
    """Review-fix P1 #1: every hero/opponent team file is checked BEFORE battle 1 (not lazily,
    once per battle, inside the loop) -- existence, non-empty, AND that the caller-supplied
    opp_team_hash for each scheduled team matches a FRESH recompute via
    ``panel.team_content_hash`` against the actual .txt+.packed files that will be played. A
    caller can no longer publish a row/manifest stamped with a hash that was never verified
    against the real sealed team content."""
    hero_abs = os.path.abspath(os.path.join(teams_root, STRENGTH_HOLDOUT_HERO_TEAM_PATH))
    try:
        hero_packed = load_packed_team(hero_abs)
    except FileNotFoundError as exc:
        raise GateBAbort(f"hero team not found at {hero_abs!r}; refusing to challenge with an empty team") from exc
    except ValueError as exc:
        raise GateBAbort(f"hero team at {hero_abs!r} is malformed: {exc}") from exc
    if not hero_packed:
        raise GateBAbort(f"hero team resolves to an EMPTY packed team at {hero_abs!r}")

    for team_id in sorted(scheduled_team_ids):
        opp_team_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.txt"
        opp_abs = os.path.abspath(os.path.join(teams_root, opp_team_path))
        try:
            opp_packed = load_packed_team(opp_abs)
        except FileNotFoundError as exc:
            raise GateBAbort(f"opponent team not found at {opp_abs!r}; refusing to challenge with an empty team") from exc
        except ValueError as exc:
            raise GateBAbort(f"opponent team at {opp_abs!r} is malformed: {exc}") from exc
        if not opp_packed:
            raise GateBAbort(f"opponent team resolves to an EMPTY packed team at {opp_abs!r}")

        try:
            fresh_hash = team_content_hash(teams_root, opp_team_path)
        except PanelError as exc:
            raise GateBAbort(f"cannot recompute the sealed hash for team_id={team_id!r}: {exc}") from exc
        claimed_hash = holdout_team_content_hashes[team_id]
        if fresh_hash != claimed_hash:
            raise GateBAbort(
                f"holdout_team_content_hashes[{team_id!r}]={claimed_hash!r} does not match the "
                f"freshly recomputed sealed hash {fresh_hash!r} for {opp_team_path!r} -- refusing "
                "to trust a caller-supplied hash that disagrees with the real team content"
            )


def run_strength_holdout_arm(
    *, hero_agent: str, schedule, out_dir: str, seed_log_path: str,
    holdout_team_content_hashes: dict[str, str], date_stratum_id: str, teams_root: str = ".",
    gauntlet_runner=None, stratum_env_override: str | None = None,
) -> dict:
    """Plays all len(schedule.battle_keys) battles for ONE arm, staged+atomically published.
    gauntlet_runner defaults to the real client.gauntlet.run_local_gauntlet; tests inject a fake
    so this whole function is testable without a live server.

    holdout_team_content_hashes maps holdout_team_id -> its REAL sealed team_content_hash
    (Task 12's seal_team output, .txt+.packed together) -- required, no default, and must
    contain EXACTLY the schedule's own six team IDs (no missing, no extra). Every entry is
    re-verified against a fresh ``panel.team_content_hash`` recompute before battle 1 (review-fix
    P1 #1) -- the row's opp_team_hash field must never fall back to the bare team_id string, nor
    to an unverified caller claim (Rev. 3 P2 fix: that field name promises a hash to every
    downstream consumer -- the leakage scan, the disjointness check, cell grouping -- and a
    wrong or non-hash placeholder there would silently defeat all three).

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

    # Review-fix P1 #4 (hero_agent half): Gate B only ever plays Candidate A ('heuristic') or
    # Baseline B ('max_damage') -- checked before any provenance/schedule work.
    if hero_agent not in _VALID_HERO_AGENTS:
        raise GateBAbort(
            f"hero_agent must be one of {sorted(_VALID_HERO_AGENTS)}, got {hero_agent!r} -- "
            "Gate B only ever plays Candidate A ('heuristic') or Baseline B ('max_damage')"
        )
    # Review-fix P1 #4 (schedule half): reject a caller-controlled/forged schedule before doing
    # any expensive provenance derivation.
    scheduled_team_ids = set(_assert_schedule_is_genuine(schedule))

    provenance = resolve_strength_holdout_provenance(hero_agent=hero_agent)

    # Review-fix P1 #1 (exact-set half): the map must name EXACTLY the scheduled teams -- not
    # merely a superset that happens to cover them, and not merely "no missing" as before.
    if set(holdout_team_content_hashes) != scheduled_team_ids:
        missing = scheduled_team_ids - set(holdout_team_content_hashes)
        extra = set(holdout_team_content_hashes) - scheduled_team_ids
        problems = []
        if missing:
            problems.append(f"missing sealed hash(es) for {sorted(missing)}")
        if extra:
            problems.append(f"unexpected extra hash(es) for {sorted(extra)}")
        raise GateBAbort(
            "holdout_team_content_hashes must contain EXACTLY the scheduled team IDs: "
            f"{' and '.join(problems)} -- every scheduled team must be sealed (Task 12) before "
            "any arm can be played, and no unrelated team may be included"
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
    # Review-fix P1 #2: SHOWDOWN_EVAL_SEED_LOG must canonically be THIS run's seed_log_path, and
    # that file must be absent/empty before battle 1 -- see the helper's own docstring.
    _assert_seed_log_bound_to_this_run(seed_log_path)

    # Rev. 15 fix (§1n, Task-3-review P1 #1/#2): stratum/platform/out_dir identity, established
    # ONCE here and written into the manifest below -- never re-derived by the combiner.
    # Review-fix P2: a whitespace-only or non-string value used to pass this check via bare
    # truthiness -- now requires a genuine non-blank string.
    if not isinstance(date_stratum_id, str) or not date_stratum_id.strip():
        raise GateBAbort(
            "date_stratum_id is required and must be a non-empty, non-blank string -- DESIGN "
            "sec 3.5 requires a pre-registered stratum/date identifier, fixed before the run, "
            "never derived after the fact"
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

    # Review-fix (Step 2 round 2, P1): PYTHONHASHSEED must be correct AT INTERPRETER START, not
    # merely present in os.environ. Setting os.environ["PYTHONHASHSEED"]="0" mid-process does NOT
    # disable hash randomization -- the env string reads "0" while sys.flags.hash_randomization
    # stays 1 and hashes still vary run-to-run. The authoritative, load-bearing signal is
    # sys.flags.hash_randomization (via the _hash_randomization_enabled seam, so tests can drive
    # it); the env string is checked too so the recorded value is meaningful and matches the pin,
    # but it is NOT sufficient on its own. Both must agree, before battle 1, fail-closed.
    live_pythonhashseed = os.environ.get("PYTHONHASHSEED")
    if _hash_randomization_enabled():
        raise GateBAbort(
            "hash randomization is ON (sys.flags.hash_randomization == 1) -- this interpreter was "
            f"not started with PYTHONHASHSEED={SH_BASELINE_PYTHONHASHSEED!r}, so hashes vary "
            f"run-to-run (os.environ says {live_pythonhashseed!r}, which is not enough: it only "
            "takes effect at interpreter start). Refusing to play an irreproducible Gate B arm."
        )
    if live_pythonhashseed != SH_BASELINE_PYTHONHASHSEED:
        raise GateBAbort(
            f"PYTHONHASHSEED must be {SH_BASELINE_PYTHONHASHSEED!r} for a reproducible Gate B arm, "
            f"got {live_pythonhashseed!r} -- refusing to play before battle 1"
        )

    # Review-fix P1 #1 (recompute half): every hero/opponent file checked and hash-verified ONCE
    # here, before any directory is created -- not lazily, once per battle, inside the loop.
    _assert_hero_and_opponent_teams_are_valid(
        teams_root=teams_root, scheduled_team_ids=scheduled_team_ids,
        holdout_team_content_hashes=holdout_team_content_hashes,
    )

    # Cheap insurance (Gate B finding 4): prove calc ANSWERS before battle 1 rather than reading
    # it off 180 silently-degraded rows afterwards. The per-seat degraded counter on every row
    # remains the real guard -- calc can die mid-run and only that sees it.
    assert_calc_answers()

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

        # winner/turns/end_reason/invalid_choices/crashes/decision_latency_p95_ms are
        # STRUCTURALLY UNREACHABLE from the returned `stats` object (verified against the full
        # real GauntletStats class -- it has only games/hero_wins/villain_wins/ties/
        # invalid_choices/crashes/latencies, all RUN-LIFETIME aggregates, no per-battle winner
        # or end_reason under any name). The real per-battle record only ever arrives through
        # this callback, exactly mirroring cli.py's run_schedule/on_br closure.
        captured: dict = {}
        callback_schema_violation: list = []

        def _capture(record, _key=key, _battle_id=battle_id, _seed=seed, _opp_team_path=opp_team_path):
            # Review-fix P1 #3: record must carry EXACTLY the real callback's known field set --
            # any unexpected OR missing field is refused outright, so **record below can never
            # collide with (and silently overwrite) a runner-owned key.
            unexpected = set(record) - _CALLBACK_RECORD_FIELDS
            missing = _CALLBACK_RECORD_FIELDS - set(record)
            if unexpected or missing:
                callback_schema_violation.append((sorted(unexpected), sorted(missing)))
                return
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
        if callback_schema_violation:
            unexpected, missing = callback_schema_violation[0]
            raise GateBAbort(
                f"battle at seed_index {key.seed_index}: on_battle_result callback record has "
                f"unexpected field(s) {unexpected} and/or is missing field(s) {missing} -- a "
                "callback payload must match the exact expected shape; a mismatched field could "
                "otherwise silently overwrite a runner-owned provenance field"
            )
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

    # Review-fix P1 #2: once the seed log genuinely verifies, its exact bytes become part of the
    # atomic arm artifact (never left outside it, and never referenced by the caller's original,
    # possibly machine-local absolute seed_log_path).
    with open(seed_log_path, "rb") as fh:
        seed_log_bytes = fh.read()
    seed_log_relpath = "seeds.jsonl"
    with open(os.path.join(staging_dir, seed_log_relpath), "wb") as fh:
        fh.write(seed_log_bytes)
    seed_log_sha256 = hashlib.sha256(seed_log_bytes).hexdigest()

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
        # Review-fix (Step 2): record the pinned reproducibility seed this arm actually ran under
        # (already asserted == SH_BASELINE_PYTHONHASHSEED before battle 1). Task 10 compares the two
        # arms' values against each other and against the static baseline.
        "pythonhashseed": live_pythonhashseed,
        # **provenance now also carries calc_backend (review-fix P1 #5) -- Task 10 must compare
        # this manifest value and pass it on to the upstream verifiers, never hardcode "oneshot".
        **provenance,
        "seed_log_relpath": seed_log_relpath, "seed_log_sha256": seed_log_sha256,
        "seed_log_n_lines": len(seed_records), "seed_log_verified": True,
        "n_rows": len(rows),
    })
    # Publish via the Windows-retry-safe atomic rename: all 180 battles already ran and staged, so a
    # lone unguarded os.replace could still throw the whole arm away on a transient WinError 5/32/33
    # (candidate c8752b3, Arm A). Same single-rename semantics, bounded retry, staging preserved on
    # persistent failure, out_dir never overwritten.
    _atomic_publish_dir(staging_dir, out_dir)
    return {"hero_agent": hero_agent, "rows": rows, "out_dir": out_dir, **provenance}


from showdown_bot.eval.result_jsonl import validate_battle_row, ResultRowError
from showdown_bot.eval.pairing import pair_runs, PairingError
from showdown_bot.eval.strength_holdout_verdict import (
    render_strength_holdout_verdict, compute_safety_pass,
    verify_i8d_verdict_artifact, verify_coverage_verdict_artifact, StrengthHoldoutRunError,
)
from showdown_bot.eval.holdout_leakage_scan import assert_no_holdout_leakage
from showdown_bot.eval.holdout_disjointness import assert_disjoint_from_coverage
from showdown_bot.eval.near_duplicate import find_near_duplicate_flags, load_team_species
from showdown_bot.eval.strata_guard import VALID_STRATA, StratumRecord, assert_no_cross_stratum_pooling
from showdown_bot.eval.heldout_ledger import append_entry, read_ledger, check_access, LedgerError
from showdown_bot.eval.baseline import (
    load_strength_holdout_baseline, verify_strength_holdout_baseline,
    BaselineError, BaselineDriftError, SH_BASELINE_PYTHONHASHSEED,
)
from showdown_bot.eval.report import _build_cells, _build_aggregates
# Rev. 19 note (Task 9 review-fix sync, §1r): _assert_seed_artifact_verified (below) needs
# `hashlib`, `re`, `Path`, `platform`, `verify_seed_log`, and `SeedLogError` -- all ALREADY
# imported module-wide at the top of strength_holdout_runner.py by Task 9's own review-fix
# (`import hashlib`/`import re`/`from pathlib import Path`/`import platform`/`from
# showdown_bot.eval.seeding import ..., verify_seed_log, SeedLogError`). No new import needed
# for Task 10 itself.


def _read_arm(arm_dir: str) -> tuple[list[dict], dict]:
    # Self-found while building the Rev. 7 exception-audit table (not in NF1's own text, same
    # function/mechanism/round -- disclosed explicitly in §1f, following the Rev. 2 precedent of
    # fixing self-found adjacent bugs in the same pass rather than deferring them unmentioned):
    # open()/json.loads()/json.load() below can raise OSError (missing arm_dir/rows.jsonl/
    # arm_manifest.json, permissions), UnicodeDecodeError (non-UTF-8 bytes on disk), or
    # json.JSONDecodeError (truncated/corrupt JSON) -- none is ResultRowError, so the except
    # clause added for NF1 does not catch them. All three are the same "corrupted or stale arm
    # directory" scenario this function exists to guard against -- not a caller-contract
    # violation (e.g. a wrong-typed arm_dir), which stays unguarded per this codebase's own
    # boundary-only validation convention.
    try:
        rows = []
        with open(os.path.join(arm_dir, "rows.jsonl"), "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    row = json.loads(line)
                    # Task-10 review-fix, P2 #4: syntactically valid JSON that is not an OBJECT
                    # (`null`, a bare number, a list) used to reach validate_battle_row, whose
                    # `field in row` membership test raises a raw TypeError for None -- escaping
                    # this function's own GateBAbort contract that the CLI depends on. Checked
                    # here, before any field access, for exactly the same reason the manifest is
                    # checked below.
                    if not isinstance(row, dict):
                        raise GateBAbort(
                            f"malformed row in {arm_dir}/rows.jsonl: expected a JSON object, got "
                            f"{type(row).__name__}"
                        )
                    try:
                        validate_battle_row(row)  # F3 fix (Rev. 6): schema conformance was never checked on read
                    except ResultRowError as exc:
                        # NF1 fix (Rev. 7): a corrupted or stale-schema rows.jsonl must produce a
                        # clean abort, not a traceback -- ResultRowError was never imported or
                        # caught anywhere in this plan before this fix.
                        raise GateBAbort(f"malformed row in {arm_dir}/rows.jsonl: {exc}") from exc
                    rows.append(row)
        with open(os.path.join(arm_dir, "arm_manifest.json"), "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        # Task-10 review-fix, P2 #4: same as the row check above -- a `null` manifest reached
        # `set(manifest)` in _assert_rows_match_manifest and raised a raw TypeError ("'NoneType'
        # object is not iterable") instead of aborting cleanly.
        if not isinstance(manifest, dict):
            raise GateBAbort(
                f"malformed arm_manifest.json in {arm_dir!r}: expected a JSON object, got "
                f"{type(manifest).__name__}"
            )
    except (OSError, UnicodeDecodeError) as exc:
        raise GateBAbort(f"cannot read arm directory {arm_dir!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GateBAbort(f"malformed JSON in arm directory {arm_dir!r}: {exc}") from exc
    return rows, manifest


# NF1 fix (Rev. 7): the exact keys _assert_rows_match_manifest indexes below, checked for
# PRESENCE before any value comparison. panel_hash is deliberately included on the row side even
# though result_jsonl.NULLABLE_FIELDS does not require it -- validate_battle_row (called in
# _read_arm above) does not guarantee its presence, so a row missing it would otherwise crash
# this function's own row[field] access with a raw KeyError, exactly the N1 bug one level up
# (see the comment at Task 9's row-building site).
_MANIFEST_REQUIRED_KEYS = ("n_rows", "config_hash", "git_sha", "schedule_hash", "seed_base",
                          "panel_hash", "hero_agent", "candidate_identity", "holdout_teams",
                          # Rev. 15 fix (§1n, Task-3-review P1 #1): presence-checked here exactly
                          # like every other required field -- closed-form validity (unknown
                          # stratum value; non-string/empty platform_attestation/date_stratum_id)
                          # is checked separately, by _validate_stratum_fields below.
                          "stratum", "platform_attestation", "date_stratum_id",
                          # Rev. 19 fix (Task 9 review-fix sync, §1r): Task 9's own review-fix
                          # (5 P1s) added calc_backend (derived internally, no longer discarded)
                          # and replaced the caller-local seed_log_path field with a four-field
                          # seed PROOF -- seed_log_relpath/seed_log_sha256/seed_log_n_lines/
                          # seed_log_verified -- so the arm's manifest never again carries a
                          # machine-local absolute path. Presence-checked here; closed-form
                          # validity by _validate_seed_proof_fields below.
                          "calc_backend", "seed_log_relpath", "seed_log_sha256",
                          "seed_log_n_lines", "seed_log_verified",
                          # Review-fix (Step 2): the pinned reproducibility seed each arm ran under.
                          "pythonhashseed")
_ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK = ("config_hash", "git_sha", "schedule_hash", "seed_base", "panel_hash")
# Rev. 14 fix (§1m, third review round P1): presence-checked in the SAME per-row loop as
# _ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK (both are just "does this row have the key"), but bound
# against holdout_teams (a per-team MAPPING) in a separate function below, not the scalar
# row[field] != manifest[field] content-match loop just below this constant, which only ever
# compares a row field against ONE manifest-wide value -- opp_team_path/opp_team_hash vary
# per row by design (each row is for a DIFFERENT one of the six teams).
_ROW_REQUIRED_KEYS_FOR_TEAM_BINDING = ("opp_team_path", "opp_team_hash")
_HOLDOUT_TEAM_ENTRY_FIELDS = frozenset({"team_path", "content_hash"})


def _validate_holdout_teams_mapping(holdout_teams, which: str) -> None:
    """Rev. 14 fix (§1m, third review round P1): holdout_teams must be a CLOSED, unambiguous,
    deterministic mapping -- Rev. 13's bare team_id LIST only ever ASSERTED which six teams were
    played; it was never bound to what the rows themselves actually contain, and nothing rejected
    a malformed shape either. Every structural deviation is rejected fail-closed here, before any
    row-binding check below even attempts to read it (mirrors panel.py's own
    missing/unknown-field pattern in _load_team_list)."""
    if not isinstance(holdout_teams, dict):
        raise GateBAbort(
            f"arm {which}: manifest's holdout_teams must be an object/mapping, got "
            f"{type(holdout_teams).__name__}"
        )
    if len(holdout_teams) != 6:
        raise GateBAbort(
            f"arm {which}: manifest's holdout_teams must have exactly 6 entries, got "
            f"{len(holdout_teams)}"
        )
    for team_id, entry in holdout_teams.items():
        if not isinstance(team_id, str) or not team_id:
            raise GateBAbort(f"arm {which}: holdout_teams has a non-string or empty team_id key: {team_id!r}")
        if not isinstance(entry, dict):
            raise GateBAbort(
                f"arm {which}: holdout_teams[{team_id!r}] must be an object/mapping, got "
                f"{type(entry).__name__}"
            )
        missing = _HOLDOUT_TEAM_ENTRY_FIELDS - set(entry)
        unknown = set(entry) - _HOLDOUT_TEAM_ENTRY_FIELDS
        if missing:
            raise GateBAbort(f"arm {which}: holdout_teams[{team_id!r}] is missing field(s): {sorted(missing)}")
        if unknown:
            raise GateBAbort(f"arm {which}: holdout_teams[{team_id!r}] has unknown field(s): {sorted(unknown)}")
        for field in _HOLDOUT_TEAM_ENTRY_FIELDS:
            if not isinstance(entry[field], str) or not entry[field]:
                raise GateBAbort(
                    f"arm {which}: holdout_teams[{team_id!r}][{field!r}] must be a non-empty "
                    f"string, got {entry[field]!r}"
                )
        expected_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.txt"
        if entry["team_path"] != expected_path:
            raise GateBAbort(
                f"arm {which}: holdout_teams[{team_id!r}]['team_path']={entry['team_path']!r} "
                f"is not the canonical path for this team_id (expected {expected_path!r})"
            )


def _validate_stratum_fields(manifest: dict, which: str) -> None:
    """Rev. 15 fix (§1n, Task-3-review P1 #1): stratum/platform_attestation/date_stratum_id are
    now REQUIRED manifest fields (presence checked by _MANIFEST_REQUIRED_KEYS, same as
    holdout_teams) -- but presence alone is not closed validation. A stratum value that is
    present but not one of strata_guard.VALID_STRATA, or a platform_attestation/date_stratum_id
    that is present but empty or the wrong type, must abort here -- exactly the same
    "missing, unknown, or type-wrong" standard _validate_holdout_teams_mapping already applies to
    holdout_teams, now applied to these three fields."""
    stratum = manifest["stratum"]
    if not isinstance(stratum, str) or stratum not in VALID_STRATA:
        raise GateBAbort(
            f"arm {which}: manifest's stratum={stratum!r} is not one of the known strata "
            f"{sorted(VALID_STRATA)}"
        )
    for field in ("platform_attestation", "date_stratum_id"):
        value = manifest[field]
        if not isinstance(value, str) or not value:
            raise GateBAbort(f"arm {which}: manifest's {field}={value!r} must be a non-empty string")


_SUPPORTED_CALC_BACKENDS = frozenset({"oneshot", "persistent"})


def _validate_seed_proof_fields(manifest: dict, which: str) -> None:
    """Rev. 19 fix (Task 9 review-fix sync, §1r): Task 9's own review-fix derives calc_backend
    internally (never caller-supplied, never discarded) and replaced the caller-local
    seed_log_path field with a four-field seed PROOF the arm carries in its own manifest --
    seed_log_relpath/seed_log_sha256/seed_log_n_lines/seed_log_verified. Closed-form validated
    here, exactly like _validate_stratum_fields already does for
    stratum/platform_attestation/date_stratum_id, before _assert_seed_artifact_verified (below)
    ever trusts these values to locate and re-verify the real seed-log bytes."""
    calc_backend = manifest["calc_backend"]
    if not isinstance(calc_backend, str) or calc_backend not in _SUPPORTED_CALC_BACKENDS:
        raise GateBAbort(
            f"arm {which}: manifest's calc_backend={calc_backend!r} is not a supported backend "
            f"{sorted(_SUPPORTED_CALC_BACKENDS)}"
        )
    seed_log_relpath = manifest["seed_log_relpath"]
    if seed_log_relpath != "seeds.jsonl":
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_relpath={seed_log_relpath!r} must be exactly "
            "'seeds.jsonl' -- no absolute path, no subdirectory, no traversal"
        )
    seed_log_sha256 = manifest["seed_log_sha256"]
    if not isinstance(seed_log_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", seed_log_sha256) is None:
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_sha256={seed_log_sha256!r} must be a lowercase "
            "64-character sha256 hex digest"
        )
    seed_log_n_lines = manifest["seed_log_n_lines"]
    if isinstance(seed_log_n_lines, bool) or not isinstance(seed_log_n_lines, int) or seed_log_n_lines < 0:
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_n_lines={seed_log_n_lines!r} must be a genuine "
            "non-negative int"
        )
    if manifest["seed_log_verified"] is not True:
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_verified={manifest['seed_log_verified']!r} must "
            "be exactly True"
        )


def _assert_seed_artifact_verified(arm_dir: str, manifest: dict, which: str) -> None:
    """Rev. 19 fix (Task 9 review-fix sync, §1r): re-verify each arm's PUBLISHED seed log fresh,
    before pairing or any verdict -- never trust Task 9's own seed_log_verified=True claim alone
    (that is a self-report from a prior, separate process; this function independently
    reproduces the proof against the bytes actually sitting in THIS arm directory). Both arms are
    verified independently -- matching manifest values alone are never sufficient, since a
    doctored manifest could claim agreement without either seed log genuinely verifying.

    Containment is canonical (mirrors run_strength_holdout_arm's own out_dir fix, Task 9): even
    though _validate_seed_proof_fields above already rejects any seed_log_relpath other than the
    literal 'seeds.jsonl', this still resolves the real path through the filesystem (following
    any symlink/junction) and checks by path COMPONENT that it lands inside arm_dir -- defense in
    depth against a symlink/junction planted at that exact relative location pointing elsewhere.
    The resolve() call itself is wrapped: on Windows, resolving certain symlink configurations can
    raise a raw OSError (observed: WinError 267) instead of just following the link -- that must
    fail closed as GateBAbort too, not escape uncaught."""
    arm_root = Path(arm_dir).resolve()
    try:
        seed_log_path = (arm_root / manifest["seed_log_relpath"]).resolve()
    except OSError as exc:
        raise GateBAbort(f"arm {which}: cannot resolve seed log path: {exc}") from exc
    arm_parts, seed_parts = arm_root.parts, seed_log_path.parts
    if platform.system() == "Windows":
        arm_parts = tuple(p.lower() for p in arm_parts)
        seed_parts = tuple(p.lower() for p in seed_parts)
    if seed_parts[: len(arm_parts)] != arm_parts:
        raise GateBAbort(
            f"arm {which}: seed_log_relpath resolves to {str(seed_log_path)!r}, outside its own "
            f"arm directory {str(arm_root)!r} -- refusing a symlink/junction escape"
        )
    try:
        with open(seed_log_path, "rb") as fh:
            seed_log_bytes = fh.read()
    except OSError as exc:
        raise GateBAbort(f"arm {which}: cannot read seed log at {str(seed_log_path)!r}: {exc}") from exc
    fresh_sha256 = hashlib.sha256(seed_log_bytes).hexdigest()
    if fresh_sha256 != manifest["seed_log_sha256"]:
        raise GateBAbort(
            f"arm {which}: seed log at {str(seed_log_path)!r} has sha256={fresh_sha256!r}, does "
            f"not match manifest's seed_log_sha256={manifest['seed_log_sha256']!r}"
        )
    try:
        seed_records = verify_seed_log(str(seed_log_path), manifest["seed_base"], manifest["n_rows"])
    except SeedLogError as exc:
        raise GateBAbort(f"arm {which}: seed-log verification failed: {exc}") from exc
    if len(seed_records) != manifest["seed_log_n_lines"]:
        raise GateBAbort(
            f"arm {which}: verified {len(seed_records)} seed-log record(s), but manifest claims "
            f"seed_log_n_lines={manifest['seed_log_n_lines']!r}"
        )


def _assert_rows_bind_to_holdout_teams(rows: list[dict], holdout_teams: dict, which: str) -> None:
    """Rev. 14 fix (§1m, third review round P1): a structurally-valid holdout_teams mapping is
    still just an ASSERTION until checked against what the rows themselves actually played.
    opp_team_path/opp_team_hash are the row-level ground truth -- Task 9's own _capture closure
    stamps them from the real per-battle key and the real sealed content hash -- so
    holdout_teams must agree with THAT, not the other way around. Requires every row to resolve
    to one of the declared six teams by path AND by hash, and every declared team to actually
    appear at least once."""
    allowed_paths = {entry["team_path"] for entry in holdout_teams.values()}
    path_to_team_id = {entry["team_path"]: team_id for team_id, entry in holdout_teams.items()}
    seen_paths = set()
    for i, row in enumerate(rows):
        opp_team_path = row["opp_team_path"]
        if opp_team_path not in allowed_paths:
            raise GateBAbort(
                f"arm {which}: row {i} has opp_team_path={opp_team_path!r}, not one of the six "
                "teams declared in holdout_teams"
            )
        team_id = path_to_team_id[opp_team_path]
        expected_hash = holdout_teams[team_id]["content_hash"]
        if row["opp_team_hash"] != expected_hash:
            raise GateBAbort(
                f"arm {which}: row {i} (team {team_id!r}) has "
                f"opp_team_hash={row['opp_team_hash']!r}, does not match holdout_teams's "
                f"content_hash={expected_hash!r} for this team"
            )
        seen_paths.add(opp_team_path)
    missing_teams = allowed_paths - seen_paths
    if missing_teams:
        missing_ids = sorted(path_to_team_id[p] for p in missing_teams)
        raise GateBAbort(
            f"arm {which}: holdout_teams declares team(s) {missing_ids} that never appear in "
            "rows -- manifest and rows.jsonl do not agree on which teams were actually played"
        )


def _assert_rows_match_manifest(rows: list[dict], manifest: dict, which: str) -> None:
    """F3 fix (Rev. 6): every downstream check in combine_strength_holdout_arms -- the two
    upstream-verdict checks, the ledger entry, the published verdict.json -- trusts
    manifest_a's identity fields (candidate_identity, git_sha, config_hash, ...) without ever
    proving they actually describe the rows sitting next to it. An arm directory assembled from
    two different runs (a stale or swapped arm_manifest.json) would pass every existing check
    silently. Never trust the pairing of a manifest with a rows.jsonl just because they share a
    directory -- prove it, the same way this plan already refuses to trust an upstream verdict's
    opaque candidate_identity alone (Task 7).

    NF1 fix (Rev. 7): a malformed or truncated manifest/row -- exactly the kind of bad input
    this function exists to catch -- must never crash it with a raw KeyError instead of
    producing the GateBAbort it was written to produce. Every expected key is checked for
    presence FIRST, before any indexed access.

    Rev. 14 fix (§1m, third review round P1): presence and internal shape are not enough for
    holdout_teams specifically -- it is validated structurally (_validate_holdout_teams_mapping)
    and then bound to what these SAME rows actually contain
    (_assert_rows_bind_to_holdout_teams), both before the scalar per-field checks below, so a
    manifest that lies about which teams were played is caught here, not three call sites
    downstream where the leakage/disjointness guards would have silently trusted it.

    Rev. 15 fix (§1n, Task-3-review P1 #1): the same standard now applies to
    stratum/platform_attestation/date_stratum_id (_validate_stratum_fields) -- presence via
    _MANIFEST_REQUIRED_KEYS, closed-form validity (unknown stratum, non-string/empty attestation
    or date-stratum id) here, before combine_strength_holdout_arms ever compares the two arms'
    values against each other."""
    missing_manifest_keys = set(_MANIFEST_REQUIRED_KEYS) - set(manifest)
    if missing_manifest_keys:
        raise GateBAbort(
            f"arm {which}: manifest is missing required key(s): {sorted(missing_manifest_keys)} "
            "-- malformed or truncated arm_manifest.json"
        )
    _validate_holdout_teams_mapping(manifest["holdout_teams"], which)
    _validate_stratum_fields(manifest, which)
    _validate_seed_proof_fields(manifest, which)
    for i, row in enumerate(rows):
        missing_row_keys = (
            set(_ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK) | set(_ROW_REQUIRED_KEYS_FOR_TEAM_BINDING)
        ) - set(row)
        if missing_row_keys:
            raise GateBAbort(
                f"arm {which}: row {i} is missing required key(s): {sorted(missing_row_keys)} "
                "-- panel_hash in particular is NULLABLE per result_jsonl's own schema, so "
                "validate_battle_row alone does not guarantee it is present here"
            )

    if len(rows) != manifest["n_rows"]:
        raise GateBAbort(
            f"arm {which}: manifest claims n_rows={manifest['n_rows']!r} but rows.jsonl has "
            f"{len(rows)} row(s) -- manifest and rows.jsonl do not belong together"
        )
    for field in _ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK:
        mismatched = sorted({row[field] for row in rows if row[field] != manifest[field]})
        if mismatched:
            raise GateBAbort(
                f"arm {which}: row field {field!r} disagrees with the manifest's "
                f"{field}={manifest[field]!r} (found: {mismatched}) -- manifest and rows.jsonl "
                f"do not belong together"
            )
    _assert_rows_bind_to_holdout_teams(rows, manifest["holdout_teams"], which)
    fresh_identity = make_candidate_identity(
        hero_agent=manifest["hero_agent"], git_sha=manifest["git_sha"], config_hash=manifest["config_hash"],
    )
    if fresh_identity != manifest["candidate_identity"]:
        raise GateBAbort(
            f"arm {which}: manifest's candidate_identity={manifest['candidate_identity']!r} "
            f"does not match the identity re-derived from its own hero_agent/git_sha/config_hash "
            f"({fresh_identity!r}) -- the manifest is internally inconsistent"
        )


_ROW_REQUIRED_KEYS_FOR_SCHEDULE_BINDING = ("seed_index", "opp_policy")
# Task-10 second review round, P1: the fields that make a row the battle its key scheduled, all
# of them re-derivable here from the manifest alone -- so a value is never merely "present and
# consistent", it is the one canonical value.
_ROW_REQUIRED_KEYS_FOR_CANONICAL_IDENTITY = (
    "seed", "battle_id", "format_id", "config_id", "run_id", "hero_team_path", "dirty",
)


def _assert_rows_cover_canonical_schedule(rows: list[dict], manifest: dict, which: str) -> None:
    """Task-10 review-fix, P1 #1: an arm must be the WHOLE canonical 180-battle-key schedule, and
    every row must be one of its keys.

    Before this fix nothing in the combiner ever rebuilt the schedule. ``n_rows`` was only ever
    compared against ``len(rows)`` (self-consistent by construction for a truncated arm) and
    ``schedule_hash`` was compared row-vs-manifest -- also self-consistent, because the writer
    stamps the same string on both. Two *matching*, *internally consistent*, 12-row arms
    therefore combined to a published "strength" verdict over 12 battles, and the fixtures that
    were supposed to prove otherwise were themselves 12-row. A short or reshaped arm is not a
    weaker strength result, it is not a strength result at all, so this is fail-closed.

    The rebuild is the same one Task 9's ``_assert_schedule_is_genuine`` performs on the write
    side, driven here from what the arm itself recorded: its own six team_ids, its own
    panel_hash, its own seed_base. ``seed_base`` is checked separately against the pinned
    namespace FIRST, for the reason Task 9 documents at its own call site -- feeding a forged
    seed_base into the rebuild and then comparing against that same forged value proves nothing.
    """
    if manifest["seed_base"] != STRENGTH_HOLDOUT_SEED_BASE:
        raise GateBAbort(
            f"arm {which}: manifest's seed_base={manifest['seed_base']!r} != the pinned seed "
            f"namespace {STRENGTH_HOLDOUT_SEED_BASE!r} -- refusing an unpinned seed namespace"
        )
    try:
        schedule = build_strength_holdout_schedule(
            holdout_team_ids=sorted(manifest["holdout_teams"]),
            panel_hash=manifest["panel_hash"], seed_base=manifest["seed_base"],
        )
    except ValueError as exc:
        raise GateBAbort(
            f"arm {which}: its own holdout_teams/panel_hash/seed_base do not rebuild a genuine "
            f"canonical strength-holdout schedule: {exc}"
        ) from exc
    if schedule.schedule_hash != manifest["schedule_hash"]:
        raise GateBAbort(
            f"arm {which}: manifest's schedule_hash={manifest['schedule_hash']!r} is not the "
            f"canonical rebuild from its own team_ids/panel_hash/seed_base "
            f"({schedule.schedule_hash!r}) -- refusing a forged or stale schedule label"
        )
    if len(rows) != len(schedule.battle_keys):
        raise GateBAbort(
            f"arm {which}: has {len(rows)} row(s) but the canonical schedule has "
            f"{len(schedule.battle_keys)} battle key(s) -- a partial arm is not a strength result"
        )
    expected = {
        (key.seed_index, key.opponent_policy, f"{HOLDOUT_TEAMS_DIR}{key.holdout_team_id}.txt")
        for key in schedule.battle_keys
    }
    played = []
    for i, row in enumerate(rows):
        missing = set(_ROW_REQUIRED_KEYS_FOR_SCHEDULE_BINDING) - set(row)
        if missing:
            raise GateBAbort(
                f"arm {which}: row {i} is missing required key(s): {sorted(missing)} -- every row "
                "must identify the canonical battle key it played"
            )
        played.append((row["seed_index"], row["opp_policy"], row["opp_team_path"]))
    if len(set(played)) != len(played):
        raise GateBAbort(
            f"arm {which}: two or more rows claim the SAME canonical battle key -- one battle key "
            "must be played exactly once"
        )
    if set(played) != expected:
        unexpected = sorted(set(played) - expected)[:3]
        unplayed = sorted(expected - set(played))[:3]
        raise GateBAbort(
            f"arm {which}: its rows do not cover the canonical schedule exactly once -- "
            f"battle key(s) played but not scheduled: {unexpected}; scheduled but not played: "
            f"{unplayed}"
        )

    # Task-10 second review round, P1: covering the (seed_index, opp_policy, opp_team_path) grid
    # says the right SLOTS are present; it says nothing about whether the result in each slot is
    # the battle that slot scheduled. seeds.jsonl proves the canonical seeds exist, but nothing
    # tied the ROWS to those seeds -- so two arms could carry identical, uniformly wrong seeds,
    # battle_ids, format, agent or hero team and still pair cleanly (pair_runs only notices
    # variance WITHIN an arm, which uniform corruption does not produce). Every field below is
    # re-derived here from the manifest and the canonical key, never merely compared for internal
    # consistency.
    keys_by_index = {key.seed_index: key for key in schedule.battle_keys}
    expected_run_id = f"{manifest['candidate_identity']}-{manifest['hero_agent']}"
    for i, row in enumerate(rows):
        missing = set(_ROW_REQUIRED_KEYS_FOR_CANONICAL_IDENTITY) - set(row)
        if missing:
            raise GateBAbort(
                f"arm {which}: row {i} is missing required key(s): {sorted(missing)} -- every row "
                "must carry the full canonical battle identity"
            )
        key = keys_by_index[row["seed_index"]]
        expected_seed = derive_battle_seed(manifest["seed_base"], key.seed_index)
        for field, expected_value in (
            ("seed", expected_seed),
            ("battle_id", make_battle_id(manifest["schedule_hash"], key.seed_index, expected_seed)),
            ("format_id", STRENGTH_HOLDOUT_FORMAT_ID),
            ("config_id", manifest["hero_agent"]),
            ("run_id", expected_run_id),
            ("hero_team_path", STRENGTH_HOLDOUT_HERO_TEAM_PATH),
        ):
            if row[field] != expected_value:
                raise GateBAbort(
                    f"arm {which}: row {i} (seed_index {key.seed_index}) has "
                    f"{field}={row[field]!r}, but the canonical battle key derives "
                    f"{field}={expected_value!r} -- this row is not the battle its key scheduled"
                )
        # `is not False` on purpose, not `if row["dirty"]`: a truthy-but-not-True value (or a
        # string "false") must fail here rather than be quietly accepted as clean.
        if row["dirty"] is not False:
            raise GateBAbort(
                f"arm {which}: row {i} (seed_index {key.seed_index}) has dirty={row['dirty']!r} "
                "-- a battle played from a dirty tree can never be part of sealed evidence"
            )


def _derive_species_from_sealed_files(holdout_teams: dict, teams_root: str) -> tuple[dict, dict]:
    """Task-10 review-fix, P1 #3: derive BOTH sides of the near-duplicate comparison from real
    sealed ``.packed`` content instead of trusting caller-supplied species mappings.

    ``holdout_candidate_species`` and ``reference_species`` were plain caller assertions: combine
    only ever checked that the candidate mapping's KEY SET matched the six scheduled teams, never
    that any listed species had anything to do with the team it was filed under. A caller could
    hand over six species lists that trivially overlap nothing and the guard would "pass".
    ``near_duplicate.load_team_species`` -- which derives species from a team's real packed file,
    and has its own tests -- existed already but had no production call site anywhere.

    The candidate side is keyed off ``manifest_a["holdout_teams"]``, which by this point is
    already proven to describe the rows actually played; the reference side is the pinned
    ``CANONICAL_REFERENCE_TEAM_PATHS``, not caller input. Any unreadable or malformed team file
    is a fail-closed abort -- a silently smaller comparison set would quietly weaken the guard.
    """
    try:
        candidates = {
            team_id: load_team_species(holdout_teams[team_id]["team_path"], teams_root=teams_root)
            for team_id in sorted(holdout_teams)
        }
        references = {
            ref_id: load_team_species(CANONICAL_REFERENCE_TEAM_PATHS[ref_id], teams_root=teams_root)
            for ref_id in sorted(CANONICAL_REFERENCE_TEAM_PATHS)
        }
    except ValueError as exc:
        raise GateBAbort(
            f"cannot derive team species from the real sealed team files under "
            f"teams_root={teams_root!r}: {exc}"
        ) from exc
    return candidates, references


@contextmanager
def _ledger_lock(ledger_path: str):
    """Task-10 review-fix, P2 #5: make the held-out access budget's check-then-reserve atomic.

    ``check_access`` reads the ledger early and ``append_entry`` writes it much later, with the
    whole guard/pairing/verdict computation in between. Two combines started concurrently could
    both observe a free budget in that window and both go on to append and publish -- exactly the
    held-out-data-reuse the ledger exists to prevent, and invisible afterwards because both
    entries look legitimate. An exclusive ``O_CREAT|O_EXCL`` lock file held across the entire
    section closes it: the second process cannot even begin.

    Deliberately fail-closed with no timeout or steal: a stale lock (left by a crashed combine)
    blocks further runs until a human removes it. For a once-per-candidate held-out gate that is
    the correct trade -- silently breaking a lock is how the budget gets spent twice.
    """
    lock_path = ledger_path + ".lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise GateBAbort(
            f"ledger lock {lock_path!r} is already held -- another combine is inside its "
            "held-out access-budget section, or a previous run crashed and left the lock behind "
            "(remove it by hand after confirming no combine is running)"
        ) from exc
    except OSError as exc:
        raise GateBAbort(f"cannot acquire ledger lock {lock_path!r}: {exc}") from exc
    try:
        try:
            os.write(fd, f"pid={os.getpid()}\n".encode("utf-8"))
        finally:
            os.close(fd)
        yield
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def _normalized_ledger_justification(value: str | None) -> str | None:
    """Normalise a caller-supplied held-out justification to either a real reason or ``None``.

    This is a BYPASS of a fail-closed budget, so the blank cases matter: ``check_access`` only
    tests ``justification is not None``, which means ``""`` and ``"   "`` would sail straight past
    the one-attempt budget. Normalising blank-to-``None`` HERE -- before either ``check_access``
    call and before the ledger entry is built -- is what makes an absent, empty or whitespace-only
    justification behave exactly as before this parameter existed: budget enforced,
    ``AccessBudgetError`` raised.

    The returned value is used for BOTH ``check_access`` call sites AND the appended entry, so the
    reason that authorised the bypass is always the reason recorded in the audit trail; they cannot
    diverge. Non-strings are refused rather than coerced -- a stray non-string here means a caller
    wired something unintended into a guard bypass, which must be loud, not silently truthy.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise GateBAbort(
            f"ledger_justification must be a string or None, got {type(value).__name__} -- "
            "refusing to bypass the held-out access budget on a non-string value"
        )
    stripped = value.strip()
    return stripped or None


def combine_strength_holdout_arms(
    *, arm_a_dir: str, arm_b_dir: str, out_dir: str,
    i8d_verdict_path: str, coverage_verdict_path: str,
    holdout_content_hashes: dict[str, str],
    baseline_manifest_path: str = "config/eval/baselines/champions-strength-holdout-v0.json",
    repo_root: str = ".",
    stratum_env_override: str | None = None,
    ledger_path: str = "config/eval/heldout_ledger.jsonl",
    teams_root: str = ".",
    ledger_justification: str | None = None,
) -> dict:
    """Reads both already-published arms, verifies the two upstream gates, checks baseline
    drift, pairs the arms, runs EVERY guard, renders the verdict via the real report.py
    pipeline, and publishes the full evidence bundle atomically.

    i8d_verdict_path/coverage_verdict_path are REQUIRED and non-empty -- Gate B may only run
    after an I8-D PASS and a Coverage PASS on this candidate (DESIGN sec 5); there is no
    optional/skip path (Rev. 3 P1 fix -- Rev. 2's `= ""` defaults let a caller silently omit
    both checks).

    holdout_content_hashes/reference_species are REQUIRED and must be non-empty (Rev. 4 P2 fix
    -- Rev. 3 allowed a legitimate-looking `{}` here, but nothing distinguished a deliberate
    test scenario from a production caller that just never wired real data through; an empty
    mapping makes the disjointness/leakage/near-duplicate guards vacuous in EITHER case, so
    production now refuses it unconditionally. Tests use small non-empty fake maps instead
    of `{}` -- see Task 10's test fixtures). NON-EMPTY alone does not prove
    holdout_content_hashes covers every scheduled team WITH the right hashes, though -- Rev. 13
    (§1l) closed the key-set-only version of this gap (a partial map) but not the value-wrong
    version (right keys, wrong hash for one), and neither Rev. 12 nor Rev. 13 checked it against
    the rows actually played, only against a bare team_id list the manifest itself never proved.
    Rev. 14 (§1m) closes both: `holdout_content_hashes` is checked for full dict equality
    (keys AND values) against each arm's own `holdout_teams` mapping (Task 9), which
    `_assert_rows_match_manifest` has already bound to that arm's OWN rows
    (`_assert_rows_bind_to_holdout_teams`) before this function ever reaches this check --
    so by the time the leakage guard's `team_ids=` argument below is built, it is provably the
    real six teams this schedule played, not merely whatever six labels a manifest or a caller
    happened to assert.

    holdout_candidate_species/reference_species (Rev. 18 fix, §1q): two GENUINELY SEPARATE
    mappings, never one dict doing double duty as both. Before this fix, the near-duplicate loop
    below iterated `reference_species` to get BOTH the six holdout candidates AND the reference
    set to compare them against -- passing `reference_teams=reference_species` (the SAME dict)
    for every team drawn FROM that same dict meant every team was compared against a reference
    set that included itself, and there was no way to supply the six holdout teams' OWN species
    at all (only their content hashes/paths were ever threaded through). `holdout_candidate_species`
    carries the six holdout teams' species sets (DESIGN sec 3.3's "holdout team" side);
    `reference_species` carries the nine existing Champions-M-A teams' species sets (its "touched
    or coverage team" side, §16 item 5) -- disjoint by construction now, not merely by caller
    discipline. `holdout_candidate_species`'s key set is checked against
    `manifest_a["holdout_teams"]` (below) exactly like `holdout_content_hashes` already is, so a
    caller cannot silently supply species for the wrong team_ids either.

    Candidate identity note (Rev. 3 P1 fix): arm A (hero_agent='heuristic') IS the shared
    candidate identity checked against I8-D/Coverage (DESIGN sec 5: "Candidate A is that shared
    candidate; Baseline B is the reference, not a separately-gated candidate"). Arm B
    (hero_agent='max_damage') is NEVER required to share candidate_identity with arm A --
    make_candidate_identity hashes hero_agent itself, so the two arms' identities differ by
    construction for every genuine run. What arm B must share with arm A is git_sha (same
    commit) and schedule_hash/panel_hash/seed_base (same battle conditions) -- checked explicitly
    below, and re-verified independently by pair_runs's own cross-run checks.

    stratum_env_override (Rev. 15 fix, §1n): NOT a source of truth -- this function never calls
    detect_stratum() itself, since the machine running combine_strength_holdout_arms need not be
    either arm's play machine. If given, it is an optional caller EXPECTATION, checked against
    what the two arms' own manifests actually recorded (already proven to agree with each other by
    the arm-vs-arm loop below); a mismatch aborts as a contradictory override, before the arms are
    ever compared to each other for pooling.

    Order: cheapest checks first, matching coverage_runner.py."""
    if not i8d_verdict_path:
        raise GateBAbort("i8d_verdict_path is required and must be non-empty -- Gate B may only run after an I8-D PASS on this candidate")
    if not coverage_verdict_path:
        raise GateBAbort("coverage_verdict_path is required and must be non-empty -- Gate B may only run after a Coverage PASS on this candidate")
    if not holdout_content_hashes:
        raise GateBAbort("holdout_content_hashes must be non-empty -- an empty mapping makes the disjointness/leakage guards vacuous")

    rows_a, manifest_a = _read_arm(arm_a_dir)
    rows_b, manifest_b = _read_arm(arm_b_dir)
    _assert_rows_match_manifest(rows_a, manifest_a, "A")
    _assert_rows_match_manifest(rows_b, manifest_b, "B")
    # Task-10 review-fix, P1 #1: each arm must BE the canonical 180-battle-key schedule, rebuilt
    # from its own recorded team_ids/panel_hash/seed_base -- the manifest-vs-rows checks above are
    # all self-consistency checks and cannot detect a truncated or reshaped arm on their own.
    _assert_rows_cover_canonical_schedule(rows_a, manifest_a, "A")
    _assert_rows_cover_canonical_schedule(rows_b, manifest_b, "B")
    # Rev. 19 fix (Task 9 review-fix sync, §1r): re-verify each arm's PUBLISHED seed log fresh,
    # before pairing or any verdict -- both arms independently, never relying on matching
    # manifest values alone (a doctored manifest could claim agreement without either seed log
    # genuinely verifying).
    _assert_seed_artifact_verified(arm_a_dir, manifest_a, "A")
    _assert_seed_artifact_verified(arm_b_dir, manifest_b, "B")

    if manifest_a["hero_agent"] != "heuristic":
        raise GateBAbort(f"arm A must be hero_agent='heuristic' (Candidate A per DESIGN sec 3.2), got {manifest_a['hero_agent']!r}")
    if manifest_b["hero_agent"] != "max_damage":
        raise GateBAbort(f"arm B must be hero_agent='max_damage' (Baseline B per DESIGN sec 3.2), got {manifest_b['hero_agent']!r}")
    if manifest_a["git_sha"] != manifest_b["git_sha"]:
        raise GateBAbort("arms disagree on git_sha -- they were not played on the same commit")
    # Task-10 review-fix, P1 #2: bind the COMBINE to the same commit the arms were played on,
    # before any repo-dependent guard runs. verify_baseline reads the working tree,
    # assert_no_holdout_leakage reads committed blobs via `git show HEAD:<path>`, and the
    # published bundle is stamped with manifest_a["git_sha"] -- so combining from a dirty tree, or
    # from a checkout sitting on a different commit, silently evaluates one commit's content and
    # labels the evidence with another's. Both conditions are technical aborts, not verdicts.
    if _git_is_dirty(cwd=repo_root):
        raise GateBAbort(
            f"refusing to combine from a dirty working tree at repo_root={repo_root!r} -- the "
            "baseline/leakage guards read this checkout, so uncommitted changes would be "
            "evaluated but never recorded in the published evidence"
        )
    head_sha = _git_sha(cwd=repo_root)
    if head_sha != manifest_a["git_sha"]:
        raise GateBAbort(
            f"HEAD at repo_root={repo_root!r} is {head_sha!r} but both arms were played at "
            f"git_sha={manifest_a['git_sha']!r} -- the repo-dependent guards would run against a "
            "different commit than the one this evidence claims"
        )
    # Rev. 15 fix (§1n, Task-3-review P1 #2): date_stratum_id added -- "different... date-strata
    # must abort" (stratum ITSELF is compared separately below, via assert_no_cross_stratum_
    # pooling, so its StrataPoolingError stays distinct from this loop's GateBAbort, matching the
    # exception-audit table's existing, deliberate separation of guard-specific exception types
    # from this trust-chain's single GateBAbort class -- see the comment above the upstream-
    # verdict try/except further down). platform_attestation is NOT compared here: two arms
    # legitimately played on the same physical box can report different platform.platform()
    # strings (e.g. an OS patch between arm A and arm B's runs) without that meaning anything --
    # only its non-empty presence is required (_validate_stratum_fields), not byte-equality.
    # Rev. 19 fix (Task 9 review-fix sync, §1r): calc_backend added -- oneshot vs persistent
    # produce the SAME config_hash/candidate_identity (make_config_hash's manifest does not
    # include calc_backend), so without this check two arms could silently run under different
    # backends while every OTHER identity field still matched.
    # Task-10 review-fix, P1 #1 (ordering consequence): holdout_teams is compared FIRST. Now that
    # schedule_hash is the canonical rebuild over the arm's own team_ids, two arms that played
    # different team sets necessarily disagree on schedule_hash too -- reporting the derived
    # symptom before the cause would be strictly less useful than naming the team-set mismatch.
    for field in ("holdout_teams", "schedule_hash", "panel_hash", "seed_base", "date_stratum_id", "calc_backend", "pythonhashseed"):
        if manifest_a[field] != manifest_b[field]:
            raise GateBAbort(f"arms disagree on {field} -- they were not played under the same battle conditions")

    # Rev. 14 fix (§1m, third review round P1): Rev. 13's key-set-only check missed a caller
    # supplying every right team_id with a WRONG hash for one of them. manifest_a["holdout_teams"]
    # is now a real per-team {team_path, content_hash} mapping, independently proven (just above,
    # via _assert_rows_match_manifest -> _assert_rows_bind_to_holdout_teams) to describe what
    # THIS arm's rows actually played -- and proven identical to manifest_b's by the loop just
    # above. Require FULL dict equality (keys AND values) against holdout_content_hashes, not a
    # key-set check -- missing, extra, or value-wrong team_ids all abort here, before any guard
    # below ever runs.
    expected_hashes = {team_id: entry["content_hash"] for team_id, entry in manifest_a["holdout_teams"].items()}
    if holdout_content_hashes != expected_hashes:
        raise GateBAbort(
            "holdout_content_hashes does not match the six teams' content hashes this schedule "
            f"actually played (schedule: {expected_hashes}, holdout_content_hashes: "
            f"{holdout_content_hashes}) -- the leakage/disjointness guards must see every "
            "scheduled team with its real hash, not a subset or a wrong value"
        )
    # Task-10 review-fix, P1 #3: Rev. 18's key-set check on a caller-supplied
    # holdout_candidate_species is gone -- there is no caller-supplied species mapping to check
    # any more. Both sides of the near-duplicate comparison are derived below from the real
    # sealed .packed files, the candidate side keyed off manifest_a["holdout_teams"], which the
    # checks above have already bound to the rows actually played.

    # NF2 fix (Rev. 7): verify_i8d_verdict_artifact/verify_coverage_verdict_artifact raise
    # StrengthHoldoutRunError, not GateBAbort -- this plan's own documentation (§1a, and the
    # comment on the PairingError fix below) claimed the CLI catches
    # `except (GateBAbort, StrengthHoldoutRunError)`, but the actual CLI handlers (Task 11) only
    # ever caught `GateBAbort`. Rather than widen the CLI's except tuple to two abort classes,
    # normalize at the source: this is the ONLY place StrengthHoldoutRunError can cross into
    # combine_strength_holdout_arms, so catching it here folds it into GateBAbort -- the same
    # choice already made below for BaselineDriftError, PairingError, and LedgerError, and in
    # _read_arm above for ResultRowError/OSError/UnicodeDecodeError/json.JSONDecodeError. This is
    # NOT true of every guard failure in this function, though:
    # check_access/assert_disjoint_from_coverage/assert_no_holdout_leakage/
    # assert_no_cross_stratum_pooling below are deliberately left UNwrapped -- their
    # AccessBudgetError/HoldoutNotDisjointError/LeakageDriftError/StrataPoolingError/
    # UnattestedStratumError propagate raw by design (see the exception-audit table, §1f), not
    # by oversight. "One abort class" describes the upstream-verdict/pairing/ledger/row-schema
    # trust chain specifically, not this whole function's entire exception surface -- an earlier
    # draft of this exact comment claimed the broader, false version of this sentence.
    # Combine-root fix (candidate a7d5330, Phase-5 combine): the I8-D/coverage canonical schedules
    # the two verifiers rebuild live under showdown_bot/ (their panel team paths are relative to a
    # teams_root of "showdown_bot"), whereas Gate B's own teams_root/repo_root is the repo root
    # (holdout/baseline/leakage/near-duplicate paths carry the showdown_bot/ prefix themselves). The
    # live combine handed the verifiers its Gate B teams_root ("."), so build_i8d_canonical_schedule/
    # build_coverage_live_schedule could never find the I8-D/coverage team files and BOTH valid
    # upstream PASSes failed to verify. Derive the upstream root canonically from the existing
    # repo_root -- never a CWD-relative literal, never a new CLI flag -- and hand ONLY that to the two
    # upstream verifiers. Every Gate B-own check below keeps the unchanged teams_root/repo_root.
    upstream_teams_root = str(Path(repo_root) / "showdown_bot")
    try:
        # Rev. 19 fix (Task 9 review-fix sync, §1r): calc_backend is now the manifest-bound value
        # Task 9 actually derived for this run (arm A and arm B already proven equal above) --
        # never the hardcoded literal "oneshot", which would silently pass an unverified backend
        # claim through to both upstream verifiers regardless of what the run actually used.
        verify_i8d_verdict_artifact(
            verdict_path=i8d_verdict_path, teams_root=upstream_teams_root,
            candidate_identity=manifest_a["candidate_identity"], git_sha=manifest_a["git_sha"],
            config_hash=manifest_a["config_hash"], hero_agent=manifest_a["hero_agent"],
            calc_backend=manifest_a["calc_backend"],
        )
        verify_coverage_verdict_artifact(
            verdict_path=coverage_verdict_path, teams_root=upstream_teams_root,
            candidate_identity=manifest_a["candidate_identity"], git_sha=manifest_a["git_sha"],
            config_hash=manifest_a["config_hash"], hero_agent=manifest_a["hero_agent"],
            calc_backend=manifest_a["calc_backend"],
        )
    except StrengthHoldoutRunError as exc:
        raise GateBAbort(f"upstream verdict verification failed: {exc}") from exc

    # Early, UNLOCKED budget check: fail fast, before 180 rows of pairing/verdict work, exactly as
    # the "cheapest checks first" ordering intends. Task-10 review-fix, P2 #5: this one is an
    # optimisation only -- it is NOT the authoritative check any more. The check that actually
    # gates the reservation runs again under the ledger lock, immediately before append_entry.
    # Normalised ONCE, here, then reused for both check_access sites and the ledger entry below --
    # the reason that authorises the bypass is by construction the reason that gets recorded.
    justification = _normalized_ledger_justification(ledger_justification)
    check_access(read_ledger(ledger_path) if os.path.exists(ledger_path) else [], manifest_a["config_hash"], justification=justification)

    # Baseline-drift guard. Task 13 step 2 (spec Amendment A1.3): Gate B uses its OWN static
    # baseline contract, NOT the generic T6 result-baseline. The generic load_baseline/
    # verify_baseline require reference_jsonl/reference_sha256 and a loadable YAML dev_schedule_path
    # -- none of which Gate B can have (a result file cannot predate its run; the schedule is
    # code-generated) -- so wiring the generic verifier here would mean this guard could only ever
    # pass against a faked result file. load_strength_holdout_baseline enforces the closed static
    # schema; verify_strength_holdout_baseline re-derives panel/hero/opponent hashes, the rebuilt
    # canonical schedule hash, and the server/seed pins from the current checkout. Both a schema
    # violation (BaselineError) and drift (BaselineDriftError) become a clean GateBAbort here,
    # before pairing, the ledger reservation, or any publish.
    try:
        baseline = load_strength_holdout_baseline(baseline_manifest_path)
        verify_strength_holdout_baseline(baseline, repo_root=repo_root, teams_root=teams_root)
    except BaselineError as exc:
        raise GateBAbort(f"baseline drift: {exc}") from exc
    # Review-fix (Step 2): both arms must have run under the baseline's pinned PYTHONHASHSEED. The
    # arm-vs-arm loop above already proved the two arms agree with each other; this binds that
    # shared value to the static baseline as well, so a run under a different (but internally
    # consistent) seed cannot slip through.
    if manifest_a["pythonhashseed"] != baseline["pythonhashseed"]:
        raise GateBAbort(
            f"baseline drift: arms ran under pythonhashseed={manifest_a['pythonhashseed']!r} but "
            f"the baseline pins {baseline['pythonhashseed']!r}"
        )

    assert_disjoint_from_coverage(holdout_content_hashes)
    assert_no_holdout_leakage(
        identifiers=list(holdout_content_hashes.values()) + list(holdout_content_hashes.keys()),
        # Rev. 12 P1 #2 fix (§1k): the leakage guard's content leg now reads each sealed team's
        # OWN committed .txt/.packed blob directly (scan_for_raw_payload_leakage), keyed by
        # team_id -- it no longer takes a hash mapping. holdout_content_hashes itself is
        # unchanged above (still required, still feeds assert_disjoint_from_coverage).
        # Rev. 14 fix (§1m): team_ids now comes from manifest_a["holdout_teams"] -- the VALIDATED,
        # ROW-BOUND mapping (_assert_rows_match_manifest, above) -- not from
        # holdout_content_hashes.keys() directly. By this point the two are already proven
        # dict-equal (the check just above), so the VALUES are identical either way; sourcing
        # from the bound manifest data is the structurally-safer choice regardless of any future
        # reordering of these checks.
        team_ids=sorted(manifest_a["holdout_teams"]),
        teams_root=teams_root,  # N3 fix: was silently hardcoded to "." inside the scan before
    )
    # Rev. 18 fix (§1q): the pre-Rev.-18 version of this loop iterated reference_species for
    # BOTH the candidates AND the reference set (`for team_id, species in
    # reference_species.items(): find_near_duplicate_flags(..., reference_teams=reference_species)`)
    # -- every team was compared against a reference set that included itself, and there was no
    # way to supply the six holdout teams' own species at all. holdout_candidate_species and
    # reference_species are now two genuinely separate mappings (validated above); iterating the
    # CANDIDATES and comparing each against the REFERENCE set is the correct DESIGN sec 3.3
    # geometry (six holdout teams checked against nine touched/coverage teams), and
    # find_near_duplicate_flags's own self-exclusion (Task 4) is defense in depth on top of that,
    # not the only thing preventing self-comparison.
    # Rev. 18 fix (§1q, self-found while wiring this loop, same pass): find_near_duplicate_flags
    # (Task 4) raises ValueError for malformed species data (an empty per-team species list, on
    # either the candidate or the reference side) -- the key-set checks above prove
    # holdout_candidate_species/reference_species name the RIGHT teams, but never validated that
    # each team's OWN species list is non-empty. Left unwrapped, a malformed entry would escape
    # combine_strength_holdout_arms as a raw ValueError, uncaught by the CLI (which only ever
    # catches GateBAbort, Task 11) -- the same "new guard, new raw exception" shape NF1/NF3 fixed
    # for _assert_rows_match_manifest/BattleResultWriter.write, applied here on introduction
    # rather than found later.
    # Task-10 review-fix, P1 #3: both mappings are now DERIVED from the real sealed team files
    # (see _derive_species_from_sealed_files) rather than taken from the caller, so the geometry
    # below is unchanged but the DATA is no longer an assertion anyone could shape at will.
    holdout_candidate_species, reference_species = _derive_species_from_sealed_files(
        manifest_a["holdout_teams"], teams_root,
    )
    try:
        near_dup_flags = []
        for team_id in sorted(holdout_candidate_species):
            near_dup_flags.extend(find_near_duplicate_flags(
                candidate_team_id=team_id, candidate_species=holdout_candidate_species[team_id],
                reference_teams=reference_species,
            ))
    except ValueError as exc:
        raise GateBAbort(f"near-duplicate check failed on malformed species data: {exc}") from exc
    # DESIGN sec 3.3: manual-review flag, never an auto-abort -- always computed and recorded
    # in the published bundle below (payload["near_duplicate_flags"]), never silently dropped.

    # Rev. 15 fix (§1n, Task-3-review P1 #2/#3): the combiner must not RE-DETERMINE stratum from
    # its own machine -- detect_stratum() reflects whatever box happens to run
    # combine_strength_holdout_arms, which need not be either arm's PLAY machine. Each arm's own
    # manifest already carries what Task 9 (its own Rev. 15 fix) recorded at play time, already
    # proven present/well-formed by _validate_stratum_fields above; compare the two ACTUAL arm
    # records instead of a freshly-detected third value.
    #
    # stratum_env_override is repurposed accordingly: no longer a source of truth fed into
    # detect_stratum, it is now an optional caller-supplied EXPECTATION checked against what the
    # arms actually recorded. A caller who expects e.g. a Windows-stratum combine and gets
    # Kaggle-stratum arms (or the reverse) gets a clear "contradictory override" abort instead of
    # silently combining the wrong stratum's arms.
    if stratum_env_override is not None and stratum_env_override != manifest_a["stratum"]:
        raise GateBAbort(
            f"stratum_env_override={stratum_env_override!r} contradicts the arms' own recorded "
            f"stratum={manifest_a['stratum']!r} -- the override must match what the arms actually "
            "recorded, not silently force a different stratum onto them"
        )
    assert_no_cross_stratum_pooling([
        StratumRecord(stratum=manifest_a["stratum"], platform_string=manifest_a["platform_attestation"], output_dir=arm_a_dir),
        StratumRecord(stratum=manifest_b["stratum"], platform_string=manifest_b["platform_attestation"], output_dir=arm_b_dir),
    ])

    try:
        # "Zwei Reste" fix (Rev. 6): expected_rows=len(rows_a) was tautological -- true by
        # construction for A, and redundant with _assert_rows_match_manifest's own n_rows check
        # for B. manifest_a["n_rows"] is the independently-sourced expectation (now itself
        # proven to match rows_a by the check above), so RowCountError becomes reachable again.
        pairs = pair_runs(rows_a, rows_b, expected_rows=manifest_a["n_rows"])
    except PairingError as exc:
        # Rev. 4 P2 fix: pair_runs can raise several PairingError subclasses (MissingPairError,
        # RunMismatchError, SelfComparisonError, DuplicateRowError, PairSeedMismatchError,
        # RowCountError) -- Rev. 3 only caught MissingPairError, letting the others escape raw
        # (uncaught by the CLI, which only ever catches GateBAbort -- corrected, Rev. 7 NF2: this
        # comment previously and incorrectly claimed the CLI also caught StrengthHoldoutRunError).
        # Catch the base class so every pairing failure becomes a uniform, CLI-handled abort.
        raise GateBAbort(f"pairing failed: {exc}") from exc

    safety_pass = compute_safety_pass(rows_a, rows_b)
    verdict = render_strength_holdout_verdict(pairs, safety_pass=safety_pass)

    staging_dir = f"{out_dir}.staging"
    for label, p in (("output", out_dir), ("staging", staging_dir)):
        if os.path.exists(p):
            raise GateBAbort(f"{label} directory {p} already exists")
    os.makedirs(staging_dir)
    shutil.copytree(arm_a_dir, os.path.join(staging_dir, "arm_a"))
    shutil.copytree(arm_b_dir, os.path.join(staging_dir, "arm_b"))

    cells_a = _build_cells(rows_a, {})
    cells_b = _build_cells(rows_b, {})
    _write_json_atomic(os.path.join(staging_dir, "cells.json"), {
        "cells_a": cells_a, "cells_b": cells_b, "aggregates_a": _build_aggregates(cells_a),
        "aggregates_b": _build_aggregates(cells_b),
    })

    payload = {
        "verdict": verdict.verdict, "reasons": verdict.reasons, "n_discordant": verdict.n_discordant,
        "n_total": verdict.n_total, "delta": verdict.delta, "exact_p": verdict.exact_p,
        "strength_delta": verdict.strength_delta, "cell_flips": verdict.cell_flips,
        "safety_pass": safety_pass, "candidate_identity": manifest_a["candidate_identity"],
        "git_sha": manifest_a["git_sha"], "config_hash_a": manifest_a["config_hash"],
        "config_hash_b": manifest_b["config_hash"], "schedule_hash": manifest_a["schedule_hash"],
        "panel_hash": manifest_a["panel_hash"], "stratum": manifest_a["stratum"],
        "near_duplicate_flags": [asdict(f) for f in near_dup_flags],
        "report_banner": "HELD-OUT RUN -- these numbers must never inform tuning.",
    }
    # N2 fix: result_sha256 must hash the EXACT bytes that land on disk, not a second,
    # independently-formatted json.dumps call -- _write_json_atomic (i8d_runner.py:106-112)
    # writes `json.dumps(obj, sort_keys=True, indent=2) + "\n"`; hashing a differently-formatted
    # re-serialization (no indent, no trailing newline, default separators) produces a DIFFERENT
    # digest than `sha256sum verdict.json` on the published file, making the ledger's
    # result_sha256 field decorative rather than verifiable. Compute the canonical text ONCE and
    # write it directly (single source of truth) instead of calling _write_json_atomic
    # separately and trusting the two calls stay byte-identical.
    verdict_text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    result_sha256 = hashlib.sha256(verdict_text.encode("utf-8")).hexdigest()
    verdict_tmp = os.path.join(staging_dir, "verdict.json.tmp")
    with open(verdict_tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(verdict_text)
    os.replace(verdict_tmp, os.path.join(staging_dir, "verdict.json"))

    # F6 fix (Rev. 6): ledger entry BEFORE publish, not after. Deliberately asymmetric, not
    # arbitrary ordering: a ledger `run` entry with no published bundle is a visible, auditable
    # failure (check_access sees the attempt was recorded and correctly refuses a retry without
    # justification, even though this specific run produced no evidence -- the budget is spent
    # slightly too eagerly, but that failure is loud). A published bundle with NO ledger entry is
    # the opposite: silent, and lets a subsequent run against the same config_hash slip straight
    # past check_access's one-attempt budget unnoticed -- exactly the held-out-data-reuse path
    # the ledger exists to prevent. If append_entry raises (e.g. LedgerError on a malformed
    # entry), os.replace(staging_dir, out_dir) below must never run, so a failed ledger write can
    # never coexist with a "successful"-looking published bundle.
    #
    # Task-10 review-fix, P2 #5: the budget CHECK and the reservation it authorises now happen
    # inside one exclusive lock. The early check_access far above is only a fail-fast; on its own
    # it left a very wide window (all of the guard/pairing/verdict work) in which a second combine
    # could read the same still-empty ledger, conclude the budget was free, and append and publish
    # too -- two "first" held-out runs against the same config_hash, both looking legitimate
    # afterwards. Re-reading the ledger here, under the lock, is what makes the decision
    # authoritative; the publish stays inside the lock as well so a reservation can never be
    # observed without the bundle it belongs to being on its way.
    with _ledger_lock(ledger_path):
        check_access(
            read_ledger(ledger_path) if os.path.exists(ledger_path) else [],
            manifest_a["config_hash"], justification=justification,
        )
        try:
            append_entry(ledger_path, {
                "kind": "run", "date": date.today().isoformat(), "purpose": "champions-strength-holdout-v0",
                "panel_hash": manifest_a["panel_hash"], "schedule_hash": manifest_a["schedule_hash"],
                "git_sha": manifest_a["git_sha"], "config_hash": manifest_a["config_hash"],
                "result_sha256": result_sha256, "justification": justification,
            })
        except LedgerError as exc:
            raise GateBAbort(f"ledger append failed, refusing to publish: {exc}") from exc

        # Same Windows-retry-safe atomic publish as the arm, kept INSIDE the ledger lock so a
        # reservation is never observable without its bundle being on the way (F6 ordering intact).
        _atomic_publish_dir(staging_dir, out_dir)
    return payload

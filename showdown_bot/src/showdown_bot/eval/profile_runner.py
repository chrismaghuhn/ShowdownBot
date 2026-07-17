"""The I8 microprofile driver (I8-C): orchestration only.

It wires the already-merged machinery into one reproducible offline run and NOTHING ELSE. It
holds no second validator, hash recipe, serialiser, arm registry or scoring implementation --
each of those has exactly one home, and this module only calls it:

    arms + order      -> profile_arms.PROFILE_ARMS / arm_specs
    fixtures/session  -> profile_fixtures (the promoted, source-owned boards + ProfileSession)
    manifest          -> profile_manifest.build/write_profile_manifest
    canonical hash    -> decision_profile.profile_manifest_hash (via the shared encode)
    rows              -> decision_profile.DecisionProfileWriter (per-row validation on write)
    per-arm execution -> profile_harness.run_arm
    dataset gate      -> decision_profile.validate_decision_profile_dataset

There is no battle and no server here: the runner drives fixtures through the scoring path, the
same as the C3 proof, and every arm's calc backend is whatever that arm declares.

Two properties protect the evidential value of a published profile:

* **Locked provenance (public API).** :func:`run_microprofile` -- the ONLY entry the authorized
  script calls -- takes no session or fixture injection. It always measures the real promoted
  fixtures over the full design matrix, so a published directory can never carry fabricated
  counters or a fixture identity that was substituted at the seam. Tests drive the orchestration
  through the private :func:`_run_microprofile`, which is where the injection lives.
* **Complete-or-nothing (completeness gate).** A run publishes only if the finished dataset
  covers EVERY ``PROFILE_ARMS`` arm at exactly ``reps`` reps. A subset run -- however valid its
  rows -- is refused, so 'a final directory exists' means 'the whole matrix', not 'some subset
  that happened to validate'.

Atomic output
-------------
Rows and the manifest are written into a SIBLING ``<name>.staging`` directory; only after every
row has passed the per-row validator (on write), the finished dataset has passed the dataset
tier, AND the completeness gate has confirmed the full matrix is present, is the staging
directory renamed onto the final path -- one atomic move, on the same filesystem. Refusing to
overwrite an existing final directory, and removing the staging directory on any failure, keep a
partial or unvalidated result from ever being exposed.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from showdown_bot.eval import profile_fixtures
from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    DecisionProfileWriter,
    arm_by_id,
    profile_manifest_hash,
    validate_decision_profile_dataset,
)
from showdown_bot.eval.profile_arms import PROFILE_ARMS, arm_specs
from showdown_bot.eval.profile_harness import run_arm
from showdown_bot.eval.profile_manifest import build_profile_manifest, write_profile_manifest

MANIFEST_NAME = "profile_manifest.json"
ROWS_NAME = "profile.jsonl"


# The authorized run's provenance is FIXED, not caller-supplied. The fixtures embody Champions
# Reg-MA scored by the heuristic path, so the manifest's format/agent and every row's config_id
# must match what is actually measured. Locking them is the other half of provenance integrity:
# removing the session/fixture seams stopped fabricated COUNTERS; fixing these stops a fabricated
# LABEL -- e.g. recording format_id="gen9ou" while measuring the Champions boards.
_AGENT = "heuristic"
_CONFIG_ID = "champions-i8-microprofile"


def run_microprofile(out_dir, *, reps: int, log=None) -> dict:
    """Run the FULL microprofile matrix into ``out_dir`` and return the dataset-validation report.

    This is the authorized, provenance-locked entry point -- the ONLY one the executable script
    calls. It takes NO provenance inputs. Not the session or fixtures (which would let a caller
    fabricate the measured counters), and not the agent/format/config_id (which would let a caller
    record a LABEL that disagrees with the Champions Reg-MA heuristic fixtures actually measured).
    Everything is fixed to the real matrix and fixtures; the only inputs are where to write and how
    many reps.

    ``reps`` is REQUIRED and has no default -- it is a run parameter (profile_arms.arm_specs). The
    reusable orchestration accepts any positive value so tests can run cheaply; only the executable
    entrypoint pins the authorized 30.
    """
    return _run_microprofile(
        out_dir,
        reps=reps, log=log,
        agent=_AGENT, format_id=profile_fixtures.FORMAT, config_id=_CONFIG_ID,
        arms=PROFILE_ARMS,
        session_provider=profile_fixtures.make_session,
        fixture_hashes=profile_fixtures.FIXTURE_HASHES,
    )


def _run_microprofile(
    out_dir,
    *,
    reps: int,
    agent: str,
    format_id: str | None,
    config_id: str,
    log,
    arms,
    session_provider,
    fixture_hashes,
) -> dict:
    """The orchestration, with the injection seams. PRIVATE: authorized callers use the public
    :func:`run_microprofile`, which fixes ``arms``/``session_provider``/``fixture_hashes`` to the
    real matrix and fixtures. Tests reach in here to drive stubs and subsets -- neither of which
    can ever publish (the completeness gate below requires the full ``PROFILE_ARMS`` matrix)."""
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ValueError(f"reps must be a positive int, got {reps!r}")

    format_id = format_id or profile_fixtures.FORMAT
    run_arms = tuple(arms)
    run_ids = [a.arm_id for a in run_arms]
    if len(set(run_ids)) != len(run_ids):
        raise DecisionProfileError(f"duplicate arm in the run set: {run_ids}")

    final = Path(out_dir)
    # Fail closed on an existing destination BEFORE doing any work: a finished run is a fixed
    # artifact, and silently overwriting one would destroy evidence a later reader might rely on.
    if final.exists():
        raise FileExistsError(
            f"{final} already exists; the microprofile writes its output directory once"
        )

    # The manifest is built over EXACTLY the arms that will be run, so a manifest can never claim
    # arms whose rows are absent. arm_specs is computed over PROFILE_ARMS; select the run arms
    # from it (design order), failing closed on an arm that is not in the design matrix.
    by_id = {s.arm_id: s for s in arm_specs(fixture_hashes, reps=reps)}
    try:
        specs = [by_id[aid] for aid in run_ids]
    except KeyError as exc:
        raise DecisionProfileError(
            f"arm {exc.args[0]!r} is not in the design matrix PROFILE_ARMS"
        ) from exc

    final.parent.mkdir(parents=True, exist_ok=True)
    # A SIBLING staging dir (same parent, same filesystem) so the final exposure is a single
    # atomic rename. os.makedirs fails closed if a leftover staging dir exists -- rather than
    # writing into unknown state, the run stops here, before it has touched anything.
    staging = final.parent / (final.name + ".staging")
    os.makedirs(staging)

    try:
        manifest = build_profile_manifest(agent=agent, format_id=format_id, arms=specs)
        mhash = profile_manifest_hash(manifest)
        write_profile_manifest(manifest, str(staging / MANIFEST_NAME))

        writer = DecisionProfileWriter(str(staging / ROWS_NAME), manifest=manifest)
        n_rows = 0
        # PROFILE_ARMS order; within an arm, run_arm returns reps 0..reps-1 in order. The rows
        # file is therefore deterministic: (arm order) x (rep order).
        for decl in run_arms:
            entry = arm_by_id(manifest, decl.arm_id)
            for row in _run_one_arm(
                decl, entry, session_provider,
                agent=agent, format_id=format_id, config_id=config_id,
                git_sha=manifest["git_sha"], mhash=mhash, reps=reps,
            ):
                writer.write(row)          # per-row validation happens HERE, on write
                n_rows += 1

        # The dataset gate runs over the FINISHED file, before anything is exposed. It re-runs
        # the per-row validator on every row AND enforces the cross-row identities.
        report = validate_decision_profile_dataset(str(staging / ROWS_NAME), manifest)
        # The completeness gate: publish ONLY the full design matrix (see module docstring).
        _require_complete_matrix(str(staging / ROWS_NAME), reps)

        # Atomic exposure: nothing named `final` existed until this rename, and it happens ONLY
        # after both validator tiers AND the completeness gate passed.
        os.rename(staging, final)
    except BaseException:
        # Never leave a partial or unvalidated result behind. rmtree targets EXACTLY the staging
        # directory this call created -- a sibling of `final`, never `final` and never the parent.
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if log is not None:
        log(f"microprofile: {len(run_arms)} arms x {reps} reps = {n_rows} rows -> {final}")
    return report


def _require_complete_matrix(rows_path: str, reps: int) -> None:
    """Refuse to publish anything but the full design matrix, EXACTLY.

    ``validate_decision_profile_dataset`` proves every row present is valid and that no arm repeats
    a rep, but it does not check which ``(arm, rep)`` coordinates are ABSENT: a one-arm dataset, or
    an arm whose reps are ``{0, 2}`` instead of ``{0, 1}``, both validate -- and the second has the
    right ROW COUNT, so a count-only gate would pass it. For the authorized run the claim is
    '450 rows = every one of the 15 arms at reps 0..29', so this reads the finished file and
    requires the coordinate set to be EXACTLY ``PROFILE_ARMS`` x ``{0..reps-1}`` -- catching a
    missing arm, a missing rep, a count-preserving gap, or an out-of-range rep. It runs before the
    atomic rename, so an incomplete matrix is never exposed. (This reads the artifact rather than
    trusting the in-memory rows, for the same reason the dataset tier re-reads: the file is what
    gets published.)
    """
    design_ids = {a.arm_id for a in PROFILE_ARMS}
    seen: dict[str, set] = {}
    with open(rows_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            seen.setdefault(row["arm_id"], set()).add(row["rep"])

    missing = sorted(design_ids - set(seen))
    unexpected = sorted(set(seen) - design_ids)
    if missing or unexpected:
        raise DecisionProfileError(
            f"incomplete matrix: a published profile must cover all {len(design_ids)} design "
            f"arms; missing {missing}, unexpected {unexpected}"
        )
    expected = set(range(reps))
    for arm_id in sorted(design_ids):
        got = seen[arm_id]
        if got != expected:
            raise DecisionProfileError(
                f"incomplete matrix: arm {arm_id!r} has reps {sorted(got)}, expected "
                f"0..{reps - 1} (missing {sorted(expected - got)}, extra {sorted(got - expected)})"
            )


def _run_one_arm(decl, entry, session_provider, *, agent, format_id, config_id,
                 git_sha, mhash, reps):
    """Run one arm through the harness with its own fresh sessions, closing every one -- on
    success or on failure -- before returning or propagating.

    ``run_arm`` builds sessions via the factory but does not own their teardown (a backend is a
    process handle); the caller does. The factory records each session so the ``finally`` can
    close it, which is what makes 'close on failure' hold when a rep or the warmup raises.
    """
    built = []

    def factory():
        session = session_provider(decl.fixture)
        built.append(session)
        return session

    try:
        return run_arm(
            decl, factory,
            agent=agent, format_id=format_id, config_id=config_id, git_sha=git_sha,
            # each arm's MANIFEST-PINNED identity: its own effective_config_hash and behavior_env
            config_hash=entry["effective_config_hash"],
            profile_manifest_hash=mhash, reps=reps,
            behavior_env=entry["behavior_env"],
        )
    finally:
        for session in built:
            _safe_close(session)


def _safe_close(session) -> None:
    close = getattr(session, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:  # noqa: BLE001 - teardown is best-effort: a close error must not mask the
        pass           # real exception, nor stop the remaining sessions from being closed

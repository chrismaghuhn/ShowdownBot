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

Atomic output
-------------
A run produces a fully-validated output directory or nothing. Rows and the manifest are written
into a SIBLING ``<name>.staging`` directory; only after every row has passed the per-row
validator (on write) AND the finished dataset has passed the dataset tier is the staging
directory renamed onto the final path -- one atomic move, on the same filesystem. Refusing to
overwrite an existing final directory, and removing the staging directory on any failure, keep a
partial or unvalidated result from ever being exposed.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from showdown_bot.eval import profile_fixtures
from showdown_bot.eval.decision_profile import (
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


def run_microprofile(
    out_dir,
    *,
    reps: int,
    agent: str = "heuristic",
    format_id: str | None = None,
    config_id: str = "champions-i8-microprofile",
    arms=None,
    session_provider=None,
    fixture_hashes=None,
    log=None,
) -> dict:
    """Run the microprofile matrix into ``out_dir`` and return the dataset-validation report.

    ``reps`` is REQUIRED and has no default -- it is a run parameter (profile_arms.arm_specs).
    The reusable runner accepts any positive value so tests can run cheaply; only the executable
    entrypoint pins the authorized 30.

    ``session_provider`` (fixture name -> session) and ``fixture_hashes`` default to the promoted
    ``profile_fixtures``; they are injectable so tests can drive the orchestration over node-free
    stubs without changing the runner.
    """
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ValueError(f"reps must be a positive int, got {reps!r}")

    format_id = format_id or profile_fixtures.FORMAT
    arms = tuple(PROFILE_ARMS if arms is None else arms)
    session_provider = session_provider or profile_fixtures.make_session
    fixture_hashes = profile_fixtures.FIXTURE_HASHES if fixture_hashes is None else fixture_hashes

    final = Path(out_dir)
    # Fail closed on an existing destination: a finished run is a fixed artifact, and silently
    # overwriting one would destroy evidence a later reader might still be relying on.
    if final.exists():
        raise FileExistsError(
            f"{final} already exists; the microprofile writes its output directory once"
        )

    final.parent.mkdir(parents=True, exist_ok=True)
    # A SIBLING staging dir (same parent, same filesystem) so the final exposure is a single
    # atomic rename. os.makedirs fails closed if a leftover staging dir exists -- rather than
    # writing into unknown state, the run stops here, before it has touched anything.
    staging = final.parent / (final.name + ".staging")
    os.makedirs(staging)

    try:
        specs = arm_specs(fixture_hashes, reps=reps)
        manifest = build_profile_manifest(agent=agent, format_id=format_id, arms=specs)
        mhash = profile_manifest_hash(manifest)
        write_profile_manifest(manifest, str(staging / MANIFEST_NAME))

        writer = DecisionProfileWriter(str(staging / ROWS_NAME), manifest=manifest)
        n_rows = 0
        # PROFILE_ARMS order; within an arm, run_arm returns reps 0..reps-1 in order. The rows
        # file is therefore deterministic: (arm order) x (rep order).
        for decl in arms:
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

        # Atomic exposure: nothing named `final` existed until this rename, and it happens ONLY
        # after both validator tiers passed.
        os.rename(staging, final)
    except BaseException:
        # Never leave a partial or unvalidated result behind. rmtree targets EXACTLY the staging
        # directory this call created -- a sibling of `final`, never `final` and never the parent.
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if log is not None:
        log(f"microprofile: {len(arms)} arms x {reps} reps = {n_rows} rows -> {final}")
    return report


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

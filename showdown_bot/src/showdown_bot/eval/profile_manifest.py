"""Profile-manifest producer (I8-C, C1): the microprofile run's provenance anchor.

Design: docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md (Rev. 11) §2.7 +
Erratum 1.

A microprofile run emits ONE manifest, and every row of that run carries its canonical hash
in ``profile_manifest_hash``. Without it, `arm_id` would be the identity -- and `arm_id` is
a label: it binds no fixture bytes, no repetition count, no warmup rule, no arm parameters
and no environment. Two runs could carry identical arm ids and be incomparable.

What this module owns, and what it does not
-------------------------------------------
C1 owns the manifest: its exact shape, its provenance, the validation that gates writing and
hashing, and the file. It does NOT decide which arms exist or what is in them -- it takes
``ArmSpec``s. The arm matrix is C2's and is not authorized here.

Two things it deliberately does not re-derive:

  * ``effective_config_hash`` comes from ``config_env.effective_config_manifest``, which
    documents itself as "the ONE place that assembles" priors/spreads/movedata plus the
    format/calc/item/species hashes, and warns that a second, independently-written
    assembly is exactly the drift risk it exists to close. This module calls it.
  * the manifest hash uses ``decision_profile.encode`` -- the same canonicalisation as the
    fixture hash and the row validator. A second canonicaliser would be free to disagree
    about the one question both exist to answer: are these the same inputs?

A single top-level ``config_hash`` could not describe an arm matrix at all: arms vary
BEHAVIOR_AFFECTING knobs, so they have different effective config hashes BY DEFINITION.
That is why the hash lives per arm (§2.7).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from showdown_bot.eval.decision_profile import (
    PROFILE_MANIFEST_SCHEMA_VERSION,
    DecisionProfileError,
    profile_manifest_hash,
    validate_profile_manifest,
)

# The field lists and the schema version live in decision_profile.py, beside the validator
# that enforces them, and are IMPORTED here. This module deliberately keeps no copy: a
# second, independently-written contract is exactly the drift the design's §9 records over
# and over, and the producer holding one would let its output and the validator disagree
# about what a manifest is. The dependency runs producer -> decision_profile, so no cycle.
__all__ = [
    "PROFILE_MANIFEST_SCHEMA_VERSION",
    "ArmSpec",
    "build_profile_manifest",
    "read_profile_manifest",
    "write_profile_manifest",
]


@dataclass
class ArmSpec:
    """What C2 must decide, and C1 merely records.

    ``effective_config_hash`` is deliberately absent: it is DERIVED from ``behavior_env`` by
    the canonical assembly, so letting a caller supply one would invite a value that
    disagrees with the environment it claims to describe.
    """

    arm_id: str
    behavior_env: dict
    arm_params: dict
    scoring_params: dict
    fixture_input_hash: str
    reps: int
    warmup: int
    lifecycle: dict = field(default_factory=dict)


def build_profile_manifest(*, agent: str, format_id: str, arms: list[ArmSpec]) -> dict:
    """Assemble and VALIDATE the manifest. Never returns an invalid one.

    Validation happens here, before the manifest can be written or hashed, so an invalid
    arm matrix cannot acquire an identity or leave an artifact behind.
    """
    from showdown_bot.eval.config_env import (
        config_provenance_for_format,
        effective_config_manifest,
        file_content_hash,
    )
    from showdown_bot.eval.result_jsonl import make_config_hash
    from showdown_bot.engine.moves import movedata_path

    _require(arms, "a manifest with no arms describes no run")

    git_sha, dirty = _git_sha_and_dirty()
    provenance = config_provenance_for_format(format_id)

    entries = []
    for spec in arms:
        _require(
            isinstance(spec, ArmSpec),
            f"arms must be ArmSpec instances, got {type(spec).__name__}",
        )
        entries.append(
            {
                "arm_id": spec.arm_id,
                # DERIVED from this arm's behavior_env by the canonical assembly, never
                # supplied and never re-derived here.
                "effective_config_hash": make_config_hash(
                    effective_config_manifest(
                        agent=agent, format_id=format_id, env=spec.behavior_env
                    )
                ),
                "behavior_env": dict(spec.behavior_env),
                "arm_params": dict(spec.arm_params),
                "scoring_params": dict(spec.scoring_params),
                "fixture_input_hash": spec.fixture_input_hash,
                "reps": spec.reps,
                "warmup": spec.warmup,
                "lifecycle": dict(spec.lifecycle),
            }
        )

    manifest = {
        "schema_version": PROFILE_MANIFEST_SCHEMA_VERSION,
        "git_sha": git_sha,
        "dirty": dirty,
        "calc_pin_hash": provenance["calc_pin_hash"],
        "format_id": format_id,
        "format_config_hash": provenance["format_config_hash"],
        "speciesdata_hash": provenance["speciesdata_hash"],
        "itemdata_hash": provenance["itemdata_hash"],
        # movedata has no *_content_hash helper of its own, unlike itemdata/speciesdata.
        # The canonical assembly hashes the file's bytes (config_env.effective_config_manifest
        # does exactly this), so this uses the same call rather than inventing a second.
        "movedata_hash": file_content_hash(movedata_path()),
        "arms": entries,
    }

    validate_profile_manifest(manifest)
    return manifest


def write_profile_manifest(manifest: dict, path: str) -> str:
    """Validate, write, return the canonical hash. In that order.

    THE FILE STORES THE MANIFEST, NOT ITS ENCODING -- and the distinction is not academic.
    ``encode`` is a canonicaliser for IDENTITY, not a serialiser: it renders floats via
    ``repr`` (a ``risk_lambda`` of ``0.0`` becomes the string ``"0.0"``) and sorts sets into
    lists. Writing ``encode(manifest)`` would freeze those substitutions into the artifact,
    so anything reading the manifest to learn a scoring parameter would get a string where
    the producer meant a float. The first cut did exactly that, and the roundtrip test
    caught it: ``read(write(m)) != m``.

    So the bytes are the manifest, key-sorted and compact, and the hash is taken over
    ``encode(manifest)`` separately. The identity remains checkable from the file alone --
    ``profile_manifest_hash(read_profile_manifest(path))`` -- via the same ``encode`` every
    consumer uses. That is a weaker property than "the bytes are the digest's input", and
    an honest one.
    """
    validate_profile_manifest(manifest)

    # Fail closed on an existing file: a manifest is a run's identity, and silently
    # replacing one would leave rows pointing at a hash whose content is gone.
    if os.path.exists(path):
        raise DecisionProfileError(f"{path} exists; a manifest is written once per run")

    # sort_keys for byte-determinism; no `default=`, so an unserialisable scoring_param
    # raises rather than being coerced into whatever str() happens to produce.
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # newline="" so the "\n" below is not translated to CRLF on Windows: this file is
    # provenance, and the same run must produce the same bytes on every platform.
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(payload + "\n")

    return profile_manifest_hash(manifest)


def read_profile_manifest(path: str) -> dict:
    """Read a manifest back and VALIDATE it. A file on disk is not a trusted writer.

    The same principle the dataset tier rests on: frozen evidence must not be trusted
    because of who wrote it. A manifest edited after the fact -- a duplicate arm injected,
    a run-level warmup added -- is rejected here rather than resolved against.
    """
    with open(path, encoding="utf-8") as fh:
        try:
            manifest = json.load(fh)
        except json.JSONDecodeError as exc:
            raise DecisionProfileError(f"{path} is not valid JSON: {exc}") from exc

    validate_profile_manifest(manifest)
    return manifest


def _git_sha_and_dirty() -> tuple[str, bool]:
    """The repo-wide helper, behind a module-level seam so a git-less run is testable.

    It returns the sentinel ``("unknown", False)`` when git is unavailable rather than
    failing -- which is right for the artifacts that helper generally serves, and wrong for
    this one. ``validate_profile_manifest`` rejects the sentinel, so a git-less environment
    gets no manifest and no file: it may run tests, it may not produce I8 evidence.
    """
    from showdown_bot.learning.provenance import git_sha_and_dirty

    return git_sha_and_dirty()


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise DecisionProfileError(message)

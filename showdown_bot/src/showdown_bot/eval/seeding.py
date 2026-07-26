"""Deterministic per-battle sim seed derivation + seed-log verification (T1b).

`derive_battle_seed` is MIRRORED CHARACTER-FOR-CHARACTER in the server patch
(tools/eval/patches/pokemon-showdown-seeded-battle.patch):

    seed_i = "sodium," + sha256(f"{base}:{index}").hexdigest()[:32]

It depends ONLY on (base, battle index) — never on teams/policies — so a fresh server
session reproduces the whole seed *sequence* and an A-vs-B paired run shares luck
(parent plan T1-CC-A / T1-CC-C).

`verify_seed_log` is the T1b PRIMARY gate (T1-CC-D): it reads the JSONL the server writes
to `SHOWDOWN_EVAL_SEED_LOG` and asserts the actually-used seeds equal the Python
derivation, with a strict contiguous-from-0 battle_index (T1-CC-B — Channel A depends on
creation order; any retry/extra battle shifts the counter and MUST fail fast).
"""
from __future__ import annotations

import hashlib
import json
import os


# The pairing's two environment variables. Both are read by the SERVER at startup (it derives the
# seeds and writes the log); the client process reads them only to know what to verify and where.
SEED_LOG_ENV = "SHOWDOWN_EVAL_SEED_LOG"
SEED_BASE_ENV = "SHOWDOWN_BATTLE_SEED_BASE"


class SeedLogError(RuntimeError):
    """The server seed log disagrees with the expected derivation / ordering."""


class SeedLogConfigError(SeedLogError):
    """The seed-log wiring is half-configured, or its path cannot serve as this run's log.

    Raised by the BEFORE-battle-1 preflight, so a run that could never verify its seeds costs
    zero battles instead of the whole schedule.
    """


def check_seed_log_env_pairing() -> tuple[str, str]:
    """Return ``(seed_base, seed_log_path)`` from the environment, refusing a HALF-configuration.

    Both variables set is a Channel-A run; neither set is a plain unseeded run (a coherent
    configuration -- the caller decides whether that is allowed here). Exactly one set is the
    failure mode that has bitten twice, in both directions, and is never valid: the run would
    either have nothing to verify against or nowhere to read the played seeds from.
    """
    base = os.environ.get(SEED_BASE_ENV, "") or ""
    seed_log = os.environ.get(SEED_LOG_ENV, "") or ""
    if base and not seed_log:
        raise SeedLogConfigError(
            f"seed-log wiring is half-configured: {SEED_BASE_ENV}={base!r} is set but "
            f"{SEED_LOG_ENV} is NOT set for this process. The missing half is the CLIENT half -- "
            f"the server may well be writing a seed log, but this run does not know where, so the "
            f"played seeds can never be read back and verified. Set {SEED_LOG_ENV} to exactly the "
            f"path the server was started with."
        )
    if seed_log and not base:
        raise SeedLogConfigError(
            f"seed-log wiring is half-configured: {SEED_LOG_ENV}={seed_log!r} is set but "
            f"{SEED_BASE_ENV} is NOT set. Without the seed namespace there is nothing to verify "
            f"the logged seeds against. Set {SEED_BASE_ENV} to the base the server was started with."
        )
    return base, seed_log


def preflight_seed_log_path(seed_log_path: str) -> None:
    """Assert the seed log's path can actually serve this run, BEFORE battle 1.

    Checks only what is observable from this process: the path is named, its directory exists and
    is writable (that is where the server appends), and the file itself is absent or empty (a
    stale or pre-populated log cannot prove THESE seeds, even if it would itself verify).

    Deliberately does NOT create the target: an absent log and an existing-but-empty log produce
    different diagnostics afterwards, and "seed log not found" is the one that names the server
    half.
    """
    if not seed_log_path:
        raise SeedLogConfigError(
            f"no seed-log path: {SEED_LOG_ENV} must name the file the server appends its "
            f"per-battle Channel-A seed records to"
        )
    parent = os.path.dirname(os.path.abspath(seed_log_path))
    if not os.path.isdir(parent):
        raise SeedLogConfigError(
            f"seed log {seed_log_path!r}: its directory {parent!r} does not exist, so the server "
            f"cannot write the log there"
        )
    probe = os.path.join(parent, f".seed_log_write_probe.{os.getpid()}")
    try:
        with open(probe, "w", encoding="utf-8"):
            pass
    except OSError as exc:
        raise SeedLogConfigError(
            f"seed log {seed_log_path!r}: its directory {parent!r} is not writable ({exc}), so "
            f"the server cannot write the log there"
        ) from exc
    finally:
        try:
            os.remove(probe)
        except OSError:
            pass
    if os.path.exists(seed_log_path):
        if os.path.getsize(seed_log_path) > 0:
            raise SeedLogConfigError(
                f"seed log {seed_log_path!r} already exists and is non-empty before any battle "
                f"has played -- a stale or pre-populated seed log cannot prove THIS run's seeds; "
                f"restart from a fresh, empty (or absent) seed log"
            )
        try:
            with open(seed_log_path, encoding="utf-8"):
                pass
        except OSError as exc:
            raise SeedLogConfigError(
                f"seed log {seed_log_path!r} exists but cannot be read back ({exc}); this run "
                f"could not verify its own seeds"
            ) from exc


def assert_server_half_is_writing(seed_log_path: str, base: str, battles_played: int) -> None:
    """The earliest sound check of the SERVER half: run the real verification after battle 1.

    No client-side preflight can observe another process's environment, so a server started
    without ``SHOWDOWN_EVAL_SEED_LOG`` is invisible until it has failed to write something. This
    turns that discovery from "after the whole schedule" into "after one battle" by applying
    ``verify_seed_log`` at ``battles_played`` records instead of waiting for the final call.
    """
    try:
        verify_seed_log(seed_log_path, base, battles_played)
    except SeedLogError as exc:
        if _seed_log_record_count(seed_log_path) > 0:
            # The server IS writing -- the log simply disagrees. That is a genuine alignment
            # failure, not a wiring fault, and it keeps its own diagnosis.
            raise
        raise SeedLogConfigError(
            f"seed-log wiring incomplete: after battle {battles_played} the log is still empty or "
            f"absent ({exc}). The missing half is the SERVER half: the server must be started with "
            f"{SEED_LOG_ENV}={seed_log_path!r} and {SEED_BASE_ENV}={base!r}. Aborting now rather "
            f"than after the rest of the schedule."
        ) from exc


def _seed_log_record_count(seed_log_path: str) -> int:
    """How many non-blank lines the log holds right now; 0 for an absent or unreadable file."""
    try:
        with open(seed_log_path, encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def derive_battle_seed(base: str, index: int) -> str:
    digest = hashlib.sha256(f"{base}:{index}".encode()).hexdigest()
    return f"sodium,{digest[:32]}"


def verify_seed_log(path: str, base: str, expected_count: int) -> list[dict]:
    """Read the server seed log and assert it matches the expected seed sequence.

    Raises ``SeedLogError`` unless there are exactly ``expected_count`` records whose
    ``battle_index`` is contiguous 0..N-1, whose ``seed_base`` == ``base``, and whose
    ``seed`` == ``derive_battle_seed(base, battle_index)``. Returns the parsed records.
    """
    if not os.path.exists(path):
        raise SeedLogError(
            f"seed log not found: {path} "
            f"(server not started with SHOWDOWN_EVAL_SEED_LOG, or wrong path)"
        )
    records: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:  # noqa: PERF203
                raise SeedLogError(f"{path}:{lineno}: malformed JSON: {exc}") from exc

    if len(records) != expected_count:
        raise SeedLogError(
            f"{path}: expected {expected_count} battles, found {len(records)} "
            f"(a retry/extra battle invalidates a Channel-A run)"
        )
    for i, rec in enumerate(records):
        if rec.get("battle_index") != i:
            raise SeedLogError(
                f"{path}: non-contiguous battle_index at position {i}: {rec.get('battle_index')!r} "
                f"(expected {i}); counter shifted"
            )
        if rec.get("seed_base") != base:
            raise SeedLogError(
                f"{path}: battle {i} seed_base {rec.get('seed_base')!r} != expected {base!r}"
            )
        expected = derive_battle_seed(base, i)
        if rec.get("seed") != expected:
            raise SeedLogError(
                f"{path}: battle {i} server seed {rec.get('seed')!r} != derive_battle_seed {expected!r} "
                f"(Python↔server derivation mismatch)"
            )
    return records

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


class SeedLogError(RuntimeError):
    """The server seed log disagrees with the expected derivation / ordering."""


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

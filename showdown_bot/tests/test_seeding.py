"""T1b per-battle seed derivation + seed-log verification.

`derive_battle_seed` is mirrored character-for-character in the server patch
(tools/eval/patches/); the known-vector test pins the formula so the server copy can be
checked against it. `verify_seed_log` is the T1b PRIMARY gate: it asserts the server's
logged seeds equal `derive_battle_seed(base, i)` and that battle_index is contiguous
from 0 (Channel A depends on creation order — any gap/extra battle must fail fast).
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval.seeding import (
    SeedLogError,
    derive_battle_seed,
    verify_seed_log,
)


def test_deterministic_and_distinct_per_index():
    assert derive_battle_seed("run2026", 0) == derive_battle_seed("run2026", 0)
    assert derive_battle_seed("run2026", 0) != derive_battle_seed("run2026", 1)


def test_valid_prngseed_form():
    s = derive_battle_seed("run2026", 0)
    assert s.startswith("sodium,")
    hexpart = s.split(",", 1)[1]
    assert len(hexpart) == 32
    int(hexpart, 16)  # parses as hex (raises if not)


def test_base_changes_sequence():
    assert derive_battle_seed("A", 0) != derive_battle_seed("B", 0)


def test_known_vector():
    # Pins the exact formula: "sodium," + sha256(f"{base}:{index}").hexdigest()[:32].
    assert derive_battle_seed("run2026", 0) == "sodium,a32cceab439a5fa3fd603bb706de835a"
    assert derive_battle_seed("run2026", 1) == "sodium,cf62088cdab12fe1542792e890d9bf9f"


def _write_log(path, records):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def test_verify_seed_log_ok(tmp_path):
    base = "run2026"
    p = tmp_path / "seeds.jsonl"
    _write_log(p, [
        {"battle_index": i, "seed": derive_battle_seed(base, i), "seed_base": base}
        for i in range(4)
    ])
    records = verify_seed_log(str(p), base, 4)
    assert [r["battle_index"] for r in records] == [0, 1, 2, 3]


def test_verify_seed_log_rejects_wrong_count(tmp_path):
    base = "run2026"
    p = tmp_path / "seeds.jsonl"
    _write_log(p, [{"battle_index": 0, "seed": derive_battle_seed(base, 0), "seed_base": base}])
    with pytest.raises(SeedLogError):
        verify_seed_log(str(p), base, 4)  # only 1 line, expected 4


def test_verify_seed_log_rejects_noncontiguous_index(tmp_path):
    # An extra/retried battle shifts the counter -> non-contiguous -> must fail fast.
    base = "run2026"
    p = tmp_path / "seeds.jsonl"
    _write_log(p, [
        {"battle_index": 0, "seed": derive_battle_seed(base, 0), "seed_base": base},
        {"battle_index": 2, "seed": derive_battle_seed(base, 2), "seed_base": base},
    ])
    with pytest.raises(SeedLogError):
        verify_seed_log(str(p), base, 2)


def test_verify_seed_log_missing_file_raises_clear_error(tmp_path):
    # N1: a missing seed log (server not run with SHOWDOWN_EVAL_SEED_LOG, or wrong path)
    # must be a clear SeedLogError, not a bare FileNotFoundError.
    missing = tmp_path / "does_not_exist.jsonl"
    with pytest.raises(SeedLogError) as exc:
        verify_seed_log(str(missing), "run2026", 4)
    assert "not found" in str(exc.value).lower()


def test_verify_seed_log_rejects_wrong_seed(tmp_path):
    # Server used a seed that doesn't match the Python derivation (T1-CC-A break).
    base = "run2026"
    p = tmp_path / "seeds.jsonl"
    _write_log(p, [
        {"battle_index": 0, "seed": "sodium,deadbeefdeadbeefdeadbeefdeadbeef", "seed_base": base},
    ])
    with pytest.raises(SeedLogError):
        verify_seed_log(str(p), base, 1)

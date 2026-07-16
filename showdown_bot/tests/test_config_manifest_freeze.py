"""I7a-C P1.4: reproducible config-manifest freeze sidecar.

``write_config_manifest_sidecar`` is the ONE dedicated, fail-closed writer for
``<results>.config-manifest.json`` -- it must call ``effective_config_manifest`` (the
same function the CLI's live config_hash computation uses), verify the computed hash
matches every row's ``config_hash`` in the target results file, and refuse to silently
overwrite an existing sidecar or freeze against a results file with missing/inconsistent
``config_hash`` values.
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval.config_manifest_freeze import (
    ConfigManifestFreezeError,
    write_config_manifest_sidecar,
)
from showdown_bot.eval.config_env import effective_config_manifest
from showdown_bot.eval.result_jsonl import make_config_hash

FORMAT_ID = "gen9championsvgc2026regma"


def _write_results(tmp_path, config_hash: str, n: int = 2):
    path = tmp_path / "results.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"battle_id": f"b{i}", "config_hash": config_hash}) + "\n")
    return path


def test_write_config_manifest_sidecar_matches_effective_manifest_hash(tmp_path):
    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)

    out_path = write_config_manifest_sidecar(
        results_path, agent="heuristic", format_id=FORMAT_ID, env={},
    )

    assert out_path == results_path.with_name(results_path.name + ".config-manifest.json")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["config_hash"] == config_hash
    assert payload["manifest"] == manifest
    assert make_config_hash(payload["manifest"]) == payload["config_hash"]


def test_write_config_manifest_sidecar_fails_closed_on_hash_mismatch(tmp_path):
    results_path = _write_results(tmp_path, "deadbeefdeadbeef")

    with pytest.raises(ConfigManifestFreezeError, match="mismatch"):
        write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

    assert not results_path.with_name(results_path.name + ".config-manifest.json").exists()


def test_write_config_manifest_sidecar_fails_closed_on_missing_results(tmp_path):
    missing = tmp_path / "nope.jsonl"
    with pytest.raises(ConfigManifestFreezeError, match="does not exist|missing|empty"):
        write_config_manifest_sidecar(missing, agent="heuristic", format_id=FORMAT_ID, env={})


def test_write_config_manifest_sidecar_fails_closed_on_inconsistent_row_hashes(tmp_path):
    path = tmp_path / "results.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"battle_id": "b0", "config_hash": "aaaaaaaaaaaaaaaa"}) + "\n")
        fh.write(json.dumps({"battle_id": "b1", "config_hash": "bbbbbbbbbbbbbbbb"}) + "\n")

    with pytest.raises(ConfigManifestFreezeError, match="inconsistent|multiple"):
        write_config_manifest_sidecar(path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_write_config_manifest_sidecar_fails_closed_on_missing_row_config_hash(tmp_path):
    path = tmp_path / "results.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"battle_id": "b0"}) + "\n")

    with pytest.raises(ConfigManifestFreezeError, match="config_hash"):
        write_config_manifest_sidecar(path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_write_config_manifest_sidecar_refuses_to_overwrite_existing_sidecar(tmp_path):
    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)

    write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

    with pytest.raises(ConfigManifestFreezeError, match="already exists"):
        write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})


# --- Codex re-review finding: a re-verification path for a frozen sidecar ----------------

def test_verify_config_manifest_sidecar_passes_for_a_freshly_written_sidecar(tmp_path):
    from showdown_bot.eval.config_manifest_freeze import verify_config_manifest_sidecar

    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)
    write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

    # Must not raise.
    verify_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_verify_config_manifest_sidecar_fails_closed_when_sidecar_missing(tmp_path):
    from showdown_bot.eval.config_manifest_freeze import verify_config_manifest_sidecar

    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)

    with pytest.raises(ConfigManifestFreezeError, match="does not exist|missing"):
        verify_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_verify_config_manifest_sidecar_fails_closed_when_sidecar_manifest_was_edited(tmp_path):
    from showdown_bot.eval.config_manifest_freeze import verify_config_manifest_sidecar

    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)
    sidecar_path = write_config_manifest_sidecar(
        results_path, agent="heuristic", format_id=FORMAT_ID, env={},
    )

    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    payload["manifest"]["format_id"] = "tampered"
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigManifestFreezeError, match="rehash|mismatch"):
        verify_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})


def test_verify_config_manifest_sidecar_fails_closed_when_a_result_row_no_longer_matches(tmp_path):
    from showdown_bot.eval.config_manifest_freeze import verify_config_manifest_sidecar

    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    config_hash = make_config_hash(manifest)
    results_path = _write_results(tmp_path, config_hash)
    write_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})

    # Simulate a post-hoc mutation (e.g. room_raw_path=null) that also broke a row's hash.
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["config_hash"] = "clearlywrong0000"
    results_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    with pytest.raises(ConfigManifestFreezeError, match="inconsistent|multiple"):
        verify_config_manifest_sidecar(results_path, agent="heuristic", format_id=FORMAT_ID, env={})


# --- LF-only sidecar bytes --------------------------------------------------
# write_config_manifest_sidecar used the platform default newline (unlike
# BattleResultWriter / eval-report, which pass newline="\n"), so on Windows it
# emitted CRLF. The frozen I7b-C evidence caught this: the on-disk sidecar was
# CRLF while its blob was LF, and the verdict report initially pinned the CRLF
# hash -- a value no checkout could reproduce.
#
# `data/eval/champions-panel-v0/** -text` stops git from REWRITING bytes on
# checkout; it cannot stop a fresh Windows run from PRODUCING CRLF. This is the
# writer-side half of that fix.


def test_config_manifest_sidecar_bytes_are_lf_only(tmp_path):
    """Assert on RAW BYTES: text mode applies universal newlines on read, so a
    text-mode assertion passes on exactly the platform that has the bug."""
    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    results_path = _write_results(tmp_path, make_config_hash(manifest))

    out_path = write_config_manifest_sidecar(
        results_path, agent="heuristic", format_id=FORMAT_ID, env={},
    )

    raw = out_path.read_bytes()
    assert b"\r" not in raw, "config-manifest sidecar must be LF-only on every platform"
    # The payload is pretty-printed JSON, so it MUST contain newlines -- otherwise
    # "no CR" would be trivially true for a single-line file and prove nothing.
    assert raw.count(b"\n") > 1


def test_config_manifest_sidecar_has_no_trailing_newline(tmp_path):
    """Pins the EXISTING byte contract, deliberately.

    The writer emits `json.dumps(...)` with no terminator, so the file ends at
    `}`. That is not an oversight to tidy up here: the frozen I7a-C and I7b-C
    sidecars both end at `}`, and appending a trailing newline would change their
    bytes, break the sha256 values their verdict reports pin, and make the
    committed evidence unreproducible by this very function. If that contract is
    ever revisited, the frozen sidecars must be re-frozen in the same change --
    this test is here to force that conversation rather than let it happen
    silently."""
    manifest = effective_config_manifest(agent="heuristic", format_id=FORMAT_ID, env={})
    results_path = _write_results(tmp_path, make_config_hash(manifest))

    out_path = write_config_manifest_sidecar(
        results_path, agent="heuristic", format_id=FORMAT_ID, env={},
    )

    raw = out_path.read_bytes()
    assert raw.endswith(b"}")
    assert not raw.endswith(b"\n")


def test_regenerated_sidecar_is_byte_identical_to_the_frozen_i7b_evidence(tmp_path):
    """The regression that matters: re-running the FIXED writer against the frozen
    I7b-C results must reproduce the committed sidecar byte for byte. If it does
    not, either the writer drifted or the frozen evidence is no longer derivable
    from it -- both invalidate the freeze."""
    import hashlib
    import shutil
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    frozen_dir = repo_root / "data" / "eval" / "champions-panel-v0" / "smoke-i7b-mega"
    frozen_results = frozen_dir / "results.jsonl"
    frozen_sidecar = frozen_dir / "results.jsonl.config-manifest.json"
    if not frozen_sidecar.exists():  # pragma: no cover - evidence not in this checkout
        pytest.skip("frozen I7b-C smoke evidence not present in this checkout")

    # Regenerate into a TEMP dir: the frozen sidecar is never touched, and the
    # writer's own refuse-to-overwrite gate stays intact.
    shutil.copy(frozen_results, tmp_path / "results.jsonl")
    out_path = write_config_manifest_sidecar(
        tmp_path / "results.jsonl", agent="heuristic", format_id=FORMAT_ID,
        # The run's real BEHAVIOR_AFFECTING env -- both vars, not just the click
        # rate: SHOWDOWN_HERO_AGENT is behavioural too, and omitting it computes
        # 379c6df1176c2372 instead of the recorded 5fb04622afebd59f.
        env={"SHOWDOWN_HERO_AGENT": "heuristic", "SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
    )

    regenerated = out_path.read_bytes()
    frozen = frozen_sidecar.read_bytes()
    assert b"\r" not in regenerated
    assert hashlib.sha256(regenerated).hexdigest() == hashlib.sha256(frozen).hexdigest(), (
        "the fixed writer no longer reproduces the frozen I7b-C sidecar"
    )
    assert regenerated == frozen

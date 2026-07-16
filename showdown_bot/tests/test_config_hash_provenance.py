"""I4 §5.3: format_config_hash + calc_pin_hash in effective config_hash."""
from __future__ import annotations

from pathlib import Path

import pytest

from showdown_bot.engine.calc.pin import (
    PinnedCalcError,
    calc_pin_hash,
    format_config_hash,
    load_pinned_calc_manifest,
)
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.eval.config_env import build_config_manifest, config_provenance_for_format
from showdown_bot.eval.result_jsonl import make_config_hash


def _manifest(**overrides):
    base = build_config_manifest(
        agent="heuristic",
        format_id="gen9vgc2025regi",
        priors_hash="p",
        spreads_hash="s",
        env={},
    )
    base.update(overrides)
    return base


def test_config_hash_includes_format_config_hash():
    cfg = load_format_config("gen9vgc2025regi")
    assert cfg.source_path is not None
    fmt_hash = format_config_hash(cfg.source_path)
    manifest = build_config_manifest(
        agent="a",
        format_id=cfg.format_id,
        priors_hash="p",
        spreads_hash="s",
        env={},
        format_config_hash=fmt_hash,
    )
    assert manifest["format_config_hash"] == fmt_hash
    assert "format_config_hash" in manifest


def test_config_hash_includes_calc_pin_hash():
    pin = calc_pin_hash()
    manifest = build_config_manifest(
        agent="a",
        format_id="f",
        priors_hash="p",
        spreads_hash="s",
        env={},
        calc_pin_hash=pin,
    )
    assert manifest["calc_pin_hash"] == pin
    assert pin == "79a4877538c8740f"


def test_pinned_calc_manifest_is_lf_on_disk():
    from showdown_bot.engine.calc.pin import DEFAULT_CALC_DIR, PINNED_CALC_FILENAME

    raw = (DEFAULT_CALC_DIR / PINNED_CALC_FILENAME).read_bytes()
    assert b"\r\n" not in raw


def test_config_hash_changes_when_calc_generation_changes(tmp_path: Path):
    def write_yaml(name: str, calc_generation: int) -> Path:
        path = tmp_path / f"{name}.yaml"
        path.write_text(
            "\n".join(
                [
                    f"format_id: {name}",
                    "level: 50",
                    "game_type: doubles",
                    f"calc_generation: {calc_generation}",
                    "meta_paths:",
                    "  default_spreads: meta/default_spreads.yaml",
                ]
            ),
            encoding="utf-8",
        )
        return path

    gen9_path = write_yaml("fmt_gen9", 9)
    gen0_path = write_yaml("fmt_gen0", 0)
    h9 = format_config_hash(gen9_path)
    h0 = format_config_hash(gen0_path)
    assert h9 != h0

    base = dict(agent="a", format_id="f", priors_hash="p", spreads_hash="s", env={})
    hash9 = make_config_hash(build_config_manifest(**base, format_config_hash=h9))
    hash0 = make_config_hash(build_config_manifest(**base, format_config_hash=h0))
    assert hash9 != hash0


def test_config_hash_changes_when_calc_artifact_changes():
    m1 = _manifest(calc_pin_hash="aaaaaaaaaaaaaaaa")
    m2 = _manifest(calc_pin_hash="bbbbbbbbbbbbbbbb")
    assert make_config_hash(m1) != make_config_hash(m2)


def test_config_provenance_for_format_includes_both_hashes():
    provenance = config_provenance_for_format("gen9vgc2025regi")
    assert provenance["format_config_hash"]
    assert provenance["calc_pin_hash"] == "79a4877538c8740f"


def test_load_pinned_calc_manifest_verifies_artifact():
    manifest = load_pinned_calc_manifest()
    assert manifest["artifact_filename"].endswith(".tgz")
    assert manifest["root_lockfile_sha256"]


def test_calc_pin_hash_fails_closed_on_artifact_mismatch(tmp_path: Path, monkeypatch):
    calc_dir = tmp_path / "calc"
    vendor = calc_dir / "vendor"
    vendor.mkdir(parents=True)
    tgz = vendor / "bad.tgz"
    tgz.write_bytes(b"not-the-real-artifact")
    manifest = {
        "artifact_filename": "bad.tgz",
        "artifact_sha256": "0" * 64,
    }
    (calc_dir / "PINNED_CALC.json").write_text(
        __import__("json").dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "showdown_bot.engine.calc.pin.DEFAULT_CALC_DIR",
        calc_dir,
    )
    with pytest.raises(PinnedCalcError, match="SHA-256 mismatch"):
        calc_pin_hash(calc_dir=calc_dir)


def test_config_provenance_propagates_artifact_mismatch(tmp_path: Path, monkeypatch):
    calc_dir = tmp_path / "calc"
    vendor = calc_dir / "vendor"
    vendor.mkdir(parents=True)
    tgz = vendor / "bad.tgz"
    tgz.write_bytes(b"not-the-real-artifact")
    manifest = {
        "artifact_filename": "bad.tgz",
        "artifact_sha256": "0" * 64,
    }
    (calc_dir / "PINNED_CALC.json").write_text(
        __import__("json").dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "showdown_bot.engine.calc.pin.DEFAULT_CALC_DIR",
        calc_dir,
    )
    with pytest.raises(PinnedCalcError, match="SHA-256 mismatch"):
        config_provenance_for_format("gen9vgc2025regi")


def test_config_provenance_missing_format_returns_none_format_hash():
    provenance = config_provenance_for_format("does_not_exist_format")
    assert provenance["format_config_hash"] is None
    assert provenance["calc_pin_hash"] == "79a4877538c8740f"


# --- config_hash must be platform-stable ------------------------------------
# test_pinned_calc_manifest_is_lf_on_disk above had the right idea and the wrong
# scope: PINNED_CALC.json was LF-pinned, every OTHER raw-byte-hashed provenance
# input was not. With core.autocrlf=true git checked those blobs out as CRLF on
# Windows and LF on Linux, so `.read_bytes()` saw different bytes and the SAME
# configuration hashed differently per host:
#
#     Windows: 5fb04622afebd59f      Linux: b3cb6ea1a4836060
#
# Two runs of an identical config on different machines therefore recorded
# different config_hash values, and any cross-platform A/B silently compared
# "different" configs. `text eol=lf` in .gitattributes fixes the inputs; these
# tests are what keep them fixed.

# Every provenance input read with .read_bytes() and hashed directly. Files whose
# hash comes from re-serialised JSON (itemdata/speciesdata via
# generated_data_hash.embedded_table_hash) are excluded on purpose: parsing
# discards line endings, so they were never part of the drift.
_RAW_BYTE_HASHED_GLOBS = (
    "showdown_bot/config/formats/*.yaml",           # format_config_hash
    "showdown_bot/config/formats/meta/**/*.yaml",   # file_content_hash: priors, spreads
    "showdown_bot/config/moves/*.json",             # file_content_hash: movedata
    "config/eval/schedules/*.yaml",                 # report.py input_sha256
    "config/eval/panels/*.yaml",                    # report.py input_sha256, baseline.py
    "showdown_bot/tools/calc/PINNED_CALC.json",     # calc_pin_hash
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_every_raw_byte_hashed_provenance_input_is_lf_on_disk():
    """The general form of test_pinned_calc_manifest_is_lf_on_disk.

    Asserts on RAW BYTES over every file whose digest feeds config_hash or a
    report's input_sha256. A single CRLF here silently forks provenance between
    Windows and Linux -- which is exactly what happened before `text eol=lf`."""
    root = _repo_root()
    offenders = []
    checked = 0
    for pattern in _RAW_BYTE_HASHED_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            checked += 1
            if b"\r" in path.read_bytes():
                offenders.append(str(path.relative_to(root)))
    assert checked >= 20, f"glob set matched only {checked} files -- did paths move?"
    assert not offenders, (
        "raw-byte-hashed provenance inputs must be LF-only or config_hash forks "
        f"per platform: {offenders}"
    )


def test_champions_config_hash_is_the_platform_stable_lf_value():
    """Pins the LF config_hash itself, not just 'no CR anywhere'.

    b3cb6ea1a4836060 is the value a Linux checkout produces (CI measured it) and,
    after the LF pin, the value a Windows checkout produces too. If this test
    fails on ONE platform only, the .gitattributes pin has regressed. If it fails
    on BOTH, a config input genuinely changed and the frozen evidence that cites
    this hash must be re-validated -- not silently re-pinned."""
    from showdown_bot.eval.config_env import effective_config_manifest

    manifest = effective_config_manifest(
        agent="heuristic", format_id="gen9championsvgc2026regma",
        # The I7b-C smoke's real BEHAVIOR_AFFECTING env, both vars.
        env={"SHOWDOWN_HERO_AGENT": "heuristic", "SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
    )
    assert make_config_hash(manifest) == "b3cb6ea1a4836060"
    # The components that actually drifted, pinned individually so a failure names
    # the culprit instead of just moving the top-level hash.
    assert manifest["priors_hash"] == "64943d724ac1c9d0"
    assert manifest["spreads_hash"] == "c3a07a45d4dd05b0"
    assert manifest["movedata_hash"] == "20b3c72e72480ee1"
    assert manifest["format_config_hash"] == "fa8eb689e95c03c6"
    # Never drifted (re-serialised / already LF-pinned) -- pinned to prove the fix
    # did not disturb them.
    assert manifest["itemdata_hash"] == "c5b00bfb5f093e98"
    assert manifest["speciesdata_hash"] == "b6e121e58c592056"
    assert manifest["calc_pin_hash"] == "79a4877538c8740f"


def test_config_hash_is_invariant_to_crlf_in_its_inputs(tmp_path):
    """The mechanism itself, proven rather than assumed.

    Rewrites the real format yaml with CRLF into a temp copy and shows
    format_config_hash changes -- i.e. line endings alone move a provenance hash.
    That is why the .gitattributes pin is load-bearing and not cosmetic: nothing
    in the hashing code normalises, so the guarantee has to come from git."""
    cfg = load_format_config("gen9championsvgc2026regma")
    src = Path(cfg.source_path)
    lf_bytes = src.read_bytes()
    assert b"\r" not in lf_bytes, "checked-out format yaml must already be LF"

    crlf_copy = tmp_path / src.name
    crlf_copy.write_bytes(lf_bytes.replace(b"\n", b"\r\n"))

    assert format_config_hash(src) == "fa8eb689e95c03c6"
    assert format_config_hash(crlf_copy) != format_config_hash(src), (
        "format_config_hash must be byte-sensitive -- if this ever passes, the hash "
        "normalises and this whole pin could be relaxed"
    )

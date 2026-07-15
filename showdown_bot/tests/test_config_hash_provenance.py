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

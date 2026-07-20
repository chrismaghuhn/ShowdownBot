from __future__ import annotations

from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.validate_bundle import BundleValidationError, validate_bundle_dir

BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-01"


def test_validate_fixture01_bundle():
    manifest = validate_bundle_dir(BUNDLE)
    assert manifest["viewer_bundle_schema"]["major"] == 1


def test_validate_refuses_undeclared_file(tmp_path):
    import shutil

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)
    (dst / "extra.txt").write_text("x", encoding="utf-8")
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason == "undeclared_file"


def test_validate_refuses_path_traversal(tmp_path):
    import hashlib
    import json
    import shutil

    from showdownbot_studio_exporter.canonicalize import dumps

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)
    (dst / "battle.jsonl").unlink()
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    # Escape would resolve to tmp_path/outside.jsonl with matching digest.
    manifest["files"]["battle_log"] = {
        "path": "../outside.jsonl",
        "present": True,
        "required": True,
        "sha256": digest,
    }
    (dst / "manifest.json").write_bytes(dumps(manifest))
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    # Escape paths are non-canonical for battle_log; path form checks also refuse.
    assert exc.value.reason in {"path_escape", "malformed_path", "noncanonical_path"}


def test_validate_refuses_subdirectory(tmp_path):
    import shutil

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)
    nested = dst / "nested"
    nested.mkdir()
    (nested / "payload.exe").write_bytes(b"MZ")
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason == "undeclared_subdirectory"


def test_validate_refuses_unknown_logical_key(tmp_path):
    import json
    import shutil

    from showdownbot_studio_exporter.canonicalize import dumps

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)
    manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    (dst / "extra.json").write_text("{}", encoding="utf-8")
    manifest["files"]["sprites"] = {
        "path": "extra.json",
        "present": True,
        "required": False,
        "sha256": __import__("hashlib").sha256(b"{}").hexdigest(),
    }
    (dst / "manifest.json").write_bytes(dumps(manifest))
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason == "unknown_logical_key"


def _rewrite_manifest(dst, mutate):
    import json

    from showdownbot_studio_exporter.canonicalize import dumps

    manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    mutate(manifest, dst)
    (dst / "manifest.json").write_bytes(dumps(manifest))


def test_validate_refuses_noncanonical_battle_path(tmp_path):
    import hashlib
    import shutil

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)
    payload = dst / "payload.exe"
    payload.write_bytes((dst / "battle.jsonl").read_bytes())
    (dst / "battle.jsonl").unlink()
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()

    def mutate(manifest, _dst):
        manifest["files"]["battle_log"]["path"] = "payload.exe"
        manifest["files"]["battle_log"]["sha256"] = digest

    _rewrite_manifest(dst, mutate)
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason == "noncanonical_path"


def test_validate_refuses_aliased_logical_paths(tmp_path):
    import hashlib
    import shutil

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)
    # Point both logical keys at the same physical decisions file (via renamed battle).
    (dst / "battle.jsonl").unlink()
    digest = hashlib.sha256((dst / "decisions.jsonl").read_bytes()).hexdigest()

    def mutate(manifest, _dst):
        manifest["files"]["battle_log"]["path"] = "decisions.jsonl"
        manifest["files"]["battle_log"]["sha256"] = digest

    _rewrite_manifest(dst, mutate)
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason in {"noncanonical_path", "duplicate_path"}


def test_validate_refuses_unknown_trace_schema_version(tmp_path):
    import shutil

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)

    def mutate(manifest, _dst):
        manifest["trace_schema_version"] = "decision-trace-v999"

    _rewrite_manifest(dst, mutate)
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason == "unsupported_trace_schema_version"


def test_validate_refuses_string_booleans(tmp_path):
    import shutil

    dst = tmp_path / "copy"
    shutil.copytree(BUNDLE, dst)

    def mutate(manifest, _dst):
        manifest["files"]["battle_log"]["present"] = "true"
        manifest["files"]["battle_log"]["required"] = "true"

    _rewrite_manifest(dst, mutate)
    with pytest.raises(BundleValidationError) as exc:
        validate_bundle_dir(dst)
    assert exc.value.reason == "malformed_type"

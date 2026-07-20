from __future__ import annotations

import inspect
import os
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.export_bundle import export_bundle

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"


def _kwargs(out: Path):
    return dict(
        out=out,
        battle_log=FIX01 / "battle.log",
        decision_trace=FIX01 / "decision_trace.jsonl",
        results=FIX01 / "results.jsonl",
    )


def test_refuse_leaves_no_out_dir(tmp_path):
    out = tmp_path / "bundle"

    def boom(*args, **kwargs):
        raise OSError("nope")

    with pytest.raises(ExportRefuse):
        export_bundle(**_kwargs(out), replace_fn=boom)
    assert not out.exists()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_exception_leaves_no_out_or_staging(tmp_path, monkeypatch):
    out = tmp_path / "bundle"

    def fail_validate(path):
        raise RuntimeError("boom")

    monkeypatch.setattr("showdownbot_studio_exporter.export_bundle.validate_bundle_dir", fail_validate)
    with pytest.raises(RuntimeError):
        export_bundle(**_kwargs(out))
    assert not out.exists()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_success_out_is_complete_bundle(tmp_path):
    out = tmp_path / "bundle"
    export_bundle(**_kwargs(out))
    assert out.is_dir()
    assert (out / "manifest.json").is_file()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_no_file_by_file_publish_api():
    from showdownbot_studio_exporter import export_bundle as mod

    public = [n for n, fn in inspect.getmembers(mod, inspect.isfunction) if not n.startswith("_")]
    assert "publish_file" not in public
    assert "export_bundle" in public


def test_atomic_publish_unsupported_refuses_clean(tmp_path):
    out = tmp_path / "bundle"

    def boom(src, dst):
        raise OSError("cross-device")

    with pytest.raises(ExportRefuse) as exc:
        export_bundle(**_kwargs(out), replace_fn=boom)
    assert exc.value.reason == "atomic_publish_unsupported"
    assert not out.exists()


def test_failed_replace_does_not_delete_foreign_out(tmp_path):
    """Exporter owns staging only; a raced/foreign --out must survive failure."""
    out = tmp_path / "bundle"

    def boom(src, dst: Path):
        dst.mkdir()
        (dst / "foreign.txt").write_text("keep-me", encoding="utf-8")
        raise OSError("replace failed after foreign out appeared")

    with pytest.raises(ExportRefuse) as exc:
        export_bundle(**_kwargs(out), replace_fn=boom)
    assert exc.value.reason == "atomic_publish_unsupported"
    assert out.is_dir()
    assert (out / "foreign.txt").read_text(encoding="utf-8") == "keep-me"
    assert not list(tmp_path.glob(".*.staging-*"))

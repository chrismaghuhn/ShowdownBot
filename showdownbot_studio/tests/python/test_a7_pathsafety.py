from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import REPO_ROOT, STUDIO_ROOT

from showdownbot_studio_exporter.errors import ExportRefuse
from showdownbot_studio_exporter.pathsafety import check_output_path

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"


@pytest.mark.skipif(sys.platform != "win32", reason="case-variant test mandatory on Windows")
def test_refuse_out_under_data_eval_case_variant(tmp_path):
    out = REPO_ROOT / "DATA" / "EVAL" / "evil-bundle"
    with pytest.raises(ExportRefuse) as exc:
        check_output_path(out, input_paths=[FIX01 / "battle.log"], repo_root=REPO_ROOT)
    assert exc.value.reason == "output_inside_protected_tree"


def test_refuse_out_via_symlink_or_junction_to_sources(tmp_path):
    if sys.platform != "win32":
        pytest.skip("symlink privilege required")
    link = tmp_path / "link-out"
    target = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"cannot create symlink: {exc}")
    out = link / "bundle"
    with pytest.raises(ExportRefuse):
        check_output_path(out.resolve(), input_paths=[FIX01 / "battle.log"], repo_root=REPO_ROOT)


def test_refuse_out_via_symlink_to_data_eval(tmp_path):
    if sys.platform != "win32":
        pytest.skip("symlink privilege required")
    link = tmp_path / "eval-link"
    try:
        os.symlink(REPO_ROOT / "data" / "eval", link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"cannot create symlink: {exc}")
    out = link / "evil" / "bundle"
    with pytest.raises(ExportRefuse):
        check_output_path(out.resolve(), input_paths=[FIX01 / "battle.log"], repo_root=REPO_ROOT)

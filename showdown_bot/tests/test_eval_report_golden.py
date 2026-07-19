"""T5 Task 6: golden report against the committed T4-rerun fixture.

Spec: docs/projects/evaluation/specs/2026-07-10-t5-report-generator-design.md R5 (determinism) + R7
(golden fixture as drift guard). ``data/eval/t4/rerun/golden-report.md`` and
``golden-report.json`` were generated once via the ``eval-report`` CLI (T5 Task 5) against the
committed run-1 bundle in ``data/eval/t4/rerun/`` and inspected by hand (verdict
``SINGLE-RUN SAFETY-PASS``; per-cell win counts matching ``reports/2026-07-10-2b35-T4-rerun.md``:
heuristic 5/15, max_damage 2/15, simple_heuristic 1/9, greedy_protect 3/6, scripted_vgc 6/6;
provenance run_id 77993ce0cc2ba67e, config_hash aeafb78a5beea9cd, panel_hash 760c1e5935fe0474).

This test regenerates the report through the SAME CLI entry point (``cli.run_eval_report``,
the exact code path that produced the golden files) TWICE into separate tmp directories and
asserts byte-identical equality against both committed golden files each time -- proving
``generate_report`` (and the ``eval-report`` CLI's own file-writing) is deterministic (R5) and
guarding the whole pipeline (stats -> pairing -> report -> CLI) against silent drift (R7).

``.gitattributes`` already has ``data/eval/t4/** -text`` covering these two new files, so they
are checked out LF-stable on every platform; files are read with ``rb`` here so the comparison
is byte-exact regardless.
"""
from __future__ import annotations

import types
from pathlib import Path

from showdown_bot import cli

_REPO_ROOT = Path(__file__).resolve().parents[2]          # <repo>/
_SB = Path(__file__).resolve().parents[1]                  # <repo>/showdown_bot/
_RERUN = _REPO_ROOT / "data" / "eval" / "t4" / "rerun"
_RESULTS = _RERUN / "t4rerun-run1.jsonl"
_SEEDLOG = _RERUN / "t4rerun-run1-seedlog.jsonl"
_SCHEDULE = _REPO_ROOT / "config" / "eval" / "schedules" / "t4_smoke_v001.yaml"
_PANEL = _REPO_ROOT / "config" / "eval" / "panels" / "panel_v001.yaml"
_GOLDEN_MD = _RERUN / "golden-report.md"
_GOLDEN_JSON = _RERUN / "golden-report.json"


def _args(out_dir):
    return types.SimpleNamespace(
        run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), run_b="", seedlog_b="",
        schedule=str(_SCHEDULE), panel=str(_PANEL), out=str(out_dir), mode="gate",
        teams_root=str(_SB),
    )


def _generate(out_dir) -> tuple[bytes, bytes]:
    cli.run_eval_report(_args(out_dir))
    return (out_dir / "report.md").read_bytes(), (out_dir / "report.json").read_bytes()


def test_golden_md_first_line_is_safety_pass_verdict():
    md_bytes = _GOLDEN_MD.read_bytes()
    first_line = md_bytes.split(b"\n", 1)[0]
    assert first_line == b"# VERDICT: SINGLE-RUN SAFETY-PASS"


def test_regenerated_report_byte_identical_to_golden_run1(tmp_path):
    md_bytes, json_bytes = _generate(tmp_path / "run1")
    assert md_bytes == _GOLDEN_MD.read_bytes()
    assert json_bytes == _GOLDEN_JSON.read_bytes()


def test_regenerated_report_byte_identical_to_golden_run2(tmp_path):
    """Second independent regeneration (R5 determinism): a fresh process-level call, into a
    separate tmp directory, must reproduce the exact same bytes as the first."""
    md_bytes, json_bytes = _generate(tmp_path / "run2")
    assert md_bytes == _GOLDEN_MD.read_bytes()
    assert json_bytes == _GOLDEN_JSON.read_bytes()


def test_two_regenerations_are_byte_identical_to_each_other(tmp_path):
    md1, json1 = _generate(tmp_path / "a")
    md2, json2 = _generate(tmp_path / "b")
    assert md1 == md2
    assert json1 == json2

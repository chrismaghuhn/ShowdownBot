"""Tests for the `eval-report` CLI subcommand (T5 Task 5).

Spec: docs/superpowers/specs/2026-07-10-t5-report-generator-design.md §1.4 — CLI shape,
manifest-sidecar convention, exit codes (0 for SAFETY-PASS/GO/NO-GO/UNDERPOWERED, 1 iff
SAFETY-FAIL). There is no existing subprocess-based CLI test in this repo (checked: no test
imports `showdown_bot.cli` and drives it via subprocess); the project's convention (see
test_gauntlet_dispatch.py etc.) is to call functions directly with a hand-built args object.
We follow that here: `cli.run_eval_report(args)` is called with a `types.SimpleNamespace`
shaped like the `argparse.Namespace` `main()` would build, and — for one test — through
`cli.main()` itself with `sys.argv` patched, to prove the argparse wiring (the new flags +
the "eval-report" command choice) is actually connected.
"""
from __future__ import annotations

import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from showdown_bot import cli
from showdown_bot.eval import report as report_mod

_REPO_ROOT = Path(__file__).resolve().parents[2]          # <repo>/
_SB = Path(__file__).resolve().parents[1]                  # <repo>/showdown_bot/
_RERUN = _REPO_ROOT / "data" / "eval" / "t4" / "rerun"
_RESULTS = _RERUN / "t4rerun-run1.jsonl"
_SEEDLOG = _RERUN / "t4rerun-run1-seedlog.jsonl"
_MANIFEST = _RERUN / "t4rerun-run1.jsonl.manifest.json"
_SCHEDULE = _REPO_ROOT / "config" / "eval" / "schedules" / "t4_smoke_v001.yaml"
_PANEL = _REPO_ROOT / "config" / "eval" / "panels" / "panel_v001.yaml"
_ROOM_RAW_RUN1 = _RERUN / "room_raw" / "run1"


def _args(**overrides):
    defaults = dict(
        run_a="", seedlog_a="", run_b="", seedlog_b="",
        schedule="", panel="", out="", mode="gate", teams_root=".", room_raw="",
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _copy_bundle(tmp_path):
    """Copy the fixture (results + sidecar + seedlog) into tmp_path; return (results, seedlog)."""
    results = tmp_path / "run1.jsonl"
    manifest = tmp_path / "run1.jsonl.manifest.json"   # resolves via <results>.manifest.json
    seedlog = tmp_path / "run1-seedlog.jsonl"
    shutil.copy(_RESULTS, results)
    shutil.copy(_MANIFEST, manifest)
    shutil.copy(_SEEDLOG, seedlog)
    return results, seedlog


# --- 1. real-fixture happy path -----------------------------------------------------------

def test_eval_report_real_fixture_writes_files_exit0(tmp_path):
    out = tmp_path / "out"
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB))
    cli.run_eval_report(args)   # must NOT raise SystemExit -> process exit code 0

    md_path, json_path = out / "report.md", out / "report.json"
    assert md_path.exists() and json_path.exists()
    md = md_path.read_text(encoding="utf-8")
    assert md.splitlines()[0] == "# VERDICT: SINGLE-RUN SAFETY-PASS"
    obj = json.loads(json_path.read_text(encoding="utf-8"))
    assert obj["verdict"] == "SINGLE-RUN SAFETY-PASS"
    assert obj["schema_version"] == 1


def test_eval_report_writes_utf8_lf_no_crlf(tmp_path):
    """Task 3's md contains non-ASCII (· / —); files must be utf-8 with \\n endings so
    Windows default encoding/newline translation cannot corrupt them or break Task 6's
    golden byte-comparison."""
    out = tmp_path / "out"
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB))
    cli.run_eval_report(args)
    for name in ("report.md", "report.json"):
        raw = (out / name).read_bytes()
        assert b"\r\n" not in raw, name
    md_text = (out / "report.md").read_bytes().decode("utf-8")
    assert "·" in md_text   # the "·" mode-line separator


def test_eval_report_mode_dev_accepted(tmp_path):
    out = tmp_path / "out"
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB), mode="dev")
    cli.run_eval_report(args)
    obj = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert obj["mode"] == "dev"
    assert obj["verdict"] == "SINGLE-RUN SAFETY-PASS"


# --- 2. tampered inputs -> exit 1 ----------------------------------------------------------

def test_eval_report_tampered_seedlog_exits_1(tmp_path):
    results, seedlog = _copy_bundle(tmp_path)
    lines = seedlog.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[3])
    rec["seed"] = "sodium," + "f" * 32
    lines[3] = json.dumps(rec, separators=(",", ":"))
    seedlog.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = tmp_path / "out"
    args = _args(run_a=str(results), seedlog_a=str(seedlog), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB))
    with pytest.raises(SystemExit) as excinfo:
        cli.run_eval_report(args)
    assert excinfo.value.code == 1
    # the report IS still written -- SAFETY-FAIL is a verdict, not a crash
    md = (out / "report.md").read_text(encoding="utf-8")
    assert md.splitlines()[0] == "# VERDICT: SINGLE-RUN SAFETY-FAIL"


def test_eval_report_load_time_input_error_exits_1(tmp_path):
    """A ReportInputError at load time (missing manifest sidecar) becomes a clean
    SystemExit(1), matching the report module's own SAFETY-FAIL exit code rather than an
    uncaught traceback."""
    dst = tmp_path / "run.jsonl"
    shutil.copy(_RESULTS, dst)   # deliberately no manifest sidecar copied
    args = _args(run_a=str(dst), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(tmp_path / "out"), teams_root=str(_SB))
    with pytest.raises(SystemExit) as excinfo:
        cli.run_eval_report(args)
    assert excinfo.value.code == 1


# --- 3. argument validation -----------------------------------------------------------------

def test_eval_report_run_b_without_seedlog_b_raises(tmp_path):
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(tmp_path / "out"), teams_root=str(_SB),
                 run_b=str(_RESULTS))   # seedlog_b left empty
    with pytest.raises(SystemExit):
        cli.run_eval_report(args)


def test_eval_report_seedlog_b_without_run_b_raises(tmp_path):
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(tmp_path / "out"), teams_root=str(_SB),
                 seedlog_b=str(_SEEDLOG))
    with pytest.raises(SystemExit):
        cli.run_eval_report(args)


def test_eval_report_missing_run_a_raises():
    args = _args(seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE), panel=str(_PANEL),
                 out="ignored", teams_root=str(_SB))
    with pytest.raises(SystemExit):
        cli.run_eval_report(args)


def test_eval_report_missing_out_raises():
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), teams_root=str(_SB))
    with pytest.raises(SystemExit):
        cli.run_eval_report(args)


def test_eval_report_missing_schedule_raises():
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), panel=str(_PANEL),
                 out="ignored", teams_root=str(_SB))
    with pytest.raises(SystemExit):
        cli.run_eval_report(args)


def test_eval_report_missing_panel_raises():
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 out="ignored", teams_root=str(_SB))
    with pytest.raises(SystemExit):
        cli.run_eval_report(args)


# --- 4. argparse wiring end-to-end (proves "eval-report" + the new flags are connected) ----

def test_main_dispatches_eval_report_end_to_end(tmp_path, monkeypatch):
    out = tmp_path / "out"
    argv = ["prog", "eval-report", "--run-a", str(_RESULTS), "--seedlog-a", str(_SEEDLOG),
            "--schedule", str(_SCHEDULE), "--panel", str(_PANEL), "--out", str(out),
            "--teams-root", str(_SB)]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()   # must not raise -> exit code 0
    assert (out / "report.md").exists()
    assert (out / "report.json").exists()


def test_main_eval_report_default_mode_is_gate(tmp_path, monkeypatch):
    out = tmp_path / "out"
    argv = ["prog", "eval-report", "--run-a", str(_RESULTS), "--seedlog-a", str(_SEEDLOG),
            "--schedule", str(_SCHEDULE), "--panel", str(_PANEL), "--out", str(out),
            "--teams-root", str(_SB)]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    obj = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert obj["mode"] == "gate"


def test_main_eval_report_rejects_bad_mode_choice(tmp_path, monkeypatch, capsys):
    argv = ["prog", "eval-report", "--run-a", str(_RESULTS), "--seedlog-a", str(_SEEDLOG),
            "--schedule", str(_SCHEDULE), "--panel", str(_PANEL), "--out", str(tmp_path / "out"),
            "--teams-root", str(_SB), "--mode", "bogus"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2   # argparse's own invalid-choice exit code


# --- 5. paired-mode CLI wiring (lighter seam, documented) -----------------------------------
#
# Building a second full file-based run (JSONL + seedlog + schedule that pairs cleanly against
# the real T4-rerun fixture) is disproportionate for a CLI-plumbing test: the McNemar
# statistics/verdict tree is already exhaustively covered against synthetic RunBundle objects
# in tests/test_eval_report_paired.py, and the paired-reproduction content itself is proven
# there too (test_paired_reproduction_lists_both_runs). Here `RunBundle.load` is monkeypatched
# to hand back two pre-built synthetic bundles, so the only thing under test is that the CLI's
# --run-b/--seedlog-b plumbing actually reaches `generate_report`'s PAIRED branch (two loads,
# `obj["paired"] is True`, the paired section renders) -- not the statistics themselves.

def _synth_row(seed_index, *, config_hash, run_id, winner):
    return {
        "battle_id": f"b{seed_index}", "config_hash": config_hash, "config_id": "cand",
        "schedule_hash": "schX", "seed_base": "baseX", "panel_hash": "panX", "run_id": run_id,
        "git_sha": "gitX", "format_id": "gen9vgc2025regi", "seed_index": seed_index,
        "seed": f"sodium,{seed_index:032x}",
        "opp_policy": "heuristic", "opp_team_hash": "h1", "hero_team_hash": "hero1",
        "panel_split": "dev", "winner": winner, "invalid_choices": 0, "crashes": 0,
        "decision_latency_p95_ms": 100, "end_reason": "normal", "dirty": False,
        "turns": 10, "end_hp_diff": 50,
    }


def _synth_bundle(rows, *, run_id, config_hash):
    manifest = {
        "run_id": run_id, "config_hash": config_hash, "schedule_hash": "schX",
        "seed_base": "baseX", "panel_hash": "panX", "git_sha": "gitX", "dirty": False,
        "start_ts": "2026-07-10T00:00:00+00:00", "cli_invocation": ["cli.py", "gauntlet"],
        "pythonhashseed": "0",
    }
    return report_mod.RunBundle(
        rows=rows, manifest=manifest, recomputed_panel_hash="panX",
        panel_dev_hashes=frozenset({"h1"}), panel_held_hashes=frozenset(),
        team_path_by_hash={"h1": "teams/h1.txt"},
        schedule_row_count=len(rows), schedule_reproducible=True,
        alignment_ok=True, alignment_detail=f"{len(rows)} contiguous, derived",
        latency_budget_ms=1000, git_sha="gitX",
        input_sha256={r: "0" * 64 for r in ("results", "seedlog", "schedule", "panel", "manifest")},
        input_basenames={r: f"{r}.x" for r in ("results", "seedlog", "schedule", "panel", "manifest")},
    )


def test_eval_report_paired_cli_wiring_lighter_seam(tmp_path, monkeypatch):
    rows_a = [_synth_row(i, config_hash="cfgA", run_id="runA", winner="hero") for i in range(12)]
    rows_b = [_synth_row(i, config_hash="cfgB", run_id="runB", winner="villain") for i in range(12)]
    bundle_a = _synth_bundle(rows_a, run_id="runA", config_hash="cfgA")
    bundle_b = _synth_bundle(rows_b, run_id="runB", config_hash="cfgB")
    calls: list = []

    def _fake_load(cls, results_path, seedlog_path, schedule_path, panel_path, *,
                   teams_root, manifest_path=None, room_raw_dir=None):
        calls.append(results_path)
        return bundle_a if len(calls) == 1 else bundle_b

    monkeypatch.setattr(report_mod.RunBundle, "load", classmethod(_fake_load))

    out = tmp_path / "out"
    args = _args(run_a="dummy-a.jsonl", seedlog_a="dummy-a-seedlog.jsonl",
                run_b="dummy-b.jsonl", seedlog_b="dummy-b-seedlog.jsonl",
                schedule="dummy.yaml", panel="dummy-panel.yaml", out=str(out))
    cli.run_eval_report(args)   # 12/12 discordant, A always wins -> GO -> no SystemExit

    assert calls == ["dummy-a.jsonl", "dummy-b.jsonl"]   # both --run-a/--run-b reached RunBundle.load
    md = (out / "report.md").read_text(encoding="utf-8")
    obj = json.loads((out / "report.json").read_text(encoding="utf-8"))
    # paired-report schema markers: run B's provenance/gates + the paired stats sub-dict
    assert "provenance_b" in obj and "safety_gates_b" in obj
    assert obj["paired"]["n_discordant"] == 12
    assert "## Paired McNemar (A vs B)" in md
    assert md.splitlines()[0].startswith("# VERDICT: GO")


# --- 6. --room-raw CLI wiring (T4c R2) -------------------------------------------------------

def _copy_bundle_with_room_raw(tmp_path):
    """Like ``_copy_bundle`` but also copies the committed ``room_raw/run1`` subset."""
    results, seedlog = _copy_bundle(tmp_path)
    room_raw = tmp_path / "room_raw"
    shutil.copytree(_ROOM_RAW_RUN1, room_raw)
    return results, seedlog, room_raw


def test_eval_report_room_raw_flag_clean_pass_exit0(tmp_path):
    out = tmp_path / "out"
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB),
                 room_raw=str(_ROOM_RAW_RUN1))
    cli.run_eval_report(args)   # must NOT raise -> exit code 0
    md = (out / "report.md").read_text(encoding="utf-8")
    assert md.splitlines()[0] == "# VERDICT: SINGLE-RUN SAFETY-PASS"


def test_eval_report_room_raw_omitted_still_works(tmp_path):
    """Default ('' / unset): the CLI's original behavior, untouched by T4c."""
    out = tmp_path / "out"
    args = _args(run_a=str(_RESULTS), seedlog_a=str(_SEEDLOG), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB))
    cli.run_eval_report(args)
    assert (out / "report.md").exists()


def test_eval_report_room_raw_tampered_row_raises_exit1(tmp_path):
    results, seedlog, room_raw = _copy_bundle_with_room_raw(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["end_reason"] = "crash"   # a wrong-but-valid enum value, real end_reason is "normal"
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = tmp_path / "out"
    args = _args(run_a=str(results), seedlog_a=str(seedlog), schedule=str(_SCHEDULE),
                 panel=str(_PANEL), out=str(out), teams_root=str(_SB), room_raw=str(room_raw))
    with pytest.raises(SystemExit) as excinfo:
        cli.run_eval_report(args)
    assert excinfo.value.code == 1
    # a LogIntegrityError is a load-time failure -- no report is written (unlike a SAFETY-FAIL
    # verdict, which still writes a report; see test_eval_report_tampered_seedlog_exits_1).
    assert not (out / "report.md").exists()


def test_main_dispatches_room_raw_flag_end_to_end(tmp_path, monkeypatch):
    """Proves the --room-raw argparse flag is actually wired to RunBundle.load, not just
    accepted and ignored."""
    out = tmp_path / "out"
    argv = ["prog", "eval-report", "--run-a", str(_RESULTS), "--seedlog-a", str(_SEEDLOG),
            "--schedule", str(_SCHEDULE), "--panel", str(_PANEL), "--out", str(out),
            "--teams-root", str(_SB), "--room-raw", str(_ROOM_RAW_RUN1)]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()   # must not raise -> exit code 0
    assert (out / "report.md").exists()


def test_main_room_raw_flag_end_to_end_detects_tampering(tmp_path, monkeypatch):
    results, seedlog, room_raw = _copy_bundle_with_room_raw(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["turns"] = row["turns"] + 1
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = tmp_path / "out"
    argv = ["prog", "eval-report", "--run-a", str(results), "--seedlog-a", str(seedlog),
            "--schedule", str(_SCHEDULE), "--panel", str(_PANEL), "--out", str(out),
            "--teams-root", str(_SB), "--room-raw", str(room_raw)]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 1

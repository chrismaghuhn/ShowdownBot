"""Tests for eval/report.py part 1 — RunBundle audit, safety gates, single-run report (T5 Task 3).

Spec: docs/superpowers/specs/2026-07-10-t5-report-generator-design.md §1.3 / §2 / §3
(R3, R5, R6, R7). Rationale: docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-
architecture-review.md §5/§8.

R6 documented deviation (see ``test_winner_flip_is_undetectable_documents_deviation``):
a *pure winner flip* in a result row is NOT detectable by any input-hash cross-check — the
run manifest carries no per-row integrity hash, and the spec's audit list (§1.3) does not
re-parse ``room_raw``. So the spec's R6 "edited result row (winner flipped)" line is
unsatisfiable as written. This slice instead recomputes ``battle_id`` and the deterministic
per-row ``seed`` derivation as a hard audit, and exercises the "edited result row" tamper
case via a SEED edit (which IS detectable). The controller should amend the spec's winner-flip
wording; see the report-back.

UPDATE (T4c R3, ``docs/superpowers/specs/2026-07-11-t4c-provenance-hardening-design.md``): the
deviation above holds only on the no-logs path. ``test_winner_flip_is_detected_with_room_raw_logs``
is the inverted twin — same flip, but with ``room_raw_dir`` supplied — and IS caught via
``LogIntegrityError``. See also ``test_eval_report_log_integrity.py`` (T4c Task 2).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from showdown_bot.eval.report import (
    HELDOUT_BANNER,
    SCHEMA_VERSION,
    UNDERPOWERED_TEXT,
    LogIntegrityError,
    ReportInputError,
    RunBundle,
    SafetyGate,
    generate_report,
    run_safety_gates,
)
from showdown_bot.eval.stats import wilson_interval

_REPO_ROOT = Path(__file__).resolve().parents[2]          # <repo>/
_SB = Path(__file__).resolve().parents[1]                  # <repo>/showdown_bot/
_RERUN = _REPO_ROOT / "data" / "eval" / "t4" / "rerun"
_RESULTS = _RERUN / "t4rerun-run1.jsonl"
_SEEDLOG = _RERUN / "t4rerun-run1-seedlog.jsonl"
_MANIFEST = _RERUN / "t4rerun-run1.jsonl.manifest.json"
_SCHEDULE = _REPO_ROOT / "config" / "eval" / "schedules" / "t4_smoke_v001.yaml"
_PANEL = _REPO_ROOT / "config" / "eval" / "panels" / "panel_v001.yaml"
_ROOM_RAW_RUN1 = _RERUN / "room_raw" / "run1"

# Team content hashes (pinned by the fixture / task brief).
_TRICKROOM = "e622869d6c68307e"
_SUN = "b0048ae65f0e9ee5"
_RAIN = "69f471c2740f1927"


def _load_fixture() -> RunBundle:
    return RunBundle.load(
        str(_RESULTS), str(_SEEDLOG), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB)
    )


# --- 1. RunBundle load + input audit ----------------------------------------------------

def test_runbundle_loads_real_fixture_clean():
    b = _load_fixture()
    assert len(b.rows) == 51
    assert b.schedule_row_count == 51
    assert b.recomputed_panel_hash == "760c1e5935fe0474"
    assert b.alignment_ok is True
    assert b.schedule_reproducible is True
    # provenance constants pulled from rows/manifest
    assert b.manifest["run_id"] == "77993ce0cc2ba67e"
    assert b.manifest["config_hash"] == "aeafb78a5beea9cd"
    assert b.manifest["seed_base"] == "t4rerun2026"
    # every input file sha256 recorded (64 hex chars each)
    for role in ("results", "seedlog", "schedule", "panel", "manifest"):
        h = b.input_sha256[role]
        assert isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_runbundle_load_missing_manifest_raises(tmp_path):
    dst = tmp_path / "run.jsonl"
    shutil.copy(_RESULTS, dst)
    # deliberately DO NOT copy the sidecar
    with pytest.raises(ReportInputError):
        RunBundle.load(str(dst), str(_SEEDLOG), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB))


# --- 2. Safety gates on the fixture -----------------------------------------------------

def test_safety_gates_all_pass_on_fixture():
    b = _load_fixture()
    gates = run_safety_gates(b, mode="gate")
    assert all(isinstance(g, SafetyGate) for g in gates)
    assert all(g.status == "PASS" for g in gates), [
        (g.gate, g.status, g.measured) for g in gates if g.status != "PASS"
    ]
    by_name = {g.gate: g for g in gates}
    # spec §1.3 gate list is present
    for name in (
        "invalid_choices", "crashes", "end_reason_normal", "latency_p95", "dirty",
        "panel_hash_match", "seed_log_alignment", "reproducible_policies",
        "rows_match_schedule", "no_duplicate_rows", "split_integrity",
        "one_config_hash", "one_schedule_hash",
    ):
        assert name in by_name, name
    # measured values are carried, not just PASS/FAIL
    assert "216" in by_name["latency_p95"].measured and "1000" in by_name["latency_p95"].measured
    assert "51 == 51" in by_name["rows_match_schedule"].measured
    assert "760c1e5935fe0474" in by_name["panel_hash_match"].measured


# --- 3. generate_report single-run PASS -------------------------------------------------

def test_generate_report_verdict_and_section_order():
    b = _load_fixture()
    md, obj = generate_report(b, mode="gate")
    assert md.splitlines()[0] == "# VERDICT: SINGLE-RUN SAFETY-PASS"
    # sections in the spec's fixed order
    order = ["## Provenance", "## Safety Gates", "## Per-Cell Results",
             "## Aggregates", "## Warnings", "## Reproduction"]
    positions = [md.index(h) for h in order]
    assert positions == sorted(positions), positions
    assert obj["schema_version"] == SCHEMA_VERSION == 1
    assert obj["verdict"] == "SINGLE-RUN SAFETY-PASS"
    assert obj["paired"] is False
    # no GO/NO-GO vocabulary anywhere in a single-run report
    assert "GO" not in md.replace("SAFETY", "")  # crude but effective; SAFETY masked out
    assert obj["verdict"] not in ("GO", "NO-GO")


def test_generate_report_per_cell_spot_checks():
    b = _load_fixture()
    _, obj = generate_report(b, mode="gate")
    cells = {(c["opp_policy"], c["opp_team_hash"]): c for c in obj["cells"]}
    # scripted_vgc × rain = 2 wins / 2 games
    sv = cells[("scripted_vgc", _RAIN)]
    assert (sv["n"], sv["wins"], sv["losses"], sv["ties"]) == (2, 2, 0, 0)
    assert sv["win_rate"] == pytest.approx(1.0)
    # heuristic × sun = 0 wins / 5 games, Wilson bounds from stats.wilson_interval
    hs = cells[("heuristic", _SUN)]
    assert (hs["n"], hs["wins"]) == (5, 0)
    lo, hi = wilson_interval(0, 5)
    assert hs["wilson_lo"] == pytest.approx(lo)
    assert hs["wilson_hi"] == pytest.approx(hi)
    assert hi == pytest.approx(0.4345, abs=1e-3)
    # a 0/5 cell is a "losing cell" (wilson upper < 0.5)
    assert hs["losing"] is True


def test_generate_report_lists_losing_cells_descriptively():
    b = _load_fixture()
    _, obj = generate_report(b, mode="gate")
    losing = set(tuple(x) for x in obj["aggregates"]["losing_cells"])
    assert ("heuristic", _RAIN) in losing
    assert ("heuristic", _SUN) in losing
    assert ("max_damage", _RAIN) in losing
    # a clearly-winning cell is NOT flagged losing
    assert ("scripted_vgc", _RAIN) not in losing


# --- 4. Determinism (R5) ----------------------------------------------------------------

def test_generate_report_is_deterministic():
    b = _load_fixture()
    md1, obj1 = generate_report(b, mode="gate")
    md2, obj2 = generate_report(b, mode="gate")
    assert md1 == md2
    assert json.dumps(obj1, sort_keys=True) == json.dumps(obj2, sort_keys=True)
    # no wall-clock timestamp leaked in: the only ISO time is the manifest's start_ts
    assert b.manifest["start_ts"] in md1


# --- 5. Tamper tests (R6) ---------------------------------------------------------------

def _copy_bundle(tmp_path):
    """Copy the fixture (results + sidecar + seedlog) into tmp_path; return the paths."""
    results = tmp_path / "run1.jsonl"
    manifest = tmp_path / "run1.jsonl.manifest.json"   # resolves via <results>.manifest.json
    seedlog = tmp_path / "run1-seedlog.jsonl"
    shutil.copy(_RESULTS, results)
    shutil.copy(_MANIFEST, manifest)
    shutil.copy(_SEEDLOG, seedlog)
    return results, seedlog


def test_tamper_edited_result_row_seed_raises(tmp_path):
    """R6 'edited result row': a mutated ``seed`` breaks the recomputed battle_id AND the
    deterministic seed derivation, so load refuses with ReportInputError."""
    results, seedlog = _copy_bundle(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["seed"] = "sodium," + "0" * 32   # plausible-looking but wrong seed
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ReportInputError):
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB))


def test_tamper_edited_seedlog_line_fails_safety(tmp_path):
    """R6 'mutated seed-log line': verify_schedule_alignment no longer matches the derivation,
    so the seed_log_alignment gate FAILs → SINGLE-RUN SAFETY-FAIL (no strength claim)."""
    results, seedlog = _copy_bundle(tmp_path)
    lines = seedlog.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[3])
    rec["seed"] = "sodium," + "f" * 32
    lines[3] = json.dumps(rec, separators=(",", ":"))
    seedlog.write_text("\n".join(lines) + "\n", encoding="utf-8")
    b = RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB))
    md, obj = generate_report(b, mode="gate")
    assert obj["verdict"] == "SINGLE-RUN SAFETY-FAIL"
    assert md.splitlines()[0] == "# VERDICT: SINGLE-RUN SAFETY-FAIL"
    gate = {g.gate: g for g in run_safety_gates(b, mode="gate")}["seed_log_alignment"]
    assert gate.status == "FAIL"


def test_tamper_swapped_panel_fails_safety(tmp_path):
    """R6 'panel file whose hash no longer matches rows': recomputed panel_hash != rows' →
    panel_hash_match gate FAIL → SAFETY-FAIL (or a load-time ReportInputError). Either is
    acceptable per R6 as long as no strength output is produced."""
    results, seedlog = _copy_bundle(tmp_path)
    text = _PANEL.read_text(encoding="utf-8")
    # swap two dev teams' paths -> different per-team tuples -> different panel_hash
    swapped = (text.replace("teams/panel_v001/sun_dev.txt", "__TMP__")
                   .replace("teams/panel_v001/rain_dev.txt", "teams/panel_v001/sun_dev.txt")
                   .replace("__TMP__", "teams/panel_v001/rain_dev.txt"))
    panel = tmp_path / "panel_swapped.yaml"
    panel.write_text(swapped, encoding="utf-8")
    try:
        b = RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(panel), teams_root=str(_SB))
    except ReportInputError:
        return  # acceptable per R6
    _, obj = generate_report(b, mode="gate")
    assert obj["verdict"] == "SINGLE-RUN SAFETY-FAIL"
    assert b.recomputed_panel_hash != "760c1e5935fe0474"


def test_winner_flip_is_undetectable_documents_deviation(tmp_path):
    """DOCUMENTED DEVIATION (R6 winner-flip line is unsatisfiable as written) -- WITHOUT LOGS.

    A pure winner flip changes no field that any input-hash cross-check covers: the manifest
    has no per-row integrity hash and the audit does not re-parse room_raw. So the bundle
    still loads clean and the report still says SAFETY-PASS. This test PINS that limitation so
    a future room_raw-parsing audit (which would flip this) forces a spec amendment rather than
    silently changing behaviour. The seed-edit test above is the real 'edited row' guard.

    Without logs: undetectable — see ``test_winner_flip_is_detected_with_room_raw_logs``
    immediately below for the logs-present inversion (T4c R3, same tamper, real fixture
    room_raw supplied via ``room_raw_dir``)."""
    results, seedlog = _copy_bundle(tmp_path)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    assert row["winner"] == "hero"
    row["winner"] = "villain"                        # flip, nothing else touched
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")
    b = RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL), teams_root=str(_SB))
    _, obj = generate_report(b, mode="gate")
    assert obj["verdict"] == "SINGLE-RUN SAFETY-PASS"   # NOT caught — documented gap


def test_winner_flip_is_detected_with_room_raw_logs(tmp_path):
    """INVERSION of the pin above (T4c R3): the identical winner-flip tamper, but with
    ``room_raw_dir`` supplied at load time, IS caught -- via ``LogIntegrityError`` naming the
    exact offending row. This is the "future room_raw-parsing audit" the pin above anticipated;
    now that it exists (T4c Task 2: ``RunBundle.load(..., room_raw_dir=...)``), the no-logs
    limitation documented above is scoped precisely to the absence of ``--room-raw``.

    See docs/superpowers/specs/2026-07-11-t4c-provenance-hardening-design.md R3 and
    test_eval_report_log_integrity.py::test_log_integrity_tampered_winner_raises (the Task 2
    preview of this same check)."""
    results, seedlog = _copy_bundle(tmp_path)
    room_raw = tmp_path / "room_raw"
    shutil.copytree(_ROOM_RAW_RUN1, room_raw)
    lines = results.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    assert row["winner"] == "hero"
    row["winner"] = "villain"                        # same flip, nothing else touched
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    results.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LogIntegrityError) as excinfo:
        RunBundle.load(str(results), str(seedlog), str(_SCHEDULE), str(_PANEL),
                       teams_root=str(_SB), room_raw_dir=str(room_raw))
    msg = str(excinfo.value)
    assert f"seed_index={row['seed_index']}" in msg
    assert row["battle_id"] in msg
    assert "winner mismatch" in msg
    assert "row='villain'" in msg
    assert "recomputed='hero'" in msg


# --- 6. mode="dev" vs "gate": latency + dirty split -------------------------------------

def _synthetic_row(seed_index, *, winner="hero", dirty=False, latency=100, crashes=0,
                   invalid=0, end_reason="normal", opp_policy="heuristic",
                   opp_team_hash="dev1", panel_split="dev"):
    return {
        "battle_id": f"b{seed_index}", "config_hash": "cfgS", "config_id": "heuristic",
        "schedule_hash": "schS", "seed_base": "baseS", "panel_hash": "panS", "run_id": "runS",
        "git_sha": "gitS", "format_id": "gen9vgc2025regi", "seed_index": seed_index,
        "opp_policy": opp_policy, "opp_team_hash": opp_team_hash, "hero_team_hash": "hero1",
        "panel_split": panel_split, "winner": winner, "invalid_choices": invalid,
        "crashes": crashes, "decision_latency_p95_ms": latency, "end_reason": end_reason,
        "dirty": dirty,
    }


def _synthetic_bundle(rows, *, budget=200):
    manifest = {
        "run_id": "runS", "config_hash": "cfgS", "schedule_hash": "schS",
        "seed_base": "baseS", "panel_hash": "panS", "git_sha": "gitS", "dirty": rows[0]["dirty"],
        "start_ts": "2026-07-10T00:00:00+00:00", "cli_invocation": ["cli.py", "gauntlet"],
        "pythonhashseed": "0",
    }
    return RunBundle(
        rows=rows, manifest=manifest, recomputed_panel_hash="panS",
        panel_dev_hashes=frozenset({"dev1"}), panel_held_hashes=frozenset({"held1"}),
        team_path_by_hash={"dev1": "teams/dev1.txt"},
        schedule_row_count=len(rows), schedule_reproducible=True,
        alignment_ok=True, alignment_detail=f"{len(rows)} contiguous, derived",
        latency_budget_ms=budget, git_sha="gitS",
        input_sha256={r: "0" * 64 for r in ("results", "seedlog", "schedule", "panel", "manifest")},
        input_basenames={r: f"{r}.x" for r in ("results", "seedlog", "schedule", "panel", "manifest")},
    )


def test_dev_mode_downgrades_dirty_and_latency_to_warn():
    rows = [_synthetic_row(i, dirty=True, latency=999) for i in range(3)]
    b = _synthetic_bundle(rows, budget=200)
    gates = {g.gate: g for g in run_safety_gates(b, mode="dev")}
    assert gates["dirty"].status == "WARN"
    assert gates["latency_p95"].status == "WARN"
    _, obj = generate_report(b, mode="dev")
    assert obj["verdict"] == "SINGLE-RUN SAFETY-PASS"   # WARN never fails


def test_gate_mode_dirty_and_latency_are_fail():
    rows = [_synthetic_row(i, dirty=True, latency=999) for i in range(3)]
    b = _synthetic_bundle(rows, budget=200)
    gates = {g.gate: g for g in run_safety_gates(b, mode="gate")}
    assert gates["dirty"].status == "FAIL"
    assert gates["latency_p95"].status == "FAIL"
    _, obj = generate_report(b, mode="gate")
    assert obj["verdict"] == "SINGLE-RUN SAFETY-FAIL"


def test_dev_mode_other_failures_still_fail():
    # a crash row is a hard FAIL in BOTH modes (only latency+dirty are downgraded)
    rows = [_synthetic_row(0), _synthetic_row(1, crashes=1), _synthetic_row(2)]
    b = _synthetic_bundle(rows)
    gates = {g.gate: g for g in run_safety_gates(b, mode="dev")}
    assert gates["crashes"].status == "FAIL"
    _, obj = generate_report(b, mode="dev")
    assert obj["verdict"] == "SINGLE-RUN SAFETY-FAIL"


# --- verbatim-text constants exist (Task 4 relies on them) ------------------------------

def test_verbatim_constants_present():
    assert "UNDERPOWERED" in UNDERPOWERED_TEXT
    assert "must not be cited to unblock 2b-4" in UNDERPOWERED_TEXT
    assert "HELD-OUT RUN" in HELDOUT_BANNER
    assert "must never inform tuning decisions" in HELDOUT_BANNER

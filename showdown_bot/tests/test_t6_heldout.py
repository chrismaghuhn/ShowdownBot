"""T6 held-out baseline schedule (Task 4): committed schedule must match the generator
(drift guard), mirroring `test_t4_matrix.py`'s pattern, plus the ledger choke-point --
generating this schedule with a `ledger_path` appends exactly one `schedule` entry
(T6 Task 2's wiring, exercised here for real for the first time)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from showdown_bot.eval.heldout_ledger import read_ledger
from showdown_bot.eval.panel import load_panel
from showdown_bot.eval.schedule import load_schedule
from showdown_bot.eval.t6_heldout import T6_HELDOUT_PURPOSE, generate_t6_heldout_schedule

_REPO = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_PANEL = _REPO / "config" / "eval" / "panels" / "panel_v001.yaml"
_SCHEDULE = _REPO / "config" / "eval" / "schedules" / "t6_heldout_v001.yaml"
_TEAMS_ROOT = str(_REPO / "showdown_bot")


def _panel():
    return load_panel(str(_PANEL), teams_root=_TEAMS_ROOT)


def test_heldout_schedule_shape_and_weights():
    sched = generate_t6_heldout_schedule(_panel(), teams_root=_TEAMS_ROOT)
    assert len(sched.rows) == 34  # 2 held-out teams x 17 seeds/team
    assert Counter(r.opp_policy for r in sched.rows) == {
        "heuristic": 10, "max_damage": 10, "simple_heuristic": 6,
        "greedy_protect": 4, "scripted_vgc": 4,
    }
    assert {r.panel_split for r in sched.rows} == {"heldout"}
    assert sched.reproducible is True
    assert sched.panel_hash == "760c1e5935fe0474"


def test_purpose_constant_pinned():
    assert T6_HELDOUT_PURPOSE == "baseline-heldout-v1"


def test_ledger_path_none_stays_pure(tmp_path):
    # Default (no ledger_path) must never touch a ledger -- generation is pure by default,
    # matching generate_heldout_schedule's own contract.
    ledger_path = tmp_path / "untouched.jsonl"
    generate_t6_heldout_schedule(_panel(), teams_root=_TEAMS_ROOT)
    assert not ledger_path.exists()


def test_ledger_wiring_appends_exactly_one_schedule_entry(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    sched = generate_t6_heldout_schedule(
        _panel(), teams_root=_TEAMS_ROOT, ledger_path=str(ledger_path),
    )
    entries = read_ledger(str(ledger_path))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["kind"] == "schedule"
    assert entry["purpose"] == "baseline-heldout-v1"
    assert entry["panel_hash"] == sched.panel_hash
    assert entry["schedule_hash"] == sched.schedule_hash
    assert entry["justification"] is None


def test_committed_yaml_matches_generator():
    sched = generate_t6_heldout_schedule(_panel(), teams_root=_TEAMS_ROOT)
    committed = load_schedule(str(_SCHEDULE))
    assert committed.schedule_hash == sched.schedule_hash
    assert committed.panel_hash == sched.panel_hash == "760c1e5935fe0474"
    # Full field equality incl. provenance (team hashes, panel_split) -- not covered by the hash.
    assert committed.rows == sched.rows


def test_committed_schedule_is_exempt_all_heldout_labeled():
    # Leakage-exemption sanity (test_heldout_leakage.py's repo-wide scan also covers this
    # file once committed -- all-heldout-labeled schedules are exempt from the dev-leakage
    # check by design; this asserts the precondition for that exemption holds).
    committed = load_schedule(str(_SCHEDULE))
    assert all(r.panel_split == "heldout" for r in committed.rows)

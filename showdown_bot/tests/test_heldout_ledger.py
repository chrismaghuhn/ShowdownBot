"""T6 Task 1: held-out ledger — round-trip API, shape validation, access budget,
append-only git-history enforcement (spec §1, review §6)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from showdown_bot.eval.heldout_ledger import (
    AccessBudgetError,
    LedgerError,
    append_entry,
    check_access,
    read_ledger,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_LEDGER_REL_PATH = "config/eval/heldout_ledger.jsonl"


def _schedule_entry(**over) -> dict:
    kw = dict(
        kind="schedule", date="2026-07-10", purpose="baseline-heldout-v1",
        panel_hash="760c1e5935fe0474", schedule_hash="a7f000867fdfbde0",
        git_sha="deadbeef", justification=None,
    )
    kw.update(over)
    return kw


def _run_entry(**over) -> dict:
    kw = dict(
        kind="run", date="2026-07-10", purpose="baseline-heldout-v1",
        panel_hash="760c1e5935fe0474", schedule_hash="a7f000867fdfbde0",
        config_hash="aeafb78a5beea9cd", git_sha="deadbeef",
        result_sha256="f" * 64, justification=None,
    )
    kw.update(over)
    return kw


# --- round-trip / append semantics -------------------------------------------------------

def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    sched = _schedule_entry()
    run = _run_entry()
    append_entry(str(path), sched)
    append_entry(str(path), run)
    entries = read_ledger(str(path))
    assert entries == [sched, run]  # both kinds, order preserved


def test_append_is_literal_file_append(tmp_path):
    path = tmp_path / "ledger.jsonl"
    append_entry(str(path), _schedule_entry())
    prefix = path.read_bytes()
    append_entry(str(path), _run_entry())
    after = path.read_bytes()
    assert after.startswith(prefix)  # existing bytes untouched
    assert len(after) > len(prefix)


def test_malformed_line_fails_fast(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"kind": "schedule", not valid json\n', encoding="utf-8")
    with pytest.raises(LedgerError):
        read_ledger(str(path))


def test_missing_required_field_rejected(tmp_path):
    path = tmp_path / "ledger.jsonl"
    entry = _schedule_entry()
    del entry["git_sha"]
    with pytest.raises(LedgerError):
        append_entry(str(path), entry)
    assert not path.exists()  # fail fast before writing — never a half-written ledger


def test_read_missing_ledger_returns_empty_list(tmp_path):
    # The ledger legitimately doesn't exist before the first held-out access.
    assert read_ledger(str(tmp_path / "does_not_exist.jsonl")) == []


# --- access budget -------------------------------------------------------------------------

def test_check_access_first_time_ok():
    entries = [_schedule_entry()]
    assert check_access(entries, "aeafb78a5beea9cd") is None


def test_check_access_second_run_same_config_refused():
    entries = [_run_entry(config_hash="cfg16")]
    with pytest.raises(AccessBudgetError):
        check_access(entries, "cfg16")


def test_check_access_with_justification_ok():
    entries = [_run_entry(config_hash="cfg16")]
    assert check_access(entries, "cfg16", justification="reproduction re-run, same session") is None


def test_check_access_schedule_entries_dont_consume_budget():
    entries = [_schedule_entry(), _schedule_entry()]
    assert check_access(entries, "aeafb78a5beea9cd") is None


# --- git-history append-only enforcement ----------------------------------------------------

def test_ledger_git_history_append_only():
    try:
        result = subprocess.run(
            ["git", "log", "--follow", "-p", "--", _LEDGER_REL_PATH],
            cwd=str(_REPO_ROOT), capture_output=True, text=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git unavailable")
    output = result.stdout
    if not output.strip():
        pytest.skip("ledger not yet in git history")
    # Conservative parser: ANY line starting with '-' that is not a diff header ('---')
    # is treated as a removal/modification of a prior line -> fail. Commit-message body
    # lines are indented 4 spaces by `git log`, so a message bullet like "- fixed X" never
    # starts at column 0 and cannot false-positive here.
    for lineno, line in enumerate(output.splitlines(), start=1):
        if line.startswith("-") and not line.startswith("---"):
            pytest.fail(
                f"git history of {_LEDGER_REL_PATH} contains a removed/modified line "
                f"(append-only violated) at output line {lineno}: {line!r}"
            )

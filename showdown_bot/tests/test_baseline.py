"""T6 Task 3: baseline manifest loader + drift-refusing verification + winner-sequence
spot-check (spec Sec.2).

A synthetic-but-real-shaped micro-repo is assembled once per test under ``tmp_path`` by
copying the ACTUAL committed panel/team/schedule/patch/provenance files (preserving their
real relative layout) plus two small fake reference jsonls -- so every hash `verify_baseline`
re-derives is a real content hash of real files, not a stub. Tamper tests mutate one copy at
a time and assert the drift is caught by the RIGHT named check.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from showdown_bot.eval.baseline import (
    BaselineDriftError,
    BaselineError,
    WinnerSequenceError,
    load_baseline,
    verify_baseline,
    verify_winner_sequence,
)
from showdown_bot.eval.panel import load_panel, team_content_hash
from showdown_bot.eval.run_manifest import load_showdown_commit, server_patch_hash
from showdown_bot.eval.schedule import load_schedule

_REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_BASELINES_GLOB = "config/eval/baselines/*.json"

_TEAM_PAIRS = [
    ("teams/panel_v001/trickroom_dev.txt", "teams/panel_v001/trickroom_dev.packed"),
    ("teams/panel_v001/sun_dev.txt", "teams/panel_v001/sun_dev.packed"),
    ("teams/panel_v001/rain_dev.txt", "teams/panel_v001/rain_dev.packed"),
    ("teams/panel_v001/balance_held.txt", "teams/panel_v001/balance_held.packed"),
    ("teams/panel_v001/tailwind_held.txt", "teams/panel_v001/tailwind_held.packed"),
    ("teams/fixed_team.txt", "teams/fixed_team.packed"),
]


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _build_micro_repo(tmp_path: Path) -> dict:
    """Assemble a real-file-shaped micro-repo under ``tmp_path`` and return a baseline
    manifest dict whose every hash is freshly computed against those copies -- so
    ``verify_baseline(manifest, repo_root=tmp_path)`` is green until a test tampers a copy.
    """
    repo_root = tmp_path
    teams_root = repo_root / "showdown_bot"

    _copy(_REPO_ROOT / "config/eval/panels/panel_v001.yaml",
          repo_root / "config/eval/panels/panel_v001.yaml")
    for txt, packed in _TEAM_PAIRS:
        _copy(_REPO_ROOT / "showdown_bot" / txt, teams_root / txt)
        _copy(_REPO_ROOT / "showdown_bot" / packed, teams_root / packed)
    _copy(_REPO_ROOT / "config/eval/schedules/t4_smoke_v001_prefix.yaml",
          repo_root / "config/eval/schedules/t4_smoke_v001_prefix.yaml")
    _copy(_REPO_ROOT / "config/eval/schedules/t4_smoke_v001.yaml",
          repo_root / "config/eval/schedules/t4_smoke_v001.yaml")
    _copy(_REPO_ROOT / "tools/eval/patches/pokemon-showdown-seeded-battle.patch",
          repo_root / "tools/eval/patches/pokemon-showdown-seeded-battle.patch")
    _copy(_REPO_ROOT / "config/eval/provenance.yaml", repo_root / "config/eval/provenance.yaml")

    ref_path = repo_root / "data/eval/fake/reference.jsonl"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_text(
        '{"battle_id":"b1","winner":"hero","seed":"sodium,aaa"}\n'
        '{"battle_id":"b2","winner":"opp","seed":"sodium,bbb"}\n',
        encoding="utf-8", newline="\n",
    )
    heldout_ref_path = repo_root / "data/eval/fake/heldout_reference.jsonl"
    heldout_ref_path.write_text(
        '{"battle_id":"h1","winner":"hero","seed":"sodium,ccc"}\n',
        encoding="utf-8", newline="\n",
    )

    panel = load_panel(
        str(repo_root / "config/eval/panels/panel_v001.yaml"), teams_root=str(teams_root)
    )
    dev_sched = load_schedule(str(repo_root / "config/eval/schedules/t4_smoke_v001_prefix.yaml"))
    heldout_sched = load_schedule(str(repo_root / "config/eval/schedules/t4_smoke_v001.yaml"))

    return {
        "baseline_id": "test-baseline",
        "config_id": "heuristic",
        "config_hash": "cfg16testtest01",
        "git_sha": "deadbeefcafef00d",
        "panel_version": panel.version,
        "panel_hash": panel.panel_hash,
        "dev_schedule_hash": dev_sched.schedule_hash,
        "dev_schedule_path": "config/eval/schedules/t4_smoke_v001_prefix.yaml",
        "hero_team_hash": team_content_hash(str(teams_root), "teams/fixed_team.txt"),
        "opp_team_hashes": {
            t.team_id: t.team_hash for t in (*panel.dev_teams, *panel.heldout_teams)
        },
        "showdown_commit": load_showdown_commit(str(repo_root / "config/eval/provenance.yaml")),
        "server_patch_hash": server_patch_hash(
            str(repo_root / "tools/eval/patches/pokemon-showdown-seeded-battle.patch")
        ),
        "seed_base": "test2026",
        "pythonhashseed": "0",
        "reference_jsonl": "data/eval/fake/reference.jsonl",
        "reference_sha256": hashlib.sha256(ref_path.read_bytes()).hexdigest(),
        "heldout_schedule_hash": heldout_sched.schedule_hash,
        "heldout_schedule_path": "config/eval/schedules/t4_smoke_v001.yaml",
        "heldout_reference_jsonl": "data/eval/fake/heldout_reference.jsonl",
        "heldout_reference_sha256": hashlib.sha256(heldout_ref_path.read_bytes()).hexdigest(),
        "heldout_seed_base": "heldouttest2026",
    }


def _write(tmp_path: Path, baseline: dict) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline, sort_keys=True, indent=2), encoding="utf-8")
    return path


# --- load_baseline -------------------------------------------------------------------------

def test_load_baseline_roundtrip(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    path = _write(tmp_path, baseline)
    assert load_baseline(str(path)) == baseline


def test_load_baseline_missing_required_field_rejected(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    del baseline["config_hash"]
    path = _write(tmp_path, baseline)
    with pytest.raises(BaselineError):
        load_baseline(str(path))


def test_load_baseline_heldout_fields_partial_rejected(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    del baseline["heldout_seed_base"]  # 4 of 5 heldout fields present -> reject
    path = _write(tmp_path, baseline)
    with pytest.raises(BaselineError):
        load_baseline(str(path))


def test_load_baseline_heldout_fields_all_absent_ok(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    for f in ("heldout_schedule_hash", "heldout_schedule_path", "heldout_reference_jsonl",
              "heldout_reference_sha256", "heldout_seed_base"):
        del baseline[f]
    path = _write(tmp_path, baseline)
    assert load_baseline(str(path)) == baseline


# --- verify_baseline: green + drift -----------------------------------------------------

def test_verify_baseline_green_on_untampered(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    checks = verify_baseline(baseline, repo_root=str(tmp_path))
    assert checks and all(c.ok for c in checks)
    names = {c.name for c in checks}
    assert names == {
        "panel_hash", "hero_team_hash", "opp_team_hashes", "dev_schedule_hash",
        "heldout_schedule_hash", "showdown_commit", "server_patch_hash",
        "reference_sha256", "heldout_reference_sha256",
    }


def test_verify_baseline_panel_edit_drift(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    panel_path = tmp_path / "config/eval/panels/panel_v001.yaml"
    text = panel_path.read_text(encoding="utf-8")
    assert "archetype: trick_room" in text
    panel_path.write_text(text.replace("archetype: trick_room", "archetype: trick_room_x"),
                           encoding="utf-8")
    with pytest.raises(BaselineDriftError) as exc_info:
        verify_baseline(baseline, repo_root=str(tmp_path))
    assert "panel_hash" in str(exc_info.value)


def test_verify_baseline_patch_edit_drift(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    patch_path = tmp_path / "tools/eval/patches/pokemon-showdown-seeded-battle.patch"
    patch_path.write_bytes(patch_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(BaselineDriftError) as exc_info:
        verify_baseline(baseline, repo_root=str(tmp_path))
    assert "server_patch_hash" in str(exc_info.value)


def test_verify_baseline_schedule_swap_drift(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    dev_path = tmp_path / "config/eval/schedules/t4_smoke_v001_prefix.yaml"
    full_path = tmp_path / "config/eval/schedules/t4_smoke_v001.yaml"
    dev_path.write_bytes(full_path.read_bytes())  # swap dev schedule content -> hash mismatch
    with pytest.raises(BaselineDriftError) as exc_info:
        verify_baseline(baseline, repo_root=str(tmp_path))
    assert "dev_schedule_hash" in str(exc_info.value)


def test_verify_baseline_reference_byte_flip_drift(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    ref_path = tmp_path / "data/eval/fake/reference.jsonl"
    data = bytearray(ref_path.read_bytes())
    data[0] ^= 0xFF
    ref_path.write_bytes(bytes(data))
    with pytest.raises(BaselineDriftError) as exc_info:
        verify_baseline(baseline, repo_root=str(tmp_path))
    assert "reference_sha256" in str(exc_info.value)


def test_verify_baseline_provenance_commit_change_drift(tmp_path):
    baseline = _build_micro_repo(tmp_path)
    prov_path = tmp_path / "config/eval/provenance.yaml"
    text = prov_path.read_text(encoding="utf-8")
    assert baseline["showdown_commit"] in text
    prov_path.write_text(text.replace(baseline["showdown_commit"], "0" * 40), encoding="utf-8")
    with pytest.raises(BaselineDriftError) as exc_info:
        verify_baseline(baseline, repo_root=str(tmp_path))
    assert "showdown_commit" in str(exc_info.value)


# --- verify_baseline on the REAL committed manifest ----------------------------------------

def test_verify_baseline_real_committed_manifest_green():
    """The committed ``config/eval/baselines/heuristic-v1.json`` verifies against the real
    working tree (T6 Task 6). Unlike the tmp_path tests above, this re-derives every hash
    from the ACTUAL repo files the baseline was frozen against -- panel v001, the five panel
    teams + hero, the dev + held-out schedules, provenance.yaml, the server patch, and both
    reference JSONLs -- so it fails the moment any of those drift from the frozen manifest."""
    manifest_path = _REPO_ROOT / "config/eval/baselines/heuristic-v1.json"
    assert manifest_path.exists(), f"committed baseline manifest missing: {manifest_path}"
    baseline = load_baseline(str(manifest_path))
    checks = verify_baseline(baseline, repo_root=str(_REPO_ROOT))
    assert checks and all(c.ok for c in checks), [
        (c.name, c.measured) for c in checks if not c.ok
    ]


# --- verify_winner_sequence ---------------------------------------------------------------

def test_verify_winner_sequence_identical_ok():
    rows = [
        {"winner": "hero", "seed": "sodium,aaa"},
        {"winner": "opp", "seed": "sodium,bbb"},
    ]
    assert verify_winner_sequence(rows, list(rows)) is None


def test_verify_winner_sequence_flipped_winner_raises():
    ref = [
        {"winner": "hero", "seed": "sodium,aaa"},
        {"winner": "opp", "seed": "sodium,bbb"},
    ]
    fresh = [{"winner": "opp", "seed": "sodium,aaa"}, ref[1]]
    with pytest.raises(WinnerSequenceError) as exc_info:
        verify_winner_sequence(ref, fresh)
    assert "index 0" in str(exc_info.value)


def test_verify_winner_sequence_reordered_raises():
    ref = [
        {"winner": "hero", "seed": "sodium,aaa"},
        {"winner": "opp", "seed": "sodium,bbb"},
    ]
    fresh = [ref[1], ref[0]]  # reordered -> per-index mismatch
    with pytest.raises(WinnerSequenceError):
        verify_winner_sequence(ref, fresh)


def test_verify_winner_sequence_length_mismatch_raises():
    ref = [{"winner": "hero", "seed": "sodium,aaa"}]
    with pytest.raises(WinnerSequenceError):
        verify_winner_sequence(ref, [])


# --- git-history immutability enforcement --------------------------------------------------

def test_baseline_manifest_git_immutability():
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:%x00%H", "--",
             f":(glob){_BASELINES_GLOB}"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git unavailable")
    output = result.stdout
    if not output.strip():
        pytest.skip("no baseline manifest committed yet")
    # Parse "\0<sha>\n<file>\n<file>\n\n\0<sha>\n<file>\n..." blocks into {filename: [shas]}.
    # STRICTER than the T6 Task 1 ledger parser (which only forbids removed/edited LINES,
    # allowing new trailing lines -- the point of append-only): here a baseline manifest file
    # is immutable outright, so we fail if the SAME filename is touched by more than one
    # commit at all (edit OR deletion OR any further append), not just on removed diff lines.
    touches: dict[str, list[str]] = {}
    for block in output.split("\x00"):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.splitlines()
        commit_sha = lines[0].strip()
        for fname in lines[1:]:
            fname = fname.strip()
            if fname:
                touches.setdefault(fname, []).append(commit_sha)
    for fname, shas in touches.items():
        if len(shas) > 1:
            pytest.fail(
                f"baseline manifest {fname!r} touched in {len(shas)} commits (must be "
                f"immutable after its first commit -- a change requires a NEW versioned "
                f"file, e.g. heuristic-v2.json): {shas}"
            )

"""The offline microprofile driver (I8-C): a runner that orchestrates the already-merged
machinery, and a thin entrypoint that requires an explicit ``--reps 30``.

NOT A RUN. Every test drives the runner over node-free STUB sessions and writes only into
tmp_path, except one small real end-to-end test that runs two cold arms at reps=2 to prove the
runner drives the REAL machinery. No test runs the authorized 15x30 = 450-row profile, starts a
server, or plays a battle. The stub is modelled on ``test_profile_harness._FakeRep``: it
accumulates counters like the real backends so ``run_arm`` emits VALID rows for both per_rep
(cold) and per_arm (warm) arms, letting the structural proofs run without the calc bridge.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path

import pytest

from showdown_bot.eval import profile_runner
from showdown_bot.eval import profile_fixtures as pf
from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    profile_manifest_hash,
)
from showdown_bot.eval.profile_arms import PROFILE_ARMS

_SRC = Path(__file__).resolve().parents[1] / "src" / "showdown_bot"
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_ENTRYPOINT = _SCRIPTS / "run_champions_i8_microprofile.py"


def _load_entrypoint():
    spec = importlib.util.spec_from_file_location("run_champions_i8_microprofile", _ENTRYPOINT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# node-free stub session: accumulates like the real backends -> valid rows.
# --------------------------------------------------------------------------

class _StubSession:
    def __init__(self, fixture, *, log, fail_prepare=False, bad_cache=False):
        self.fixture = fixture
        self._log = log
        self._fail_prepare = fail_prepare
        self._bad_cache = bad_cache
        self.stats = self.types = self.attempts = self.spawn = 0
        self.dmg = self.planned = self.implicit = 0
        self.closed = False
        log.setdefault("built", []).append(self)

    def counters(self):
        return {"damage_batch_calls": self.dmg, "planned_damage_batches": self.planned,
                "implicit_damage_batches": self.implicit, "stats_batch_calls": self.stats,
                "types_batch_calls": self.types, "transport_attempts": self.attempts,
                "spawn_count": self.spawn, "requests_total": 0, "requests_unique": 0,
                "cache_hits": 0}

    def cache_sizes(self):
        # bad_cache makes a COLD arm's row fail the per-row validator (cold + populated cache).
        return {"damage": 7 if self._bad_cache else 0, "speed": 0, "dex": 0}

    def prepare(self):
        if self._fail_prepare:
            raise RuntimeError("stub context construction failed")

    def score(self):
        self.dmg += 1; self.planned += 1; self.attempts += 1; self.spawn += 1
        return {"n_candidates": 12, "n_responses": 3, "n_mega_twins": 2, "n_branches": 2,
                "n_worlds": 1, "depth2_frontier": 0, "foe_mega_active": True}

    def close(self):
        self.closed = True
        self._log.setdefault("closed", []).append(self)


def _stub_provider(log, **kw):
    return lambda fixture: _StubSession(fixture, log=log, **kw)


def _read_rows(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def _run(out_dir, *, reps=2, arms=None, log=None, **provider_kw):
    log = {} if log is None else log
    return profile_runner.run_microprofile(
        out_dir, reps=reps, arms=arms,
        session_provider=_stub_provider(log, **provider_kw),
        fixture_hashes=pf.FIXTURE_HASHES,
    ), log


# --------------------------------------------------------------------------
# existence + hygiene
# --------------------------------------------------------------------------

def test_runner_and_entrypoint_modules_exist():
    assert hasattr(profile_runner, "run_microprofile")
    mod = _load_entrypoint()
    assert hasattr(mod, "main") and hasattr(mod, "build_parser")


def test_no_source_module_imports_from_tests():
    """A driver that imported tests/ would be exactly the coupling this promotion removes.
    Scan EVERY source module's import statements, not only the new ones."""
    offenders = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "tests":
                offenders.append((py.name, node.module))
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] == "tests":
                        offenders.append((py.name, a.name))
    assert offenders == [], offenders


def test_no_server_or_battle_apis_in_the_driver():
    """The driver measures scoring offline; it must not start a Showdown server or play a
    battle. None of the driver's own modules may reference the live-run entrypoints."""
    forbidden = ("run_schedule", "run_local_gauntlet", "pokemon-showdown", "LOCAL_SERVER",
                 "websocket", "start --no-security")
    for name in ("profile_runner.py", "profile_fixtures.py"):
        text = (_SRC / "eval" / name).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{name} references {token!r}"
    entry = _ENTRYPOINT.read_text(encoding="utf-8")
    for token in forbidden:
        assert token not in entry, f"entrypoint references {token!r}"


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

def test_all_fifteen_arms_run_exactly_once_in_declared_order(tmp_path):
    report, _ = _run(tmp_path / "out", reps=2)
    rows = _read_rows(tmp_path / "out" / "profile.jsonl")
    # every arm once, PROFILE_ARMS order, reps 0..1 within each arm
    expected = [(a.arm_id, r) for a in PROFILE_ARMS for r in range(2)]
    assert [(row["arm_id"], row["rep"]) for row in rows] == expected
    assert report["rows"] == 2 * len(PROFILE_ARMS)
    assert set(report["arms"]) == {a.arm_id for a in PROFILE_ARMS}


def test_rows_join_their_written_manifest(tmp_path):
    _run(tmp_path / "out", reps=1)
    manifest = json.loads((tmp_path / "out" / "profile_manifest.json").read_text(encoding="utf-8"))
    mhash = profile_manifest_hash(manifest)
    by_arm = {e["arm_id"]: e for e in manifest["arms"]}
    for row in _read_rows(tmp_path / "out" / "profile.jsonl"):
        assert row["profile_manifest_hash"] == mhash
        assert row["config_hash"] == by_arm[row["arm_id"]]["effective_config_hash"]
        assert row["git_sha"] == manifest["git_sha"]
    # manifest order IS the arm order
    assert [e["arm_id"] for e in manifest["arms"]] == [a.arm_id for a in PROFILE_ARMS]


def test_dataset_validation_runs_and_returns_its_report(tmp_path):
    report, _ = _run(tmp_path / "out", reps=2)
    assert report["rows"] == 2 * len(PROFILE_ARMS)
    assert report["arms"]


def test_per_row_validation_runs_at_write_time(tmp_path):
    """A row that violates a semantic rule (cold arm, populated cache) must be rejected AT
    WRITE by the runner's DecisionProfileWriter, aborting the run with no final output."""
    a01 = next(a for a in PROFILE_ARMS if a.arm_id == "A01_no_foe_mega")
    with pytest.raises(DecisionProfileError):
        _run(tmp_path / "out", reps=1, arms=[a01], bad_cache=True)
    assert not (tmp_path / "out").exists()


def test_output_is_lf_only_as_raw_bytes(tmp_path):
    _run(tmp_path / "out", reps=1)
    for name in ("profile.jsonl", "profile_manifest.json"):
        raw = (tmp_path / "out" / name).read_bytes()
        assert b"\r\n" not in raw, name
        assert raw.endswith(b"\n")


# --------------------------------------------------------------------------
# atomic output + failure paths
# --------------------------------------------------------------------------

def test_refuses_an_existing_final_directory(tmp_path):
    final = tmp_path / "out"
    final.mkdir()
    (final / "sentinel").write_text("keep me", encoding="utf-8")
    log = {}
    with pytest.raises(FileExistsError):
        _run(final, reps=1, log=log)
    assert (final / "sentinel").read_text(encoding="utf-8") == "keep me"   # untouched
    # It must refuse EARLY -- before building a single session or a staging dir -- not discover
    # the collision only when the final rename fails. (On Linux os.rename onto a non-empty dir
    # raises OSError, not FileExistsError, so the early check is also what makes this portable.)
    assert not log.get("built"), "refused only after doing work: no early destination check"
    assert not (tmp_path / "out.staging").exists()


def test_a_session_failure_exposes_no_final_output_and_removes_staging(tmp_path):
    final = tmp_path / "out"
    with pytest.raises(Exception):
        _run(final, reps=1, fail_prepare=True)
    assert not final.exists()
    assert not (tmp_path / "out.staging").exists()


def test_staging_cleanup_does_not_touch_unrelated_siblings(tmp_path):
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("do not delete", encoding="utf-8")
    sib_dir = tmp_path / "sibling_dir"
    sib_dir.mkdir(); (sib_dir / "f").write_text("x", encoding="utf-8")
    with pytest.raises(Exception):
        _run(tmp_path / "out", reps=1, fail_prepare=True)
    assert unrelated.read_text(encoding="utf-8") == "do not delete"
    assert (sib_dir / "f").read_text(encoding="utf-8") == "x"
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "out.staging").exists()


def test_sessions_close_on_success(tmp_path):
    _, log = _run(tmp_path / "out", reps=2)
    built = log.get("built", [])
    assert built, "no sessions built"
    assert all(s.closed for s in built)


def test_sessions_close_on_failure(tmp_path):
    log = {}
    with pytest.raises(Exception):
        _run(tmp_path / "out", reps=1, log=log, fail_prepare=True)
    built = log.get("built", [])
    assert built, "no session was built before the failure"
    assert all(s.closed for s in built)


def test_environment_is_restored_after_success_and_after_failure(tmp_path):
    before = dict(os.environ)
    _run(tmp_path / "ok", reps=1)
    assert dict(os.environ) == before
    with pytest.raises(Exception):
        _run(tmp_path / "bad", reps=1, fail_prepare=True)
    assert dict(os.environ) == before


# --------------------------------------------------------------------------
# the real machinery, small, into tmp only
# --------------------------------------------------------------------------

def test_small_real_end_to_end_run_into_tmp(tmp_path):
    """Two REAL cold arms at reps=2 through the real scoring path -- proves the runner drives
    the actual machinery and the dataset validates. Small and tmp-only: no evidence, no 450-row
    profile. This is the only test here that touches the calc bridge."""
    arms = [a for a in PROFILE_ARMS if a.arm_id in ("A01_no_foe_mega", "A03_click_rate_default")]
    report = profile_runner.run_microprofile(tmp_path / "real", reps=2, arms=arms)
    assert report["rows"] == 2 * len(arms)
    assert (tmp_path / "real" / "profile.jsonl").exists()
    assert (tmp_path / "real" / "profile_manifest.json").exists()
    raw = (tmp_path / "real" / "profile.jsonl").read_bytes()
    assert b"\r\n" not in raw


# --------------------------------------------------------------------------
# the thin entrypoint: requires an explicit --reps 30, and refuses anything else.
# these tests parse args only; they NEVER execute the run.
# --------------------------------------------------------------------------

def test_entrypoint_requires_reps():
    mod = _load_entrypoint()
    with pytest.raises(SystemExit):
        mod.parse_args(["--out-dir", "x"])


def test_entrypoint_requires_out_dir():
    mod = _load_entrypoint()
    with pytest.raises(SystemExit):
        mod.parse_args(["--reps", "30"])


def test_entrypoint_accepts_reps_30_without_running():
    mod = _load_entrypoint()
    args = mod.parse_args(["--reps", "30", "--out-dir", "somewhere"])
    assert args.reps == 30
    assert args.out_dir == "somewhere"


@pytest.mark.parametrize("bad", ["0", "-1", "1", "29", "31", "450", "abc"])
def test_entrypoint_rejects_any_reps_other_than_30(bad):
    mod = _load_entrypoint()
    with pytest.raises(SystemExit):
        mod.parse_args(["--reps", bad, "--out-dir", "x"])


def test_entrypoint_help_visibly_names_30():
    """The authorized command must visibly carry the value 30."""
    mod = _load_entrypoint()
    help_text = mod.build_parser().format_help()
    assert "30" in help_text

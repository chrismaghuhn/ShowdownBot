"""T3f Task 3: run_id + run-manifest sidecar + provenance config.

T4c Task 4 additions: the informational ``environment`` block (``collect_environment`` /
``collect_node_version``) and the config_hash-unchanged pin
(``docs/projects/evaluation/specs/2026-07-11-t4c-provenance-hardening-design.md`` R4).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from showdown_bot.eval.run_manifest import (
    ProvenanceError,
    build_run_manifest,
    collect_environment,
    collect_node_version,
    load_showdown_commit,
    make_run_id,
    manifest_path_for,
    server_patch_hash,
    write_run_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/  (tests/ -> showdown_bot/ -> <repo>)
_PATCH = _REPO_ROOT / "tools" / "eval" / "patches" / "pokemon-showdown-seeded-battle.patch"
_PROVENANCE = _REPO_ROOT / "config" / "eval" / "provenance.yaml"


# --- run_id -----------------------------------------------------------------------------

def test_run_id_stable_for_identical_inputs():
    a = make_run_id("run2026", "sched16", "cfg16", "2026-07-02T00:00:00+00:00")
    b = make_run_id("run2026", "sched16", "cfg16", "2026-07-02T00:00:00+00:00")
    assert a == b and len(a) == 16


def test_run_id_changes_when_start_ts_changes():
    a = make_run_id("run2026", "sched16", "cfg16", "2026-07-02T00:00:00+00:00")
    b = make_run_id("run2026", "sched16", "cfg16", "2026-07-02T00:00:01+00:00")
    assert a != b


def test_run_id_changes_on_any_component():
    base = ("run2026", "sched16", "cfg16", "ts")
    h = make_run_id(*base)
    assert make_run_id("other", "sched16", "cfg16", "ts") != h
    assert make_run_id("run2026", "other", "cfg16", "ts") != h
    assert make_run_id("run2026", "sched16", "other", "ts") != h


# --- provenance config + patch hash -----------------------------------------------------

def test_load_showdown_commit_from_repo_config():
    commit = load_showdown_commit()  # default path = config/eval/provenance.yaml
    assert commit and commit == commit.strip()


def test_load_showdown_commit_missing_key_raises(tmp_path):
    p = tmp_path / "provenance.yaml"
    p.write_text("something_else: 1\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        load_showdown_commit(str(p))


def test_load_showdown_commit_missing_file_raises(tmp_path):
    with pytest.raises(ProvenanceError):
        load_showdown_commit(str(tmp_path / "nope.yaml"))


def test_server_patch_hash_is_content_hash_of_patch_file():
    import hashlib

    expected = hashlib.sha1(_PATCH.read_bytes()).hexdigest()[:16]
    assert server_patch_hash() == expected
    assert server_patch_hash(str(_PATCH)) == expected


def test_server_patch_hash_missing_file_is_none(tmp_path):
    assert server_patch_hash(str(tmp_path / "absent.patch")) is None


# --- manifest ---------------------------------------------------------------------------

def test_manifest_path_convention():
    assert manifest_path_for("data/eval/results.jsonl") == "data/eval/results.jsonl.manifest.json"


def _manifest(**over):
    kw = dict(
        run_id="rid16", seed_base="run2026", schedule_hash="sched16", panel_hash="pan16",
        config_hash="cfg16", start_ts="2026-07-02T00:00:00+00:00", pythonhashseed="0",
        cli_invocation=["python", "-m", "showdown_bot.cli", "gauntlet"], git_sha="deadbeef",
        dirty=False, showdown_commit="f8ac140", patch_hash="patch16",
    )
    kw.update(over)
    return build_run_manifest(**kw)


def test_manifest_builds_from_known_inputs():
    m = _manifest()
    assert m["run_id"] == "rid16"
    assert m["seed_base"] == "run2026"
    assert m["schedule_hash"] == "sched16"
    assert m["panel_hash"] == "pan16"
    assert m["config_hash"] == "cfg16"
    assert m["pythonhashseed"] == "0"
    assert m["cli_invocation"][-1] == "gauntlet"
    assert m["showdown_commit"] == "f8ac140"
    assert m["server_patch_hash"] == "patch16"
    assert m["git_sha"] == "deadbeef" and m["dirty"] is False


def test_manifest_defaults_pull_from_config_and_patch():
    # No explicit showdown_commit/patch_hash -> resolved from repo config + patch file.
    m = build_run_manifest(
        run_id="rid16", seed_base="run2026", schedule_hash="sched16", panel_hash="pan16",
        config_hash="cfg16", start_ts="ts", pythonhashseed="0", cli_invocation=["x"],
        git_sha="deadbeef", dirty=False,
    )
    assert m["showdown_commit"] == load_showdown_commit()
    assert m["server_patch_hash"] == server_patch_hash()


def test_write_run_manifest_roundtrips(tmp_path):
    result_out = str(tmp_path / "results.jsonl")
    m = _manifest()
    path = write_run_manifest(result_out, m)
    assert path == result_out + ".manifest.json"
    assert json.loads(Path(path).read_text(encoding="utf-8")) == m


# --- environment block (T4c R4) ----------------------------------------------------------

class _FakeCompleted:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout


def test_collect_node_version_returns_stripped_output_on_success():
    def _fake_run(cmd, **kw):
        assert cmd == ["node", "--version"]
        return _FakeCompleted(0, "v20.11.0\n")

    assert collect_node_version(run=_fake_run) == "v20.11.0"


def test_collect_node_version_none_on_nonzero_exit():
    def _fake_run(cmd, **kw):
        return _FakeCompleted(1, "")

    assert collect_node_version(run=_fake_run) is None


def test_collect_node_version_none_on_missing_binary():
    def _fake_run(cmd, **kw):
        raise FileNotFoundError("node not found")

    assert collect_node_version(run=_fake_run) is None


def test_collect_node_version_none_on_timeout():
    def _fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd="node --version", timeout=5)

    assert collect_node_version(run=_fake_run) is None


def test_collect_node_version_none_on_empty_stdout():
    def _fake_run(cmd, **kw):
        return _FakeCompleted(0, "   \n")

    assert collect_node_version(run=_fake_run) is None


def test_collect_environment_shape_with_injected_node_version():
    import sys

    env = collect_environment(node_version_fn=lambda: "v20.11.0")
    assert env["python"] == sys.version.split()[0]
    assert env["node"] == "v20.11.0"
    assert isinstance(env["platform"], str) and env["platform"]
    assert set(env["deps"]) == {"pydantic", "websockets", "lightgbm"}
    # pydantic/websockets are hard dependencies of this package -> always resolvable here.
    assert isinstance(env["deps"]["pydantic"], str)
    assert isinstance(env["deps"]["websockets"], str)


def test_collect_environment_never_calls_real_subprocess_when_injected(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("real subprocess.run must not be called when node_version_fn is injected")

    monkeypatch.setattr(subprocess, "run", _boom)
    env = collect_environment(node_version_fn=lambda: "v20.0.0")
    assert env["node"] == "v20.0.0"


def test_collect_environment_deps_not_importable_is_none():
    from showdown_bot.eval import run_manifest as _rm

    assert _rm._dep_version("this-package-does-not-exist-xyz") is None


def test_manifest_environment_defaults_to_none_when_not_passed():
    m = _manifest()
    assert m["environment"] is None


def test_manifest_environment_is_carried_through_when_passed():
    env = {"python": "3.11.5", "node": "v20.11.0", "platform": "Windows-11",
           "deps": {"pydantic": "2.13.4", "websockets": "16.0", "lightgbm": None}}
    m = _manifest(environment=env)
    assert m["environment"] == env


# --- pin: config_hash is UNCHANGED by the environment block (T4c R4) ---------------------

def test_config_hash_unchanged_by_environment_block():
    """The environment block must never fork config lineage. ``config_hash`` is passed into
    ``build_run_manifest`` as an already-computed opaque string (see ``eval/config_env.py`` +
    ``eval/result_jsonl.make_config_hash`` for its actual construction, which never reads
    python/node/platform/dep versions) -- so it must come out identical whether the manifest
    carries no environment block, an empty one, or a fully populated one."""
    env = collect_environment(node_version_fn=lambda: "v20.11.0")

    m_absent = _manifest()
    m_present = _manifest(environment=env)
    m_none_explicit = _manifest(environment=None)

    assert m_absent["config_hash"] == m_present["config_hash"] == m_none_explicit["config_hash"]
    assert m_absent["config_hash"] == "cfg16"
    # The environment block itself differs (that's the point) while config_hash does not.
    assert m_absent["environment"] != m_present["environment"]

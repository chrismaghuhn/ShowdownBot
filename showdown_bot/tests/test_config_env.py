"""T3f Task 1: fail-closed SHOWDOWN_* env classification + effective config_hash.

- ``behavior_env`` is fail-closed: every set SHOWDOWN_* var is included EXCEPT explicitly
  excluded ones (denylist exact/prefix or captured-by-reason) — unknown/new vars are included.
- ``make_config_hash(manifest)`` is stable + order-independent; it changes on behavior-affecting
  env changes and is unchanged by denylisted / captured-by-reason env changes.
- A drift test scans the whole package for SHOWDOWN_* reads and fails on any unclassified one.
"""
from __future__ import annotations

import re
from pathlib import Path

import showdown_bot.eval.config_env as config_env
from showdown_bot.eval.config_env import (
    BEHAVIOR_AFFECTING,
    behavior_env,
    build_config_manifest,
    is_classified,
)
from showdown_bot.eval.result_jsonl import make_config_hash


# --- behavior_env fail-closed semantics -----------------------------------------------

def test_behavior_env_includes_behavior_affecting_only_showdown():
    env = {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_REAL_SPREADS": "1", "PATH": "x"}
    assert behavior_env(env) == {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_REAL_SPREADS": "1"}


def test_behavior_env_excludes_denylist_prefixes_and_reasoned():
    env = {
        "SHOWDOWN_CALC_BACKEND": "persistent",        # denylist (caveat)
        "SHOWDOWN_EVAL_SEED_LOG": "/x",               # denylist
        "SHOWDOWN_EVAL_POLICY_TELEMETRY": "/y",       # denylist (T3e P2)
        "SHOWDOWN_AUTH_LOGIN_URL": "http://",         # prefix family
        "SHOWDOWN_DATASET_EXPORT": "1",               # prefix family
        "SHOWDOWN_FORMAT": "gen9vgc2025regi",         # excluded-by-reason
        "SHOWDOWN_TEAM_PATH": "teams/x.txt",          # excluded-by-reason
        "SHOWDOWN_MUST_REACT_LAMBDA": "0.5",          # behavior-affecting
    }
    assert behavior_env(env) == {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}


def test_behavior_env_failclosed_includes_unknown_var():
    env = {"SHOWDOWN_BRAND_NEW_FLAG": "7", "SHOWDOWN_CALC_BACKEND": "persistent"}
    # Unknown SHOWDOWN_* -> INCLUDED (non-pairable, safe); known denylisted -> excluded.
    assert behavior_env(env) == {"SHOWDOWN_BRAND_NEW_FLAG": "7"}


# --- make_config_hash over the manifest ------------------------------------------------

def _manifest(env, *, agent="heuristic", format_id="f", model_hash=None, model_manifest_hash=None):
    return build_config_manifest(
        agent=agent, format_id=format_id, priors_hash="p", spreads_hash="s", env=env,
        model_hash=model_hash, model_manifest_hash=model_manifest_hash,
    )


def test_config_hash_stable_and_order_independent():
    m1 = _manifest({"SHOWDOWN_REAL_SPREADS": "1", "SHOWDOWN_OPP_SETS": "a"})
    m2 = _manifest({"SHOWDOWN_OPP_SETS": "a", "SHOWDOWN_REAL_SPREADS": "1"})  # reordered
    assert make_config_hash(m1) == make_config_hash(m2)
    assert make_config_hash(m1) == make_config_hash(m1)  # identical -> identical


def test_config_hash_changes_on_behavior_affecting_env_change():
    h1 = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h2 = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.9"})))
    assert h1 != h2


def test_config_hash_unchanged_on_denylisted_env_change():
    e1 = behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_CALC_BACKEND": "oneshot",
                       "SHOWDOWN_EVAL_SEED_LOG": "/a"})
    e2 = behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_CALC_BACKEND": "persistent",
                       "SHOWDOWN_EVAL_SEED_LOG": "/b"})
    assert make_config_hash(_manifest(e1)) == make_config_hash(_manifest(e2))


def test_config_hash_unchanged_on_excluded_by_reason_env_change():
    # SHOWDOWN_FORMAT is behavior-relevant but captured via format_id, not env -> env-level
    # change (with format_id held constant) must NOT move the hash.
    e1 = behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_FORMAT": "gen9a",
                       "SHOWDOWN_TEAM_PATH": "teams/a.txt"})
    e2 = behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_FORMAT": "gen9b",
                       "SHOWDOWN_TEAM_PATH": "teams/b.txt"})
    assert make_config_hash(_manifest(e1)) == make_config_hash(_manifest(e2))


def test_model_hashes_present_only_when_provided_and_change_hash():
    m_off = _manifest({})
    assert "model_hash" not in m_off and "model_manifest_hash" not in m_off
    m_on = _manifest({}, model_hash="mh", model_manifest_hash="mmh")
    assert m_on["model_hash"] == "mh" and m_on["model_manifest_hash"] == "mmh"
    assert make_config_hash(m_off) != make_config_hash(m_on)  # reranker-off vs on never collide


# --- drift test: every SHOWDOWN_* read in the package must be classified ----------------

_PKG_ROOT = Path(config_env.__file__).resolve().parents[1]  # .../showdown_bot/ (whole package)
_READ = re.compile(
    r"""(?:os\.environ\.get|os\.getenv|os\.environ)\s*(?:\(|\[)\s*["'](SHOWDOWN_[A-Z0-9_]+)["']"""
)


def _scanned_reads() -> dict[str, list[str]]:
    """Map each SHOWDOWN_* env-read name -> files it appears in, across the whole package."""
    found: dict[str, list[str]] = {}
    for py in _PKG_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        for name in _READ.findall(py.read_text(encoding="utf-8")):
            found.setdefault(name, []).append(py.name)
    return found


def test_every_showdown_env_read_is_classified():
    reads = _scanned_reads()
    assert reads, "drift scan found no SHOWDOWN_* reads — regex/scope broken"
    unclassified = {n: files for n, files in reads.items() if not is_classified(n)}
    assert not unclassified, f"unclassified SHOWDOWN_* reads (classify them in config_env): {unclassified}"


def test_behavior_affecting_flags_are_actually_read_in_source():
    # Hardening: a hardcoded BEHAVIOR_AFFECTING flag that is never read is dead/renamed.
    seen = set(_scanned_reads())
    missing = set(BEHAVIOR_AFFECTING) - seen
    assert not missing, f"BEHAVIOR_AFFECTING flags never read in source: {sorted(missing)}"

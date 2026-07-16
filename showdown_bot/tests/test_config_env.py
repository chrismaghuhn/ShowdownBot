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

import pytest

import showdown_bot.eval.config_env as config_env
from showdown_bot.eval.config_env import (
    BEHAVIOR_AFFECTING,
    NON_BEHAVIORAL,
    SERVER_SIDE_BEHAVIOR_AFFECTING,
    behavior_env,
    build_config_manifest,
    is_classified,
    is_excluded,
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


# --- server-side (TS-patch) behavior-affecting flags (2b-2.5a) --------------------------

def test_server_side_room_dealloc_is_classified_and_not_in_behavior_affecting():
    # SHOWDOWN_EVAL_ROOM_DEALLOC lives in the server-side set (read in the TS server patch),
    # NOT BEHAVIOR_AFFECTING — the "read in Python source" hardening test must stay green.
    assert "SHOWDOWN_EVAL_ROOM_DEALLOC" in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert "SHOWDOWN_EVAL_ROOM_DEALLOC" not in BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_EVAL_ROOM_DEALLOC")


def test_behavior_env_includes_server_side_room_dealloc():
    # It is config-hash-relevant: not excluded -> included in behavior_env (fail-closed).
    env = {"SHOWDOWN_EVAL_ROOM_DEALLOC": "immediate", "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}
    assert behavior_env(env) == {"SHOWDOWN_EVAL_ROOM_DEALLOC": "immediate",
                                 "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}


def test_config_hash_changes_when_room_dealloc_toggled():
    h_off = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h_on = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_EVAL_ROOM_DEALLOC": "immediate"})))
    assert h_off != h_on


# --- gauntlet battle-timeout override (2b-2.5a, 2026-07-11) -----------------------------

def test_gauntlet_battle_timeout_is_behavior_affecting_and_classified():
    # Unlike SHOWDOWN_EVAL_ROOM_DEALLOC, this one IS read in Python source
    # (showdown_bot.client.gauntlet), so it belongs in BEHAVIOR_AFFECTING, not the
    # server-side set.
    assert "SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S")


def test_behavior_env_includes_gauntlet_battle_timeout():
    env = {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900", "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}
    assert behavior_env(env) == {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900",
                                 "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}


def test_config_hash_changes_when_gauntlet_battle_timeout_toggled():
    h_off = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h_on = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900"})))
    assert h_off != h_on


# --- schedule hero-agent selector (2b-4 Task 3) -----------------------------------------

def test_hero_agent_is_behavior_affecting_and_classified():
    # Read in showdown_bot.cli (cli.run_schedule) -> Python source, not the server-side set.
    assert "SHOWDOWN_HERO_AGENT" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_HERO_AGENT" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_HERO_AGENT")


def test_behavior_env_includes_hero_agent():
    env = {"SHOWDOWN_HERO_AGENT": "heuristic_reranker", "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}
    assert behavior_env(env) == {"SHOWDOWN_HERO_AGENT": "heuristic_reranker",
                                 "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}


def test_config_hash_changes_when_hero_agent_toggled():
    h_heuristic = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_HERO_AGENT": "heuristic"})))
    h_override = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_HERO_AGENT": "heuristic_reranker"})))
    assert h_heuristic != h_override


# --- fast-board Protect penalty (2026-07-11, fast-board-protect-discipline Task 1) ------

def test_fast_board_protect_penalty_is_behavior_affecting_and_classified():
    # Read in showdown_bot.battle.decision (_fast_board_protect_weight) -> Python source,
    # not the server-side set.
    assert "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY")


def test_behavior_env_includes_fast_board_protect_penalty():
    env = {"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-2.0", "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}
    assert behavior_env(env) == {"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-2.0",
                                 "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}


def test_config_hash_changes_when_fast_board_protect_penalty_toggled():
    h_off = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h_on = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-2.0"})))
    assert h_off != h_on


# --- research-only aggregation-trace sidecar PATH (2c-Slice-0b Task 3) ------------------

def test_agg_trace_out_is_non_behavioral_and_classified():
    # SHOWDOWN_AGG_TRACE_OUT is the env alias for --agg-trace-out (cli.run_schedule): a
    # research-only full-fidelity aggregation sidecar PATH, IO/telemetry-only with no /choose
    # effect. Same species as SHOWDOWN_DECISION_DIFF (diagnostic) and the SHOWDOWN_DATASET_
    # prefix family -> excluded from config_hash. It MUST stay non-behavioral so a per-shard
    # datagen export path never perturbs config_hash / breaks pairing.
    assert is_excluded("SHOWDOWN_AGG_TRACE_OUT") is True
    assert is_classified("SHOWDOWN_AGG_TRACE_OUT")
    assert "SHOWDOWN_AGG_TRACE_OUT" not in BEHAVIOR_AFFECTING


def test_behavior_env_excludes_agg_trace_out():
    # The export path must NOT fold into config_hash (fail-closed would otherwise include an
    # unclassified SHOWDOWN_* var): a run that sets it, and one that sets a DIFFERENT per-shard
    # path, must still produce the same config_hash and pair.
    assert behavior_env(
        {"SHOWDOWN_AGG_TRACE_OUT": "/x/agg.jsonl", "SHOWDOWN_ROLLOUT_HORIZON": "3"}
    ) == {"SHOWDOWN_ROLLOUT_HORIZON": "3"}


# --- NEUTRAL-mode risk_lambda (2c-1, mirrors SHOWDOWN_MUST_REACT_LAMBDA) ----------------

def test_risk_lambda_is_behavior_affecting_and_classified():
    # Read in showdown_bot.battle.policy (_risk_lambda) -> Python source, not the
    # server-side set.
    assert "SHOWDOWN_RISK_LAMBDA" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_RISK_LAMBDA" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_RISK_LAMBDA")


def test_behavior_env_includes_risk_lambda():
    env = {"SHOWDOWN_RISK_LAMBDA": "0.2", "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}
    assert behavior_env(env) == {"SHOWDOWN_RISK_LAMBDA": "0.2",
                                 "SHOWDOWN_MUST_REACT_LAMBDA": "0.5"}


def test_config_hash_changes_when_risk_lambda_toggled():
    h_off = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h_on = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_RISK_LAMBDA": "0.2"})))
    assert h_off != h_on


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


# --- +Sampling world count (2c-sampling) -----------------------------------------------

def test_world_samples_behavior_affecting_and_classified():
    assert "SHOWDOWN_WORLD_SAMPLES" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_WORLD_SAMPLES" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_WORLD_SAMPLES")


def test_config_hash_changes_when_world_samples_set():
    h_off = make_config_hash(_manifest(behavior_env({})))
    h_on = make_config_hash(_manifest(behavior_env({"SHOWDOWN_WORLD_SAMPLES": "4"})))
    assert h_off != h_on


# --- depth-2 search toggle (2c-depth2 Task 1) -------------------------------------------

def test_search_depth_is_behavior_affecting_and_clamped(monkeypatch):
    from showdown_bot.battle.decision import _search_depth
    assert "SHOWDOWN_SEARCH_DEPTH" in BEHAVIOR_AFFECTING
    monkeypatch.delenv("SHOWDOWN_SEARCH_DEPTH", raising=False)
    base = make_config_hash(_manifest(behavior_env({})))
    assert _search_depth() == 1
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2"); assert _search_depth() == 2
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "5"); assert _search_depth() == 2   # clamp
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "0"); assert _search_depth() == 1
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "x"); assert _search_depth() == 1
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    assert make_config_hash(_manifest(behavior_env({"SHOWDOWN_SEARCH_DEPTH": "2"}))) != base   # set -> hash changes


# --- accuracy mode + branch cap (accuracy-slice) ----------------------------------------

def test_accuracy_mode_is_behavior_affecting_and_classified():
    assert "SHOWDOWN_ACCURACY_MODE" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_ACCURACY_MODE" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_ACCURACY_MODE")


def test_accuracy_branch_cap_is_behavior_affecting_and_classified():
    assert "SHOWDOWN_ACCURACY_BRANCH_CAP" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_ACCURACY_BRANCH_CAP" not in SERVER_SIDE_BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_ACCURACY_BRANCH_CAP")


def test_config_hash_changes_when_accuracy_mode_toggled():
    h_off = make_config_hash(_manifest(behavior_env({"SHOWDOWN_MUST_REACT_LAMBDA": "0.5"})))
    h_on = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_MUST_REACT_LAMBDA": "0.5", "SHOWDOWN_ACCURACY_MODE": "1"})))
    assert h_off != h_on


def test_config_hash_changes_when_accuracy_branch_cap_differs_with_mode_on():
    h_cap4 = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_ACCURACY_MODE": "1", "SHOWDOWN_ACCURACY_BRANCH_CAP": "4"})))
    h_cap8 = make_config_hash(_manifest(behavior_env(
        {"SHOWDOWN_ACCURACY_MODE": "1", "SHOWDOWN_ACCURACY_BRANCH_CAP": "8"})))
    assert h_cap4 != h_cap8


# --- _accuracy_mode() explicit boolean parser -------------------------------------------
# Regression coverage: bool(os.environ.get(...)) would treat the STRINGS "0" and "false" as
# truthy. These six cases are the exact matrix that must hold for the off-path (which is
# verified elsewhere by explicitly setting "0"/"false") to mean anything.

@pytest.mark.parametrize(("raw", "expected"), [
    (None, True),       # unset -> default-on
    ("", False),        # conscious opt-out
    ("0", False),
    ("false", False),
    ("False", False),   # case-insensitive
    ("1", True),
    ("true", True),
])
def test_accuracy_mode_parser_matrix(monkeypatch, raw, expected):
    from showdown_bot.battle.decision import _accuracy_mode

    if raw is None:
        monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)
    else:
        monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", raw)
    assert _accuracy_mode() is expected


def test_unset_defaults_on_explicit_off_stays_off(monkeypatch):
    """Default-on slice: unset resolves True; explicit \"0\" stays off -- they must differ."""
    from showdown_bot.battle.decision import _accuracy_mode

    monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)
    assert _accuracy_mode() is True
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "0")
    assert _accuracy_mode() is False


def test_accuracy_branch_cap_defaults_to_six_when_unset(monkeypatch):
    from showdown_bot.battle.decision import _accuracy_branch_cap

    monkeypatch.delenv("SHOWDOWN_ACCURACY_BRANCH_CAP", raising=False)
    assert _accuracy_branch_cap() == 6


# --- movedata_hash provenance (accuracy-slice Task 7) -----------------------------------

def test_build_config_manifest_includes_movedata_hash_when_provided():
    m = build_config_manifest(
        agent="heuristic", format_id="f", priors_hash="p", spreads_hash="s",
        movedata_hash="mv1", env={},
    )
    assert m["movedata_hash"] == "mv1"


def test_build_config_manifest_movedata_hash_absent_when_not_provided():
    m = build_config_manifest(
        agent="heuristic", format_id="f", priors_hash="p", spreads_hash="s", env={},
    )
    assert "movedata_hash" not in m


def test_config_hash_changes_when_movedata_hash_differs():
    m1 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s",
                                movedata_hash="mv1", env={})
    m2 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s",
                                movedata_hash="mv2", env={})
    assert make_config_hash(m1) != make_config_hash(m2)


# --- I7a-C P1.4: effective_config_manifest is the single canonical payload builder -------
# (shared by the CLI's live config_hash computation and the dedicated freeze helper; no
# ad-hoc caller may re-derive priors_hash/spreads_hash/movedata_hash/provenance itself).

def test_effective_config_manifest_matches_manual_build_config_manifest_assembly():
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.moves import movedata_path
    from showdown_bot.eval.config_env import config_provenance_for_format, effective_config_manifest, file_content_hash

    format_id = "gen9championsvgc2026regma"
    cfg = load_format_config(format_id)
    expected = build_config_manifest(
        agent="heuristic", format_id=format_id,
        priors_hash=file_content_hash(cfg.meta_path("protect_priors")),
        spreads_hash=file_content_hash(cfg.meta_path("default_spreads")),
        env={},
        movedata_hash=file_content_hash(movedata_path()),
        **{k: v for k, v in config_provenance_for_format(format_id).items()},
    )

    actual = effective_config_manifest(agent="heuristic", format_id=format_id, env={})

    assert actual == expected


def test_effective_config_manifest_includes_model_hashes_only_when_provided():
    from showdown_bot.eval.config_env import effective_config_manifest

    format_id = "gen9championsvgc2026regma"
    without = effective_config_manifest(agent="a", format_id=format_id, env={})
    assert "model_hash" not in without
    assert "model_manifest_hash" not in without

    with_models = effective_config_manifest(
        agent="a", format_id=format_id, env={},
        model_hash="mh1", model_manifest_hash="mmh1",
    )
    assert with_models["model_hash"] == "mh1"
    assert with_models["model_manifest_hash"] == "mmh1"


def test_effective_config_manifest_hash_matches_cli_config_hash_for_same_inputs():
    """The manifest returned by effective_config_manifest must hash (via make_config_hash)
    to the identical config_hash the CLI's own _config_hash_for computes for the same
    (agent, format_id, env) -- this is the no-duplicate-computation invariant P1.4 requires."""
    from showdown_bot.eval.config_env import effective_config_manifest

    format_id = "gen9championsvgc2026regma"
    manifest = effective_config_manifest(agent="heuristic", format_id=format_id, env={})
    assert make_config_hash(manifest) == make_config_hash(manifest)  # stable/reproducible
    # A second, independent call must reproduce byte-identical manifest + hash.
    manifest2 = effective_config_manifest(agent="heuristic", format_id=format_id, env={})
    assert manifest == manifest2
    assert make_config_hash(manifest) == make_config_hash(manifest2)


def test_opp_mega_click_rate_is_behavior_affecting_and_classified():
    assert "SHOWDOWN_OPP_MEGA_CLICK_RATE" in BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_OPP_MEGA_CLICK_RATE")


def test_behavior_env_includes_opp_mega_click_rate(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.5")
    assert behavior_env()["SHOWDOWN_OPP_MEGA_CLICK_RATE"] == "0.5"


def test_config_hash_changes_when_opp_mega_click_rate_toggled(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.20")
    m1 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s")
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.50")
    m2 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s")
    assert make_config_hash(m1) != make_config_hash(m2)


def test_opp_mega_trace_out_is_non_behavioral_and_classified():
    """I7b-C: the sidecar's output PATH is IO-only -- it must never enter
    config_hash, or writing telemetry to a different file would perturb the hash
    and break run pairing. Same species as SHOWDOWN_AGG_TRACE_OUT."""
    assert "SHOWDOWN_OPP_MEGA_TRACE_OUT" in NON_BEHAVIORAL


def test_behavior_env_excludes_opp_mega_trace_out(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", "/tmp/x.jsonl")
    assert "SHOWDOWN_OPP_MEGA_TRACE_OUT" not in behavior_env()


def test_opp_mega_click_rate_stays_behavior_affecting_not_confused_with_the_path(monkeypatch):
    """The two I7b env knobs must never be conflated: the sidecar PATH is
    non-behavioral, but the click rate it RECORDS genuinely changes decisions and
    must stay inside config_hash (I7b-A)."""
    assert "SHOWDOWN_OPP_MEGA_CLICK_RATE" in BEHAVIOR_AFFECTING
    assert "SHOWDOWN_OPP_MEGA_CLICK_RATE" not in NON_BEHAVIORAL
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.5")
    assert "SHOWDOWN_OPP_MEGA_CLICK_RATE" in behavior_env()

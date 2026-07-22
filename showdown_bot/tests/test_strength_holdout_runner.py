# showdown_bot/tests/test_strength_holdout_runner.py
"""Task 9: Gate B single-arm battle execution (injectable gauntlet runner).

Fully offline: gauntlet_runner is always injected (a fake), no real server, no real battles, no
external writes beyond tmp_path. Real BattleResultWriter/seeding/schedule contracts are exercised
directly (not mocked) wherever that's possible offline.

Fixture-team deviation from the plan's bare `teams_root="."` sketch: Task 13 (which seals the six
real holdout teams under HOLDOUT_TEAMS_DIR) has not landed yet, so those real `.packed` files do
not exist in this checkout. Every test that reaches the battle loop instead builds minimal fixture
`.packed` files under `tmp_path`, mirroring HOLDOUT_TEAMS_DIR/STRENGTH_HOLDOUT_HERO_TEAM_PATH's
exact relative layout, and passes `teams_root=str(tmp_path)` -- production itself is unaffected
(a real caller still passes `teams_root="."` from the repo root, per Task 11's future CLI).

Known-P1 fix (out_dir containment): the Rev. 18 sketch's `posixpath.normpath` + substring check is
replaced with a canonical, symlink/junction-aware, component-based containment check
(`_assert_out_dir_contained`) -- see the five dedicated path-regression tests near the bottom of
this file. Because that check resolves the relative `expected_root` against the process CWD (the
same way a real caller running from the repo root would), tests that reach it `monkeypatch.chdir
(tmp_path)` first (bundled into `_setup_common`) so the resolved root lands under tmp_path,
matching the tmp_path-rooted `out_dir` every test here already constructs.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from showdown_bot.eval.strength_holdout_runner import (
    resolve_strength_holdout_provenance, run_strength_holdout_arm, GateBAbort,
)
from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule


def _six_teams():
    return sorted(f"holdout_{i}" for i in range(6))


def _fake_team_content_hashes():
    # fixture-only, deliberately hash-shaped (16 hex chars) so downstream code that expects a
    # real team_content_hash format isn't accidentally exercised with an obviously-fake string
    return {team_id: f"{i:016x}" for i, team_id in enumerate(_six_teams())}


def _write_fixture_team_files(teams_root: Path) -> None:
    """Minimal single-line-packed fixture files under teams_root, at the exact relative paths
    HOLDOUT_TEAMS_DIR/STRENGTH_HOLDOUT_HERO_TEAM_PATH expect -- the real sealed teams (Task 13)
    do not exist yet in this checkout."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    from showdown_bot.eval.strength_holdout_schedule import STRENGTH_HOLDOUT_HERO_TEAM_PATH

    hero_packed = (teams_root / STRENGTH_HOLDOUT_HERO_TEAM_PATH).with_suffix(".packed")
    hero_packed.parent.mkdir(parents=True, exist_ok=True)
    hero_packed.write_text("FixtureHero||||Overheat|Timid|||||50|]", encoding="utf-8")

    for team_id in _six_teams():
        opp_packed = (teams_root / HOLDOUT_TEAMS_DIR / f"{team_id}.txt").with_suffix(".packed")
        opp_packed.parent.mkdir(parents=True, exist_ok=True)
        opp_packed.write_text(f"FixtureOpp{team_id}||||Tackle|Hardy|||||50|]", encoding="utf-8")


def test_resolve_provenance_refuses_a_dirty_tree(monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: True)
    with pytest.raises(GateBAbort, match="dirty"):
        resolve_strength_holdout_provenance(hero_agent="heuristic")


def test_resolve_provenance_derives_git_sha_and_config_hash_itself(monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfgderived")
    prov = resolve_strength_holdout_provenance(hero_agent="heuristic")
    assert prov["git_sha"] == "abc123"
    assert prov["config_hash"] == "cfgderived"
    assert prov["candidate_identity"]  # non-empty, sha1-derived


def test_derive_config_hash_and_i8d_provenance_build_the_identical_manifest_call(monkeypatch):
    # Rev. 10 fix: PROVES the reconciliation claim in _derive_config_hash's own docstring --
    # resolve_coverage_provenance (which _derive_config_hash calls) and resolve_i8d_provenance
    # call effective_config_manifest with IDENTICAL arguments for the same hero_agent, which
    # guarantees the same config_hash regardless of what the real config files/environment
    # happen to contain at test-run time (asserting on the real output directly would make this
    # test depend on ambient repo state -- itemdata/speciesdata staleness, format yaml presence --
    # that has nothing to do with the claim being proven here).
    calls = []

    def fake_effective_config_manifest(**kwargs):
        calls.append(kwargs)
        return {"fixture": "manifest"}

    monkeypatch.setattr("showdown_bot.learning.provenance.git_sha_and_dirty", lambda: ("fixture-sha", False))
    monkeypatch.setattr("showdown_bot.eval.config_env.effective_config_manifest", fake_effective_config_manifest)

    from showdown_bot.eval.strength_holdout_runner import _derive_config_hash
    from showdown_bot.eval.i8d_runner import resolve_i8d_provenance
    from showdown_bot.eval.strength_holdout_schedule import STRENGTH_HOLDOUT_FORMAT_ID

    _derive_config_hash("heuristic")
    resolve_i8d_provenance(hero_agent="heuristic")

    assert len(calls) == 2
    assert calls[0] == calls[1]
    # P3 fix: the equality above only pins COVERAGE_FORMAT == I8D_FORMAT (both flow through
    # calls[0]/calls[1] equally, whatever they are) -- it does NOT pin either to
    # STRENGTH_HOLDOUT_FORMAT_ID, the format Gate B's own schedule actually plays under. Without
    # this line, _derive_config_hash could silently drift onto a DIFFERENT format than Gate B's
    # own battles use while this test kept passing. Closes the triangle, not just one edge of it.
    assert calls[0]["format_id"] == STRENGTH_HOLDOUT_FORMAT_ID


def test_derive_config_hash_wraps_each_known_provenance_failure_type(monkeypatch):
    # Rev. 10 fix: CoverageRunError/ItemdataStaleError/SpeciesMetaStaleError/PinnedCalcError are
    # all confirmed-real exception types resolve_coverage_provenance's own call graph can raise
    # (config_env.py:254-320) -- caught SPECIFICALLY here, not via a blanket except Exception
    # (unlike NF5's gauntlet_runner wrap), since this callee is auditable and was actually
    # audited rather than assumed opaque.
    from showdown_bot.eval.strength_holdout_runner import _derive_config_hash, GateBAbort
    from showdown_bot.eval.coverage_runner import CoverageRunError
    from showdown_bot.engine.items import ItemdataStaleError
    from showdown_bot.engine.species_meta import SpeciesMetaStaleError
    from showdown_bot.engine.calc.pin import PinnedCalcError

    for exc_type in (CoverageRunError, ItemdataStaleError, SpeciesMetaStaleError, PinnedCalcError):
        # Grounding fix vs. the plan's embedded snippet: the real call (P3 fix, Rev. 10) passes
        # format_id=STRENGTH_HOLDOUT_FORMAT_ID explicitly, not just hero_agent -- this fake must
        # accept both or the monkeypatched call itself raises a spurious TypeError instead of
        # exercising the except clause under test.
        def _raise(*, hero_agent, format_id, _exc_type=exc_type):
            raise _exc_type("fixture-forced failure")
        monkeypatch.setattr("showdown_bot.eval.coverage_runner.resolve_coverage_provenance", _raise)
        with pytest.raises(GateBAbort, match="config provenance derivation failed"):
            _derive_config_hash("heuristic")


def test_git_is_dirty_wraps_a_called_process_error(monkeypatch):
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError outside a git checkout;
    # this was unguarded and would escape resolve_strength_holdout_provenance ->
    # run_strength_holdout_arm as a raw traceback, before a single battle plays.
    from showdown_bot.eval.strength_holdout_runner import _git_is_dirty
    import subprocess as subprocess_module

    def _raise(*a, **kw):
        raise subprocess_module.CalledProcessError(128, ["git", "status", "--porcelain"])

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.subprocess.run", _raise)
    with pytest.raises(GateBAbort, match="git dirty-state"):
        _git_is_dirty()


def test_git_sha_wraps_a_missing_git_executable(monkeypatch):
    # Same fix, the FileNotFoundError branch (git missing from PATH entirely).
    from showdown_bot.eval.strength_holdout_runner import _git_sha

    def _raise(*a, **kw):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.subprocess.run", _raise)
    with pytest.raises(GateBAbort, match="git sha"):
        _git_sha()


@dataclass
class _FakeGauntletStats:
    # Rev. 4 fix: matches the REAL GauntletStats shape (gauntlet.py:222-240) exactly --
    # `games` only. Rev. 3's fake carried `winner`/`invalid_choices`/`crashes`/`end_reason`
    # directly on stats; the real class has none of those (verified by reading the full class
    # body). Every per-battle result field only ever arrives via the `on_battle_result`
    # callback's `record` argument -- see `_fake_gauntlet_runner_factory` below.
    games: int = 1


def _fake_gauntlet_runner_factory(winner="hero", end_reason="normal"):
    calls = []

    async def fake_run_local_gauntlet(*, on_battle_result=None, **kwargs):
        calls.append(kwargs)
        if on_battle_result is not None:
            # Matches gauntlet.py's real on_battle_result(record) contract exactly (called
            # synchronously with one positional dict arg, built by _battle_result_record):
            # 9 keys -- winner/turns/end_reason/end_hp_diff/invalid_choices/crashes/
            # decision_latency_p95_ms/room_raw_path/normalized_room_log_sha256.
            on_battle_result({
                "winner": winner, "turns": 5, "end_reason": end_reason, "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
            })
        return _FakeGauntletStats(games=1)

    fake_run_local_gauntlet.calls = calls
    return fake_run_local_gauntlet


def _write_valid_seed_log(path, seed_base, count):
    from showdown_bot.eval.seeding import derive_battle_seed as _dbs
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(json.dumps({"battle_index": i, "seed": _dbs(seed_base, i), "seed_base": seed_base}) + "\n")


def _setup_common(monkeypatch, tmp_path, schedule):
    """Shared fixture setup for tests that need to reach the battle loop: dirty-tree/provenance
    mocks, the Channel-A seed-base env var, a seed log that will genuinely verify, fixture team
    files, and a CWD change so the containment check's relative stratum root resolves under
    tmp_path (see module docstring)."""
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: f"cfg-{hero_agent}")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    monkeypatch.chdir(tmp_path)
    _write_fixture_team_files(tmp_path)
    seed_log_path = tmp_path / "seeds.jsonl"
    _write_valid_seed_log(str(seed_log_path), schedule.seed_base, len(schedule.battle_keys))
    return str(seed_log_path)


def _arm_out_dir(tmp_path, name, stratum="windows"):
    """Rev. 15 fix (§1n, Task-3-review P1 #2): run_strength_holdout_arm now bindingly validates
    out_dir against stratum_output_root -- every test reaching that check needs an out_dir
    actually rooted there, not a bare tmp_path child. Returns a Path (like the `tmp_path /
    "arm_a"` expressions this replaces), so existing `.exists()` / `/` usage keeps working."""
    from showdown_bot.eval.strata_guard import stratum_output_root
    from showdown_bot.eval.strength_holdout_runner import STRENGTH_HOLDOUT_OUTPUT_BASE
    return tmp_path / stratum_output_root(stratum, STRENGTH_HOLDOUT_OUTPUT_BASE) / name


def test_run_strength_holdout_arm_plays_every_battle_key_exactly_once(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    fake_runner = _fake_gauntlet_runner_factory(winner="hero")

    result = run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_fake_team_content_hashes(),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )

    assert len(fake_runner.calls) == 180
    assert result["hero_agent"] == "heuristic"
    assert len(result["rows"]) == 180
    assert all(row["winner"] == "hero" for row in result["rows"])
    # every row's seed comes from the GLOBAL seed_index, never the colliding local `seed`
    seeds_used = {row["seed_index"] for row in result["rows"]}
    assert seeds_used == set(range(180))


def test_run_strength_holdout_arm_publishes_atomically(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    out_dir = _arm_out_dir(tmp_path, "arm_a")
    run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
        seed_log_path=seed_log_path, teams_root=str(tmp_path),
        gauntlet_runner=_fake_gauntlet_runner_factory(),
        holdout_team_content_hashes=_fake_team_content_hashes(),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert not out_dir.with_name(out_dir.name + ".staging").exists()  # staging dir cleaned up via rename
    assert out_dir.exists()
    with open(out_dir / "rows.jsonl", "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    assert len(lines) == 180


def test_run_strength_holdout_arm_aborts_cleanly_on_a_row_that_fails_schema_validation(tmp_path, monkeypatch):
    # NF3 fix (Rev. 8): BattleResultWriter.write() (called once per row) validates via
    # validate_battle_row internally and can raise ResultRowError -- the same exception type NF1
    # (Rev. 7) fixed on the READ side (_read_arm), but this is the WRITE side, in a different
    # function the Rev. 7 audit table didn't cover (it was scoped to "functions touched in Rev.
    # 7," not to this function's full exception surface -- see §1g). Simulate exactly the
    # realistic failure mode from the fix comment: on_battle_result fires with a field
    # result_jsonl.py's schema doesn't recognize (schema drift between this plan's row-building
    # and the independently-evolving REQUIRED/NULLABLE field sets).
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def runner_with_an_unknown_field(*, on_battle_result=None, **kwargs):
        if on_battle_result is not None:
            on_battle_result({
                "winner": "hero", "turns": 5, "end_reason": "normal", "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
                "a_field_result_jsonl_has_never_heard_of": True,
            })
        return _FakeGauntletStats(games=1)

    out_dir = _arm_out_dir(tmp_path, "arm_a")
    with pytest.raises(GateBAbort, match="fails schema validation"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=runner_with_an_unknown_field,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()  # never published -- orphaned staging dir left behind instead


def test_run_strength_holdout_arm_refuses_an_existing_out_dir(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    out_dir = _arm_out_dir(tmp_path, "arm_a")
    out_dir.mkdir(parents=True)
    with pytest.raises(GateBAbort, match="already exists"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path),
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def test_run_strength_holdout_arm_discards_a_timed_out_battle_and_aborts(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def timing_out_runner(*, on_battle_result=None, **kwargs):
        return _FakeGauntletStats(games=0)

    with pytest.raises(GateBAbort, match="did not complete"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=timing_out_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def test_run_strength_holdout_arm_aborts_cleanly_if_the_gauntlet_runner_raises(tmp_path, monkeypatch):
    # NF5 fix (Rev. 9): gauntlet_runner (the real run_local_gauntlet) can raise -- a server
    # disconnect mid-battle, for example -- not just misbehave via its return value (the
    # stats.games != 1 / empty-captured checks the two tests above and below this one exercise).
    # Nothing wrapped the call itself before. Confirm the abort is GateBAbort, names the
    # seed_index it broke at, and preserves the original exception via `from exc`.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def disconnecting_runner(*, on_battle_result=None, **kwargs):
        raise ConnectionError("fixture-forced server disconnect")

    with pytest.raises(GateBAbort, match="seed_index 0") as exc_info:
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=disconnecting_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert isinstance(exc_info.value.__cause__, ConnectionError)


def test_run_strength_holdout_arm_aborts_before_playing_if_a_scheduled_team_has_no_sealed_hash(tmp_path, monkeypatch):
    # P2 fix (Rev. 3): opp_team_hash must never fall back to the bare team_id -- a scheduled
    # team missing from holdout_team_content_hashes is a sealing gap, not something to paper
    # over with a non-hash placeholder. Must abort before the FIRST battle plays, not after --
    # this check runs before the seed-base/seed-log checks too, so no seed setup is needed.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    incomplete_hashes = _fake_team_content_hashes()
    del incomplete_hashes["holdout_0"]
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="holdout_0"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=incomplete_hashes,
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0  # no battle played before the check fired


def test_run_strength_holdout_arm_rejects_a_seed_base_env_mismatch(tmp_path, monkeypatch):
    # P1 fix (Rev. 4): the Channel-A seed namespace must be proven BEFORE any battle plays,
    # exactly like i8d_runner.py/coverage_runner.py's own early checks.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "some-other-namespace")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="SHOWDOWN_BATTLE_SEED_BASE"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_requires_a_seed_log_path(tmp_path, monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="seed_log_path"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path="", teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_aborts_if_the_seed_log_does_not_verify(tmp_path, monkeypatch):
    # P1 fix (Rev. 4): a malformed/misaligned seed log must abort with NO out_dir published,
    # even though every battle in the loop itself "succeeded" (the fake runner always reports
    # games=1) -- proving the server's seeds cannot be trusted must block publish regardless of
    # in-loop success.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    monkeypatch.chdir(tmp_path)
    _write_fixture_team_files(tmp_path)
    bad_seed_log = tmp_path / "seeds.jsonl"
    _write_valid_seed_log(str(bad_seed_log), "wrong-seed-base-recorded", len(schedule.battle_keys))
    out_dir = _arm_out_dir(tmp_path, "arm_a")

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=str(bad_seed_log), teams_root=str(tmp_path),
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()


# --- Task 9 known P1: canonical, symlink/junction-safe out_dir containment -------------------
# The Rev. 18 sketch bound out_dir with posixpath.normpath + a slash-bounded substring check --
# lexical only, so a foreign absolute path that merely CONTAINS the expected root's text, a
# pre-existing symlink/junction inside the root pointing elsewhere, or Windows' case-insensitive
# filesystem could all defeat it. run_strength_holdout_arm now resolves both out_dir and the
# expected stratum root to their REAL canonical absolute form (following any existing symlinks/
# junctions) and compares path COMPONENTS, case-folded on Windows only.

def test_run_strength_holdout_arm_accepts_a_real_absolute_child_path_under_the_stratum_root(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    fake_runner = _fake_gauntlet_runner_factory()
    result = run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_fake_team_content_hashes(),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert len(fake_runner.calls) == 180
    assert Path(result["out_dir"]).exists()


def test_run_strength_holdout_arm_rejects_a_similarly_named_path_containing_the_root_text(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    from showdown_bot.eval.strength_holdout_runner import STRENGTH_HOLDOUT_OUTPUT_BASE
    # This out_dir's STRING contains expected_root's exact slash-bounded text as a substring
    # (which the old posixpath.normpath+substring check would have wrongly accepted), but its
    # REAL resolved location sits under an unrelated "decoy_root" sibling -- never actually
    # inside the genuine, canonically-resolved stratum root.
    decoy_out_dir = tmp_path / "decoy_root" / STRENGTH_HOLDOUT_OUTPUT_BASE / "windows" / "arm_a"
    with pytest.raises(GateBAbort, match="out_dir"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(decoy_out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path),
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def test_run_strength_holdout_arm_rejects_dotdot_traversal_out_of_the_root(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    from showdown_bot.eval.strength_holdout_runner import STRENGTH_HOLDOUT_OUTPUT_BASE
    root = tmp_path / STRENGTH_HOLDOUT_OUTPUT_BASE / "windows"
    traversal_out_dir = root / ".." / ".." / ".." / ".." / "elsewhere"
    with pytest.raises(GateBAbort, match="out_dir"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(traversal_out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path),
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def _make_windows_junction(link_path: Path, target_path: Path) -> None:
    """Create a Windows directory junction via mklink /J -- unlike symlinks, this needs no admin
    privilege / Developer Mode. Raises OSError on failure."""
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise OSError(f"mklink /J failed (rc={result.returncode}): {result.stdout} {result.stderr}")


def test_run_strength_holdout_arm_rejects_a_symlink_or_junction_escape_from_the_root(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    from showdown_bot.eval.strength_holdout_runner import STRENGTH_HOLDOUT_OUTPUT_BASE
    stratum_root = tmp_path / STRENGTH_HOLDOUT_OUTPUT_BASE / "windows"
    stratum_root.mkdir(parents=True)
    escape_target = tmp_path / "outside_root"
    escape_target.mkdir()
    link_path = stratum_root / "escape_link"
    try:
        os.symlink(str(escape_target), str(link_path), target_is_directory=True)
    except OSError:
        try:
            _make_windows_junction(link_path, escape_target)
        except OSError as exc:
            pytest.skip(
                "neither os.symlink nor mklink /J is available in this test environment "
                f"(insufficient privilege) -- cannot exercise a real link escape: {exc}"
            )

    escaping_out_dir = link_path / "arm_a"
    with pytest.raises(GateBAbort, match="out_dir"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(escaping_out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path),
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def test_run_strength_holdout_arm_accepts_a_windows_case_variant_of_the_stratum_root(tmp_path, monkeypatch):
    if platform.system() != "Windows":
        pytest.skip("case-insensitive path containment is a Windows-specific behavior")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    from showdown_bot.eval.strength_holdout_runner import STRENGTH_HOLDOUT_OUTPUT_BASE
    real_root = tmp_path / STRENGTH_HOLDOUT_OUTPUT_BASE / "windows"
    real_root.mkdir(parents=True)
    # Windows' NTFS is case-insensitive/case-preserving: this ALL-CAPS path refers to the exact
    # same real directory just created above.
    case_variant_out_dir = tmp_path / STRENGTH_HOLDOUT_OUTPUT_BASE.upper() / "WINDOWS" / "arm_a"
    fake_runner = _fake_gauntlet_runner_factory()
    run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(case_variant_out_dir),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_fake_team_content_hashes(),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert len(fake_runner.calls) == 180

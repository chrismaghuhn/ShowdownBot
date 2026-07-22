# showdown_bot/tests/test_strength_holdout_runner.py
"""Task 9: Gate B single-arm battle execution (injectable gauntlet runner).

Fully offline: gauntlet_runner is always injected (a fake), no real server, no real battles, no
external writes beyond tmp_path. Real BattleResultWriter/seeding/schedule contracts are exercised
directly (not mocked) wherever that's possible offline.

Fixture-team deviation from the plan's bare `teams_root="."` sketch: Task 13 (which seals the six
real holdout teams under HOLDOUT_TEAMS_DIR) has not landed yet, so those real team files do not
exist in this checkout. Every test that reaches the battle loop instead builds minimal fixture
`.txt`+`.packed` files under `tmp_path`, mirroring HOLDOUT_TEAMS_DIR/STRENGTH_HOLDOUT_HERO_TEAM_
PATH's exact relative layout, and passes `teams_root=str(tmp_path)` -- production itself is
unaffected (a real caller still passes `teams_root="."` from the repo root, per Task 11's future
CLI). Review-fix P1 #1 requires the REAL team_content_hash of those fixture files, not an
arbitrary synthetic value -- see `_compute_real_team_content_hashes` vs the still-synthetic
`_fake_team_content_hashes` (valid only for tests that abort before the hash-recompute step).

Known-P1 fix (out_dir containment): the Rev. 18 sketch's `posixpath.normpath` + substring check is
replaced with a canonical, symlink/junction-aware, component-based containment check
(`_assert_out_dir_contained`) -- see the path-regression tests near the bottom of this file.
Because that check resolves the relative `expected_root` against the process CWD (the same way a
real caller running from the repo root would), tests that reach it `monkeypatch.chdir(tmp_path)`
first (bundled into `_setup_common`) so the resolved root lands under tmp_path, matching the
tmp_path-rooted `out_dir` every test here already constructs.

Review-fix P1 #2 (seed-log run-binding): the seed log must be built DURING this run (absent/empty
before battle 1, SHOWDOWN_EVAL_SEED_LOG canonically equal to seed_log_path) -- so the fake
gauntlet runner now APPENDS one seed-log line per simulated battle (mirroring what a real server
writes), instead of the whole log being pre-populated before the call.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.eval.strength_holdout_runner import (
    resolve_strength_holdout_provenance, run_strength_holdout_arm, GateBAbort,
)
from showdown_bot.eval.strength_holdout_schedule import (
    build_strength_holdout_schedule, STRENGTH_HOLDOUT_FORMAT_ID, STRENGTH_HOLDOUT_SEED_BASE,
)


def _six_teams():
    return sorted(f"holdout_{i}" for i in range(6))


def _fake_team_content_hashes():
    # Synthetic, hash-shaped (16 hex chars) map with the CORRECT key set but ARBITRARY values --
    # valid only for tests that abort before the team-hash recompute step (review-fix P1 #1):
    # the exact-set check, Channel-A checks, seed-log checks, date_stratum_id, and out_dir
    # containment all run first and never look at the VALUES.
    return {team_id: f"{i:016x}" for i, team_id in enumerate(_six_teams())}


def _write_fixture_team_files(teams_root: Path) -> None:
    """Minimal fixture .txt+.packed files under teams_root, at the exact relative paths
    HOLDOUT_TEAMS_DIR/STRENGTH_HOLDOUT_HERO_TEAM_PATH expect -- the real sealed teams (Task 13)
    do not exist yet in this checkout. Both files are required: panel.team_content_hash (review-
    fix P1 #1) hashes .txt+.packed together and raises PanelError if either is missing."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    from showdown_bot.eval.strength_holdout_schedule import STRENGTH_HOLDOUT_HERO_TEAM_PATH

    hero_txt = teams_root / STRENGTH_HOLDOUT_HERO_TEAM_PATH
    hero_txt.parent.mkdir(parents=True, exist_ok=True)
    hero_txt.write_text("Fixture Hero Team\n", encoding="utf-8")
    hero_txt.with_suffix(".packed").write_text("FixtureHero||||Overheat|Timid|||||50|]", encoding="utf-8")

    for team_id in _six_teams():
        opp_txt = teams_root / HOLDOUT_TEAMS_DIR / f"{team_id}.txt"
        opp_txt.parent.mkdir(parents=True, exist_ok=True)
        opp_txt.write_text(f"Fixture Opponent {team_id}\n", encoding="utf-8")
        opp_txt.with_suffix(".packed").write_text(
            f"FixtureOpp{team_id}||||Tackle|Hardy|||||50|]", encoding="utf-8",
        )


def _compute_real_team_content_hashes(teams_root: Path) -> dict:
    """Real team_content_hash values for the six fixture opponent teams
    _write_fixture_team_files just created. Review-fix P1 #1: run_strength_holdout_arm now
    recomputes and compares against these, so tests reaching the battle loop must supply THESE,
    not an arbitrary synthetic map."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    from showdown_bot.eval.panel import team_content_hash
    return {
        team_id: team_content_hash(str(teams_root), f"{HOLDOUT_TEAMS_DIR}{team_id}.txt")
        for team_id in _six_teams()
    }


def test_resolve_provenance_refuses_a_dirty_tree(monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: True)
    with pytest.raises(GateBAbort, match="dirty"):
        resolve_strength_holdout_provenance(hero_agent="heuristic")


def test_resolve_provenance_derives_git_sha_and_config_hash_itself(monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfgderived", "calc_backend": "oneshot"},
    )
    prov = resolve_strength_holdout_provenance(hero_agent="heuristic")
    assert prov["git_sha"] == "abc123"
    assert prov["config_hash"] == "cfgderived"
    # Review-fix P1 #5: calc_backend is derived internally alongside config_hash, never discarded.
    assert prov["calc_backend"] == "oneshot"
    assert prov["candidate_identity"]  # non-empty, sha1-derived


def test_derive_config_provenance_and_i8d_provenance_build_the_identical_manifest_call(monkeypatch):
    # Rev. 10 fix: PROVES the reconciliation claim in _derive_config_provenance's own docstring
    # -- resolve_coverage_provenance (which _derive_config_provenance calls) and
    # resolve_i8d_provenance call effective_config_manifest with IDENTICAL arguments for the same
    # hero_agent, which guarantees the same config_hash regardless of what the real config
    # files/environment happen to contain at test-run time (asserting on the real output directly
    # would make this test depend on ambient repo state -- itemdata/speciesdata staleness, format
    # yaml presence -- that has nothing to do with the claim being proven here).
    calls = []

    def fake_effective_config_manifest(**kwargs):
        calls.append(kwargs)
        return {"fixture": "manifest"}

    monkeypatch.setattr("showdown_bot.learning.provenance.git_sha_and_dirty", lambda: ("fixture-sha", False))
    monkeypatch.setattr("showdown_bot.eval.config_env.effective_config_manifest", fake_effective_config_manifest)

    from showdown_bot.eval.strength_holdout_runner import _derive_config_provenance
    from showdown_bot.eval.i8d_runner import resolve_i8d_provenance

    _derive_config_provenance("heuristic")
    resolve_i8d_provenance(hero_agent="heuristic")

    assert len(calls) == 2
    assert calls[0] == calls[1]
    # P3 fix: the equality above only pins COVERAGE_FORMAT == I8D_FORMAT (both flow through
    # calls[0]/calls[1] equally, whatever they are) -- it does NOT pin either to
    # STRENGTH_HOLDOUT_FORMAT_ID, the format Gate B's own schedule actually plays under. Without
    # this line, _derive_config_provenance could silently drift onto a DIFFERENT format than Gate
    # B's own battles use while this test kept passing. Closes the triangle, not just one edge.
    assert calls[0]["format_id"] == STRENGTH_HOLDOUT_FORMAT_ID


def test_derive_config_provenance_wraps_each_known_provenance_failure_type(monkeypatch):
    # Rev. 10 fix: CoverageRunError/ItemdataStaleError/SpeciesMetaStaleError/PinnedCalcError are
    # all confirmed-real exception types resolve_coverage_provenance's own call graph can raise
    # (config_env.py:254-320) -- caught SPECIFICALLY here, not via a blanket except Exception
    # (unlike NF5's gauntlet_runner wrap), since this callee is auditable and was actually
    # audited rather than assumed opaque.
    from showdown_bot.eval.strength_holdout_runner import _derive_config_provenance, GateBAbort
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
            _derive_config_provenance("heuristic")


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


def _fake_gauntlet_runner_factory(*, winner="hero", end_reason="normal", seed_log_path=None, seed_base=None):
    """seed_log_path/seed_base: when given, the fake runner APPENDS one seed-log line per
    simulated battle (mirroring what a real server writes to SHOWDOWN_EVAL_SEED_LOG as battles
    happen) -- review-fix P1 #2: the log must be built DURING this run, never pre-populated."""
    calls = []
    next_index = [0]

    async def fake_run_local_gauntlet(*, on_battle_result=None, **kwargs):
        calls.append(kwargs)
        if seed_log_path is not None:
            index = next_index[0]
            next_index[0] += 1
            seed = derive_battle_seed(seed_base, index)
            with open(seed_log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"battle_index": index, "seed": seed, "seed_base": seed_base}) + "\n")
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


def _setup_common(monkeypatch, tmp_path, schedule, *, calc_backend="oneshot"):
    """Shared fixture setup for tests that need to reach the battle loop: dirty-tree/provenance
    mocks, the Channel-A seed-base env var, fixture team files, a CWD change so the containment
    check's relative stratum root resolves under tmp_path, and SHOWDOWN_EVAL_SEED_LOG pointed at
    (but not pre-populating) this run's seed log path (review-fix P1 #2)."""
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": f"cfg-{hero_agent}", "calc_backend": calc_backend},
    )
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    monkeypatch.chdir(tmp_path)
    _write_fixture_team_files(tmp_path)
    seed_log_path = tmp_path / "seeds.jsonl"
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(seed_log_path))
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
    fake_runner = _fake_gauntlet_runner_factory(winner="hero", seed_log_path=seed_log_path, seed_base=schedule.seed_base)

    result = run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
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
        gauntlet_runner=_fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base),
        holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert not out_dir.with_name(out_dir.name + ".staging").exists()  # staging dir cleaned up via rename
    assert out_dir.exists()
    with open(out_dir / "rows.jsonl", "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    assert len(lines) == 180

    # Review-fix P1 #2: the verified seed log is copied byte-exact into the artifact, and the
    # manifest records a relative path + sha256 + line count + seed_log_verified, never the
    # caller's original (possibly machine-local absolute) seed_log_path.
    with open(out_dir / "seeds.jsonl", "rb") as fh:
        published_seed_log_bytes = fh.read()
    with open(seed_log_path, "rb") as fh:
        original_seed_log_bytes = fh.read()
    assert published_seed_log_bytes == original_seed_log_bytes
    with open(out_dir / "arm_manifest.json", "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["seed_log_relpath"] == "seeds.jsonl"
    assert manifest["seed_log_sha256"] == hashlib.sha256(published_seed_log_bytes).hexdigest()
    assert manifest["seed_log_n_lines"] == 180
    assert manifest["seed_log_verified"] is True
    assert "seed_log_path" not in manifest  # never the caller's raw local path
    # Review-fix P1 #5: calc_backend is derived internally and recorded, not discarded.
    assert manifest["calc_backend"] == "oneshot"


def test_run_strength_holdout_arm_aborts_cleanly_on_a_row_that_fails_schema_validation(tmp_path, monkeypatch):
    # NF3 fix (Rev. 8): BattleResultWriter.write() (called once per row) validates via
    # validate_battle_row internally and can raise ResultRowError. Uses an INVALID winner VALUE
    # (not an extra/unexpected field -- that is now caught earlier by the review-fix P1 #3
    # callback whitelist; see test_run_strength_holdout_arm_rejects_a_callback_with_an_unexpected_
    # field below) so this specifically exercises the WRITE-side schema check downstream of the
    # whitelist.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def runner_with_an_invalid_winner_value(*, on_battle_result=None, **kwargs):
        if on_battle_result is not None:
            on_battle_result({
                "winner": "not_a_real_winner_value", "turns": 5, "end_reason": "normal", "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
            })
        return _FakeGauntletStats(games=1)

    out_dir = _arm_out_dir(tmp_path, "arm_a")
    with pytest.raises(GateBAbort, match="fails schema validation"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=runner_with_an_invalid_winner_value,
            holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
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
            gauntlet_runner=_fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base),
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
            holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
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
            holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
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
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfg", "calc_backend": "oneshot"},
    )
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
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfg", "calc_backend": "oneshot"},
    )
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
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfg", "calc_backend": "oneshot"},
    )
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
    # P1 fix (Rev. 4), extended by review-fix P1 #2: a malformed/misaligned seed log must abort
    # with NO out_dir published, even though every battle in the loop itself "succeeded" (the
    # fake runner always reports games=1) -- proving the server's seeds cannot be trusted must
    # block publish regardless of in-loop success. The seed log is now built DURING the run (it
    # must be absent/empty before battle 1), so this simulates a misconfigured server: the log
    # fills up as battles play, but every line is stamped with the WRONG seed_base.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    out_dir = _arm_out_dir(tmp_path, "arm_a")
    bad_runner = _fake_gauntlet_runner_factory(
        seed_log_path=seed_log_path, seed_base="wrong-seed-base-recorded",
    )

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path),
            gauntlet_runner=bad_runner,
            holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()


# --- Review-fix P1 #1: sealed team hashes must be recomputed and verified, not just trusted ---

def test_run_strength_holdout_arm_rejects_an_extra_team_hash_not_in_the_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfg", "calc_backend": "oneshot"},
    )
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    extra_hashes = _fake_team_content_hashes()
    extra_hashes["not_a_scheduled_team"] = "0" * 16
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="not_a_scheduled_team"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=extra_hashes,
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_rejects_a_team_hash_that_does_not_match_the_real_file(tmp_path, monkeypatch):
    # Review-fix P1 #1: a caller-supplied hash that names the right team but does not match the
    # REAL .txt+.packed content must be rejected before battle 1 -- the map used to be trusted
    # as-is, never recomputed against the actual sealed team content.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    wrong_hashes = _compute_real_team_content_hashes(tmp_path)
    wrong_hashes["holdout_0"] = "0" * 16  # does not match the real fixture file's content
    fake_runner = _fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base)

    with pytest.raises(GateBAbort, match="holdout_0"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=wrong_hashes,
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0  # rejected before battle 1, not mid-loop


# --- Review-fix P1 #2 (additional): SHOWDOWN_EVAL_SEED_LOG binding + freshness -----------------

def test_run_strength_holdout_arm_rejects_a_seed_log_env_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfg", "calc_backend": "oneshot"},
    )
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(tmp_path / "a_totally_different_file.jsonl"))
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="SHOWDOWN_EVAL_SEED_LOG"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_rejects_a_preexisting_nonempty_seed_log(tmp_path, monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_runner._derive_config_provenance",
        lambda hero_agent: {"config_hash": "cfg", "calc_backend": "oneshot"},
    )
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    seed_log_path = tmp_path / "seeds.jsonl"
    seed_log_path.write_text(
        json.dumps({"battle_index": 0, "seed": derive_battle_seed(schedule.seed_base, 0),
                    "seed_base": schedule.seed_base}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SHOWDOWN_EVAL_SEED_LOG", str(seed_log_path))
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="already exists and is non-empty"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(seed_log_path), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


# --- Review-fix P1 #3: on_battle_result callback field whitelist ------------------------------

def test_run_strength_holdout_arm_rejects_a_callback_with_an_unexpected_field(tmp_path, monkeypatch):
    # **record used to be unpacked LAST in the row dict literal, so a record containing any
    # runner-owned key name (e.g. git_sha) would silently overwrite that trusted value.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def poisoning_runner(*, on_battle_result=None, **kwargs):
        if on_battle_result is not None:
            on_battle_result({
                "winner": "hero", "turns": 5, "end_reason": "normal", "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
                "git_sha": "attacker-controlled-sha",  # a runner-owned field name, injected
            })
        return _FakeGauntletStats(games=1)

    out_dir = _arm_out_dir(tmp_path, "arm_a")
    with pytest.raises(GateBAbort, match="unexpected field"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=poisoning_runner,
            holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()


def test_run_strength_holdout_arm_rejects_a_callback_missing_a_required_field(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def incomplete_runner(*, on_battle_result=None, **kwargs):
        if on_battle_result is not None:
            record = {
                "winner": "hero", "turns": 5, "end_reason": "normal", "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
            }
            del record["crashes"]
            on_battle_result(record)
        return _FakeGauntletStats(games=1)

    out_dir = _arm_out_dir(tmp_path, "arm_a")
    with pytest.raises(GateBAbort, match="missing field"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=incomplete_runner,
            holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()


# --- Review-fix P1 #4: the schedule must be a genuine, rebuild-verified StrengthHoldoutSchedule -

def test_run_strength_holdout_arm_rejects_a_non_genuine_schedule_object(tmp_path):
    @dataclass
    class _FakeSchedule:
        battle_keys: tuple = ()
        schedule_hash: str = "fake"
        panel_hash: str = "a" * 16
        seed_base: str = STRENGTH_HOLDOUT_SEED_BASE
        format_id: str = STRENGTH_HOLDOUT_FORMAT_ID

    fake_runner = _fake_gauntlet_runner_factory()
    with pytest.raises(GateBAbort, match="StrengthHoldoutSchedule"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=_FakeSchedule(), out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes={},
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_rejects_a_schedule_with_an_unpinned_seed_base(tmp_path):
    schedule = build_strength_holdout_schedule(
        holdout_team_ids=_six_teams(), panel_hash="a" * 16, seed_base="attacker-chosen-namespace",
    )
    fake_runner = _fake_gauntlet_runner_factory()
    with pytest.raises(GateBAbort, match="pinned seed namespace"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_rejects_a_schedule_that_does_not_rebuild_match(tmp_path):
    # Every OTHER field is genuine, but schedule_hash is tampered -- does not match what a fresh
    # rebuild from its own team_ids/panel_hash/seed_base produces.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    tampered = dataclasses.replace(schedule, schedule_hash="tampered-schedule-hash")
    fake_runner = _fake_gauntlet_runner_factory()
    with pytest.raises(GateBAbort, match="does not match the canonical rebuild"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=tampered, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_rejects_an_invalid_hero_agent(tmp_path):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    fake_runner = _fake_gauntlet_runner_factory()
    with pytest.raises(GateBAbort, match="hero_agent"):
        run_strength_holdout_arm(
            hero_agent="some_other_agent", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


# --- Review-fix P1 #5: calc_backend is derived internally, never caller-supplied --------------

def test_run_strength_holdout_arm_records_the_derived_calc_backend_not_hardcoded(tmp_path, monkeypatch):
    # calc_backend is no longer a parameter at all -- proven here by mocking a DIFFERENT derived
    # value than the "oneshot" default and confirming the manifest/result reflect it exactly.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule, calc_backend="persistent")
    out_dir = _arm_out_dir(tmp_path, "arm_a")
    fake_runner = _fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base)

    result = run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert result["calc_backend"] == "persistent"
    with open(out_dir / "arm_manifest.json", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["calc_backend"] == "persistent"


# --- Review-fix P2: date_stratum_id must be a genuine non-blank string -------------------------

def test_run_strength_holdout_arm_rejects_a_blank_date_stratum_id(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    fake_runner = _fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base)
    with pytest.raises(GateBAbort, match="date_stratum_id"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="   ",  # whitespace-only: truthy but blank
            stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


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
    fake_runner = _fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base)
    result = run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
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
    fake_runner = _fake_gauntlet_runner_factory(seed_log_path=seed_log_path, seed_base=schedule.seed_base)
    run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(case_variant_out_dir),
        seed_log_path=seed_log_path, teams_root=str(tmp_path), gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_compute_real_team_content_hashes(tmp_path),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert len(fake_runner.calls) == 180

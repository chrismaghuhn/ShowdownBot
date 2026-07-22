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
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from showdown_bot.eval.seeding import derive_battle_seed
from showdown_bot.eval.strength_holdout_runner import (
    resolve_strength_holdout_provenance, run_strength_holdout_arm, GateBAbort,
    CANONICAL_REFERENCE_TEAM_PATHS,
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


from showdown_bot.eval.heldout_ledger import AccessBudgetError, read_ledger
from showdown_bot.eval.strength_holdout_runner import combine_strength_holdout_arms
from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError
from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
from showdown_bot.eval.strength_holdout_verdict import StrengthHoldoutRunError
from showdown_bot.learning.provenance import make_candidate_identity


def _fake_holdout_teams():
    # Rev. 14 fix (§1m, third review round P1): structurally valid (six entries, canonical
    # paths, non-empty hash-shaped strings) but NOT backed by any real committed git content --
    # fine as _write_arm's DEFAULT, since every row _write_arm builds is stamped from THIS SAME
    # mapping (below), so manifest and rows always agree with each other by construction,
    # regardless of whether the hash values are real. Tests that must reach the real leakage
    # scanner pass an explicit holdout_teams derived from _write_holdout_teams_repo instead
    # (_holdout_teams_mapping).
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    return {
        team_id: {"team_path": f"{HOLDOUT_TEAMS_DIR}{team_id}.txt", "content_hash": f"{i:016x}"}
        for i, team_id in enumerate(_six_teams())
    }


def _holdout_teams_mapping(hashes: dict) -> dict:
    """Converts a flat {team_id: content_hash} map (as _write_holdout_teams_repo returns, and as
    combine_strength_holdout_arms's own holdout_content_hashes parameter still takes -- that
    shape is UNCHANGED by Rev. 14) into the nested holdout_teams shape _write_arm's manifest now
    needs. Kept separate from _write_holdout_teams_repo itself so that helper's own job (real git
    repo + real hashes) stays focused."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    return {
        team_id: {"team_path": f"{HOLDOUT_TEAMS_DIR}{team_id}.txt", "content_hash": content_hash}
        for team_id, content_hash in hashes.items()
    }


def _write_arm(tmp_path, name, *, hero_agent, config_hash, git_sha="abc123", winner="hero", n=None,
                holdout_teams=None, stratum="windows", platform_attestation="Fixture-Platform-1",
                date_stratum_id="fixture-date-stratum-0", calc_backend="oneshot",
                seed_base="champions-strength-holdout-v0", panel_hash="panel1",
                schedule_hash=None):
    # Rev. 3 fix: candidate_identity is DERIVED via the real formula, never hardcoded the same
    # for both arms -- hero_agent is a hash input, so heuristic vs max_damage always produces
    # different identities. A test that hardcodes one shared value can't catch a broken equality
    # check between arms (exactly how Rev. 2's bug hid from its own tests).
    candidate_identity = make_candidate_identity(hero_agent=hero_agent, git_sha=git_sha, config_hash=config_hash)
    # "Zwei Reste" fix (Rev. 6): derive_battle_seed's real return shape is "sodium,<32 hex>",
    # never a bare int -- a fixture that writes "seed": i is the same class of unfaithful stand-in
    # N4 already fixed for JSON formatting, just on a different field. Local import, matching the
    # existing pattern in _write_valid_seed_log above.
    from showdown_bot.eval.seeding import derive_battle_seed as _seed_for
    # Rev. 14 fix (§1m, third review round P1): default matches _fake_holdout_teams() -- both
    # arms of a test that doesn't care about team identity specifically therefore agree with
    # each other AND with their own rows by construction (every row below is stamped from THIS
    # SAME mapping, cycled); a test that DOES care passes an explicit, different mapping for one
    # arm, or corrupts the written manifest/rows afterward (see the binding-mismatch tests below).
    if holdout_teams is None:
        holdout_teams = _fake_holdout_teams()
    # Review-fix (Task-10 review P1 #1): the arm this fixture writes must be a REAL canonical
    # 180-battle-key arm by default, not a 12-row stand-in. combine_strength_holdout_arms now
    # rebuilds the canonical schedule from the manifest's own team_ids/panel_hash/seed_base and
    # binds every row to exactly one battle key, so a fixture that emits an arbitrary row count
    # with a made-up "sched1" hash can no longer prove the success path -- and, worse, could not
    # have caught the truncated-arm hole the review found (two matching 12-row arms passed).
    # The rows below are therefore generated FROM build_strength_holdout_schedule itself.
    #
    # Fixtures that deliberately supply a structurally INVALID holdout_teams mapping (wrong
    # entry shape, wrong count, non-string ids) still need to reach combine's own shape
    # validation rather than exploding inside this helper, so a failed rebuild falls back to the
    # pre-review cycling behaviour with a placeholder hash -- those tests abort long before the
    # canonical-schedule guard runs.
    try:
        _schedule = build_strength_holdout_schedule(
            holdout_team_ids=sorted(holdout_teams), panel_hash=panel_hash, seed_base=seed_base,
        )
    except (ValueError, TypeError, AttributeError):
        _schedule = None
    arm_dir = tmp_path / name
    arm_dir.mkdir()
    rows = []
    if _schedule is not None:
        keys = _schedule.battle_keys if n is None else _schedule.battle_keys[:n]
        real_schedule_hash = _schedule.schedule_hash if schedule_hash is None else schedule_hash
        for key in keys:
            team_entry = holdout_teams[key.holdout_team_id]
            rows.append({
                "battle_id": f"b{key.seed_index}", "run_id": "r", "config_id": hero_agent,
                "format_id": "gen9championsvgc2026regma",
                "config_hash": config_hash, "schedule_hash": real_schedule_hash,
                "seed_index": key.seed_index,
                # opp_policy now comes from the battle key itself (real schedules alternate
                # heuristic/max_damage across the 12 (team, policy) cells) -- a fixture that
                # hardcoded "heuristic" for every row could never satisfy the canonical-schedule
                # binding this arm is supposed to demonstrate.
                "opp_policy": key.opponent_policy, "hero_team_path": "h.txt",
                "opp_team_path": team_entry["team_path"],
                "seed": _seed_for(seed_base, key.seed_index), "seed_base": seed_base,
                "winner": winner, "turns": 5,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 5.0, "git_sha": git_sha,
                "dirty": False, "end_reason": "normal", "opp_team_hash": team_entry["content_hash"],
                # panel_hash: required by pairing.py's _check_constant_fields (direct row[field]
                # index, pairing.py:105) even though result_jsonl.py's schema treats it as nullable
                # -- omitting it here reproduces the exact bug this fixture exists to catch.
                "panel_hash": panel_hash,
            })
    else:
        team_ids_cycle = sorted(holdout_teams)
        real_schedule_hash = "sched1" if schedule_hash is None else schedule_hash
        for i in range(12 if n is None else n):
            team_id = team_ids_cycle[i % len(team_ids_cycle)]
            team_entry = holdout_teams[team_id]
            rows.append({
                "battle_id": f"b{i}", "run_id": "r", "config_id": hero_agent,
                "format_id": "gen9championsvgc2026regma",
                "config_hash": config_hash, "schedule_hash": real_schedule_hash, "seed_index": i,
                "opp_policy": "heuristic", "hero_team_path": "h.txt",
                "opp_team_path": team_entry["team_path"],
                "seed": _seed_for(seed_base, i), "seed_base": seed_base,
                "winner": winner, "turns": 5,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 5.0, "git_sha": git_sha,
                "dirty": False, "end_reason": "normal", "opp_team_hash": team_entry["content_hash"],
                "panel_hash": panel_hash,
            })
    n = len(rows)
    # newline="" + separators=(",", ":") mirrors the canonical eval.result_jsonl.to_jsonl_line/
    # BattleResultWriter format (compact separators, LF only, no CRLF-on-Windows translation) --
    # a fixture that writes differently-formatted-but-equivalent JSON isn't wrong today (json.loads
    # doesn't care), but it stops being a faithful stand-in the moment anything hashes the file
    # (as combine's evidence bundle now does after the N2 fix below).
    with open(arm_dir / "rows.jsonl", "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    # Rev. 19 fix (Task 9 review-fix sync, §1r): a REAL seeds.jsonl, matching verify_seed_log's
    # own expected shape and derive_battle_seed's own real derivation, so combine's new per-arm
    # seed-artifact re-verification (_assert_seed_artifact_verified) can genuinely succeed
    # against real bytes -- not a manifest-only claim. newline="\n" (no translation) so the bytes
    # written match exactly what seed_log_sha256 below hashes.
    seed_log_lines = [
        json.dumps({"battle_index": i, "seed": _seed_for(seed_base, i), "seed_base": seed_base})
        for i in range(n)
    ]
    seed_log_text = "".join(line + "\n" for line in seed_log_lines)
    with open(arm_dir / "seeds.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(seed_log_text)
    seed_log_sha256 = hashlib.sha256(seed_log_text.encode("utf-8")).hexdigest()

    manifest = {
        "hero_agent": hero_agent, "schedule_hash": real_schedule_hash, "seed_base": seed_base,
        "panel_hash": panel_hash, "git_sha": git_sha, "config_hash": config_hash,
        "candidate_identity": candidate_identity, "n_rows": n,
        "holdout_teams": holdout_teams,
        # Rev. 15 fix (§1n, Task-3-review P1 #1): both arms default to the SAME stratum/
        # platform_attestation/date_stratum_id, so a test that doesn't care about strata
        # specifically (most of them) gets two equally-attested arms by construction -- exactly
        # the "accept two equally-attested arms" scenario the review requires as its own test.
        # A test that DOES care (mixed strata / differing date_stratum_id / contradictory
        # override) passes an explicit, different value for one arm.
        "stratum": stratum, "platform_attestation": platform_attestation,
        "date_stratum_id": date_stratum_id,
        # Rev. 19 fix (Task 9 review-fix sync, §1r): calc_backend + the four-field seed proof,
        # replacing the old caller-local seed_log_path field Task 9's own review-fix removed.
        "calc_backend": calc_backend,
        "seed_log_relpath": "seeds.jsonl", "seed_log_sha256": seed_log_sha256,
        "seed_log_n_lines": n, "seed_log_verified": True,
    }
    with open(arm_dir / "arm_manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return str(arm_dir)


def _fake_holdout_hashes():
    # Deliberately NOT six real committed teams: every remaining caller of this helper (below)
    # asserts an abort that fires before combine_strength_holdout_arms's holdout_teams
    # cross-check or the leakage scan ever run (Rev. 13/14, §1l/§1m) -- an i8d/coverage-path
    # guard, an arm-read/manifest-schema guard, or an arm-role/git_sha mismatch, all earlier in
    # the function. Content is irrelevant there; only non-empty-ness is. Tests that DO reach the
    # cross-check or the leakage scan use _write_holdout_teams_repo instead, not this.
    return {"holdout_0": "aaaa1111bbbb2222", "holdout_1": "cccc3333dddd4444"}


def _candidate_packed(index: int) -> str:
    """The packed content for holdout candidate #index -- two species, named by INDEX only (see
    _write_holdout_teams_repo for why the team_id must never appear in a species name)."""
    return f"|FixtureCandidate{index}A|||||||||]|FixtureCandidate{index}B|||||||||"


def _write_holdout_teams_repo(tmp_path):
    """A real, isolated git repo seeded with six committed, allowlist-conformant sealed team
    files. Rev. 13 fix (§1l, second review round P1): the leakage guard (Task 2) now reads
    committed git blobs at combine-time -- a test that actually reaches assert_no_holdout_leakage
    needs real committed content at the real HOLDOUT_TEAMS_DIR convention with teams_root pointed
    at it, not the ambient worktree (no sealed teams exist there yet -- Task 13 the plan task is
    still blocked) and not a bare fake hash string. _fake_holdout_hashes() above stays in use for
    the tests that abort before that guard ever runs, where content is irrelevant -- this helper
    is for every test that reaches it for real. tmp_path is already function-scoped, so a fresh
    repo per call means no test's mutation of it can leak into another. Returns (teams_root,
    holdout_content_hashes); team_ids match _six_teams()."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    from showdown_bot.eval.panel import team_content_hash

    repo = tmp_path / "teams_repo"
    team_dir = repo / HOLDOUT_TEAMS_DIR
    team_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)

    for i, team_id in enumerate(_six_teams()):
        (team_dir / f"{team_id}.txt").write_text(f"Fixture Mon {team_id} @ Focus Sash\n", encoding="utf-8")
        # Review-fix (Task-10 review P1 #3): combine now DERIVES each holdout team's species from
        # this real .packed file via load_team_species, instead of trusting a caller-supplied
        # species mapping -- so the packed content has to be genuinely parseable, with per-team
        # distinct species, not an inert placeholder.
        #
        # Species are keyed by INDEX, never by team_id: a species name containing the team_id
        # would, the moment a test copies it onto a reference team's packed file (see the
        # near-duplicate test), read to the leakage scanner as a real holdout identifier leaking
        # outside the allowlist -- a true positive from that guard, but about the fixture rather
        # than the code under test.
        (team_dir / f"{team_id}.packed").write_text(
            _candidate_packed(i), encoding="utf-8",
        )
    # Review-fix (Task-10 review P1 #3): the NINE canonical reference teams (five
    # panel_champions_v0 + four coverage foes) are no longer a caller-supplied species mapping
    # either -- combine reads them from their own real committed .packed files at the pinned
    # canonical paths. Any test that reaches the near-duplicate guard therefore needs them to
    # exist under this same teams_root, exactly like the six holdout teams above.
    for ref_id, ref_path in CANONICAL_REFERENCE_TEAM_PATHS.items():
        ref_file = repo / ref_path
        ref_file.parent.mkdir(parents=True, exist_ok=True)
        ref_file.write_text(f"Reference Mon {ref_id} @ Leftovers\n", encoding="utf-8")
        ref_file.with_suffix(".packed").write_text(
            f"|ReferenceMon{ref_id}A|||||||||]|ReferenceMon{ref_id}B|||||||||", encoding="utf-8",
        )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture holdout teams"], cwd=repo, check=True)

    hashes = {
        team_id: team_content_hash(str(repo), f"{HOLDOUT_TEAMS_DIR}{team_id}.txt")
        for team_id in _six_teams()
    }
    return str(repo), hashes


def _repo_head_sha(repo_root: str) -> str:
    """Review-fix (Task-10 review P1 #2): combine now refuses to run against a dirty tree and
    requires HEAD to equal the arms' recorded git_sha, so any test that reaches that guard for
    real needs the actual HEAD of the isolated fixture repo -- not the fixture's default
    "abc123" placeholder. Kept as its own helper so _write_holdout_teams_repo's existing
    two-value return contract (used by ~20 call sites) stays unchanged."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _patch_upstream_verdicts_as_pass(monkeypatch):
    # Rev. 3 fix: patch the REAL functions combine_strength_holdout_arms actually calls (they
    # have their own full, independent RED/GREEN coverage in Task 7) -- not a same-named
    # production-unreachable stub (Rev. 2's `_all_guards_pass_for_test` bug). Patching at
    # strength_holdout_runner's own imported name is what actually intercepts the call, since
    # Python resolves the name in the CALLING module's namespace at call time.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    # Rev. 4 P1 fix: baseline drift is now unconditionally checked too (see Task 10's
    # implementation) -- load_baseline/verify_baseline are existing, independently-tested
    # eval/baseline.py functions (not reimplemented here), so orchestration tests patch them
    # the same way as the two verdict-artifact functions above, for the same reason.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", lambda baseline, **kw: [])
    # Review-fix (Task-10 review P1 #2): combine now refuses a dirty tree and requires
    # HEAD == the arms' git_sha. _git_is_dirty/_git_sha are subprocess boundary calls into git --
    # the same category as the two upstream verdict verifiers patched above -- and the ambient
    # worktree these tests run in is legitimately dirty (untracked local artifacts), so leaving
    # them live would make every orchestration test abort on an irrelevant, environment-dependent
    # condition. Patched here to the fixture's own default git_sha, and separately proven against
    # a REAL, clean, isolated git repo by the three dedicated tests at the end of this file
    # (clean+matching HEAD passes, dirty aborts, HEAD mismatch aborts) -- which deliberately do
    # NOT call this helper, so the guard itself is never mocked away from its own coverage.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda cwd=None: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda cwd=None: "abc123")


def test_combine_does_not_require_matching_candidate_identity_between_arms(tmp_path, monkeypatch):
    # P1 fix (Rev. 3): make_candidate_identity hashes hero_agent, so arm A (heuristic) and arm B
    # (max_damage) NEVER share a candidate_identity for any genuine run -- DESIGN sec 5:
    # "Candidate A IS that shared candidate; Baseline B is the reference, not a separately-gated
    # candidate." This must succeed, not abort, despite the arms' candidate_identity differing.
    # Full valid success path, six real committed teams (Rev. 14, §1m, requirement 8): also now
    # exercises _assert_rows_bind_to_holdout_teams for real, not just the Rev. 13 checks.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)

    result = combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert result["verdict"] in ("UNDERPOWERED", "GO", "NO-GO", "SAFETY-FAIL")  # ran to a real verdict, did not abort


def test_combine_publishes_near_duplicate_flags_without_aborting_or_gating_the_verdict(tmp_path, monkeypatch):
    # Rev. 18 fix (§1q) / DESIGN sec 3.3: a near-duplicate flag is a manual-review hint, never an
    # automatic reject.
    #
    # Review-fix (Task-10 review P1 #3): the overlap is now created in the REAL .packed files
    # both sides are derived from, not by handing combine two caller-built species dicts. One
    # canonical reference team's packed content is rewritten to carry the exact species of one
    # holdout candidate, so load_team_species independently derives overlap_fraction == 1.0 for
    # that pair -- the same "flags identical species sets" scenario as before, but now proving
    # the derivation path rather than a caller's assertion.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    first_candidate_id = sorted(holdout_teams)[0]
    duplicated_ref_id = sorted(CANONICAL_REFERENCE_TEAM_PATHS)[0]
    # Copy holdout candidate #0's exact species pair onto one reference team's packed file, so
    # load_team_species derives overlap_fraction == 1.0 for that pair from real content.
    Path(teams_root, CANONICAL_REFERENCE_TEAM_PATHS[duplicated_ref_id]).with_suffix(".packed").write_text(
        _candidate_packed(sorted(holdout_teams).index(first_candidate_id)), encoding="utf-8",
    )

    result = combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert result["verdict"] in ("UNDERPOWERED", "GO", "NO-GO", "SAFETY-FAIL")  # not aborted
    flags = result["near_duplicate_flags"]
    assert len(flags) == 1
    assert flags[0]["candidate_team_id"] == first_candidate_id
    assert flags[0]["reference_team_id"] == duplicated_ref_id
    assert flags[0]["overlap_fraction"] == pytest.approx(1.0)


def test_combine_aborts_if_arms_disagree_on_git_sha(tmp_path, monkeypatch):
    # The replacement for Rev. 2's broken candidate_identity check: arms must share git_sha
    # (same commit) even though they never share candidate_identity.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", git_sha="sha-one")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", git_sha="sha-two", winner="villain")
    with pytest.raises(GateBAbort, match="git_sha"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arm_roles_are_swapped_or_wrong(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="max_damage", config_hash="cfgA")  # wrong: A must be heuristic
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="heuristic", config_hash="cfgB", winner="villain")
    with pytest.raises(GateBAbort, match="heuristic"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_without_an_i8d_verdict_path_before_any_pairing_or_publish(tmp_path, monkeypatch):
    # P1 fix (Rev. 3): Gate B may only run after an I8-D PASS -- an empty/omitted path must
    # abort, not silently skip verification. Must fire before out_dir exists at all.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    out_dir = tmp_path / "combined"
    with pytest.raises(GateBAbort, match="i8d_verdict_path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path="", coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_aborts_without_a_coverage_verdict_path_before_any_pairing_or_publish(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    out_dir = tmp_path / "combined"
    with pytest.raises(GateBAbort, match="coverage_verdict_path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path="",
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_wraps_a_strength_holdout_run_error_from_i8d_verification(tmp_path, monkeypatch):
    # NF2 fix (Rev. 7): verify_i8d_verdict_artifact/verify_coverage_verdict_artifact raise
    # StrengthHoldoutRunError -- a class the CLI (Task 11) never caught, only GateBAbort. Force
    # the FIRST of the two calls to fail and confirm it is normalized to GateBAbort here, at the
    # only place StrengthHoldoutRunError can cross into combine_strength_holdout_arms.
    _patch_upstream_verdicts_as_pass(monkeypatch)

    def _raise_i8d_error(**kw):
        raise StrengthHoldoutRunError("fixture-forced I8-D verification failure")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", _raise_i8d_error)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    with pytest.raises(GateBAbort, match="upstream verdict verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_wraps_a_strength_holdout_run_error_from_coverage_verification(tmp_path, monkeypatch):
    # Same as above, but forcing the SECOND call (verify_coverage_verdict_artifact) -- proves the
    # try/except wraps both call sites, not just whichever one happens to run first.
    _patch_upstream_verdicts_as_pass(monkeypatch)

    def _raise_coverage_error(**kw):
        raise StrengthHoldoutRunError("fixture-forced Coverage verification failure")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", _raise_coverage_error)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    with pytest.raises(GateBAbort, match="upstream verdict verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_publishes_full_evidence_bundle_not_just_verdict_json(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", winner="hero", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )

    assert (out_dir / "verdict.json").exists()
    assert (out_dir / "cells.json").exists()
    assert (out_dir / "arm_a" / "rows.jsonl").exists()
    assert (out_dir / "arm_b" / "rows.jsonl").exists()


def test_combine_appends_a_ledger_run_entry_with_all_real_required_fields(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    ledger_path = tmp_path / "ledger.jsonl"

    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(ledger_path),
    )

    entries = read_ledger(str(ledger_path))
    assert len(entries) == 1
    entry = entries[0]
    for field in ("kind", "date", "purpose", "panel_hash", "schedule_hash", "git_sha", "config_hash", "result_sha256", "justification"):
        assert field in entry, f"ledger entry missing required field {field!r}"
    assert entry["kind"] == "run"


def test_combine_refuses_a_repeat_config_hash_without_justification(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    ledger_path = tmp_path / "ledger.jsonl"
    arm_a = _write_arm(tmp_path, "arm_a1", hero_agent="heuristic", config_hash="dup-cfg", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b1", hero_agent="max_damage", config_hash="dup-cfg-b", winner="villain", holdout_teams=holdout_teams)
    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined1"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(ledger_path),
    )

    arm_a2 = _write_arm(tmp_path, "arm_a2", hero_agent="heuristic", config_hash="dup-cfg", holdout_teams=holdout_teams)
    arm_b2 = _write_arm(tmp_path, "arm_b2", hero_agent="max_damage", config_hash="dup-cfg-b", winner="villain", holdout_teams=holdout_teams)
    with pytest.raises(AccessBudgetError):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a2, arm_b_dir=arm_b2, out_dir=str(tmp_path / "combined2"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root,
            ledger_path=str(ledger_path),
        )


def test_combine_aborts_on_baseline_drift(tmp_path, monkeypatch):
    # P1 fix (Rev. 4): Task 6 creates/loads the baseline manifest, but nothing previously called
    # verify_baseline from the live combine flow. Patch load_baseline/verify_baseline directly
    # (not the umbrella helper) so THIS test proves the wiring actually calls verify_baseline
    # and reacts to a BaselineDriftError, rather than assuming it via the umbrella patch.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})

    from showdown_bot.eval.baseline import BaselineDriftError

    def _raise_drift(baseline, **kw):
        raise BaselineDriftError("fixture-forced drift")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", _raise_drift)
    # Review-fix (Task-10 review P1 #2): this test patches the baseline functions directly rather
    # than via the umbrella helper, so it must patch the two git helpers itself as well -- the
    # HEAD-binding guard now runs before verify_baseline and would otherwise abort on the ambient
    # worktree being dirty, masking the baseline-drift path this test exists to prove.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda cwd=None: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda cwd=None: "abc123")
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    with pytest.raises(GateBAbort, match="baseline drift"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_wraps_a_non_missing_pair_error_too(tmp_path, monkeypatch):
    # P2 fix (Rev. 4): pair_runs can raise several PairingError subclasses -- Rev. 3 only
    # caught MissingPairError. Force a DIFFERENT subclass (DuplicateRowError, via a duplicate
    # battle_id/config_hash pair in arm A's own rows) and confirm it still becomes GateBAbort.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    # Review-fix (Task-10 review P1 #1): this test used to duplicate a row inside arm A to force
    # a DuplicateRowError out of the real pair_runs. That is no longer reachable -- the new
    # canonical-schedule guard rejects "two rows claim the same battle key" strictly earlier, by
    # design. The behaviour under test here is the EXCEPT clause (every PairingError subclass,
    # not just MissingPairError, is folded into GateBAbort), so the error is now injected at the
    # pair_runs seam directly, with two otherwise-valid canonical arms.
    from showdown_bot.eval.pairing import DuplicateRowError

    def _raise_duplicate(rows_a, rows_b, *, expected_rows):
        raise DuplicateRowError("fixture-forced duplicate row")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.pair_runs", _raise_duplicate)

    with pytest.raises(GateBAbort, match="pairing failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined2"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_rejects_empty_holdout_content_hashes(tmp_path, monkeypatch):
    # P2 fix (Rev. 4): an empty mapping makes the disjointness/leakage guards vacuous in
    # production just as much as in a test -- reject it unconditionally.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    with pytest.raises(GateBAbort, match="holdout_content_hashes"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={},
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_an_arms_manifest_does_not_match_its_own_rows(tmp_path, monkeypatch):
    # F3 fix (Rev. 6): an arm directory assembled from two different runs (here: arm A's
    # manifest swapped for one with a different config_hash than its own rows.jsonl actually
    # carries) must abort -- before this fix it passed I8-D verification, Coverage verification,
    # check_access, the ledger entry, and the published verdict unnoticed.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    # Swap in a manifest whose config_hash doesn't match what's actually in arm_a/rows.jsonl.
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["config_hash"] = "a-completely-different-config-hash-from-another-run"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="config_hash"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_on_a_malformed_row_not_a_raw_resultrowerror(tmp_path, monkeypatch):
    # NF1 fix (Rev. 7): _read_arm's validate_battle_row call can raise ResultRowError -- before
    # this fix that exception was never imported or caught anywhere in this module, so a
    # corrupted or stale-schema rows.jsonl would escape combine_strength_holdout_arms raw,
    # uncaught by the CLI (which only ever catches GateBAbort). Corrupt one row in arm A by
    # deleting a required field (result_jsonl.REQUIRED_FIELDS includes "turns") and confirm the
    # abort is GateBAbort, not ResultRowError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    rows_path = tmp_path / "arm_a" / "rows.jsonl"
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    first_row = json.loads(lines[0])
    del first_row["turns"]
    lines[0] = json.dumps(first_row, sort_keys=True, separators=(",", ":"))
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(GateBAbort, match="malformed row"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_on_a_manifest_missing_a_required_key_not_a_raw_keyerror(tmp_path, monkeypatch):
    # NF1 fix (Rev. 7): _assert_rows_match_manifest used to index manifest["n_rows"]/
    # manifest[field] directly -- a truncated or hand-edited manifest missing any of those keys
    # raised a raw KeyError, uncaught by the CLI. Delete "panel_hash" (also required one step
    # further downstream by pairing.py's own _check_constant_fields) and confirm the abort is
    # GateBAbort, not KeyError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["panel_hash"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="missing required key"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_when_an_arm_directory_is_missing_not_a_raw_oserror(tmp_path, monkeypatch):
    # Self-found while building the Rev. 7 exception-audit table (§1f): _read_arm's open() calls
    # can raise FileNotFoundError (an OSError) for a missing/never-published arm directory --
    # not ResultRowError, so NF1's own fix does not catch it. Confirm the abort is GateBAbort,
    # not a raw OSError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    with pytest.raises(GateBAbort, match="cannot read arm directory"):
        combine_strength_holdout_arms(
            arm_a_dir=str(tmp_path / "arm_a_never_published"), arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_on_truncated_json_not_a_raw_jsondecodeerror(tmp_path, monkeypatch):
    # Same audit finding as above, the json.JSONDecodeError branch: a truncated/corrupted
    # arm_manifest.json must abort as GateBAbort, not escape as json.JSONDecodeError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    (tmp_path / "arm_a" / "arm_manifest.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(GateBAbort, match="malformed JSON"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_does_not_publish_if_the_ledger_append_fails(tmp_path, monkeypatch):
    # F6 fix (Rev. 6): the ledger entry now happens BEFORE publish -- if append_entry fails for
    # any reason, out_dir must never come into existence, so a failed ledger write can never
    # coexist with a "successful"-looking published bundle the next run's check_access wouldn't
    # even know to budget against.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    from showdown_bot.eval.heldout_ledger import LedgerError

    def _raise_ledger_error(path, entry):
        raise LedgerError("fixture-forced ledger failure")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.append_entry", _raise_ledger_error)

    with pytest.raises(GateBAbort, match="ledger"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_aborts_if_holdout_content_hashes_omits_a_scheduled_team(tmp_path, monkeypatch):
    # P1 fix (Rev. 13, §1l, second review round): holdout_content_hashes being non-empty is not
    # enough -- it must cover every team the schedule actually played, or the leakage/
    # disjointness guards below would silently scan only whichever subset a caller happened to
    # supply. Both arms agree on all six teams (the _write_arm default); holdout_content_hashes
    # here covers only one of them. No real teams_repo needed -- this abort fires before the
    # leakage scan ever runs.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    with pytest.raises(GateBAbort, match="does not match the six teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={"holdout_0": "fakehash1111aaaa"},
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_holdout_content_hashes_has_a_wrong_value_for_a_correct_key(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m, third review round): Rev. 13 only checked KEY-set equality between
    # holdout_content_hashes and the schedule's real team set -- a caller supplying every right
    # team_id but a WRONG hash value for one of them would have passed that check. The comparison
    # is now full dict equality (keys AND values).
    _patch_upstream_verdicts_as_pass(monkeypatch)
    holdout_teams = _fake_holdout_teams()
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    wrong_value_hashes = {t: e["content_hash"] for t, e in holdout_teams.items()}
    wrong_value_hashes[sorted(holdout_teams)[0]] = "totally-wrong-hash-value"
    with pytest.raises(GateBAbort, match="does not match the six teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=wrong_value_hashes,
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arms_disagree_on_holdout_teams(tmp_path, monkeypatch):
    # P1 fix (Rev. 13/14, §1l/§1m): holdout_teams is part of the same arm-vs-arm agreement check
    # as schedule_hash/panel_hash/seed_base -- two arms that somehow scheduled a different team
    # set were not played under the same battle conditions. Each entry in mismatched_teams is
    # itself internally well-formed (_holdout_teams_mapping derives team_path from its own key),
    # so only the arm-vs-arm inequality fires here, not the structural/canonical-path checks.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    default_teams = _fake_holdout_teams()
    mismatched_ids = _six_teams()[:5] + ["holdout_other"]
    mismatched_teams = _holdout_teams_mapping({tid: f"{i:016x}" for i, tid in enumerate(mismatched_ids)})
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=mismatched_teams)
    with pytest.raises(GateBAbort, match="holdout_teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={t: e["content_hash"] for t, e in default_teams.items()},

            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_both_manifests_claim_wrong_teams_but_rows_are_unchanged(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m, third review round): a manifest's holdout_teams is just an assertion
    # until bound to the rows -- if BOTH arms' manifests agree with EACH OTHER (so an arm-vs-arm
    # check alone would pass) but neither actually matches what's in rows.jsonl (still the
    # normal, real per-team data from _write_arm), the leakage/disjointness guards would scan for
    # the WRONG six teams while the REAL opponent teams go completely unchecked.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    wrong_teams = _holdout_teams_mapping({f"wrong_{i}": f"{i:016x}" for i in range(6)})
    for arm_dir in (tmp_path / "arm_a", tmp_path / "arm_b"):
        manifest_path = arm_dir / "arm_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["holdout_teams"] = wrong_teams
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="not one of the six"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={t: e["content_hash"] for t, e in wrong_teams.items()},

            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_a_rows_opp_team_hash_does_not_match_the_manifest(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): a manifest can declare the CORRECT team_id/team_path for a team
    # while lying about its content_hash -- only binding opp_team_hash per row catches this; a
    # bare ID (or even a team_path-only mapping) never would.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_team_id = sorted(manifest["holdout_teams"])[0]
    manifest["holdout_teams"][first_team_id]["content_hash"] = "wrong-hash-not-in-rows"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(GateBAbort, match="does not match holdout_teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_a_manifest_team_path_is_not_canonical(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): a manifest could declare the right team_id and a content_hash that
    # matches its own rows, but point team_path at a non-canonical location -- rejected by
    # _validate_holdout_teams_mapping before any row-binding check even runs.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_team_id = sorted(manifest["holdout_teams"])[0]
    manifest["holdout_teams"][first_team_id]["team_path"] = "showdown_bot/teams/wrong_dir/not_canonical.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(GateBAbort, match="canonical path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_one_row_has_an_unknown_opponent_path(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): the manifest itself may be perfectly valid and match every OTHER
    # row -- a single corrupted row with an opp_team_path outside the declared six must still
    # abort, not slip through because most rows are fine.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    rows_path = tmp_path / "arm_a" / "rows.jsonl"
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    first_row = json.loads(lines[0])
    first_row["opp_team_path"] = "showdown_bot/teams/panel_champions_v0/not_a_holdout_team.txt"
    lines[0] = json.dumps(first_row, sort_keys=True, separators=(",", ":"))
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(GateBAbort, match="not one of the six"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_a_manifest_team_never_appears_in_rows(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): a manifest declaring six teams is not enough if one of them never
    # actually appears among the rows -- e.g. a battle silently never got played for that team,
    # or every row for it got corrupted/overwritten. The leakage/disjointness guards must never
    # trust a declared team that isn't backed by at least one real row.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    holdout_teams = _fake_holdout_teams()
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", n=12, holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", n=12, holdout_teams=holdout_teams)
    # Overwrite every row that would have represented team_ids[5] (rows 5 and 11 -- n=12 cycling
    # 6 teams puts that team at both positions) with team_ids[0]'s data instead: team_ids[5] is
    # still fully declared in the manifest, but now appears in zero rows.
    rows_path = tmp_path / "arm_a" / "rows.jsonl"
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    lines[5] = lines[0]
    lines[11] = lines[0]
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(GateBAbort, match="never appear in rows"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={t: e["content_hash"] for t, e in holdout_teams.items()},

            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_holdout_teams_has_an_invalid_shape(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): holdout_teams must be a genuine object/mapping with exactly the
    # expected shape -- null, a bare string, an array, or a mapping whose entries carry
    # unexpected fields must all be rejected fail-closed, before any row-binding check even
    # attempts to read it.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    valid_teams = _fake_holdout_teams()
    first_id = sorted(valid_teams)[0]
    malformed_shapes = {
        "null": None,
        "string": ",".join(sorted(valid_teams)),
        "array": sorted(valid_teams),
        "unknown_field": {**valid_teams, first_id: {**valid_teams[first_id], "extra_field": "x"}},
    }
    for label, shape in malformed_shapes.items():
        arm_a = _write_arm(tmp_path, f"arm_a_{label}", hero_agent="heuristic", config_hash="cfgA")
        arm_b = _write_arm(tmp_path, f"arm_b_{label}", hero_agent="max_damage", config_hash="cfgB", winner="villain")
        manifest_path = tmp_path / f"arm_a_{label}" / "arm_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["holdout_teams"] = shape
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(GateBAbort, match="holdout_teams"):
            combine_strength_holdout_arms(
                arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / f"combined_{label}"),
                i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
                holdout_content_hashes=_fake_holdout_hashes(),
                stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
            )


# Rev. 15 (§1n, Task-3-review): Task 9 now writes stratum/platform_attestation/date_stratum_id
# into each arm's own manifest (its own Rev. 15 fix); the six tests below prove Task 10 validates
# them in closed form and compares the two ACTUAL arm records, never re-determining its own
# stratum from detect_stratum().


def test_combine_rejects_mixed_windows_and_kaggle_arms(tmp_path, monkeypatch):
    # P1 #3: "different strata... must abort" -- arm A played on Windows, arm B on Kaggle, must
    # never combine even though every other field agrees.
    from showdown_bot.eval.strata_guard import StrataPoolingError
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, stratum="windows")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, stratum="kaggle")

    with pytest.raises(StrataPoolingError):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_accepts_two_equally_attested_arms(tmp_path, monkeypatch):
    # Required test: the mirror image of the rejection above -- two arms sharing one stratum,
    # each with its own non-empty platform_attestation, must combine successfully.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, stratum="windows",
                        platform_attestation="Windows-11-10.0.26200")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, stratum="windows",
                        platform_attestation="Windows-11-10.0.26200")

    result = combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert result["stratum"] == "windows"


def test_combine_rejects_a_contradictory_stratum_override(tmp_path, monkeypatch):
    # Required test: both arms genuinely agree (windows/windows), but the caller-supplied
    # stratum_env_override="kaggle" contradicts what they actually recorded -- must abort, not
    # silently force a mismatched label onto real data.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, stratum="windows")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, stratum="windows")

    with pytest.raises(GateBAbort, match="contradicts"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="kaggle", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arms_disagree_on_date_stratum_id(tmp_path, monkeypatch):
    # P1 #3: "different... date-strata must abort" -- same stratum (windows/windows, so
    # assert_no_cross_stratum_pooling alone would NOT catch this) but two different pre-
    # registered run identifiers must still never combine.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        date_stratum_id="run-2026-07-01")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        date_stratum_id="run-2026-08-01")

    with pytest.raises(GateBAbort, match="date_stratum_id"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_an_unknown_stratum_value(tmp_path, monkeypatch):
    # P1 #4: "unknown... manifest values must abort" -- a stratum value present but not one of
    # strata_guard.VALID_STRATA (a hand-edited or future-format manifest) must be rejected in
    # closed form, not silently accepted or crash downstream with a raw KeyError/ValueError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stratum"] = "colab"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="not one of the known strata"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_a_type_wrong_platform_attestation(tmp_path, monkeypatch):
    # P1 #4: "type-wrong manifest values must abort" -- a non-string platform_attestation (an
    # accidental int from a hand-edited or differently-typed manifest) must be rejected, not
    # silently accepted or crash the StratumRecord construction downstream unclearly.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["platform_attestation"] = 12345
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="platform_attestation"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


# Rev. 19 (Task 9 review-fix sync, §1r): Task 9's own review-fix (5 P1s) added calc_backend
# (derived internally, threaded through) and replaced the caller-local seed_log_path field with a
# four-field seed PROOF (seed_log_relpath/seed_log_sha256/seed_log_n_lines/seed_log_verified) --
# the thirteen tests below prove Task 10 validates the new fields in closed form, independently
# re-verifies both arms' real seed-log bytes (never trusting seed_log_verified=True alone), and
# passes the manifest-bound calc_backend to both upstream verifiers instead of a hardcoded
# "oneshot" literal.

def test_combine_aborts_if_manifest_is_missing_calc_backend(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["calc_backend"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="missing required key"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arms_disagree_on_calc_backend(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", calc_backend="oneshot")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", calc_backend="persistent")

    with pytest.raises(GateBAbort, match="calc_backend"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_passes_the_manifest_bound_calc_backend_to_both_upstream_verifiers(tmp_path, monkeypatch):
    # Proves the fix directly: mocks capture the kwargs each upstream verifier was actually
    # called with, using a NON-DEFAULT backend ("persistent") so a hardcoded "oneshot" literal
    # would be caught red-handed, not accidentally matched by coincidence.
    calls = {}

    def _capture_i8d(**kw):
        calls["i8d"] = kw
        return {"verdict": "PASS"}

    def _capture_coverage(**kw):
        calls["coverage"] = kw
        return {"verdict": "PASS"}

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", _capture_i8d)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", _capture_coverage)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", lambda baseline, **kw: [])
    # Review-fix (Task-10 review P1 #2): this test installs its own capturing verifiers instead of
    # the umbrella helper, so it must stub the two git helpers itself -- the HEAD-binding guard
    # runs before the verifiers and would otherwise abort on the ambient dirty worktree.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda cwd=None: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda cwd=None: "abc123")
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, calc_backend="persistent")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, calc_backend="persistent")

    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert calls["i8d"]["calc_backend"] == "persistent"
    assert calls["coverage"]["calc_backend"] == "persistent"


def test_combine_aborts_if_manifest_is_missing_a_seed_proof_field(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    for field in ("seed_log_relpath", "seed_log_sha256", "seed_log_n_lines", "seed_log_verified"):
        arm_a = _write_arm(tmp_path, f"arm_a_{field}", hero_agent="heuristic", config_hash="cfgA")
        arm_b = _write_arm(tmp_path, f"arm_b_{field}", hero_agent="max_damage", config_hash="cfgB", winner="villain")
        manifest_path = tmp_path / f"arm_a_{field}" / "arm_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest[field]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(GateBAbort, match="missing required key"):
            combine_strength_holdout_arms(
                arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / f"combined_{field}"),
                i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
                holdout_content_hashes=_fake_holdout_hashes(),
                stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
            )


def test_combine_aborts_if_seed_log_verified_is_not_true(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_verified"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_verified"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_an_absolute_seed_log_relpath(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_relpath"] = str(tmp_path / "arm_a" / "seeds.jsonl")  # absolute, not "seeds.jsonl"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_relpath"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_a_traversing_seed_log_relpath(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_relpath"] = "../seeds.jsonl"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_relpath"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_file_is_missing(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    (tmp_path / "arm_a" / "seeds.jsonl").unlink()

    with pytest.raises(GateBAbort, match="cannot read seed log"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_sha256_does_not_match(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = "0" * 64  # a well-formed but wrong digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="does not match manifest's seed_log_sha256"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_content_fails_verify_seed_log(tmp_path, monkeypatch):
    # The sha256 is recomputed to match the CORRUPTED content, isolating this test to
    # verify_seed_log's own content check (wrong seed_base recorded in every line), not the
    # digest check above.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    from showdown_bot.eval.seeding import derive_battle_seed as _dbs
    corrupted_text = "".join(
        json.dumps({"battle_index": i, "seed": _dbs("wrong-seed-base-recorded", i), "seed_base": "wrong-seed-base-recorded"}) + "\n"
        for i in range(12)
    )
    (tmp_path / "arm_a" / "seeds.jsonl").write_text(corrupted_text, encoding="utf-8", newline="\n")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = hashlib.sha256(corrupted_text.encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_seed_log_n_lines_does_not_match_the_verified_count(tmp_path, monkeypatch):
    # manifest claims n_rows=12 (matching rows.jsonl, so verify_seed_log's own expected_count
    # check passes) but seed_log_n_lines is a DIFFERENT, wrong number -- isolates the SEPARATE
    # seed_log_n_lines-vs-verified-count check from the n_rows-bound expected_count check inside
    # verify_seed_log itself.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_n_lines"] = 179
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_n_lines"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_line_count_does_not_match_n_rows(tmp_path, monkeypatch):
    # The seed log genuinely verifies against seed_base, but has a DIFFERENT line count than
    # n_rows -- verify_seed_log's own expected_count=manifest["n_rows"] parameter must catch this
    # (SeedLogError, wrapped as GateBAbort), not just the separate seed_log_n_lines check.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    from showdown_bot.eval.seeding import derive_battle_seed as _dbs
    # 179 lines (not 180) -- still genuinely verifiable seeds, just the wrong count vs n_rows.
    short_text = "".join(
        json.dumps({"battle_index": i, "seed": _dbs("champions-strength-holdout-v0", i), "seed_base": "champions-strength-holdout-v0"}) + "\n"
        for i in range(179)
    )
    (tmp_path / "arm_a" / "seeds.jsonl").write_text(short_text, encoding="utf-8", newline="\n")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = hashlib.sha256(short_text.encode("utf-8")).hexdigest()
    manifest["seed_log_n_lines"] = 179
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_verifies_both_arms_seed_logs_independently(tmp_path, monkeypatch):
    # Arm A's seed log is genuinely valid; ONLY arm B's is corrupted. Must still abort -- proves
    # both arms are independently re-verified, not just arm A (or only checked once via shared
    # manifest agreement).
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    manifest_path = tmp_path / "arm_b" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="does not match manifest's seed_log_sha256"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def _make_windows_junction(link_path, target_path):
    """Creates a Windows directory junction via mklink /J -- unlike symlinks, this needs no
    admin privilege / Developer Mode. Raises OSError on failure. Mirrors Task 9's own
    _make_windows_junction helper."""
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise OSError(f"mklink /J failed (rc={result.returncode}): {result.stdout} {result.stderr}")


def test_combine_rejects_a_seed_log_symlink_escape_from_the_arm_directory(tmp_path, monkeypatch):
    import os as _os
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    escape_target_dir = tmp_path / "outside_arm_a"
    escape_target_dir.mkdir()
    real_seed_log = tmp_path / "arm_a" / "seeds.jsonl"
    escape_target = escape_target_dir / "seeds.jsonl"
    escape_target.write_text(real_seed_log.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    real_seed_log.unlink()
    try:
        _os.symlink(str(escape_target), str(real_seed_log))
    except OSError:
        try:
            _make_windows_junction(real_seed_log, escape_target)
        except OSError as exc:
            pytest.skip(
                "neither os.symlink nor mklink /J is available in this test environment "
                f"(insufficient privilege) -- cannot exercise a real link escape: {exc}"
            )

    # The symlink points to a byte-identical copy, so sha256/verify_seed_log both still pass --
    # the containment check must fire regardless, on the resolved location alone. Self-found:
    # Windows can raise a raw OSError (WinError 267) while RESOLVING certain symlink
    # configurations, before the containment comparison itself ever runs -- both outcomes are
    # an acceptable, fail-closed rejection of the escape attempt (never a raw traceback, never a
    # silent accept), so the match covers either message.
    with pytest.raises(GateBAbort, match="outside its own arm directory|cannot resolve seed log path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


# ---------------------------------------------------------------------------
# Task-10 review-fix (three P1s + two P2s). Every test below goes RED against
# 24ada4b and closes exactly one reviewed finding.
# ---------------------------------------------------------------------------


def _combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, **overrides):
    """The full valid argument set for a far-reaching combine call, so the review-fix tests
    below differ only in the ONE thing each is about."""
    kwargs = dict(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes, stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    kwargs.update(overrides)
    return kwargs


# --- P1 #1: the canonical 180-battle-key schedule must be rebuilt and bound ------------------


def test_combine_accepts_two_real_canonical_180_key_arms(tmp_path, monkeypatch):
    """P1 #1 baseline: the DEFAULT fixture arm is now a real 180-row canonical arm, and the
    success path still runs to a real verdict through the new schedule guard."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    # The fixture really did emit the full canonical schedule, not a 12-row stand-in.
    with open(Path(arm_a) / "arm_manifest.json", encoding="utf-8") as fh:
        assert json.load(fh)["n_rows"] == 180

    result = combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))
    assert result["n_total"] == 180


def test_combine_aborts_on_a_truncated_arm_that_omits_battle_keys(tmp_path, monkeypatch):
    """P1 #1, the exact hole the review found: two arms that AGREE with each other and with
    their own manifests, but only carry 12 of the canonical 180 battle keys, were accepted.
    A short arm is not a strength result at all -- it must abort."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, n=179)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, n=179)

    with pytest.raises(GateBAbort, match="canonical|180|battle key"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))
    assert not os.path.exists(str(tmp_path / "combined"))


def test_combine_aborts_if_the_manifest_schedule_hash_is_not_the_canonical_rebuild(tmp_path, monkeypatch):
    """P1 #1: schedule_hash must be the value build_strength_holdout_schedule itself derives from
    the manifest's own team_ids/panel_hash/seed_base -- a self-consistent but forged label
    (stamped identically on the manifest AND every row of BOTH arms) must not pass."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                       holdout_teams=holdout_teams, schedule_hash="0123456789abcdef")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                       holdout_teams=holdout_teams, schedule_hash="0123456789abcdef")

    with pytest.raises(GateBAbort, match="schedule_hash"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_aborts_on_an_unpinned_seed_base(tmp_path, monkeypatch):
    """P1 #1: the rebuild is fed the manifest's OWN seed_base, so that one field must be checked
    separately against the pinned namespace -- otherwise a foreign seed_base rebuilds
    self-consistently and the check is vacuous (Task 9's _assert_schedule_is_genuine makes the
    same distinction for the same reason)."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                       holdout_teams=holdout_teams, seed_base="not-the-pinned-namespace")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                       holdout_teams=holdout_teams, seed_base="not-the-pinned-namespace")

    with pytest.raises(GateBAbort, match="seed_base"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_aborts_if_a_row_does_not_match_its_canonical_battle_key(tmp_path, monkeypatch):
    """P1 #1: the right NUMBER of rows is not enough -- each row must correspond to exactly one
    real battle key. Here one row's opp_policy is flipped, so the played set no longer covers
    the canonical (team, policy, seed_index) grid even though the count still says 180."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    rows_path = Path(arm_a) / "rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["opp_policy"] = "max_damage" if rows[0]["opp_policy"] == "heuristic" else "heuristic"
    with open(rows_path, "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(GateBAbort, match="battle key|canonical"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


# --- P1 #2: the combine result must be bound to a clean, matching HEAD -----------------------


def _patch_non_git_dependencies(monkeypatch):
    """Everything _patch_upstream_verdicts_as_pass patches EXCEPT the two git helpers -- so the
    three HEAD-binding tests below exercise the real _git_is_dirty/_git_sha against a real,
    isolated git repo instead of a stub."""
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", lambda baseline, **kw: [])


def test_combine_accepts_a_clean_repo_whose_head_matches_the_arms(tmp_path, monkeypatch):
    """P1 #2, positive half -- deliberately does NOT patch _git_is_dirty/_git_sha: the REAL git
    calls run against the real, clean, isolated fixture repo, whose real HEAD is what both arms
    recorded."""
    _patch_non_git_dependencies(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    head = _repo_head_sha(teams_root)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, git_sha=head)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, git_sha=head)

    result = combine_strength_holdout_arms(
        **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, repo_root=teams_root)
    )
    assert result["git_sha"] == head


def test_combine_refuses_a_dirty_working_tree(tmp_path, monkeypatch):
    """P1 #2: baseline/leakage/report checks read the CURRENT checkout, so an uncommitted change
    can silently alter what those guards see while the published bundle is still labelled with
    the arms' old git_sha. Real git, real dirty repo, no patching of the guard itself."""
    _patch_non_git_dependencies(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    head = _repo_head_sha(teams_root)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, git_sha=head)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, git_sha=head)
    Path(teams_root, "uncommitted_change.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(GateBAbort, match="dirty"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, repo_root=teams_root)
        )
    assert not os.path.exists(str(tmp_path / "combined"))


def test_combine_refuses_when_head_does_not_match_the_arms_git_sha(tmp_path, monkeypatch):
    """P1 #2: a clean tree is not enough -- combining arms played at commit X while the checkout
    sits at commit Y would run the repo-dependent guards against Y and label the result X."""
    _patch_non_git_dependencies(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    # Both arms claim a DIFFERENT commit than the repo's real HEAD.
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, git_sha="f" * 40)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, git_sha="f" * 40)

    with pytest.raises(GateBAbort, match="HEAD"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, repo_root=teams_root)
        )


# --- P1 #3: species evidence must come from the real .packed files ---------------------------


def test_combine_derives_both_species_sides_from_real_packed_files(tmp_path, monkeypatch):
    """P1 #3: holdout_candidate_species/reference_species were caller assertions and
    load_team_species had no production call site at all. Both sides are now derived from real
    sealed files -- proven here by recording every path load_team_species is asked for and
    checking it is exactly the six row-bound holdout teams plus the nine canonical references."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)

    from showdown_bot.eval import strength_holdout_runner as mod
    real_loader = mod.load_team_species
    asked = []

    def _recording_loader(team_path, *, teams_root):
        asked.append(team_path)
        return real_loader(team_path, teams_root=teams_root)

    monkeypatch.setattr(mod, "load_team_species", _recording_loader)

    combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))

    expected_holdout = {entry["team_path"] for entry in holdout_teams.values()}
    expected_reference = set(CANONICAL_REFERENCE_TEAM_PATHS.values())
    assert len(expected_reference) == 9
    assert set(asked) == expected_holdout | expected_reference


def test_combine_aborts_if_a_holdout_teams_packed_file_is_missing(tmp_path, monkeypatch):
    """P1 #3: with species now DERIVED, an unreadable sealed team is a real, fail-closed abort
    (load_team_species raises ValueError) -- not something a caller can paper over by supplying
    a species list for a file that is not there."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    victim = sorted(holdout_teams)[0]
    Path(teams_root, holdout_teams[victim]["team_path"]).with_suffix(".packed").unlink()

    with pytest.raises(GateBAbort, match="species"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_aborts_if_a_canonical_reference_packed_file_is_missing(tmp_path, monkeypatch):
    """P1 #3, reference side: the nine canonical references are pinned paths, not caller input,
    so a missing one is likewise a fail-closed abort rather than a silently smaller comparison
    set that would make the near-duplicate guard quietly weaker."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    victim = sorted(CANONICAL_REFERENCE_TEAM_PATHS)[0]
    Path(teams_root, CANONICAL_REFERENCE_TEAM_PATHS[victim]).with_suffix(".packed").unlink()

    with pytest.raises(GateBAbort, match="species"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_canonical_reference_team_paths_are_the_nine_real_champions_teams():
    """P1 #3: the pinned reference set is the nine EXISTING Champions M-A teams (five
    panel_champions_v0 + four coverage foes), and every one of them really exists in this repo
    -- a pinned constant that drifts from the tree would silently weaken the guard."""
    assert len(CANONICAL_REFERENCE_TEAM_PATHS) == 9
    for team_id, rel_path in CANONICAL_REFERENCE_TEAM_PATHS.items():
        assert Path(rel_path).with_suffix(".packed").exists(), f"{team_id} -> {rel_path}"


# --- P2 #4: non-object JSON must abort, not raise a raw TypeError ----------------------------


def test_combine_aborts_on_a_non_object_row_not_a_raw_typeerror(tmp_path, monkeypatch):
    """P2 #4, freshly reproduced by the reviewer: a `null` row reached validate_battle_row, which
    raised TypeError ('argument of type NoneType is not a container') -- escaping the GateBAbort
    contract the CLI relies on."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    with open(Path(arm_a) / "rows.jsonl", "a", encoding="utf-8", newline="") as fh:
        fh.write("null\n")

    with pytest.raises(GateBAbort, match="object"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, ".", _fake_holdout_hashes())
        )


def test_combine_aborts_on_a_non_object_manifest_not_a_raw_typeerror(tmp_path, monkeypatch):
    """P2 #4, manifest side: `null` reached `set(manifest)` and raised
    TypeError ('NoneType object is not iterable')."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    (Path(arm_a) / "arm_manifest.json").write_text("null", encoding="utf-8")

    with pytest.raises(GateBAbort, match="object"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, ".", _fake_holdout_hashes())
        )


# --- P2 #5: the access-budget check and its reservation must be one atomic section -----------


def test_combine_holds_one_lock_across_the_budget_check_and_the_ledger_append(tmp_path, monkeypatch):
    """P2 #5: check_access read the ledger near the start and append_entry wrote it much later,
    so two concurrent combines could both observe a free budget and both publish. Proven here by
    recording lock state at each call: both must happen while the SAME lock is held."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    ledger_path = str(tmp_path / "ledger.jsonl")

    from showdown_bot.eval import strength_holdout_runner as mod
    events = []
    real_check, real_append = mod.check_access, mod.append_entry

    def _spy_check(entries, config_hash, **kw):
        events.append(("check", os.path.exists(ledger_path + ".lock")))
        return real_check(entries, config_hash, **kw)

    def _spy_append(path, entry):
        events.append(("append", os.path.exists(ledger_path + ".lock")))
        return real_append(path, entry)

    monkeypatch.setattr(mod, "check_access", _spy_check)
    monkeypatch.setattr(mod, "append_entry", _spy_append)

    combine_strength_holdout_arms(
        **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, ledger_path=ledger_path)
    )
    # The AUTHORITATIVE check is the one immediately before the reservation, and both are under
    # the lock. (An earlier, unlocked check_access is allowed as a fail-fast, so this asserts the
    # tail of the sequence rather than the whole of it.)
    assert events[-2:] == [("check", True), ("append", True)]
    # And the lock is released again once the section completes.
    assert not os.path.exists(ledger_path + ".lock")


def test_combine_refuses_to_start_while_another_combine_holds_the_ledger_lock(tmp_path, monkeypatch):
    """P2 #5: a second concurrent combine must not slip past the budget while the first one is
    still between its check and its append -- it aborts fail-closed instead of racing."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    ledger_path = str(tmp_path / "ledger.jsonl")
    Path(ledger_path + ".lock").write_text("held by another combine\n", encoding="utf-8")

    with pytest.raises(GateBAbort, match="lock"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, ledger_path=ledger_path)
        )
    assert not os.path.exists(str(tmp_path / "combined"))

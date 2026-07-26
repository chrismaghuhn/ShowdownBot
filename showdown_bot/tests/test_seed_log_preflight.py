"""Seed-log wiring must fail fast and be impossible to half-configure.

The seed-log pairing has two halves that live in DIFFERENT processes:

- the **client** half -- ``SHOWDOWN_EVAL_SEED_LOG`` (+ ``SHOWDOWN_BATTLE_SEED_BASE``) visible to
  this Python process, which is what tells the run *what* to verify and *where*;
- the **server** half -- the Showdown server actually having been started with
  ``SHOWDOWN_EVAL_SEED_LOG``, which is what WRITES the file.

Both opposite half-configurations have already cost real runs, and both surfaced only after
30-75 battles: a server started without the variable (``SeedLogError: seed log not found`` at the
very end) and a client started without it (``seed-log alignment SKIPPED`` -- the check silently did
not happen). These tests pin the fail-fast contract:

- everything observable from this process is validated BEFORE battle 1 (``check_seed_log_env_pairing``
  + ``preflight_seed_log_path``);
- the server half is not observable before battle 1 -- no client-side check can see another
  process's environment -- so the earliest sound detection point is immediately AFTER battle 1,
  and the gate runners abort there rather than burning the rest of the schedule;
- a skipped alignment check never yields a verified verdict.
"""
from __future__ import annotations

import argparse
import os

import pytest

from showdown_bot.eval.seeding import (
    SEED_BASE_ENV,
    SEED_LOG_ENV,
    SeedLogConfigError,
    check_seed_log_env_pairing,
    preflight_seed_log_path,
)

_SCHEDULE_YAML = """\
version: "1"
rows:
  - format_id: gen9vgc2025regi
    hero_team_path: teams/fixed_team.txt
    opp_policy: max_damage
    opp_team_path: teams/fixed_team.txt
    seed_index: 0
  - format_id: gen9vgc2025regi
    hero_team_path: teams/fixed_team.txt
    opp_policy: max_damage
    opp_team_path: teams/fixed_team.txt
    seed_index: 1
"""


@pytest.fixture
def _sched_path(tmp_path):
    p = tmp_path / "sched.yaml"
    p.write_text(_SCHEDULE_YAML, encoding="utf-8")
    return str(p)


# --- the env pairing: neither half may be configured alone ------------------------------------


def test_env_pairing_names_the_missing_seed_log_half(monkeypatch):
    """Run 2's shape: the server was told where to write, this process was not."""
    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.delenv(SEED_LOG_ENV, raising=False)
    with pytest.raises(SeedLogConfigError, match=SEED_LOG_ENV):
        check_seed_log_env_pairing()


def test_env_pairing_names_the_missing_seed_base_half(monkeypatch, tmp_path):
    monkeypatch.delenv(SEED_BASE_ENV, raising=False)
    monkeypatch.setenv(SEED_LOG_ENV, str(tmp_path / "seeds.jsonl"))
    with pytest.raises(SeedLogConfigError, match=SEED_BASE_ENV):
        check_seed_log_env_pairing()


def test_env_pairing_returns_both_halves_when_fully_configured(monkeypatch, tmp_path):
    seed_log = str(tmp_path / "seeds.jsonl")
    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.setenv(SEED_LOG_ENV, seed_log)
    assert check_seed_log_env_pairing() == ("soak2026", seed_log)


def test_env_pairing_reports_neither_half_when_both_are_absent(monkeypatch):
    """Both absent is a *coherent* configuration (a plain non-Channel-A run), not a half-config:
    the caller decides whether that is allowed, so this returns rather than raises."""
    monkeypatch.delenv(SEED_BASE_ENV, raising=False)
    monkeypatch.delenv(SEED_LOG_ENV, raising=False)
    assert check_seed_log_env_pairing() == ("", "")


# --- the path preflight: the file the server must write has to be usable and fresh -------------


def test_preflight_rejects_a_path_whose_parent_directory_does_not_exist(tmp_path):
    missing = str(tmp_path / "no_such_dir" / "seeds.jsonl")
    with pytest.raises(SeedLogConfigError, match="directory"):
        preflight_seed_log_path(missing)


def test_preflight_rejects_a_stale_non_empty_seed_log(tmp_path):
    stale = tmp_path / "seeds.jsonl"
    stale.write_text('{"battle_index": 0}\n', encoding="utf-8")
    with pytest.raises(SeedLogConfigError, match="already exists and is non-empty"):
        preflight_seed_log_path(str(stale))


def test_preflight_accepts_an_absent_path_and_leaves_it_absent(tmp_path):
    """The probe must not create the target: an existing-but-empty log and an absent one produce
    DIFFERENT diagnostics later ('found 0 records' vs 'seed log not found'), and the second is the
    one that names the server half."""
    target = tmp_path / "seeds.jsonl"
    preflight_seed_log_path(str(target))
    assert not target.exists()


def test_preflight_accepts_an_existing_empty_seed_log(tmp_path):
    target = tmp_path / "seeds.jsonl"
    target.write_text("", encoding="utf-8")
    preflight_seed_log_path(str(target))


def test_preflight_rejects_an_empty_path(tmp_path):
    with pytest.raises(SeedLogConfigError, match=SEED_LOG_ENV):
        preflight_seed_log_path("")


# --- run-schedule: the configuration is validated BEFORE battle 1 ------------------------------


def _args(sched_path, **kw):
    ns = argparse.Namespace(schedule=sched_path, result_out="", decision_trace_out="",
                            agg_trace_out="", allow_unverified_seeds=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _forbid_battles(monkeypatch):
    """Any battle at all is a failure for these tests: the abort must happen before battle 1."""
    import showdown_bot.client.gauntlet as g

    async def _never(**kw):
        raise AssertionError("a battle was started despite a half-configured seed log")

    monkeypatch.setattr(g, "run_local_gauntlet", _never)


def test_run_schedule_aborts_before_battle_one_when_the_seed_log_half_is_missing(
        _sched_path, monkeypatch):
    from showdown_bot import cli

    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.delenv(SEED_LOG_ENV, raising=False)
    _forbid_battles(monkeypatch)
    with pytest.raises(SystemExit, match=SEED_LOG_ENV):
        cli.run_schedule(_args(_sched_path))


def test_run_schedule_aborts_before_battle_one_when_the_seed_base_half_is_missing(
        _sched_path, tmp_path, monkeypatch):
    from showdown_bot import cli

    monkeypatch.delenv(SEED_BASE_ENV, raising=False)
    monkeypatch.setenv(SEED_LOG_ENV, str(tmp_path / "seeds.jsonl"))
    _forbid_battles(monkeypatch)
    with pytest.raises(SystemExit, match=SEED_BASE_ENV):
        cli.run_schedule(_args(_sched_path))


def test_run_schedule_aborts_before_battle_one_when_the_seed_log_path_is_unusable(
        _sched_path, tmp_path, monkeypatch):
    from showdown_bot import cli

    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.setenv(SEED_LOG_ENV, str(tmp_path / "no_such_dir" / "seeds.jsonl"))
    _forbid_battles(monkeypatch)
    with pytest.raises(SystemExit, match="directory"):
        cli.run_schedule(_args(_sched_path))


def test_run_schedule_aborts_before_battle_one_on_a_stale_seed_log(
        _sched_path, tmp_path, monkeypatch):
    from showdown_bot import cli

    stale = tmp_path / "seeds.jsonl"
    stale.write_text('{"battle_index": 0}\n', encoding="utf-8")
    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.setenv(SEED_LOG_ENV, str(stale))
    _forbid_battles(monkeypatch)
    with pytest.raises(SystemExit, match="already exists and is non-empty"):
        cli.run_schedule(_args(_sched_path))


def test_run_schedule_half_configuration_is_skippable_only_by_explicit_opt_in(
        _sched_path, monkeypatch, capsys):
    """The diagnostic/soak path stays usable -- but only when the caller SAYS the run's seeds are
    unverified, and the notice may not read like a passed check."""
    import showdown_bot.client.gauntlet as g
    from showdown_bot import cli

    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.delenv(SEED_LOG_ENV, raising=False)

    async def _fake(**kw):
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    cli.run_schedule(_args(_sched_path, allow_unverified_seeds=True))
    out = capsys.readouterr().out
    assert "NOT VERIFIED" in out
    assert "OK" not in out.split("seed-log")[-1]


def test_run_schedule_without_either_half_is_a_plain_unseeded_run(_sched_path, monkeypatch, capsys):
    """Neither half set = not a Channel-A run at all; it must still run and still say the seeds
    are unverified."""
    import showdown_bot.client.gauntlet as g
    from showdown_bot import cli

    monkeypatch.delenv(SEED_BASE_ENV, raising=False)
    monkeypatch.delenv(SEED_LOG_ENV, raising=False)

    async def _fake(**kw):
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    cli.run_schedule(_args(_sched_path))
    assert "NOT VERIFIED" in capsys.readouterr().out


def test_the_parser_exposes_the_opt_out_and_defaults_it_off():
    from showdown_bot.cli import _build_parser

    args = _build_parser().parse_args(["gauntlet", "--schedule", "s.yaml"])
    assert args.allow_unverified_seeds is False
    args = _build_parser().parse_args(
        ["gauntlet", "--schedule", "s.yaml", "--allow-unverified-seeds"])
    assert args.allow_unverified_seeds is True


# --- the env var names are the ones the server patch reads ------------------------------------


def test_the_env_var_names_are_the_pinned_ones():
    assert (SEED_LOG_ENV, SEED_BASE_ENV) == ("SHOWDOWN_EVAL_SEED_LOG", "SHOWDOWN_BATTLE_SEED_BASE")
    assert os.environ.get("PYTEST_CURRENT_TEST") is not None


# --- the server half, checked after battle 1 rather than after the schedule --------------------


def _sched_rows_count(path):
    from showdown_bot.eval.schedule import load_schedule
    return len(load_schedule(path).rows)


def test_run_schedule_aborts_after_one_battle_when_the_server_never_wrote_the_log(
        _sched_path, tmp_path, monkeypatch):
    """The server was started without SHOWDOWN_EVAL_SEED_LOG: nothing is ever appended. One
    battle is burned, not the schedule, and the abort names the SERVER half."""
    import showdown_bot.client.gauntlet as g
    from showdown_bot import cli

    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.setenv(SEED_LOG_ENV, str(tmp_path / "seeds.jsonl"))
    battles = {"n": 0}

    async def _fake(**kw):
        battles["n"] += 1
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    with pytest.raises(SystemExit, match="SERVER half"):
        cli.run_schedule(_args(_sched_path))
    assert battles["n"] == 1
    assert _sched_rows_count(_sched_path) > 1   # the schedule really had more rows to burn


def test_run_schedule_aborts_cleanly_after_one_battle_on_a_non_fresh_server(
        _sched_path, tmp_path, monkeypatch):
    """A server whose battle counter did not start at 0 writes MORE records than battles played.
    That is a real Channel-A fault and must abort as a clean CLI error, not a raw traceback."""
    import json

    import showdown_bot.client.gauntlet as g
    from showdown_bot import cli
    from showdown_bot.eval.seeding import derive_battle_seed

    seed_log = tmp_path / "seeds.jsonl"
    monkeypatch.setenv(SEED_BASE_ENV, "soak2026")
    monkeypatch.setenv(SEED_LOG_ENV, str(seed_log))
    battles = {"n": 0}

    async def _fake(**kw):
        battles["n"] += 1
        with open(seed_log, "a", encoding="utf-8") as fh:   # two records for one battle
            for i in (0, 1):
                fh.write(json.dumps({"battle_index": i, "seed_base": "soak2026",
                                     "seed": derive_battle_seed("soak2026", i)}) + "\n")
        return g.GauntletStats(games=1, hero_wins=1)

    monkeypatch.setattr(g, "run_local_gauntlet", _fake)
    with pytest.raises(SystemExit, match="expected 1 battles, found 2"):
        cli.run_schedule(_args(_sched_path))
    assert battles["n"] == 1


# --- seed_log_verified must be DERIVED from the verification, not asserted beside it -----------
#
# The flag used to be a literal ``True`` placed after the verification call. That was correct only
# by POSITION: nothing in the code stopped a later early-return or swallowed exception above it
# from turning the field into a silent lie -- the same false-clean family that has already cost a
# ledger slot. ``seed_log_verified_flag`` makes the value come out of what the verification itself
# returned, so a caller that skipped it has nothing to derive a truthy flag from.


def test_the_flag_is_true_only_for_a_complete_record_set():
    from showdown_bot.eval.seeding import seed_log_verified_flag

    records = [{"battle_index": i} for i in range(3)]
    assert seed_log_verified_flag(records, 3) is True


def test_the_flag_is_false_when_the_verification_returned_nothing():
    """What a skipped verification leaves behind: no records at all."""
    from showdown_bot.eval.seeding import seed_log_verified_flag

    assert seed_log_verified_flag(None, 3) is False


def test_the_flag_is_false_for_a_bare_truthy_value_standing_in_for_records():
    """A caller cannot hand it a stand-in claim instead of the verification's own output."""
    from showdown_bot.eval.seeding import seed_log_verified_flag

    assert seed_log_verified_flag(True, 3) is False
    assert seed_log_verified_flag("verified", 3) is False


def test_the_flag_is_false_for_a_record_set_that_does_not_cover_every_battle():
    from showdown_bot.eval.seeding import seed_log_verified_flag

    assert seed_log_verified_flag([{"battle_index": 0}], 3) is False


def test_the_flag_is_false_when_no_battle_was_played():
    """Zero records for zero battles is not a proof of anything; the old literal said True."""
    from showdown_bot.eval.seeding import seed_log_verified_flag

    assert seed_log_verified_flag([], 0) is False

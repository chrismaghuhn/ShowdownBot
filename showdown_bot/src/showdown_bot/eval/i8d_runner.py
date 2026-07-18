"""I8-D live-latency exposure/cap runner and verdict (design §5, plan §5.1–5.4).

The runner drives the FIXED I8-D schedule battle-by-battle, stops on the exposure floor or a cap
(never mid-battle), and — only once the run has stopped — computes the p95 of active foe-Mega
decisions and renders the three-way verdict. It starts a real server and plays real battles when
invoked; this module only BUILDS that harness. ``measured_ms`` is never an input to the stop rule.
"""
from __future__ import annotations

import json
import os

from showdown_bot.eval.decision_profile import (
    DecisionProfileWriter,
    LiveProfileContext,
    is_active_valid_live_row,
    validate_live_profile_dataset,
)
from showdown_bot.eval.gates import load_latency_budget_ms
from showdown_bot.eval.i8d_schedule import (
    I8D_EXPECTED_PANEL_HASH,
    I8D_FORMAT,
    I8D_MAX_BATTLES,
    I8D_SEED_BASE,
    build_i8d_schedule,
)

# --- CLOSED numbers -- not chosen here, referenced. D-1 floor (design §5.4), D-2 caps (§4.1). ---
I8D_MIN_ACTIVE_DECISIONS = 60          # ≥ 60 valid active foe-Mega decisions
I8D_MIN_DISTINCT_BATTLES = 20          # from ≥ 20 distinct battle_id
I8D_MAX_SCORED_DECISIONS = 2000        # D-2 decision cap (I8D_MAX_BATTLES=200 lives in i8d_schedule)

INCONCLUSIVE_MESSAGE = "INCONCLUSIVE — exposure floor not met"


class I8DRunError(RuntimeError):
    """The live gate cannot start or continue safely (e.g. a restart would merge a partial run)."""


def exposure_floor_met(active_valid: int, distinct_battles: int) -> bool:
    """D-1, both minima. A precondition evaluated BEFORE any p95 (§5.2); neither may be lowered
    to rescue a run."""
    return active_valid >= I8D_MIN_ACTIVE_DECISIONS and distinct_battles >= I8D_MIN_DISTINCT_BATTLES


def should_stop(*, battles_played: int, scored_decisions: int, active_valid: int,
                distinct_battles: int) -> tuple[bool, str | None]:
    """Plan §5.1's stop rule, in its order: D-1 floor first (the good stop), then the two caps.
    Evaluated by the runner ONLY after a fully-completed, validated battle. There is deliberately
    no latency parameter -- ``measured_ms`` is never a stop input (not a threshold, not a trend,
    not a "looks fine, stop early")."""
    if exposure_floor_met(active_valid, distinct_battles):
        return True, "exposure_floor_met"
    if battles_played >= I8D_MAX_BATTLES:
        return True, "max_battles"
    if scored_decisions >= I8D_MAX_SCORED_DECISIONS:
        return True, "max_scored_decisions"
    return False, None


def i8d_active_p95_ms(measured_values) -> float:
    """The p95 of active-decision ``measured_ms``, as the SAME nearest-rank statistic the
    per-battle gate applies (``gauntlet._latency_p95``) -- reused, not re-derived, so the verdict
    p95 and the gate p95 can never drift (design §5.4). Returns the raw float ms (no rounding):
    the budget comparison is on ``measured_ms`` directly, and rounding would move the > 1000 ms
    boundary."""
    from showdown_bot.client.gauntlet import _latency_p95
    return _latency_p95(list(measured_values))


def i8d_verdict(*, active_valid: int, distinct_battles: int, active_measured_ms,
                budget_ms: int) -> dict:
    """The §5.2 verdict. The floor is a precondition: the p95 is computed and gate-compared ONLY
    when the floor is met. A run that misses the floor is INCONCLUSIVE and reports no gate p95
    (``p95_ms=None``); its exposure p95 may still be surfaced elsewhere, explicitly not a gate
    value."""
    met = exposure_floor_met(active_valid, distinct_battles)
    base = {
        "exposure_floor_met": met,
        "min_active_decisions": I8D_MIN_ACTIVE_DECISIONS,
        "min_distinct_battles": I8D_MIN_DISTINCT_BATTLES,
        "budget_ms": budget_ms,
    }
    if not met:
        return {**base, "verdict": INCONCLUSIVE_MESSAGE, "p95_ms": None, "p95_is_gate_value": False}
    p95 = i8d_active_p95_ms(active_measured_ms)
    return {**base, "verdict": "PASS" if p95 <= budget_ms else "FAIL",
            "p95_ms": p95, "p95_is_gate_value": True}


def _active_measured_ms(profile_out: str) -> list[float]:
    """The ``measured_ms`` of every ACTIVE valid row in the frozen dataset (the verdict
    population). Active rows are ``outcome == "ok"``, so each carries a finite ``measured_ms``."""
    out: list[float] = []
    with open(profile_out, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if is_active_valid_live_row(row):
                out.append(row["measured_ms"])
    return out


def _write_json_atomic(path: str, obj: dict) -> None:
    """Stage the verdict via a temp file + ``os.replace`` so a reader never sees a partial
    verdict. LF-stable (``newline=""`` + explicit ``"\n"``), sorted keys for byte-determinism."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(obj, sort_keys=True, indent=2) + "\n")
    os.replace(tmp, path)


def _read_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def _adopt_battle_atomic(dataset_path: str, battle_path: str) -> None:
    """Merge a proven-complete battle's staged rows into the accumulating dataset **atomically**
    (re-review blocker 1): write the new full dataset (existing + this battle) to a temp file, then
    ``os.replace`` it into place. A process/file error mid-write leaves either the pre-battle or the
    post-battle dataset -- never a half battle. LF-stable. Called only after the battle returned
    exactly one completed game AND its staged rows validated."""
    merged = _read_lines(dataset_path) + _read_lines(battle_path)
    tmp = f"{dataset_path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        for line in merged:
            fh.write(line + "\n")
    os.replace(tmp, dataset_path)


def _verify_seed_alignment(seed_log_path: str, seed_base: str, schedule, battles_played: int) -> None:
    """Prove the server actually played the approved seeds for the battles that ran (finding 2).

    ``verify_seed_log`` requires EXACTLY ``battles_played`` Channel-A records, contiguous
    ``battle_index`` 0..N-1, ``seed_base == seed_base``, and ``seed == derive_battle_seed(...)``;
    a retried/extra battle or a Python↔server derivation mismatch fails it. Then the played rows'
    ``seed_index`` is cross-checked against the logged ``battle_index``."""
    from showdown_bot.eval.seeding import SeedLogError, verify_seed_log

    try:
        records = verify_seed_log(seed_log_path, seed_base, battles_played)
    except SeedLogError as exc:
        raise I8DRunError(f"seed-log verification failed: {exc}") from exc
    for row, rec in zip(schedule.rows, records):
        if row.seed_index != rec["battle_index"]:
            raise I8DRunError(
                f"seed-log/schedule misalignment: row seed_index {row.seed_index} != logged "
                f"battle_index {rec['battle_index']}"
            )


def resolve_i8d_provenance(*, hero_agent: str = "heuristic", format_id: str = I8D_FORMAT) -> dict:
    """Derive the gate's provenance from the REAL environment and repo state, fail-closed
    (code-review finding 5): none of ``git_sha`` / ``config_hash`` / ``calc_backend`` may be a
    caller-supplied label.

    - ``git_sha``: the current commit; refused if git is unavailable OR the tree is dirty (a
      verdict's ``git_sha`` must identify exactly the code that produced it).
    - ``config_hash``: recomputed from the effective config manifest -- the SAME assembly
      ``cli.run_schedule`` uses, so a gate row's ``config_hash`` matches a result row's.
    - ``calc_backend``: normalised from ``SHOWDOWN_CALC_BACKEND`` exactly as ``make_calc_backend``
      selects it, fail-closed on unknown values.
    """
    from showdown_bot.eval.config_env import behavior_env, effective_config_manifest
    from showdown_bot.eval.result_jsonl import make_config_hash
    from showdown_bot.learning.provenance import git_sha_and_dirty

    git_sha, dirty = git_sha_and_dirty()
    if not git_sha or git_sha == "unknown":
        raise I8DRunError(
            "cannot resolve a git sha for the I8-D gate (not a git checkout?); the verdict's "
            "provenance would be unverifiable"
        )
    if dirty:
        raise I8DRunError(
            "the working tree is dirty; commit or stash before an I8-D gate run so the verdict's "
            "git_sha identifies exactly the code that produced it"
        )
    manifest = effective_config_manifest(
        agent=hero_agent, format_id=format_id, env=behavior_env(),
        model_hash=None, model_manifest_hash=None,
    )
    config_hash = make_config_hash(manifest)
    raw_backend = os.environ.get("SHOWDOWN_CALC_BACKEND", "oneshot")
    if raw_backend in ("", "oneshot"):
        calc_backend = "oneshot"
    elif raw_backend == "persistent":
        calc_backend = "persistent"
    else:
        raise I8DRunError(
            f"unknown SHOWDOWN_CALC_BACKEND={raw_backend!r} (expected 'oneshot' or 'persistent')"
        )
    return {"git_sha": git_sha, "config_hash": config_hash,
            "calc_backend": calc_backend, "hero_agent": hero_agent}


def build_i8d_live_schedule(panel_path: str, *, n_battles: int = I8D_MAX_BATTLES,
                            teams_root: str = "."):
    """Bind the fixed I8-D schedule (all seeds materialised, frozen in ``schedule_hash``) BEFORE
    the first battle. Thin wrapper over ``load_panel`` + ``build_i8d_schedule``; held-out teams
    are excluded and ``seed_index=i`` is bound immutably to row ``i`` by ``build_i8d_schedule``."""
    from showdown_bot.eval.panel import load_panel
    panel = load_panel(panel_path, teams_root=teams_root)
    return build_i8d_schedule(panel, n_battles=n_battles, teams_root=teams_root)


def run_i8d_live_gate(*, schedule, out_dir: str, seed_log_path: str,
                      config_hash: str, git_sha: str, calc_backend: str = "oneshot",
                      hero_agent: str = "heuristic", expected_battles: int = I8D_MAX_BATTLES,
                      expected_panel_hash: str = I8D_EXPECTED_PANEL_HASH) -> dict:
    """Drive the schedule with whole-battle stop and render the verdict, verifying every execution
    boundary up front rather than trusting labels (code-review findings 1-3 + re-review blocker 1).

    - **Schedule re-lock (finding 3):** ``verify_i8d_schedule`` re-derives the full structure and
      recomputes the hash before the first battle -- an arbitrary/truncated schedule is refused.
    - **Seed proof (finding 2):** the server reads ``SHOWDOWN_BATTLE_SEED_BASE`` at startup
      (Channel A); this asserts it is the approved ``I8D_SEED_BASE`` (the namespace ``schedule_hash``
      does not cover) and requires the server's ``seed_log_path``, then after the run proves the
      logged seeds are exactly ``derive_battle_seed(base, i)`` for the battles that ran.
    - **Atomic run (finding 1 + re-review blocker 1):** the WHOLE run happens in a run-staging
      directory ``{out_dir}.staging``; each battle stages in isolation and is adopted into the
      accumulating dataset ONLY after ``run_local_gauntlet`` reports exactly one completed game and
      the staged rows validate -- and that adoption is a temp-file + ``os.replace`` (never a
      partial battle in the dataset). ``out_dir`` itself appears only via a single atomic
      ``os.replace(staging_dir, out_dir)`` AFTER seed-log, dataset and verdict validation, so a
      crash at any point leaves the un-published staging dir and never half a battle in the final
      evidence. A timeout (``games == 0``) discards the staged battle and fails closed.

    Restart-from-seed-0-no-merge: refuses an existing ``out_dir`` or staging dir. The p95 is
    computed only after the run has stopped; the scored cap is a THRESHOLD the last battle may
    overshoot by exactly its own rows (reported in ``scored_overshoot``, never truncated).
    """
    import asyncio

    from showdown_bot.client.gauntlet import run_local_gauntlet
    from showdown_bot.eval.i8d_schedule import verify_i8d_schedule
    from showdown_bot.eval.result_jsonl import make_battle_id
    from showdown_bot.eval.seeding import derive_battle_seed

    # (finding 3) never trust the caller's schedule -- re-derive structure + recompute the hash.
    verify_i8d_schedule(schedule, expected_battles=expected_battles)

    # (re-review blocker 2) the panel + team CONTENTS are bound to the verdict identity: panel_hash
    # is content-derived, so a swapped panel or changed team content is refused here. (The CLI path
    # additionally re-reads the team files before battle 1 via verify_i8d_panel_and_teams; this is
    # the runner's stored-value guard so no schedule with the wrong content-identity is ever run.)
    if schedule.panel_hash != expected_panel_hash:
        raise I8DRunError(
            f"schedule panel_hash {schedule.panel_hash!r} != expected champions panel "
            f"{expected_panel_hash!r}: the panel/team contents are not the approved ones"
        )

    # (finding 2) the seed NAMESPACE is bound by explicit verification, not by schedule_hash.
    seed_base = os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "")
    if seed_base != I8D_SEED_BASE:
        raise I8DRunError(
            f"SHOWDOWN_BATTLE_SEED_BASE must be {I8D_SEED_BASE!r} for I8-D (Channel A), got "
            f"{seed_base!r}: the server must be started with the approved seed namespace"
        )
    if not seed_log_path:
        raise I8DRunError(
            "I8-D requires the server's seed log (SHOWDOWN_EVAL_SEED_LOG) so the played seeds can "
            "be proven; without it the run's seeds are only labelled, not verified"
        )

    # (blocker 1) all work happens in a run-staging directory; out_dir appears only via one atomic
    # rename after everything validates. A leftover staging dir is a crashed run -- fail closed.
    staging_dir = f"{out_dir}.staging"
    for label, p in (("output", out_dir), ("staging", staging_dir)):
        if os.path.exists(p):
            raise I8DRunError(
                f"{label} directory {p} already exists; an I8-D restart runs from seed 0 into a "
                f"fresh directory and never merges a partial run"
            )
    os.makedirs(staging_dir)
    staging_profile = os.path.join(staging_dir, "profile.jsonl")
    staging_battle = os.path.join(staging_dir, "battle.jsonl")
    open(staging_profile, "a", encoding="utf-8", newline="").close()   # the empty dataset exists
    budget_ms = load_latency_budget_ms()   # the pinned 1000 ms from gates.yaml, not a local copy

    battles_played = 0
    scored_decisions = active_valid = distinct_battles = 0
    stop_reason: str | None = None
    for row in schedule.rows:   # verified contiguous seed_index from 0 (bound up front)
        seed = derive_battle_seed(seed_base, row.seed_index)
        battle_id = make_battle_id(schedule.schedule_hash, row.seed_index, seed)
        context = LiveProfileContext(
            battle_id=battle_id, config_id=hero_agent, config_hash=config_hash,
            schedule_hash=schedule.schedule_hash, format_id=row.format_id,
            git_sha=git_sha, calc_backend=calc_backend)
        # (finding 1) stage this battle in isolation; a distinct writer per battle so partial rows
        # never touch the accumulating dataset before the battle is proven complete.
        if os.path.exists(staging_battle):
            os.remove(staging_battle)
        stage_writer = DecisionProfileWriter(staging_battle, manifest=None)
        stats = asyncio.run(run_local_gauntlet(
            games=1, hero_agent=hero_agent, villain_agent=row.opp_policy,
            format_id=row.format_id, team_path=row.hero_team_path, opp_team_path=row.opp_team_path,
            decision_profile_writer=stage_writer, decision_profile_context=context))
        if stats.games != 1:
            # A timeout returns normally with games == 0 and partial rows staged. Discard them and
            # fail closed: a run restarted for an infrastructure fault restarts from seed 0 (§5.1),
            # never adopting a half-played battle's exposure or scored decisions.
            if os.path.exists(staging_battle):
                os.remove(staging_battle)
            raise I8DRunError(
                f"battle at seed_index {row.seed_index} did not complete exactly one game "
                f"(games={stats.games}); its partial rows are discarded -- restart from seed 0"
            )
        # §5.4.4: validate the battle's staged artifacts, adopt them ATOMICALLY into the dataset,
        # THEN recount and evaluate the stop rule. (No staged file => 0 scored decisions.)
        if os.path.exists(staging_battle):
            validate_live_profile_dataset(staging_battle)
            _adopt_battle_atomic(staging_profile, staging_battle)
            os.remove(staging_battle)
        battles_played += 1
        counts = validate_live_profile_dataset(staging_profile)
        scored_decisions = counts["rows"]
        active_valid = counts["active_valid_rows"]
        distinct_battles = counts["distinct_active_battle_ids"]
        stop, stop_reason = should_stop(
            battles_played=battles_played, scored_decisions=scored_decisions,
            active_valid=active_valid, distinct_battles=distinct_battles)
        if stop:
            break
    else:
        stop_reason = "schedule_exhausted"

    # (finding 2) prove the server played the approved seeds for the battles that ran, BEFORE any
    # verdict is written: a run whose seeds cannot be proven yields no verdict (and no out_dir).
    _verify_seed_alignment(seed_log_path, seed_base, schedule, battles_played)
    validate_live_profile_dataset(staging_profile)   # final dataset validation before publishing

    verdict = i8d_verdict(active_valid=active_valid, distinct_battles=distinct_battles,
                          active_measured_ms=_active_measured_ms(staging_profile), budget_ms=budget_ms)
    report = {
        "schedule_hash": schedule.schedule_hash,
        # (blocker 2) the content-bound panel + team identity, recorded in the verdict so two runs
        # over different team CONTENTS can never read as the same verdict identity.
        "panel_hash": schedule.panel_hash,
        "hero_team_hash": schedule.rows[0].hero_team_hash if schedule.rows else None,
        "opp_team_hashes": sorted({r.opp_team_hash for r in schedule.rows
                                   if r.opp_team_hash is not None}),
        "seed_base": seed_base,
        "seed_log_verified": True,
        "battles_played": battles_played,
        "scored_decisions": scored_decisions,
        "max_scored_decisions": I8D_MAX_SCORED_DECISIONS,
        "scored_overshoot": max(0, scored_decisions - I8D_MAX_SCORED_DECISIONS),
        "active_valid_decisions": active_valid,
        "distinct_active_battles": distinct_battles,
        "stop_reason": stop_reason,
        **verdict,
    }
    _write_json_atomic(os.path.join(staging_dir, "verdict.json"), report)
    # (blocker 1) publish the COMPLETE output directory atomically -- profile + verdict together --
    # in one rename, from a fully-validated staging dir into the not-yet-existing out_dir.
    os.replace(staging_dir, out_dir)
    return report

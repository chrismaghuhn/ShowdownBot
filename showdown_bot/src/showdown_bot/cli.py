from __future__ import annotations

import argparse
import asyncio
import logging

from pathlib import Path

from showdown_bot.client.fixture_runner import replay_request_fixture
from showdown_bot.client.runner import run_challenge, run_ladder_search, run_smoke_battle
from showdown_bot.config import Settings


def run_validate_log(args) -> None:
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.validate import load_known_sets, validate_log

    if not args.log:
        raise SystemExit("validate-log requires --log PATH")

    raw = Path(args.log).read_text(encoding="utf-8")
    cfg = load_format_config(args.format_id)
    known = load_known_sets(Path(args.sets)) if args.sets else {}

    report = validate_log(
        raw,
        calc=CalcClient(),
        format_config=cfg,
        known_sets=known,
    )
    print(f"validate-log {args.log} (side={args.side})")
    print(report.summary())
    for rec in report.records:
        status = "OK " if rec.matched else "XX "
        inst = rec.instance
        print(
            f"  {status}[{rec.mode}] {inst.attacker_species} {inst.move} -> "
            f"{inst.defender_species}: observed {rec.observed_frac * 100:.1f}% "
            f"vs calc [{rec.calc_min_frac * 100:.1f}, {rec.calc_max_frac * 100:.1f}]%"
        )


def _file_content_hash(path) -> str | None:
    """sha1[:16] of a file's bytes, or None if it can't be read (T3f config_hash provenance)."""
    import hashlib

    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:  # noqa: BLE001 - provenance is best-effort; missing file -> None
        return None


def run_schedule(args) -> None:
    """Non-mirror schedule mode (T1c): run each row as one battle in seed_index order.

    Channel A: when SHOWDOWN_BATTLE_SEED_BASE is set the server derives seed_i by battle
    creation order, so this MUST run against a **fresh** server (counter from 0). Rows are
    executed sorted by seed_index (the loader guarantees contiguous-from-0). No battle-level
    retry: a retry/extra battle desyncs the counter and the final seed-log alignment fails.
    """
    import os

    from showdown_bot.client.gauntlet import build_schedule_export_runtime, run_local_gauntlet
    from showdown_bot.eval.schedule import load_schedule, verify_schedule_alignment

    sched = load_schedule(args.schedule)
    base = os.environ.get("SHOWDOWN_BATTLE_SEED_BASE")
    print(f"schedule {args.schedule}: {len(sched.rows)} rows, schedule_hash={sched.schedule_hash}")
    if base:
        print("  seed mode: per-battle (SHOWDOWN_BATTLE_SEED_BASE) — REQUIRES a fresh server (Channel A)")

    # 2b-2.5a fix: dataset export is RUN-scoped, not battle-scoped. Each row below plays as
    # its own run_local_gauntlet(games=1) call; building a fresh export runtime per call (the
    # old behavior) meant every battle's flush overwrote the file, so only the LAST battle in
    # the whole schedule ever survived to disk. Build ONE runtime here (representative row 0 —
    # datagen schedules are one hero team/format per file) and thread the SAME instance through
    # every row so their rows accumulate into one file; close it once after the loop.
    export_runtime = None
    if os.environ.get("SHOWDOWN_DATASET_EXPORT"):
        export_runtime = build_schedule_export_runtime(sched.rows[0].format_id, sched.rows[0].hero_team_path)
        if export_runtime is not None:
            print(f"  dataset export -> {os.environ['SHOWDOWN_DATASET_EXPORT']} "
                  f"(run-scoped across all {len(sched.rows)} rows)")

    # T2 per-battle result JSONL (Fix 3: --result-out must be missing or empty at start).
    result_out = getattr(args, "result_out", "")
    writer = None
    written = []
    if result_out:
        import sys
        from datetime import datetime, timezone

        from showdown_bot.eval.config_env import behavior_env, build_config_manifest
        from showdown_bot.eval.result_jsonl import BattleResultWriter, make_battle_id, make_config_hash
        from showdown_bot.eval.run_manifest import build_run_manifest, make_run_id, write_run_manifest
        from showdown_bot.eval.seeding import derive_battle_seed
        from showdown_bot.learning.provenance import git_sha_and_dirty

        if not base:
            raise SystemExit("--result-out requires SHOWDOWN_BATTLE_SEED_BASE (the 'seed' field must be meaningful)")
        if os.path.exists(result_out) and os.path.getsize(result_out) > 0:
            raise SystemExit(f"--result-out {result_out} already has rows; must be non-existing or empty (T2-CC-2)")
        writer = BattleResultWriter(result_out)
        git_sha, dirty = git_sha_and_dirty()  # T3e P4: row provenance includes the dirty flag
        print(f"  result JSONL -> {result_out}")

        # T3f: effective config_hash over the behavior manifest. Snapshot the behavior env once
        # (env is stable across a run) + model hashes when the reranker is on; priors/spreads
        # hashes depend on the format, so cache config_hash per (agent, format_id).
        _behavior_env = behavior_env()
        _reranker_on = bool(_behavior_env.get("SHOWDOWN_RERANKER_SHADOW"))
        _model_hash = _file_content_hash(os.environ.get("SHOWDOWN_RERANKER_MODEL_PATH")) if _reranker_on else None
        _model_manifest_hash = _file_content_hash(os.environ.get("SHOWDOWN_RERANKER_MANIFEST_PATH")) if _reranker_on else None
        _cfg_hash_cache: dict = {}

        def _config_hash_for(agent, format_id):
            key = (agent, format_id)
            if key not in _cfg_hash_cache:
                priors_hash = spreads_hash = None
                try:
                    from showdown_bot.engine.format_config import load_format_config

                    cfg = load_format_config(format_id)
                    priors_hash = _file_content_hash(cfg.meta_path("protect_priors"))
                    spreads_hash = _file_content_hash(cfg.meta_path("default_spreads"))
                except Exception:  # noqa: BLE001 - provenance best-effort; missing config -> None
                    pass
                manifest = build_config_manifest(
                    agent=agent, format_id=format_id,
                    priors_hash=priors_hash, spreads_hash=spreads_hash, env=_behavior_env,
                    model_hash=_model_hash, model_manifest_hash=_model_manifest_hash,
                )
                _cfg_hash_cache[key] = make_config_hash(manifest)
            return _cfg_hash_cache[key]

        # T3f Task 3: one run_id for the whole run + a self-describing manifest sidecar.
        # start_ts is captured ONCE here (so run_id is constant across rows, new per run);
        # the run-level config_hash uses the schedule's representative (agent, format).
        _start_ts = datetime.now(timezone.utc).isoformat()
        _run_config_hash = _config_hash_for("heuristic", sched.rows[0].format_id)
        run_id = make_run_id(base, sched.schedule_hash, _run_config_hash, _start_ts)
        manifest = build_run_manifest(
            run_id=run_id, seed_base=base, schedule_hash=sched.schedule_hash,
            panel_hash=sched.panel_hash, config_hash=_run_config_hash, start_ts=_start_ts,
            pythonhashseed=os.environ.get("PYTHONHASHSEED"), cli_invocation=list(sys.argv),
            git_sha=git_sha, dirty=dirty,
        )
        manifest_out = write_run_manifest(result_out, manifest)
        print(f"  run manifest -> {manifest_out} (run_id={run_id})")

    totals = {"games": 0, "hero_wins": 0, "villain_wins": 0, "ties": 0, "invalid": 0, "crashes": 0}
    try:
        for row in sched.rows:  # loader-sorted by seed_index, contiguous from 0
            on_br = None
            if writer is not None:
                def on_br(record, _row=row):  # noqa: B023 - _row default-arg captures this iteration
                    seed = derive_battle_seed(base, _row.seed_index)
                    config_id, format_id = "heuristic", _row.format_id  # bot version vs format (Fix 1)
                    writer.write({
                        "battle_id": make_battle_id(sched.schedule_hash, _row.seed_index, seed),
                        "run_id": run_id,  # T3f Task 3: constant across the run; matches manifest.run_id
                        "config_id": config_id, "format_id": format_id,
                        "config_hash": _config_hash_for(config_id, format_id),
                        "schedule_hash": sched.schedule_hash, "seed_index": _row.seed_index,
                        "opp_policy": _row.opp_policy, "hero_team_path": _row.hero_team_path,
                        "opp_team_path": _row.opp_team_path, "seed": seed,
                        # T3f Task 2: raw base string (SHOWDOWN_BATTLE_SEED_BASE), NOT re-derived
                        # from seed. Lets T5 pair on (schedule_hash, seed_base, seed_index).
                        "seed_base": base, "git_sha": git_sha,
                        "dirty": dirty,  # T3e P4 provenance
                        # Provenance from the schedule row (legacy schedules -> null).
                        "hero_team_hash": _row.hero_team_hash, "opp_team_hash": _row.opp_team_hash,
                        "panel_split": _row.panel_split,  # T3f Task 4: "dev"/"heldout" or null
                        "timeouts": None, "panel_hash": sched.panel_hash, **record,
                    })
                    written.append(_row.seed_index)

            stats = asyncio.run(
                run_local_gauntlet(
                    games=1,
                    hero_agent="heuristic",
                    villain_agent=row.opp_policy,
                    format_id=row.format_id,
                    team_path=row.hero_team_path,
                    opp_team_path=row.opp_team_path,
                    on_battle_result=on_br,
                    export_runtime=export_runtime,  # 2b-2.5a: SAME runtime for every row
                )
            )
            totals["games"] += stats.games
            totals["hero_wins"] += stats.hero_wins
            totals["villain_wins"] += stats.villain_wins
            totals["ties"] += stats.ties
            totals["invalid"] += stats.invalid_choices
            totals["crashes"] += stats.crashes
            print(
                f"  seed_index={row.seed_index}: {row.hero_team_path} vs {row.opp_team_path} "
                f"[{row.opp_policy}] -> games={stats.games} hero_wins={stats.hero_wins} "
                f"invalid={stats.invalid_choices} crashes={stats.crashes}"
            )
    finally:
        # 2b-2.5a: close the run-scoped runtime (rollout CalcClient teardown, if any) exactly
        # once, whether the loop finished cleanly or raised mid-schedule. Rows are already on
        # disk via each battle's own flush() (see _run_client) -- close() is teardown-only.
        if export_runtime is not None:
            export_runtime.close()
    print(f"schedule totals: {totals}")

    if writer is not None:
        if len(written) != len(sched.rows):  # T2-CC-4: one row per schedule row, fail fast
            raise SystemExit(f"T2: wrote {len(written)} rows but schedule has {len(sched.rows)} "
                             f"(retry/extra or missing battle)")
        print(f"result JSONL: {len(written)} rows written (one per schedule row)")

    seed_log = os.environ.get("SHOWDOWN_EVAL_SEED_LOG")
    if seed_log and base:
        verify_schedule_alignment(sched, seed_log, base)  # raises on retry/extra/misalign
        print(f"seed-log alignment OK: {len(sched.rows)} battles, seed_i == derive_battle_seed(base, seed_index)")
    else:
        print("seed-log alignment SKIPPED (SHOWDOWN_BATTLE_SEED_BASE / SHOWDOWN_EVAL_SEED_LOG not both set)")


def run_eval_report(args) -> None:
    """T5 Task 5: `eval-report` CLI — turns one or two eval runs into a deterministic
    md+json report (spec §1.4). Manifest sidecars are found via the existing
    `<run>.manifest.json` convention (``RunBundle.load`` does this internally).

    Exit code signals SAFETY, not strength (spec §1.4): 0 for SAFETY-PASS/GO/NO-GO/
    UNDERPOWERED, 1 (SystemExit) iff the verdict is a SAFETY-FAIL (single- or paired-mode).
    A load-time ``ReportInputError`` (unreadable/tampered/missing-sidecar input) also becomes
    a clean SystemExit(1) rather than an uncaught traceback.
    """
    import json as _json

    from showdown_bot.eval.report import (
        VERDICT_SAFETY_FAIL,
        VERDICT_SINGLE_FAIL,
        ReportInputError,
        RunBundle,
        generate_report,
    )

    if not args.run_a or not args.seedlog_a:
        raise SystemExit("eval-report requires --run-a and --seedlog-a")
    if not args.schedule:
        raise SystemExit("eval-report requires --schedule")
    if not args.panel:
        raise SystemExit("eval-report requires --panel")
    if not args.out:
        raise SystemExit("eval-report requires --out")
    if bool(args.run_b) != bool(args.seedlog_b):
        raise SystemExit(
            "eval-report: --run-b and --seedlog-b must be given together "
            "(paired mode needs both, single-run mode needs neither)"
        )

    try:
        bundle_a = RunBundle.load(
            args.run_a, args.seedlog_a, args.schedule, args.panel, teams_root=args.teams_root,
        )
        bundle_b = None
        if args.run_b:
            bundle_b = RunBundle.load(
                args.run_b, args.seedlog_b, args.schedule, args.panel, teams_root=args.teams_root,
            )
    except ReportInputError as exc:
        # Load-time input audit failure (unreadable/tampered/missing-sidecar input): a bare
        # SystemExit(1) so the numeric exit code matches the SAFETY-FAIL contract below exactly
        # (not just "truthy" via the string-to-1 coercion Python applies at process shutdown).
        print(f"eval-report: input audit failed: {exc}")
        raise SystemExit(1) from exc

    md, obj = generate_report(bundle_a, bundle_b, mode=args.mode)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "report.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    with open(out_dir / "report.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_json.dumps(obj, sort_keys=True, indent=2) + "\n")

    print(f"eval-report: wrote {out_dir / 'report.md'} and {out_dir / 'report.json'}")
    print(f"verdict: {obj['verdict']}")

    # Exit code signals SAFETY, not strength (spec §1.4): NO-GO/UNDERPOWERED still exit 0.
    if obj["verdict"] in (VERDICT_SAFETY_FAIL, VERDICT_SINGLE_FAIL):
        raise SystemExit(1)


def run_gauntlet(args) -> None:
    import os

    if getattr(args, "schedule", ""):
        run_schedule(args)
        return

    from showdown_bot.client.gauntlet import run_local_gauntlet

    # The gauntlet uses local guest auth, so it does not need SHOWDOWN_USERNAME;
    # only the team path matters here.
    team_path = os.environ.get("SHOWDOWN_TEAM_PATH", "teams/fixed_team.txt")
    stats = asyncio.run(
        run_local_gauntlet(
            games=args.games,
            hero_agent="heuristic",
            villain_agent=args.villain,
            format_id=args.format_id,
            team_path=team_path,
        )
    )
    p95 = stats.latency_p95()
    print(f"gauntlet vs {args.villain}: {stats.hero_wins}/{stats.games} wins "
          f"({stats.winrate * 100:.1f}%), ties={stats.ties}")
    print(f"  invalid_choices={stats.invalid_choices} crashes={stats.crashes} "
          f"latency_p95={p95 * 1000:.0f}ms")

    if args.strict:
        threshold = 0.60 if args.villain == "random" else 0.55
        failures = []
        if stats.games < 50:
            failures.append(f"games {stats.games} < 50")
        if stats.winrate < threshold:
            failures.append(f"winrate {stats.winrate:.2f} < {threshold}")
        if stats.invalid_choices > 0:
            failures.append(f"invalid_choices={stats.invalid_choices}")
        if stats.crashes > 0:
            failures.append(f"crashes={stats.crashes}")
        if p95 >= 1.5:
            failures.append(f"latency_p95 {p95:.2f}s >= 1.5s")
        if failures:
            raise SystemExit("gauntlet FAILED: " + "; ".join(failures))
        print("gauntlet PASSED strict thresholds")


def main() -> None:
    parser = argparse.ArgumentParser(description="VGC Showdown Bot")
    parser.add_argument(
        "command",
        choices=["ladder", "challenge", "smoke", "replay-fixture", "validate-log", "gauntlet",
                 "eval-report"],
        help="ladder/challenge/smoke/replay-fixture/validate-log/gauntlet/eval-report",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--max-battles",
        type=int,
        default=1,
        help="Stop after N completed battles",
    )
    parser.add_argument(
        "--opponent",
        type=str,
        default="",
        help="Opponent username for challenge command",
    )
    parser.add_argument(
        "--fixture",
        default="tests/fixtures/request_doubles_moves.json",
        help="Path to request JSON fixture (replay-fixture)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed for action selection (replay-fixture)",
    )
    parser.add_argument(
        "--log",
        default="",
        help="Path to a battle log file (validate-log)",
    )
    parser.add_argument(
        "--side",
        default="p1",
        help="Our side for validation context (validate-log)",
    )
    parser.add_argument(
        "--sets",
        default="",
        help="Path to known-sets JSON for strict validation (validate-log)",
    )
    parser.add_argument(
        "--format",
        dest="format_id",
        default="gen9vgc2025regi",
        help="Format id for config/spread selection (validate-log/gauntlet)",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=10,
        help="Number of games to play (gauntlet)",
    )
    from showdown_bot.eval.policies import POLICIES as _POLICIES

    parser.add_argument(
        "--villain",
        default="max_damage",
        choices=sorted(n for n, p in _POLICIES.items() if p.implemented),
        help="Opponent agent (gauntlet); sourced from the eval policy registry",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce Phase 2 exit thresholds and exit non-zero on failure (gauntlet)",
    )
    parser.add_argument(
        "--schedule",
        default="",
        help="Path to a non-mirror eval schedule YAML. For gauntlet: runs each row as one "
        "battle in seed_index order; requires a fresh server when using "
        "SHOWDOWN_BATTLE_SEED_BASE (Channel A). For eval-report (required): re-verifies seed-"
        "log alignment against this same schedule.",
    )
    parser.add_argument(
        "--result-out",
        dest="result_out",
        default="",
        help="Path for the T2 per-battle result JSONL (gauntlet --schedule). Must be "
        "non-existing or empty; requires SHOWDOWN_BATTLE_SEED_BASE.",
    )
    parser.add_argument(
        "--run-a",
        dest="run_a",
        default="",
        help="Path to run A's per-battle result JSONL (eval-report, required). The run "
        "manifest sidecar is found via the '<run>.manifest.json' convention.",
    )
    parser.add_argument(
        "--seedlog-a",
        dest="seedlog_a",
        default="",
        help="Path to run A's seed log (eval-report, required), for re-verifying schedule "
        "alignment.",
    )
    parser.add_argument(
        "--run-b",
        dest="run_b",
        default="",
        help="Path to run B's (baseline) per-battle result JSONL (eval-report, optional). "
        "Give together with --seedlog-b to switch to paired McNemar mode; omit both for "
        "single-run safety mode.",
    )
    parser.add_argument(
        "--seedlog-b",
        dest="seedlog_b",
        default="",
        help="Path to run B's seed log (eval-report). Required iff --run-b is given.",
    )
    parser.add_argument(
        "--panel",
        default="",
        help="Path to the eval panel YAML (eval-report, required); team_path entries inside "
        "it resolve against --teams-root.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output directory for report.md + report.json (eval-report, required); "
        "created if missing.",
    )
    parser.add_argument(
        "--mode",
        default="gate",
        choices=["gate", "dev"],
        help="eval-report safety-gate strictness (default 'gate'): 'gate' fails the run on "
        "latency-budget or dirty-worktree violations; 'dev' downgrades only those two gates "
        "to WARN. Every other safety gate is a hard FAIL in both modes.",
    )
    parser.add_argument(
        "--teams-root",
        dest="teams_root",
        default=".",
        help="Directory panel team_path entries resolve against (eval-report). Team paths in "
        "config/eval/panels/*.yaml are written relative to the gauntlet working directory, so "
        "this defaults to '.' -- run eval-report from inside showdown_bot/ (as gauntlet runs "
        "already are), or pass the absolute path to showdown_bot/ explicitly.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.command == "replay-fixture":
        print(replay_request_fixture(args.fixture, seed=args.seed))
        return

    if args.command == "validate-log":
        run_validate_log(args)
        return

    if args.command == "gauntlet":
        run_gauntlet(args)
        return

    if args.command == "eval-report":
        run_eval_report(args)
        return

    settings = Settings.from_env()
    if args.command == "ladder":
        asyncio.run(run_ladder_search(settings, max_battles=args.max_battles))
    elif args.command == "challenge":
        if not args.opponent:
            parser.error("challenge requires --opponent USERNAME")
        asyncio.run(run_challenge(settings, args.opponent, max_battles=args.max_battles))
    elif args.command == "smoke":
        asyncio.run(run_smoke_battle(settings))


if __name__ == "__main__":
    main()

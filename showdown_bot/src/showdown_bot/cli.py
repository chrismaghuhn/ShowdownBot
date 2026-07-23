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
    # 2b-4 Task 3: hero-agent selector for schedule runs (Kaggle kernel wiring for the
    # heuristic_reranker override agent -- see tools/kaggle/kernel_payload.py's
    # run_gated_override_determinism/_strength). Absent -> "heuristic", byte-identical to
    # every prior run_schedule behavior. This is the ONLY way to pick a non-default hero
    # agent for a schedule run: ScheduleRow has no per-row hero-agent field (rows only vary
    # opp_policy/opp_team_path/seed_index -- the opponent side; see eval/schedule.py).
    hero_agent = os.environ.get("SHOWDOWN_HERO_AGENT", "heuristic")
    print(f"schedule {args.schedule}: {len(sched.rows)} rows, schedule_hash={sched.schedule_hash}")
    if hero_agent != "heuristic":
        print(f"  hero agent: {hero_agent} (SHOWDOWN_HERO_AGENT)")
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
        export_runtime = build_schedule_export_runtime(
            sched.rows[0].format_id, sched.rows[0].hero_team_path, sched.rows[0].opp_team_path,
        )
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

        from showdown_bot.eval.config_env import behavior_env, effective_config_manifest, file_content_hash
        from showdown_bot.eval.result_jsonl import BattleResultWriter, make_battle_id, make_config_hash
        from showdown_bot.eval.run_manifest import (
            build_run_manifest,
            collect_environment,
            make_run_id,
            write_run_manifest,
        )
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
        _model_hash = file_content_hash(os.environ.get("SHOWDOWN_RERANKER_MODEL_PATH")) if _reranker_on else None
        _model_manifest_hash = file_content_hash(os.environ.get("SHOWDOWN_RERANKER_MANIFEST_PATH")) if _reranker_on else None
        _cfg_hash_cache: dict = {}

        def _config_hash_for(agent, format_id):
            key = (agent, format_id)
            if key not in _cfg_hash_cache:
                # I7a-C P1.4: effective_config_manifest is the ONE shared assembly of
                # priors/spreads/movedata/provenance hashes -- a dedicated config-manifest
                # freeze helper (eval/config_manifest_freeze.py) calls the exact same
                # function, so the two paths cannot drift apart.
                manifest = effective_config_manifest(
                    agent=agent, format_id=format_id, env=_behavior_env,
                    model_hash=_model_hash, model_manifest_hash=_model_manifest_hash,
                )
                _cfg_hash_cache[key] = make_config_hash(manifest)
            return _cfg_hash_cache[key]

        # T3f Task 3: one run_id for the whole run + a self-describing manifest sidecar.
        # start_ts is captured ONCE here (so run_id is constant across rows, new per run);
        # the run-level config_hash uses the schedule's representative (agent, format).
        _start_ts = datetime.now(timezone.utc).isoformat()
        _run_config_hash = _config_hash_for(hero_agent, sched.rows[0].format_id)
        run_id = make_run_id(base, sched.schedule_hash, _run_config_hash, _start_ts)
        manifest = build_run_manifest(
            run_id=run_id, seed_base=base, schedule_hash=sched.schedule_hash,
            panel_hash=sched.panel_hash, config_hash=_run_config_hash, start_ts=_start_ts,
            pythonhashseed=os.environ.get("PYTHONHASHSEED"), cli_invocation=list(sys.argv),
            git_sha=git_sha, dirty=dirty, environment=collect_environment(),
        )
        manifest_out = write_run_manifest(result_out, manifest)
        print(f"  run manifest -> {manifest_out} (run_id={run_id})")

    # Task 4 (candidate-vs-baseline-diff): optional per-battle hero decision sidecar. Off by
    # default (decision_trace_out unset -> trace_writer stays None, byte-identical to every
    # prior run_schedule call). Requires --result-out (the trace binds into that row) --
    # transitively also requires SHOWDOWN_BATTLE_SEED_BASE, since --result-out already does.
    trace_out = getattr(args, "decision_trace_out", "")
    trace_writer = None
    if trace_out:
        if not result_out:
            raise SystemExit("--decision-trace-out requires --result-out")
        from showdown_bot.eval.decision_capture import BattleTraceContext, DecisionTraceWriter

        trace_writer = DecisionTraceWriter(trace_out)
        print(f"  decision trace -> {trace_out}")

    # 2c-Slice-0b Task 3: optional per-battle full-fidelity aggregation-trace sidecar. Off by
    # default (neither the flag nor the env alias set -> agg_writer stays None, byte-identical
    # to every prior run_schedule call). Requires --result-out (mirrors --decision-trace-out's
    # own gate) -- transitively also requires SHOWDOWN_BATTLE_SEED_BASE, since --result-out
    # already does. INDEPENDENT of --decision-trace-out: either, both, or neither may be given.
    #
    # SHOWDOWN_AGG_TRACE_OUT env alias (Task 5 Kaggle reachability): the datagen kernel builds a
    # HARDCODED argv (--schedule + --result-out only) and can inject per-run config ONLY via its
    # EXTRA_ENV passthrough (tools/kaggle/kernel_payload.py), so a CLI-only flag would silently
    # no-op in the datagen run that Task 5 needs. The flag WINS when both are set (an explicit
    # CLI override of the ambient env). config_env classifies SHOWDOWN_AGG_TRACE_OUT
    # NON_BEHAVIORAL (research-only IO path), so setting it never perturbs config_hash.
    agg_trace_out = getattr(args, "agg_trace_out", "") or os.environ.get("SHOWDOWN_AGG_TRACE_OUT", "")
    agg_writer = None
    if agg_trace_out:
        if not result_out:
            raise SystemExit("--agg-trace-out requires --result-out")
        from showdown_bot.research.aggregation_trace import AggTraceContext, AggTraceWriter

        agg_writer = AggTraceWriter(agg_trace_out)
        print(f"  agg trace -> {agg_trace_out}")

    # I7b-C Task 2 Step 6: optional opponent-Mega evidence sidecar. Off by default
    # (SHOWDOWN_OPP_MEGA_TRACE_OUT unset -> opp_mega_writer stays None, byte-identical to
    # every prior run_schedule call). Env-only, no CLI flag: the datagen/eval kernels inject
    # per-run config solely through their EXTRA_ENV passthrough, and config_env classifies
    # this var NON_BEHAVIORAL (an IO path), so setting it never perturbs config_hash --
    # unlike SHOWDOWN_OPP_MEGA_CLICK_RATE, which is BEHAVIOR_AFFECTING and must never be
    # confused with it.
    #
    # Requires --result-out for two independent reasons: evidence with no result row to join
    # against is unusable provenance, AND battle_id/config_id/config_hash are only computed
    # on that path at all -- without them the context could only be filled with placeholders.
    opp_mega_trace_out = os.environ.get("SHOWDOWN_OPP_MEGA_TRACE_OUT", "")
    opp_mega_writer = None
    if opp_mega_trace_out:
        if not result_out:
            raise SystemExit("SHOWDOWN_OPP_MEGA_TRACE_OUT requires --result-out")
        # Same fail-closed rule as --result-out's own T2-CC-2 gate: appending onto an
        # existing run's rows would interleave two runs into one file that later reads as a
        # single run, and the sidecar is provenance -- it must never silently mix.
        if os.path.exists(opp_mega_trace_out) and os.path.getsize(opp_mega_trace_out) > 0:
            raise SystemExit(
                f"SHOWDOWN_OPP_MEGA_TRACE_OUT {opp_mega_trace_out} already has rows; "
                f"must be non-existing or empty"
            )
        from showdown_bot.eval.opp_mega_trace import OppMegaTraceContext, OppMegaTraceWriter

        # ONE run-scoped writer for the whole schedule (every row appends to the same file);
        # the per-battle binding is the CONTEXT, built fresh per row below.
        opp_mega_writer = OppMegaTraceWriter(opp_mega_trace_out)
        print(f"  opp-mega trace -> {opp_mega_trace_out}")

    # I8-D: optional live decision-profile telemetry sidecar. Off by default
    # (SHOWDOWN_DECISION_PROFILE_OUT unset -> decision_profile_writer stays None, byte-identical
    # to every prior run_schedule call). Same env-only, NON_BEHAVIORAL IO-path contract as the
    # opp-mega sidecar above (config_env classifies it an IO path -> never perturbs config_hash),
    # and requires --result-out for the same two reasons: the live row's
    # battle_id/config_id/config_hash are only computed on that path, and a profile with no
    # result row to join against is unusable provenance.
    decision_profile_out = os.environ.get("SHOWDOWN_DECISION_PROFILE_OUT", "")
    decision_profile_writer = None
    calc_backend_name = "oneshot"
    if decision_profile_out:
        if not result_out:
            raise SystemExit("SHOWDOWN_DECISION_PROFILE_OUT requires --result-out")
        # Same fail-closed rule as --result-out's own T2-CC-2 gate and the opp-mega sidecar:
        # appending onto an existing run's rows would interleave two runs into one file that
        # later reads as a single run.
        if os.path.exists(decision_profile_out) and os.path.getsize(decision_profile_out) > 0:
            raise SystemExit(
                f"SHOWDOWN_DECISION_PROFILE_OUT {decision_profile_out} already has rows; "
                f"must be non-existing or empty"
            )
        # The provenance label for the calc backend this run configures, normalised EXACTLY as
        # make_calc_backend() selects it (engine/calc/client.py) and fail-closed on the same
        # unknown values -- so the row records the backend the client actually builds, in the
        # same process and env.
        _raw_calc_backend = os.environ.get("SHOWDOWN_CALC_BACKEND", "oneshot")
        if _raw_calc_backend in ("", "oneshot"):
            calc_backend_name = "oneshot"
        elif _raw_calc_backend == "persistent":
            calc_backend_name = "persistent"
        else:
            raise SystemExit(
                f"unknown SHOWDOWN_CALC_BACKEND={_raw_calc_backend!r} "
                f"(expected 'oneshot' or 'persistent')"
            )
        from showdown_bot.eval.decision_profile import DecisionProfileWriter, LiveProfileContext

        # ONE run-scoped writer for the whole schedule (live rows carry no manifest); the
        # per-battle binding is the CONTEXT, built fresh per row below.
        decision_profile_writer = DecisionProfileWriter(decision_profile_out, manifest=None)
        print(f"  decision profile -> {decision_profile_out}")

    totals = {"games": 0, "hero_wins": 0, "villain_wins": 0, "ties": 0, "invalid": 0, "crashes": 0}
    try:
        for row in sched.rows:  # loader-sorted by seed_index, contiguous from 0
            on_br = None
            trace_context = None
            agg_context = None
            opp_mega_context = None
            decision_profile_context = None
            if writer is not None:
                # Seed/battle_id/config_id/config_hash computed ONCE per battle, BEFORE the
                # battle runs (Task 4 needs battle_id up front to build trace_context) and
                # reused by on_br below instead of being recomputed at battle-end.
                seed = derive_battle_seed(base, row.seed_index)
                battle_id = make_battle_id(sched.schedule_hash, row.seed_index, seed)
                config_id, row_format_id = hero_agent, row.format_id  # bot version vs format (Fix 1)
                config_hash = _config_hash_for(config_id, row_format_id)
                if trace_writer is not None:
                    trace_context = BattleTraceContext(
                        battle_id=battle_id, seed_index=row.seed_index, config_id=config_id,
                        config_hash=config_hash, schedule_hash=sched.schedule_hash,
                        format_id=row_format_id, git_sha=git_sha,
                    )
                if agg_writer is not None:
                    # 2c-Slice-0b Task 3: INDEPENDENT of trace_context above -- built whenever
                    # agg_writer is on, regardless of whether --decision-trace-out is also given.
                    # our_side="p1" matches BattleTraceContext's own implicit default (never
                    # overridden above either); AggTraceContext has no default for it.
                    agg_context = AggTraceContext(
                        battle_id=battle_id, seed_index=row.seed_index, our_side="p1",
                        config_id=config_id, config_hash=config_hash,
                        schedule_hash=sched.schedule_hash, format_id=row_format_id,
                        git_sha=git_sha,
                    )
                if opp_mega_writer is not None:
                    # I7b-C Task 2 Step 6: a FRESH context per row, off the same real
                    # battle_id/config_hash computed above -- independent of both seams
                    # above. The run-scoped writer is shared by every battle; the context
                    # never is, or every row would carry the first battle's battle_id and
                    # the whole file would read as a single battle.
                    opp_mega_context = OppMegaTraceContext(
                        battle_id=battle_id, config_id=config_id, config_hash=config_hash,
                        schedule_hash=sched.schedule_hash, format_id=row_format_id,
                        git_sha=git_sha,
                    )
                if decision_profile_writer is not None:
                    # I8-D: a FRESH context per row off the same real battle_id/config_hash
                    # computed above -- independent of the seams above. Adds the calc_backend
                    # label (drives the row's backend_class) the other contexts don't carry.
                    decision_profile_context = LiveProfileContext(
                        battle_id=battle_id, config_id=config_id, config_hash=config_hash,
                        schedule_hash=sched.schedule_hash, format_id=row_format_id,
                        git_sha=git_sha, calc_backend=calc_backend_name,
                    )

                def on_br(record, _row=row, _battle_id=battle_id, _seed=seed,
                          _config_id=config_id, _format_id=row_format_id,
                          _config_hash=config_hash):  # noqa: B023 - defaults capture this iteration
                    # Task 4: bind the sidecar's count/sha256 into this row. {} (both None) when
                    # capture is off -- decision_trace_count/_sha256 are nullable fields.
                    trace_binding = trace_writer.finish_battle(_battle_id) if trace_writer is not None else {}
                    # 2c-Slice-0b Task 3: validate the agg-trace sidecar for this battle the same
                    # way -- finish_battle raises on a capture error or on zero rows for this
                    # battle (fail-fast, no partial/corrupt sidecar), keeping the same "no silent
                    # corruption" discipline as decision-trace above. Deliberate scope boundary:
                    # unlike decision-trace, this binding is NOT merged into the --result-out row
                    # -- eval/result_jsonl.py's closed field allowlist is untouched by this slice
                    # (Task 3 is scoped to client/gauntlet.py + cli.py only). The sidecar file
                    # itself (research.aggregation_trace.load_agg_trace) is the source of truth
                    # for the Task 4/5 probe, not this row.
                    if agg_writer is not None:
                        agg_writer.finish_battle(_battle_id)
                    writer.write({
                        "battle_id": _battle_id,
                        "run_id": run_id,  # T3f Task 3: constant across the run; matches manifest.run_id
                        "config_id": _config_id, "format_id": _format_id,
                        "config_hash": _config_hash,
                        "schedule_hash": sched.schedule_hash, "seed_index": _row.seed_index,
                        "opp_policy": _row.opp_policy, "hero_team_path": _row.hero_team_path,
                        "opp_team_path": _row.opp_team_path, "seed": _seed,
                        # T3f Task 2: raw base string (SHOWDOWN_BATTLE_SEED_BASE), NOT re-derived
                        # from seed. Lets T5 pair on (schedule_hash, seed_base, seed_index).
                        "seed_base": base, "git_sha": git_sha,
                        "dirty": dirty,  # T3e P4 provenance
                        # Provenance from the schedule row (legacy schedules -> null).
                        "hero_team_hash": _row.hero_team_hash, "opp_team_hash": _row.opp_team_hash,
                        "panel_split": _row.panel_split,  # T3f Task 4: "dev"/"heldout" or null
                        "timeouts": None, "panel_hash": sched.panel_hash,
                        "decision_trace_count": trace_binding.get("decision_trace_count"),
                        "decision_trace_sha256": trace_binding.get("decision_trace_sha256"),
                        **record,
                    })
                    written.append(_row.seed_index)

            stats = asyncio.run(
                run_local_gauntlet(
                    games=1,
                    hero_agent=hero_agent,
                    villain_agent=row.opp_policy,
                    format_id=row.format_id,
                    team_path=row.hero_team_path,
                    opp_team_path=row.opp_team_path,
                    on_battle_result=on_br,
                    export_runtime=export_runtime,  # 2b-2.5a: SAME runtime for every row
                    decision_trace_writer=trace_writer,  # Task 4: None unless --decision-trace-out
                    decision_trace_context=trace_context,
                    agg_trace_writer=agg_writer,  # 2c-Slice-0b Task 3: None unless --agg-trace-out
                    agg_trace_context=agg_context,
                    # I7b-C Task 2 Step 6: None unless SHOWDOWN_OPP_MEGA_TRACE_OUT is set.
                    opp_mega_trace_writer=opp_mega_writer,
                    opp_mega_trace_context=opp_mega_context,
                    # I8-D: None unless SHOWDOWN_DECISION_PROFILE_OUT is set.
                    decision_profile_writer=decision_profile_writer,
                    decision_profile_context=decision_profile_context,
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

    T4c R2: ``--room-raw`` (``args.room_raw``, optional) enables fail-closed row<->log
    re-derivation (``RunBundle.load(..., room_raw_dir=...)``); a ``LogIntegrityError`` there is
    likewise a clean SystemExit(1), not a traceback. Absent (the default, ``""``/unset), this
    function's behavior is byte-identical to before T4c.
    """
    import json as _json

    from showdown_bot.eval.report import (
        VERDICT_SAFETY_FAIL,
        VERDICT_SINGLE_FAIL,
        LogIntegrityError,
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

    room_raw_dir = getattr(args, "room_raw", "") or None

    try:
        bundle_a = RunBundle.load(
            args.run_a, args.seedlog_a, args.schedule, args.panel, teams_root=args.teams_root,
            room_raw_dir=room_raw_dir,
        )
        bundle_b = None
        if args.run_b:
            bundle_b = RunBundle.load(
                args.run_b, args.seedlog_b, args.schedule, args.panel, teams_root=args.teams_root,
                room_raw_dir=room_raw_dir,
            )
    except ReportInputError as exc:
        # Load-time input audit failure (unreadable/tampered/missing-sidecar input): a bare
        # SystemExit(1) so the numeric exit code matches the SAFETY-FAIL contract below exactly
        # (not just "truthy" via the string-to-1 coercion Python applies at process shutdown).
        print(f"eval-report: input audit failed: {exc}")
        raise SystemExit(1) from exc
    except LogIntegrityError as exc:
        # T4c R2: corrupted/forged evidence against --room-raw is a hard refusal, same exit
        # code contract as ReportInputError -- no report is written on a failed integrity audit.
        print(f"eval-report: room-log integrity check failed: {exc}")
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


def _run_decision_diff_impl(args) -> None:
    """Task 9: offline candidate-vs-baseline decision-diff report.

    Loads the baseline/candidate result JSONLs via the existing ``RunBundle.load`` (same
    input-audit/tamper checks as ``eval-report``), optionally validates their decision-trace
    sidecars (full mode), pairs+analyzes via ``analyze_decision_diff`` (which itself calls
    ``pair_runs`` -- see decision_diff.py), and writes ``report.md``/``report.json`` via
    ``build_report_object``/``render_markdown``. ``--outcome-only`` skips sidecar loading
    entirely and asks ``analyze_decision_diff`` for the outcome-only-flagged report (no
    decision-claim); full mode (the default) hard-requires both trace paths so a caller can
    never silently fall back to a weaker claim.
    """
    import json

    from showdown_bot.eval.decision_capture import load_decision_trace
    from showdown_bot.eval.decision_diff import analyze_decision_diff, validate_trace_run
    from showdown_bot.eval.decision_diff_report import build_report_object, render_markdown
    from showdown_bot.eval.panel import load_panel
    from showdown_bot.eval.report import RunBundle

    required = ("baseline_run", "baseline_seedlog", "candidate_run", "candidate_seedlog",
                "schedule", "panel", "out")
    missing = [name for name in required if not getattr(args, name, "")]
    if missing:
        raise SystemExit(f"decision-diff missing required inputs: {missing}")
    if not args.outcome_only and (not args.baseline_trace or not args.candidate_trace):
        raise SystemExit("full mode requires --baseline-trace and --candidate-trace")

    baseline = RunBundle.load(
        args.baseline_run, args.baseline_seedlog, args.schedule, args.panel,
        teams_root=args.teams_root, room_raw_dir=args.baseline_room_raw or None,
    )
    candidate = RunBundle.load(
        args.candidate_run, args.candidate_seedlog, args.schedule, args.panel,
        teams_root=args.teams_root, room_raw_dir=args.candidate_room_raw or None,
    )
    baseline_trace = candidate_trace = None
    if not args.outcome_only:
        baseline_trace = validate_trace_run(baseline.rows, load_decision_trace(args.baseline_trace))
        candidate_trace = validate_trace_run(candidate.rows, load_decision_trace(args.candidate_trace))
    panel = load_panel(args.panel, teams_root=args.teams_root)
    analysis = analyze_decision_diff(
        baseline, candidate, panel=panel,
        baseline_trace=baseline_trace, candidate_trace=candidate_trace,
        outcome_only=args.outcome_only,
        baseline_repeat=load_decision_trace(args.baseline_repeat_trace) if args.baseline_repeat_trace else None,
        candidate_repeat=load_decision_trace(args.candidate_repeat_trace) if args.candidate_repeat_trace else None,
    )
    obj = build_report_object(analysis)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(obj), encoding="utf-8", newline="\n")
    (out / "report.json").write_text(
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"decision-diff: wrote {out / 'report.md'} and {out / 'report.json'} "
          f"(capability_mode={obj['capability_mode']})")


def run_decision_diff(args) -> None:
    from showdown_bot.eval.decision_capture import DecisionCaptureError
    from showdown_bot.eval.decision_diff import DecisionDiffError
    from showdown_bot.eval.pairing import PairingError
    from showdown_bot.eval.report import LogIntegrityError, ReportInputError

    try:
        _run_decision_diff_impl(args)
    except (PairingError, ReportInputError, LogIntegrityError,
            DecisionCaptureError, DecisionDiffError) as exc:
        print(f"decision-diff: input/integrity failure: {exc}")
        raise SystemExit(1) from exc


def run_gauntlet(args) -> None:
    import os

    if getattr(args, "schedule", ""):
        run_schedule(args)
        return

    from showdown_bot.client.gauntlet import run_local_gauntlet

    # I7b-C Task 2 Step 6: this path has no schedule, so it computes no
    # battle_id/config_hash/schedule_hash and cannot build an OppMegaTraceContext. Silently
    # ignoring the env would leave an empty sidecar that later reads as "the bot generated
    # no foe-Mega hypotheses" -- a false claim about a run that never even had the seam on.
    # Fail closed and name the one supported path.
    if os.environ.get("SHOWDOWN_OPP_MEGA_TRACE_OUT", ""):
        raise SystemExit(
            "SHOWDOWN_OPP_MEGA_TRACE_OUT is only supported on the --schedule + --result-out "
            "path (the plain gauntlet has no battle_id/config_hash to bind evidence to)"
        )
    # I8-D: same reasoning for the live decision-profile sidecar -- this path builds no
    # battle_id/config_hash/schedule_hash, so it can never bind a live row. Silently ignoring
    # the env would leave an empty file that reads as "the bot made no scored decisions".
    if os.environ.get("SHOWDOWN_DECISION_PROFILE_OUT", ""):
        raise SystemExit(
            "SHOWDOWN_DECISION_PROFILE_OUT is only supported on the --schedule + --result-out "
            "path (the plain gauntlet has no battle_id/config_hash to bind a live row to)"
        )

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


def run_generalisation_analyze(args):
    from showdown_bot.analysis.generalisation.runner import analyze_runs
    report = analyze_runs(policy_path=args.analysis_policy, catalog_path=args.team_catalog,
        exposure_path=args.exposure, taxonomy_path=args.taxonomy,
        manifest_path=args.generalisation_manifest,
        panel_path=args.panel, schedule_path=args.schedule, run_a=args.run_a,
        seedlog_a=args.seedlog_a, room_raw_a=args.room_raw_a,
        run_manifest_a=args.manifest_a or None,
        run_b=args.run_b or None, seedlog_b=args.seedlog_b or None,
        room_raw_b=args.room_raw_b or None,
        run_manifest_b=args.manifest_b or None, teams_root=args.teams_root, out_dir=args.out,
        overwrite=args.overwrite)
    if report["status"] in {"INVALID", "INCONCLUSIVE", "REGRESSION"}:
        raise SystemExit(1)


def run_generalisation_plan(args):
    from showdown_bot.analysis.generalisation.runner import plan_schedule
    plan_schedule(policy_path=args.analysis_policy, catalog_path=args.team_catalog,
        exposure_path=args.exposure, manifest_path=args.generalisation_manifest,
        panel_path=args.panel,
        out_dir=args.out,
        teams_root=args.teams_root, mode=args.planner_mode,
        confirm_heldout=args.confirm_heldout,
        ledger_path=args.ledger, purpose=args.purpose, git_sha=args.git_sha,
        justification=args.justification, overwrite=args.overwrite)


def run_i8d_gate(args) -> None:
    """The executable, provenance-locked I8-D live-latency gate (code-review findings 4, 5).

    The ONLY authorizable command that drives the exposure-stop loop and renders the three-way
    verdict. Everything is derived and verified here rather than trusted: provenance comes from the
    real repo/env (``resolve_i8d_provenance``, fail-closed), the schedule is BUILT from the panel
    and re-locked by the runner, the seed namespace + server seed log are proven, and no partial
    battle is adopted. Starts a real server + battles when run -- gated by explicit authorization.
    """
    import os

    from showdown_bot.eval.i8d_runner import (
        I8D_MAX_BATTLES,
        build_i8d_live_schedule,
        resolve_i8d_provenance,
        run_i8d_live_gate,
    )
    from showdown_bot.eval.i8d_schedule import I8D_PANEL_PATH, verify_i8d_panel_and_teams

    out_dir = getattr(args, "out_dir", "")
    if not out_dir:
        raise SystemExit("i8d-live-gate requires --out-dir")
    seed_log = os.environ.get("SHOWDOWN_EVAL_SEED_LOG", "")
    if not seed_log:
        raise SystemExit(
            "i8d-live-gate requires SHOWDOWN_EVAL_SEED_LOG (the server's seed log) so the played "
            "seeds can be proven -- the server must be started with it and SHOWDOWN_BATTLE_SEED_BASE"
        )
    teams_root = getattr(args, "teams_root", ".") or "."

    prov = resolve_i8d_provenance()   # fail-closed git_sha / config_hash / calc_backend
    # (blocker 2) the panel path is LOCKED to the canonical champions panel (not caller-chosen), and
    # the panel + team CONTENTS are re-verified from disk before battle 1: panel_hash against the
    # frozen champions value + every team file re-hashed.
    schedule = build_i8d_live_schedule(I8D_PANEL_PATH, n_battles=I8D_MAX_BATTLES, teams_root=teams_root)
    verify_i8d_panel_and_teams(schedule, teams_root=teams_root)
    print(f"i8d-live-gate: schedule_hash={schedule.schedule_hash} panel_hash={schedule.panel_hash} "
          f"git_sha={prov['git_sha']} config_hash={prov['config_hash']} "
          f"calc_backend={prov['calc_backend']}")
    report = run_i8d_live_gate(
        schedule=schedule, out_dir=out_dir, seed_log_path=seed_log,
        config_hash=prov["config_hash"], git_sha=prov["git_sha"], calc_backend=prov["calc_backend"],
        hero_agent=prov["hero_agent"], expected_battles=I8D_MAX_BATTLES,
        # (team-path wiring fix) the SAME execution root verify_i8d_panel_and_teams hashed against,
        # now threaded into the battle team loading so the gauntlet finds the team files regardless
        # of the process CWD (the panel path stays repo-root-relative; the teams live under it).
        teams_root=teams_root)
    print(f"i8d-live-gate verdict: {report['verdict']} "
          f"(active={report['active_valid_decisions']} from {report['distinct_active_battles']} "
          f"battles, battles_played={report['battles_played']}, p95_ms={report['p95_ms']}, "
          f"stop={report['stop_reason']}) -> {out_dir}/")


def run_coverage_gate_cli(args) -> None:
    """The executable, provenance-locked opponent-Mega coverage gate (Task 7).

    Mirrors ``run_i8d_gate``: the coverage panel + manifest are LOCKED (not caller-chosen),
    provenance is DERIVED inside ``run_coverage_gate`` (fail-closed, never caller-supplied), the
    panel + team CONTENTS are re-verified from disk before battle 1, and the hardened coverage runner
    drives the fixed schedule. Built and authorizable; starts a real server + battles ONLY when
    explicitly run under separate authorization.
    """
    import os

    from showdown_bot.eval.coverage_runner import build_coverage_live_schedule, run_coverage_gate
    from showdown_bot.eval.coverage_schedule import (
        COVERAGE_MANIFEST_PATH,
        COVERAGE_MAX_BATTLES,
        COVERAGE_PANEL_PATH,
        verify_coverage_panel_and_teams,
    )

    out_dir = getattr(args, "out_dir", "")
    if not out_dir:
        raise SystemExit("champions-coverage-gate requires --out-dir")
    seed_log = os.environ.get("SHOWDOWN_EVAL_SEED_LOG", "")
    if not seed_log:
        raise SystemExit(
            "champions-coverage-gate requires SHOWDOWN_EVAL_SEED_LOG (the server's seed log) so the "
            "played seeds can be proven -- the server must be started with it and SHOWDOWN_BATTLE_SEED_BASE"
        )
    i8d_verdict_path = getattr(args, "i8d_verdict_path", "")
    if not i8d_verdict_path:
        raise SystemExit("champions-coverage-gate requires --i8d-verdict-path")
    teams_root = getattr(args, "teams_root", ".") or "."

    # the panel + manifest are LOCKED to the coverage ones (not caller-chosen); the panel + team
    # CONTENTS are re-verified from disk before battle 1 (panel_hash + every team file re-hashed).
    schedule = build_coverage_live_schedule(
        COVERAGE_PANEL_PATH, COVERAGE_MANIFEST_PATH, n_battles=COVERAGE_MAX_BATTLES, teams_root=teams_root)
    verify_coverage_panel_and_teams(schedule, teams_root=teams_root)
    print(f"champions-coverage-gate: schedule_hash={schedule.schedule_hash} "
          f"panel_hash={schedule.panel_hash}")
    report = run_coverage_gate(
        schedule=schedule, out_dir=out_dir, seed_log_path=seed_log,
        expected_battles=COVERAGE_MAX_BATTLES, teams_root=teams_root,
        i8d_verdict_path=i8d_verdict_path)
    print(f"champions-coverage-gate verdict: {report['verdict']} "
          f"(stop={report['stop_reason']}, safety_violations={report['safety_violations']}, "
          f"candidate_identity={report['candidate_identity']}) -> {out_dir}/")


def _load_holdout_content_hashes(teams_root: str) -> dict:
    """Read the six holdout ``{team_id: team_content_hash}`` from the AUTHORITATIVE holdout manifest
    (Amendment A1.1 -- the manifest is the single source of these IDs; nothing hardcodes them).
    Resolved under ``teams_root`` (Gate B's repo-root geometry). Every malformed/missing/degenerate
    shape becomes a clean ``GateBAbort`` -- never a raw ``OSError``/``JSONDecodeError``/``KeyError``
    -- so both CLI handlers stop fail-closed, before any runner/combiner call and before any
    battle or publish (Task 13 step 3)."""
    import json
    import os

    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    from showdown_bot.eval.strength_holdout_schedule import STRENGTH_HOLDOUT_MANIFEST_PATH

    path = os.path.join(teams_root or ".", STRENGTH_HOLDOUT_MANIFEST_PATH)
    try:
        man = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateBAbort(f"could not read the holdout manifest at {path!r}: {exc}") from exc
    if not isinstance(man, dict) or not isinstance(man.get("teams"), list):
        raise GateBAbort(f"holdout manifest at {path!r} must be an object with a 'teams' list")
    hashes: dict[str, str] = {}
    for i, entry in enumerate(man["teams"]):
        if not isinstance(entry, dict):
            raise GateBAbort(f"holdout manifest teams[{i}] must be an object")
        team_id, content_hash = entry.get("team_id"), entry.get("team_content_hash")
        if not (isinstance(team_id, str) and team_id.strip()
                and isinstance(content_hash, str) and content_hash.strip()):
            raise GateBAbort(
                f"holdout manifest teams[{i}] has a blank/non-string team_id or team_content_hash"
            )
        if team_id in hashes:
            raise GateBAbort(f"holdout manifest has a duplicate team_id {team_id!r}")
        hashes[team_id] = content_hash
    if len(hashes) != 6:
        raise GateBAbort(f"holdout manifest must register exactly six teams, got {len(hashes)}")
    return hashes


def _load_gate_b_panel_hash(teams_root: str) -> str:
    """``panel_hash`` of the real Gate B panel, resolved under ``teams_root`` (repo-root geometry).
    Any load/parse failure -- missing file, malformed YAML, or a panel-schema violation -- becomes a
    clean ``GateBAbort`` rather than a raw traceback."""
    import os

    import yaml

    from showdown_bot.eval.panel import PanelError, load_panel
    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    from showdown_bot.eval.strength_holdout_schedule import STRENGTH_HOLDOUT_PANEL_PATH

    root = teams_root or "."
    panel_path = os.path.join(root, STRENGTH_HOLDOUT_PANEL_PATH)
    try:
        return load_panel(panel_path, teams_root=root).panel_hash
    except (PanelError, OSError, yaml.YAMLError) as exc:
        raise GateBAbort(f"could not load the Gate B panel at {panel_path!r}: {exc}") from exc


def _load_and_verify_frozen_gate_b_identity(teams_root: str) -> str:
    """Bind the on-disk panel and holdout manifest to their FROZEN identities (Task 13 step-3
    hash-freeze) and return the verified ``panel_hash`` -- BEFORE any battle or verdict.

    P1 fix: sourcing the panel/manifest and re-hashing team content internally is not enough. A
    *consistent* drift -- the panel, the manifest, and the baseline edited together to a different
    six teams -- passes ``verify_strength_holdout_baseline`` (which only checks those three agree
    with each other and with disk). The frozen constants are the external anchor a re-sealed or
    swapped holdout can never satisfy, so the arm must refuse before battle 1 and combine before it
    publishes a verdict. Fail-closed ``GateBAbort``.
    """
    import os

    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    from showdown_bot.eval.strength_holdout_schedule import (
        STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH, STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH,
        STRENGTH_HOLDOUT_MANIFEST_PATH, strength_holdout_manifest_hash,
    )

    panel_hash = _load_gate_b_panel_hash(teams_root)
    if panel_hash != STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH:
        raise GateBAbort(
            f"Gate B panel drift: on-disk panel_hash {panel_hash!r} != frozen "
            f"{STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH!r} -- refusing before battle 1"
        )
    try:
        manifest_hash = strength_holdout_manifest_hash(
            os.path.join(teams_root or ".", STRENGTH_HOLDOUT_MANIFEST_PATH)
        )
    except ValueError as exc:
        raise GateBAbort(f"could not hash the holdout manifest: {exc}") from exc
    if manifest_hash != STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH:
        raise GateBAbort(
            f"Gate B holdout-manifest drift: on-disk manifest hash {manifest_hash!r} != frozen "
            f"{STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH!r} -- refusing before battle 1"
        )
    return panel_hash


def run_strength_holdout_arm_cli(args) -> int:
    """Gate B, one arm of the 180-battle-key strength holdout (plan §14, Task 11; WIRED in Task 13
    step 3).

    Sources the six holdout IDs + content hashes from the authoritative manifest, builds the real
    180-key schedule from the real panel, and plays the arm via ``run_strength_holdout_arm``.
    ``date_stratum_id`` is required (enforced by ``main`` via ``parser.error``); ``stratum_override``
    is optional and threads into ``detect_stratum`` (needed for a real Kaggle run). Every
    data-sourcing / runner failure is a clean ``GateBAbort``/``UnattestedStratumError`` mapped to a
    named stderr line + exit 1 -- never a traceback and never a half-built publish.
    """
    import sys

    from showdown_bot.eval.strata_guard import UnattestedStratumError
    from showdown_bot.eval.strength_holdout_runner import GateBAbort, run_strength_holdout_arm
    from showdown_bot.eval.strength_holdout_schedule import (
        STRENGTH_HOLDOUT_SEED_BASE, build_strength_holdout_schedule,
    )

    try:
        content_hashes = _load_holdout_content_hashes(args.teams_root)
        # P1: bind the frozen panel + manifest identity BEFORE building the schedule or playing.
        panel_hash = _load_and_verify_frozen_gate_b_identity(args.teams_root)
        schedule = build_strength_holdout_schedule(
            holdout_team_ids=sorted(content_hashes), panel_hash=panel_hash,
            seed_base=STRENGTH_HOLDOUT_SEED_BASE,
        )
        run_strength_holdout_arm(
            hero_agent=args.hero_agent, schedule=schedule, out_dir=args.out_dir,
            seed_log_path=args.seed_log_path, holdout_team_content_hashes=content_hashes,
            date_stratum_id=args.date_stratum_id, teams_root=args.teams_root,
            stratum_env_override=(args.stratum_override or None),
        )
        return 0
    except (GateBAbort, UnattestedStratumError) as exc:
        # Every exception reachable from the arm's data-sourcing + run_strength_holdout_arm call
        # graph is GateBAbort (the loaders above wrap OSError/JSON/YAML/PanelError into it), with
        # detect_stratum's own UnattestedStratumError the one sibling class -- hence the two-class
        # tuple (Rev. 9 §1h / Rev. 15 §1n).
        print(f"champions-strength-holdout-arm: {exc}", file=sys.stderr)
        return 1


def _describe_strength_holdout_combine_error(exc: BaseException) -> tuple[str, int]:
    """NF4 fix (Rev. 8): ``combine_strength_holdout_arms`` can raise 7 exception CLASSES across 4
    meaningfully DISTINCT message/exit-code CATEGORIES (§1f/§1g's audit table) -- Task 10
    deliberately keeps these distinct rather than folding all of them into ``GateBAbort``:

    1. ``GateBAbort`` -- the row-schema/manifest/upstream-verdict/pairing/ledger/git-infra trust
       chain, exit 1.
    2. ``AccessBudgetError`` -- a policy refusal with a defined override (pass a justification),
       not a technical failure; collapsing it would hide the one exception an operator may
       legitimately overrule, exit 2.
    3. ``HoldoutNotDisjointError``/``LeakageDriftError``/``StrataPoolingError``/
       ``UnattestedStratumError`` -- four DIFFERENT classes, ONE category: integrity judgments
       about the holdout itself, exit 3.
    4. ``LeakageScanError`` -- the scan could not even run; neither a policy refusal nor an
       integrity judgment, exit 4. Checked BEFORE ``LeakageDriftError`` would be reached, because
       "couldn't check" must never read as "checked, found a problem".

    Returns ``(message, exit_code)``. Deliberately does not recognize anything outside those 7
    classes -- an unrecognized type raises ``TypeError`` rather than being mislabeled.
    """
    from showdown_bot.eval.heldout_ledger import AccessBudgetError
    from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    from showdown_bot.eval.strata_guard import StrataPoolingError, UnattestedStratumError
    from showdown_bot.eval.strength_holdout_runner import GateBAbort

    if isinstance(exc, AccessBudgetError):
        return (
            f"ledger budget refused: {exc} (this is a policy decision, not a technical failure "
            "-- pass a justification to override it if that override is warranted)", 2,
        )
    if isinstance(exc, LeakageScanError):
        return (f"leakage scan could not be completed: {exc}", 4)
    if isinstance(exc, (HoldoutNotDisjointError, LeakageDriftError, StrataPoolingError, UnattestedStratumError)):
        return (f"holdout integrity check failed: {exc}", 3)
    if isinstance(exc, GateBAbort):
        return (str(exc), 1)
    raise TypeError(
        f"unrecognized exception type for the strength-holdout combine CLI: {type(exc).__name__}"
    ) from exc


def run_strength_holdout_combine_cli(args) -> int:
    """Gate B, combine the two published arms into a verdict (plan §14, Task 11; WIRED in Task 13
    step 3).

    Sources the six holdout content hashes from the authoritative manifest (the species side is NOT
    a CLI concern -- ``combine_strength_holdout_arms`` derives both species mappings from the real
    sealed ``.packed`` files, Task 10 review-fix) and runs the real combiner. ``stratum_override``
    is passed only as an EXPECTATION checked against the arms' own recorded stratum -- combine never
    re-detects the stratum here. The seven combine exception classes map to four exit codes via
    ``_describe_strength_holdout_combine_error`` (NF4, §1f/§1g).
    """
    import sys

    from showdown_bot.eval.heldout_ledger import AccessBudgetError
    from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    from showdown_bot.eval.strata_guard import StrataPoolingError, UnattestedStratumError
    from showdown_bot.eval.strength_holdout_runner import GateBAbort, combine_strength_holdout_arms

    try:
        content_hashes = _load_holdout_content_hashes(args.teams_root)
        # P1: bind the frozen panel + manifest identity before publishing any verdict.
        _load_and_verify_frozen_gate_b_identity(args.teams_root)
        combine_strength_holdout_arms(
            arm_a_dir=args.arm_a_dir, arm_b_dir=args.arm_b_dir, out_dir=args.out_dir,
            i8d_verdict_path=args.i8d_verdict_path,
            coverage_verdict_path=args.coverage_verdict_path,
            holdout_content_hashes=content_hashes,
            repo_root=(args.teams_root or "."), teams_root=(args.teams_root or "."),
            stratum_env_override=(args.stratum_override or None),
        )
        return 0
    except (GateBAbort, AccessBudgetError, HoldoutNotDisjointError, LeakageDriftError,
            LeakageScanError, StrataPoolingError, UnattestedStratumError) as exc:
        # NF4 fix (Rev. 8): the seven combine exception classes across four categories -- the
        # data-sourcing loader wraps its own OSError/JSON into GateBAbort, and combine itself raises
        # the other six; _describe_strength_holdout_combine_error maps each to its exit code.
        message, code = _describe_strength_holdout_combine_error(exc)
        print(f"champions-strength-holdout-combine: {message}", file=sys.stderr)
        return code


def _build_parser() -> argparse.ArgumentParser:
    """Parser construction split out from ``main`` so tests can drive the REAL parser (e.g. to
    prove a new global flag's default doesn't break other commands) without executing dispatch."""
    parser = argparse.ArgumentParser(description="VGC Showdown Bot")
    parser.add_argument(
        "command",
        choices=["ladder", "challenge", "smoke", "replay-fixture", "validate-log", "gauntlet",
                 "eval-report", "decision-diff", "generalisation-plan", "generalisation-analyze",
                 "i8d-live-gate", "champions-coverage-gate",
                 "champions-strength-holdout-arm", "champions-strength-holdout-combine"],
        help="ladder/challenge/smoke/replay-fixture/validate-log/gauntlet/eval-report/"
        "decision-diff/generalisation-plan/generalisation-analyze/i8d-live-gate/champions-coverage-gate/"
        "champions-strength-holdout-arm/champions-strength-holdout-combine",
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
        "--decision-trace-out",
        dest="decision_trace_out",
        default="",
        help="Optional hero decision sidecar for gauntlet --schedule; requires --result-out.",
    )
    parser.add_argument(
        "--agg-trace-out",
        dest="agg_trace_out",
        default="",
        help="Optional hero full-fidelity aggregation-trace sidecar for gauntlet --schedule "
        "(2c-Slice-0b); requires --result-out. Independent of --decision-trace-out -- either, "
        "both, or neither may be given. The SHOWDOWN_AGG_TRACE_OUT env var is an alias for this "
        "flag (the flag wins if both are set) and is what the Kaggle datagen kernel uses, since "
        "it injects config only via EXTRA_ENV, not extra CLI flags.",
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
        "--out-dir",
        dest="out_dir",
        default="",
        help="Output directory for the I8-D gate (i8d-live-gate, required): profile.jsonl + "
        "verdict.json are published together via one atomic rename from a run-staging dir. Must "
        "NOT already exist -- a restart runs from seed 0 into a fresh directory, never merges.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output directory for report.md + report.json (eval-report, required); "
        "created if missing.",
    )
    parser.add_argument(
        "--i8d-verdict-path",
        dest="i8d_verdict_path",
        default="",
        help="Path to the I8-D gate's verdict.json for the SAME candidate (champions-coverage-gate, "
        "required): the runner refuses to run unless that verdict's candidate_identity matches this "
        "run's freshly-derived one AND its verdict is 'PASS'. Global default is empty so other "
        "commands are unaffected; only champions-coverage-gate's own handler requires it.",
    )
    # Gate B (strength holdout, Task 11). All five are GLOBAL flags with an empty default, like
    # --i8d-verdict-path above and for the same reason: this CLI has a single flat `command`
    # positional, not argparse subparsers, so `required=True` on any of them would make EVERY
    # other command (ladder, smoke, gauntlet, ...) refuse to start. Per-command required-ness is
    # enforced in main() via parser.error(), exactly as generalisation-plan/-analyze already do.
    parser.add_argument(
        "--hero-agent",
        dest="hero_agent",
        default="",
        help="Which arm to play for champions-strength-holdout-arm (required for it): "
        "'heuristic' is Candidate A, 'max_damage' is Baseline B.",
    )
    parser.add_argument(
        "--seed-log-path",
        dest="seed_log_path",
        default="",
        help="Path the server's seed log is written to (champions-strength-holdout-arm, "
        "required): the arm refuses to run unless the log is built during this very run.",
    )
    parser.add_argument(
        "--arm-a-dir",
        dest="arm_a_dir",
        default="",
        help="Published Candidate-A arm directory (champions-strength-holdout-combine, required).",
    )
    parser.add_argument(
        "--arm-b-dir",
        dest="arm_b_dir",
        default="",
        help="Published Baseline-B arm directory (champions-strength-holdout-combine, required).",
    )
    parser.add_argument(
        "--coverage-verdict-path",
        dest="coverage_verdict_path",
        default="",
        help="Path to the Coverage gate's verdict.json for the SAME candidate "
        "(champions-strength-holdout-combine, required): Gate B may only run after an I8-D PASS "
        "AND a Coverage PASS. Global default is empty so other commands are unaffected.",
    )
    parser.add_argument(
        "--date-stratum-id",
        dest="date_stratum_id",
        default="",
        help="Pre-registered date/stratum identifier for champions-strength-holdout-arm (required "
        "for it; whitespace-only is treated as missing): fixed before the run, threaded unchanged "
        "into the arm's provenance (DESIGN sec 3.5 -- 'a Kaggle strength stratum is a separate "
        "pre-registered run'). Global default empty so other commands are unaffected.",
    )
    parser.add_argument(
        "--stratum-override",
        dest="stratum_override",
        default="",
        choices=["windows", "kaggle"],
        help="Optional explicit hardware stratum. For champions-strength-holdout-arm it is passed "
        "to detect_stratum (required for a real Kaggle run, which detect_stratum refuses to guess "
        "from a bare non-Windows platform read); for champions-strength-holdout-combine it is ONLY "
        "an expectation checked against the arms' own recorded stratum, never a re-detection. "
        "Empty default (auto-detect / no expectation).",
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
    parser.add_argument(
        "--room-raw",
        dest="room_raw",
        default="",
        help="Directory of committed room_raw logs (eval-report, optional; T4c R2). When "
        "given, every row's winner/turns/end_reason/end_hp_diff (and normalized-log sha, for "
        "rows that carry one) are re-derived from the row's room log -- resolved by basename "
        "under this directory -- and compared against the row; any mismatch or missing log "
        "raises LogIntegrityError (fail-closed, no partial verdict). Omit for the original "
        "behavior: byte-identical reports, no room_raw access.",
    )
    parser.add_argument("--analysis-policy", default="")
    parser.add_argument("--team-catalog", default="")
    parser.add_argument("--exposure", default="")
    parser.add_argument("--taxonomy", default="")
    parser.add_argument("--generalisation-manifest", default="")
    parser.add_argument("--room-raw-a", default="")
    parser.add_argument("--room-raw-b", default="")
    parser.add_argument("--manifest-a", default="")
    parser.add_argument("--manifest-b", default="")
    parser.add_argument("--planner-mode",
                        choices=("fresh", "dev-supplement", "heldout-fresh"), default="fresh")
    parser.add_argument("--confirm-heldout", action="store_true")
    parser.add_argument("--ledger", default="")
    parser.add_argument("--purpose", default="")
    parser.add_argument("--git-sha", default="")
    parser.add_argument("--justification", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--baseline-run",
        dest="baseline_run",
        default="",
        help="Path to the baseline run's per-battle result JSONL (decision-diff, required).",
    )
    parser.add_argument(
        "--baseline-seedlog",
        dest="baseline_seedlog",
        default="",
        help="Path to the baseline run's seed log (decision-diff, required).",
    )
    parser.add_argument(
        "--baseline-trace",
        dest="baseline_trace",
        default="",
        help="Path to the baseline run's decision-trace sidecar (decision-diff full mode; "
        "required unless --outcome-only).",
    )
    parser.add_argument(
        "--baseline-repeat-trace",
        dest="baseline_repeat_trace",
        default="",
        help="Optional second decision-trace sidecar for the baseline run, for the "
        "determinism/stability block (decision-diff).",
    )
    parser.add_argument(
        "--baseline-room-raw",
        dest="baseline_room_raw",
        default="",
        help="Optional room_raw log directory for the baseline run (decision-diff; see "
        "eval-report's --room-raw).",
    )
    parser.add_argument(
        "--candidate-run",
        dest="candidate_run",
        default="",
        help="Path to the candidate run's per-battle result JSONL (decision-diff, required).",
    )
    parser.add_argument(
        "--candidate-seedlog",
        dest="candidate_seedlog",
        default="",
        help="Path to the candidate run's seed log (decision-diff, required).",
    )
    parser.add_argument(
        "--candidate-trace",
        dest="candidate_trace",
        default="",
        help="Path to the candidate run's decision-trace sidecar (decision-diff full mode; "
        "required unless --outcome-only).",
    )
    parser.add_argument(
        "--candidate-repeat-trace",
        dest="candidate_repeat_trace",
        default="",
        help="Optional second decision-trace sidecar for the candidate run, for the "
        "determinism/stability block (decision-diff).",
    )
    parser.add_argument(
        "--candidate-room-raw",
        dest="candidate_room_raw",
        default="",
        help="Optional room_raw log directory for the candidate run (decision-diff; see "
        "eval-report's --room-raw).",
    )
    parser.add_argument(
        "--outcome-only",
        dest="outcome_only",
        action="store_true",
        help="decision-diff: run outcome-only mode from result rows alone (no decision-trace "
        "sidecars required); the report is flagged capability_mode=outcome_only and carries "
        "no decision-level claim. Default off (full mode), which requires --baseline-trace "
        "and --candidate-trace.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
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

    if args.command == "generalisation-plan":
        required = (args.analysis_policy, args.team_catalog, args.exposure,
                    args.generalisation_manifest, args.panel, args.out)
        if not all(required):
            parser.error("generalisation-plan requires policy, catalog, exposure, manifest, panel and out")
        run_generalisation_plan(args)
        return

    if args.command == "generalisation-analyze":
        required = (args.analysis_policy, args.team_catalog, args.exposure, args.taxonomy,
                    args.generalisation_manifest, args.panel, args.schedule, args.run_a,
                    args.seedlog_a, args.room_raw_a, args.out)
        if not all(required):
            parser.error("generalisation-analyze is missing a required offline input")
        if bool(args.run_b) != bool(args.seedlog_b) or bool(args.run_b) != bool(args.room_raw_b):
            parser.error("run-b, seedlog-b and room-raw-b must be supplied together")
        run_generalisation_analyze(args)
        return

    if args.command == "decision-diff":
        run_decision_diff(args)
        return

    if args.command == "i8d-live-gate":
        run_i8d_gate(args)
        return

    if args.command == "champions-coverage-gate":
        run_coverage_gate_cli(args)
        return

    if args.command == "champions-strength-holdout-arm":
        # parser.error() (not argparse `required=True`) because these are shared GLOBAL flags --
        # see the Gate B block in _build_parser. It is still argparse's own error path: usage to
        # stderr, exit 2, same as generalisation-plan's existing check.
        missing = [
            flag for flag, value in (
                ("--hero-agent", args.hero_agent), ("--out-dir", args.out_dir),
                ("--seed-log-path", args.seed_log_path), ("--teams-root", args.teams_root),
                ("--date-stratum-id", args.date_stratum_id),
            ) if not (value or "").strip()  # whitespace-only counts as missing (date-stratum-id)
        ]
        if missing:
            parser.error(f"champions-strength-holdout-arm requires {', '.join(missing)}")
        raise SystemExit(run_strength_holdout_arm_cli(args))

    if args.command == "champions-strength-holdout-combine":
        missing = [
            flag for flag, value in (
                ("--arm-a-dir", args.arm_a_dir), ("--arm-b-dir", args.arm_b_dir),
                ("--out-dir", args.out_dir), ("--i8d-verdict-path", args.i8d_verdict_path),
                ("--coverage-verdict-path", args.coverage_verdict_path),
            ) if not value
        ]
        if missing:
            parser.error(f"champions-strength-holdout-combine requires {', '.join(missing)}")
        raise SystemExit(run_strength_holdout_combine_cli(args))

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

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

    from showdown_bot.client.gauntlet import run_local_gauntlet
    from showdown_bot.eval.schedule import load_schedule, verify_schedule_alignment

    sched = load_schedule(args.schedule)
    print(f"schedule {args.schedule}: {len(sched.rows)} rows, schedule_hash={sched.schedule_hash}")
    if os.environ.get("SHOWDOWN_BATTLE_SEED_BASE"):
        print("  seed mode: per-battle (SHOWDOWN_BATTLE_SEED_BASE) — REQUIRES a fresh server (Channel A)")

    totals = {"games": 0, "hero_wins": 0, "villain_wins": 0, "ties": 0, "invalid": 0, "crashes": 0}
    for row in sched.rows:  # loader-sorted by seed_index, contiguous from 0
        stats = asyncio.run(
            run_local_gauntlet(
                games=1,
                hero_agent="heuristic",
                villain_agent=row.opp_policy,
                format_id=row.config_id,
                team_path=row.hero_team_path,
                opp_team_path=row.opp_team_path,
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
    print(f"schedule totals: {totals}")

    seed_log = os.environ.get("SHOWDOWN_EVAL_SEED_LOG")
    base = os.environ.get("SHOWDOWN_BATTLE_SEED_BASE")
    if seed_log and base:
        verify_schedule_alignment(sched, seed_log, base)  # raises on retry/extra/misalign
        print(f"seed-log alignment OK: {len(sched.rows)} battles, seed_i == derive_battle_seed(base, seed_index)")
    else:
        print("seed-log alignment SKIPPED (SHOWDOWN_BATTLE_SEED_BASE / SHOWDOWN_EVAL_SEED_LOG not both set)")


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
        choices=["ladder", "challenge", "smoke", "replay-fixture", "validate-log", "gauntlet"],
        help="ladder/challenge/smoke/replay-fixture/validate-log/gauntlet",
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
    parser.add_argument(
        "--villain",
        default="max_damage",
        choices=["max_damage", "random", "heuristic"],
        help="Baseline opponent agent (gauntlet)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce Phase 2 exit thresholds and exit non-zero on failure (gauntlet)",
    )
    parser.add_argument(
        "--schedule",
        default="",
        help="Path to a non-mirror eval schedule YAML (gauntlet). Runs each row as one "
        "battle in seed_index order; requires a fresh server when using "
        "SHOWDOWN_BATTLE_SEED_BASE (Channel A).",
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

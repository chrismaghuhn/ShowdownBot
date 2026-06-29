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


def main() -> None:
    parser = argparse.ArgumentParser(description="VGC Showdown Bot")
    parser.add_argument(
        "command",
        choices=["ladder", "challenge", "smoke", "replay-fixture", "validate-log"],
        help="ladder/challenge/smoke/replay-fixture/validate-log",
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
        default="gen9vgc2026regi",
        help="Format id for config/spread selection (validate-log)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.command == "replay-fixture":
        print(replay_request_fixture(args.fixture, seed=args.seed))
        return

    if args.command == "validate-log":
        run_validate_log(args)
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

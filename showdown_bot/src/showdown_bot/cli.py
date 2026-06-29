from __future__ import annotations

import argparse
import asyncio
import logging

from showdown_bot.client.fixture_runner import replay_request_fixture
from showdown_bot.client.runner import run_ladder_search
from showdown_bot.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="VGC Showdown Bot")
    parser.add_argument(
        "command",
        choices=["ladder", "replay-fixture"],
        help="Run bot on ladder or replay a request fixture offline",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if args.command == "replay-fixture":
        print(replay_request_fixture(args.fixture, seed=args.seed))
        return
    settings = Settings.from_env()
    if args.command == "ladder":
        asyncio.run(run_ladder_search(settings))


if __name__ == "__main__":
    main()

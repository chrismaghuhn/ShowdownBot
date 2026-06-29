from __future__ import annotations

import argparse
import asyncio
import logging

from showdown_bot.client.runner import run_ladder_search
from showdown_bot.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="VGC Showdown Bot")
    parser.add_argument("command", choices=["ladder"], help="Run bot on ladder")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    settings = Settings.from_env()
    if args.command == "ladder":
        asyncio.run(run_ladder_search(settings))


if __name__ == "__main__":
    main()
